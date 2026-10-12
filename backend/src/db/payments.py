"""payment-api が書く Payment の読み取り（`kuroko-api` は読むだけ。ARCHITECTURE 4.6）。"""

from typing import Protocol


class PaymentReader(Protocol):
    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool: ...

    def list_payments(self, event_id: str) -> list[dict]:
        """イベントの支払い（payment-api が書いたもの）。読み取りだけ。"""

    def open_transfer_id(self, event_id: str, payer_user_id: str) -> str | None:
        """銀行での承認を待っている振込依頼の ID（無ければ None）。画面には出さない。"""


class MemoryPaymentReader:
    def __init__(self, completed: set[tuple[str, str]] | None = None) -> None:
        self.completed = completed or set()
        self.payments: list[dict] = []

    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool:
        return (event_id, payer_user_id) in self.completed

    def _of(self, event_id):
        return [p for p in self.payments if p.get("event_id", event_id) == event_id]

    def list_payments(self, event_id):
        # 振込依頼の ID は、一覧に出さない（実装の FirestorePaymentReader と同じ）
        return [{k: v for k, v in p.items() if k != "transfer_id"} for p in self._of(event_id)]

    def open_transfer_id(self, event_id, payer_user_id):
        for p in self._of(event_id):
            if p.get("payer_user_id") == payer_user_id and p.get("status") == AWAITING:
                return p.get("transfer_id")
        return None


AWAITING = "awaiting_bank_approval"

_PAYMENT_FIELDS = (
    "payment_id", "payer_user_id", "payee_user_id", "amount_yen", "status",
    "approval_deadline", "retry_count", "block_reason", "updated_at",
)  # fmt: skip


class FirestorePaymentReader:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None, database=database)

    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool:
        q = (
            self._db.collection("payments")
            .where("event_id", "==", event_id)
            .where("payer_user_id", "==", payer_user_id)
            .where("status", "==", "completed")
            .limit(1)
        )
        return any(True for _ in q.stream())

    def open_transfer_id(self, event_id: str, payer_user_id: str) -> str | None:
        docs = self._db.collection("payments").where("event_id", "==", event_id).stream()
        for d in docs:
            r = d.to_dict() or {}
            if r.get("payer_user_id") == payer_user_id and r.get("status") == AWAITING:
                return r.get("transfer_id")
        return None

    def list_payments(self, event_id: str) -> list[dict]:
        docs = self._db.collection("payments").where("event_id", "==", event_id).stream()
        rows = [d.to_dict() or {} for d in docs]
        return sorted(
            ({k: _plain(r.get(k)) for k in _PAYMENT_FIELDS} for r in rows),
            key=lambda r: str(r["payer_user_id"]),
        )


def _plain(v):  # noqa: ANN001, ANN202
    """Firestore の日時などを、JSON にできる値にする。"""
    return v.isoformat() if hasattr(v, "isoformat") else v
