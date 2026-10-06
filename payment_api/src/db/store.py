"""payment-api のデータ（Firestore `(default)`）。委任状の写し・支払い・使用済み nonce。

委任状の中身（上限・支払先・期限）の正は署名済み SD-JWT で、ここの `cap_yen` などは写し
（ARCHITECTURE 4.6）。`status` と nonce の使用状況はここが正。
"""

from copy import deepcopy
from typing import Any, Protocol


class Store(Protocol):
    def put_mandate(self, mandate_id: str, record: dict[str, Any]) -> None: ...

    def get_mandate(self, mandate_id: str) -> dict[str, Any] | None: ...

    def update_mandate(self, mandate_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def claim_nonce(self, key: str) -> bool:
        """未使用なら使用済みにして True（原子的）。使用済みなら False。"""

    def create_payment_if_absent(
        self, payment_id: str, record: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]: ...

    def get_payment(self, payment_id: str) -> dict[str, Any] | None: ...

    def update_payment(self, payment_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def find_open_payment(
        self, event_id: str, payer_user_id: str, exclude_payment_id: str | None = None
    ) -> dict[str, Any] | None:
        """同じ参加者の、完了済み・承認待ちの支払い（exclude の支払いを除く）。"""


_OPEN = ("pending", "awaiting_bank_approval", "completed")


class MemoryStore:
    def __init__(self) -> None:
        self.mandates: dict[str, dict[str, Any]] = {}
        self.payments: dict[str, dict[str, Any]] = {}
        self.nonces: set[str] = set()

    def put_mandate(self, mandate_id, record):
        self.mandates[mandate_id] = deepcopy(record)

    def get_mandate(self, mandate_id):
        rec = self.mandates.get(mandate_id)
        return deepcopy(rec) if rec else None

    def update_mandate(self, mandate_id, fields):
        self.mandates[mandate_id].update(fields)
        return deepcopy(self.mandates[mandate_id])

    def claim_nonce(self, key):
        if key in self.nonces:
            return False
        self.nonces.add(key)
        return True

    def create_payment_if_absent(self, payment_id, record):
        if payment_id in self.payments:
            return deepcopy(self.payments[payment_id]), False
        self.payments[payment_id] = deepcopy(record)
        return deepcopy(record), True

    def get_payment(self, payment_id):
        rec = self.payments.get(payment_id)
        return deepcopy(rec) if rec else None

    def update_payment(self, payment_id, fields):
        self.payments[payment_id].update(fields)
        return deepcopy(self.payments[payment_id])

    def find_open_payment(self, event_id, payer_user_id, exclude_payment_id=None):
        for rec in self.payments.values():
            if (
                rec["payment_id"] != exclude_payment_id
                and rec["event_id"] == event_id
                and rec["payer_user_id"] == payer_user_id
                and rec["status"] in _OPEN
            ):
                return deepcopy(rec)
        return None


class FirestoreStore:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._fs = firestore
        self._db = firestore.Client(project=project or None, database=database)

    def put_mandate(self, mandate_id, record):
        self._db.collection("mandates").document(mandate_id).set(record)

    def get_mandate(self, mandate_id):
        snap = self._db.collection("mandates").document(mandate_id).get()
        return snap.to_dict() if snap.exists else None

    def update_mandate(self, mandate_id, fields):
        ref = self._db.collection("mandates").document(mandate_id)
        ref.update(fields)
        return ref.get().to_dict()

    def claim_nonce(self, key):
        from google.api_core.exceptions import AlreadyExists

        try:
            self._db.collection("nonces").document(key).create({"used": True})
        except AlreadyExists:
            return False
        return True

    def create_payment_if_absent(self, payment_id, record):
        from google.api_core.exceptions import AlreadyExists

        ref = self._db.collection("payments").document(payment_id)
        try:
            ref.create(record)
        except AlreadyExists:
            return ref.get().to_dict(), False
        return record, True

    def get_payment(self, payment_id):
        snap = self._db.collection("payments").document(payment_id).get()
        return snap.to_dict() if snap.exists else None

    def update_payment(self, payment_id, fields):
        ref = self._db.collection("payments").document(payment_id)
        ref.update(fields)
        return ref.get().to_dict()

    def find_open_payment(self, event_id, payer_user_id, exclude_payment_id=None):
        q = (
            self._db.collection("payments")
            .where("event_id", "==", event_id)
            .where("payer_user_id", "==", payer_user_id)
            .where("status", "in", list(_OPEN))
        )
        for snap in q.stream():
            if snap.id != exclude_payment_id:
                return snap.to_dict()
        return None
