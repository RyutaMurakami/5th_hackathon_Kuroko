"""Web のチャット画面（3人ぶん）のカードから、登場人物として HITL の操作をする（SPEC 7.7）。

Slack と同じ処理（`SlackActions`）を通り、体験用（sandbox）のイベントを作った本人だけが押せる。
"""

import datetime as dt

import pytest

from src.db.events import MemoryEventStore
from src.db.mandates import MemoryMandateReader
from src.db.payments import MemoryPaymentReader
from src.models.dashboard import Actor, Role
from src.models.event import EventStatus, Receipt, RsvpStatus
from src.models.slack import Action, SlackInteraction
from src.models.split import ApprovalStatus
from src.services.dashboard import DashboardError, DashboardService
from src.services.lifecycle import Lifecycle
from src.services.policy_gates import Gate, check_before_checkout
from src.services.slack_actions import SlackActions
from tests.test_dashboard import PLAN, Dispatcher, Signer
from tests.test_slack_actions import FakeSlack

NOW = dt.datetime(2026, 10, 10, 12, 0, tzinfo=dt.UTC)
JUDGE = Actor(uid="g1", email="judge@example.com", role=Role.GUEST)
OTHER = Actor(uid="g2", email="other@example.com", role=Role.GUEST)
ORG = Actor(uid="u-org", email="org@example.com", role=Role.ORGANIZER)


class Bank:
    def __init__(self):
        self.approved: list[str] = []

    async def demo_approve(self, transfer_id):
        self.approved.append(transfer_id)
        return True


class World:
    def __init__(self, slack_users=None, live_emails=()):
        self.store, self.slack, self.signed = MemoryEventStore(), FakeSlack(), []
        self.store.slack_users = dict(slack_users or {})
        self.store.live_emails = set(live_emails)
        self.payments, self.bank = MemoryPaymentReader(), Bank()
        life = Lifecycle(store=self.store, now=lambda: NOW)

        async def proxy_sign(path, payload, task_id):
            self.signed.append((path, payload, task_id))

        async def enqueue(path, payload, task_id):
            self.queued.append((path, payload))

        self.queued: list[tuple] = []
        self.actions = SlackActions(
            store=self.store, slack=self.slack, enqueue_self=enqueue,
            mandates=MemoryMandateReader(), lifecycle=life, proxy_sign=proxy_sign,
            now=lambda: NOW,
        )  # fmt: skip

        async def chat(key, text):
            return "了解"

        self.svc = DashboardService(
            store=self.store, chat=chat, signer=Signer(), dispatcher=Dispatcher(),
            lifecycle=life, payments=self.payments, personas=self.actions, bank=self.bank,
            now=lambda: NOW,
        )  # fmt: skip

    async def start(self, actor=JUDGE):
        """依頼 → 計画の確定 → 出欠の依頼（Cloud Tasks の代わりに、その場で送る）。"""
        eid = (await self.svc.send_message(actor, None, "歓送迎会をしたい"))["event_id"]
        await self.svc.confirm_event_plan(actor, eid, PLAN)
        await self.actions.send_consent_requests(eid)
        return eid

    def cards(self, eid, user, actor=JUDGE):
        personas = self.svc.get_event(actor, eid)["personas"]
        return next(p for p in personas if p["user_id"] == user)["cards"]

    def person(self, eid, user):
        return next(p for p in self.store.list_participants(eid) if p.user_id == user)

    async def to_approval(self, eid):
        for user in ("kurao", "hanako"):
            await self.svc.press_persona_card(JUDGE, eid, self.cards(eid, user)[0]["card_id"], 0)
        event = self.store.get_event(eid)
        self.store.save_event(
            event.model_copy(update={"total_amount_yen": 49_500, "status": EventStatus.SPLIT})
        )
        self.store.save_receipt(
            Receipt(event_id=eid, total_amount_yen=49_500, confirmed_by="g1", confirmed_at=NOW)
        )
        out = await self.actions.request_split_approval(eid)
        assert out["ok"], out
        return next(c for c in self.cards(eid, "hanako") if c["kind"] == "approval")


