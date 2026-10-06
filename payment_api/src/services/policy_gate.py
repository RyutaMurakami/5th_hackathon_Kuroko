"""Policy Gate 6.3（振込依頼を出す前の検査。SPEC 6.3・ARCHITECTURE D10）。

決定論的なコードだけで判断する。LLM・エージェントは関与しない。1つでも通らなければ依頼を作らず、
`block_reason` を返す。金額の上限・支払先は、委任状の署名つきの中身を AP2 SDK の
`check_payment_constraints` で検査する（Firestore の写しは信用しない。ARCHITECTURE 4.6）。
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from ap2.sdk.constraints import check_payment_constraints
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient

from src.clients.bank_adapter import BankAdapter
from src.clients.signers import MandateSigner
from src.db.store import Store
from src.models.schemas import BlockReason, MandateStatus, StartPaymentRequest
from src.services.checkout import CheckoutVerifier
from src.services.mandates import (
    CURRENCY,
    INSTRUMENT_TYPE,
    mandate_id_for,
    participant_kid,
    token_kid,
)


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: BlockReason | None = None
    open_token: str | None = None
    mandate_id: str | None = None


def _blocked(reason: BlockReason) -> GateResult:
    return GateResult(ok=False, reason=reason)


def classify_violation(message: str) -> BlockReason:
    """SDK の違反メッセージを、block_reason に分類する。"""
    m = message.lower()
    if "exceeds maximum" in m:
        return BlockReason.OVER_CAP
    if "below minimum" in m or "currency" in m:
        return BlockReason.INVALID_AMOUNT
    if "payee" in m:
        return BlockReason.PAYEE_NOT_ALLOWED
    if "instrument" in m:
        return BlockReason.PAYER_MISMATCH
    return BlockReason.INVALID_CHECKOUT


class PolicyGate:
    def __init__(
        self,
        *,
        store: Store,
        participant_signer: MandateSigner,
        bank: BankAdapter,
        checkout_verifier: CheckoutVerifier,
        mandate_lookup,  # MandateService.current（期限切れの更新つきで読む）
    ) -> None:
        self._store = store
        self._participant = participant_signer
        self._bank = bank
        self._checkout = checkout_verifier
        self._mandate = mandate_lookup
        self._client = MandateClient()

    def check(self, req: StartPaymentRequest, *, now: datetime, attempt: int) -> GateResult:
        # 1. 委任状があり、有効（active・期限内・取り消されていない）
        mandate_id = mandate_id_for(req.event_id, req.payer_user_id)
        record = self._mandate(mandate_id)
        if record is None:
            return _blocked(BlockReason.NO_MANDATE)
        status = record["status"]
        if status == MandateStatus.REVOKED.value:
            return _blocked(BlockReason.MANDATE_REVOKED)
        if status == MandateStatus.EXPIRED.value:
            return _blocked(BlockReason.MANDATE_EXPIRED)
        if status != MandateStatus.ACTIVE.value:
            return _blocked(BlockReason.MANDATE_INACTIVE)

        # 2. 署名が参加者本人（の鍵・kid）で検証できる。中身は署名つきの委任状から読む
        token = record["open_payment_mandate"]
        if token_kid(token) != participant_kid(req.payer_user_id):
            return _blocked(BlockReason.BAD_SIGNATURE)
        try:
            verified = self._client.verify(
                token=token,
                key_or_provider=self._participant.public_key(),
                payload_type=OpenPaymentMandate,
                current_time=int(now.timestamp()),  # SDK の期限・iat の検査に、注入した時計を使う
            )
            open_mandate = OpenPaymentMandate.model_validate(verified.mandate_payload)
        except Exception:  # noqa: BLE001  署名・形式・期限のどれでも、通さない
            return _blocked(BlockReason.BAD_SIGNATURE)
        if int(now.timestamp()) >= (open_mandate.exp or 0):
            return _blocked(BlockReason.MANDATE_EXPIRED)

        # 3. 請求の event_id が、署名つきの委任状のイベントと一致する
        if (open_mandate.risk_data or {}).get("event_id") != req.event_id:
            return _blocked(BlockReason.EVENT_MISMATCH)

        # 4. 振込元は本人、振込先は委任状の支払先（幹事）、金額は上限以内（SDK の制約の検査）
        if req.payer_user_id == req.payee_user_id:
            return _blocked(BlockReason.PAYEE_NOT_ALLOWED)
        candidate = PaymentMandate(
            transaction_id=req.checkout_hash,
            payee=Merchant(id=req.payee_user_id, name=req.payee_user_id),
            payment_amount=Amount(amount=req.amount_yen, currency=CURRENCY),
            payment_instrument=PaymentInstrument(id=req.payer_user_id, type=INSTRUMENT_TYPE),
            iat=int(now.timestamp()),
            exp=int(now.timestamp()) + 60,
        )
        violations = check_payment_constraints(open_mandate, candidate)
        if violations:
            return _blocked(classify_violation(violations[0]))

        # 5. 請求にKUROKO（請求側）の有効な署名があり、按分表のハッシュ値を含む（B13）
        if not self._checkout.verify(
            checkout_jwt=req.checkout_jwt,
            checkout_hash=req.checkout_hash,
            event_id=req.event_id,
            payer_user_id=req.payer_user_id,
            payee_user_id=req.payee_user_id,
            amount_yen=req.amount_yen,
        ):
            return _blocked(BlockReason.INVALID_CHECKOUT)

        # 6. 本人の銀行の利用の認可が有効
        if not self._bank.is_authorized(req.payer_user_id):
            return _blocked(BlockReason.BANK_NOT_AUTHORIZED)

        # 7. 同じ参加者への完了済み・承認待ちの依頼がない
        other = self._store.find_open_payment(
            req.event_id, req.payer_user_id, exclude_payment_id=req.payment_id
        )
        if other is not None:
            return _blocked(BlockReason.DUPLICATE_PAYMENT)

        # 8. nonce が未使用（最後に確保する。ほかの検査で落ちた依頼で nonce を消費しない）
        if not self._store.claim_nonce(nonce_for(mandate_id, req.checkout_hash, attempt)):
            return _blocked(BlockReason.NONCE_REUSED)

        return GateResult(ok=True, open_token=token, mandate_id=mandate_id)


def nonce_for(mandate_id: str, checkout_hash: str, attempt: int) -> str:
    import hashlib

    raw = f"{mandate_id}|{checkout_hash}|{attempt}".encode()
    return hashlib.sha256(raw).hexdigest()[:48]


def utcnow() -> datetime:
    return datetime.now(UTC)
