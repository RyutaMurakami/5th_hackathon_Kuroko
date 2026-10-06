"""出席者の区分の判定（按分・承認者の決定が共通で使う。SPEC 3章 Participant）。"""

import datetime as dt

from src.models.event import Participant
from src.models.policy import MemberClass, PolicySnapshot


class SplitInputError(Exception):
    """按分に進めない入力（Policy Gate 6.1 で差し戻す）。message に個人情報を入れない。"""


def _months_between(start: dt.date, end: dt.date) -> int:
    """入社日から基準日までの満月数。"""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def classify_member(policy: PolicySnapshot, p: Participant, on: dt.date) -> MemberClass:
    """規程の区分（上から順に評価し、最初に一致したもの）。"""
    tenure = _months_between(p.hire_date, on)
    for c in policy.member_classes:
        if c.role != p.job_title:
            continue
        if c.tenure_months_less_than is not None and tenure >= c.tenure_months_less_than:
            continue
        return c
    raise SplitInputError("unknown_member_class")