async def test_a_judge_sees_the_same_cards_as_slack_for_the_two_personas_only():
    w = World()
    eid = await w.start()
    personas = w.svc.get_event(JUDGE, eid)["personas"]
    assert [p["user_id"] for p in personas] == ["hanako", "kurao"]  # 列があるのは2人だけ
    card = w.cards(eid, "hanako")[0]
    assert card["kind"] == "consent" and "12,000円" in "".join(card["sections"])  # 部長の上限
    assert [b["label"] for b in card["buttons"]] == ["参加して、委任に同意する", "欠席する"]
    assert "value" not in str(card["buttons"])  # ボタンの値（上限・支払先）は、画面に渡さない
    # ほかの5人は、これまでどおり自動の代行。2人は、人が答えるまで未回答
    assert len(w.signed) == 5 and w.person(eid, "kurao").rsvp_status is RsvpStatus.PENDING
    assert w.slack.dms == []  # Slack の宛先が無ければ、DM は送らない（Web だけで進められる）


async def test_consenting_on_the_web_signs_the_same_mandate_through_the_demo_route():
    w = World()
    eid = await w.start()
    card = w.cards(eid, "kurao")[0]
    out = await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0)
    assert "委任に同意しました" in out["resolved_text"]
    kurao = w.person(eid, "kurao")
    assert kurao.rsvp_status is RsvpStatus.ATTENDING and kurao.mandate_id == f"{eid}:kurao"
    path, payload, _ = w.signed[-1]
    assert path == "/mandates" and payload["user_id"] == "kurao"
    assert payload["cap_yen"] == 6000 and payload["payee_user_id"] == "kanji"  # カードの値のまま
    assert payload["signed_via"] == "demo-runner"
    after = w.cards(eid, "kurao")[0]
    assert after["buttons"] == [] and after["resolved_text"]  # 回答済みの表示に変わる
    with pytest.raises(DashboardError) as e:  # 2回は押せない
        await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0)
    assert e.value.code == "card_already_answered"
    assert w.store.get_event(eid).status is EventStatus.RSVP  # 花子の回答を待つ
    await w.svc.press_persona_card(JUDGE, eid, w.cards(eid, "hanako")[0]["card_id"], 0)
    assert w.store.get_event(eid).status is EventStatus.VENUE


async def test_declining_on_the_web_signs_nothing():
    w = World()
    eid = await w.start()
    before = len(w.signed)
    await w.svc.press_persona_card(JUDGE, eid, w.cards(eid, "kurao")[0]["card_id"], 1)
    assert w.person(eid, "kurao").rsvp_status is RsvpStatus.DECLINING and len(w.signed) == before


async def test_only_the_owner_of_a_sandbox_event_can_press_the_cards():
    w = World()
    eid = await w.start()
    card_id = w.cards(eid, "kurao")[0]["card_id"]
    with pytest.raises(DashboardError) as e:  # 他のゲストには、イベントが「存在しない」
        await w.svc.press_persona_card(OTHER, eid, card_id, 0)
    assert e.value.status == 404
    with pytest.raises(DashboardError):
        await w.svc.approve_bank_transfer(OTHER, eid, "kurao")
    assert w.person(eid, "kurao").rsvp_status is RsvpStatus.PENDING


async def test_cards_are_not_offered_or_accepted_outside_a_sandbox_event():
    w = World(slack_users={"kurao": "U_K", "hanako": "U_H"})
    eid = await w.start(actor=ORG)  # 幹事（許可リスト）のイベントは、体験用ではない
    assert w.svc.get_event(ORG, eid)["personas"] == []
    assert w.store.list_cards(eid) == []  # カードは保存されない（Slack の DM だけ）
    assert len(w.slack.dms) == 2
    with pytest.raises(DashboardError) as e:
        await w.svc.press_persona_card(ORG, eid, "cd_x", 0)
    assert e.value.status == 403
    with pytest.raises(DashboardError) as e:
        await w.svc.approve_bank_transfer(ORG, eid, "kurao")
    assert e.value.status == 403


async def test_slack_and_web_both_work_and_the_first_answer_closes_the_other_card():
    w = World(slack_users={"kurao": "U_K", "hanako": "U_H"})
    eid = await w.start()
    assert {dm[0] for dm in w.slack.dms} == {"U_K", "U_H"}  # Slack にも同じカードが届く
    # くらおは Slack で答える → Web のカードも回答済みになる
    button = w.slack.dms[[dm[0] for dm in w.slack.dms].index("U_K")][2][-1]["elements"][0]
    import json

    await w.actions.handle(
        SlackInteraction(
            interaction_id="s1", action=Action.CONSENT, team_id="T", user_id="U_K",
            value=json.loads(button["value"]),
        )
    )  # fmt: skip
    assert w.cards(eid, "kurao")[0]["resolved_text"]
    # 花子は Web で答える
    await w.svc.press_persona_card(JUDGE, eid, w.cards(eid, "hanako")[0]["card_id"], 0)
    assert w.store.get_event(eid).status is EventStatus.VENUE


