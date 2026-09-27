"""kuroko-gateway の Slack の入口（ARCHITECTURE 4.1）。

署名検証 → Cloud Tasks に投入 → 3秒以内に Ack だけを返す。
"""

import json

from fastapi import APIRouter, HTTPException, Request
from slack_sdk.signature import SignatureVerifier

from src.clients.cloud_tasks import enqueue_kuroko_api
from src.config import get_settings
from src.services.slack_intake import extract_direct_message

router = APIRouter(prefix="/slack")


@router.post("/events")
async def events(request: Request) -> dict[str, str]:
    body = await request.body()
    verifier = SignatureVerifier(get_settings().slack_signing_secret)
    if not verifier.is_valid(
        body=body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        signature=request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    message = extract_direct_message(payload)
    if message:
        # タスク名に event_id を使い、Slack の再送（3秒で Ack できなかったとき）を1回にまとめる
        await enqueue_kuroko_api(
            "/tasks/slack/message", message.model_dump(), task_id=f"slack-dm-{message.event_id}"
        )
    return {"status": "ok"}
