"""`/mcp`（エージェント用のツール）。呼べるのは agent-kuroko だけ。公開するのは「LLM 可」だけ。"""

import base64
import contextlib
import json
from pathlib import Path

import yaml
from httpx import ASGITransport, AsyncClient

from src.clients.ekispert import EkispertError
from src.config import get_settings
from src.db.events import MemoryEventStore
from src.main import create_app
from src.routers import mcp as mcp_router
from src.services.policy import load_snapshot
from src.services.venue_search import EventNotFound, VenueSearchResult
from tests.sample_company import demo_event, demo_participants

URL = "https://kuroko-api.test"
AGENT = "agent-kuroko-principal"
RULES = Path(__file__).resolve().parents[2] / "policies" / "company_rules.yaml"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
TOOLS = {"get_event_summary", "check_budget", "search_venues", "retrieve_policy"}


def bearer(identity: str | None, aud: str = URL, claim: str = "email") -> dict[str, str]:
    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    claims = {"aud": aud} | ({claim: identity} if identity else {})
    return {"Authorization": f"Bearer {b64({'alg': 'none'})}.{b64(claims)}."}


def raw_bearer(claims: dict) -> dict[str, str]:
    """クレームをそのまま入れたトークン（空の値も含めて）。"""

    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    return {"Authorization": f"Bearer {b64({'alg': 'none'})}.{b64(claims)}."}


@contextlib.asynccontextmanager
async def running(monkeypatch, principal: str = AGENT):
    """アプリ（MCP のセッション管理を含む）を、同じタスクの中で開始・終了する。"""
    monkeypatch.setenv("AGENT_KUROKO_PRINCIPAL", principal)
    monkeypatch.setenv("KUROKO_API_URL", URL)
    get_settings.cache_clear()
    store = MemoryEventStore()
    event = demo_event().model_copy(
        update={"title": "歓送迎会", "policy_snapshot": load_snapshot()}
    )
    store.save_event(event)
    for p in demo_participants():
        store.save_participant(event.event_id, p)
    monkeypatch.setattr(mcp_router, "get_event_store", lambda: store)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            yield client


async def rpc(client, method, params=None, who=AGENT, **kw):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return await client.post("/mcp/", json=body, headers={**HEADERS, **bearer(who, **kw)})


def result_of(res) -> dict:
    data = res.json()
    assert "error" not in data, data
    return data["result"]


async def call(client, name, args, **kw):
    result = result_of(await rpc(client, "tools/call", {"name": name, "arguments": args}, **kw))
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


# ---------------- 呼び出し元 ----------------
async def test_only_agent_kuroko_can_call_mcp(monkeypatch):
    async with running(monkeypatch) as client:
        assert (await rpc(client, "tools/list")).status_code == 200
        for who in ("someone@example.com", "sa-api@test.iam.gserviceaccount.com", None):
            assert (await rpc(client, "tools/list", who=who)).status_code == 403
        assert (await client.post("/mcp/", json={}, headers=HEADERS)).status_code == 403
        # audience が違うトークンは、身元が合っていても受け付けない
        assert (await rpc(client, "tools/list", aud="https://other")).status_code == 403
        # Agent Identity の ID トークンが email でなく sub に身元を持つ場合も確かめられる
        assert (await rpc(client, "tools/list", claim="sub")).status_code == 200


async def test_mcp_is_closed_until_the_agent_identity_is_configured(monkeypatch):
    async with running(monkeypatch, principal="") as client:
        assert (await rpc(client, "tools/list", who="")).status_code == 403
        assert (await rpc(client, "tools/list")).status_code == 403  # fail closed


async def test_an_empty_identity_never_matches_an_empty_configuration(monkeypatch):
    """設定が空で、トークンの sub も空のとき、「空 = 空」で通してはならない。"""
    async with running(monkeypatch, principal="") as client:
        for claims in ({"aud": URL, "sub": ""}, {"aud": URL, "email": "", "sub": ""}, {"aud": URL}):
            res = await client.post("/mcp/", json={}, headers={**HEADERS, **raw_bearer(claims)})
            assert res.status_code == 403, claims


async def test_other_routes_do_not_accept_the_agent_identity(monkeypatch):
    """エージェントの ID では、/tasks/* の内部ルートに届かない（ルートごとの絞り込み）。"""
    async with running(monkeypatch) as client:
        for path in ("/tasks/internal/checkouts", "/tasks/internal/approval-requests"):
            res = await client.post(path, json={"event_id": "x"}, headers=bearer(AGENT))
            assert res.status_code == 403
        res = await client.post("/tasks/slack/interaction", json={}, headers=bearer(AGENT))
        assert res.status_code in (403, 422) and res.status_code != 200


