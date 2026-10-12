import base64
import json

import pytest

from src.services import slack_conversation
from tests.conftest import GATEWAY_SA, KUROKO_API_URL

MESSAGE = {
    "event_id": "Ev1",
    "team_id": "T1",
    "user_id": "U1",
    "channel_id": "D1",
    "text": "hi",
    "ts": "1.0",
}


def _token(email: str, aud: str = KUROKO_API_URL) -> str:
    # Cloud Run が署名を外したあとの形（署名の検証は Cloud Run の IAM が済ませている）
    def enc(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = enc({"alg": "RS256", "typ": "JWT"})
    claims = enc({"aud": aud, "email": email, "email_verified": True})
    return f"Bearer {header}.{claims}.SIG"


@pytest.fixture
def slack_io(monkeypatch):
    posted = []

    async def fake_reply(user_key, text):
        return f"echo:{user_key}:{text}"

    async def fake_post(channel_id, text):
        posted.append((channel_id, text))
        return f"ts{len(posted)}"

    async def fake_update(channel_id, ts, text):
        # 画面に見えている文面を、そのメッセージの位置で書き換える
        posted[int(ts.removeprefix("ts")) - 1] = (channel_id, text)

    monkeypatch.setattr(slack_conversation.kuroko_chat, "reply", fake_reply)
    monkeypatch.setattr(slack_conversation.slack, "post_message", fake_post)
    monkeypatch.setattr(slack_conversation.slack, "update_message", fake_update)
    return posted


async def test_gateway_caller_gets_agent_reply(client, slack_io):
    response = await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert response.status_code == 200
    assert slack_io == [("D1", "echo:slack:T1:U1:hi")]


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        _token("sa-api@test.iam.gserviceaccount.com"),
        _token(GATEWAY_SA, aud="https://other.test"),
    ],
)
async def test_other_callers_are_rejected(client, slack_io, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    response = await client.post("/tasks/slack/message", json=MESSAGE, headers=headers)
    assert response.status_code == 403
    assert slack_io == []


async def test_agent_failure_posts_fixed_text(client, slack_io, monkeypatch):
    async def broken(user_key, text):
        raise RuntimeError("boom")

    monkeypatch.setattr(slack_conversation.kuroko_chat, "reply", broken)
    response = await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert response.status_code == 200
    assert slack_io == [("D1", slack_conversation.FALLBACK_TEXT)]


async def test_a_thinking_message_is_shown_first_and_then_replaced_by_the_reply(
    client, slack_io, monkeypatch
):
    seen_while_thinking = []

    async def slow_reply(user_key, text):
        seen_while_thinking.extend(slack_io)  # 返答を作っているあいだに見えているもの
        return "できました"

    monkeypatch.setattr(slack_conversation.kuroko_chat, "reply", slow_reply)
    await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert seen_while_thinking == [("D1", slack_conversation.THINKING_TEXT)]
    assert slack_io == [("D1", "できました")]  # 「考え中」は残らない（返答に置き換わる）


async def test_the_reply_still_arrives_when_the_thinking_message_cannot_be_shown_or_replaced(
    client, slack_io, monkeypatch
):
    async def broken_update(channel_id, ts, text):
        raise RuntimeError("cannot update")

    monkeypatch.setattr(slack_conversation.slack, "update_message", broken_update)
    await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert slack_io[-1] == ("D1", "echo:slack:T1:U1:hi")  # 書き換えられなくても、返答は届く
