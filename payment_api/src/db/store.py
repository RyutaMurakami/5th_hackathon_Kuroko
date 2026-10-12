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

    def demo_proxy_allowed(self, event_id: str, user_id: str) -> bool:
        """`sandbox` のイベントの参加者で、Slack のアカウントを持たないか（SPEC 7.6）、
        Web のチャット画面に列がある登場人物か（SPEC 7.7）。"""

    def web_bank_approval(self, event_id: str) -> bool:
        """登場人物の振込を、Web のカードで承認する体験用のイベントか（SPEC 7.7）。"""

    def claim_nonce(self, key: str) -> bool:
        """未使用なら使用済みにして True（原子的）。使用済みなら False。"""

    def create_payment_if_absent(
        self, payment_id: str, record: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]: ...

    def get_payment(self, payment_id: str) -> dict[str, Any] | None: ...

    def update_payment(self, payment_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def update_mandate_if_exists(self, event_id: str, user_id: str, status: str) -> None: ...

    def list_payments_by_status(self, status: str) -> list[dict[str, Any]]: ...

    def claim_settlement(self, item_key: str, payment_id: str) -> bool:
        """入金（明細の1件）を1つの支払いにだけ使う。同じ支払いの再確認は True。"""

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
        self.settlements: dict[str, str] = {}
        self.demo_proxy: set[tuple[str, str]] = set()  # 代行できる (event_id, user_id)
        self.web_bank_events: set[str] = set()  # 銀行の承認を Web のカードで行うイベント

    def web_bank_approval(self, event_id):
        return event_id in self.web_bank_events

    def demo_proxy_allowed(self, event_id, user_id):
        return (event_id, user_id) in self.demo_proxy

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

    def update_mandate_if_exists(self, event_id, user_id, status):
        key = f"{event_id}:{user_id}"
        if key in self.mandates:
            self.mandates[key]["status"] = status

    def list_payments_by_status(self, status):
        return [deepcopy(r) for r in self.payments.values() if r["status"] == status]

    def claim_settlement(self, item_key, payment_id):
        return self.settlements.setdefault(item_key, payment_id) == payment_id

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

    def demo_proxy_allowed(self, event_id, user_id):
        event = self._db.collection("events").document(event_id)
        if (event.get().to_dict() or {}).get("sandbox") is not True:
            return False
        person = event.collection("participants").document(user_id).get()
        data = person.to_dict() or {}
        return person.exists and (not data.get("slack_user_id") or data.get("demo_persona") is True)

    def web_bank_approval(self, event_id):
        data = self._db.collection("events").document(event_id).get().to_dict() or {}
        return data.get("sandbox") is True and data.get("bank_approval") == "web"

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

    def update_mandate_if_exists(self, event_id, user_id, status):
        ref = self._db.collection("mandates").document(f"{event_id}:{user_id}")
        if ref.get().exists:
            ref.update({"status": status})

    def list_payments_by_status(self, status):
        q = self._db.collection("payments").where("status", "==", status)
        return [d.to_dict() for d in q.stream()]

    def claim_settlement(self, item_key, payment_id):
        from google.api_core.exceptions import AlreadyExists

        ref = self._db.collection("settlements").document(item_key)
        try:
            ref.create({"payment_id": payment_id})
        except AlreadyExists:
            return ref.get().to_dict().get("payment_id") == payment_id
        return True

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
