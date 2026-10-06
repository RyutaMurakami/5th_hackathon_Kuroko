import base64
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.clients.stub_bank import StubBank
from src.config import Settings, get_settings
from src.db.store import MemoryStore
from src.main import create_app
from src.services.container import get_service
from src.services.transfers import BankService

URL = "https://bank-adapter.test"
API_SA = "sa-api@kuroko.iam.gserviceaccount.com"
PAYMENT_SA = "sa-payment-api@kuroko.iam.gserviceaccount.com"
AGENT = "agent-kuroko@kuroko.iam.gserviceaccount.com"


def token(email: str, aud: str = URL, verified: bool = True) -> dict[str, str]:
    """Cloud Run が署名を外して渡す ID トークンの形（署名は検証しない）。"""

    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    claims = {"email": email, "aud": aud, "email_verified": verified}
    return {"Authorization": f"Bearer {b64({'alg': 'none'})}.{b64(claims)}."}


class Clock:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t


@pytest.fixture
def bank() -> StubBank:
    return StubBank()


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore()
    # 仮名 user_id → 口座ラベル（デモ参加者の一部）
    s.set_label("organizer", "acct01")
    s.set_label("approver", "acct02")
    s.set_label("member", "acct03")
    return s


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(bank, store, clock):
    settings = Settings(
        bank_adapter_url=URL,
        api_service_account=API_SA,
        payment_api_service_account=PAYMENT_SA,
        approval_ttl_seconds=600,
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    service = BankService(store=store, bank=bank, approval_ttl_seconds=600, now=clock)
    app.dependency_overrides[get_service] = lambda: service
    # caller_auth は get_settings() を直接呼ぶので、キャッシュ済みの設定を差し替える
    get_settings.cache_clear()
    import src.services.caller_auth as ca

    ca.get_settings = lambda: settings
    return TestClient(app)
