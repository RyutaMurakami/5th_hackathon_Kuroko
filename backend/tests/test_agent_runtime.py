import json

import httpx
import pytest

from src.clients.agent_runtime import (
    AgentRuntimeClient,
    AgentRuntimeError,
    SessionNotFound,
    extract_text,
)
from src.db.agent_sessions import MemorySessionStore
from src.services import kuroko_chat

ENGINE = "projects/123/locations/us-central1/reasoningEngines/456"


def ndjson(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events) + "\n"


def model(text: str, **extra) -> dict:
    return {"content": {"role": "model", "parts": [{"text": text}]}, **extra}


class FakeRuntime:
    """Agent Runtime の :query / :streamQuery の形だけを模す。"""

    def __init__(self, stream_events=None, stream_status=200, stream_body=None):
        self.requests: list[httpx.Request] = []
        self.sessions = 0
        self.stream_events = stream_events if stream_events is not None else [model("こんにちは")]
        self.stream_status = stream_status
        self.stream_body = stream_body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        if request.url.path.endswith(":query"):
            assert body["class_method"] == "async_create_session"
            self.sessions += 1
            return httpx.Response(200, json={"output": {"id": f"s{self.sessions}"}})
        assert request.url.path.endswith(":streamQuery")
        assert body["class_method"] == "async_stream_query"
        if self.stream_status != 200:
            return httpx.Response(self.stream_status, text=self.stream_body or "")
        return httpx.Response(200, text=ndjson(*self.stream_events))


def make(fake: FakeRuntime) -> AgentRuntimeClient:
    async def token() -> str:
        return "TOKEN"

    return AgentRuntimeClient(
        engine=ENGINE,
        location="us-central1",
        http=httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)),
        token=token,
    )


def test_extract_text_skips_partial_thought_and_user_events():
    events = [
        {"content": {"role": "user", "parts": [{"text": "質問"}]}},
        model("途中", partial=True),
        {"content": {"role": "model", "parts": [{"text": "考え中", "thought": True}]}},
        model("答え1。"),
        model("答え2。"),
        {"content": {"role": "model", "parts": [{"function_call": {"name": "x"}}]}},
    ]
    assert extract_text(events) == "答え1。答え2。"
    assert extract_text([]) == ""


async def test_create_session_and_stream_query_use_the_adk_contract():
    fake = FakeRuntime()
    client = make(fake)
    session = await client.create_session("u_abc")
    text = await client.stream_query(user_id="u_abc", session_id=session, message="やあ")
    assert (session, text) == ("s1", "こんにちは")
    assert str(fake.requests[0].url) == (
        f"https://us-central1-aiplatform.googleapis.com/v1/{ENGINE}:query"
    )
    assert fake.requests[0].headers["authorization"] == "Bearer TOKEN"
    sent = json.loads(fake.requests[1].content)["input"]
    assert sent == {"user_id": "u_abc", "session_id": "s1", "message": "やあ"}


async def test_errors_never_carry_response_bodies():
    fake = FakeRuntime(stream_status=500, stream_body="SECRET-INTERNAL-DETAIL")
    with pytest.raises(AgentRuntimeError) as e:
        await make(fake).stream_query(user_id="u", session_id="s", message="x")
    assert e.value.code == "stream_query_500"
    assert "SECRET" not in str(e.value)


async def test_missing_session_is_distinguished():
    fake = FakeRuntime(stream_status=404)
    with pytest.raises(SessionNotFound):
        await make(fake).stream_query(user_id="u", session_id="gone", message="x")


async def test_network_failure_is_an_agent_runtime_error():
    def boom(request):
        raise httpx.ConnectTimeout("t")

    async def token() -> str:
        return "T"

    client = AgentRuntimeClient(
        engine=ENGINE,
        location="us-central1",
        http=httpx.AsyncClient(transport=httpx.MockTransport(boom)),
        token=token,
    )
    with pytest.raises(AgentRuntimeError) as e:
        await client.create_session("u")
    assert e.value.code.startswith("unreachable")


async def test_chat_creates_one_session_per_user_and_reuses_it():
    fake, store = FakeRuntime(), MemorySessionStore()
    client = make(fake)
    await kuroko_chat._reply_via_runtime(client, store, "slack:T:U1", "1回目")
    await kuroko_chat._reply_via_runtime(client, store, "slack:T:U1", "2回目")
    await kuroko_chat._reply_via_runtime(client, store, "slack:T:U2", "別の人")
    assert fake.sessions == 2
    stream = [json.loads(r.content)["input"] for r in fake.requests if "streamQuery" in r.url.path]
    assert [s["session_id"] for s in stream] == ["s1", "s1", "s2"]


async def test_chat_sends_a_pseudonym_not_the_slack_user_id():
    fake, store = FakeRuntime(), MemorySessionStore()
    await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T123:UABC", "x")
    for r in fake.requests:
        assert "UABC" not in r.content.decode() and "T123" not in r.content.decode()
        assert json.loads(r.content)["input"]["user_id"] == kuroko_chat.pseudonym("slack:T123:UABC")


