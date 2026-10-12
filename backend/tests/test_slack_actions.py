"""Slack のボタン操作の処理（出欠・委任・按分の承認・予算超過の確認）と、DM の送信。"""

import datetime as dt
import json

import pytest

from src.db.events import MemoryEventStore
from src.db.mandates import MandateInfo, MemoryMandateReader
from src.models.event import EventStatus, Receipt, RsvpStatus
from src.models.slack import Action, SlackHomeOpened, SlackInteraction, encode_value
from src.models.split import ApprovalStatus, BudgetEscalation
from src.services.policy import load_snapshot
from src.services.slack_actions import SlackActions
from tests.sample_company import demo_event, demo_participants

POLICY = load_snapshot()
NOW = dt.datetime(2026, 10, 31, 12, 0, tzinfo=dt.UTC)
SLACK = {p.user_id: f"U_{p.user_id.upper()}" for p in demo_participants()}


class FakeSlack:
    def __init__(self):
        self.dms: list[tuple[str, str, list]] = []
        self.responses: list[tuple[str, str]] = []
        self.homes: dict[str, dict] = {}

    async def post_dm(self, slack_user_id, text, blocks):
        self.dms.append((slack_user_id, text, blocks))

    async def respond(self, response_url, text, blocks):
        self.responses.append((response_url, text))

    async def publish_home(self, slack_user_id, view):
        self.homes[slack_user_id] = view


def build(total=60_300, **event_kw):
    store, slack, queued = MemoryEventStore(), FakeSlack(), []
    event = demo_event(total).model_copy(
        update={"policy_snapshot": POLICY, "organizer_web_uid": "uid", "title": "歓送迎会"}
        | event_kw
    )
    store.save_event(event)
    for p in demo_participants():
        store.save_participant(
            event.event_id, p.model_copy(update={"slack_user_id": SLACK[p.user_id]})
        )
    store.save_receipt(
        Receipt(
            event_id=event.event_id, total_amount_yen=total, confirmed_by="uid", confirmed_at=NOW
        )
    )

    async def enqueue(path, payload, task_id):
        queued.append((path, payload, task_id))

    mandates = MemoryMandateReader()
    actions = SlackActions(
        store=store, slack=slack, enqueue_self=enqueue, mandates=mandates, now=lambda: NOW
    )
    return actions, store, slack, queued, mandates


def press(action: Action, value: dict, user: str, url="https://hooks.slack.test/r"):
    return SlackInteraction(
        interaction_id="i1", action=action, team_id="T1", user_id=user,
        response_url=url, value=value,
    )  # fmt: skip


def blocks_text(blocks) -> str:
    return json.dumps(blocks, ensure_ascii=False)


# ---------------- 同意依頼の送信 ----------------
async def test_consent_requests_go_to_payers_only_with_class_caps():
    actions, store, slack, *_ = build()
    out = await actions.send_consent_requests("ev-demo")
    sent_to = {uid for uid in out["sent"]}
    assert sent_to == {"hanako", "sasaki", "kurao", "watanabe", "nakamura", "kobayashi", "kato"}
    assert {"kanji", "matsumoto", "inoue"} <= set(out["skipped"])  # 幹事・主役には送らない
    by_slack = {dm[0]: dm for dm in slack.dms}
    yamada_text = blocks_text(by_slack[SLACK["hanako"]][2])
    assert "12,000円" in yamada_text  # 部長の上限（規程の consent_cap_yen）
    assert "支払先: 幹事だけ" in yamada_text  # 支払先は幹事だけ
    kato_text = blocks_text(by_slack[SLACK["kato"]][2])
    assert "3,000円" in kato_text  # 入社1年未満の上限（規程の consent_cap_yen）
    # ボタンの値: 押した本人・支払先（幹事）・上限・期限（開催日 + 7日）
    button = by_slack[SLACK["kato"]][2][-1]["elements"][0]
    value = json.loads(button["value"])
    assert value["s"] == SLACK["kato"] and value["p"] == "kanji" and value["c"] == 3000
    assert value["x"].startswith("2026-11-06T19:00")


