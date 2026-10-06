"""統括エージェントの構造の検査（LLM を呼ばない）。LLM の応答は eval で見る（tests/eval）。"""

import re
from pathlib import Path

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


def test_agent_has_the_callback_and_no_unexpected_tools():
    assert root_agent.before_tool_callback is callbacks.before_tool_callback
    assert root_agent.tools == []  # /mcp のツールセットは B21 で足す


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
