"""kuroko-gateway の Slack の入口（ARCHITECTURE 4.1）。

署名検証 → Cloud Tasks に投入 → 3秒以内に Ack だけを返す。業務判断・外部 API の呼び出しはしない。

- `/slack/events`: Events API（DM・App Home を開いた）
- `/slack/interactivity`: ボタン操作。委任の同意・取り消しは `payment-api` に直接タスクを投入し、
  それ以外は `kuroko-api` に渡す（署名検証済みの Slack 操作だけが、委任・承認のきっかけになる）
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from slack_sdk.signature import SignatureVerifier

from src.clients.cloud_tasks import enqueue_kuroko_api, enqueue_payment_api
from src.config import get_settings
from src.services.slack_intake import extract_direct_message
from src.services.slack_interactions import (
    InvalidInteraction,
    extract_home_opened,
    extract_interaction,
    parse_form_payload,
    plan_tasks,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slack")


def _verify(request: Request, body: bytes) -> None:
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    verifier = SignatureVerifier(get_settings().slack_signing_secret)
    # ヘッダーが欠けている・数値でないと slack_sdk が例外を出すので、先に弾く
    if not timestamp.isdigit() or not verifier.is_valid(
        body=body, timestamp=timestamp, signature=signature
    ):
        raise HTTPException(status_code=401, detail="invalid signature")


@router.post("/events")
async def events(request: Request) -> dict[str, str]:
    body = await request.body()
    _verify(request, body)

    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    message = extract_direct_message(payload)
    if message:
        # タスク名に event_id を使い、Slack の再送（3秒で Ack できなかったとき）を1回にまとめる
        await enqueue_kuroko_api(
            "/tasks/slack/message", message.model_dump(), task_id=f"slack-dm-{message.event_id}"
        )
    home = extract_home_opened(payload)
    if home:
        await enqueue_kuroko_api(
            "/tasks/slack/home", home.model_dump(), task_id=f"slack-home-{home.event_id}"
        )
    return {"status": "ok"}


@router.post("/interactivity")
async def interactivity(request: Request) -> dict[str, str]:
    body = await request.body()
    _verify(request, body)
    try:
        payload = parse_form_payload(body)
    except InvalidInteraction:
        raise HTTPException(status_code=400, detail="invalid payload") from None

    interaction = extract_interaction(payload)
    if interaction is None:
        return {"status": "ignored"}  # KUROKO のボタンではない
    tasks = plan_tasks(interaction)
    if not tasks:
        # 押した人が、DM の宛先の本人ではない・値が不正。何も起こさない（ログだけ残す）
        logger.warning("interaction rejected: action=%s", interaction.action.value)
        return {"status": "rejected"}
    for task in tasks:
        enqueue = enqueue_payment_api if task.target == "payment-api" else enqueue_kuroko_api
        await enqueue(task.path, task.payload, task.task_id)
    return {"status": "ok"}
