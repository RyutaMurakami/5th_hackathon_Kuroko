import base64
import json

import pytest

from src.services import slack_conversation
from tests.conftest import GATEWAY_SA, KUROKO_API_URL

MESSAGE = {
    "event_id": "Ev1",
    "team_id": "T1",
    "user_id": "U1",
    "channel_id": "D1",
    "text": "hi",
    "ts": "1.0",
}


def _token(email: str, aud: str = KUROKO_API_URL) -> str:
    # Cloud Run が署名を外したあとの形（署名の検証は Cloud Run の IAM が済ませている）
    def enc(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = enc({"alg": "RS256", "typ": "JWT"})
    claims = enc({"aud": aud, "email": email, "email_verified": True})
    return f"Bearer {header}.{claims}.SIG"


@pytest.fixture
def slack_io(monkeypatch):
    posted = []

    async def fake_reply(user_key, text):
        return f"echo:{user_key}:{text}"

    async def fake_post(channel_id, text):
        posted.append((channel_id, text))

    monkeypatch.setattr(slack_conversation.provisional_agent, "reply", fake_reply)
    monkeypatch.setattr(slack_conversation.slack, "post_message", fake_post)
    return posted


async def test_gateway_caller_gets_agent_reply(client, slack_io):
    response = await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert response.status_code == 200
    assert slack_io == [("D1", "echo:slack:T1:U1:hi")]


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        _token("sa-api@test.iam.gserviceaccount.com"),
        _token(GATEWAY_SA, aud="https://other.test"),
    ],
)
async def test_other_callers_are_rejected(client, slack_io, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    response = await client.post("/tasks/slack/message", json=MESSAGE, headers=headers)
    assert response.status_code == 403
    assert slack_io == []


async def test_agent_failure_posts_fixed_text(client, slack_io, monkeypatch):
    async def broken(user_key, text):
        raise RuntimeError("boom")

    monkeypatch.setattr(slack_conversation.provisional_agent, "reply", broken)
    response = await client.post(
        "/tasks/slack/message", json=MESSAGE, headers={"Authorization": _token(GATEWAY_SA)}
    )
    assert response.status_code == 200
    assert slack_io == [("D1", slack_conversation.FALLBACK_TEXT)]
