"""Policy Gate 6.1（按分確定前）と 6.2（請求を出す前）。SPEC 6章・ARCHITECTURE 4.2。

決定論的なコードだけで判定する（LLM・エージェントは関与しない）。**1つでも満たさなければ次に進まない**。
不合格の理由は、止めた項目をすべて集めて返す（判断ログに残すため。最初の1つで止めない）。

- 6.4: 記憶（Memory Bank）に書き込んでよいか（`save_memory` の手前）
- 6.1: 按分に進んでよいか（`calculate_split` の手前）
- 6.2: 請求（Checkout）を作ってよいか（請求の手前）。6.3（支払いエージェント側）は `payment_api/` が
  別に検査する（請求側を信用しすぎない）
"""

from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import Protocol

from src.db.events import EventStore
from src.models.event import Event, Participant, Receipt
from src.models.feedback import MemoryFact, Retrospective, RetroStatus
from src.models.policy import PolicySnapshot
from src.models.split import Approval, ApprovalStatus, SplitResult
from src.services.approver import determine_approver
from src.services.members import SplitInputError, classify_member
from src.services.split import calculate_split


class Gate(StrEnum):
    # 6.1 按分確定前
    POLICY_SNAPSHOT_MISSING = "policy_snapshot_missing"
    ATTENDEES_NOT_CONFIRMED = "attendees_not_confirmed"
    MEMBER_CLASS_UNRESOLVED = "member_class_unresolved"
    EMPLOYMENT_TYPE_MISSING = "employment_type_missing"
    TOTAL_NOT_CONFIRMED = "total_not_confirmed_by_organizer"
    OVER_LIMIT_NOT_APPROVED = "over_hard_limit_not_approved"
    # 6.2 請求を出す前
    SPLIT_MISSING = "split_missing"
    APPROVAL_MISSING = "approval_missing"
    APPROVER_MISMATCH = "approver_mismatch"
    SPLIT_HASH_MISMATCH = "split_hash_mismatch"
    SPLIT_TAMPERED = "split_tampered"
    TOTAL_MISMATCH = "checkout_total_mismatch"
    PAYEE_NOT_ORGANIZER = "payee_not_organizer"
    ORGANIZER_OR_GUEST_CHARGED = "organizer_or_guest_charged"
    CHECKOUT_NOT_IN_SPLIT = "checkout_not_in_split"
    INVALID_AMOUNT = "invalid_amount"
    DUPLICATE_PAYMENT = "duplicate_payment"
    # 6.4 記憶を保存する前
    RETRO_NOT_READY = "retro_not_awaiting_organizer"
    NOT_THE_ORGANIZER = "not_the_organizer"
    FACT_NOT_FROM_TEMPLATE = "fact_not_from_template"
    BREAKDOWN_WITH_FEW_RESPONSES = "breakdown_with_few_responses"
    MEMORY_ALREADY_SAVED = "memory_already_saved"


@dataclass(frozen=True)
class GateResult:
    failures: list[Gate] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class CheckoutLine:
    """これから請求する1件（B13 の `create_checkout` が作る。ゲートは作り手を信用しない）。"""

    payer_user_id: str
    payee_user_id: str
    amount_yen: int
    split_hash: str


class PaymentLookup(Protocol):
    def has_completed_payment(self, event_id: str, payer_user_id: str) -> bool:
        """同じ参加者への、完了済みの支払いがあるか（`payment-api` が書く Payment を読む）。"""


