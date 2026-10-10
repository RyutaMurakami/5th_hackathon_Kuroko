FROM python:3.12-slim AS base
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
# 規程（policies/company_rules.yaml）。リポジトリのルートにあるので、CD がビルドの前に backend/policies/ へ写す
# （deploy.yml）。コードは、`/policies/company_rules.yaml` を読む（services/policy.py）
COPY policies /policies
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
# kuroko-api と kuroko-gateway は同じイメージ。起動するアプリは APP_MODULE で選ぶ（infra/terraform/cloud_run.tf）
CMD exec uvicorn "${APP_MODULE:-src.main:app}" --host 0.0.0.0 --port "${PORT:-8080}"
