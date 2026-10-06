FROM python:3.12-slim AS base
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# AP2 SDK を GitHub から入れるため git が要る
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8080}"
