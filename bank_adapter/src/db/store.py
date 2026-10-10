"""bank-adapter のデータ（専用の Firestore データベース `bank`。ARCHITECTURE 4.6）。

- accounts/{user_id}: 仮名 user_id → 口座ラベル（口座番号は持たない。実機のトークンから引く）
- transfers/{transfer_id}: 振込依頼の記録。transfer_id は冪等キーから決めるので、
  同じキーなら同じ記録に当たる
- simulated_transfers/{apply_no}: デモで代行した振込（口座ラベル・金額・日付だけ。SPEC 8.10）
"""

from copy import deepcopy
from typing import Any, Protocol


class Store(Protocol):
    def get_label(self, user_id: str) -> str | None: ...

    def set_label(self, user_id: str, label: str) -> None: ...

    def delete_label(self, user_id: str) -> bool: ...

    def list_labels(self) -> dict[str, str]:
        """仮名 user_id → 口座ラベル（明細の相手の解決に使う）。"""

    def create_transfer_if_absent(
        self, transfer_id: str, record: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        """無ければ作って (record, True)、あれば既存を (record, False) で返す（原子的）。"""

    def get_transfer(self, transfer_id: str) -> dict[str, Any] | None: ...

    def update_transfer(self, transfer_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def save_simulated(self, apply_no: str, record: dict[str, Any]) -> None:
        """代行した振込を記録する（同じ受付番号なら上書き＝1件のまま）。"""

    def list_simulated(self) -> dict[str, dict[str, Any]]: ...


class MemoryStore:
    def __init__(self) -> None:
        self.labels: dict[str, str] = {}
        self.transfers: dict[str, dict[str, Any]] = {}
        self.simulated: dict[str, dict[str, Any]] = {}

    def get_label(self, user_id: str) -> str | None:
        return self.labels.get(user_id)

    def set_label(self, user_id: str, label: str) -> None:
        self.labels[user_id] = label

    def delete_label(self, user_id: str) -> bool:
        return self.labels.pop(user_id, None) is not None

    def list_labels(self) -> dict[str, str]:
        return dict(self.labels)

    def create_transfer_if_absent(self, transfer_id, record):
        if transfer_id in self.transfers:
            return deepcopy(self.transfers[transfer_id]), False
        self.transfers[transfer_id] = deepcopy(record)
        return deepcopy(record), True

    def get_transfer(self, transfer_id):
        rec = self.transfers.get(transfer_id)
        return deepcopy(rec) if rec else None

    def update_transfer(self, transfer_id, fields):
        self.transfers[transfer_id].update(fields)
        return deepcopy(self.transfers[transfer_id])

    def save_simulated(self, apply_no, record):
        self.simulated[apply_no] = deepcopy(record)

    def list_simulated(self):
        return deepcopy(self.simulated)


class FirestoreStore:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None, database=database)

    def get_label(self, user_id):
        snap = self._db.collection("accounts").document(user_id).get()
        return snap.to_dict().get("label") if snap.exists else None

    def set_label(self, user_id, label):
        self._db.collection("accounts").document(user_id).set({"label": label})

    def delete_label(self, user_id):
        ref = self._db.collection("accounts").document(user_id)
        existed = ref.get().exists
        ref.delete()
        return existed

    def list_labels(self):
        return {d.id: d.to_dict().get("label") for d in self._db.collection("accounts").stream()}

    def create_transfer_if_absent(self, transfer_id, record):
        from google.api_core.exceptions import AlreadyExists

        ref = self._db.collection("transfers").document(transfer_id)
        try:
            ref.create(record)
        except AlreadyExists:
            return ref.get().to_dict(), False
        return record, True

    def get_transfer(self, transfer_id):
        snap = self._db.collection("transfers").document(transfer_id).get()
        return snap.to_dict() if snap.exists else None

    def update_transfer(self, transfer_id, fields):
        ref = self._db.collection("transfers").document(transfer_id)
        ref.update(fields)
        return ref.get().to_dict()

    def save_simulated(self, apply_no, record):
        self._db.collection("simulated_transfers").document(apply_no).set(record)

    def list_simulated(self):
        return {d.id: d.to_dict() for d in self._db.collection("simulated_transfers").stream()}
