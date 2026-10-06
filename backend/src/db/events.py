"""イベント・参加者・按分・承認のデータアクセス（Firestore `(default)`。TASKS B1）。

永続化の詳細はここに閉じ込め、services/ は `EventStore`（Protocol）だけを見る。
- events/{event_id}                       Event（policy_snapshot を含む）
- events/{event_id}/participants/{user_id} Participant
- events/{event_id}/splits/current         SplitResult（承認の対象の金額表。上書きは承認前だけ）
- events/{event_id}/approvals/current      Approval
"""

from typing import Protocol

from src.models.event import Event, Participant
from src.models.split import Approval, ApprovalStatus, SplitResult


class EventStore(Protocol):
    def save_event(self, event: Event) -> None: ...

    def get_event(self, event_id: str) -> Event | None: ...

    def save_participant(self, event_id: str, participant: Participant) -> None: ...

    def list_participants(self, event_id: str) -> list[Participant]: ...

    def save_split(self, split: SplitResult) -> None: ...

    def get_split(self, event_id: str) -> SplitResult | None: ...

    def save_approval(self, approval: Approval) -> None: ...

    def get_approval(self, event_id: str) -> Approval | None: ...


class ApprovedSplitIsFinal(Exception):
    """承認済みの按分は、上書きできない（承認されたハッシュ値と請求の金額表を一致させるため）。"""


def _guard_split_overwrite(approval: Approval | None) -> None:
    if approval is not None and approval.status == ApprovalStatus.APPROVED:
        raise ApprovedSplitIsFinal


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: dict[str, Event] = {}
        self.participants: dict[str, dict[str, Participant]] = {}
        self.splits: dict[str, SplitResult] = {}
        self.approvals: dict[str, Approval] = {}

    def save_event(self, event: Event) -> None:
        self.events[event.event_id] = event.model_copy(deep=True)

    def get_event(self, event_id: str) -> Event | None:
        e = self.events.get(event_id)
        return e.model_copy(deep=True) if e else None

    def save_participant(self, event_id: str, participant: Participant) -> None:
        self.participants.setdefault(event_id, {})[participant.user_id] = participant.model_copy()

    def list_participants(self, event_id: str) -> list[Participant]:
        rows = self.participants.get(event_id, {})
        return [rows[k].model_copy() for k in sorted(rows)]

    def save_split(self, split: SplitResult) -> None:
        _guard_split_overwrite(self.approvals.get(split.event_id))
        self.splits[split.event_id] = split.model_copy(deep=True)

    def get_split(self, event_id: str) -> SplitResult | None:
        s = self.splits.get(event_id)
        return s.model_copy(deep=True) if s else None

    def save_approval(self, approval: Approval) -> None:
        self.approvals[approval.event_id] = approval.model_copy()

    def get_approval(self, event_id: str) -> Approval | None:
        a = self.approvals.get(event_id)
        return a.model_copy() if a else None


class FirestoreEventStore:
    def __init__(self, *, project: str, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None, database=database)

    def _event(self, event_id: str):
        return self._db.collection("events").document(event_id)

    def save_event(self, event: Event) -> None:
        self._event(event.event_id).set(event.model_dump(mode="json"))

    def get_event(self, event_id: str) -> Event | None:
        snap = self._event(event_id).get()
        return Event.model_validate(snap.to_dict()) if snap.exists else None

    def save_participant(self, event_id: str, participant: Participant) -> None:
        self._event(event_id).collection("participants").document(participant.user_id).set(
            participant.model_dump(mode="json")
        )

    def list_participants(self, event_id: str) -> list[Participant]:
        docs = self._event(event_id).collection("participants").stream()
        return sorted(
            (Participant.model_validate(d.to_dict()) for d in docs), key=lambda p: p.user_id
        )

    def save_split(self, split: SplitResult) -> None:
        _guard_split_overwrite(self.get_approval(split.event_id))
        self._event(split.event_id).collection("splits").document("current").set(
            split.model_dump(mode="json")
        )

    def get_split(self, event_id: str) -> SplitResult | None:
        snap = self._event(event_id).collection("splits").document("current").get()
        return SplitResult.model_validate(snap.to_dict()) if snap.exists else None

    def save_approval(self, approval: Approval) -> None:
        self._event(approval.event_id).collection("approvals").document("current").set(
            approval.model_dump(mode="json")
        )

    def get_approval(self, event_id: str) -> Approval | None:
        snap = self._event(event_id).collection("approvals").document("current").get()
        return Approval.model_validate(snap.to_dict()) if snap.exists else None
