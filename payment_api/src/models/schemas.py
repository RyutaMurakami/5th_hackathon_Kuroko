"""payment-api の入出力。仮名の user_id だけを扱い、口座番号・トークンは扱わない（SPEC 10章）。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MandateStatus(StrEnum):
    ACTIVE = "active"
    USED = "used"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AWAITING_BANK_APPROVAL = "awaiting_bank_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class BlockReason(StrEnum):
    """Policy Gate 6.3 で止めた理由（Payment.block_reason）。"""

    NO_MANDATE = "no_mandate"
    MANDATE_REVOKED = "mandate_revoked"
    MANDATE_EXPIRED = "mandate_expired"
    MANDATE_INACTIVE = "mandate_inactive"
    BAD_SIGNATURE = "bad_signature"
    EVENT_MISMATCH = "event_mismatch"
    PAYER_MISMATCH = "payer_mismatch"
    PAYEE_NOT_ALLOWED = "payee_not_allowed"
    OVER_CAP = "over_cap"
    INVALID_CHECKOUT = "invalid_checkout"
    NONCE_REUSED = "nonce_reused"
    BANK_NOT_AUTHORIZED = "bank_not_authorized"
    DUPLICATE_PAYMENT = "duplicate_payment"
    INVALID_AMOUNT = "invalid_amount"


class SignMandateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=64)
    payee_user_id: str = Field(min_length=1, max_length=64)  # 幹事
    cap_yen: int = Field(gt=0, le=1_000_000)
    expires_at: datetime
    signed_via: str = Field(min_length=1, max_length=128)  # 署名検証済みの Slack インタラクションID


class MandateResponse(BaseModel):
    mandate_id: str
    event_id: str
    user_id: str
    payee_user_id: str
    cap_yen: int
    status: MandateStatus
    signed_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class StartPaymentRequest(BaseModel):
    payment_id: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=64)
    payer_user_id: str = Field(min_length=1, max_length=64)
    payee_user_id: str = Field(min_length=1, max_length=64)
    amount_yen: int = Field(gt=0, le=10_000_000)
    # KUROKO（請求側）が署名した請求（B13）と、按分表のハッシュ値
    checkout_jwt: str = Field(min_length=1)
    checkout_hash: str = Field(min_length=1, max_length=128)


class PaymentResponse(BaseModel):
    payment_id: str
    event_id: str
    payer_user_id: str
    payee_user_id: str
    amount_yen: int
    status: PaymentStatus
    block_reason: BlockReason | None = None
    transfer_id: str | None = None
    approval_deadline: datetime | None = None
    retry_count: int = 0
    created_at: datetime