async def test_consent_request_is_not_resent_after_an_answer():
    actions, store, slack, *_ = build()
    store.save_participant(
        "ev-demo",
        next(p for p in store.list_participants("ev-demo") if p.user_id == "kurao").model_copy(
            update={"rsvp_status": RsvpStatus.ATTENDING}
        ),
    )
    out = await actions.send_consent_requests("ev-demo")
    assert "kurao" not in out["sent"] and "kurao" in out["skipped"]


# ---------------- デモ用の代行（SPEC 7.6） ----------------
ON_SLACK = {"hanako", "kurao"}  # Slack に実在する2人。ほかの人はアカウントを持たない


def build_demo(sandbox=True, with_proxy=True):
    from src.services.lifecycle import Lifecycle

    actions, store, slack, queued, mandates = build(sandbox=sandbox)
    for p in store.list_participants("ev-demo"):
        if p.user_id not in ON_SLACK:
            store.save_participant("ev-demo", p.model_copy(update={"slack_user_id": None}))
    store.save_event(store.get_event("ev-demo").model_copy(update={"status": EventStatus.RSVP}))
    signed: list[tuple] = []

    async def proxy_sign(path, payload, task_id):
        signed.append((path, payload, task_id))

    actions._proxy_sign = proxy_sign if with_proxy else None
    actions._life = Lifecycle(store=store, now=lambda: NOW)
    return actions, store, slack, signed


async def test_people_without_slack_are_answered_by_the_demo_runner_and_get_no_message():
    actions, store, slack, signed = build_demo()
    out = await actions.send_consent_requests("ev-demo")
    assert set(out["sent"]) == ON_SLACK  # DM が届くのは、Slack に実在する2人だけ
    assert {dm[0] for dm in slack.dms} == {SLACK["hanako"], SLACK["kurao"]}
    assert set(out["proxied"]) == {"sasaki", "watanabe", "nakamura", "kobayashi", "kato"}
    people = {p.user_id: p for p in store.list_participants("ev-demo")}
    assert people["kato"].rsvp_status is RsvpStatus.ATTENDING
    assert people["kato"].mandate_id == "ev-demo:kato"
    # 委任状の中身は、本人が Slack で同意するときと同じ（上限は規程の区分・支払先は幹事だけ）
    by_user = {payload["user_id"]: (path, payload, tid) for path, payload, tid in signed}
    path, payload, tid = by_user["kato"]
    assert path == "/mandates" and tid == "demo-sign-ev-demo-kato"
    assert payload["cap_yen"] == 3000 and payload["payee_user_id"] == "kanji"
    assert payload["signed_via"] == "demo-runner" and payload["expires_at"].startswith("2026-11-06")
    assert by_user["sasaki"][1]["cap_yen"] == 9000
    # 幹事・主役・Slack の2人のぶんは代行しない
    assert not set(by_user) & {"kanji", "matsumoto", "inoue", "hanako", "kurao"}
    assert people["hanako"].rsvp_status is RsvpStatus.PENDING
    assert any("デモ用の代行" in d.summary for d in store.list_decisions("ev-demo"))
    assert store.get_event("ev-demo").status is EventStatus.RSVP  # 2人の回答を待つ


async def test_the_event_moves_on_once_the_two_people_on_slack_answer():
    actions, store, slack, signed = build_demo()
    await actions.send_consent_requests("ev-demo")
    await actions.handle(press(Action.CONSENT, consent_value("hanako", 12000), SLACK["hanako"]))
    assert store.get_event("ev-demo").status is EventStatus.RSVP
    await actions.handle(press(Action.CONSENT, consent_value("kurao"), SLACK["kurao"]))
    assert store.get_event("ev-demo").status is EventStatus.VENUE


