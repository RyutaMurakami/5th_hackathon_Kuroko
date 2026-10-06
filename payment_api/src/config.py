from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 既定は本番側（安全側）。ローカルは .env で local・テスト用の鍵・メモリ・スタブにする
    environment: str = "production"
    google_cloud_project: str = ""
    firestore_database: str = "(default)"

    # local: テスト用の鍵（メモリ上）／ kms: Cloud KMS（ES256。P-256）
    signer_mode: Literal["local", "kms"] = "kms"
    kms_participant_key_version: str = ""
    kms_payment_agent_key_version: str = ""

    store_backend: Literal["memory", "firestore"] = "firestore"
    # stub: 銀行アダプタを呼ばない（ローカル・テスト）／ http: bank-adapter を呼ぶ
    bank_mode: Literal["stub", "http"] = "http"
    bank_adapter_url: str = ""

    # 呼び出し元の検査（ARCHITECTURE 6章）。audience は自分の URL
    payment_api_url: str = ""
    gateway_service_account: str = ""  # sa-gateway: 委任状の署名・取り消し
    api_service_account: str = ""  # sa-api: 支払いの開始・参照
    scheduler_service_account: str = ""  # sa-scheduler: ポーリング（B10）

    # 委任状を1回の支払いに絞るときの Closed Mandate の有効期間
    closed_mandate_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