# ---------------- 公開するツール ----------------
async def test_only_llm_allowed_tools_are_exposed():
    forbidden = set(yaml.safe_load(RULES.read_text())["audit"]["llm_must_not"])
    names = {t.name for t in await mcp_router.mcp.list_tools()}
    assert names == TOOLS
    assert not names & forbidden  # llm_must_not に当たる処理は、ツールにしない
    # お金・委任・承認・記憶・Slack に触れる名前のツールが無い
    for bad in ("split", "approve", "payee", "mandate", "sign", "pay", "memory", "slack"):
        assert not any(bad in n for n in names), bad


async def test_tools_accept_only_an_event_id_and_a_price(monkeypatch):
    async with running(monkeypatch) as client:
        tools = result_of(await rpc(client, "tools/list"))["tools"]
        assert {t["name"] for t in tools} == TOOLS
        for t in tools:  # 条件（人数・予算・食べられないもの）は、LLM から受けない
            allowed = {"event_id", "course_price_yen"}
            if t["name"] == "retrieve_policy":
                allowed = {"event_id", "question"}  # 規程の検索の問いだけ（値は変えられない）
            assert set(t["inputSchema"]["properties"]) <= allowed


# ---------------- ツールの挙動 ----------------
async def test_event_summary_has_no_personal_information(monkeypatch):
    async with running(monkeypatch) as client:
        out = await call(client, "get_event_summary", {"event_id": "ev-demo"})
    assert out["ok"] and out["attendee_count"] == 10 and out["hard_limit_per_person_yen"] == 7000
    text = json.dumps(out, ensure_ascii=False)
    for p in demo_participants():
        assert p.user_id not in text  # 個人（仮名ID・名前）を返さない


async def test_unknown_event_is_a_plain_error_without_internals(monkeypatch):
    async with running(monkeypatch) as client:
        out = await call(client, "get_event_summary", {"event_id": "nope"})
    assert out == {"ok": False, "error": "event_not_found"}


async def test_check_budget_boundary_and_invalid_price(monkeypatch):
    async with running(monkeypatch) as client:
        args = {"event_id": "ev-demo"}
        at = await call(client, "check_budget", args | {"course_price_yen": 7000})
        assert at["ok"] and not at["over_hard_limit"]  # ちょうど上限は超過ではない
        over = await call(client, "check_budget", args | {"course_price_yen": 7001})
        assert not over["ok"] and over["over_hard_limit"] and over["next"]
        bad = await call(client, "check_budget", args | {"course_price_yen": 0})
        assert bad == {"ok": False, "error": "invalid_price"}


class FakeSearch:
    def __init__(self, outcome):
        self.outcome = outcome

    async def run(self, event_id):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


async def test_search_venues_returns_the_service_result_and_hides_failures(monkeypatch):
    async with running(monkeypatch) as client:
        monkeypatch.setattr(
            mcp_router,
            "get_venue_search",
            lambda: FakeSearch(VenueSearchResult(False, "no_stations")),
        )
        assert (await call(client, "search_venues", {"event_id": "e"}))["reason"] == "no_stations"
        monkeypatch.setattr(mcp_router, "get_venue_search", lambda: FakeSearch(EventNotFound()))
        out = await call(client, "search_venues", {"event_id": "e"})
        assert out["error"] == "event_not_found"
        monkeypatch.setattr(
            mcp_router, "get_venue_search", lambda: FakeSearch(EkispertError("station_not_found"))
        )
        out = await call(client, "search_venues", {"event_id": "e"})
        assert out == {"ok": False, "error": "external_api_station_not_found"}


async def test_the_callers_identity_claims_are_logged_for_v1_but_never_the_token(
    monkeypatch, caplog
):
    import logging

    caplog.set_level(logging.INFO, logger="src.services.mcp_auth")
    async with running(
        monkeypatch, principal=""
    ) as client:  # 設定が空 = 拒否。それでも実際の値が分かる
        headers = bearer("principal://agents.global.proj-1.system.id.goog/resources/x", claim="sub")
        assert (
            await client.post("/mcp/", json={}, headers={**HEADERS, **headers})
        ).status_code == 403
    line = next(r.getMessage() for r in caplog.records if "mcp caller" in r.getMessage())
    assert "principal://agents.global.proj-1" in line and "allowed=False" in line
    token = headers["Authorization"].removeprefix("Bearer ")
    assert token not in caplog.text  # トークン本体は出さない


async def test_mcp_without_the_trailing_slash_is_served_in_place_and_still_checks_the_identity(
    monkeypatch,
):
    """Registry の登録 URL は `/mcp`。307 にせず、同じ身元の検査で受ける。"""
    async with running(monkeypatch) as client:
        assert (await client.post("/mcp", json={}, headers=HEADERS)).status_code == 403  # 身元なし
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        res = await client.post("/mcp", json=body, headers={**HEADERS, **bearer(AGENT)})
        assert res.status_code == 200 and res.status_code != 307
        other = await client.post("/mcp", json=body, headers={**HEADERS, **bearer("someone-else")})
        assert other.status_code == 403
        # ほかのパスは巻き込まない（/mcpx などは、これまでどおり 404）
        assert (await client.post("/mcpx", json={}, headers=HEADERS)).status_code == 404
