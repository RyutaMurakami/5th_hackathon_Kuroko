"""Slack のボタン操作の処理と、DM の送信（kuroko-api の後段。SPEC 7.1・7.2・9.1）。

**署名検証済みの操作だけ**がここに届く（`/tasks/slack/*` は sa-gateway だけ）。そのうえで、
- 押した人の Slack ユーザーが、記録上の本人（参加者・承認者）と一致することを、もう一度確かめる
- 承認は、承認者本人の操作だけ。承認が、請求（Policy Gate 6.2）の起点になる
- 押された操作は、LLM・エージェントを通さない（決定論的なコード）
"""

import json
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
from src.services.cards import close_cards, deliver_card
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

BankApprove = Callable[[str, str], Awaitable[bool]]  # (event_id, user_id) → 承認できたか

# Web のカードから押せる操作（SPEC 7.7）。取り消しは Slack だけ
WEB_ACTIONS = {
    Action.CONSENT, Action.DECLINE, Action.APPROVE, Action.BUDGET, Action.RATE, Action.BANK,
}  # fmt: skip


class CardError(Exception):
    """Web のカードの操作を受け付けられない。message は画面に返すコード。"""



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
        bank_approve: BankApprove | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        # 体験用の「銀行で承認する」（体験用の承認待ちの振込だけに効く。SPEC 7.7）
        self._bank_approve = bank_approve
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
            Action.BANK: self._bank,
        }[i.action]
        await handler(i)

    async def _reply(self, i: SlackInteraction, text: str) -> None:
        if i.response_url:
            await self._slack.respond(i.response_url, text, msg.resolved(text))

    async def _done(
        self, i: SlackInteraction, event_id: str, kind: str, user_id: str, text: str
    ) -> None:
        """操作が成立した。押されたメッセージを結果に置き換え、Web のカードも回答済みにする。"""
        self._close_cards(event_id, kind, user_id, text)
        await self._reply(i, text)

    def _close_cards(self, event_id: str, kind: str, user_id: str, text: str) -> None:
        close_cards(self._store, event_id, kind, user_id, text)

    def _acts_as(self, i: SlackInteraction, event: Event, person: Participant | None) -> bool:
        """この操作を、記録上の本人のものとして扱ってよいか。

        Slack: 署名検証済みの Slack ユーザーが、記録上の本人と一致する。
        Web（SPEC 7.7）: 体験用のイベントを作った本人が、デモの登場人物として押した。
        """
        if person is None:
            return False
        if i.acting_for is not None:
            return (
                event.sandbox
                and person.demo_persona
                and i.acting_for == person.user_id
                and bool(i.web_uid)
                and i.web_uid == event.guest_owner_uid
            )
        return bool(person.slack_user_id) and person.slack_user_id == i.user_id

    async def _deliver(
        self, event: Event, person: Participant, kind: str, text: str, blocks: list[dict]
    ) -> bool:
        """カードを届ける。Slack の DM と、体験用のイベントでは Web のチャット画面にも。"""
        return await deliver_card(
            self._store, self._slack, event, person, kind, text, blocks, self._now()
        )

    # ------------------------------------------------------------------ Web のカード（SPEC 7.7）
    async def press_card(self, event: Event, card_id: str, index: int, web_uid: str) -> None:
        """Web のチャット画面のカードのボタン。値は、保存したカードから取る（画面の値は使わない）。

        呼び出し側（DashboardService）が、イベントの持ち主であることを確かめてから呼ぶ。
        """
        card = self._store.get_card(event.event_id, card_id)
        if not event.sandbox or card is None:
            raise CardError("card_not_found")
        if card.resolved_text is not None:
            raise CardError("card_already_answered")
        buttons = [
            el for b in card.blocks if b.get("type") == "actions" for el in b.get("elements", [])
        ]
        if not 0 <= index < len(buttons):
            raise CardError("invalid_action")
        try:
            action = Action.parse(buttons[index].get("action_id", ""))
            value = json.loads(buttons[index].get("value") or "{}")
        except ValueError:
            raise CardError("invalid_action") from None
        if action not in WEB_ACTIONS or not isinstance(value, dict):
            raise CardError("invalid_action")
        await self.handle(
            SlackInteraction(
                interaction_id=f"web-{card_id}-{index}", action=action, team_id="web",
                user_id="", value=value, acting_for=card.user_id, web_uid=web_uid,
            )
        )  # fmt: skip

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
        if not self._acts_as(i, event, person) or person.role in (
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
            await self._done(i, event.event_id, "consent", person.user_id, "欠席で回答しました。")
            return await self._after_rsvp(event.event_id)
        cap = int(i.value["c"])
        mandate_id = f"{event.event_id}:{person.user_id}"
        if i.acting_for is not None:
            # Slack では、ゲートウェイが payment-api に署名を依頼する。Web では、同じ内容を
            # デモ用の代行の経路で依頼する（署名するのは、どちらも payment-api）
            if self._proxy_sign is None:
                return await self._reply(i, "この操作はできません。")
            await self._proxy_sign(
                "/mandates",
                {
                    "user_id": person.user_id, "event_id": event.event_id,
                    "payee_user_id": i.value["p"], "cap_yen": cap,
                    "expires_at": i.value["x"], "signed_via": DEMO_RUNNER,
                },
                f"web-sign-{event.event_id}-{person.user_id}",
            )  # fmt: skip
        self._store.save_participant(
            event.event_id,
            person.model_copy(
                update={"rsvp_status": RsvpStatus.ATTENDING, "mandate_id": mandate_id}
            ),
        )
        await self._done(
            i, event.event_id, "consent", person.user_id,
            f"参加で回答し、支払いの委任に同意しました（上限 {msg.yen(cap)}・幹事のみ）。"
            "按分の承認のあと、銀行での承認をお願いします。取り消しは App Home からできます。",
        )  # fmt: skip
        await self._after_rsvp(event.event_id)

    async def _after_rsvp(self, event_id: str) -> None:
        """出欠が出そろったら、店の選択へ進め、店の検索を始める（SPEC 7.5）。

        検索は時間がかかる（駅すぱあと・Google Maps で30秒ほど）ので、自分自身へのタスクで行う。
        投入できなくても、出欠は成立している（幹事が、画面の「もう一度探す」から探せる）。
        """
        if not self._life or not self._life.after_rsvp(event_id):
            return
        try:
            await self._enqueue(
                "/tasks/internal/venue-searches", {"event_id": event_id}, f"venues-{event_id}"
            )
        except Exception:
            logger.exception("could not start the venue search: event=%s", event_id)
            event = self._store.get_event(event_id)
            if event is not None:
                self._store.save_event(
                    event.model_copy(
                        update={"venue_search": "failed", "venue_search_error": "failed"}
                    )
                )

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
        # **規程で決まった承認者本人**の操作だけ（署名検証済みの Slack ユーザーで判定する。
        # 体験用のイベントでは、イベントを作った本人が Web のカードから押せる。SPEC 7.7）
        if not self._acts_as(i, event, approver):
            logger.warning("approval rejected: not the approver event=%s", event_id)
            return await self._reply(i, "この按分を承認できるのは、規程で決まった承認者だけです。")
        web = i.acting_for is not None
        approved = Approval(
            event_id=event_id,
            approver_user_id=split.approver_user_id,
            split_hash=split.hash,
            status=ApprovalStatus.APPROVED,
            approved_at=self._now(),
            approved_by_slack_user_id=None if web else i.user_id,
            approved_via="web_demo" if web else "slack",
            approved_by_web_uid=i.web_uid if web else None,
        )
        self._store.save_approval(approved)
        # 承認のあと、**幹事が「振込の依頼を送る」ことを承認してから**、請求を作る
        # （`DashboardService.approve_transfers`。SPEC 7.5）。状態は、そのときまで `approval`
        if self._life:
            where = "Web・体験用" if web else "Slack"
            self._life.log(
                event.event_id, "human", "署名", f"承認者が按分を承認しました（{where}）"
            )
            self._life.notify(
                event, NotificationKind.CONFIRM_NEEDED,
                "按分が承認されました。参加者への振込の依頼を送るか、確認してください",
            )  # fmt: skip
            approver_name = approver.display_name if approver else "承認者"
            self._life.say(
                event_id,
                f"承認者の {approver_name} さんが、按分を承認しました。"
                "参加者に、振込の依頼（各自が銀行で承認するもの）を送ってよいか、"
                "下のカードで確認してください。",
                card="transfer",
            )
        await self._done(
            i, event_id, "approval", split.approver_user_id,
            "按分を承認しました。幹事が振込の依頼を送ることを確認すると、各自の支払いが始まります。",
        )  # fmt: skip

    async def _rate(self, i: SlackInteraction) -> None:
        """振り返りの満足度（1タップ）。記録上の本人だけ。1人1回。"""
        from src.services.retrospective import THANKS

        if self._retro is None:
            return await self._reply(i, "いまは振り返りを受け付けていません。")
        try:
            rating = int(i.value["r"])
        except (KeyError, TypeError, ValueError):
            return await self._reply(i, "この操作はできません。")
        web = i.acting_for is not None
        if web:
            # Web: 体験用のイベントを作った本人が、デモの登場人物として押した（SPEC 7.7）
            found = self._event_and_person(i)
            if found is None or not self._acts_as(i, *found):
                return await self._reply(i, "この操作はできません。")
        result = self._retro.record_rating(
            str(i.value.get("e", "")), str(i.value.get("u", "")), i.user_id, rating, via_web=web
        )
        await self._reply(
            i,
            {
                "recorded": THANKS,
                "duplicate": "すでに回答いただいています。ありがとうございました。",
                "closed": "この振り返りは、すでに締め切りました。",
            }.get(result, "この操作はできません。"),
        )

    # ------------------------------------------------------------------ 銀行での承認（体験用）
    async def send_bank_requests(self, event_id: str, outcomes: dict[str, str]) -> dict[str, Any]:
        """体験用のイベントで、登場人物に「銀行で承認してください」を届ける（SPEC 7.7）。

        本物の銀行（sunabar）で承認するイベントでは、`payment-api` が DM を送るので、何もしない。
        """
        event = self._store.get_event(event_id)
        if event is None or not event.sandbox or event.bank_approval != "web":
            return {"sent": []}
        split = self._store.get_split(event_id)
        shares = {r.user_id: r.share_yen for r in split.rows} if split else {}
        sent = []
        # 再送（Cloud Tasks のやり直し）で、同じ依頼を二重に届けない
        asked = {
            c.user_id
            for c in self._store.list_cards(event_id)
            if c.kind == "bank" and c.resolved_text is None
        }
        for p in self._store.list_participants(event_id):
            if (
                not p.demo_persona
                or outcomes.get(p.user_id) != "awaiting_bank_approval"
                or p.user_id not in shares
                or p.user_id in asked
            ):
                continue
            text, blocks = msg.bank_request(
                event, p, amount_yen=shares[p.user_id], slack_user_id=p.slack_user_id or ""
            )
            await self._deliver(event, p, "bank", text, blocks)
            sent.append(p.user_id)
        return {"sent": sent}

    async def approve_bank(self, event: Event, person: Participant) -> bool:
        """体験用の承認待ちの振込を、承認済みにする。Slack のボタンと Web の画面の両方が通る。

        呼び出し側が、本人（または、体験用のイベントを作った本人）の操作であることを確かめてから呼ぶ。
        支払いを完了にするのは、これまでどおり、明細での確認（payment-api・kuroko-api）。
        """
        if (
            not event.sandbox
            or event.bank_approval != "web"
            or not person.demo_persona
            or self._bank_approve is None
        ):
            return False
        if not await self._bank_approve(event.event_id, person.user_id):
            return False
        self._close_cards(
            event.event_id, "bank", person.user_id,
            "銀行で振込を承認しました（体験用）。入金の確認に進みます。",
        )  # fmt: skip
        if self._life:
            self._life.log(
                event.event_id, "human", "確認",
                f"{person.display_name} が銀行で振込を承認しました（体験用）",
            )  # fmt: skip
        return True

    async def _bank(self, i: SlackInteraction) -> None:
        found = self._event_and_person(i)
        if found is None or not self._acts_as(i, *found):
            return await self._reply(i, "この操作はできません。")
        event, person = found
        if not await self.approve_bank(event, person):
            return await self._reply(
                i, "承認できる振込がありません（すでに承認済みか、体験用の振込ではありません）。"
            )
        await self._reply(i, "銀行で振込を承認しました（体験用）。1〜2分で、入金の確認に進みます。")

    async def _budget(self, i: SlackInteraction) -> None:
        event = self._store.get_event(str(i.value.get("e", "")))
        esc = event.budget_escalation if event else None
        if event is None or esc is None or esc.organizer_confirmed_at is None:
            return await self._reply(i, "確認する内容が見つかりませんでした。")
        approver = next((p for p in self._store.list_participants(event.event_id)
                         if p.user_id == esc.escalated_to), None)  # fmt: skip
        if not self._acts_as(i, event, approver):
            return await self._reply(i, "この確認ができるのは、承認者だけです。")
        assert approver is not None
        if esc.final_confirmed_at is None:
            event.budget_escalation = esc.model_copy(update={"final_confirmed_at": self._now()})
            self._store.save_event(event)
            if self._life and self._life.after_budget_final(event.event_id):
                await self.send_event_notice(event.event_id)
        await self._done(
            i, event.event_id, "budget", approver.user_id, "予算超過での続行を承認しました。"
        )

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

        def on_web(p: Participant) -> bool:  # Web のチャット画面で、人が答える（SPEC 7.7）
            return event.sandbox and p.demo_persona
        for p in people:
            if (
                p.user_id == event.organizer_user_id
                or p.user_id in event.guests_of_honor
                or p.rsvp_status is not RsvpStatus.PENDING
                or (not p.slack_user_id and not can_proxy and not on_web(p))
            ):
                skipped.append(p.user_id)
                continue
            try:
                cap = classify_member(policy, p, event.datetime.date()).consent_cap_yen
            except SplitInputError:
                skipped.append(p.user_id)
                continue
            if not p.slack_user_id and not on_web(p):
                await self._proxy_consent(event, p, organizer, cap, expires)
                proxied.append(p.user_id)
                continue
            text, blocks = msg.consent_request(
                event, p, organizer, cap_yen=cap, expires_at=_aware(expires),
                slack_user_id=p.slack_user_id or "",
            )  # fmt: skip
            await self._deliver(event, p, "consent", text, blocks)
            sent.append(p.user_id)
        if proxied:
            if self._life:
                self._life.log(
                    event_id,
                    "kuroko",
                    "記録",
                    f"デモ用の代行: Slack を使わない {len(proxied)}名の出欠と委任を代行しました",
                )
            await self._after_rsvp(event_id)
        return {"sent": sent, "skipped": skipped, "proxied": proxied}

    async def _proxy_consent(
        self, event: Event, p: Participant, organizer: Participant, cap: int, expires: datetime
    ) -> None:
        """Slack のアカウントを持たない参加者の、出欠（参加）と委任の同意を代行する。

        委任状の署名は、本人の Slack 操作のときと同じく `payment-api` が行う（内容も同じ）。
        """
        assert self._proxy_sign is not None
        expires = _aware(expires)
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

    async def send_event_notice(self, event_id: str) -> dict[str, Any]:
        """予約が確定したら、参加者に開催の案内（日時・店・地図）を届ける（SPEC 7.5）。

        宛先は、出席する人のうち、届けられる人（Slack を使える人と、デモの登場人物）。幹事は除く。
        主役には、費用の話を書かない。やり直しても、同じ人に二重に届けない。
        """
        event = self._store.get_event(event_id)
        if event is None or event.status is not EventStatus.BOOKED:
            return {"sent": []}
        already = {c.user_id for c in self._store.list_cards(event_id) if c.kind == "notice"}
        sent = []
        for p in self._store.list_participants(event_id):
            if (
                p.user_id == event.organizer_user_id
                or p.rsvp_status is RsvpStatus.DECLINING
                or p.user_id in already
            ):
                continue
            text, blocks = msg.event_notice(
                event, guest_of_honor=p.user_id in event.guests_of_honor
            )
            try:
                if await self._deliver(event, p, "notice", text, blocks):
                    sent.append(p.user_id)
            except Exception:  # 1人に届かなくても、ほかの人への案内を止めない
                logger.exception("could not deliver the event notice: event=%s", event_id)
        if self._life and sent:
            self._life.log(
                event_id, "kuroko", "送信", f"{len(sent)}名に開催の案内（日時・店）を送りました"
            )
            self._life.say(
                event_id,
                f"参加者 {len(sent)}名に、開催の案内（日時・お店・地図）をお送りしました。"
                "当日はお楽しみください。開催が終わったら、下の「開催が終わった」を押してください。",
            )
        return {"sent": sent}

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
        # 承認者への依頼は、**幹事が内訳を確かめてから**送る（`send_approval_request`）。
        # 内訳を先に見せて、そのあとに依頼が届く順にする（SPEC 7.5）
        if self._life:
            self._life.log(event_id, "kuroko", "記録", "按分を計算しました。幹事の確認を待ちます")
            self._life.notify(
                event, NotificationKind.CONFIRM_NEEDED,
                "按分を計算しました。内訳を確かめて、承認者に承認を依頼してください",
            )  # fmt: skip
            self._life.say(
                event_id,
                f"按分を計算しました（会計 {msg.yen(split.total_amount_yen)}・"
                f"会社補助 {msg.yen(split.subsidy_yen)}）。内訳は下のとおりです。"
                f"確かめて、規程で決まる承認者の {approver.display_name or '承認者'} さんに"
                "承認を依頼してください。",
                card="split",
            )
        return {"ok": True, "failures": [], "approver": approver.user_id, "hash": split.hash}

    async def send_approval_request(self, event_id: str) -> dict[str, Any]:
        """幹事が内訳を確かめたあと、承認者に按分の承認を依頼する（SPEC 7.5）。

        計算済みの金額表と承認の記録（`pending`）を使う。ここで金額は変わらない。
        やり直しても、同じ承認者に二重に届けない（届いた未回答のカードは置き換わる）。
        """
        event = self._store.get_event(event_id)
        split = self._store.get_split(event_id)
        approval = self._store.get_approval(event_id)
        if (
            event is None or split is None or approval is None
            or approval.status is not ApprovalStatus.PENDING
            or event.status not in (EventStatus.SPLIT, EventStatus.APPROVAL)
        ):  # fmt: skip
            return {"ok": False, "failures": ["no_split_to_approve"]}
        people = {p.user_id: p for p in self._store.list_participants(event_id)}
        approver = people.get(split.approver_user_id)
        if approver is None:
            return {"ok": False, "failures": ["no_approver"]}
        text, blocks = msg.split_approval_request(
            event, split, people, approver_slack_user_id=approver.slack_user_id or ""
        )
        if not await self._deliver(event, approver, "approval", text, blocks):
            return {"ok": False, "failures": ["approver_has_no_slack_user"]}
        if event.status is not EventStatus.APPROVAL:
            event.status = EventStatus.APPROVAL
            self._store.save_event(event)
        if self._life:
            self._life.log(event_id, "kuroko", "送信", "承認者に按分の承認を依頼しました")
            self._life.notify(
                event, NotificationKind.SLACK_WAITING, "承認者の按分の承認を待っています"
            )
            self._life.say(
                event_id,
                f"{approver.display_name or '承認者'} さんに、按分の承認を依頼しました。"
                "承認されたら、お知らせします。",
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
        reachable = approver.slack_user_id or (event.sandbox and approver.demo_persona)
        if not reachable or event.total_amount_yen is None:
            return {"ok": False, "failures": ["approver_has_no_slack_user"]}
        event.budget_escalation = esc.model_copy(
            update={"escalated_to": approver_id, "escalated_at": self._now()}
        )
        self._store.save_event(event)
        text, blocks = msg.budget_request(
            event,
            per_person_yen=-(-event.total_amount_yen // len(attendees)),
            limit_yen=event.policy_snapshot.hard_limit_per_person_yen,
            approver_slack_user_id=approver.slack_user_id or "",
        )
        await self._deliver(event, approver, "budget", text, blocks)
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


def _aware(value: datetime) -> datetime:
    """委任状の期限は、時差つきで渡す（payment-api は、時差の無い期限を受け付けない）。"""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
