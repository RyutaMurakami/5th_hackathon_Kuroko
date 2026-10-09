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
    assert sent_to == {"yamada", "sasaki", "ito", "watanabe", "nakamura", "kobayashi", "kato"}
    assert {"takahashi", "matsumoto", "inoue"} <= set(out["skipped"])  # 幹事・主役には送らない
    by_slack = {dm[0]: dm for dm in slack.dms}
    yamada_text = blocks_text(by_slack[SLACK["yamada"]][2])
    assert "12,000円" in yamada_text  # 部長の上限（規程の consent_cap_yen）
    assert "takahashi さんだけ" in yamada_text  # 支払先は幹事だけ（フィクスチャの表示名）
    kato_text = blocks_text(by_slack[SLACK["kato"]][2])
    assert "3,000円" in kato_text  # 入社1年未満の上限（規程の consent_cap_yen）
    # ボタンの値: 押した本人・支払先（幹事）・上限・期限（開催日 + 7日）
    button = by_slack[SLACK["kato"]][2][-1]["elements"][0]
    value = json.loads(button["value"])
    assert value["s"] == SLACK["kato"] and value["p"] == "takahashi" and value["c"] == 3000
    assert value["x"].startswith("2026-11-06T19:00")


async def test_consent_request_is_not_resent_after_an_answer():
    actions, store, slack, *_ = build()
    store.save_participant(
        "ev-demo",
        next(p for p in store.list_participants("ev-demo") if p.user_id == "ito").model_copy(
            update={"rsvp_status": RsvpStatus.ATTENDING}
        ),
    )
    out = await actions.send_consent_requests("ev-demo")
    assert "ito" not in out["sent"] and "ito" in out["skipped"]


# ---------------- 出欠・委任 ----------------
def consent_value(uid="ito", cap=6000, slack=None):
    return {"k": "consent", "e": "ev-demo", "u": uid, "s": slack or SLACK[uid], "p": "takahashi",
            "c": cap, "x": "2026-11-06T19:00:00"}  # fmt: skip


async def test_consent_records_attending_and_replies():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(), SLACK["ito"]))
    ito = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    assert ito.rsvp_status is RsvpStatus.ATTENDING and ito.mandate_id == "ev-demo:ito"
    assert "委任に同意" in slack.responses[0][1] and "6,000円" in slack.responses[0][1]


async def test_decline_records_declining():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.DECLINE, consent_value(), SLACK["ito"]))
    ito = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    assert ito.rsvp_status is RsvpStatus.DECLINING and ito.mandate_id is None


async def test_someone_else_cannot_answer_for_a_participant():
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(), "U_ATTACKER"))
    ito = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    assert ito.rsvp_status is RsvpStatus.PENDING and ito.mandate_id is None


@pytest.mark.parametrize("uid", ["takahashi", "matsumoto"])
async def test_organizer_and_guests_of_honor_cannot_delegate_payment(uid):
    actions, store, slack, *_ = build()
    await actions.handle(press(Action.CONSENT, consent_value(uid), SLACK[uid]))
    person = next(p for p in store.list_participants("ev-demo") if p.user_id == uid)
    assert person.mandate_id is None


async def test_no_answers_after_the_split_has_been_approved():
    actions, store, slack, *_ = build(status=EventStatus.PAYMENT)
    await actions.handle(press(Action.CONSENT, consent_value(), SLACK["ito"]))
    ito = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    assert ito.rsvp_status is RsvpStatus.PENDING


# ---------------- 按分の承認 ----------------
async def requested(total=60_300):
    actions, store, slack, queued, mandates = build(total)
    out = await actions.request_split_approval("ev-demo")
    return actions, store, slack, queued, out


async def test_approval_request_goes_to_the_approver_with_the_split_summary():
    actions, store, slack, queued, out = await requested()
    assert out["ok"] and out["approver"] == "yamada"
    ((slack_id, text, blocks),) = slack.dms
    assert slack_id == SLACK["yamada"]
    body = blocks_text(blocks)
    assert "7,200円" in body and "22.22%" in body and "按分の対象額 30,300円" in body
    assert "承認すると、7名の請求が作られ" in body  # 承認が請求の起点になることを明記
    value = json.loads(blocks[-1]["elements"][0]["value"])
    assert value["h"] == out["hash"] and value["s"] == SLACK["yamada"]
    approval = store.get_approval("ev-demo")
    assert approval.status is ApprovalStatus.PENDING and approval.split_hash == out["hash"]
    assert store.get_event("ev-demo").status.value == "approval"


async def test_approval_request_is_blocked_by_policy_gate_6_1():
    actions, store, slack, queued, mandates = build()
    store.save_receipt(Receipt(event_id="ev-demo", total_amount_yen=60_300))  # 幹事が未確定
    out = await actions.request_split_approval("ev-demo")
    assert not out["ok"] and "total_not_confirmed_by_organizer" in out["failures"]
    assert slack.dms == [] and store.get_split("ev-demo") is None


async def test_only_the_approver_can_approve_and_it_starts_billing():
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["yamada"]}
    # 承認者以外（幹事・別の参加者）は承認できない
    for who in (SLACK["takahashi"], SLACK["sasaki"], "U_ATTACKER"):
        await actions.handle(press(Action.APPROVE, value, who))
    assert store.get_approval("ev-demo").status is ApprovalStatus.PENDING and queued == []
    await actions.handle(press(Action.APPROVE, value, SLACK["yamada"]))
    approval = store.get_approval("ev-demo")
    assert approval.status is ApprovalStatus.APPROVED
    assert approval.approved_by_slack_user_id == SLACK["yamada"] and approval.approved_at == NOW
    # 承認が請求の起点（kuroko-api 自身のタスク）
    assert queued == [
        (
            "/tasks/internal/checkouts",
            {"event_id": "ev-demo"},
            f"checkout-ev-demo-{out['hash'][:16]}",
        )
    ]
    assert store.get_event("ev-demo").status.value == "payment"
    assert "承認しました" in slack.responses[-1][1]