async def test_the_demo_runner_answers_nobody_twice():
    actions, store, slack, signed = build_demo()
    await actions.send_consent_requests("ev-demo")
    again = await actions.send_consent_requests("ev-demo")
    assert again["proxied"] == [] and len(signed) == 5


async def test_nothing_is_proxied_outside_a_sandbox_event_or_without_the_demo_identity():
    for kw in ({"sandbox": False}, {"with_proxy": False}):
        actions, store, slack, signed = build_demo(**kw)
        out = await actions.send_consent_requests("ev-demo")
        assert out["proxied"] == [] and signed == []
        assert "kato" in out["skipped"]
        people = {p.user_id: p for p in store.list_participants("ev-demo")}
        assert people["kato"].rsvp_status is RsvpStatus.PENDING
        assert people["kato"].mandate_id is None


# ---------------- 出欠・委任 ----------------
def consent_value(uid="kurao", cap=6000, slack=None):
    return {"k": "consent", "e": "ev-demo", "u": uid, "s": slack or SLACK[uid], "p": "kanji",
            "c": cap, "x": "2026-11-06T19:00:00"}  # fmt: skip


async def test_consent_records_attending_and_replies():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(), SLACK["kurao"]))
    kurao = next(p for p in store.list_participants("ev-demo") if p.user_id == "kurao")
    assert kurao.rsvp_status is RsvpStatus.ATTENDING and kurao.mandate_id == "ev-demo:kurao"
    assert "委任に同意" in slack.responses[0][1] and "6,000円" in slack.responses[0][1]


async def test_decline_records_declining():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.DECLINE, consent_value(), SLACK["kurao"]))
    kurao = next(p for p in store.list_participants("ev-demo") if p.user_id == "kurao")
    assert kurao.rsvp_status is RsvpStatus.DECLINING and kurao.mandate_id is None


async def test_someone_else_cannot_answer_for_a_participant():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(), "U_ATTACKER"))
    kurao = next(p for p in store.list_participants("ev-demo") if p.user_id == "kurao")
    assert kurao.rsvp_status is RsvpStatus.PENDING and kurao.mandate_id is None


@pytest.mark.parametrize("uid", ["kanji", "matsumoto"])
async def test_organizer_and_guests_of_honor_cannot_delegate_payment(uid):
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(uid), SLACK[uid]))
    person = next(p for p in store.list_participants("ev-demo") if p.user_id == uid)
    assert person.mandate_id is None


async def test_no_answers_after_the_split_has_been_approved():
    actions, store, slack, *_ = build(status=EventStatus.PAYMENT)
    await actions.handle(press(Action.CONSENT, consent_value(), SLACK["kurao"]))
    kurao = next(p for p in store.list_participants("ev-demo") if p.user_id == "kurao")
    assert kurao.rsvp_status is RsvpStatus.PENDING


# ---------------- 按分の承認 ----------------
async def requested(total=60_300):
    """按分を計算し、幹事が内訳を確かめて、承認者に承認を依頼したところまで（SPEC 7.5）。"""
    actions, store, slack, queued, mandates = build(total, status=EventStatus.SPLIT)
    out = await actions.request_split_approval("ev-demo")
    assert slack.dms == [] and store.get_event("ev-demo").status.value == "split"  # 内訳が先
    sent = await actions.send_approval_request("ev-demo")
    assert sent["ok"]
    return actions, store, slack, queued, out


async def test_approval_request_goes_to_the_approver_with_the_split_summary():
    actions, store, slack, queued, out = await requested()
    assert out["ok"] and out["approver"] == "hanako"
    ((slack_id, text, blocks),) = slack.dms
    assert slack_id == SLACK["hanako"]
    body = blocks_text(blocks)
    assert "7,200円" in body and "22.22%" in body and "按分の対象額 30,300円" in body
    assert "承認すると、7名の請求が作られ" in body  # 承認が請求の起点になることを明記
    value = json.loads(blocks[-1]["elements"][0]["value"])
    assert value["h"] == out["hash"] and value["s"] == SLACK["hanako"]
    approval = store.get_approval("ev-demo")
    assert approval.status is ApprovalStatus.PENDING and approval.split_hash == out["hash"]
    assert store.get_event("ev-demo").status.value == "approval"


