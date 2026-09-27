import hashlib
import hmac
import json
import time

import pytest

from src.routers import slack as slack_router
from tests.conftest import SIGNING_SECRET


def _signed(body: dict, secret: str = SIGNING_SECRET) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/json",
    }


@pytest.fixture
def enqueued(monkeypatch):
    calls = []

    async def fake_enqueue(path, payload, task_id):
        calls.append((path, payload, task_id))

    monkeypatch.setattr(slack_router, "enqueue_kuroko_api", fake_enqueue)
    return calls


async def test_invalid_signature_is_rejected(gateway_client, enqueued):
    raw, headers = _signed({"type": "url_verification", "challenge": "x"}, secret="wrong")
    response = await gateway_client.post("/slack/events", content=raw, headers=headers)
    assert response.status_code == 401
    assert enqueued == []


async def test_missing_signature_headers_are_rejected(gateway_client, enqueued):
    response = await gateway_client.post("/slack/events", content=b"{}")
    assert response.status_code == 401
    assert enqueued == []


async def test_url_verification_returns_challenge(gateway_client):
    raw, headers = _signed({"type": "url_verification", "challenge": "abc"})
    response = await gateway_client.post("/slack/events", content=raw, headers=headers)
    assert response.json() == {"challenge": "abc"}


async def test_direct_message_is_enqueued_with_event_id(gateway_client, enqueued):
    raw, headers = _signed(
        {
            "type": "event_callback",
            "event_id": "Ev123",
            "team_id": "T1",
            "event": {
                "type": "message",
                "channel_type": "im",
                "user": "U1",
                "channel": "D1",
                "text": "hi",
                "ts": "1.0",
            },
        }
    )
    response = await gateway_client.post("/slack/events", content=raw, headers=headers)
    assert response.status_code == 200
    assert len(enqueued) == 1
    path, payload, task_id = enqueued[0]
    assert path == "/tasks/slack/message"
    assert task_id == "slack-dm-Ev123"
    assert payload["text"] == "hi"


async def test_bot_message_is_not_enqueued(gateway_client, enqueued):
    raw, headers = _signed(
        {
            "type": "event_callback",
            "event_id": "Ev124",
            "event": {
                "type": "message",
                "channel_type": "im",
                "bot_id": "B1",
                "channel": "D1",
                "text": "hi",
            },
        }
    )
    response = await gateway_client.post("/slack/events", content=raw, headers=headers)
    assert response.status_code == 200
    assert enqueued == []