def check_before_split(
    event: Event,
    participants: list[Participant],
    receipt: Receipt | None,
) -> GateResult:
    """6.1 按分確定前。"""
    failures: list[Gate] = []
    policy = event.policy_snapshot
    if policy is None:
        failures.append(Gate.POLICY_SNAPSHOT_MISSING)

    attendees = [p for p in participants if p.attendance_confirmed]
    ids = {p.user_id for p in attendees}
    guests = set(event.guests_of_honor)
    if (
        not attendees
        or len(ids) != len(attendees)
        or event.organizer_user_id not in ids
        or not guests <= ids
    ):
        failures.append(Gate.ATTENDEES_NOT_CONFIRMED)

    if any(not p.employment_type.strip() for p in attendees):
        failures.append(Gate.EMPLOYMENT_TYPE_MISSING)
    if policy is not None:
        try:
            for p in attendees:
                classify_member(policy, p, event.datetime.date())
        except SplitInputError:
            failures.append(Gate.MEMBER_CLASS_UNRESOLVED)

    # 会計金額は、領収書の金額を、この幹事（Web の UID が一致する人）が確定したものだけ
    total = event.total_amount_yen
    confirmed = (
        receipt is not None
        and bool(event.organizer_web_uid)
        and receipt.confirmed_by == event.organizer_web_uid
        and receipt.confirmed_at is not None
        and total is not None
        and receipt.total_amount_yen == total
    )
    if not confirmed:
        failures.append(Gate.TOTAL_NOT_CONFIRMED)

    # 1人あたりの会計単価（出席者全員で割る）が上限以内。超えるなら 9.1 の確認が両方そろっている
    if confirmed and policy is not None and attendees and total is not None:
        over = Fraction(total, len(attendees)) > policy.hard_limit_per_person_yen
        if over and not _escalation_approved(event, attendees, policy):
            failures.append(Gate.OVER_LIMIT_NOT_APPROVED)
    return GateResult(failures)


def _escalation_approved(
    event: Event, attendees: list[Participant], policy: PolicySnapshot
) -> bool:
    """予算超過の確認（幹事 → 承認者）が両方済んでいて、承認者が今の按分の承認者と同じ。"""
    approval = event.budget_escalation
    if approval is None or approval.organizer_confirmed_at is None:
        return False
    if approval.final_confirmed_at is None or approval.escalated_to is None:
        return False
    try:
        current = determine_approver(
            attendees,
            policy,
            event_date=event.datetime.date(),
            guests_of_honor=event.guests_of_honor,
        )
    except SplitInputError:
        return False
    return approval.escalated_to == current  # 出席者が変わって承認者が変わったら、やり直す


