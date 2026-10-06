from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 既定は本番側（安全側）。ローカルは .env で local・スタブ・メモリにする
    environment: str = "production"
    google_cloud_project: str = ""

    # stub: メモリ上の疑似銀行（ローカル・テスト）／ sunabar: 実機
    bank_mode: Literal["stub", "sunabar"] = "sunabar"
    # memory: プロセス内（ローカル・テスト）／ firestore: 名前付きデータベース `bank`
    store_backend: Literal["memory", "firestore"] = "firestore"
    firestore_database: str = "bank"

    # Secret Manager のシークレット名（projects/<p>/secrets/sunabar-tokens）
    # 中身は 口座ラベル → トークン の JSON
    sunabar_tokens_secret: str = ""
    sunabar_base_url: str = "https://api.sunabar.gmo-aozora.com/personal/v1"

    # 呼び出し元の検査（ARCHITECTURE 6章）。audience は自分の URL
    bank_adapter_url: str = ""
    api_service_account: str = ""  # sa-api: 幹事口座の入金明細だけ
    payment_api_service_account: str = ""  # sa-payment-api: 振込・本人の明細・認可

    # 振込依頼の承認期限（銀行の承認は依頼から約10分。SPEC 8.7）
    approval_ttl_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
