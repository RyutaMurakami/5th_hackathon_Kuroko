"""振込の依頼・状況・明細・認可・削除（決定論的なコード。LLM は関与しない）。

重複の防止はここで行う: sunabar は同じ Idempotency-Key でも別の受付番号を振るので、
冪等キーから決めた transfer_id で記録を先に作り（原子的）、銀行を呼ぶのはそのあとの1回だけにする。
"""

import hashlib
import unicodedata
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from src.clients.bank import BankClient, BankError
from src.db.store import Store
from src.models.schemas import (
    StatementEntry,
    StatementResponse,
    TransferResponse,
    TransferStatus,
)

_NAMESPACE = uuid.UUID("6f1b0b52-4d0e-4c58-9a57-1d3c6e2c8a10")  # transfer_id を決める固定の名前空間

Caller = Literal["api", "payment"]


def _normalize_name(text: str) -> str:
    """全角・半角の違い（カナ・空白）を揃える。口座の名義（半角カナ）と摘要（全角）を比べるため。"""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _resolve_counterparty(remarks: str, names: dict[str, str]) -> str | None:
    """摘要の名義が、知っている口座のうちちょうど1つと一致するときだけ、その user_id を返す。"""
    text = _normalize_name(remarks)
    for prefix in ("振込 ", "振込"):
        if text.startswith(prefix):
            text = text.removeprefix(prefix).strip()
            break
    hits = [uid for uid, name in names.items() if name and name == text]
    return hits[0] if len(hits) == 1 else None


class UnknownUser(Exception):
    pass


class UnknownTransfer(Exception):
    pass


class InvalidTransfer(Exception):
    """自分宛てなど、作ってはいけない依頼。"""


class IdempotencyConflict(Exception):
    """同じ冪等キーが、別の内容の依頼に使われた。"""


class InProgress(Exception):
    """同じ冪等キーの依頼が処理の途中（結果が未確定）。銀行へ重複して送らない。"""


class BankFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def transfer_id_for(idempotency_key: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, idempotency_key))


class BankService:
    def __init__(
        self,
        *,
        store: Store,
        bank: BankClient,
        approval_ttl_seconds: int,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        is_simulated: Callable[[str], bool] = lambda _label: False,
    ) -> None:
        self._store = store
        self._bank = bank
        self._is_simulated = is_simulated  # デモで代行する振込元か（SPEC 8.10）
        self._ttl = timedelta(seconds=approval_ttl_seconds)
        self._now = now

    # --- 認可・削除 ---
    def authorize(self, user_id: str) -> bool:
        label = self._store.get_label(user_id)
        return bool(label and self._bank.has_account(label=label))

    def redact(self, user_id: str) -> bool:
        """トークンと口座の対応表を破棄する（SPEC 9.6）。transfers の記録には口座情報がない。"""
        return self._store.delete_label(user_id)

    # --- 振込 ---
    def create_transfer(
        self, *, payer_user_id: str, payee_user_id: str, amount_yen: int, idempotency_key: str
    ) -> TransferResponse:
        if payer_user_id == payee_user_id:
            raise InvalidTransfer
        payer_label = self._store.get_label(payer_user_id)
        payee_label = self._store.get_label(payee_user_id)
        if not payer_label or not payee_label:
            raise UnknownUser

        transfer_id = transfer_id_for(idempotency_key)
        fingerprint = hashlib.sha256(
            f"{payer_user_id}|{payee_user_id}|{amount_yen}".encode()
        ).hexdigest()
        record = {
            "transfer_id": transfer_id,
            "payer_user_id": payer_user_id,
            "payee_user_id": payee_user_id,
            "amount_yen": amount_yen,
            "fingerprint": fingerprint,
            "status": TransferStatus.CREATING.value,
            "apply_no": None,
            "created_at": self._now(),
            "simulated": self._is_simulated(payer_label),
        }
        existing, created = self._store.create_transfer_if_absent(transfer_id, record)
        if not created:
            if existing["fingerprint"] != fingerprint:
                raise IdempotencyConflict
            if existing["status"] == TransferStatus.CREATING.value:
                raise InProgress
            return self._refresh(existing)

        try:
            apply_no = self._bank.create_transfer(
                payer_label=payer_label,
                payee_label=payee_label,
                amount_yen=amount_yen,
                request_key=transfer_id.upper(),  # sunabar の transferRequestKey（UUID）
                idempotency_key=idempotency_key,
            )
        except BankError as e:
            self._store.update_transfer(
                transfer_id, {"status": TransferStatus.FAILED.value, "error_code": e.code}
            )
            raise BankFailure(e.code) from None
        updated = self._store.update_transfer(
            transfer_id,
            {"status": TransferStatus.AWAITING_APPROVAL.value, "apply_no": apply_no},
        )
        return self._response(updated)

    def get_transfer(self, transfer_id: str) -> TransferResponse:
        record = self._store.get_transfer(transfer_id)
        if record is None:
            raise UnknownTransfer
        return self._refresh(record)

    def _refresh(self, record: dict) -> TransferResponse:
        """承認待ちなら銀行に照会して、手続済・期限切れに進める（Webhook が無いのでポーリング）。"""
        if record["status"] == TransferStatus.AWAITING_APPROVAL.value:
            payer_label = self._store.get_label(record["payer_user_id"])
            processed = False
            if payer_label:
                try:
                    processed = self._bank.is_processed(
                        payer_label=payer_label, apply_no=record["apply_no"]
                    )
                except BankError:
                    processed = False  # 照会の失敗では状態を変えない（次のポーリングで再確認）
            if processed:
                record = self._store.update_transfer(
                    record["transfer_id"], {"status": TransferStatus.PROCESSED.value}
                )
            elif self._now() >= record["created_at"] + self._ttl:
                record = self._store.update_transfer(
                    record["transfer_id"], {"status": TransferStatus.EXPIRED.value}
                )
        return self._response(record)

    def _response(self, record: dict) -> TransferResponse:
        awaiting = record["status"] == TransferStatus.AWAITING_APPROVAL.value
        return TransferResponse(
            transfer_id=record["transfer_id"],
            status=TransferStatus(record["status"]),
            amount_yen=record["amount_yen"],
            apply_no=record.get("apply_no"),
            created_at=record["created_at"],
            approval_expires_at=record["created_at"] + self._ttl if awaiting else None,
            simulated=bool(record.get("simulated")),
        )

    def _holder_names(self, *, exclude: str) -> dict[str, str]:
        """相手の解決用: 仮名 user_id → 正規化した口座名義。この外には出さない。"""
        names: dict[str, str] = {}
        for uid, label in self._store.list_labels().items():
            if uid == exclude:
                continue
            try:
                names[uid] = _normalize_name(self._bank.holder_name(label=label))
            except BankError:
                continue
        return names

    # --- 明細 ---
    def statements(
        self, *, user_id: str, date_from: date, date_to: date, caller: Caller
    ) -> StatementResponse:
        label = self._store.get_label(user_id)
        if not label:
            raise UnknownUser
        rows, has_next = self._bank.transactions(label=label, date_from=date_from, date_to=date_to)
        names = self._holder_names(exclude=user_id)
        if caller == "api":
            rows = [r for r in rows if r.direction == "in"]  # kuroko-api は幹事口座の入金だけ
        return StatementResponse(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            entries=[
                StatementEntry(
                    item_key=r.item_key,
                    date=r.date,
                    direction=r.direction,
                    amount_yen=r.amount_yen,
                    counterparty_user_id=_resolve_counterparty(r.remarks, names),
                )
                for r in rows
            ],
            has_next=has_next,
        )
