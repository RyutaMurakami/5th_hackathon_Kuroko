"""calculate_split（SPEC 12.1）。review 04 6章の数字を固定し、性質をランダムな入力でも確かめる。"""

import random

import pytest

from src.models.event import Event, ParticipantRole
from src.services.members import SplitInputError
from src.services.policy import load_snapshot
from src.services.split import calculate_split
from tests.sample_company import EVENT_DATE, demo_event, demo_participants, person

POLICY = load_snapshot()


def shares(result) -> dict[str, int]:
    return {r.user_id: r.share_yen for r in result.rows}


def test_review04_numbers():
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    assert (r.total_amount_yen, r.subsidy_yen, r.base_amount_yen) == (60_300, 30_000, 30_300)
    assert r.weight_sum == 9.0 and r.per_weight_yen == 3366
    assert shares(r) == {
        "yamada": 7_200,  # 部長 6,700 + 端数の不足分 500
        "sasaki": 5_000,
        "takahashi": 3_300,
        "ito": 3_300,
        "watanabe": 3_300,
        "nakamura": 3_300,
        "kobayashi": 3_300,
        "kato": 1_600,
        "matsumoto": 0,
        "inoue": 0,
    }
    assert (r.shortfall_yen, r.shortfall_to, r.approver_user_id) == (500, "yamada", "yamada")
    # 振込で回収する額 = 按分の対象額 − 幹事本人の負担（review 04: 27,000円・7件）
    transfers = [s for u, s in shares(r).items() if u != "takahashi" and s > 0]
    assert len(transfers) == 7  # 山田・佐々木・伊藤・渡辺・中村・小林・加藤
    assert sum(transfers) == 30_300 - 3_300 == 27_000


def test_guests_of_honor_pay_nothing_and_have_zero_weight():
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    for row in r.rows:
        if row.user_id in {"matsumoto", "inoue"}:
            assert row.share_yen == 0 and row.weight == 0.0


def test_total_of_shares_equals_base_amount():
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    assert sum(x.share_yen for x in r.rows) == r.base_amount_yen
    assert r.base_amount_yen == r.total_amount_yen - r.subsidy_yen


def test_larger_weight_never_pays_less():
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    rows = [x for x in r.rows if x.weight > 0 and x.user_id != r.approver_user_id]
    for a in rows:
        for b in rows:
            if a.weight > b.weight:
                assert a.share_yen >= b.share_yen


def test_non_approver_shares_are_multiples_of_the_unit():
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    for row in r.rows:
        if row.user_id != r.approver_user_id:
            assert row.share_yen % POLICY.rounding_unit_yen == 0


def test_subsidy_excludes_ineligible_employment_types_but_they_still_pay():
    people = demo_participants()
    people[3] = person("ito", "一般", "2020-04-01", "E102", employment_type="業務委託")
    r = calculate_split(demo_event(), people, POLICY)
    assert r.subsidy_yen == 27_000  # 対象は9名
    assert r.base_amount_yen == 33_300
    ito = next(x for x in r.rows if x.user_id == "ito")
    assert ito.subsidy_eligible is False and ito.share_yen > 0
    assert sum(x.share_yen for x in r.rows) == 33_300


def test_subsidy_is_capped_per_event_and_by_the_total():
    many = [person(f"u{i:02d}", "一般", "2020-04-01", f"E{i:03d}") for i in range(25)]
    ev = Event(
        event_id="big", datetime=EVENT_DATE, organizer_user_id="u00", total_amount_yen=200_000
    )
    assert calculate_split(ev, many, POLICY).subsidy_yen == 60_000  # 25×3,000=75,000 → 上限
    tiny = ev.model_copy(update={"total_amount_yen": 2_000})
    r = calculate_split(tiny, many, POLICY)
    assert (r.subsidy_yen, r.base_amount_yen) == (2_000, 0)  # 会計金額を超えない
    assert all(x.share_yen == 0 for x in r.rows) and r.shortfall_yen == 0


def test_subsidy_can_exclude_guests_of_honor_when_the_policy_says_so():
    policy = POLICY.model_copy(
        update={"subsidy": POLICY.subsidy.model_copy(update={"include_guests_of_honor": False})}
    )
    r = calculate_split(demo_event(), demo_participants(), policy)
    assert r.subsidy_yen == 24_000  # 主役を除く8名


def test_deterministic_and_independent_of_participant_order():
    a = calculate_split(demo_event(), demo_participants(), POLICY)
    shuffled = demo_participants()
    random.Random(1).shuffle(shuffled)
    b = calculate_split(demo_event(), shuffled, POLICY)
    assert a == b and a.hash == b.hash
    assert calculate_split(demo_event(), demo_participants(), POLICY).hash == a.hash


def test_hash_changes_when_anything_that_matters_changes():
    base = calculate_split(demo_event(), demo_participants(), POLICY).hash
    assert calculate_split(demo_event(60_400), demo_participants(), POLICY).hash != base
    other = demo_participants()
    other[1] = person("sasaki", "一般", "2012-04-01", "E014")  # 課長 → 一般
    assert calculate_split(demo_event(), other, POLICY).hash != base
    renamed = demo_event().model_copy(update={"event_id": "ev-other"})
    assert calculate_split(renamed, demo_participants(), POLICY).hash != base


