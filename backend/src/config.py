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

    # --- Web ダッシュボード（B14。SPEC 4.3・7.5・7.6）---
    # Firebase のプロジェクト（ID トークンの aud・iss の検査に使う。空なら全て拒否）
    firebase_project_id: str = ""
    # 予約画面・領収書のアップロード先の Cloud Storage バケット（署名付きURLで直接アップロード）
    upload_bucket: str = ""
    upload_url_ttl_seconds: int = 300

    # --- Slack（値は Secret Manager から Cloud Run の環境変数で渡る。secrets.tf）---
    slack_signing_secret: str = ""  # kuroko-gateway だけ
    slack_bot_token: str = ""  # kuroko-api だけ

    # --- Cloud Tasks（kuroko-gateway → kuroko-api。ARCHITECTURE 6章）---
    kuroko_api_url: str = ""
    tasks_queue_default: str = "kuroko-default"
    # 委任状の署名・取り消し（kuroko-gateway → payment-api）のキュー
    tasks_queue_mandates: str = "kuroko-mandates"
    # タスクの OIDC 主体（投入した側の SA）
    tasks_service_account: str = ""
    # /tasks/slack/* が受け付ける呼び出し元（sa-gateway）
    gateway_service_account: str = ""

    # --- 請求・入金の確認（TASKS B13）---
    payment_api_url: str = ""
    bank_adapter_url: str = ""
    # /tasks/internal/* が受け付ける呼び出し元（kuroko-api 自身。sa-api）
    api_service_account: str = ""
    # /api/dashboard/* が受け付ける呼び出し元（kuroko-dashboard。sa-dashboard）
    dashboard_service_account: str = ""
    # /tasks/scheduled/* が受け付ける呼び出し元（sa-scheduler。Cloud Scheduler）
    scheduler_service_account: str = ""
    # 請求（Checkout）の署名鍵（Cloud KMS `claim-signing` の鍵バージョン。ES256）
    kms_claim_key_version: str = ""
    checkout_ttl_seconds: int = 3 * 24 * 3600

    # --- 外部 API のキー（Secret Manager から環境変数で渡る。TASKS B18）---
    ekispert_api_key: str = ""
    maps_api_key: str = ""

    # --- MCP（エージェント用のツールの入口。TASKS B21）---
    # `/mcp` を呼べるエージェントの身元（Agent Gateway 経由の agent-kuroko の ID トークンの
    # email/sub）。
    # 空のあいだは、すべて拒否する（fail closed。V1 の確認後に設定する）
    agent_kuroko_principal: str = ""

    # --- 隔離抽出エージェント（Agent Runtime。TASKS B26）---
    # 空のあいだは、振り返りのコメントだけ、キーワードの仮実装で語彙に落とす
    extract_agent_engine: str = ""

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
