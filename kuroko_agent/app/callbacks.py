"""ADK コールバック（ARCHITECTURE 4.9）。決定論的な Python で、LLM の判断に左右されない。

ここに置くのは「止める・差し替える」ものだけ。鍵・お金・Slack・状態の書き込みは置かない。
確認待ちへの遷移（`pending_confirmation`）や `load_memory` の段階制限は B24 で足す。
"""

from typing import Any

from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext

# 呼んでよいツール名の許可リスト。`kuroko-api` の /mcp の「LLM可」のツール（SPEC 4.1）だけを入れる。
# 追加は B21（/mcp の実装）と一緒に行い、`llm_must_not` に当たるものは入れない（テストで固定）。
ALLOWED_TOOLS: frozenset[str] = frozenset()


def before_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """許可リストにないツールの呼び出しを止める。止めた場合は、ツールの代わりに返す辞書を返す。"""
    if tool.name in ALLOWED_TOOLS:
        return None
    return {"error": "tool_not_allowed", "message": "このツールは使えません。"}
