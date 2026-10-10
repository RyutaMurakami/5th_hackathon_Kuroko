"""イベント・参加者・按分・承認のデータアクセス（Firestore `(default)`。TASKS B1）。

永続化の詳細はここに閉じ込め、services/ は `EventStore`（Protocol）だけを見る。
- events/{event_id}                       Event（policy_snapshot を含む）
- events/{event_id}/participants/{user_id} Participant
- events/{event_id}/receipts/current       Receipt（幹事が確定した領収書の金額）
- events/{event_id}/splits/current         SplitResult（承認の対象の金額表。上書きは承認前だけ）
- events/{event_id}/approvals/current      Approval
"""

from typing import Protocol

from src.models.event import Event, Participant, Receipt
from src.models.split import Approval, ApprovalStatus, SplitResult


class EventStore(Protocol):
    def save_event(self, event: Event) -> None: ...

    def get_event(self, event_id: str) -> Event | None: ...

    def save_participant(self, event_id: str, participant: Participant) -> None: ...

    def list_participants(self, event_id: str) -> list[Participant]: ...

    def find_by_slack_user(self, slack_user_id: str) -> list[tuple[Event, Participant]]:
        """この Slack ユーザーが参加者として載っているイベント（App Home の表示用）。"""

    def save_receipt(self, receipt: Receipt) -> None: ...

    def get_receipt(self, event_id: str) -> Receipt | None: ...

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
        self.receipts: dict[str, Receipt] = {}
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

    def find_by_slack_user(self, slack_user_id):
        found = []
        for event_id, rows in self.participants.items():
            for p in rows.values():
                if p.slack_user_id == slack_user_id and event_id in self.events:
                    found.append((self.events[event_id].model_copy(deep=True), p.model_copy()))
        return sorted(found, key=lambda x: (x[0].datetime, x[0].event_id))

    def save_receipt(self, receipt: Receipt) -> None:
        self.receipts[receipt.event_id] = receipt.model_copy()

    def get_receipt(self, event_id: str) -> Receipt | None:
        r = self.receipts.get(event_id)
        return r.model_copy() if r else None

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

    def find_by_slack_user(self, slack_user_id):
        found = []
        docs = self._db.collection_group("participants").where("slack_user_id", "==", slack_user_id)
        for doc in docs.stream():
            event_id = doc.reference.parent.parent.id
            event = self.get_event(event_id)
            if event is not None:
                found.append((event, Participant.model_validate(doc.to_dict())))
        return sorted(found, key=lambda x: (x[0].datetime, x[0].event_id))

    def save_receipt(self, receipt: Receipt) -> None:
        self._event(receipt.event_id).collection("receipts").document("current").set(
            receipt.model_dump(mode="json")
        )

    def get_receipt(self, event_id: str) -> Receipt | None:
        snap = self._event(event_id).collection("receipts").document("current").get()
        return Receipt.model_validate(snap.to_dict()) if snap.exists else None

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