async def test_chat_recreates_a_lost_session_once():
    class Flaky(FakeRuntime):
        def handler(self, request):
            if request.url.path.endswith(":streamQuery") and self.sessions == 1:
                self.requests.append(request)
                return httpx.Response(404)
            return super().handler(request)

    fake, store = Flaky(), MemorySessionStore()
    text = await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T:U", "x")
    assert text == "こんにちは"
    assert fake.sessions == 2
    assert await store.get(kuroko_chat.session_key(ENGINE, "slack:T:U")) == "s2"


async def test_reply_falls_back_to_the_provisional_agent_until_an_engine_is_configured(
    monkeypatch, settings
):
    calls = []

    async def provisional(user_key, text):
        calls.append((user_key, text))
        return "仮の返答"

    monkeypatch.setattr(kuroko_chat.provisional_agent, "reply", provisional)
    assert settings.kuroko_agent_engine == ""
    assert await kuroko_chat.reply("slack:T:U", "やあ") == "仮の返答"
    assert calls == [("slack:T:U", "やあ")]


async def test_reply_uses_the_runtime_when_an_engine_is_configured(monkeypatch, settings):
    from src.config import get_settings

    monkeypatch.setenv("KUROKO_AGENT_ENGINE", ENGINE)
    get_settings.cache_clear()
    kuroko_chat._client.cache_clear()
    kuroko_chat._store.cache_clear()
    fake = FakeRuntime()
    monkeypatch.setattr(kuroko_chat, "_client", lambda: make(fake))

    async def must_not_be_called(*_):
        raise AssertionError("provisional agent must not be used")

    monkeypatch.setattr(kuroko_chat.provisional_agent, "reply", must_not_be_called)
    assert await kuroko_chat.reply("slack:T:U", "やあ") == "こんにちは"
    kuroko_chat._store.cache_clear()


async def test_a_session_saved_for_another_engine_is_never_used():
    """エンジンを切り替えたあと、古いエンジンのセッション ID を使わない（実機で返答が止まった）。"""
    fake, store = FakeRuntime(), MemorySessionStore()
    await store.put("other-engine|slack:T:U", "stale-session")  # 切り替え前のエンジンのもの
    await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T:U", "x")
    stream = [json.loads(r.content)["input"] for r in fake.requests if "streamQuery" in r.url.path]
    assert [s["session_id"] for s in stream] == ["s1"] and fake.sessions == 1


async def test_an_empty_200_stream_is_treated_as_a_missing_session_and_retried_once():
    """ADK は、セッションが無いと、ストリームを 200 で始めたあとに例外にする（本文が空になる）。"""

    class EmptyOnce(FakeRuntime):
        def handler(self, request):
            if request.url.path.endswith(":streamQuery") and self.sessions == 1:
                self.requests.append(request)
                return httpx.Response(200, content=b"")
            return super().handler(request)

    fake, store = EmptyOnce(), MemorySessionStore()
    text = await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T:U", "x")
    assert text == "こんにちは" and fake.sessions == 2


async def test_two_empty_streams_in_a_row_fail_instead_of_looping():
    class AlwaysEmpty(FakeRuntime):
        def handler(self, request):
            if request.url.path.endswith(":streamQuery"):
                self.requests.append(request)
                return httpx.Response(200, content=b"")
            return super().handler(request)

    fake, store = AlwaysEmpty(), MemorySessionStore()
    with pytest.raises(SessionNotFound):
        await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T:U", "x")
    assert fake.sessions == 2  # 1回だけやり直して終える


def test_the_session_key_is_a_valid_firestore_document_id():
    """実機で、キーにエンジンの完全な名前（`/` を含む）を使って、Firestore が拒否した。"""
    engine = "projects/1054683553459/locations/us-central1/reasoningEngines/4459953688672206848"
    key = kuroko_chat.session_key(engine, "slack:T123:UABC")
    assert "/" not in key and key == "4459953688672206848|slack:T123:UABC"
    assert "/" not in kuroko_chat.session_key(
        engine, "web:ev/1:uid"
    )  # ユーザー側の鍵にも `/` を入れない
    assert kuroko_chat.session_key(engine, "u") != kuroko_chat.session_key(
        engine.replace("4459", "9999"), "u"
    )


async def test_the_memory_store_used_in_tests_rejects_a_key_firestore_would_reject():
    """テストの保存先が、Firestore と同じ制約（`/` を含まない）で確かめる。"""
    from src.db.agent_sessions import MemorySessionStore

    fake, store = FakeRuntime(), MemorySessionStore()
    original_put = store.put

    async def strict_put(key, session_id):
        assert "/" not in key, key
        await original_put(key, session_id)

    store.put = strict_put
    await kuroko_chat._reply_via_runtime(make(fake), store, "slack:T:U", "x")
