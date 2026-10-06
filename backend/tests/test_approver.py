"""determine_approver（係数 → 役職ランク → 入社日 → 社員番号）。"""

import datetime as dt

import pytest

from src.models.event import ParticipantRole
from src.services.approver import ApproverTie, determine_approver
from src.services.members import SplitInputError, classify_member
from src.services.policy import load_snapshot
from tests.sample_company import demo_participants, person

POLICY = load_snapshot()
ON = dt.date(2026, 10, 30)


def pick(people, guests=()):
    return determine_approver(people, POLICY, event_date=ON, guests_of_honor=list(guests))


def test_unique_highest_weight_wins():
    assert pick(demo_participants(), ["matsumoto", "inoue"]) == "yamada"


def test_ties_are_broken_by_rank_then_hire_date_then_employee_id():
    # 同じ係数（部長 2.0）が2名 → 区分が同じなので役職ランクも同じ → 入社日が早いほう
    people = [
        person("a", "部長", "2010-04-01", "E050"),
        person("b", "部長", "2009-04-01", "E060"),
        person("c", "一般", "2001-04-01", "E001"),
    ]
    assert pick(people) == "b"
    # 入社日も同じなら、社員番号が小さいほう
    people[0] = person("a", "部長", "2009-04-01", "E050")
    assert pick(people) == "a"


def test_rank_is_used_when_weights_tie():
    from src.models.policy import MemberClass

    # 係数が同じで ランクだけ違う区分を作って、2番目の比較が効くことを確かめる
    classes = [
        MemberClass(id="x", label="X", role="X", rank=1, weight=1.0, consent_cap_yen=1000),
        MemberClass(id="y", label="Y", role="Y", rank=5, weight=1.0, consent_cap_yen=1000),
    ]
    policy = POLICY.model_copy(update={"member_classes": classes})
    people = [person("p", "X", "2000-01-01", "E001"), person("q", "Y", "2020-01-01", "E999")]
    assert determine_approver(people, policy, event_date=ON, guests_of_honor=[]) == "q"


def test_guests_of_honor_are_never_approvers_even_with_the_top_weight():
    people = demo_participants()
    people.append(person("vp", "部長", "2000-04-01", "E000", role=ParticipantRole.GUEST_OF_HONOR))
    assert pick(people, ["matsumoto", "inoue", "vp"]) == "yamada"


def test_only_confirmed_attendees_can_approve():
    people = demo_participants()
    people[0] = person("yamada", "部長", "2008-04-01", "E001", attending=False)
    assert pick(people, ["matsumoto", "inoue"]) == "sasaki"


def test_result_does_not_depend_on_the_order():
    people = demo_participants()
    assert pick(list(reversed(people)), ["matsumoto", "inoue"]) == pick(
        people, ["matsumoto", "inoue"]
    )


def test_duplicate_employee_ids_with_all_else_equal_raise_instead_of_guessing():
    people = [person("a", "部長", "2009-04-01", "E001"), person("b", "部長", "2009-04-01", "E001")]
    with pytest.raises(ApproverTie):
        pick(people)


def test_no_candidates_is_an_error():
    with pytest.raises(SplitInputError):
        pick([person("g", "一般", "2020-04-01", "E1")], ["g"])


@pytest.mark.parametrize(
    ("hire", "expected"),
    [
        ("2025-10-29", "staff"),  # 12か月と1日
        ("2025-10-30", "staff"),  # ちょうど満12か月 → 「12か月未満」ではない
        ("2025-10-31", "new_hire"),  # 11か月と30日
        ("2026-04-01", "new_hire"),
        ("2026-10-29", "new_hire"),
    ],
)
def test_new_hire_boundary_is_12_full_months(hire, expected):
    cls = classify_member(POLICY, person("p", "一般", hire, "E1"), ON)
    assert cls.id == expected
