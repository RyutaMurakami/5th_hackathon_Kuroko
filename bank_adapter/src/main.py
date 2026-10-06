"""bank-adapter（非公開の Cloud Run）。sunabar への窓口。ARCHITECTURE 4.4。"""

import logging

from fastapi import FastAPI

from src.routers import bank, health


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="bank-adapter", version="0.1.0")
    app.include_router(health.router)
    app.include_router(bank.router)
    return app


app = create_app()
