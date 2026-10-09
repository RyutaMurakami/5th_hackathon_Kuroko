"""店舗の選定ロジック（SPEC 9.9。TASKS B5）。**LLM を呼ばない。同じ入力なら同じ順位**。

足切り（ハード制約）→ 辞書式の並べ替え → 提案の選び方 → 理由の元（`reason_facts`）。
「重みの足し合わせ」ではなく、優先度の順に並べる（なぜこの店かを説明できるようにするため）:
 (a) 最も遠い人の所要時間の帯（5分刻み。小さい順）
 (b) 希望の一致度（一致する希望の「希望した人数」の合計。大きい順）
 (c) 過去の実績による調整（同じ帯の中だけ）
 (d) 苦手なものに当たる人数（少ない順）
 (e) 平均所要時間（小さい順）
 (f) 口コミの評価（高い順）
**仮実装**: 店のジャンル・設備は、Google Maps の「種類」と店名から決める（収容人数・アレルゲン・
個室の有無は Google Maps に無い）。口コミ本文は使わない（外部入力。隔離抽出を通すまで）。
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from src.clients.maps import Venue
from src.models.venue import ReasonFacts, StageResult, VenueCandidate
from src.services.access import AccessibleStation
from src.services.vocab import REQUEST_TAGS

BAND_MINUTES = 5
MAX_PROPOSALS = 3

# 店名から、固定の語彙のタグを決める（仮。Google Maps に設備の情報が無いため）
_NAME_TAGS: dict[str, tuple[str, ...]] = {
    "居酒屋": ("居酒屋", "酒場", "大衆酒場"),
    "焼き鳥": ("焼き鳥", "焼鳥", "やきとり", "串焼"),
    "海鮮": ("海鮮", "鮮魚", "寿司", "すし", "刺身"),
    "肉": ("焼肉", "ステーキ", "肉", "ホルモン", "しゃぶしゃぶ"),
    "和食": ("和食", "割烹", "懐石", "日本料理"),
    "洋食": ("イタリアン", "フレンチ", "洋食", "ビストロ", "バル"),
    "中華": ("中華", "餃子", "飲茶"),
    "個室": ("個室",),
    "掘りごたつ": ("掘りごたつ", "掘り炬燵", "ほりごたつ"),
    "静か": ("隠れ家",),
}
# Google の店の種類 → タグ
_TYPE_TAGS = {
    "japanese_restaurant": "和食",
    "seafood_restaurant": "海鮮",
    "chinese_restaurant": "中華",
    "steak_house": "肉",
    "barbecue_restaurant": "肉",
    "yakiniku_restaurant": "肉",
    "italian_restaurant": "洋食",
    "french_restaurant": "洋食",
    "izakaya": "居酒屋",
}
# 食べられないもの → 店名・種類に出てくる語（**明らかに該当する店**だけを外す。保証はしない）
_DIETARY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "えび": ("えび", "エビ", "海老"),
    "かに": ("かに", "カニ", "蟹"),
    "そば": ("そば", "蕎麦"),
    "小麦": ("ラーメン", "うどん", "パスタ", "ピザ", "ベーカリー"),
    "卵": ("オムライス", "親子丼"),
    "乳": ("チーズ", "ミルク", "グラタン"),
    "豚": ("豚", "とんかつ", "トンカツ", "ラーメン"),
    "牛": ("牛", "焼肉", "ステーキ"),
    "アルコール": ("居酒屋", "酒場", "バー", "BAR", "ワイン"),
}


def derive_tags(name: str, types: tuple[str, ...]) -> list[str]:
    tags = [t for t, kws in _NAME_TAGS.items() if any(k in name for k in kws)]
    tags += [_TYPE_TAGS[t] for t in types if t in _TYPE_TAGS]
    return [t for t in REQUEST_TAGS if t in set(tags)]


@dataclass(frozen=True)
class MemoryRecord:
    """同じ店の過去の実績（Memory Bank の定型の事実から）。順位への影響は同じ帯の中だけ。"""

    within_budget: bool = False
    rating: float | None = None
    reuse_intent: Literal["yes", "no"] | None = None
    note: str | None = None
    ref: str | None = None

    def adjust(self) -> int:
        score = (1 if self.within_budget else 0) + (1 if (self.rating or 0) >= 4 else 0)
        if self.reuse_intent == "yes":
            score += 2
        elif self.reuse_intent == "no":
            score -= 3
        return score


@dataclass(frozen=True)
class Constraints:
    party_size: int
    hard_limit_per_person_yen: int  # 規程（policy_snapshot）の上限
    dietary_must: frozenset[str] = frozenset()  # 参加者に1人でもいれば、ハード制約
    required_tags: frozenset[str] = frozenset()  # 幹事が計画で決めた条件（例: 個室が必須）


@dataclass(frozen=True)
class Preferences:
    request_tags: Counter = field(default_factory=Counter)  # タグ → 希望した人数
    dietary_avoid: Counter = field(default_factory=Counter)  # 苦手なもの → 人数


@dataclass
class RankingResult:
    proposals: list[VenueCandidate] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (店名, 理由)
    ranked_count: int = 0  # 足切りを通った店の数


def _hits(name: str, types: tuple[str, ...], dietary: str) -> bool:
    text = name + " " + " ".join(types)
    return any(k in text for k in _DIETARY_KEYWORDS.get(dietary, ()))


def _exclusion(v: Venue, tags: list[str], c: Constraints) -> str | None:
    """ハード制約で外す理由（なければ None）。"""
    if v.price_min_yen is not None and v.price_min_yen > c.hard_limit_per_person_yen:
        return f"価格帯の下限が上限（{c.hard_limit_per_person_yen}円）を超える"
    for d in sorted(c.dietary_must):
        if _hits(v.name, v.types, d):
            return f"食べられないもの（{d}）に明らかに該当する"
    missing = sorted(c.required_tags - set(tags))
    if missing:
        return f"幹事が決めた条件（{'・'.join(missing)}）を満たさない"
    return None


def rank_venues(
    venues: list[tuple[Venue, AccessibleStation]],
    constraints: Constraints,
    preferences: Preferences,
    *,
    memory: dict[str, MemoryRecord] | None = None,
    relaxed_to_minutes: int | None = None,
) -> RankingResult:
    """`venues` は（店, その店がある候補駅）。同じ入力なら、必ず同じ結果。"""
    memory = memory or {}
    result = RankingResult()
    scored: list[tuple[tuple, VenueCandidate]] = []
    seen: set[str] = set()
    for venue, station in sorted(venues, key=lambda x: (x[0].place_id, x[1].code)):
        if venue.place_id in seen:
            continue  # 同じ店が複数の駅の検索に出ても、1回だけ（近いほうの駅）
        seen.add(venue.place_id)
        tags = derive_tags(venue.name, venue.types)
        reason = _exclusion(venue, tags, constraints)
        if reason:
            result.excluded.append((venue.name, reason))
            continue
        match = {t: n for t, n in preferences.request_tags.items() if t in tags and n > 0}
        unmet = {t: n for t, n in preferences.request_tags.items() if t not in tags and n > 0}
        avoid = sum(
            n for d, n in preferences.dietary_avoid.items() if _hits(venue.name, venue.types, d)
        )
        mem = memory.get(venue.place_id)
        stage = StageResult(
            hard_passed=True,
            band=station.max_minutes // BAND_MINUTES,
            preference_match=match,
            unmet_preferences=unmet,
            avoid_hits=avoid,
            memory_adjust=mem.adjust() if mem else 0,
        )
        facts = ReasonFacts(
            max_travel_minutes=station.max_minutes,
            avg_travel_minutes=station.avg_minutes,
            passed_checks=["人数", "予算", "食べられないもの"]
            + (["幹事が決めた条件"] if constraints.required_tags else []),
            reflected=match,
            unmet_preferences=unmet,
            relaxed_to_minutes=relaxed_to_minutes,
            memory_note=mem.note if mem else None,
            price_min_yen=venue.price_min_yen,
            price_max_yen=venue.price_max_yen,
        )
        candidate = VenueCandidate(
            place_id=venue.place_id,
            name=venue.name,
            address=venue.address,
            nearest_station=station.name,
            max_travel_minutes=station.max_minutes,
            avg_travel_minutes=station.avg_minutes,
            price_min_yen=venue.price_min_yen,
            price_max_yen=venue.price_max_yen,
            features=tags,
            rating=venue.rating,
            memory_note=mem.note if mem else None,
            memory_refs=[mem.ref] if mem and mem.ref else [],
            stage_result=stage,
            reason_facts=facts,
            selection_reason=render_reason(facts),
        )
        key = (
            stage.band,
            -sum(match.values()),
            -stage.memory_adjust,
            stage.avoid_hits,
            station.avg_minutes,
            -(venue.rating or 0.0),
            venue.name,
            venue.place_id,
        )
        scored.append((key, candidate))
    scored.sort(key=lambda x: x[0])
    result.ranked_count = len(scored)
    ordered = [c for _, c in scored]
    result.proposals = _select(ordered)
    return result


def _select(ordered: list[VenueCandidate]) -> list[VenueCandidate]:
    """総合の上位3件。希望の一致度が最大の店が入らないときは、3件目をその店に置き換える。"""
    top = ordered[:MAX_PROPOSALS]
    if len(ordered) <= MAX_PROPOSALS or not top:
        return top
    best = max(ordered, key=lambda c: sum(c.stage_result.preference_match.values()))
    # 同点なら総合順位が上の店（max は先頭を返す）。一致度が0なら置き換えない
    if sum(best.stage_result.preference_match.values()) > 0 and best not in top:
        pref = best.model_copy(update={"role": "preference_first"})
        return [*top[: MAX_PROPOSALS - 1], pref]
    return top


# ---------------------------------------------------------------- 理由の文章
def render_reason(f: ReasonFacts) -> str:
    """定型の理由の文（`reason_facts` の値だけから作る。検査に落ちた LLM の文の差し替え先）。"""
    parts = [f"最も遠い方でも{f.max_travel_minutes}分で着けます。"]
    if f.relaxed_to_minutes:
        parts.append(
            f"全員が着ける駅が少なかったため、所要時間の上限を{f.relaxed_to_minutes}分に緩めました。"
        )
    if f.reflected:
        wanted = "、".join(f"{t}{n}名" for t, n in f.reflected.items())
        parts.append(f"希望のうち、{wanted}を反映しています。")
    if f.unmet_preferences:
        unmet = "、".join(f"{t}{n}名" for t, n in f.unmet_preferences.items())
        parts.append(f"{unmet}の希望は、この店では反映できていません。")
    if f.memory_note:
        parts.append(f.memory_note)
    parts.append("アレルゲンは、店に確認してください。")
    return "".join(parts)


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _allowed_numbers(f: ReasonFacts) -> set[str]:
    nums: list[float | int | None] = [
        f.max_travel_minutes, f.avg_travel_minutes, f.relaxed_to_minutes,
        f.price_min_yen, f.price_max_yen,
        *f.reflected.values(), *f.unmet_preferences.values(),
    ]  # fmt: skip
    out = {str(int(n)) if float(n).is_integer() else str(n) for n in nums if n is not None}
    if f.memory_note:
        out |= set(_NUMBER.findall(f.memory_note))
    return out


def guard_reason(text: str, f: ReasonFacts, *, other_venue_names: set[str]) -> str:
    """LLM の理由に、`reason_facts` にない数値・他の店の名前があれば、定型の文に差し替える。"""
    allowed = _allowed_numbers(f)
    if any(n not in allowed for n in _NUMBER.findall(text)):
        return render_reason(f)
    # この店以外の候補の店の名前が出てきたら、差し替える（理由は、この店の事実だけで書く）
    if any(name in text for name in other_venue_names):
        return render_reason(f)
    return text.strip()
