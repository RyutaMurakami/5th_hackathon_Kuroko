"""Policy Gate 6.1・6.2（SPEC 6章）。通る場合と、項目ごとに止まる場合を確かめる。"""

import datetime as dt

import pytest

from src.models.event import Event, Receipt
from src.models.split import Approval, ApprovalStatus, BudgetEscalation
from src.services.policy import load_snapshot
from src.services.policy_gates import (
    CheckoutLine,
    Gate,
    check_before_checkout,
    check_before_split,
)
from src.services.split import calculate_split
from tests.sample_company import demo_event, demo_participants

POLICY = load_snapshot()
WEB_UID = "firebase-uid-kanji"
NOW = dt.datetime(2026, 10, 31, 12, 0, tzinfo=dt.UTC)


def event(total=60_300, **kw) -> Event:
    return demo_event(total).model_copy(
        update={"policy_snapshot": POLICY, "organizer_web_uid": WEB_UID} | kw
    )


def receipt(total=60_300, **kw) -> Receipt:
    fields = {"confirmed_by": WEB_UID, "confirmed_at": NOW} | kw
    return Receipt(event_id="ev-demo", total_amount_yen=total, **fields)


def people():
    ps = demo_participants()
    # 承認者（山田）の Slack ユーザー
    return [p.model_copy(update={"slack_user_id": f"U_{p.user_id.upper()}"}) for p in ps]


# ---------------- 6.1 ----------------
def test_6_1_passes_for_the_demo_event():
    assert check_before_split(event(), people(), receipt()).ok


def test_6_1_requires_a_policy_snapshot():
    r = check_before_split(event(policy_snapshot=None), people(), receipt())
    assert Gate.POLICY_SNAPSHOT_MISSING in r.failures


@pytest.mark.parametrize(
    "mutate",
    [
        lambda ps: [],  # 出席者がいない
        lambda ps: [p for p in ps if p.user_id != "kanji"],  # 幹事が出席していない
        lambda ps: [p for p in ps if p.user_id != "matsumoto"],  # 主役が出席していない
        lambda ps: ps + [ps[0]],  # 同じ人が2回
    ],
)
def test_6_1_requires_confirmed_attendees(mutate):
    r = check_before_split(event(), mutate(people()), receipt())
    assert Gate.ATTENDEES_NOT_CONFIRMED in r.failures


def test_6_1_requires_an_employment_type_and_a_resolvable_class():
    ps = people()
    ps[3] = ps[3].model_copy(update={"employment_type": " "})
    assert Gate.EMPLOYMENT_TYPE_MISSING in check_before_split(event(), ps, receipt()).failures
    ps = people()
    ps[3] = ps[3].model_copy(update={"job_title": "常務"})
    assert Gate.MEMBER_CLASS_UNRESOLVED in check_before_split(event(), ps, receipt()).failures


@pytest.mark.parametrize(
    "rec",
    [
        None,  # 領収書がない
        receipt(confirmed_by=None, confirmed_at=None),  # 未確定
        receipt(confirmed_by="someone-else"),  # 幹事以外が確定
        receipt(60_000),  # 確定した金額と Event の金額が違う
    ],
)
def test_6_1_requires_the_total_confirmed_by_the_organizer(rec):
    r = check_before_split(event(), people(), rec)
    assert Gate.TOTAL_NOT_CONFIRMED in r.failures


def test_6_1_total_without_an_organizer_web_uid_is_never_confirmed():
    r = check_before_split(event(organizer_web_uid=""), people(), receipt(confirmed_by=""))
    assert Gate.TOTAL_NOT_CONFIRMED in r.failures


def test_6_1_unit_price_over_the_hard_limit_needs_both_confirmations():
    over = 70_100  # 10名で 7,010円 > 7,000円
    ev, rc = event(over), receipt(over)
    assert Gate.OVER_LIMIT_NOT_APPROVED in check_before_split(ev, people(), rc).failures

    only_organizer = BudgetEscalation(organizer_confirmed_at=NOW, escalated_to="hanako")
    ev1 = ev.model_copy(update={"budget_escalation": only_organizer})
    assert Gate.OVER_LIMIT_NOT_APPROVED in check_before_split(ev1, people(), rc).failures

    both = only_organizer.model_copy(update={"escalated_at": NOW, "final_confirmed_at": NOW})
    ev2 = ev.model_copy(update={"budget_escalation": both})
    assert check_before_split(ev2, people(), rc).ok

    # 最終確認を求めた相手が、いまの承認者と違う（出席者が変わった）ならやり直し
    wrong = both.model_copy(update={"escalated_to": "sasaki"})
    ev3 = ev.model_copy(update={"budget_escalation": wrong})
    assert Gate.OVER_LIMIT_NOT_APPROVED in check_before_split(ev3, people(), rc).failures


