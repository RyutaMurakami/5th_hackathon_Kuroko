import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.models.schemas import SlackDirectMessage
from src.models.slack import SlackHomeOpened, SlackInteraction
from src.services.billing import UnknownEvent
from src.services.container import get_billing, get_dashboard, get_retro, get_slack_actions
from src.services.slack_conversation import handle_direct_message
from src.services.task_auth import require_gateway, require_scheduler, require_self

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks")


@router.post("/slack/message", dependencies=[Depends(require_gateway)])
async def slack_message(message: SlackDirectMessage) -> dict[str, str]:
    await handle_direct_message(message)
    return {"status": "ok"}


@router.post("/slack/interaction", dependencies=[Depends(require_gateway)])
async def slack_interaction(interaction: SlackInteraction) -> dict[str, str]:
    """署名検証済みのボタン操作（出欠・委任・承認・予算超過の確認）。sa-gateway だけ。"""
    # Web のカード用の欄（だれとして押したか）は、kuroko-api の中でだけ設定する（SPEC 7.7）
    interaction = interaction.model_copy(update={"acting_for": None, "web_uid": None})
    await get_slack_actions().handle(interaction)
    return {"status": "ok"}


@router.post("/slack/home", dependencies=[Depends(require_gateway)])
async def slack_home(opened: SlackHomeOpened) -> dict[str, str]:
    await get_slack_actions().refresh_home(opened)
    return {"status": "ok"}


class EventRef(BaseModel):
    event_id: str


@router.post("/internal/checkouts", dependencies=[Depends(require_self)])
async def create_checkouts(ref: EventRef) -> dict:
    """按分の承認後、Policy Gate 6.2 を通った請求を `payment-api` に渡す（自分自身が投入）。"""
    try:
        run = await get_billing().create_checkouts(ref.event_id)
    except UnknownEvent:
        raise HTTPException(status_code=404, detail="unknown_event") from None
    # 体験用のイベントでは、登場人物に「銀行で承認してください」を届ける（SPEC 7.7）。
    # 届けられなくても、請求は成立している（Web の画面は、支払いの状態からカードを出す）
    try:
        await get_slack_actions().send_bank_requests(ref.event_id, run.outcomes)
    except Exception:
        logger.exception("could not deliver the bank requests: event=%s", ref.event_id)
    return {
        "ok": run.ok,
        "failures": [f.value for f in run.failures],
        "outcomes": run.outcomes,
        "errors": run.errors,
    }


@router.post("/internal/collections", dependencies=[Depends(require_self)])
async def confirm_collections(ref: EventRef) -> dict:
    """幹事口座の入金明細で、回収状況を更新する。"""
    try:
        run = await get_billing().confirm_incoming_payments(ref.event_id)
    except UnknownEvent:
        raise HTTPException(status_code=404, detail="unknown_event") from None
    return {
        "received": run.received,
        "missing": run.missing,
        "amount_mismatch": run.amount_mismatch,
        "all_received": run.all_received,
    }


@router.post("/internal/rsvp-requests", dependencies=[Depends(require_self)])
async def rsvp_requests(ref: EventRef) -> dict:
    """出欠＋委任の依頼を、参加者の DM に送る。"""
    return await get_slack_actions().send_consent_requests(ref.event_id)


@router.post("/internal/approval-requests", dependencies=[Depends(require_self)])
async def approval_requests(ref: EventRef) -> dict:
    """Policy Gate 6.1 を通ったら按分を計算し、承認者に承認依頼を送る。"""
    return await get_slack_actions().request_split_approval(ref.event_id)


@router.post("/internal/budget-requests", dependencies=[Depends(require_self)])
async def budget_requests(ref: EventRef) -> dict:
    """幹事が続行を確認した予算超過について、承認者に最終確認を求める。"""
    return await get_slack_actions().request_budget_confirmation(ref.event_id)


@router.post("/internal/feedback-requests", dependencies=[Depends(require_self)])
async def feedback_requests(ref: EventRef) -> dict:
    """振り返りの依頼を、出席者に送る（完了の直後に、kuroko-api が自分に投入する。SPEC 7.4）。"""
    return await get_retro().collect_feedback(ref.event_id)


@router.post("/scheduled/sandbox-cleanup", dependencies=[Depends(require_scheduler)])
def purge_sandbox() -> dict[str, int]:
    """作成から7日たったゲスト（sandbox）のイベントを削除する（SPEC 7.6）。"""
    return {"deleted": get_dashboard().purge_expired_sandbox()}


@router.post("/scheduled/retrospectives", dependencies=[Depends(require_scheduler)])
async def scheduled_retrospectives() -> dict[str, int]:
    """1日1回: 始まっていない依頼の拾い直し・2日後のリマインド・3日後の締切。件数だけを返す。"""
    return await get_retro().tick()


@router.post("/scheduled/collections", dependencies=[Depends(require_scheduler)])
async def scheduled_collections() -> dict[str, int]:
    """1分ごと: 支払いが完了したイベントの、幹事口座の入金を確認する（SPEC 8.6）。件数だけ。"""
    return await get_billing().poll_collections()
