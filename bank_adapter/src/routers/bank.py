"""bank-adapter の入口（ARCHITECTURE 4.4）。

すべて仮名の user_id で受け、口座番号を引数にも応答にも出さない。

- POST /authorizations・POST /transfers・GET /transfers/{id}: sa-payment-api だけ
- POST /transfers/{id}/demo-approval: sa-api だけ（体験用の「承認待ち」の代行の振込だけ。SPEC 7.7）
- GET /statements・POST /redactions: sa-api（幹事の入金だけ）と sa-payment-api
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.models.schemas import (
    AuthorizationRequest,
    AuthorizationResponse,
    CreateTransferRequest,
    RedactionResponse,
    StatementResponse,
    TransferResponse,
)
from src.services.caller_auth import (
    Caller,
    require_api,
    require_api_or_payment,
    require_payment,
)
from src.services.container import get_service
from src.services.transfers import (
    BankFailure,
    BankService,
    IdempotencyConflict,
    InProgress,
    InvalidTransfer,
    UnknownTransfer,
    UnknownUser,
)

router = APIRouter()

PaymentCaller = Annotated[Caller, Depends(require_payment)]
AnyCaller = Annotated[Caller, Depends(require_api_or_payment)]
ApiCaller = Annotated[Caller, Depends(require_api)]
Service = Annotated[BankService, Depends(get_service)]


@router.post("/authorizations", response_model=AuthorizationResponse)
def authorize(
    body: AuthorizationRequest,
    _: PaymentCaller,
    service: Service,
) -> AuthorizationResponse:
    """銀行の利用の認可。

    sunabar には OAuth の流れが無く、口座ごとのトークンを事前に登録しているので、
    「この user_id の口座が使えるか」を確かめて返す（本番の銀行APIでは OAuth の交換になる）。
    """
    if not service.authorize(body.user_id):
        raise HTTPException(status_code=404, detail="unknown_user")
    return AuthorizationResponse(user_id=body.user_id, authorized=True)


@router.post("/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(
    body: CreateTransferRequest,
    _: PaymentCaller,
    service: Service,
) -> TransferResponse:
    try:
        return service.create_transfer(**body.model_dump())
    except UnknownUser:
        raise HTTPException(status_code=404, detail="unknown_user") from None
    except InvalidTransfer:
        raise HTTPException(status_code=422, detail="invalid_transfer") from None
    except IdempotencyConflict:
        raise HTTPException(status_code=409, detail="idempotency_key_reuse") from None
    except InProgress:
        raise HTTPException(status_code=409, detail="in_progress") from None
    except BankFailure as e:
        raise HTTPException(status_code=502, detail=e.code) from None


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: str,
    _: PaymentCaller,
    service: Service,
) -> TransferResponse:
    try:
        return service.get_transfer(transfer_id)
    except UnknownTransfer:
        raise HTTPException(status_code=404, detail="unknown_transfer") from None


@router.post("/transfers/{transfer_id}/demo-approval", response_model=TransferResponse)
def demo_approve(transfer_id: str, _: ApiCaller, service: Service) -> TransferResponse:
    """体験用の「銀行で承認する」（SPEC 7.7）。承認待ちの代行の振込だけ。本物の振込には効かない。"""
    try:
        return service.demo_approve(transfer_id)
    except UnknownTransfer:
        raise HTTPException(status_code=404, detail="unknown_transfer") from None
    except InvalidTransfer:
        raise HTTPException(status_code=409, detail="not_a_held_transfer") from None


@router.get("/statements", response_model=StatementResponse)
def statements(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    date_from: date,
    date_to: date,
    caller: AnyCaller,
    service: Service,
) -> StatementResponse:
    if date_to < date_from or (date_to - date_from).days > 31:
        raise HTTPException(status_code=422, detail="invalid_range")
    try:
        return service.statements(
            user_id=user_id, date_from=date_from, date_to=date_to, caller=caller
        )
    except UnknownUser:
        raise HTTPException(status_code=404, detail="unknown_user") from None


@router.post("/redactions", response_model=RedactionResponse)
def redact(
    body: AuthorizationRequest,
    _: AnyCaller,
    service: Service,
) -> RedactionResponse:
    return RedactionResponse(user_id=body.user_id, redacted=service.redact(body.user_id))