def test_only_confirmed_attendees_are_counted():
    people = demo_participants()
    people[6] = person("kobayashi", "一般", "2022-04-01", "E105", attending=False)
    r = calculate_split(demo_event(), people, POLICY)
    assert "kobayashi" not in shares(r)
    assert r.subsidy_yen == 27_000


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda ev, ps: (ev.model_copy(update={"total_amount_yen": None}), ps), "total"),
        (lambda ev, ps: (ev.model_copy(update={"organizer_user_id": "nobody"}), ps), "organizer"),
        (lambda ev, ps: (ev.model_copy(update={"guests_of_honor": ["nobody"]}), ps), "guest"),
        (lambda ev, ps: (ev, []), "attendees"),
        (lambda ev, ps: (ev, ps + [ps[0]]), "attendees"),  # user_id の重複
    ],
)
def test_inputs_that_cannot_be_split_are_rejected(mutate, code):
    ev, ps = mutate(demo_event(), demo_participants())
    with pytest.raises(SplitInputError):
        calculate_split(ev, ps, POLICY)


def test_unknown_job_title_is_rejected_not_guessed():
    people = demo_participants()
    people[2] = person("takahashi", "常務", "2019-04-01", "E101", role=ParticipantRole.ORGANIZER)
    with pytest.raises(SplitInputError):
        calculate_split(demo_event(), people, POLICY)


def test_random_inputs_keep_the_invariants():
    """合計一致・主役0円・不足分は承認者だけ・不足は単位未満×人数 未満。"""
    rng = random.Random(20261030)
    titles = ["部長", "課長", "一般", "一般", "一般"]
    for trial in range(300):
        n = rng.randint(2, 30)
        people = [
            person(
                f"u{i:02d}",
                rng.choice(titles),
                f"{rng.randint(2005, 2026)}-0{rng.randint(1, 9)}-15"
                if rng.random() < 0.9
                else "2026-06-01",
                f"E{i:03d}",
                employment_type=rng.choice(["正社員", "正社員", "契約社員", "業務委託"]),
            )
            for i in range(n)
        ]
        guests = [p.user_id for p in rng.sample(people, rng.randint(0, min(2, n - 1)))]
        organizer = next(p.user_id for p in people if p.user_id not in guests)
        ev = Event(
            event_id=f"ev{trial}",
            datetime=EVENT_DATE,
            organizer_user_id=organizer,
            guests_of_honor=guests,
            total_amount_yen=rng.randint(1_000, 400_000),
        )
        r = calculate_split(ev, people, POLICY)
        assert sum(x.share_yen for x in r.rows) == r.base_amount_yen
        assert all(x.share_yen == 0 for x in r.rows if x.user_id in guests)
        assert all(x.share_yen >= 0 for x in r.rows)
        assert 0 <= r.shortfall_yen < POLICY.rounding_unit_yen * len(r.rows)
        assert r.approver_user_id not in guests
        for x in r.rows:
            if x.user_id != r.approver_user_id:
                assert x.share_yen % 100 == 0


def test_each_person_has_a_burden_ratio_from_the_weights():
    """負担割合（％）= 係数 ÷ 係数の合計。review 04: 部長 2.0 / 9.0 など。"""
    r = calculate_split(demo_event(), demo_participants(), POLICY)
    ratio = {x.user_id: x.ratio_percent for x in r.rows}
    assert ratio["yamada"] == 22.22  # 2.0 / 9.0
    assert ratio["sasaki"] == 16.67  # 1.5 / 9.0
    assert ratio["takahashi"] == ratio["ito"] == ratio["kobayashi"] == 11.11  # 1.0 / 9.0
    assert ratio["kato"] == 5.56  # 0.5 / 9.0
    assert ratio["matsumoto"] == ratio["inoue"] == 0.0  # 主役は負担なし
    assert abs(sum(ratio.values()) - 100) < 0.05 * len(ratio)  # 丸めの誤差だけ


def test_amounts_follow_the_exact_ratio_not_the_rounded_percent():
    """％は表示用に丸める。金額は、丸めた％でなく、分数から求めた値と一致する。"""
    from fractions import Fraction

    people = demo_participants()
    r = calculate_split(demo_event(), people, POLICY)
    exact = {
        "yamada": Fraction(2) * 30_300 / 9,
        "kato": Fraction(1, 2) * 30_300 / 9,
    }
    # 承認者以外は、正確な負担額を100円単位で切り捨てた値
    assert shares(r)["kato"] == int(exact["kato"] // 100) * 100
    assert shares(r)["yamada"] - r.shortfall_yen == int(exact["yamada"] // 100) * 100


def test_ratio_is_part_of_the_hash():
    base = calculate_split(demo_event(), demo_participants(), POLICY)
    other = demo_participants()
    other[2] = person("takahashi", "課長", "2019-04-01", "E101", role=ParticipantRole.ORGANIZER)
    assert calculate_split(demo_event(), other, POLICY).hash != base.hash