async def test_approval_request_is_blocked_by_policy_gate_6_1():
    actions, store, slack, queued, mandates = build()
    store.save_receipt(Receipt(event_id="ev-demo", total_amount_yen=60_300))  # 幹事が未確定
    out = await actions.request_split_approval("ev-demo")
    assert not out["ok"] and "total_not_confirmed_by_organizer" in out["failures"]
    assert slack.dms == [] and store.get_split("ev-demo") is None


async def test_only_the_approver_can_approve_and_billing_waits_for_the_organizer():
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["hanako"]}
    # 承認者以外（幹事・別の参加者）は承認できない
    for who in (SLACK["kanji"], SLACK["sasaki"], "U_ATTACKER"):
        await actions.handle(press(Action.APPROVE, value, who))
    assert store.get_approval("ev-demo").status is ApprovalStatus.PENDING and queued == []
    await actions.handle(press(Action.APPROVE, value, SLACK["hanako"]))
    approval = store.get_approval("ev-demo")
    assert approval.status is ApprovalStatus.APPROVED
    assert approval.approved_by_slack_user_id == SLACK["hanako"] and approval.approved_at == NOW
    # 承認だけでは請求は始まらない。幹事が振込の依頼を送ることを承認してから（SPEC 7.5）
    assert queued == []
    assert store.get_event("ev-demo").status.value == "approval"
    assert "承認しました" in slack.responses[-1][1]


async def test_approving_twice_does_not_queue_billing_twice():
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["hanako"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["hanako"]))
    await actions.handle(press(Action.APPROVE, value, SLACK["hanako"]))
    assert "すでに承認" in slack.responses[-1][1] and queued == []


async def test_a_stale_approval_card_cannot_approve_a_recomputed_split():
    actions, store, slack, queued, out = await requested()
    old = {"k": "approve", "e": "ev-demo", "h": "0" * 64, "s": SLACK["hanako"]}
    await actions.handle(press(Action.APPROVE, old, SLACK["hanako"]))
    assert store.get_approval("ev-demo").status is ApprovalStatus.PENDING and queued == []
    assert "更新されました" in slack.responses[-1][1]


async def test_a_rewritten_split_after_approval_stops_at_gate_6_2():
    """承認後に金額表を書き換えても、請求のゲート（6.2）が止める。承認の操作自体は通る。"""
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["hanako"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["hanako"]))
    from src.db.events import ApprovedSplitIsFinal

    with pytest.raises(ApprovedSplitIsFinal):
        store.save_split(store.get_split("ev-demo"))  # 承認後は、金額表そのものを上書きできない


async def test_approve_without_a_pending_request_is_a_noop():
    actions, store, slack, queued, mandates = build()
    value = {"k": "approve", "e": "ev-demo", "h": "x", "s": SLACK["hanako"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["hanako"]))
    assert queued == [] and "見つかりません" in slack.responses[-1][1]


# ---------------- 予算超過 ----------------
async def test_budget_confirmation_flow():
    over = 70_100  # 10名で 7,010円 > 7,000円
    actions, store, slack, queued, mandates = build(over)
    event = store.get_event("ev-demo")
    # 幹事の確認が済む前は、承認者には送らない
    assert (await actions.request_budget_confirmation("ev-demo"))["failures"] == [
        "organizer_not_confirmed"
    ]
    event.budget_escalation = BudgetEscalation(organizer_confirmed_at=NOW)
    store.save_event(event)
    out = await actions.request_budget_confirmation("ev-demo")
    assert out == {"ok": True, "failures": [], "approver": "hanako"}
    ((slack_id, _, blocks),) = slack.dms
    assert slack_id == SLACK["hanako"] and "7,010円" in blocks_text(blocks)
    esc = store.get_event("ev-demo").budget_escalation
    assert esc.escalated_to == "hanako" and esc.final_confirmed_at is None
    value = {"k": "budget", "e": "ev-demo", "s": SLACK["hanako"]}
    await actions.handle(press(Action.BUDGET, value, SLACK["sasaki"]))  # 承認者以外
    assert store.get_event("ev-demo").budget_escalation.final_confirmed_at is None
    await actions.handle(press(Action.BUDGET, value, SLACK["hanako"]))
    assert store.get_event("ev-demo").budget_escalation.final_confirmed_at == NOW