def test_6_1_exactly_at_the_limit_passes_without_escalation():
    at_limit = 70_000  # 10名でちょうど 7,000円
    assert check_before_split(event(at_limit), people(), receipt(at_limit)).ok


def test_6_1_collects_every_failure_not_only_the_first():
    r = check_before_split(event(policy_snapshot=None), [], None)
    assert {
        Gate.POLICY_SNAPSHOT_MISSING,
        Gate.ATTENDEES_NOT_CONFIRMED,
        Gate.TOTAL_NOT_CONFIRMED,
    } <= set(r.failures)


# ---------------- 6.2 ----------------
class Payments:
    def __init__(self, completed=()):
        self.completed = set(completed)

    def has_completed_payment(self, event_id, payer_user_id):
        return payer_user_id in self.completed


def fixture():
    ev, ps = event(), people()
    split = calculate_split(ev, ps, POLICY)
    approval = Approval(
        event_id="ev-demo",
        approver_user_id=split.approver_user_id,
        split_hash=split.hash,
        status=ApprovalStatus.APPROVED,
        approved_at=NOW,
        approved_by_slack_user_id="U_HANAKO",
    )
    lines = [
        CheckoutLine(r.user_id, "kanji", r.share_yen, split.hash)
        for r in split.rows
        if r.share_yen > 0 and r.user_id != "kanji"
    ]
    return ev, ps, split, approval, lines


def gate(ev, ps, split, approval, lines, payments=None):
    return check_before_checkout(ev, ps, split, approval, lines, payments or Payments())


def test_6_2_passes_for_the_demo_event():
    r = gate(*fixture())
    assert r.ok, r.failures
    ev, ps, split, approval, lines = fixture()
    assert len(lines) == 7 and sum(line.amount_yen for line in lines) == 27_000


def test_6_2_requires_an_approval():
    ev, ps, split, approval, lines = fixture()
    assert Gate.APPROVAL_MISSING in gate(ev, ps, split, None, lines).failures
    pending = approval.model_copy(update={"status": ApprovalStatus.PENDING})
    assert Gate.APPROVAL_MISSING in gate(ev, ps, split, pending, lines).failures
    no_time = approval.model_copy(update={"approved_at": None})
    assert Gate.APPROVAL_MISSING in gate(ev, ps, split, no_time, lines).failures


def test_6_2_the_approver_must_be_the_person_the_policy_chose():
    ev, ps, split, approval, lines = fixture()
    for who in ("U_SASAKI", "U_KANJI", None, ""):
        bad = approval.model_copy(update={"approved_by_slack_user_id": who})
        assert Gate.APPROVER_MISMATCH in gate(ev, ps, split, bad, lines).failures
    # 承認者の Slack ユーザーが未登録なら、誰が承認しても本人と確認できない
    ps2 = [p.model_copy(update={"slack_user_id": None}) if p.user_id == "hanako" else p for p in ps]
    assert Gate.APPROVER_MISMATCH in gate(ev, ps2, split, approval, lines).failures
    # 承認の記録の承認者が、按分の承認者と違う
    other = approval.model_copy(update={"approver_user_id": "sasaki"})
    assert Gate.APPROVER_MISMATCH in gate(ev, ps, split, other, lines).failures


def test_6_2_the_approved_hash_must_match_the_split_and_the_checkout():
    ev, ps, split, approval, lines = fixture()
    stale = approval.model_copy(update={"split_hash": "0" * 64})
    assert Gate.SPLIT_HASH_MISMATCH in gate(ev, ps, split, stale, lines).failures
    wrong_hash_lines = [
        CheckoutLine(x.payer_user_id, x.payee_user_id, x.amount_yen, "bad") for x in lines
    ]
    assert Gate.CHECKOUT_NOT_IN_SPLIT in gate(ev, ps, split, approval, wrong_hash_lines).failures


def test_6_2_a_split_edited_after_approval_is_detected_by_recomputing():
    ev, ps, split, approval, lines = fixture()
    # 金額表のデータだけを書き換えた（ハッシュも合わせた）場合でも、計算し直した結果と違えば止める
    tampered_rows = [
        r.model_copy(update={"share_yen": r.share_yen - 100}) if r.user_id == "kurao" else r
        for r in split.rows
    ]
    tampered = split.model_copy(update={"rows": tampered_rows, "hash": "f" * 64})
    ok_approval = approval.model_copy(update={"split_hash": "f" * 64})
    assert Gate.SPLIT_TAMPERED in gate(ev, ps, tampered, ok_approval, lines).failures
    # 出席者が変わって、計算し直すと別の金額表になる場合も止める
    ps2 = [p for p in ps if p.user_id != "kobayashi"]
    assert Gate.SPLIT_TAMPERED in gate(ev, ps2, split, approval, lines).failures


