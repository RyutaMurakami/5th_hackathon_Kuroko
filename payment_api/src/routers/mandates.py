"""委任状の署名・取り消し（`sa-gateway` だけ。署名検証済みの Slack 操作）。ARCHITECTURE 4.3。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.models.schemas import MandateResponse, SignMandateRequest
from src.services.caller_auth import Caller, require_gateway
from src.services.container import Services, get_services
from src.services.mandates import (
    InvalidMandate,
    MandateConflict,
    PaymentAlreadyStarted,
    UnknownMandate,
)

router = APIRouter()

GatewayCaller = Annotated[Caller, Depends(require_gateway)]
Svc = Annotated[Services, Depends(get_services)]


@router.post("/mandates", response_model=MandateResponse, status_code=201)
def sign_mandate(body: SignMandateRequest, _: GatewayCaller, svc: Svc) -> MandateResponse:
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
