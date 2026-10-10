"""Web ダッシュボードの API（`/api/dashboard/*`。SPEC 4.3・7.5・7.6、ARCHITECTURE 4.5。TASKS B14）。

呼び出し元は kuroko-dashboard（Cloud Run の ID トークン）で、利用者は Firebase の ID トークン
（`X-Firebase-Token`）で確かめる。**委任・承認・取り消し・振込の操作はここに無い**（Slack だけ）。
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


class VenueIn(BaseModel):
    place_id: str
    name: str


@router.get("/me")
def me(actor: Who) -> dict[str, str]:
    """利用者の役割（幹事／ゲスト）。画面の出し分けに使う（権限の強制は各操作の側）。"""
    return {"role": actor.role.value}


@router.get("/events")
def list_events(actor: Who, s: Svc) -> list[dict[str, Any]]:
    return s.list_events(actor)


@router.get("/events/{event_id}")
def get_event(event_id: str, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.get_event(actor, event_id)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/messages")
async def send_message(body: MessageIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return await s.send_message(actor, body.event_id, body.text)
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
def confirm_extraction(event_id: str, body: ConfirmIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.confirm_extraction(actor, event_id, body.kind, body.values, body.source)
    except DashboardError as e:
        raise _raise(e) from None


@router.post("/events/{event_id}/select-venue")
def select_venue(event_id: str, body: VenueIn, actor: Who, s: Svc) -> dict[str, Any]:
    try:
        return s.select_venue(actor, event_id, body.place_id, body.name)
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
