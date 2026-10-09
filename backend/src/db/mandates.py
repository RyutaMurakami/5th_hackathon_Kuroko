"""payment-api が書く委任状の記録（status・上限・期限）の読み取り（App Home の表示用）。

`kuroko-api` は読むだけ。署名つきの委任状の本体（SD-JWT）は読まない・返さない。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class MandateInfo:
    mandate_id: str
    status: str  # active / used / revoked / expired
    cap_yen: int
    expires_at: datetime | None


class MandateReader(Protocol):
    def get(self, mandate_id: str) -> MandateInfo | None: ...


class MemoryMandateReader:
    def __init__(self, items: dict[str, MandateInfo] | None = None) -> None:
        self.items = items or {}

    def get(self, mandate_id: str) -> MandateInfo | None:
        return self.items.get(mandate_id)


class FirestoreMandateReader:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None, database=database)

    def get(self, mandate_id: str) -> MandateInfo | None:
        snap = self._db.collection("mandates").document(mandate_id).get()
        if not snap.exists:
            return None
        d = snap.to_dict()
        return MandateInfo(
            mandate_id=mandate_id,
            status=d["status"],
            cap_yen=int(d["cap_yen"]),
            expires_at=d.get("expires_at"),
        )
