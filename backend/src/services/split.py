"""按分計算 `calculate_split`（SPEC 4.1・9.3。**LLM を呼ばない・決定論的**）。

- 会社補助 = 補助対象の人数 × 1人あたりの額（上限・会計金額を超えない）
- 按分の対象額 = 会計金額 − 会社補助
- 主役は0円。主役を除く全員（会社補助の対象外の人を含む）の係数で按分する
- 各人の負担割合（％）= 係数 ÷ 係数の合計。**負担額 = 按分の対象額 × 負担割合** を、
  分数で正確に計算し、規程の単位（100円）で切り捨てる
- 切り捨ての不足分は承認者が負担する（`shortfall_to: approver`）
同じ入力は、人の並びに関わらず、同じ結果・同じハッシュになる。
"""

import hashlib
import json
from fractions import Fraction

from src.models.event import Event, Participant
from src.models.policy import PolicySnapshot
from src.models.split import SplitResult, SplitRow
from src.services.approver import determine_approver
from src.services.members import SplitInputError, classify_member


def subsidy_yen(
    policy: PolicySnapshot, attendees: list[Participant], guests: set[str], total_amount_yen: int
) -> int:
    s = policy.subsidy
    eligible = [
        p
        for p in attendees
        if p.employment_type in s.eligible_employment_types
        and (s.include_guests_of_honor or p.user_id not in guests)
    ]
    return min(s.per_attendee_yen * len(eligible), s.max_per_event_yen, total_amount_yen)


def _ratio_percent(weight: Fraction, weight_sum: Fraction) -> float:
    """負担割合（％）。小数第2位まで（四捨五入）。表示用。"""
    return float(round(weight / weight_sum * 100, 2))


def split_hash(result_core: dict) -> str:
    raw = json.dumps(result_core, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def calculate_split(
    event: Event, participants: list[Participant], policy: PolicySnapshot
) -> SplitResult:
    total = event.total_amount_yen
    if not total or total <= 0:
        raise SplitInputError("total_amount_not_confirmed")
    attendees = sorted((p for p in participants if p.attendance_confirmed), key=lambda p: p.user_id)
    ids = [p.user_id for p in attendees]
    if not attendees or len(set(ids)) != len(ids):
        raise SplitInputError("invalid_attendees")
    guests = set(event.guests_of_honor)
    if not guests <= set(ids):
        raise SplitInputError("guest_of_honor_not_attending")
    if event.organizer_user_id not in ids:
        raise SplitInputError("organizer_not_attending")
    payers = [p for p in attendees if p.user_id not in guests]
    if not payers:
        raise SplitInputError("no_payers")

    on = event.datetime.date()
    classes = {p.user_id: classify_member(policy, p, on) for p in attendees}
    approver = determine_approver(attendees, policy, event_date=on, guests_of_honor=list(guests))

    subsidy = subsidy_yen(policy, attendees, guests, total)
    base = total - subsidy
    weights = {p.user_id: Fraction(str(classes[p.user_id].weight)) for p in payers}
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise SplitInputError("zero_weight_sum")

    unit = policy.rounding_unit_yen
    shares: dict[str, int] = {}
    for p in payers:
        exact = weights[p.user_id] * base / weight_sum  # 分数のまま
        shares[p.user_id] = int(exact // unit) * unit  # 切り捨て（base ≥ 0 なので床）
    shortfall = base - sum(shares.values())
    shares[approver] += shortfall

    eligible_ids = {
        p.user_id
        for p in attendees
        if p.employment_type in policy.subsidy.eligible_employment_types
    }
    rows = [
        SplitRow(
            user_id=p.user_id,
            member_class_id=classes[p.user_id].id,
            weight=0.0 if p.user_id in guests else classes[p.user_id].weight,
            ratio_percent=0.0
            if p.user_id in guests
            else _ratio_percent(weights[p.user_id], weight_sum),
            subsidy_eligible=p.user_id in eligible_ids,
            share_yen=0 if p.user_id in guests else shares[p.user_id],
        )
        for p in attendees
    ]
    per_weight = int(Fraction(base) / weight_sum)
    core = {
        "event_id": event.event_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.version,
        "total_amount_yen": total,
        "subsidy_yen": subsidy,
        "rows": [r.model_dump() for r in rows],
        "shortfall_yen": shortfall,
        "approver_user_id": approver,
    }
    return SplitResult(
        event_id=event.event_id,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        total_amount_yen=total,
        base_amount_yen=base,
        subsidy_yen=subsidy,
        weight_sum=float(weight_sum),
        per_weight_yen=per_weight,
        rows=rows,
        shortfall_yen=shortfall,
        shortfall_to=approver,
        approver_user_id=approver,
        hash=split_hash(core),
    )
