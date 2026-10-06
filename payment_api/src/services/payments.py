"""支払いの開始: Policy Gate 6.3 → Closed Payment Mandate → 銀行アダプタへの振込依頼（SPEC 8.5）。

Gate を通らなければ依頼を作らず `blocked` にする（銀行アダプタを呼ばない）。
承認待ちのポーリング・期限切れの作り直し・入金の確認（`verify_settlement`）は B10・B12。
"""

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient

from src.clients.bank_adapter import BankAdapter, BankAdapterError
from src.clients.signers import MandateSigner
from src.db.store import Store
from src.models.schemas import (
    BlockReason,
    PaymentResponse,
    PaymentStatus,
    StartPaymentRequest,
)
from src.services.mandates import AGENT_KID, CURRENCY, INSTRUMENT_TYPE
from src.services.policy_gate import PolicyGate, nonce_for

logger = logging.getLogger(__name__)

AUDIENCE = "payment-api"


class PaymentConflict(Exception):
    """同じ payment_id が、別の内容の依頼に使われた。"""


class UnknownPayment(Exception):
    pass


class BankFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PaymentService:
    def __init__(
        self,
        *,
        store: Store,
        gate: PolicyGate,
        agent_signer: MandateSigner,
        participant_signer: MandateSigner,
        bank: BankAdapter,
        closed_mandate_ttl_seconds: int,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._gate = gate
        self._agent = agent_signer
        self._participant = participant_signer
        self._bank = bank
        self._ttl = timedelta(seconds=closed_mandate_ttl_seconds)
        self._now = now
        self._client = MandateClient()

    def start(self, req: StartPaymentRequest) -> PaymentResponse:
        now = self._now()
        fingerprint = hashlib.sha256(
            f"{req.event_id}|{req.payer_user_id}|{req.payee_user_id}|{req.amount_yen}|"
            f"{req.checkout_hash}".encode()
        ).hexdigest()
        record = {
            "payment_id": req.payment_id,
            "event_id": req.event_id,
            "payer_user_id": req.payer_user_id,
            "payee_user_id": req.payee_user_id,
            "amount_yen": req.amount_yen,
            "checkout_hash": req.checkout_hash,
            "fingerprint": fingerprint,
            "status": PaymentStatus.PENDING.value,
            "block_reason": None,
            "transfer_id": None,
            "approval_deadline": None,
            "retry_count": 0,
            "closed_payment_mandate": None,
            "created_at": now,
        }
        existing, created = self._store.create_payment_if_absent(req.payment_id, record)
        if not created:
            if existing["fingerprint"] != fingerprint:
                raise PaymentConflict
            return self._response(existing)  # 同じ依頼の再送は、結果をそのまま返す

        attempt = 0
        result = self._gate.check(req, now=now, attempt=attempt)
        if not result.ok:
            logger.info(
                "policy_gate blocked payment=%s reason=%s", req.payment_id, result.reason.value
            )
            return self._response(
                self._store.update_payment(
                    req.payment_id,
                    {"status": PaymentStatus.BLOCKED.value, "block_reason": result.reason.value},
                )
            )

        closed_token = self._create_closed_mandate(req, result.open_token, now, attempt)
        if closed_token is None:
            return self._response(
                self._store.update_payment(
                    req.payment_id,
                    {
                        "status": PaymentStatus.BLOCKED.value,
                        "block_reason": BlockReason.BAD_SIGNATURE.value,
                    },
                )
            )
        try:
            transfer = self._bank.create_transfer(
                payer_user_id=req.payer_user_id,
                payee_user_id=req.payee_user_id,
                amount_yen=req.amount_yen,
                idempotency_key=f"{req.payment_id}:{attempt}",
            )
        except BankAdapterError as e:
            self._store.update_payment(
                req.payment_id,
                {"status": PaymentStatus.FAILED.value, "closed_payment_mandate": closed_token},
            )
            raise BankFailure(e.code) from None
        return self._response(
            self._store.update_payment(
                req.payment_id,
                {
                    "status": PaymentStatus.AWAITING_BANK_APPROVAL.value,
                    "closed_payment_mandate": closed_token,
                    "transfer_id": transfer.transfer_id,
                    "approval_deadline": transfer.approval_expires_at,
                },
            )
        )

    def get(self, payment_id: str) -> PaymentResponse:
        record = self._store.get_payment(payment_id)
        if record is None:
            raise UnknownPayment
        return self._response(record)

    def _create_closed_mandate(
        self, req: StartPaymentRequest, open_token: str, now: datetime, attempt: int
    ) -> str | None:
        """支払いエージェントの鍵で Closed Payment Mandate に絞り、チェーンを検証する。"""
        nonce = nonce_for(f"{req.event_id}:{req.payer_user_id}", req.checkout_hash, attempt)
        closed = PaymentMandate(
            transaction_id=req.checkout_hash,
            payee=Merchant(id=req.payee_user_id, name=req.payee_user_id),
            payment_amount=Amount(amount=req.amount_yen, currency=CURRENCY),
            payment_instrument=PaymentInstrument(id=req.payer_user_id, type=INSTRUMENT_TYPE),
            iat=int(now.timestamp()),
            exp=int((now + self._ttl).timestamp()),
        )
        chain = self._client.present(
            holder_key=self._agent.signing_key(AGENT_KID),
            mandate_token=open_token,
            payloads=[closed],
            nonce=nonce,
            aud=AUDIENCE,
        )
        try:
            self._client.verify(
                token=chain,
                key_or_provider=lambda _token: self._participant.public_key(),
                expected_aud=AUDIENCE,
                expected_nonce=nonce,
                current_time=int(now.timestamp()),
            )
        except Exception:  # noqa: BLE001
            return None
        return chain

    @staticmethod
    def _response(record: dict) -> PaymentResponse:
        return PaymentResponse(
            payment_id=record["payment_id"],
            event_id=record["event_id"],
            payer_user_id=record["payer_user_id"],
            payee_user_id=record["payee_user_id"],
            amount_yen=record["amount_yen"],
            status=PaymentStatus(record["status"]),
            block_reason=(
                BlockReason(record["block_reason"]) if record.get("block_reason") else None
            ),
            transfer_id=record.get("transfer_id"),
            approval_deadline=record.get("approval_deadline"),
            retry_count=record.get("retry_count", 0),
            created_at=record["created_at"],
        )