def check_before_checkout(
    event: Event,
    participants: list[Participant],
    split: SplitResult | None,
    approval: Approval | None,
    lines: list[CheckoutLine],
    payments: PaymentLookup,
) -> GateResult:
    """6.2 請求を出す前。"""
    failures: list[Gate] = []

    if split is None:
        failures.append(Gate.SPLIT_MISSING)
    if (
        approval is None
        or approval.status != ApprovalStatus.APPROVED
        or approval.approved_at is None
    ):
        failures.append(Gate.APPROVAL_MISSING)
    elif split is not None:
        # 承認したのが、規程で決まった承認者本人（署名検証済みの Slack 操作から取った ID）
        approver = next((p for p in participants if p.user_id == split.approver_user_id), None)
        slack_id = approval.approved_by_slack_user_id
        if approval.approved_via == "web_demo":
            # 体験用のイベントで、イベントを作った本人が、Web のカードから承認者として押した
            # （SPEC 7.7）。体験用でないイベントでは、この経路の承認を認めない
            by_approver = (
                event.sandbox
                and approver is not None
                and approver.demo_persona
                and bool(approval.approved_by_web_uid)
                and approval.approved_by_web_uid == event.guest_owner_uid
            )
        else:
            by_approver = (
                approver is not None
                and bool(approver.slack_user_id)
                and bool(slack_id)
                and slack_id == approver.slack_user_id
            )
        if not by_approver or approval.approver_user_id != split.approver_user_id:
            failures.append(Gate.APPROVER_MISMATCH)
        # 承認された金額表と、いま保存されている金額表が同じ
        if approval.split_hash != split.hash:
            failures.append(Gate.SPLIT_HASH_MISMATCH)

    # 保存された金額表が、入力から計算し直した結果と**中身まで**一致する（書き換えられていない）。
    # ハッシュの欄だけの比較では、負担額を書き換えてもハッシュを残されたら検出できない
    if split is not None and event.policy_snapshot is not None:
        try:
            recomputed = calculate_split(event, participants, event.policy_snapshot)
        except SplitInputError:
            failures.append(Gate.SPLIT_TAMPERED)
        else:
            if recomputed.model_dump() != split.model_dump():
                failures.append(Gate.SPLIT_TAMPERED)

    guests = set(event.guests_of_honor)
    if any(line.payee_user_id != event.organizer_user_id for line in lines):
        failures.append(Gate.PAYEE_NOT_ORGANIZER)
    if any(
        line.payer_user_id == event.organizer_user_id or line.payer_user_id in guests
        for line in lines
    ):
        failures.append(Gate.ORGANIZER_OR_GUEST_CHARGED)
    if any(line.amount_yen <= 0 for line in lines):
        failures.append(Gate.INVALID_AMOUNT)
    if len({line.payer_user_id for line in lines}) != len(lines):
        failures.append(Gate.CHECKOUT_NOT_IN_SPLIT)  # 同じ人に2件

    if split is not None:
        rows = {r.user_id: r.share_yen for r in split.rows}
        for line in lines:
            if line.split_hash != split.hash or rows.get(line.payer_user_id) != line.amount_yen:
                failures.append(Gate.CHECKOUT_NOT_IN_SPLIT)
                break
        # 請求額の合計 = 会計金額 − 会社補助 − 幹事本人の負担額
        organizer_share = rows.get(event.organizer_user_id, 0)
        expected = split.total_amount_yen - split.subsidy_yen - organizer_share
        if sum(line.amount_yen for line in lines) != expected:
            failures.append(Gate.TOTAL_MISMATCH)

    if any(payments.has_completed_payment(event.event_id, line.payer_user_id) for line in lines):
        failures.append(Gate.DUPLICATE_PAYMENT)
    return GateResult(_dedupe(failures))


def _dedupe(failures: list[Gate]) -> list[Gate]:
    return list(dict.fromkeys(failures))


def load_and_check_before_split(store: EventStore, event_id: str) -> GateResult:
    """保存済みのデータで 6.1 を検査する（呼び出し側は、結果が ok のときだけ按分に進む）。"""
    event = store.get_event(event_id)
    if event is None:
        return GateResult([Gate.POLICY_SNAPSHOT_MISSING])
    return check_before_split(event, store.list_participants(event_id), store.get_receipt(event_id))


MIN_RESPONSES_FOR_BREAKDOWN = 3


def check_before_memory(
    event: Event, retro: Retrospective | None, web_uid: str, facts: list[MemoryFact]
) -> GateResult:
    """Policy Gate 6.4（記憶を保存する前）。書き込むのは、幹事が確認した、定型の事実だけ。"""
    from src.services.memory_facts import has_breakdown, is_template_fact

    failures: list[Gate] = []
    if retro is None or retro.status is not RetroStatus.AWAITING_ORGANIZER:
        failures.append(Gate.RETRO_NOT_READY)
    # 確認したのは、このイベントの幹事本人（Web の認証の UID）
    if not web_uid or web_uid != event.organizer_web_uid:
        failures.append(Gate.NOT_THE_ORGANIZER)
    # 定型のテンプレートの形の文だけ（LLM が書いた文・編集した文は、ここで落ちる）
    if any(not is_template_fact(f.text) for f in facts):
        failures.append(Gate.FACT_NOT_FROM_TEMPLATE)
    few = retro is None or retro.response_count < MIN_RESPONSES_FOR_BREAKDOWN
    if few and any(has_breakdown(f.text) for f in facts):
        failures.append(Gate.BREAKDOWN_WITH_FEW_RESPONSES)
    if retro is not None and (retro.saved_at is not None or retro.memory_refs):
        failures.append(Gate.MEMORY_ALREADY_SAVED)
    return GateResult(failures)
