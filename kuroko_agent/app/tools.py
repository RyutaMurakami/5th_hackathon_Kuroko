"""統括エージェントのツール（`kuroko-api` の `/mcp` の MCP ツールセットだけ。ARCHITECTURE 4.2）。

`KUROKO_MCP_URL` が設定されているときだけ接続する（ローカルの会話の確認では、ツールなしで動く）。
接続先は、Agent Gateway の出口を通る（デプロイ後に、Registry への登録と IAM を設定する）。
公開されているツールのうち、`callbacks.ALLOWED_TOOLS` にあるものだけを渡し（`tool_filter`）、
呼び出しの直前にも `before_tool_callback` が同じ許可リストで止める（二重に守る）。
"""

import os

from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from app.callbacks import ALLOWED_TOOLS


def build_tools() -> list:
    url = os.environ.get("KUROKO_MCP_URL", "").strip()
    if not url:
        return []
    # ローカルの確認用に、Authorization ヘッダーを足せる（デプロイでは Agent Gateway が身元を扱う）
    bearer = os.environ.get("KUROKO_MCP_BEARER", "").strip()
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else None
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=url, headers=headers, timeout=60.0),
            tool_filter=sorted(ALLOWED_TOOLS),
        )
    ]
