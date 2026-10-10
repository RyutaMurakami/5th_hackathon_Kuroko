"""kuroko-api（後段。非公開）のアプリ（ARCHITECTURE 4.2）。

/tasks/*（Cloud Tasks から）・/mcp（エージェント用のツール。agent-kuroko だけ）などを受ける。
"""

import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.transport_security import TransportSecuritySettings

from src.config import get_settings
from src.routers import dashboard, health, tasks
from src.routers.mcp import build_mcp
from src.services.mcp_auth import AgentOnly, McpPathNormalizer


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    # MCP の Streamable HTTP（ステートレス・JSON 応答。Cloud Run のインスタンスをまたいでも動く）
    mcp = build_mcp()  # アプリごとに新しいサーバー（セッションの管理は1回だけ開始できる）
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        # SDK のホスト名の検査（DNS リバインディング対策）は、ローカルのサーバー向け。
        # kuroko-api は非公開の Cloud Run（IAM）で、`/mcp` は agent-kuroko の身元で守る
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="kuroko-api", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(dashboard.router)
    # `/mcp` は、Agent Gateway 経由の agent-kuroko だけ（それ以外のエージェント・SA は 403）
    app.mount("/mcp", AgentOnly(mcp_app))
    app.add_middleware(McpPathNormalizer)  # `/mcp` も `/mcp/` と同じに扱う（リダイレクトしない）

    return app


app = create_app()