async def test_approving_twice_does_not_queue_billing_twice():
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["yamada"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["yamada"]))
    await actions.handle(press(Action.APPROVE, value, SLACK["yamada"]))
    assert len(queued) == 1 and "すでに承認" in slack.responses[-1][1]


async def test_a_stale_approval_card_cannot_approve_a_recomputed_split():
    actions, store, slack, queued, out = await requested()
    old = {"k": "approve", "e": "ev-demo", "h": "0" * 64, "s": SLACK["yamada"]}
    await actions.handle(press(Action.APPROVE, old, SLACK["yamada"]))
    assert store.get_approval("ev-demo").status is ApprovalStatus.PENDING and queued == []
    assert "更新されました" in slack.responses[-1][1]


async def test_a_rewritten_split_after_approval_stops_at_gate_6_2():
    """承認後に金額表を書き換えても、請求のゲート（6.2）が止める。承認の操作自体は通る。"""
    actions, store, slack, queued, out = await requested()
    value = {"k": "approve", "e": "ev-demo", "h": out["hash"], "s": SLACK["yamada"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["yamada"]))
    from src.db.events import ApprovedSplitIsFinal

    with pytest.raises(ApprovedSplitIsFinal):
        store.save_split(store.get_split("ev-demo"))  # 承認後は、金額表そのものを上書きできない


async def test_approve_without_a_pending_request_is_a_noop():
    actions, store, slack, queued, mandates = build()
    value = {"k": "approve", "e": "ev-demo", "h": "x", "s": SLACK["yamada"]}
    await actions.handle(press(Action.APPROVE, value, SLACK["yamada"]))
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
    assert out == {"ok": True, "failures": [], "approver": "yamada"}
    ((slack_id, _, blocks),) = slack.dms
    assert slack_id == SLACK["yamada"] and "7,010円" in blocks_text(blocks)
    esc = store.get_event("ev-demo").budget_escalation
    assert esc.escalated_to == "yamada" and esc.final_confirmed_at is None
    value = {"k": "budget", "e": "ev-demo", "s": SLACK["yamada"]}
    await actions.handle(press(Action.BUDGET, value, SLACK["sasaki"]))  # 承認者以外
    assert store.get_event("ev-demo").budget_escalation.final_confirmed_at is None
    await actions.handle(press(Action.BUDGET, value, SLACK["yamada"]))
    assert store.get_event("ev-demo").budget_escalation.final_confirmed_at == NOW


# ---------------- App Home ----------------
async def test_home_shows_mandate_status_and_pending_approval():
    actions, store, slack, queued, mandates = build()
    mandates.items["ev-demo:ito"] = MandateInfo("ev-demo:ito", "active", 6000, NOW)
    await actions.refresh_home(SlackHomeOpened(event_id="E1", team_id="T", user_id=SLACK["ito"]))
    home = blocks_text(slack.homes[SLACK["ito"]]["blocks"])
    assert "委任中" in home and "6,000円" in home and "委任を取り消す" in home
    revoke = next(
        b for blk in slack.homes[SLACK["ito"]]["blocks"] if blk.get("type") == "actions"
        for b in blk["elements"]
    )  # fmt: skip
    assert json.loads(revoke["value"]) == {"k": "revoke", "m": "ev-demo:ito", "s": SLACK["ito"]}
    await actions.request_split_approval("ev-demo")
    await actions.refresh_home(SlackHomeOpened(event_id="E2", team_id="T", user_id=SLACK["yamada"]))
    assert "按分の承認待ち" in blocks_text(slack.homes[SLACK["yamada"]]["blocks"])
    await actions.refresh_home(SlackHomeOpened(event_id="E3", team_id="T", user_id="U_NOBODY"))
    assert "関わっている飲み会はありません" in blocks_text(slack.homes["U_NOBODY"]["blocks"])


def test_button_values_stay_under_slack_limit():
    assert len(encode_value(consent_value())) < 400
    with pytest.raises(ValueError):
        encode_value({"x": "a" * 2000})


# ---------------- Slack の制約（Block Kit） ----------------
def _check_limits(blocks):
    assert len(blocks) <= 50
    for b in blocks:
        text = (b.get("text") or {}).get("text", "")
        assert len(text) <= 3000  # section の文字数の上限
        for el in b.get("elements", []):
            if el["type"] == "button":
                assert len(el["text"]["text"]) <= 75 and len(el["value"]) <= 2000
                assert len(el["action_id"]) <= 255
        assert len(b.get("elements", [])) <= 25


async def test_every_card_respects_slack_block_kit_limits():
    actions, store, slack, queued, mandates = build()
    await actions.send_consent_requests("ev-demo")
    await actions.request_split_approval("ev-demo")
    event = store.get_event("ev-demo")
    event.budget_escalation = BudgetEscalation(organizer_confirmed_at=NOW)
    store.save_event(event)
    await actions.request_budget_confirmation("ev-demo")
    assert len(slack.dms) == 7 + 1 + 1
    for _, text, blocks in slack.dms:
        assert text and len(text) <= 3000
        _check_limits(blocks)
    mandates.items["ev-demo:ito"] = MandateInfo("ev-demo:ito", "active", 6000, NOW)
    await actions.refresh_home(SlackHomeOpened(event_id="E", team_id="T", user_id=SLACK["ito"]))
    _check_limits(slack.homes[SLACK["ito"]]["blocks"])
