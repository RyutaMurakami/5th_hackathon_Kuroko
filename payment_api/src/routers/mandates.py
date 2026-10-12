"""委任状の署名・取り消し（`sa-gateway`。署名検証済みの Slack 操作）。ARCHITECTURE 4.3。

署名だけは、デモ用の代行（`sa-demo-runner`）も受け付ける。ただし `sandbox` のイベントで、
Slack のアカウントを持たない参加者のときだけ（SPEC 7.6）。取り消しは代行しない。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.models.schemas import MandateResponse, SignMandateRequest
from src.services.caller_auth import Caller, require_gateway, require_signer
from src.services.container import Services, get_services
from src.services.mandates import (
    DEMO_RUNNER,
    InvalidMandate,
    MandateConflict,
    PaymentAlreadyStarted,
    UnknownMandate,
)

router = APIRouter()

GatewayCaller = Annotated[Caller, Depends(require_gateway)]
SignerCaller = Annotated[Caller, Depends(require_signer)]
Svc = Annotated[Services, Depends(get_services)]


@router.post("/mandates", response_model=MandateResponse, status_code=201)
def sign_mandate(body: SignMandateRequest, caller: SignerCaller, svc: Svc) -> MandateResponse:
    # 代行の印（signed_via）は、代行の身元だけが使える。代行できる相手は記録で確かめる
    if (caller == "demo") != (body.signed_via == DEMO_RUNNER):
        raise HTTPException(status_code=403, detail="forbidden")
    if caller == "demo" and not svc.mandates.demo_proxy_allowed(body.event_id, body.user_id):
        raise HTTPException(status_code=403, detail="demo_proxy_not_allowed")
    try:
        return svc.mandates.sign(body)
    except InvalidMandate:
        raise HTTPException(status_code=422, detail="invalid_mandate") from None
    except MandateConflict:
        raise HTTPException(status_code=409, detail="mandate_exists") from None


@router.post("/mandates/{mandate_id}/revoke", response_model=MandateResponse)
def revoke_mandate(mandate_id: str, _: GatewayCaller, svc: Svc) -> MandateResponse:
    try:
        return svc.mandates.revoke(mandate_id)
    except UnknownMandate:
        raise HTTPException(status_code=404, detail="unknown_mandate") from None
    except PaymentAlreadyStarted:
        raise HTTPException(status_code=409, detail="payment_started") from None
