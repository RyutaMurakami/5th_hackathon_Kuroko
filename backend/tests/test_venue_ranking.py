"""店舗の選定ロジック（SPEC 9.9）。同じ入力なら同じ順位で、優先度の順に並ぶ。"""

import random
from collections import Counter

from src.clients.maps import Venue
from src.models.venue import ReasonFacts
from src.services.access import AccessibleStation
from src.services.venue_ranking import (
    Constraints,
    MemoryRecord,
    Preferences,
    derive_tags,
    guard_reason,
    rank_venues,
    render_reason,
)


def venue(pid, name, *, rating=4.0, price=(3000, 5000), types=()) -> Venue:
    return Venue(
        place_id=pid, name=name, address="東京都", rating=rating, rating_count=100,
        price_level=None, price_min_yen=price[0], price_max_yen=price[1], maps_uri=None,
        types=tuple(types),
    )  # fmt: skip


def station(name, mx, avg=None, code=1) -> AccessibleStation:
    return AccessibleStation(name=name, code=code, max_minutes=mx, avg_minutes=avg or float(mx))


C = Constraints(party_size=10, hard_limit_per_person_yen=7000)
NO_PREF = Preferences()


def names(result):
    return [p.name for p in result.proposals]


def test_tags_come_from_the_name_and_google_types():
    assert derive_tags("個室居酒屋 黒", ()) == ["居酒屋", "個室"]
    assert derive_tags("海鮮と焼鳥 だいもん", ()) == ["焼き鳥", "海鮮"]
    assert derive_tags("名前だけ", ("japanese_restaurant",)) == ["和食"]
    assert derive_tags("無関係な店", ()) == []


# ---------------- ハード制約 ----------------
def test_price_floor_above_the_hard_limit_is_excluded_but_straddling_is_kept():
    s = station("渋谷", 20)
    r = rank_venues(
        [(venue("a", "高い店", price=(8000, 12000)), s),
         (venue("b", "上限をまたぐ店", price=(6000, 9000)), s)],
        C, NO_PREF,
    )  # fmt: skip
    assert names(r) == ["上限をまたぐ店"]
    assert r.excluded == [("高い店", "価格帯の下限が上限（7000円）を超える")]


def test_dietary_must_excludes_only_clearly_matching_venues():
    s = station("渋谷", 20)
    c = Constraints(10, 7000, dietary_must=frozenset({"そば", "アルコール"}))
    r = rank_venues(
        [(venue("a", "手打ち蕎麦 山", types=()), s),
         (venue("b", "個室居酒屋 黒"), s),
         (venue("c", "創作ダイニング 月"), s)],
        c, NO_PREF,
    )  # fmt: skip
    assert names(r) == ["創作ダイニング 月"]
    assert {n for n, _ in r.excluded} == {"手打ち蕎麦 山", "個室居酒屋 黒"}


def test_required_tags_set_by_the_organizer_are_hard():
    s = station("渋谷", 20)
    c = Constraints(10, 7000, required_tags=frozenset({"個室"}))
    r = rank_venues(
        [(venue("a", "個室居酒屋 黒"), s), (venue("b", "大衆酒場 ひろば"), s)], c, NO_PREF
    )
    assert names(r) == ["個室居酒屋 黒"]
    assert "個室" in r.excluded[0][1]
    # 参加者の希望としての「個室」はソフト（足切りに使わない）
    soft = rank_venues(
        [(venue("a", "個室居酒屋 黒"), s), (venue("b", "大衆酒場 ひろば"), s)],
        C, Preferences(request_tags=Counter({"個室": 3})),
    )  # fmt: skip
    assert len(soft.proposals) == 2


# ---------------- 辞書式の並べ替え ----------------
def test_distance_band_comes_first_then_preference_then_the_rest():
    near = station("近い駅", 12, avg=10.0, code=1)  # 帯 2
    mid = station("中の駅", 14, avg=12.0, code=2)  # 帯 2（同じ帯）
    far = station("遠い駅", 30, avg=20.0, code=3)  # 帯 6
    pref = Preferences(request_tags=Counter({"個室": 3}))
    r = rank_venues(
        [(venue("a", "遠くの個室居酒屋 ひので"), far),   # 希望に合うが、帯が遠い
         (venue("b", "近くの食堂 まる"), near),          # 帯2・希望なし
         (venue("c", "中の個室居酒屋 つき"), mid)],      # 帯2・希望あり
        C, pref,
    )  # fmt: skip
    # 帯が同じなら希望の一致度が先。帯が違えば、希望が合っても帯が優先
    assert names(r) == ["中の個室居酒屋 つき", "近くの食堂 まる", "遠くの個室居酒屋 ひので"]


def test_the_tie_breaks_follow_the_documented_order():
    s = station("渋谷", 20, avg=15.0)
    base = [
        (venue("a", "A店", rating=3.5), station("渋谷", 20, avg=18.0)),  # 平均が遠い
        (venue("b", "B店", rating=3.5), s),  # 平均が近い
        (venue("c", "C店", rating=4.8), s),  # 同じ平均で評価が高い
    ]
    assert names(rank_venues(base, C, NO_PREF)) == ["C店", "B店", "A店"]


def test_average_travel_time_outranks_rating():
    """(e) 平均所要時間は、(f) 口コミの評価より先。評価が高くても、平均が遠い店は後ろ。"""
    r = rank_venues(
        [(venue("a", "評価の高い店", rating=4.9), station("渋谷", 20, avg=18.0)),
         (venue("b", "近い店", rating=3.2), station("渋谷", 20, avg=15.0))],
        C, NO_PREF,
    )  # fmt: skip
    assert names(r) == ["近い店", "評価の高い店"]


