"""統括エージェントの構造の検査（LLM を呼ばない）。LLM の応答は eval で見る（tests/eval）。"""

import json
import re
from pathlib import Path
from typing import ClassVar

import pytest

from app import callbacks
from app.agent import INSTRUCTION, MODEL, root_agent

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# audit.llm_must_not（policies/company_rules.yaml）に当たる処理は、ツールにしない
LLM_MUST_NOT = {
    "calculate_amounts",
    "calculate_split",
    "choose_approver",
    "determine_approver",
    "choose_payee",
    "modify_policy",
    "sign_mandates",
    "sign_open_mandates",
}


def test_allowlist_contains_no_forbidden_tools():
    assert not (callbacks.ALLOWED_TOOLS & LLM_MUST_NOT)


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


@pytest.mark.parametrize("name", sorted(LLM_MUST_NOT | {"anything_else", "add_session_to_memory"}))
def test_unlisted_tools_are_blocked(name):
    result = callbacks.before_tool_callback(FakeTool(name), {}, None)
    assert result is not None and result["error"] == "tool_not_allowed"


def test_listed_tool_passes(monkeypatch):
    monkeypatch.setattr(callbacks, "ALLOWED_TOOLS", frozenset({"search_venues"}))
    assert callbacks.before_tool_callback(FakeTool("search_venues"), {}, None) is None


def test_agent_has_the_callback_and_only_the_mcp_toolset():
    assert root_agent.before_tool_callback is callbacks.before_tool_callback
    assert root_agent.tools == []  # KUROKO_MCP_URL が無いローカルでは、ツールなし


def test_toolset_is_built_only_with_a_url_and_filtered_to_the_allowlist(monkeypatch):
    from app.tools import build_tools

    monkeypatch.delenv("KUROKO_MCP_URL", raising=False)
    assert build_tools() == []
    monkeypatch.setenv("KUROKO_MCP_URL", "https://kuroko-api.example/mcp/")
    (toolset,) = build_tools()
    assert sorted(toolset.tool_filter) == sorted(callbacks.ALLOWED_TOOLS)


def test_allowlist_matches_the_tools_the_api_actually_exposes():
    """backend/mcp_toolspec.json（/mcp の実際のツール）と一致する。ずれたら、どちらかを直す。"""
    spec = json.loads((APP_DIR.parent.parent / "backend" / "mcp_toolspec.json").read_text())
    assert {t["name"] for t in spec["tools"]} == set(callbacks.ALLOWED_TOOLS)


def test_agent_code_has_no_memory_write_or_secret_access():
    """記憶の書き込み・鍵・Slack・Firestore への直接のアクセスを、エージェントのコードに書かない。"""
    banned = [
        r"add_session_to_memory",
        r"memories\.create",
        r"PreloadMemoryTool",
        r"firestore",
        r"secretmanager",
        r"cloudkms",
        r"slack_sdk",
        r"WebClient",
    ]
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text()
        for pattern in banned:
            assert not re.search(pattern, text, re.IGNORECASE), f"{path.name}: {pattern}"


def test_instruction_states_the_hard_limits():
    for phrase in ("按分", "承認", "送金", "順位", "口座番号", "無視して"):
        assert phrase in INSTRUCTION


def test_model_is_the_verified_one():
    assert MODEL == "gemini-3.8-flash"  # 変更は、動作確認のうえ明示的に行う


# ---------------- /mcp の認証（Agent identity が呼び出し用 SA を偽装する） ----------------
def test_audience_is_the_scheme_and_host_only():
    from app.tools import audience_of

    assert audience_of("https://kuroko-api-x.a.run.app/mcp") == "https://kuroko-api-x.a.run.app"
    assert audience_of("https://kuroko-api-x.a.run.app/mcp/") == "https://kuroko-api-x.a.run.app"


class _FakeCreds:
    minted: ClassVar[list[dict]] = []

    def __init__(self, target, target_audience, include_email):
        self.target_audience = target_audience
        self.token = f"token-for-{target_audience}"
        self.expiry = None
        self._invoker = target.target_principal
        self._include_email = include_email

    def refresh(self, _request):
        _FakeCreds.minted.append(
            {"aud": self.target_audience, "sa": self._invoker, "email": self._include_email}
        )


