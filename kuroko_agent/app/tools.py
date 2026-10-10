"""統括エージェントのツール（`kuroko-api` の `/mcp` の MCP ツールセットだけ。ARCHITECTURE 4.2）。

`KUROKO_MCP_URL` が設定されているときだけ接続する（ローカルの会話の確認では、ツールなしで動く）。
公開されているツールのうち、`callbacks.ALLOWED_TOOLS` にあるものだけを渡し（`tool_filter`）、
呼び出しの直前にも `before_tool_callback` が同じ許可リストで止める（二重に守る）。

**認証**（`kuroko-api` は非公開の Cloud Run。呼び出しには、宛先を `kuroko-api` にした ID トークンが要る）:
Agent identity（このエージェント自身の身元）は、専用の呼び出し用サービスアカウント
（`KUROKO_MCP_INVOKER_SA`）を**偽装して** ID トークンを作る。偽装できるのは、このエージェントの
Agent identity だけ（IAM の `serviceAccountTokenCreator`。Terraform）。`kuroko-api` は、その SA の
メールだけを `/mcp` に通す。トークンは期限の手前まで使い回す。
"""

import os
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from app.callbacks import ALLOWED_TOOLS

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_REFRESH_MARGIN_SECONDS = 300


def audience_of(url: str) -> str:
    """宛先（aud）は、URL のスキームとホストだけ（Cloud Run の ID トークンの規則）。"""
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def id_token_header_provider(invoker_sa: str, audience: str) -> Callable[[Any], dict[str, str]]:
    """Agent identity から、呼び出し用 SA を偽装して ID トークンを作り、ヘッダーに入れる。"""
    cache: dict[str, Any] = {"token": None, "expiry": 0.0}

    def mint() -> None:
        import google.auth
        from google.auth import impersonated_credentials
        from google.auth.transport.requests import Request

        source, _ = google.auth.default(scopes=_SCOPES)
        target = impersonated_credentials.Credentials(
            source_credentials=source, target_principal=invoker_sa, target_scopes=_SCOPES
        )
        creds = impersonated_credentials.IDTokenCredentials(
            target, target_audience=audience, include_email=True
        )
        creds.refresh(Request())
        cache["token"] = creds.token
        expiry = getattr(creds, "expiry", None)
        cache["expiry"] = expiry.timestamp() if expiry else time.time() + 3000

    def provider(_context: Any) -> dict[str, str]:
        if cache["token"] is None or cache["expiry"] - time.time() < _REFRESH_MARGIN_SECONDS:
            mint()  # 失敗したら例外のまま（ツールが使えないだけで、別の身元には落とさない）
        return {"Authorization": f"Bearer {cache['token']}"}

    return provider


def build_tools() -> list:
    url = os.environ.get("KUROKO_MCP_URL", "").strip()
    if not url:
        return []
    headers: dict[str, str] | None = None
    provider = None
    invoker = os.environ.get("KUROKO_MCP_INVOKER_SA", "").strip()
    if invoker:
        provider = id_token_header_provider(invoker, audience_of(url))
    else:
        # ローカルの確認用に、固定の Authorization ヘッダーを足せる
        bearer = os.environ.get("KUROKO_MCP_BEARER", "").strip()
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else None
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url, headers=headers, timeout=60.0
            ),
            tool_filter=sorted(ALLOWED_TOOLS),
            header_provider=provider,
        )
    ]