def test_6_2_moving_money_between_rows_while_keeping_the_hash_is_detected():
    """合計も承認のハッシュも変えずに、伊藤の100円を渡辺に付け替える改ざん。"""
    ev, ps, split, approval, lines = fixture()
    rows = [
        r.model_copy(
            update={"share_yen": r.share_yen + 100 * (1 if r.user_id == "watanabe" else -1)}
        )
        if r.user_id in {"kurao", "watanabe"}
        else r
        for r in split.rows
    ]
    tampered = split.model_copy(update={"rows": rows})  # hash は元のまま
    assert tampered.hash == split.hash
    moved = [
        CheckoutLine(
            x.payer_user_id,
            x.payee_user_id,
            x.amount_yen
            + (100 if x.payer_user_id == "watanabe" else -100 if x.payer_user_id == "kurao" else 0),
            x.split_hash,
        )
        for x in lines
    ]
    r = gate(ev, ps, tampered, approval, moved)
    assert Gate.SPLIT_TAMPERED in r.failures
    assert Gate.TOTAL_MISMATCH not in r.failures  # 合計は変わらない。合計の検査だけでは通ってしまう


def test_6_2_the_payee_is_always_the_organizer():
    ev, ps, split, approval, lines = fixture()
    redirected = [
        CheckoutLine(x.payer_user_id, "attacker", x.amount_yen, x.split_hash) for x in lines
    ]
    assert Gate.PAYEE_NOT_ORGANIZER in gate(ev, ps, split, approval, redirected).failures
    one = lines[:1] + [
        CheckoutLine(x.payer_user_id, "hanako", x.amount_yen, x.split_hash) for x in lines[1:2]
    ]
    assert Gate.PAYEE_NOT_ORGANIZER in gate(ev, ps, split, approval, one).failures


@pytest.mark.parametrize("payer", ["kanji", "matsumoto", "inoue"])
def test_6_2_never_charges_the_organizer_or_guests_of_honor(payer):
    ev, ps, split, approval, lines = fixture()
    extra = lines + [CheckoutLine(payer, "kanji", 100, split.hash)]
    assert Gate.ORGANIZER_OR_GUEST_CHARGED in gate(ev, ps, split, approval, extra).failures


def test_6_2_the_total_and_each_amount_must_match_the_split():
    ev, ps, split, approval, lines = fixture()
    short = lines[:-1]  # 1人ぶん請求し忘れ
    assert Gate.TOTAL_MISMATCH in gate(ev, ps, split, approval, short).failures
    over = [
        CheckoutLine(x.payer_user_id, x.payee_user_id, x.amount_yen + 100, x.split_hash)
        if x.payer_user_id == "kurao"
        else x
        for x in lines
    ]
    r = gate(ev, ps, split, approval, over)
    assert Gate.CHECKOUT_NOT_IN_SPLIT in r.failures and Gate.TOTAL_MISMATCH in r.failures
    stranger = lines + [CheckoutLine("stranger", "kanji", 100, split.hash)]
    assert Gate.CHECKOUT_NOT_IN_SPLIT in gate(ev, ps, split, approval, stranger).failures
    twice = lines + lines[:1]
    assert Gate.CHECKOUT_NOT_IN_SPLIT in gate(ev, ps, split, approval, twice).failures


def test_6_2_rejects_non_positive_amounts():
    ev, ps, split, approval, lines = fixture()
    zero = [CheckoutLine(x.payer_user_id, x.payee_user_id, 0, x.split_hash) for x in lines]
    assert Gate.INVALID_AMOUNT in gate(ev, ps, split, approval, zero).failures


def test_6_2_stops_when_a_payment_for_the_same_person_is_already_completed():
    ev, ps, split, approval, lines = fixture()
    r = gate(ev, ps, split, approval, lines, Payments(completed={"nakamura"}))
    assert r.failures == [Gate.DUPLICATE_PAYMENT]


def test_6_2_without_a_split_nothing_passes():
    ev, ps, split, approval, lines = fixture()
    assert Gate.SPLIT_MISSING in gate(ev, ps, None, approval, lines).failures
    assert not gate(ev, ps, None, None, []).ok


def test_gate_results_have_no_duplicates():
    ev, ps, split, approval, lines = fixture()
    r = gate(ev, ps, split, None, lines + lines)
    assert len(r.failures) == len(set(r.failures))
