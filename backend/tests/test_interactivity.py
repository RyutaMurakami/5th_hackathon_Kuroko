"""kuroko-gateway の /slack/interactivity と、タスクの決め方（署名検証済みの操作だけが起点）。"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from src.models.slack import Action, encode_value
from src.routers import slack as slack_router
from src.services.slack_interactions import extract_interaction, plan_tasks
from tests.conftest import SIGNING_SECRET

SLACK_USER = "U_KURAO"
CONSENT = {
    "k": "consent", "e": "ev1", "u": "kurao", "s": SLACK_USER, "p": "kanji",
    "c": 6000, "x": "2026-11-06T00:00:00+00:00",
}  # fmt: skip


def payload(action: Action, value: dict, user=SLACK_USER) -> dict:
    return {
        "type": "block_actions",
        "user": {"id": user},
        "team": {"id": "T1"},
        "channel": {"id": "D1"},
        "message": {"ts": "1.2"},
        "response_url": "https://hooks.slack.test/x",
        "actions": [{"action_id": action.value, "value": encode_value(value)}],
    }


def signed_form(body: dict, secret: str = SIGNING_SECRET) -> tuple[bytes, dict]:
    raw = urlencode({"payload": json.dumps(body)}).encode()
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    }


@pytest.fixture
def enqueued(monkeypatch):
    calls = []

    async def to_api(path, body, task_id):
        calls.append(("kuroko-api", path, body, task_id))

    async def to_pay(path, body, task_id):
        calls.append(("payment-api", path, body, task_id))

    monkeypatch.setattr(slack_router, "enqueue_kuroko_api", to_api)
    monkeypatch.setattr(slack_router, "enqueue_payment_api", to_pay)
    return calls


async def test_invalid_signature_enqueues_nothing(gateway_client, enqueued):
    raw, headers = signed_form(payload(Action.CONSENT, CONSENT), secret="wrong")
    res = await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    assert res.status_code == 401 and enqueued == []
    assert (await gateway_client.post("/slack/interactivity", content=raw)).status_code == 401


async def test_consent_signs_the_mandate_at_payment_api_directly_and_records_the_rsvp(
    gateway_client, enqueued
):
    raw, headers = signed_form(payload(Action.CONSENT, CONSENT))
    res = await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    assert res.json() == {"status": "ok"}
    (t1, p1, b1, id1), (t2, p2, b2, _) = enqueued
    assert (t1, p1) == ("payment-api", "/mandates")  # kuroko-api を経由しない
    assert b1 == {
        "user_id": "kurao", "event_id": "ev1", "payee_user_id": "kanji", "cap_yen": 6000,
        "expires_at": "2026-11-06T00:00:00+00:00", "signed_via": b2["interaction_id"],
    }  # fmt: skip
    assert (t2, p2) == ("kuroko-api", "/tasks/slack/interaction")
    assert b2["user_id"] == SLACK_USER and b2["action"] == "consent"


async def test_someone_else_pressing_the_button_does_nothing(gateway_client, enqueued):
    for action, value in ((Action.CONSENT, CONSENT), (Action.APPROVE, {"s": SLACK_USER, "e": "e"})):
        raw, headers = signed_form(payload(action, value, user="U_OTHER"))
        res = await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
        assert res.json() == {"status": "rejected"}
    assert enqueued == []


async def test_revoke_goes_to_payment_api_and_approve_goes_to_kuroko_api(gateway_client, enqueued):
    raw, headers = signed_form(
        payload(Action.REVOKE, {"k": "revoke", "m": "ev1:kurao", "s": SLACK_USER})
    )
    await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    assert enqueued[0][:2] == ("payment-api", "/mandates/ev1:kurao/revoke")
    enqueued.clear()
    approve = {"k": "approve", "e": "ev1", "h": "hash", "s": SLACK_USER}
    raw, headers = signed_form(payload(Action.APPROVE, approve))
    await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    assert [(t, p) for t, p, *_ in enqueued] == [("kuroko-api", "/tasks/slack/interaction")]


async def test_double_click_has_the_same_task_ids(gateway_client, enqueued):
    for _ in range(2):
        raw, headers = signed_form(payload(Action.CONSENT, CONSENT))
        await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    ids = [c[3] for c in enqueued]
    assert ids[:2] == ids[2:]  # Cloud Tasks が重複として弾く


async def test_other_blocks_and_malformed_payloads_are_ignored_or_rejected(
    gateway_client, enqueued
):
    raw, headers = signed_form({"type": "view_submission"})
    assert (
        await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    ).json() == {"status": "ignored"}
    unknown = payload(Action.CONSENT, CONSENT)
    unknown["actions"][0]["action_id"] = "something_else"
    raw, headers = signed_form(unknown)
    assert (
        await gateway_client.post("/slack/interactivity", content=raw, headers=headers)
    ).json() == {"status": "ignored"}
    import hashlib as h
    import hmac as hm
    import time as t

    raw = b"not-a-form"
    ts = str(int(t.time()))
    sig = "v0=" + hm.new(SIGNING_SECRET.encode(), f"v0:{ts}:".encode() + raw, h.sha256).hexdigest()
    bad = await gateway_client.post(
        "/slack/interactivity",
        content=raw,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert bad.status_code == 400
    assert enqueued == []


def test_consent_with_a_broken_value_plans_nothing():
    broken = {k: v for k, v in CONSENT.items() if k != "c"}
    i = extract_interaction(payload(Action.CONSENT, broken))
    assert plan_tasks(i) == []
    non_numeric = CONSENT | {"c": "abc"}
    assert plan_tasks(extract_interaction(payload(Action.CONSENT, non_numeric))) == []


def test_home_opened_event_is_extracted():
    from src.services.slack_interactions import extract_home_opened

    ev = {"type": "event_callback", "event_id": "E1", "team_id": "T1",
          "event": {"type": "app_home_opened", "user": "U1", "tab": "home"}}  # fmt: skip
    assert extract_home_opened(ev).user_id == "U1"
    assert extract_home_opened({**ev, "event": {**ev["event"], "tab": "messages"}}) is None
