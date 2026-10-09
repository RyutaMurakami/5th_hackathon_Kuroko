"""ADK コールバック（ARCHITECTURE 4.9）。決定論的な Python で、LLM の判断に左右されない。

- `before_model`: 入力の長さの上限（長い文は切る）。用途（mode）が壊れた入力は、モデルに渡さない
- `after_model`: 出力を、用途ごとの固定の語彙・形に検証し、外れたら**空の結果**に差し替える
- `before_tool`: このエージェントは**ツールを持たない**ので、どのツールも止める
"""

import json
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.sanitize import EMPTY, parse_request, sanitize
from app.vocab import MAX_INPUT_CHARS


def _user_text(contents: list[types.Content]) -> str:
    for content in reversed(contents):
        if content.role == "user":
            return "".join(p.text or "" for p in content.parts or [])
    return ""


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    mode, body = parse_request(_user_text(llm_request.contents))
    if not mode:
        # 形が壊れた入力は、モデルに渡さず、空の結果を返す（何も実行されない）
        return _response(EMPTY)
    callback_context.state["mode"] = mode
    # 入力を、API が組み立てた形（mode と、長さを切った text）だけにして、モデルに渡す
    cleaned = json.dumps({"mode": mode, "text": body[:MAX_INPUT_CHARS]}, ensure_ascii=False)
    for content in reversed(llm_request.contents):
        if content.role == "user":
            content.parts = [types.Part(text=cleaned)]
            break
    return None


def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    mode = callback_context.state.get("mode", "")
    text = "".join(
        p.text or "" for p in (llm_response.content.parts if llm_response.content else [])
    )
    try:
        raw = json.loads(text)
    except ValueError:
        raw = None
    return _response(sanitize(raw, mode))


def before_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    return {"error": "tool_not_allowed"}  # このエージェントは、ツールを持たない


def _response(payload: dict[str, Any]) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part(text=json.dumps(payload, ensure_ascii=False))]
        )
    )
