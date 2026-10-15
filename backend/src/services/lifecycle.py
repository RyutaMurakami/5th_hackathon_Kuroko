"""イベントの状態の進行・経緯（判断ログ）・通知（SPEC 5章・7.5。TASKS B14）。

状態を進めるのは**コード**で、きっかけは事実（出欠が出そろった・予約を確定した・領収書を確定した…）。
LLM は状態を動かさない。経緯には、誰が・何をしたかの**要約だけ**を残す（個人情報・原文は入れない）。
"""

import datetime as dt
import uuid
from collections.abc import Callable

from src.db.events import EventStore
from src.models.dashboard import DecisionEntry, Message, Notification, NotificationKind
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

    def say(self, event_id: str, text: str, card: str | None = None) -> None:
        """幹事の Web のチャットに、KUROKO の進み具合の発言を残す（SPEC 7.5）。

        状態から決まる**固定の文**で、LLM は使わない。個人ごとの回答・口座の情報は入れない。
        """
        self._store.save_message(
            Message(
                message_id=f"m_{uuid.uuid4().hex[:16]}",
                event_id=event_id,
                role="kuroko",
                text=text[:2000],
                card=card,
                created_at=self._now(),
            )
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
        self,
        event: Event,
        *,
        owner_email: str = "",
        snapshot: PolicySnapshot | None = None,
        honorees: list[str] | None = None,
    ) -> Event:
        """規程の写し（以後の計算はこれだけを使う。9.7）と、参加者（株式会社Akakuraの名簿）を用意する。

        Slack ユーザーは `config/slack_users`（登場人物 → Slack ID）から入れる。
        無い人には DM を送れない。
        幹事の `user_id` は名簿の幹事（銀行の口座の対応づけに使う）。
        `honorees` は、幹事が計画のカードで足した主役（名簿の主役は外せない。名簿の主役は口座を
        持たないので、支払う側にしない）。幹事・デモの登場人物は、主役にできない。
        """
        # 規程の文書から読み取って検証した値（呼び出し側が渡す）。無ければ、既定の値（yaml）
        snap = snapshot or self._snapshot()
        added = set(honorees or [])
        people = [_as_honoree(p) if p.user_id in added else p for p in self._roster()]
        slack = self._store.slack_user_map()
        organizer = next((p for p in people if p.role is ParticipantRole.ORGANIZER), None)
        for p in people:
            self._store.save_participant(
                event.event_id,
                p.model_copy(
                    update={"slack_user_id": slack.get(p.user_id), "attendance_confirmed": True}
                ),
            )
        # 実演用は、本物の銀行（sunabar。資金は仮想）で承認する。審査員の体験は、体験用の
        # ボタンで承認する（取引パスワードが要らない。2026-10-15）。
        # `config/demo.experience_bank = bank` で、体験も sunabar にできる（SPEC 7.7）
        experience_web = (
            event.sandbox
            and event.ui_mode != "live"
            and self._store.experience_bank_mode() != "bank"
        )
        return event.model_copy(
            update={
                "bank_approval": "web" if experience_web else "bank",
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
    def after_budget_final(self, event_id: str) -> bool:
        """予約を確定済みにできたら True（呼び出し側が、参加者に開催の案内を送る）。"""
        event = self._store.get_event(event_id)
        esc = event.budget_escalation if event else None
        if event is None or esc is None or esc.final_confirmed_at is None:
            return False
        if event.status is not EventStatus.VENUE or not (event.venue or {}).get("course_price_yen"):
            return False
        self._store.save_event(event.model_copy(update={"status": EventStatus.BOOKED}))
        self.log(event_id, "human", "確認", "承認者が予算超過での続行を承認しました（Slack）")
        self.notify(
            event, NotificationKind.CONFIRM_NEEDED, "予約が確定しました。開催後にお知らせください"
        )
        return True

    # ---- 出欠が出そろったら、店の選択へ ----
    def after_rsvp(self, event_id: str) -> bool:
        """店の選択に進めたら True（呼び出し側が、店の検索を始める。SPEC 7.5）。"""
        event = self._store.get_event(event_id)
        if event is None or event.status is not EventStatus.RSVP:
            return False
        payers = [p for p in self._store.list_participants(event_id) if p.role in PAYERS]
        if not payers or any(p.rsvp_status is RsvpStatus.PENDING for p in payers):
            return False
        attending = sum(1 for p in payers if p.rsvp_status is RsvpStatus.ATTENDING)
        self._store.save_event(
            event.model_copy(update={"status": EventStatus.VENUE, "venue_search": "searching"})
        )
        self.say(
            event_id,
            f"出欠が出そろいました（参加 {attending}名・欠席 {len(payers) - attending}名）。"
            "みなさんの開催希望駅から帰りやすい駅を駅すぱあとで調べて、お店を探しています。"
            "30秒ほどお待ちください。",
        )
        self.log(
            event_id,
            "human",
            "記録",
            f"出欠が出そろいました（参加 {attending}名・欠席 {len(payers) - attending}名）",
        )
        self.notify(
            event, NotificationKind.CONFIRM_NEEDED, "出欠が出そろいました。店を選んでください"
        )
        return True


def _as_honoree(p: Participant) -> Participant:
    """幹事が足した主役。幹事・デモの登場人物（承認者を含む）は、主役にしない。"""
    if p.role is not ParticipantRole.PARTICIPANT or p.demo_persona:
        return p
    return p.model_copy(update={"role": ParticipantRole.GUEST_OF_HONOR})
