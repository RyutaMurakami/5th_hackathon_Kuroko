"""payment-api が書く Payment の読み取り（`kuroko-api` は読むだけ。ARCHITECTURE 4.6）。"""

from typing import Protocol


class PaymentReader(Protocol):
    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool: ...


class MemoryPaymentReader:
    def __init__(self, completed: set[tuple[str, str]] | None = None) -> None:
        self.completed = completed or set()

    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool:
        return (event_id, payer_user_id) in self.completed


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
