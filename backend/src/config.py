from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    port: int = 8080
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    google_cloud_project: str = ""
    # リソース（Cloud Run・Cloud Tasks など）のリージョン。Terraform が渡す
    google_cloud_region: str = "us-central1"
    # Gemini の呼び出し先。新しいモデルは global エンドポイントに
    # しかないことがある
    google_cloud_location: str = "global"

    firestore_database_id: str = "(default)"

    # --- Slack（値は Secret Manager から Cloud Run の環境変数で渡る。secrets.tf）---
    slack_signing_secret: str = ""  # kuroko-gateway だけ
    slack_bot_token: str = ""  # kuroko-api だけ

    # --- Cloud Tasks（kuroko-gateway → kuroko-api。ARCHITECTURE 6章）---
    kuroko_api_url: str = ""
    tasks_queue_default: str = "kuroko-default"
    # タスクの OIDC 主体（投入した側の SA）
    tasks_service_account: str = ""
    # /tasks/slack/* が受け付ける呼び出し元（sa-gateway）
    gateway_service_account: str = ""

    # --- 統括エージェント（Agent Runtime。TASKS B22）---
    # 空のあいだは仮のエージェント（下）で返す。値は「projects/<番号>/locations/<リージョン>/
    # reasoningEngines/<ID>」。デプロイ後に Terraform の変数で渡す（infra/terraform/variables.tf）
    kuroko_agent_engine: str = ""
    kuroko_agent_timeout_seconds: float = 90.0

    # --- 仮のエージェント（TASKS B16a。Agent Runtime の統括エージェントができたら差し替える）---
    provisional_agent_model: str = "gemini-3.8-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
