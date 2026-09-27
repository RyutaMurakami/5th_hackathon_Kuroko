"""仮のエージェント（TASKS B16a。2026-09-27 ユーザー合意の一時的な構成）。

Slack → kuroko-gateway → Cloud Tasks → kuroko-api の経路を先に通すため、
ツールを持たない ADK エージェントを kuroko-api の中で動かし、Vertex AI の Gemini を呼ぶ。
ARCHITECTURE D6（ADK エージェントは Agent Runtime）の一時的な例外。統括エージェント
（`kuroko_agent/`。B23）ができたら `clients/agent_runtime.py`（B22）の呼び出しに差し替え、
このモジュールは消す。

会話の履歴はインスタンスのメモリにだけ持つ（再起動・スケールで消える。仮なので許容する）。
"""

import os
from functools import lru_cache

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.config import get_settings

APP_NAME = "kuroko-provisional"

INSTRUCTION = """\
あなたは「KUROKO」です。会社の飲み会の幹事を代行する AI エージェントですが、今は仮の版で、
飲み会の企画・出欠・お店探し・按分・送金などの機能はまだつながっていません。
- 日本語で、Slack の DM に合う短さ（3〜5文程度）で答える。
- 機能について聞かれたら、準備中であることを正直に伝える。できないことをできると言わない。
- 金額の計算・承認・送金・委任の約束はしない。
"""


@lru_cache
def _runner() -> Runner:
    s = get_settings()
    # ADK（google-genai）は環境変数で Vertex AI とその呼び出し先を選ぶ
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", s.google_cloud_project)
    os.environ["GOOGLE_CLOUD_LOCATION"] = s.google_cloud_location
    agent = Agent(
        name="kuroko_provisional",
        model=s.provisional_agent_model,
        description="Slack 疎通用の仮のエージェント（ツールなし）",
        instruction=INSTRUCTION,
        tools=[],
    )
    return Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )


async def reply(user_key: str, text: str) -> str:
    """`user_key`（Slack のワークスペースとユーザー）ごとの会話として1ターン進める。

    返り値は返答の文面。
    """
    parts: list[str] = []
    async for event in _runner().run_async(
        user_id=user_key,
        session_id=user_key,
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            parts.extend(p.text for p in event.content.parts if p.text)
    return "".join(parts).strip()
