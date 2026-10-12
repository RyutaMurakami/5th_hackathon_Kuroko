"""イベントの状態の進行・経緯（判断ログ）・通知（SPEC 5章・7.5。TASKS B14）。

状態を進めるのは**コード**で、きっかけは事実（出欠が出そろった・予約を確定した・領収書を確定した…）。
LLM は状態を動かさない。経緯には、誰が・何をしたかの**要約だけ**を残す（個人情報・原文は入れない）。
"""

import datetime as dt
import uuid
from collections.abc import Callable

from src.db.events import EventStore
from src.models.dashboard import DecisionEntry, Notification, NotificationKind
from src.models.event import Event, EventStatus, Participant, ParticipantRole, RsvpStatus
from src.models.policy import PolicySnapshot
from src.seed.sample_company import demo_participants
from src.services.policy import load_snapshot

PAYERS = (ParticipantRole.PARTICIPANT, ParticipantRole.APPROVER)


class Lifecycle:
    def __init__(
        self,
        *,
        store: EventStore,
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
        roster: Callable[[], list[Participant]] = demo_participants,
        snapshot=load_snapshot,  # noqa: ANN001
    ) -> None:
        self._store, self._now, self._roster, self._snapshot = store, now, roster, snapshot

    # ---- 経緯・通知 ----
    def log(self, event_id: str, actor: str, action_type: str, summary: str) -> None:
        self._store.save_decision(
            event_id,
            DecisionEntry(
                at=self._now(), actor=actor, action_type=action_type, summary=summary[:200]
            ),  # type: ignore[arg-type]
        )

    def notify(self, event: Event, kind: NotificationKind, text: str) -> None:
        if not event.organizer_web_uid:
            return
        self._store.save_notification(
            Notification(
                notification_id=f"nt_{uuid.uuid4().hex[:16]}",
                uid=event.organizer_web_uid,
                event_id=event.event_id,
                kind=kind,
                text=text[:200],
                created_at=self._now(),
            )
        )

    # ---- 計画の確定: 規程の写しと参加者を用意する ----
    def prepare_event(
        self, event: Event, *, owner_email: str = "", snapshot: PolicySnapshot | None = None
    ) -> Event:
        """規程の写し（以後の計算はこれだけを使う。9.7）と、参加者（株式会社Akakuraの名簿）を用意する。

        Slack ユーザーは `config/slack_users`（登場人物 → Slack ID）から入れる。
        無い人には DM を送れない。
        幹事の `user_id` は名簿の幹事（銀行の口座の対応づけに使う）。
        """
        # 規程の文書から読み取って検証した値（呼び出し側が渡す）。無ければ、既定の値（yaml）
        snap = snapshot or self._snapshot()
        people = self._roster()
        slack = self._store.slack_user_map()
        organizer = next((p for p in people if p.role is ParticipantRole.ORGANIZER), None)
        for p in people:
            self._store.save_participant(
                event.event_id,
                p.model_copy(
                    update={"slack_user_id": slack.get(p.user_id), "attendance_confirmed": True}
                ),
            )
        # 体験用のイベントでは、登場人物の振込を Web のカードで承認する。実演用に登録した
        # アカウントのイベントだけ、本物の銀行（sunabar）で承認する（SPEC 7.7）
        # 開発者の実演用の画面で作ったイベント（`ui_mode = live`）で、登録したアカウントのときだけ
        live = event.ui_mode == "live" and owner_email.lower() in self._store.live_bank_emails()
        return event.model_copy(
            update={
                "bank_approval": "web" if event.sandbox and not live else "bank",
                "policy_snapshot": snap,
                "policy_id": snap.policy_id,
                "policy_version": snap.version,
                "organizer_user_id": organizer.user_id if organizer else event.organizer_user_id,
                "guests_of_honor": [
                    p.user_id for p in people if p.role is ParticipantRole.GUEST_OF_HONOR
                ],
            }
        )

    # ---- 予算超過の最終確認（承認者。Slack）のあと、予約を確定済みにする ----
    def after_budget_final(self, event_id: str) -> None:
        event = self._store.get_event(event_id)
        esc = event.budget_escalation if event else None
        if event is None or esc is None or esc.final_confirmed_at is None:
            return
        if event.status is not EventStatus.VENUE or not (event.venue or {}).get("course_price_yen"):
            return
        self._store.save_event(event.model_copy(update={"status": EventStatus.BOOKED}))
        self.log(event_id, "human", "確認", "承認者が予算超過での続行を承認しました（Slack）")
        self.notify(
            event, NotificationKind.CONFIRM_NEEDED, "予約が確定しました。開催後にお知らせください"
        )

    # ---- 出欠が出そろったら、店の選択へ ----
    def after_rsvp(self, event_id: str) -> None:
        event = self._store.get_event(event_id)
        if event is None or event.status is not EventStatus.RSVP:
            return
        payers = [p for p in self._store.list_participants(event_id) if p.role in PAYERS]
        if not payers or any(p.rsvp_status is RsvpStatus.PENDING for p in payers):
            return
        attending = sum(1 for p in payers if p.rsvp_status is RsvpStatus.ATTENDING)
        self._store.save_event(event.model_copy(update={"status": EventStatus.VENUE}))
        self.log(
            event_id,
            "human",
            "記録",
            f"出欠が出そろいました（参加 {attending}名・欠席 {len(payers) - attending}名）",
        )
        self.notify(
            event, NotificationKind.CONFIRM_NEEDED, "出欠が出そろいました。店を選んでください"
        )