class _FakeImpersonated:
    def __init__(self, source_credentials, target_principal, target_scopes):
        self.target_principal = target_principal


def _patch_google_auth(monkeypatch):
    import google.auth
    from google.auth import impersonated_credentials

    _FakeCreds.minted = []
    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (object(), "p"))
    monkeypatch.setattr(impersonated_credentials, "Credentials", _FakeImpersonated)
    monkeypatch.setattr(impersonated_credentials, "IDTokenCredentials", _FakeCreds)


def test_the_token_is_minted_for_the_api_audience_via_the_invoker_sa_and_reused(monkeypatch):
    from app.tools import id_token_header_provider

    _patch_google_auth(monkeypatch)
    p = id_token_header_provider("sa-agent-mcp@p.iam.gserviceaccount.com", "https://api.example")
    assert p(None) == {"Authorization": "Bearer token-for-https://api.example"}
    p(None)
    p(None)
    assert _FakeCreds.minted == [
        {
            "aud": "https://api.example",
            "sa": "sa-agent-mcp@p.iam.gserviceaccount.com",
            "email": True,
        }
    ]  # 1回だけ作り、使い回す。メールを含める（kuroko-api が身元の検査に使う）


def test_an_expiring_token_is_minted_again(monkeypatch):
    import datetime

    from app import tools

    _patch_google_auth(monkeypatch)
    soon = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=30)
    monkeypatch.setattr(_FakeCreds, "expiry", soon, raising=False)
    p = tools.id_token_header_provider("sa@p", "https://api.example")
    orig = _FakeCreds.refresh

    def refresh(self, request):
        orig(self, request)
        self.expiry = soon  # 期限が近いまま

    monkeypatch.setattr(_FakeCreds, "refresh", refresh)
    p(None)
    p(None)
    assert len(_FakeCreds.minted) == 2  # 期限の手前（5分以内）なら、作り直す


def test_a_failure_to_mint_never_falls_back_to_another_identity(monkeypatch):
    import google.auth

    from app.tools import id_token_header_provider

    def boom(scopes=None):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(google.auth, "default", boom)
    p = id_token_header_provider("sa@p", "https://api.example")
    with pytest.raises(RuntimeError):
        p(None)  # ヘッダーなし（別の身元）で呼ぶことはしない


def test_toolset_uses_the_provider_only_when_the_invoker_sa_is_configured(monkeypatch):
    from app import tools

    monkeypatch.setenv("KUROKO_MCP_URL", "https://api.example/mcp")
    monkeypatch.delenv("KUROKO_MCP_INVOKER_SA", raising=False)
    monkeypatch.delenv("KUROKO_MCP_BEARER", raising=False)
    (plain,) = tools.build_tools()
    assert plain.header_provider is None
    monkeypatch.setenv("KUROKO_MCP_INVOKER_SA", "sa-agent-mcp@p.iam.gserviceaccount.com")
    (with_provider,) = tools.build_tools()
    assert callable(with_provider.header_provider)
    monkeypatch.delenv("KUROKO_MCP_URL")
    assert tools.build_tools() == []  # URL が無ければ、ツールなし


def test_the_token_audience_can_differ_from_the_registered_url(monkeypatch):
    """Registry の登録 URL（宛先のホスト）と、kuroko-api が期待する aud の綴りは別でよい。"""
    from app import tools

    seen = {}
    monkeypatch.setattr(
        tools,
        "id_token_header_provider",
        lambda sa, aud: seen.update(sa=sa, aud=aud) or (lambda c: {}),
    )
    monkeypatch.setenv("KUROKO_MCP_URL", "https://kuroko-api-hash-uc.a.run.app/mcp")
    monkeypatch.setenv("KUROKO_MCP_INVOKER_SA", "sa@p")
    monkeypatch.setenv("KUROKO_MCP_AUDIENCE", "https://kuroko-api-123.us-central1.run.app")
    tools.build_tools()
    assert seen["aud"] == "https://kuroko-api-123.us-central1.run.app"
    monkeypatch.delenv("KUROKO_MCP_AUDIENCE")
    tools.build_tools()
    assert seen["aud"] == "https://kuroko-api-hash-uc.a.run.app"  # 未設定なら URL のホスト
