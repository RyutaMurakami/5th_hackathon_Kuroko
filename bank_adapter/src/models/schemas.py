"""bank-adapter の入出力。仮名の user_id だけを受け、口座番号・トークンは出さない（SPEC 10章）。"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class TransferStatus(StrEnum):
    CREATING = "creating"  # 銀行への依頼の途中（結果が未確定。人が確認する）
    AWAITING_APPROVAL = "awaiting_approval"  # 依頼済み。銀行での本人承認を待っている
    # 銀行が手続済にした（payment-api が完了にしてよいのは、入金を明細で確認できたときだけ）
    PROCESSED = "processed"
    EXPIRED = "expired"  # 承認期限を過ぎても手続済にならなかった（作り直す）
    FAILED = "failed"  # 銀行が依頼を受け付けなかった


class AuthorizationRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class AuthorizationResponse(BaseModel):
    user_id: str
    authorized: bool


class CreateTransferRequest(BaseModel):
    payer_user_id: str = Field(min_length=1, max_length=64)
    payee_user_id: str = Field(min_length=1, max_length=64)
    amount_yen: int = Field(gt=0, le=1_000_000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class TransferResponse(BaseModel):
    transfer_id: str
    status: TransferStatus
    amount_yen: int
    apply_no: str | None = None
    created_at: datetime
    approval_expires_at: datetime | None = None


class StatementEntry(BaseModel):
    item_key: str
    date: date
    direction: Literal["in", "out"]
    amount_yen: int
    # 摘要（「振込 」＋ 相手の名義）の名義から解決した、相手の仮名 user_id。一意に決まらなければ
    # None（推測しない）。**摘要・名義・口座番号は、この API の外に出さない**（SPEC 10章）
    counterparty_user_id: str | None = None


class StatementResponse(BaseModel):
    user_id: str
    date_from: date
    date_to: date
    entries: list[StatementEntry]
    has_next: bool = False


class RedactionResponse(BaseModel):
    user_id: str
    redacted: bool
