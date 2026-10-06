"""Agent Runtime のエージェントを呼ぶクライアント（ARCHITECTURE 4.2・8章。TASKS B22）。

ADK の `:query`（セッションの作成）と `:streamQuery`（会話の1ターン）を HTTP で呼ぶ。
エージェントの応答は「提案」にすぎない。失敗・タイムアウトは例外にして、呼び出し側が
決まった文面に落とす（エージェントの出力を使わない）。お金・委任・承認に関わる処理は、
応答がなければ進めない（fail closed）。

Gateway を付けたあとも、呼び出しは `streamQuery` だけを使う（Gateway が検査するのは
`query` / `streamQuery` だけ。ARCHITECTURE 4.8）。
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import google.auth
import httpx
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class AgentRuntimeError(Exception):
    """エージェントの呼び出しが失敗した。message に本文・秘密を入れない。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SessionNotFound(AgentRuntimeError):
    """保存していたセッションが Agent Runtime に無い（作り直せば続けられる）。"""


def extract_text(events: list[dict[str, Any]]) -> str:
    """応答の文面。途中経過（partial）・思考・ユーザー側のイベントは使わない。"""
    parts: list[str] = []
    for event in events:
        content = event.get("content") or {}
        if event.get("partial") or content.get("role") != "model":
            continue
        for part in content.get("parts") or []:
            if part.get("text") and not part.get("thought"):
                parts.append(part["text"])
    return "".join(parts).strip()


async def _default_token() -> str:
    creds, _ = await asyncio.to_thread(google.auth.default, scopes=SCOPES)
    await asyncio.to_thread(creds.refresh, Request())
    return creds.token


class AgentRuntimeClient:
    def __init__(
        self,
        *,
        engine: str,
        location: str,
        timeout: float = 90.0,
        http: httpx.AsyncClient | None = None,
        token: Callable[[], Awaitable[str]] = _default_token,
    ) -> None:
        self._base = f"https://{location}-aiplatform.googleapis.com/v1/{engine}"
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._token = token

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._token()}"}

    async def create_session(self, user_id: str) -> str:
        try:
            res = await self._http.post(
                f"{self._base}:query",
                headers=await self._headers(),
                json={"class_method": "async_create_session", "input": {"user_id": user_id}},
            )
        except httpx.HTTPError as e:
            raise AgentRuntimeError(f"unreachable:{type(e).__name__}") from None
        if res.status_code != 200:
            raise AgentRuntimeError(f"create_session_{res.status_code}")
        session_id = (res.json().get("output") or {}).get("id")
        if not session_id:
            raise AgentRuntimeError("no_session_id")
        return str(session_id)

    async def stream_query(self, *, user_id: str, session_id: str, message: str) -> str:
        """1ターン進めて、応答の文面を返す。"""
        events: list[dict[str, Any]] = []
        try:
            async with self._http.stream(
                "POST",
                f"{self._base}:streamQuery",
                headers=await self._headers(),
                json={
                    "class_method": "async_stream_query",
                    "input": {"user_id": user_id, "session_id": session_id, "message": message},
                },
            ) as res:
                if res.status_code != 200:
                    await res.aread()
                    # セッションが無いときだけ、作り直せる失敗として区別する
                    if res.status_code == 404 or "Session not found" in res.text:
                        raise SessionNotFound(f"stream_query_{res.status_code}")
                    raise AgentRuntimeError(f"stream_query_{res.status_code}")
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("agent runtime: unparsable event line")
        except httpx.HTTPError as e:
            raise AgentRuntimeError(f"unreachable:{type(e).__name__}") from None
        return extract_text(events)
