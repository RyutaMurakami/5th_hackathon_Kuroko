"""`/mcp` の呼び出し元の検査（ARCHITECTURE 4.7・6章。TASKS B21）。

`/mcp` は、**Agent Gateway 経由の `agent-kuroko` だけ**を受け付ける。ほかのルートは、エージェントの
identity を一切受け付けない（`task_auth` が sa-gateway・sa-api だけ）。Cloud Run の IAM はサービス
単位なので、ルートごとの絞り込みは、このアプリ層で行う。

ID トークンの署名は Cloud Run の IAM（invoker）が検証済みなので、ここでは再検証せず、クレーム
（audience と身元）だけを確かめる。**身元の設定が空のあいだは、すべて拒否する（fail closed）**。
Agent Identity の ID トークンにどのクレームが入るかは、デプロイ後に確かめる（V1）。
"""

import json
from typing import Any

from google.auth import jwt

from src.config import get_settings


def agent_identity(authorization: str | None) -> str | None:
    """宛先（aud）が正しいトークンの、身元のクレーム（email → sub の順）。無ければ None。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization.removeprefix("Bearer "), verify=False)
    except ValueError:
        return None
    if claims.get("aud") != get_settings().kuroko_api_url:
        return None
    return claims.get("email") or claims.get("sub")


def is_allowed_agent(authorization: str | None) -> bool:
    expected = get_settings().agent_kuroko_principal
    return bool(expected) and agent_identity(authorization) == expected


class AgentOnly:
    """`/mcp` に載せる ASGI ミドルウェア。許可された agent-kuroko 以外は 403。"""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if not is_allowed_agent(headers.get("authorization")):
                body = json.dumps({"detail": "forbidden"}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self._app(scope, receive, send)
