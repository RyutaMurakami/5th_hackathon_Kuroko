"""支払いの開始・承認待ちの確認・入金の確認・期限切れの作り直し（SPEC 8.5〜8.7）。

- 開始: Policy Gate 6.3 → Closed Payment Mandate → 銀行アダプタへの振込依頼。Gate を通らなければ
  依頼を作らず `blocked` にする（銀行アダプタを呼ばない）
- 確認（ポーリング。sunabar に Webhook が無いため）: 銀行が手続済にしたら、**本人の出金明細で振込を
  確認できたときだけ**完了にし、確認結果に支払いエージェントの鍵で署名する（領収書）。結果コード
  だけでは完了にしない
- 期限切れ（承認なしで10分）: 前の依頼が未完了と確かめて、新しい nonce・冪等キーで
  作り直す（最大2回）
"""

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from jwcrypto.jws import JWS

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
from src.services.notifier import Notifier, NullNotifier
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


MAX_RETRIES = 2  # 承認の期限切れで依頼を作り直す回数の上限（SPEC 8.7）
JST = ZoneInfo("Asia/Tokyo")


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
        notifier: Notifier | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._gate = gate
        self._agent = agent_signer
        self._participant = participant_signer
        self._bank = bank
        self._notifier = notifier or NullNotifier()
        self._ttl = timedelta(seconds=closed_mandate_ttl_seconds)
        self._now = now
        self._client = MandateClient()

    # ------------------------------------------------------------------ 開始
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
            "checkout_jwt": req.checkout_jwt,
            "checkout_hash": req.checkout_hash,
            "fingerprint": fingerprint,
            "status": PaymentStatus.PENDING.value,
            "block_reason": None,
            "transfer_id": None,
            "approval_deadline": None,
            "retry_count": 0,
            "closed_payment_mandate": None,
            "settlement_verified": False,
            "receipt": None,
            "created_at": now,
            "completed_at": None,
        }
        existing, created = self._store.create_payment_if_absent(req.payment_id, record)
        if not created:
            if existing["fingerprint"] != fingerprint:
                raise PaymentConflict
            return self._response(existing)  # 同じ依頼の再送は、結果をそのまま返す

        outcome = self._issue(req, record, attempt=0, now=now)
        if outcome == "failed":
            raise BankFailure("bank_adapter_failure")
        return self._response(self._store.get_payment(req.payment_id))

    def _issue(self, req: StartPaymentRequest, record: dict, *, attempt: int, now: datetime) -> str:
        """Gate 6.3 → Closed Mandate → 振込依頼。結果: issued / blocked / failed。"""
        pid = req.payment_id
        result = self._gate.check(req, now=now, attempt=attempt)
        if not result.ok:
            logger.info("policy_gate blocked payment=%s reason=%s", pid, result.reason.value)
            self._store.update_payment(
                pid, {"status": PaymentStatus.BLOCKED.value, "block_reason": result.reason.value}
            )
            return "blocked"
        closed_token = self._create_closed_mandate(req, result.open_token, now, attempt)
        if closed_token is None:
            self._store.update_payment(
                pid,
                {
                    "status": PaymentStatus.BLOCKED.value,
                    "block_reason": BlockReason.BAD_SIGNATURE.value,
                },
            )
            return "blocked"
        try:
            transfer = self._bank.create_transfer(
                payer_user_id=req.payer_user_id,
                payee_user_id=req.payee_user_id,
                amount_yen=req.amount_yen,
                idempotency_key=f"{pid}:{attempt}",
                # 体験用のイベントでは、銀行での承認を Web のカードで行う（SPEC 7.7）
                demo_hold=self._store.web_bank_approval(req.event_id),
            )
        except BankAdapterError:
            self._store.update_payment(
                pid, {"status": PaymentStatus.FAILED.value, "closed_payment_mandate": closed_token}
            )
            return "failed"
        updated = self._store.update_payment(
            pid,
            {
                "status": PaymentStatus.AWAITING_BANK_APPROVAL.value,
                "closed_payment_mandate": closed_token,
                "transfer_id": transfer.transfer_id,
                "approval_deadline": transfer.approval_expires_at,
                "retry_count": attempt,
                "simulated": transfer.simulated,
            },
        )
        if not transfer.simulated:  # 代行ぶんは、本人が銀行で承認することが無い（SPEC 8.10）
            self._notify(lambda: self._notifier.transfer_requested(updated, reissued=attempt > 0))
        return "issued"

    # ------------------------------------------------------------------ 確認（ポーリング）
    def poll_all(self) -> dict[str, int]:
        """承認待ちの支払いをすべて確認する（Cloud Scheduler が1分ごとに呼ぶ）。"""
        counts: dict[str, int] = {}
        for rec in self._store.list_payments_by_status(PaymentStatus.AWAITING_BANK_APPROVAL.value):
            try:
                result = self.poll_one(rec["payment_id"])
            except Exception:  # noqa: BLE001  1件の失敗で、ほかの支払いの確認を止めない
                logger.exception("poll failed: payment=%s", rec["payment_id"])
                result = "error"
            counts[result] = counts.get(result, 0) + 1
        return counts

    def poll_one(self, payment_id: str) -> str:
        rec = self._store.get_payment(payment_id)
        if rec is None:
            raise UnknownPayment
        if rec["status"] != PaymentStatus.AWAITING_BANK_APPROVAL.value:
            return "skipped"
        try:
            transfer = self._bank.get_transfer(rec["transfer_id"])
        except BankAdapterError:
            return "bank_unreachable"  # 照会の失敗では状態を変えない（次のポーリングで再確認）
        if transfer.status == "processed":
            return self._settle(rec)
        if transfer.status == "expired":
            return self._reissue(rec)
        if transfer.status == "failed":
            return self._fail(rec)
        return "waiting"

    def _settle(self, rec: dict) -> str:
        """銀行が手続済にした。**本人の出金明細で振込を確認できたときだけ**完了にする。"""
        today = self._now().astimezone(JST).date()
        start = rec["created_at"].astimezone(JST).date()
        try:
            entries = self._bank.outgoing(rec["payer_user_id"], start, today)
        except BankAdapterError:
            return "bank_unreachable"
        match = next(
            (
                e
                for e in entries
                if e.amount_yen == rec["amount_yen"]
                and e.counterparty_user_id == rec["payee_user_id"]
                and self._store.claim_settlement(e.item_key, rec["payment_id"])
            ),
            None,
        )
        if match is None:
            # 手続済だが、出金明細で確認できない（金額違い・反映待ち）。完了にしない
            return "unverified"
        now = self._now()
        updated = self._store.update_payment(
            rec["payment_id"],
            {
                "status": PaymentStatus.COMPLETED.value,
                "settlement_verified": True,
                "receipt": self._sign_receipt(rec, match.item_key, now),
                "completed_at": now,
            },
        )
        self._store.update_mandate_if_exists(rec["event_id"], rec["payer_user_id"], "used")
        self._notify(lambda: self._notifier.completed(updated))
        return "completed"

    def _reissue(self, rec: dict) -> str:
        """承認の期限切れ。前の依頼が未完了と確かめたうえで、新しい nonce・冪等キーで作り直す。"""
        pid = rec["payment_id"]
        attempt = rec["retry_count"] + 1
        if attempt > MAX_RETRIES:
            return self._fail(rec)
        req = StartPaymentRequest(
            payment_id=pid,
            event_id=rec["event_id"],
            payer_user_id=rec["payer_user_id"],
            payee_user_id=rec["payee_user_id"],
            amount_yen=rec["amount_yen"],
            checkout_jwt=rec["checkout_jwt"],
            checkout_hash=rec["checkout_hash"],
        )
        outcome = self._issue(req, rec, attempt=attempt, now=self._now())
        if outcome == "failed":
            self._notify(lambda: self._notifier.failed(self._store.get_payment(pid)))
        return {"issued": "reissued", "blocked": "blocked", "failed": "failed"}[outcome]

    def _fail(self, rec: dict) -> str:
        updated = self._store.update_payment(
            rec["payment_id"], {"status": PaymentStatus.FAILED.value}
        )
        self._notify(lambda: self._notifier.failed(updated))
        return "failed"

    def _notify(self, send: Callable[[], None]) -> None:
        try:
            send()
        except Exception:  # noqa: BLE001  通知の失敗で、支払いの状態は変えない
            logger.exception("notification failed")

    def _sign_receipt(self, rec: dict, item_key: str, now: datetime) -> str:
        """出金明細で確認した結果に、支払いエージェントの鍵で署名する（AP2 の Receipt に相当）。"""
        payload = {
            "iss": "payment-api",
            "payment_id": rec["payment_id"],
            "event_id": rec["event_id"],
            "payer": rec["payer_user_id"],
            "payee": rec["payee_user_id"],
            "amount_yen": rec["amount_yen"],
            "currency": CURRENCY,
            "statement_item": item_key,
            "verified_at": int(now.timestamp()),
        }
        header = {"alg": "ES256", "typ": "JWT", "kid": AGENT_KID}
        jws = JWS(json.dumps(payload, separators=(",", ":")).encode())
        jws.add_signature(
            self._agent.signing_key(AGENT_KID), alg="ES256", protected=json.dumps(header)
        )
        return jws.serialize(compact=True)

    # ------------------------------------------------------------------ 参照・Closed Mandate
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
