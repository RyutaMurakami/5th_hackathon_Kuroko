"""/tasks/internal/*（請求の作成・入金の確認）は、kuroko-api 自身（sa-api）だけが呼べる。"""

import pytest

from src.config import get_settings
from src.routers import tasks
from src.services.billing import CheckoutRun, CollectionRun, UnknownEvent
from src.services.policy_gates import Gate
from tests.conftest import GATEWAY_SA
from tests.test_tasks import _token

API_SA = "sa-api@test.iam.gserviceaccount.com"
PATHS = ["/tasks/internal/checkouts", "/tasks/internal/collections"]


class FakeBilling:
    async def create_checkouts(self, event_id):
        if event_id == "nope":
            raise UnknownEvent
        if event_id == "blocked":
            return CheckoutRun(ok=False, failures=[Gate.APPROVAL_MISSING])
        return CheckoutRun(ok=True, outcomes={"ito": "awaiting_bank_approval"})

    async def confirm_incoming_payments(self, event_id):
        if event_id == "nope":
            raise UnknownEvent
        return CollectionRun(received=["ito"], missing=["kato"], all_received=False)


@pytest.fixture(autouse=True)
def billing(monkeypatch):
    monkeypatch.setenv("API_SERVICE_ACCOUNT", API_SA)
    get_settings.cache_clear()
    monkeypatch.setattr(tasks, "get_billing", lambda: FakeBilling())


@pytest.mark.parametrize("path", PATHS)
async def test_only_kuroko_api_itself_can_call_the_internal_tasks(client, path):
    ok = await client.post(
        path, json={"event_id": "ev1"}, headers={"Authorization": _token(API_SA)}
    )
    assert ok.status_code == 200
    for who in (GATEWAY_SA, "agent@x.iam.gserviceaccount.com", "attacker@example.com"):
        res = await client.post(
            path, json={"event_id": "ev1"}, headers={"Authorization": _token(who)}
        )
        assert res.status_code == 403
    assert (await client.post(path, json={"event_id": "ev1"})).status_code == 403
    wrong_aud = _token(API_SA, aud="https://other")
    res = await client.post(path, json={"event_id": "ev1"}, headers={"Authorization": wrong_aud})
    assert res.status_code == 403


async def test_checkouts_report_the_gate_failures_and_outcomes(client):
    h = {"Authorization": _token(API_SA)}
    res = await client.post("/tasks/internal/checkouts", json={"event_id": "ev1"}, headers=h)
    assert res.json() == {
        "ok": True, "failures": [], "outcomes": {"ito": "awaiting_bank_approval"}, "errors": {},
    }  # fmt: skip
    res = await client.post("/tasks/internal/checkouts", json={"event_id": "blocked"}, headers=h)
    assert res.json()["ok"] is False and res.json()["failures"] == ["approval_missing"]
    missing = await client.post("/tasks/internal/checkouts", json={"event_id": "nope"}, headers=h)
    assert missing.status_code == 404


async def test_collections_report_who_has_paid(client):
    h = {"Authorization": _token(API_SA)}
    res = await client.post("/tasks/internal/collections", json={"event_id": "ev1"}, headers=h)
    assert res.json() == {
        "received": ["ito"], "missing": ["kato"], "amount_mismatch": [], "all_received": False,
    }  # fmt: skip
    res = await client.post("/tasks/internal/collections", json={"event_id": "nope"}, headers=h)
    assert res.status_code == 404


async def test_internal_tasks_are_disabled_when_the_service_account_is_not_configured(
    client, monkeypatch
):
    monkeypatch.setenv("API_SERVICE_ACCOUNT", "")
    get_settings.cache_clear()
    res = await client.post(
        "/tasks/internal/checkouts", json={"event_id": "ev1"}, headers={"Authorization": _token("")}
    )
    assert res.status_code == 403
