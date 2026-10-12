"""イベント・参加者・按分・承認のデータアクセス（Firestore `(default)`。TASKS B1）。

永続化の詳細はここに閉じ込め、services/ は `EventStore`（Protocol）だけを見る。
- events/{event_id}                       Event（policy_snapshot を含む）
- events/{event_id}/participants/{user_id} Participant
- events/{event_id}/receipts/current       Receipt（幹事が確定した領収書の金額）
- events/{event_id}/splits/current         SplitResult（承認の対象の金額表。上書きは承認前だけ）
- events/{event_id}/approvals/current      Approval
- events/{event_id}/cards/{card_id}        PersonaCard（登場人物に届いたカード。SPEC 7.7）
"""

from typing import Protocol

from src.models.dashboard import DecisionEntry, Message, Notification, PersonaCard, Upload
from src.models.event import Event, Participant, Receipt
from src.models.feedback import Feedback, Retrospective
from src.models.split import Approval, ApprovalStatus, SplitResult


class EventStore(Protocol):
    def save_event(self, event: Event) -> None: ...

    def get_event(self, event_id: str) -> Event | None: ...

    def save_participant(self, event_id: str, participant: Participant) -> None: ...

    def list_participants(self, event_id: str) -> list[Participant]: ...

    # ---- Web ダッシュボード（B14）----
    def list_events_for_organizer(self, uid: str) -> list[Event]: ...

    def list_events_for_guest(self, uid: str) -> list[Event]: ...

    def list_expired_sandbox(self, now) -> list[Event]: ...  # noqa: ANN001

    def delete_event(self, event_id: str) -> None:
        """イベントと、そのサブコレクション（参加者・按分・メッセージなど）をすべて削除する。"""

    def save_message(self, message: Message) -> None: ...

    def get_message(self, event_id: str, message_id: str) -> Message | None: ...

    def list_messages(self, event_id: str) -> list[Message]: ...

    def save_notification(self, notification: Notification) -> None: ...

    def get_notification(self, notification_id: str) -> Notification | None: ...

    def list_notifications(self, uid: str) -> list[Notification]: ...

    def save_upload(self, upload: Upload) -> None: ...

    def get_upload(self, event_id: str, upload_id: str) -> Upload | None: ...

    def list_uploads(self, event_id: str) -> list[Upload]: ...

    def save_decision(self, event_id: str, entry: DecisionEntry) -> None: ...

    def list_decisions(self, event_id: str) -> list[DecisionEntry]: ...

    def slack_user_map(self) -> dict[str, str]:
        """登場人物の user_id → Slack ユーザーID（Firestore `config/slack_users`。検証用）。"""

    def dashboard_role(self, email: str) -> str | None:
        """許可リスト（`dashboard_users`）の役割。載っていなければ None（= ゲスト）。"""

    def guest_enabled(self) -> bool:
        """ゲストの全体のキルスイッチ（Firestore `config/guest.guest_enabled`）。既定は有効。"""

    def list_events_by_status(self, status: str) -> list[Event]: ...

    def live_bank_emails(self) -> set[str]:
        """本物の銀行で承認する実演用の Google アカウント（`config/demo`。SPEC 7.7）。"""

    def save_card(self, card: PersonaCard) -> None: ...

    def get_card(self, event_id: str, card_id: str) -> PersonaCard | None: ...

    def list_cards(self, event_id: str) -> list[PersonaCard]: ...

    def save_feedback(self, feedback: Feedback) -> None: ...

    def get_feedback(self, event_id: str, user_id: str) -> Feedback | None: ...

    def list_feedbacks(self, event_id: str) -> list[Feedback]: ...

    def find_open_comment(self, slack_user_id: str) -> Feedback | None:
        """この Slack ユーザーの、コメントを受け付け中の振り返り（いちばん新しいもの）。"""

    def save_retro(self, retro: Retrospective) -> None: ...

    def get_retro(self, event_id: str) -> Retrospective | None: ...

    def list_retros_by_status(self, status: str) -> list[Retrospective]: ...

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
        self.feedbacks: dict[tuple[str, str], Feedback] = {}
        self.messages: dict[str, dict[str, Message]] = {}
        self.notifications: dict[str, Notification] = {}
        self.uploads: dict[str, dict[str, Upload]] = {}
        self.decisions: dict[str, list[DecisionEntry]] = {}
        self.slack_users: dict[str, str] = {}
        self.users: dict[str, str] = {}  # メール → 役割
        self.guest_switch = True
        self.retros: dict[str, Retrospective] = {}
        self.splits: dict[str, SplitResult] = {}
        self.approvals: dict[str, Approval] = {}
        self.cards: dict[str, dict[str, PersonaCard]] = {}
        self.live_emails: set[str] = set()

    def live_bank_emails(self):
        return set(self.live_emails)

    def save_card(self, card):
        self.cards.setdefault(card.event_id, {})[card.card_id] = card.model_copy(deep=True)

    def get_card(self, event_id, card_id):
        c = self.cards.get(event_id, {}).get(card_id)
        return c.model_copy(deep=True) if c else None

    def list_cards(self, event_id):
        rows = self.cards.get(event_id, {}).values()
        return [c.model_copy(deep=True) for c in sorted(rows, key=lambda c: c.created_at)]

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

    def list_events_for_organizer(self, uid):
        rows = [e for e in self.events.values() if e.organizer_web_uid == uid and not e.sandbox]
        return [e.model_copy(deep=True) for e in sorted(rows, key=lambda e: e.datetime)]

    def list_events_for_guest(self, uid):
        rows = [e for e in self.events.values() if e.sandbox and e.guest_owner_uid == uid]
        return [e.model_copy(deep=True) for e in sorted(rows, key=lambda e: e.datetime)]

    def list_expired_sandbox(self, now):
        return [
            e.model_copy(deep=True)
            for e in self.events.values()
            if e.sandbox and e.expires_at is not None and e.expires_at <= now
        ]

    def delete_event(self, event_id):
        self.events.pop(event_id, None)
        for table in (self.participants, self.messages, self.uploads, self.decisions, self.cards):
            table.pop(event_id, None)
        for table in (self.receipts, self.splits, self.approvals, self.retros):
            table.pop(event_id, None)
        self.feedbacks = {k: v for k, v in self.feedbacks.items() if k[0] != event_id}

    def save_message(self, message):
        self.messages.setdefault(message.event_id, {})[message.message_id] = message.model_copy()

    def get_message(self, event_id, message_id):
        m = self.messages.get(event_id, {}).get(message_id)
        return m.model_copy() if m else None

    def list_messages(self, event_id):
        rows = self.messages.get(event_id, {}).values()
        return [m.model_copy() for m in sorted(rows, key=lambda m: (m.created_at, m.message_id))]

    def save_notification(self, notification):
        self.notifications[notification.notification_id] = notification.model_copy()

    def get_notification(self, notification_id):
        n = self.notifications.get(notification_id)
        return n.model_copy() if n else None

    def list_notifications(self, uid):
        rows = [n for n in self.notifications.values() if n.uid == uid]
        return [n.model_copy() for n in sorted(rows, key=lambda n: n.created_at, reverse=True)]

    def save_upload(self, upload):
        self.uploads.setdefault(upload.event_id, {})[upload.upload_id] = upload.model_copy()

    def get_upload(self, event_id, upload_id):
        u = self.uploads.get(event_id, {}).get(upload_id)
        return u.model_copy() if u else None

    def list_uploads(self, event_id):
        rows = self.uploads.get(event_id, {}).values()
        return [u.model_copy() for u in sorted(rows, key=lambda u: (u.created_at, u.upload_id))]

    def save_decision(self, event_id, entry):
        self.decisions.setdefault(event_id, []).append(entry)

    def list_decisions(self, event_id):
        return list(self.decisions.get(event_id, []))

    def slack_user_map(self):
        return dict(self.slack_users)

    def dashboard_role(self, email):
        return self.users.get(email.lower())

    def guest_enabled(self):
        return self.guest_switch

    def list_events_by_status(self, status):
        return [e.model_copy(deep=True) for e in self.events.values() if e.status.value == status]

    def save_feedback(self, feedback):
        self.feedbacks[(feedback.event_id, feedback.user_id)] = feedback.model_copy(deep=True)

    def get_feedback(self, event_id, user_id):
        f = self.feedbacks.get((event_id, user_id))
        return f.model_copy(deep=True) if f else None

    def list_feedbacks(self, event_id):
        return [
            f.model_copy(deep=True) for (e, _), f in sorted(self.feedbacks.items()) if e == event_id
        ]

    def find_open_comment(self, slack_user_id):
        mine = []
        for (event_id, user_id), f in self.feedbacks.items():
            p = self.participants.get(event_id, {}).get(user_id)
            if f.comment_open and p and p.slack_user_id == slack_user_id:
                mine.append(f)
        return max(mine, key=lambda f: f.submitted_at).model_copy(deep=True) if mine else None

    def save_retro(self, retro):
        self.retros[retro.event_id] = retro.model_copy(deep=True)

    def get_retro(self, event_id):
        r = self.retros.get(event_id)
        return r.model_copy(deep=True) if r else None

    def list_retros_by_status(self, status):
        return [r.model_copy(deep=True) for r in self.retros.values() if r.status.value == status]

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

    def list_events_for_organizer(self, uid):
        docs = self._db.collection("events").where("organizer_web_uid", "==", uid).stream()
        events = [Event.model_validate(d.to_dict()) for d in docs]
        return sorted((e for e in events if not e.sandbox), key=lambda e: e.datetime)

    def list_events_for_guest(self, uid):
        docs = self._db.collection("events").where("guest_owner_uid", "==", uid).stream()
        events = [Event.model_validate(d.to_dict()) for d in docs]
        return sorted((e for e in events if e.sandbox), key=lambda e: e.datetime)

    def list_expired_sandbox(self, now):
        docs = self._db.collection("events").where("sandbox", "==", True).stream()
        events = [Event.model_validate(d.to_dict()) for d in docs]
        return [e for e in events if e.expires_at is not None and e.expires_at <= now]

    def delete_event(self, event_id):
        self._db.recursive_delete(self._event(event_id))  # サブコレクションごと削除する

    def save_message(self, message):
        self._event(message.event_id).collection("messages").document(message.message_id).set(
            message.model_dump(mode="json")
        )

    def get_message(self, event_id, message_id):
        snap = self._event(event_id).collection("messages").document(message_id).get()
        return Message.model_validate(snap.to_dict()) if snap.exists else None

    def list_messages(self, event_id):
        docs = self._event(event_id).collection("messages").stream()
        rows = [Message.model_validate(d.to_dict()) for d in docs]
        return sorted(rows, key=lambda m: (m.created_at, m.message_id))

    def save_notification(self, notification):
        self._db.collection("notifications").document(notification.notification_id).set(
            notification.model_dump(mode="json")
        )

    def get_notification(self, notification_id):
        snap = self._db.collection("notifications").document(notification_id).get()
        return Notification.model_validate(snap.to_dict()) if snap.exists else None

    def list_notifications(self, uid):
        docs = self._db.collection("notifications").where("uid", "==", uid).stream()
        rows = [Notification.model_validate(d.to_dict()) for d in docs]
        return sorted(rows, key=lambda n: n.created_at, reverse=True)

    def save_upload(self, upload):
        self._event(upload.event_id).collection("uploads").document(upload.upload_id).set(
            upload.model_dump(mode="json")
        )

    def get_upload(self, event_id, upload_id):
        snap = self._event(event_id).collection("uploads").document(upload_id).get()
        return Upload.model_validate(snap.to_dict()) if snap.exists else None

    def list_uploads(self, event_id):
        docs = self._event(event_id).collection("uploads").stream()
        rows = [Upload.model_validate(d.to_dict()) for d in docs]
        return sorted(rows, key=lambda u: (u.created_at, u.upload_id))

    def save_decision(self, event_id, entry):
        self._event(event_id).collection("decisions").add(entry.model_dump(mode="json"))

    def list_decisions(self, event_id):
        docs = self._event(event_id).collection("decisions").stream()
        rows = [DecisionEntry.model_validate(d.to_dict()) for d in docs]
        return sorted(rows, key=lambda d: d.at)

    def slack_user_map(self):
        snap = self._db.collection("config").document("slack_users").get()
        return {str(k): str(v) for k, v in (snap.to_dict() or {}).items()} if snap.exists else {}

    def dashboard_role(self, email):
        snap = self._db.collection("dashboard_users").document(email.lower()).get()
        return (snap.to_dict() or {}).get("role") if snap.exists else None

    def guest_enabled(self):
        snap = self._db.collection("config").document("guest").get()
        return bool((snap.to_dict() or {}).get("guest_enabled", True)) if snap.exists else True

    def list_events_by_status(self, status):
        docs = self._db.collection("events").where("status", "==", status).stream()
        return [Event.model_validate(d.to_dict()) for d in docs]

    def save_feedback(self, feedback):
        self._event(feedback.event_id).collection("feedbacks").document(feedback.user_id).set(
            feedback.model_dump(mode="json")
        )

    def get_feedback(self, event_id, user_id):
        snap = self._event(event_id).collection("feedbacks").document(user_id).get()
        return Feedback.model_validate(snap.to_dict()) if snap.exists else None

    def list_feedbacks(self, event_id):
        docs = self._event(event_id).collection("feedbacks").stream()
        return sorted((Feedback.model_validate(d.to_dict()) for d in docs), key=lambda f: f.user_id)

    def find_open_comment(self, slack_user_id):
        mine = []
        for event, p in self.find_by_slack_user(slack_user_id):
            f = self.get_feedback(event.event_id, p.user_id)
            if f is not None and f.comment_open:
                mine.append(f)
        return max(mine, key=lambda f: f.submitted_at) if mine else None

    def save_retro(self, retro):
        self._event(retro.event_id).collection("retros").document("current").set(
            retro.model_dump(mode="json")
        )

    def get_retro(self, event_id):
        snap = self._event(event_id).collection("retros").document("current").get()
        return Retrospective.model_validate(snap.to_dict()) if snap.exists else None

    def list_retros_by_status(self, status):
        docs = self._db.collection_group("retros").where("status", "==", status).stream()
        return [Retrospective.model_validate(d.to_dict()) for d in docs]

    def live_bank_emails(self):
        snap = self._db.collection("config").document("demo").get()
        emails = (snap.to_dict() or {}).get("live_bank_emails") or [] if snap.exists else []
        return {str(e).lower() for e in emails}

    def save_card(self, card):
        self._event(card.event_id).collection("cards").document(card.card_id).set(
            card.model_dump(mode="json")
        )

    def get_card(self, event_id, card_id):
        snap = self._event(event_id).collection("cards").document(card_id).get()
        return PersonaCard.model_validate(snap.to_dict()) if snap.exists else None

    def list_cards(self, event_id):
        docs = self._event(event_id).collection("cards").stream()
        return sorted(
            (PersonaCard.model_validate(d.to_dict()) for d in docs), key=lambda c: c.created_at
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
