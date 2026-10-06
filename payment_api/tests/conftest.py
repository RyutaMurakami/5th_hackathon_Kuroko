import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.clients.fake_bank_adapter import FakeBankAdapter
from src.clients.signers import LocalSigner
from src.config import Settings
from src.db.store import MemoryStore
from src.main import create_app
from src.services import caller_auth
from src.services.checkout import AcceptAllCheckouts
from src.services.container import Services, get_services
from src.services.mandates import MandateService
from src.services.payments import PaymentService
from src.services.policy_gate import PolicyGate

URL = "https://payment-api.test"
GATEWAY_SA = "sa-gateway@kuroko.iam.gserviceaccount.com"
API_SA = "sa-api@kuroko.iam.gserviceaccount.com"
AGENT = "agent-payment@kuroko.iam.gserviceaccount.com"
T0 = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def token(email: str, aud: str = URL, verified: bool = True) -> dict[str, str]:
    """Cloud Run が署名を外して渡す ID トークンの形（署名は検証しない）。"""

    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    claims = {"email": email, "aud": aud, "email_verified": verified}
    return {"Authorization": f"Bearer {b64({'alg': 'none'})}.{b64(claims)}."}


GATEWAY = token(GATEWAY_SA)
API = token(API_SA)


class Clock:
    def __init__(self) -> None:
        self.t = T0

    def __call__(self) -> datetime:
        return self.t


class Env:
    """テスト用の組み立て（署名鍵はテスト用。KMS は使わない）。"""

    def __init__(self, checkout=None) -> None:
        self.store = MemoryStore()
        self.clock = Clock()
        self.bank = FakeBankAdapter()
        self.participant = LocalSigner()
        self.agent = LocalSigner()
        self.mandates = MandateService(
            store=self.store,
            participant_signer=self.participant,
            agent_signer=self.agent,
            now=self.clock,
        )
        self.checkout = checkout or AcceptAllCheckouts()
        gate = PolicyGate(
            store=self.store,
            participant_signer=self.participant,
            bank=self.bank,
            checkout_verifier=self.checkout,
            mandate_lookup=self.mandates.current,
        )
        self.payments = PaymentService(
            store=self.store,
            gate=gate,
            agent_signer=self.agent,
            participant_signer=self.participant,
            bank=self.bank,
            closed_mandate_ttl_seconds=3600,
            now=self.clock,
        )


@pytest.fixture
def env() -> Env:
    return Env()


def make_client(env: Env) -> TestClient:
    settings = Settings(
        payment_api_url=URL, gateway_service_account=GATEWAY_SA, api_service_account=API_SA
    )
    caller_auth.get_settings = lambda: settings
    app = create_app()
    app.dependency_overrides[get_services] = lambda: Services(
        mandates=env.mandates, payments=env.payments
    )
    return TestClient(app)


@pytest.fixture
def client(env) -> TestClient:
    return make_client(env)


def sign_body(user="member", event="ev1", payee="organizer", cap=5000, days=7, **kw) -> dict:
    return {
        "user_id": user,
        "event_id": event,
        "payee_user_id": payee,
        "cap_yen": cap,
        "expires_at": (T0 + timedelta(days=days)).isoformat(),
        "signed_via": "slack-interaction-1",
    } | kw


def pay_body(payment_id="p1", user="member", event="ev1", payee="organizer", amount=3300, **kw):
    return {
        "payment_id": payment_id,
        "event_id": event,
        "payer_user_id": user,
        "payee_user_id": payee,
        "amount_yen": amount,
        "checkout_jwt": "checkout.jwt.signed",
        "checkout_hash": "hash-of-split-table",
    } | kw
