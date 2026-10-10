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


SCHEDULER_SA = "sa-scheduler@test.iam.gserviceaccount.com"


class FakeRetro:
    async def collect_feedback(self, event_id):
        return {"started": True, "invited": 9}

    async def tick(self):
        return {"started": 1, "reminded": 0, "closed": 0}


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
    monkeypatch.setenv("SCHEDULER_SERVICE_ACCOUNT", SCHEDULER_SA)
    monkeypatch.setattr(tasks, "get_retro", lambda: FakeRetro())
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


async def test_feedback_requests_are_internal_only(client):
    ok = await client.post(
        "/tasks/internal/feedback-requests",
        json={"event_id": "ev1"},
        headers={"Authorization": _token(API_SA)},
    )
    assert ok.json() == {"started": True, "invited": 9}
    for who in (GATEWAY_SA, SCHEDULER_SA, "attacker@example.com"):
        res = await client.post(
            "/tasks/internal/feedback-requests",
            json={"event_id": "ev1"},
            headers={"Authorization": _token(who)},
        )
        assert res.status_code == 403


async def test_the_daily_retrospective_job_accepts_only_the_scheduler(client):
    ok = await client.post(
        "/tasks/scheduled/retrospectives", headers={"Authorization": _token(SCHEDULER_SA)}
    )
    assert ok.json() == {"started": 1, "reminded": 0, "closed": 0}  # 件数だけ。個人は含まない
    for who in (API_SA, GATEWAY_SA, "attacker@example.com"):
        res = await client.post(
            "/tasks/scheduled/retrospectives", headers={"Authorization": _token(who)}
        )
        assert res.status_code == 403
    assert (await client.post("/tasks/scheduled/retrospectives")).status_code == 403


async def test_the_sandbox_cleanup_job_accepts_only_the_scheduler_and_matches_terraform(
    client, monkeypatch
):
    from pathlib import Path

    from src.services import container  # noqa: F401

    class Dash:
        def purge_expired_sandbox(self):
            return 2

    monkeypatch.setattr(tasks, "get_dashboard", lambda: Dash())
    path = "/tasks/scheduled/sandbox-cleanup"
    ok = await client.post(path, headers={"Authorization": _token(SCHEDULER_SA)})
    assert ok.status_code == 200 and ok.json() == {"deleted": 2}
    for who in (API_SA, GATEWAY_SA, "attacker@example.com"):
        res = await client.post(path, headers={"Authorization": _token(who)})
        assert res.status_code == 403
    # Terraform の Scheduler が呼ぶパスと一致している（食い違うと、削除が動かない）
    tf = (Path(__file__).resolve().parents[2] / "infra/terraform/tasks.tf").read_text()
    assert f'path        = "{path}"' in tf
