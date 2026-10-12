"""Slack のボタン操作の処理と、DM の送信（kuroko-api の後段。SPEC 7.1・7.2・9.1）。

**署名検証済みの操作だけ**がここに届く（`/tasks/slack/*` は sa-gateway だけ）。そのうえで、
- 押した人の Slack ユーザーが、記録上の本人（参加者・承認者）と一致することを、もう一度確かめる
- 承認は、承認者本人の操作だけ。承認が、請求（Policy Gate 6.2）の起点になる
- 押された操作は、LLM・エージェントを通さない（決定論的なコード）
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.db.events import ApprovedSplitIsFinal, EventStore
from src.db.mandates import MandateReader
from src.models.dashboard import NotificationKind
from src.models.event import Event, EventStatus, Participant, ParticipantRole, RsvpStatus
from src.models.slack import Action, SlackHomeOpened, SlackInteraction
from src.models.split import Approval, ApprovalStatus
from src.services import slack_messages as msg
from src.services.approver import determine_approver
from src.services.members import SplitInputError, classify_member
from src.services.policy_gates import load_and_check_before_split
from src.services.slack_port import SlackPort
from src.services.split import calculate_split

if TYPE_CHECKING:
    from src.services.lifecycle import Lifecycle
    from src.services.retrospective import Retrospectives

logger = logging.getLogger(__name__)

FINISHED = {"approval", "payment", "completed", "retro", "closed"}
DEMO_RUNNER = "demo-runner"  # 代行で署名した委任状の `signed_via`（SPEC 7.6）


Enqueue = Callable[[str, dict, str], Awaitable[None]]  # (path, payload, task_id)


class SlackActions:
    def __init__(
        self,
        *,
        store: EventStore,
        slack: SlackPort,
        enqueue_self: Enqueue,
        mandates: MandateReader,
        retro: "Retrospectives | None" = None,
        lifecycle: "Lifecycle | None" = None,
        proxy_sign: Enqueue | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        # デモ用の代行（SPEC 7.6）: Slack のアカウントを持たない参加者の、委任状の署名の依頼先
        self._proxy_sign = proxy_sign
        self._retro = retro
        self._life = lifecycle
        self._store, self._slack, self._enqueue = store, slack, enqueue_self
        self._mandates, self._now = mandates, now

    # ------------------------------------------------------------------ ボタン操作
    async def handle(self, i: SlackInteraction) -> None:
        handler = {
            Action.CONSENT: self._rsvp,
            Action.DECLINE: self._rsvp,
            Action.REVOKE: self._revoke,
            Action.APPROVE: self._approve,
            Action.BUDGET: self._budget,
            Action.RATE: self._rate,
        }[i.action]
        await handler(i)

    async def _reply(self, i: SlackInteraction, text: str) -> None:
        if i.response_url:
            await self._slack.respond(i.response_url, text, msg.resolved(text))

    def _event_and_person(self, i: SlackInteraction) -> tuple[Event, Participant] | None:
        event = self._store.get_event(str(i.value.get("e", "")))
        if event is None:
            return None
        uid = str(i.value.get("u", ""))
        person = next((p for p in self._store.list_participants(event.event_id)
                       if p.user_id == uid), None)  # fmt: skip
        return (event, person) if person else None

    async def _rsvp(self, i: SlackInteraction) -> None:
        found = self._event_and_person(i)
        if found is None:
            return await self._reply(i, "この飲み会の情報が見つかりませんでした。")
        event, person = found
        # 記録上の本人でなければ受け付けない（ゲートウェイの確認に加えて、記録でも確かめる）
        if person.slack_user_id != i.user_id or person.role in (
            ParticipantRole.ORGANIZER, ParticipantRole.GUEST_OF_HONOR,
        ):  # fmt: skip
            logger.warning("rsvp rejected: event=%s", event.event_id)
            return await self._reply(i, "この操作はできません。")
        if event.status.value in FINISHED:
            return await self._reply(i, "この飲み会は、すでに按分の手続きに進んでいます。")
        if i.action is Action.DECLINE:
            self._store.save_participant(
                event.event_id, person.model_copy(update={"rsvp_status": RsvpStatus.DECLINING})
            )
            await self._reply(i, "欠席で回答しました。")
            return self._after_rsvp(event.event_id)
        cap = int(i.value["c"])
        mandate_id = f"{event.event_id}:{person.user_id}"
        self._store.save_participant(
            event.event_id,
            person.model_copy(
                update={"rsvp_status": RsvpStatus.ATTENDING, "mandate_id": mandate_id}
            ),
        )
        await self._reply(
            i,
            f"参加で回答し、支払いの委任に同意しました（上限 {msg.yen(cap)}・幹事のみ）。"
            "按分の承認のあと、銀行での承認をお願いします。取り消しは App Home からできます。",
        )
        self._after_rsvp(event.event_id)

    def _after_rsvp(self, event_id: str) -> None:
        if self._life:
            self._life.after_rsvp(event_id)  # 出欠が出そろったら、店の選択へ進める

    async def _revoke(self, i: SlackInteraction) -> None:
        # 取り消しの本体は、ゲートウェイが payment-api に直接投入済み。ここは表示を更新するだけ
        await self._reply(
            i,
            "委任の取り消しを受け付けました。振込の依頼が作られる前なら、この委任は無効になります。",
        )

    async def _approve(self, i: SlackInteraction) -> None:
        event_id = str(i.value.get("e", ""))
        event = self._store.get_event(event_id)
        split = self._store.get_split(event_id)
        approval = self._store.get_approval(event_id)
        if event is None or split is None or approval is None:
            return await self._reply(i, "承認する按分案が見つかりませんでした。")
        if approval.status == ApprovalStatus.APPROVED:
            return await self._reply(i, "この按分は、すでに承認されています。")
        # 古いカード（金額表が作り直された）は承認できない
        if i.value.get("h") != split.hash or approval.split_hash != split.hash:
            return await self._reply(
                i, "この按分案は更新されました。新しい承認依頼をご確認ください。"
            )
        approver = next((p for p in self._store.list_participants(event_id)
                         if p.user_id == split.approver_user_id), None)  # fmt: skip
        # **規程で決まった承認者本人**の操作だけ（署名検証済みの Slack ユーザーで判定する）
        if approver is None or not approver.slack_user_id or approver.slack_user_id != i.user_id:
            logger.warning("approval rejected: not the approver event=%s", event_id)
            return await self._reply(i, "この按分を承認できるのは、規程で決まった承認者だけです。")
        approved = Approval(
            event_id=event_id,
            approver_user_id=split.approver_user_id,
            split_hash=split.hash,
            status=ApprovalStatus.APPROVED,
            approved_at=self._now(),
            approved_by_slack_user_id=i.user_id,
        )
        self._store.save_approval(approved)
        event.status = EventStatus.PAYMENT
        self._store.save_event(event)
        if self._life:
            self._life.log(event.event_id, "human", "署名", "承認者が按分を承認しました（Slack）")
            self._life.notify(
                event, NotificationKind.SLACK_WAITING, "参加者の銀行での承認を待っています"
            )
        # 承認を起点に、Policy Gate 6.2 を通った請求だけが作られる（kuroko-api 自身のタスク）
        await self._enqueue(
            "/tasks/internal/checkouts",
            {"event_id": event_id},
            f"checkout-{event_id}-{split.hash[:16]}",
        )
        await self._reply(i, "按分を承認しました。請求を作成し、各自の支払いを開始します。")

    async def _rate(self, i: SlackInteraction) -> None:
        """振り返りの満足度（1タップ）。記録上の本人だけ。1人1回。"""
        from src.services.retrospective import THANKS

        if self._retro is None:
            return await self._reply(i, "いまは振り返りを受け付けていません。")
        try:
            rating = int(i.value["r"])
        except (KeyError, TypeError, ValueError):
            return await self._reply(i, "この操作はできません。")
        result = self._retro.record_rating(
            str(i.value.get("e", "")), str(i.value.get("u", "")), i.user_id, rating
        )
        await self._reply(
            i,
            {
                "recorded": THANKS,
                "duplicate": "すでに回答いただいています。ありがとうございました。",
                "closed": "この振り返りは、すでに締め切りました。",
            }.get(result, "この操作はできません。"),
        )

    async def _budget(self, i: SlackInteraction) -> None:
        event = self._store.get_event(str(i.value.get("e", "")))
        esc = event.budget_escalation if event else None
        if event is None or esc is None or esc.organizer_confirmed_at is None:
            return await self._reply(i, "確認する内容が見つかりませんでした。")
        approver = next((p for p in self._store.list_participants(event.event_id)
                         if p.user_id == esc.escalated_to), None)  # fmt: skip
        if approver is None or not approver.slack_user_id or approver.slack_user_id != i.user_id:
            return await self._reply(i, "この確認ができるのは、承認者だけです。")
        if esc.final_confirmed_at is None:
            event.budget_escalation = esc.model_copy(update={"final_confirmed_at": self._now()})
            self._store.save_event(event)
            if self._life:
                self._life.after_budget_final(event.event_id)
        await self._reply(i, "予算超過での続行を承認しました。")

    # ------------------------------------------------------------------ 依頼の送信
    async def send_consent_requests(self, event_id: str) -> dict[str, Any]:
        event = self._store.get_event(event_id)
        if event is None or event.policy_snapshot is None:
            return {"sent": [], "skipped": ["event_or_policy_missing"]}
        policy = event.policy_snapshot
        people = self._store.list_participants(event_id)
        organizer = next((p for p in people if p.user_id == event.organizer_user_id), None)
        if organizer is None:
            return {"sent": [], "skipped": ["organizer_missing"]}
        expires = event.datetime + timedelta(days=policy.mandate_valid_days_after_event)
        sent, skipped, proxied = [], [], []
        # 代行は sandbox のイベントで、Slack のアカウントを持たない人だけ（SPEC 7.6）
        can_proxy = event.sandbox and self._proxy_sign is not None
        for p in people:
            if (
                p.user_id == event.organizer_user_id
                or p.user_id in event.guests_of_honor
                or p.rsvp_status is not RsvpStatus.PENDING
                or (not p.slack_user_id and not can_proxy)
            ):
                skipped.append(p.user_id)
                continue
            try:
                cap = classify_member(policy, p, event.datetime.date()).consent_cap_yen
            except SplitInputError:
                skipped.append(p.user_id)
                continue
            if not p.slack_user_id:
                await self._proxy_consent(event, p, organizer, cap, expires)
                proxied.append(p.user_id)
                continue
            text, blocks = msg.consent_request(
                event, p, organizer, cap_yen=cap, expires_at=expires, slack_user_id=p.slack_user_id
            )
            await self._slack.post_dm(p.slack_user_id, text, blocks)
            sent.append(p.user_id)
        if proxied:
            if self._life:
                self._life.log(
                    event_id,
                    "kuroko",
                    "記録",
                    f"デモ用の代行: Slack を使わない {len(proxied)}名の出欠と委任を代行しました",
                )
            self._after_rsvp(event_id)
        return {"sent": sent, "skipped": skipped, "proxied": proxied}

    async def _proxy_consent(
        self, event: Event, p: Participant, organizer: Participant, cap: int, expires: datetime
    ) -> None:
        """Slack のアカウントを持たない参加者の、出欠（参加）と委任の同意を代行する。

        委任状の署名は、本人の Slack 操作のときと同じく `payment-api` が行う（内容も同じ）。
        """
        assert self._proxy_sign is not None
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        await self._proxy_sign(
            "/mandates",
            {
                "user_id": p.user_id,
                "event_id": event.event_id,
                "payee_user_id": organizer.user_id,
                "cap_yen": cap,
                "expires_at": expires.isoformat(),
                "signed_via": DEMO_RUNNER,
            },
            f"demo-sign-{event.event_id}-{p.user_id}",
        )
        self._store.save_participant(
            event.event_id,
            p.model_copy(
                update={
                    "rsvp_status": RsvpStatus.ATTENDING,
                    "mandate_id": f"{event.event_id}:{p.user_id}",
                }
            ),
        )

    async def request_split_approval(self, event_id: str) -> dict[str, Any]:
        """Policy Gate 6.1 を通ったら按分を計算し、承認者に承認依頼を送る。"""
        gate = load_and_check_before_split(self._store, event_id)
        if not gate.ok:
            if self._life:
                self._life.log(event_id, "kuroko", "ブロック", "按分の前の検査で止まりました")
            return {"ok": False, "failures": [f.value for f in gate.failures]}
        event = self._store.get_event(event_id)
        people = self._store.list_participants(event_id)
        assert event is not None and event.policy_snapshot is not None
        try:
            split = calculate_split(event, people, event.policy_snapshot)
            self._store.save_split(split)
        except ApprovedSplitIsFinal:
            return {"ok": False, "failures": ["already_approved"]}
        except SplitInputError as e:
            return {"ok": False, "failures": [str(e)]}
        self._store.save_approval(
            Approval(
                event_id=event_id, approver_user_id=split.approver_user_id, split_hash=split.hash
            )  # fmt: skip
        )
        by_id = {p.user_id: p for p in people}
        approver = by_id[split.approver_user_id]
        if not approver.slack_user_id:
            return {"ok": False, "failures": ["approver_has_no_slack_user"]}
        text, blocks = msg.split_approval_request(
            event, split, by_id, approver_slack_user_id=approver.slack_user_id
        )
        await self._slack.post_dm(approver.slack_user_id, text, blocks)
        event.status = EventStatus.APPROVAL
        self._store.save_event(event)
        if self._life:
            self._life.log(
                event_id, "kuroko", "送信", "按分を計算し、承認者に承認を依頼しました（Slack）"
            )
            self._life.notify(
                event, NotificationKind.SLACK_WAITING, "承認者の按分の承認を Slack で待っています"
            )
        return {"ok": True, "failures": [], "approver": approver.user_id, "hash": split.hash}

    async def request_budget_confirmation(self, event_id: str) -> dict[str, Any]:
        """幹事が続行を確認したあと、承認者に最終確認を求める（SPEC 9.1。仮の承認者）。"""
        event = self._store.get_event(event_id)
        if event is None or event.policy_snapshot is None:
            return {"ok": False, "failures": ["event_or_policy_missing"]}
        esc = event.budget_escalation
        if esc is None or esc.organizer_confirmed_at is None:
            return {"ok": False, "failures": ["organizer_not_confirmed"]}
        people = self._store.list_participants(event_id)
        attendees = [p for p in people if p.attendance_confirmed]
        try:
            approver_id = determine_approver(
                attendees, event.policy_snapshot, event_date=event.datetime.date(),
                guests_of_honor=event.guests_of_honor,
            )  # fmt: skip
        except SplitInputError:
            return {"ok": False, "failures": ["no_approver"]}
        approver = next(p for p in people if p.user_id == approver_id)
        if not approver.slack_user_id or event.total_amount_yen is None:
            return {"ok": False, "failures": ["approver_has_no_slack_user"]}
        event.budget_escalation = esc.model_copy(
            update={"escalated_to": approver_id, "escalated_at": self._now()}
        )
        self._store.save_event(event)
        text, blocks = msg.budget_request(
            event,
            per_person_yen=-(-event.total_amount_yen // len(attendees)),
            limit_yen=event.policy_snapshot.hard_limit_per_person_yen,
            approver_slack_user_id=approver.slack_user_id,
        )
        await self._slack.post_dm(approver.slack_user_id, text, blocks)
        return {"ok": True, "failures": [], "approver": approver_id}

    # ------------------------------------------------------------------ App Home
    async def refresh_home(self, opened: SlackHomeOpened) -> None:
        items: list[dict[str, Any]] = []
        for event, me in self._store.find_by_slack_user(opened.user_id):
            lines = [f"日時: {_jst_label(event)}"]
            buttons = []
            mandate = self._mandates.get(f"{event.event_id}:{me.user_id}")
            if mandate is not None:
                label = {"active": "委任中", "used": "支払い済み", "revoked": "取り消し済み",
                         "expired": "期限切れ"}.get(mandate.status, mandate.status)  # fmt: skip
                lines.append(f"委任: {label}（上限 {msg.yen(mandate.cap_yen)}・幹事のみ）")
                if mandate.status == "active":
                    buttons.append(
                        (
                            "委任を取り消す",
                            Action.REVOKE,
                            {"k": "revoke", "m": mandate.mandate_id, "s": opened.user_id},
                            "danger",
                        )
                    )
            elif me.rsvp_status is RsvpStatus.DECLINING:
                lines.append("出欠: 欠席")
            split = self._store.get_split(event.event_id)
            approval = self._store.get_approval(event.event_id)
            if split and approval and split.approver_user_id == me.user_id:
                if approval.status is ApprovalStatus.PENDING:
                    lines.append("*按分の承認待ちです*（DM のカードから承認してください）")
                else:
                    lines.append("按分: 承認済み")
            items.append({"title": event.title or "飲み会", "lines": lines, "buttons": buttons})
        await self._slack.publish_home(opened.user_id, msg.home_view(items))


def _jst_label(event: Event) -> str:
    return f"{event.datetime.month}/{event.datetime.day} {event.datetime:%H:%M}"
