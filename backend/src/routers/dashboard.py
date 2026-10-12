"""Web ダッシュボードの API（`/api/dashboard/*`。SPEC 4.3・7.5・7.6、ARCHITECTURE 4.5。TASKS B14）。

呼び出し元は kuroko-dashboard（Cloud Run の ID トークン）で、利用者は Firebase の ID トークン
（`X-Firebase-Token`）で確かめる。**委任・承認・取り消し・振込の操作は、原則ここに無い**
（Slack だけ）。
例外は、体験用（sandbox）のイベントの、登場人物のカード（SPEC 7.7）。
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.models.dashboard import Actor, UploadKind
from src.services.container import get_dashboard
from src.services.dashboard import DashboardError, DashboardService
from src.services.dashboard_auth import current_actor
from src.services.task_auth import require_dashboard

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_dashboard)]
)
Who = Annotated[Actor, Depends(current_actor)]


def svc() -> DashboardService:
    return get_dashboard()


Svc = Annotated[DashboardService, Depends(svc)]


def _raise(e: DashboardError) -> HTTPException:
    return HTTPException(e.status, e.code)


class MessageIn(BaseModel):
    event_id: str | None = None  # 最初の発言は無し（イベントが作られる）
    text: str = Field(max_length=2000)
    # イベントを作るときだけ使う。live（実演用）は、登録したアカウントだけ（SPEC 7.7）
    mode: Literal["experience", "live"] = "experience"


class PlanIn(BaseModel):
    plan: dict[str, Any]


class UploadIn(BaseModel):
    kind: UploadKind
    content_type: str
    size_bytes: int
    source: Literal["upload", "paste"] = "upload"


class ConfirmIn(BaseModel):
    kind: UploadKind
    values: dict[str, Any]
    source: Literal["extracted", "manual"]


class CardActionIn(BaseModel):
    index: int = Field(ge=0, le=10)  # カードの何番目のボタンか（値はサーバー側のカードから取る）


class BankApprovalIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class RetroIn(BaseModel):
    # 画面から受けるのは、選択だけ（事実の文面は受けない。コードが作り直す。Policy Gate 6.4）
    reuse_intent: Literal["yes", "no", "unanswered"] = "unanswered"
    include: list[Literal["venue_record", "venue_evaluation"]] = Field(default=[], max_length=2)
    decision: Literal["save", "skip"]


class ResetIn(BaseModel):
    mode: Literal["experience", "live"]


class VenueIn(BaseModel):
    place_id: str
    name: str


@router.get("/me")
def me(actor: Who, s: Svc) -> dict[str, Any]:
    """利用者の役割（幹事／ゲスト）。画面の出し分けに使う（権限の強制は各操作の側）。"""
    return s.me(actor)


@router.get("/events")
def list_events(
    actor: Who, s: Svc, mode: Literal["experience", "live"] | None = None
) -> list[dict[str, Any]]:
    return s.list_events(actor, mode)


@router.get("/events/{event_id}")
def get_event(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.get_event(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/messages")
async def send_message(body: MessageIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.send_message(actor, body.event_id, body.text, body.mode)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/reset")
def reset_scenario(body: ResetIn, actor: Who, s: Svc) -> dict[str, int]:
    """この画面で自分が作ったイベントと通知を削除し、シナリオを最初から始める（SPEC 7.7）。"""
    try:
        return s.reset_scenario(actor, body.mode)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/confirm-plan")
async def confirm_plan(event_id: str, body: PlanIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.confirm_event_plan(actor, event_id, body.plan)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/uploads")
def issue_upload(event_id: str, body: UploadIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.issue_upload_url(
            actor, event_id, body.kind, body.content_type, body.size_bytes, body.source
        )
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/uploads/{upload_id}/register")
async def register_upload(event_id: str, upload_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.register_upload(actor, event_id, upload_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/confirm-extraction")
async def confirm_extraction(event_id: str, body: ConfirmIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.confirm_extraction(actor, event_id, body.kind, body.values, body.source)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/confirm-budget-overrun")
async def confirm_budget_overrun(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.confirm_budget_overrun(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/mark-held")
def mark_held(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.mark_event_held(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/venue-candidates")
async def find_venues(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    """店の候補を出す（順位はコードが決める。幹事が画面で選ぶ）。"""
    try:
        return await s.find_venues(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/select-venue")
def select_venue(event_id: str, body: VenueIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.select_venue(actor, event_id, body.place_id, body.name)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/persona-cards/{card_id}/actions")
async def press_persona_card(
    event_id: str, card_id: str, body: CardActionIn, actor: Who, s: Svc
) -> dict[str, Any]:
    """登場人物として、カードのボタンを押す（体験用のイベントを作った本人だけ。SPEC 7.7）。"""
    try:
        return await s.press_persona_card(actor, event_id, card_id, body.index)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/bank-approvals")
async def approve_bank(event_id: str, body: BankApprovalIn, actor: Who, s: Svc) -> dict[str, Any]:
    """体験用の「銀行で承認する」（本物の銀行の振込には効かない。SPEC 7.7）。"""
    try:
        return await s.approve_bank_transfer(actor, event_id, body.user_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/close-retro")
def close_retro(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    """振り返りの回答を、待たずに締め切る（その時点の回答で集計する。SPEC 7.4）。"""
    try:
        return s.close_retro(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/confirm-retro")
async def confirm_retro(event_id: str, body: RetroIn, actor: Who, s: Svc) -> dict[str, Any]:
    """振り返りのまとめの確認。「覚えさせる」なら、定型の事実を記憶に保存する（SPEC 9.8）。"""
    try:
        return await s.confirm_retro(
            actor, event_id, body.reuse_intent, list(body.include), body.decision
        )
    except DashboardError as e:
        raise _raise(e) from None


@router.get("/notifications")
def list_notifications(actor: Who, s: Svc) -> list[dict[str, Any]]:
    return s.list_notifications(actor)


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, actor: Who, s: Svc) -> dict[str, str]:
    try:
        s.mark_read(actor, notification_id)
    except DashboardError as e:
        raise _raise(e) from None
    return {"status": "ok"}
