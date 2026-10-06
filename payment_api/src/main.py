"""payment-api（非公開の Cloud Run）。AP2 の委任状・Policy Gate 6.3・振込依頼。ARCHITECTURE 4.3。"""

import logging

from fastapi import FastAPI

from src.routers import health, mandates, payments


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="payment-api", version="0.1.0")
    app.include_router(health.router)
    app.include_router(mandates.router)
    app.include_router(payments.router)
    return app


app = create_app()
