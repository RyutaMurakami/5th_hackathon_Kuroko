"""支払いの開始・参照（`sa-api` だけ）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.models.schemas import PaymentResponse, StartPaymentRequest
from src.services.caller_auth import Caller, require_api, require_poller
from src.services.container import Services, get_services
from src.services.payments import BankFailure, PaymentConflict, UnknownPayment

router = APIRouter()

ApiCaller = Annotated[Caller, Depends(require_api)]
Svc = Annotated[Services, Depends(get_services)]


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def start_payment(body: StartPaymentRequest, _: ApiCaller, svc: Svc) -> PaymentResponse:
    """Policy Gate 6.3 を通った依頼だけ、銀行アダプタへ振込を依頼する。止めた場合も 201 で、
    `status=blocked` と `block_reason` を返す（依頼は作られない）。"""
    try:
        return svc.payments.start(body)
    except PaymentConflict:
        raise HTTPException(status_code=409, detail="payment_id_reuse") from None
    except BankFailure as e:
        raise HTTPException(status_code=502, detail=e.code) from None


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str, _: ApiCaller, svc: Svc) -> PaymentResponse:
    try:
        return svc.payments.get(payment_id)
    except UnknownPayment:
        raise HTTPException(status_code=404, detail="unknown_payment") from None


@router.post("/tasks/internal/payments/poll")
def poll_payments(_: Annotated[Caller, Depends(require_poller)], svc: Svc) -> dict[str, int]:
    """承認待ちの支払いを確認する（sunabar に Webhook が無いため、1分ごとのポーリング）。
    結果は、状態ごとの件数だけを返す（個人・金額は載せない）。"""
    return svc.payments.poll_all()
