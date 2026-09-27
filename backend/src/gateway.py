"""kuroko-gateway（前段。公開）のアプリ（ARCHITECTURE 4.1）。

Slack の署名検証・Ack・Cloud Tasks への投入だけを行う。

業務判断・外部 API の呼び出し・エージェントの呼び出しはしない。kuroko-api と同じイメージで、
Cloud Run の環境変数 APP_MODULE=src.gateway:app で起動する。
"""

import logging

from fastapi import FastAPI

from src.routers import health, slack


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="kuroko-gateway", version="0.1.0")
    app.include_router(health.router)
    app.include_router(slack.router)
    return app


app = create_app()