# ---------------- App Home ----------------
async def test_home_shows_mandate_status_and_pending_approval():
    actions, store, slack, queued, mandates = build()
    mandates.items["ev-demo:kurao"] = MandateInfo("ev-demo:kurao", "active", 6000, NOW)
    await actions.refresh_home(SlackHomeOpened(event_id="E1", team_id="T", user_id=SLACK["kurao"]))
    home = blocks_text(slack.homes[SLACK["kurao"]]["blocks"])
    assert "委任中" in home and "6,000円" in home and "委任を取り消す" in home
    revoke = next(
        b for blk in slack.homes[SLACK["kurao"]]["blocks"] if blk.get("type") == "actions"
        for b in blk["elements"]
    )  # fmt: skip
    assert json.loads(revoke["value"]) == {"k": "revoke", "m": "ev-demo:kurao", "s": SLACK["kurao"]}
    await actions.request_split_approval("ev-demo")
    await actions.refresh_home(SlackHomeOpened(event_id="E2", team_id="T", user_id=SLACK["hanako"]))
    assert "按分の承認待ち" in blocks_text(slack.homes[SLACK["hanako"]]["blocks"])
    await actions.refresh_home(SlackHomeOpened(event_id="E3", team_id="T", user_id="U_NOBODY"))
    assert "関わっている飲み会はありません" in blocks_text(slack.homes["U_NOBODY"]["blocks"])


def test_button_values_stay_under_slack_limit():
    assert len(encode_value(consent_value())) < 400
    with pytest.raises(ValueError):
        encode_value({"x": "a" * 2000})


# ---------------- Slack の制約（Block Kit） ----------------
def _check_limits(blocks):
    assert len(blocks) <= 50
    all_ids = [
        el["action_id"] for b in blocks for el in b.get("elements", []) if "action_id" in el
    ]
    assert len(all_ids) == len(set(all_ids))
    for b in blocks:
        text = (b.get("text") or {}).get("text", "")
        assert len(text) <= 3000  # section の文字数の上限
        for el in b.get("elements", []):
            if el["type"] == "button":
                assert len(el["text"]["text"]) <= 75 and len(el["value"]) <= 2000
                assert len(el["action_id"]) <= 255
        # Slack は、1通のメッセージの中の action_id の重複を認めない（`invalid_blocks`）
        ids = [el["action_id"] for el in b.get("elements", []) if "action_id" in el]
        assert len(ids) == len(set(ids))
        assert len(b.get("elements", [])) <= 25


async def test_every_card_respects_slack_block_kit_limits():
    actions, store, slack, queued, mandates = build(status=EventStatus.SPLIT)
    await actions.send_consent_requests("ev-demo")
    await actions.request_split_approval("ev-demo")
    await actions.send_approval_request("ev-demo")
    event = store.get_event("ev-demo")
    event.budget_escalation = BudgetEscalation(organizer_confirmed_at=NOW)
    store.save_event(event)
    await actions.request_budget_confirmation("ev-demo")
    assert len(slack.dms) == 7 + 1 + 1
    for _, text, blocks in slack.dms:
        assert text and len(text) <= 3000
        _check_limits(blocks)
    mandates.items["ev-demo:kurao"] = MandateInfo("ev-demo:kurao", "active", 6000, NOW)
    await actions.refresh_home(SlackHomeOpened(event_id="E", team_id="T", user_id=SLACK["kurao"]))
    _check_limits(slack.homes[SLACK["kurao"]]["blocks"])