async def test_a_forged_web_marker_from_outside_is_not_trusted():
    """Web のカード用の欄は、イベントを作った本人の UID と一致しなければ効かない。"""
    w = World()
    eid = await w.start()
    card = w.store.list_cards(eid)[0]
    import json

    value = json.loads(card.blocks[-1]["elements"][0]["value"])
    await w.actions.handle(
        SlackInteraction(
            interaction_id="x", action=Action.CONSENT, team_id="T", user_id="U_ATTACKER",
            value=value, acting_for=card.user_id, web_uid="someone-else",
        )
    )  # fmt: skip
    assert w.person(eid, card.user_id).rsvp_status is RsvpStatus.PENDING


async def test_the_approver_persona_approves_on_the_web_and_the_gate_accepts_only_that():
    w = World()
    eid = await w.start()
    card = await w.to_approval(eid)
    assert card["buttons"][0]["label"] == "この按分を承認する"
    assert w.cards(eid, "kurao")[-1]["kind"] != "approval"  # 承認依頼は、承認者にだけ届く
    await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0)
    approval = w.store.get_approval(eid)
    assert approval.status is ApprovalStatus.APPROVED and approval.approved_via == "web_demo"
    assert approval.approved_by_web_uid == "g1" and approval.approved_by_slack_user_id is None
    assert w.store.get_event(eid).status is EventStatus.PAYMENT
    assert w.queued[-1] == ("/tasks/internal/checkouts", {"event_id": eid})  # 請求の起点

    def gate(event, approval):
        people = w.store.list_participants(eid)
        return check_before_checkout(
            event, people, w.store.get_split(eid), approval, [], MemoryPaymentReader()
        ).failures

    event = w.store.get_event(eid)
    assert Gate.APPROVER_MISMATCH not in gate(event, approval)
    # 体験用でないイベント・イベントを作った本人でない UID の「Web での承認」は、通さない
    assert Gate.APPROVER_MISMATCH in gate(event.model_copy(update={"sandbox": False}), approval)
    forged = approval.model_copy(update={"approved_by_web_uid": "g2"})
    assert Gate.APPROVER_MISMATCH in gate(event, forged)


async def test_the_bank_button_approves_only_the_personas_held_transfer_in_web_mode():
    w = World()
    eid = await w.start()
    assert w.store.get_event(eid).bank_approval == "web"
    w.payments.payments = [
        {"event_id": eid, "payment_id": "p1", "payer_user_id": "kurao", "amount_yen": 2100,
         "status": "awaiting_bank_approval", "transfer_id": "tr-1", "updated_at": "t"},
    ]  # fmt: skip
    card = w.cards(eid, "kurao")[-1]
    assert card["kind"] == "bank" and card["buttons"][0]["label"] == "銀行で承認する（体験用）"
    assert "tr-1" not in str(w.svc.get_event(JUDGE, eid))  # 振込依頼の ID は、画面に出さない
    await w.svc.approve_bank_transfer(JUDGE, eid, "kurao")
    assert w.bank.approved == ["tr-1"]
    for user in ("sasaki", "hanako"):  # 列の無い人・承認待ちの振込が無い人のぶんは、押せない
        with pytest.raises(DashboardError):
            await w.svc.approve_bank_transfer(JUDGE, eid, user)
    assert w.bank.approved == ["tr-1"]
    w.payments.payments[0]["status"] = "completed"
    done = w.cards(eid, "kurao")[-1]
    assert done["buttons"] == [] and "入金を確認しました" in done["text"]


async def test_a_live_demo_account_uses_the_real_bank_and_gets_no_bank_button():
    w = World(live_emails={"judge@example.com"})
    eid = await w.start()
    assert w.store.get_event(eid).bank_approval == "bank"
    w.payments.payments = [
        {"event_id": eid, "payment_id": "p1", "payer_user_id": "kurao", "amount_yen": 2100,
         "status": "awaiting_bank_approval", "transfer_id": "tr-1", "updated_at": "t"},
    ]  # fmt: skip
    card = w.cards(eid, "kurao")[-1]
    assert card["buttons"] == [] and "sunabar" in card["text"]
    with pytest.raises(DashboardError):
        await w.svc.approve_bank_transfer(JUDGE, eid, "kurao")
    assert w.bank.approved == []
