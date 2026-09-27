"""kuroko-api（後段。非公開）のアプリ（ARCHITECTURE 4.2）。

/tasks/*（Cloud Tasks から）などを受ける。
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routers import health, tasks


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = FastAPI(title="kuroko-api", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(tasks.router)

    return app


app = create_app()