def test_avoid_hits_rank_below_otherwise_equal_venues():
    s = station("渋谷", 20)
    pref = Preferences(dietary_avoid=Counter({"豚": 2}))
    r = rank_venues(
        [(venue("a", "豚骨ラーメン一番"), s), (venue("b", "魚料理 なぎさ"), s)], C, pref
    )
    assert names(r) == ["魚料理 なぎさ", "豚骨ラーメン一番"]


def test_memory_moves_a_venue_within_its_band_only():
    near, far = station("近", 12, code=1), station("遠", 40, code=2)
    mem = {"a": MemoryRecord(within_budget=True, rating=4.5, reuse_intent="yes", note="前回利用")}
    r = rank_venues(
        [(venue("a", "実績のある店 A"), far), (venue("b", "初めての店 B"), near)],
        C, NO_PREF, memory=mem,
    )  # fmt: skip
    assert names(r) == ["初めての店 B", "実績のある店 A"]  # 帯が優先。実績があっても追い越さない
    same = rank_venues(
        [(venue("a", "実績のある店 A"), near), (venue("b", "初めての店 B"), near)],
        C, NO_PREF, memory=mem,
    )  # fmt: skip
    assert names(same) == ["実績のある店 A", "初めての店 B"]
    bad = {"a": MemoryRecord(reuse_intent="no")}
    down = rank_venues(
        [(venue("a", "使いたくない店 A"), near), (venue("b", "初めての店 B"), near)],
        C, NO_PREF, memory=bad,
    )  # fmt: skip
    assert names(down) == ["初めての店 B", "使いたくない店 A"]


# ---------------- 提案の選び方 ----------------
def test_at_most_three_and_the_best_preference_venue_replaces_the_third():
    close = station("近", 10)
    far = station("遠", 40, code=2)
    pref = Preferences(request_tags=Counter({"焼き鳥": 5}))
    vs = [(venue(f"v{i}", f"普通の店{i}"), close) for i in range(4)]
    vs.append((venue("y", "焼き鳥 とり吉"), far))  # 希望に最も合うが、遠くて総合4位以下
    r = rank_venues(vs, C, pref)
    assert len(r.proposals) == 3
    assert r.proposals[2].name == "焼き鳥 とり吉" and r.proposals[2].role == "preference_first"
    assert [p.role for p in r.proposals[:2]] == ["overall", "overall"]


def test_no_replacement_when_nobody_matches_the_preferences():
    close = station("近", 10)
    vs = [(venue(f"v{i}", f"普通の店{i}"), close) for i in range(5)]
    r = rank_venues(vs, C, Preferences(request_tags=Counter({"焼き鳥": 5})))
    assert all(p.role == "overall" for p in r.proposals) and len(r.proposals) == 3


def test_unmet_preferences_are_recorded_and_stated_in_the_reason():
    s = station("渋谷", 20)
    pref = Preferences(request_tags=Counter({"個室": 3, "肉": 1}))
    r = rank_venues([(venue("a", "個室居酒屋 黒"), s)], C, pref)
    (p,) = r.proposals
    assert p.reason_facts.reflected == {"個室": 3} and p.reason_facts.unmet_preferences == {"肉": 1}
    assert (
        "個室3名" in p.selection_reason
        and "肉1名の希望は、この店では反映できていません" in p.selection_reason
    )
    assert "アレルゲンは、店に確認してください" in p.selection_reason


def test_relaxed_limit_is_in_the_reason_without_naming_anyone():
    r = rank_venues([(venue("a", "店"), station("渋谷", 52))], C, NO_PREF, relaxed_to_minutes=60)
    assert "上限を60分に緩めました" in r.proposals[0].selection_reason
    assert "最も遠い方でも52分" in r.proposals[0].selection_reason


# ---------------- 決定論・重複 ----------------
def test_same_input_gives_the_same_result_whatever_the_order():
    rng = random.Random(7)
    s = [station("渋谷", 15, code=1), station("新宿", 25, code=2)]
    vs = [(venue(f"p{i}", f"店{i}", rating=3 + (i % 5) / 4), s[i % 2]) for i in range(12)]
    first = rank_venues(vs, C, NO_PREF)
    for _ in range(5):
        shuffled = vs[:]
        rng.shuffle(shuffled)
        again = rank_venues(shuffled, C, NO_PREF)
        assert [p.place_id for p in again.proposals] == [p.place_id for p in first.proposals]


def test_a_venue_found_from_two_stations_is_counted_once():
    v = venue("a", "両方で出る店")
    r = rank_venues([(v, station("遠", 40, code=2)), (v, station("近", 10, code=1))], C, NO_PREF)
    assert len(r.proposals) == 1


# ---------------- 理由の検査 ----------------
FACTS = ReasonFacts(
    max_travel_minutes=40, avg_travel_minutes=31.5, passed_checks=["人数"],
    reflected={"個室": 3}, unmet_preferences={"肉": 1}, price_min_yen=3000, price_max_yen=5000,
)  # fmt: skip


def test_a_reason_with_numbers_from_the_facts_is_kept():
    text = "最も遠い方でも40分で、個室の希望3名を反映しています。"
    assert guard_reason(text, FACTS, other_venue_names=set()) == text


def test_a_reason_with_an_invented_number_or_another_venue_is_replaced():
    for text in (
        "最も遠い方でも25分で着けます。",  # 事実にない数値
        "5名の希望を反映しました。",  # 事実にない人数
        "近くの「食堂 まる」より、こちらがおすすめです。",  # 他の店の名前
    ):
        guarded = guard_reason(text, FACTS, other_venue_names={"食堂 まる"})
        assert guarded == render_reason(FACTS)
