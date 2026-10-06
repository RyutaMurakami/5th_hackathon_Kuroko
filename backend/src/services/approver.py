"""承認者の決定 `determine_approver`（SPEC 4.1・6章。**LLM を呼ばない**）。

規程の `approval.approver_selection` の順に比較し、必ず1名に決める。
候補は、出席者のうち主役を除いた人（主役は費用を負担せず、按分を承認する立場にない）。
"""

import datetime as dt
from collections.abc import Callable

from src.models.event import Participant
from src.models.policy import MemberClass, PolicySnapshot
from src.services.members import SplitInputError, classify_member


class ApproverTie(SplitInputError):
    """比較の最後まで同順位が残った（社員番号が重複している）。"""


def determine_approver(
    participants: list[Participant],
    policy: PolicySnapshot,
    *,
    event_date: dt.date,
    guests_of_honor: list[str],
) -> str:
    """承認者の user_id。"""
    candidates = [
        p for p in participants if p.attendance_confirmed and p.user_id not in guests_of_honor
    ]
    if not candidates:
        raise SplitInputError("no_candidates")
    classes: dict[str, MemberClass] = {
        p.user_id: classify_member(policy, p, event_date) for p in candidates
    }
    # 「小さいほどよい」キーに揃える（先頭から順に比較する）
    keys: dict[str, Callable[[Participant], object]] = {
        "highest_weight": lambda p: -classes[p.user_id].weight,
        "highest_rank": lambda p: -classes[p.user_id].rank,
        "earliest_hire_date": lambda p: p.hire_date,
        "lowest_employee_id": lambda p: p.employee_id,
    }
    ordered = sorted(candidates, key=lambda p: tuple(keys[r](p) for r in policy.approver_selection))
    best = ordered[0]
    if len(ordered) > 1 and tuple(keys[r](ordered[1]) for r in policy.approver_selection) == tuple(
        keys[r](best) for r in policy.approver_selection
    ):
        raise ApproverTie("approver_tie")
    return best.user_id
