"""記憶の事実（SPEC 9.8）。**定型の文**を、検証済みの値からコードが作り、コードが読み戻す。

- 文面は固定のテンプレート。スロットに入るのは、イベントのデータから取った値だけ
  （LLM が書いた文・自由記述の原文・個人の名前・個人ごとの回答は入らない）
- 読み戻し（`records_by_venue`）は、同じテンプレートの形に合う文だけを使う。合わない文は捨てる
  （記憶に別の文が混ざっても、店の順位・理由には届かない）
"""

import re
from collections.abc import Iterable

from src.models.feedback import MemoryFact, Retrospective
from src.services.venue_ranking import MemoryRecord
from src.services.vocab import CONCERNS, LIKED

TEAM_LABEL = "第一開発チーム"  # 株式会社Akakura（架空）のチーム
TEAM_SCOPE = "team:sample-co:dev1"
EVENT_LABELS = {"welcome_farewell": "歓送迎会"}

LIKED_LABELS = {
    "food": "料理", "atmosphere": "雰囲気", "private_room": "個室", "access": "行きやすさ",
    "price": "価格", "service": "接客", "drinks": "飲み物",
}  # fmt: skip
CONCERN_LABELS = {
    "noisy": "騒がしさ", "slow_service": "提供の遅さ", "pricey": "価格の高さ", "small": "狭さ",
    "access_far": "駅からの遠さ", "food_quality": "料理の質", "other": "その他",
}  # fmt: skip
assert set(LIKED_LABELS) == set(LIKED) and set(CONCERN_LABELS) == set(CONCERNS)


def scope_for(sandbox: bool, guest_uid: str | None) -> str:
    """書き込みのスコープ。体験用のイベントは、作ったゲストごと（ほかのゲストと混ざらない）。"""
    return f"{TEAM_SCOPE}:guest:{guest_uid}" if sandbox and guest_uid else TEAM_SCOPE


def read_scopes(sandbox: bool, guest_uid: str | None) -> list[str]:
    """読むスコープ。体験用のイベントは、自分のスコープと、事前に入れた記憶（seed）のスコープ。"""
    own = scope_for(sandbox, guest_uid)
    return [own] if own == TEAM_SCOPE else [own, TEAM_SCOPE]


def _clean(name: str) -> str:
    """店名から、文の区切りに使う記号と改行を除く（読み戻しの形を崩さない）。"""
    return re.sub(r"[『』\s]+", " ", name).strip()[:60]


def record_fact(
    *, event_type: str, year: int, month: int, venue_name: str, party_size: int,
    per_person_yen: int, course_price_yen: int | None, within_budget: bool,
) -> str:  # fmt: skip
    course = f"（コース{course_price_yen:,}円）" if course_price_yen else ""
    return (
        f"{TEAM_LABEL}の{EVENT_LABELS.get(event_type, '懇親会')}（{year}/{month:02d}）で"
        f"『{_clean(venue_name)}』を{party_size}名で利用。"
        f"1人あたり{per_person_yen:,}円{course}で予算{'内' if within_budget else '超過'}。"
    )


def evaluation_fact(
    *, event_type: str, year: int, month: int, venue_name: str, avg_rating: float,
    response_count: int, reuse_intent: str, liked: Iterable[str] = (),
    concerns: Iterable[str] = (),
) -> str:  # fmt: skip
    text = (
        f"{TEAM_LABEL}の{EVENT_LABELS.get(event_type, '懇親会')}（{year}/{month:02d}）の"
        f"『{_clean(venue_name)}』の満足度は平均{avg_rating:.1f}（{response_count}名回答）。"
    )
    if reuse_intent in ("yes", "no"):
        text += f"幹事は次回も{'使いたい' if reuse_intent == 'yes' else '使いたくない'}。"
    good = [LIKED_LABELS[x] for x in liked if x in LIKED_LABELS]
    bad = [CONCERN_LABELS[x] for x in concerns if x in CONCERN_LABELS]
    if good:
        text += f"良かった点は{'・'.join(good)}。"
    if bad:
        text += f"気になった点は{'・'.join(bad)}。"
    return text


_HEAD = r"^第一開発チームの\S+?（(?P<ym>\d{4}/\d{2})）"
_RECORD = re.compile(
    _HEAD + r"で『(?P<name>[^『』]{1,60})』を(?P<n>\d{1,3})名で利用。"
    r"1人あたり(?P<pp>[\d,]{1,9})円(?:（コース[\d,]{1,9}円）)?で予算(?P<b>内|超過)。$"
)
_EVAL = re.compile(
    _HEAD + r"の『(?P<name>[^『』]{1,60})』の満足度は平均(?P<avg>\d\.\d)（\d{1,3}名回答）。"
    r"(?:幹事は次回も(?P<reuse>使いたい|使いたくない)。)?"
    r"(?:良かった点は[^。]{1,60}。)?(?:気になった点は[^。]{1,60}。)?$"
)


def venue_key(name: str) -> str:
    """店名の突き合わせの鍵（空白と大文字小文字の違いを無視する）。"""
    return re.sub(r"\s+", "", _clean(name)).lower()


def records_by_venue(facts: Iterable[str]) -> dict[str, MemoryRecord]:
    """事実から、店ごとの実績（順位の調整と、理由に添える文）を作る。鍵は `venue_key`。

    同じ店の事実が複数あるときは、時期が新しいものを使う。
    """
    latest: dict[str, dict] = {}
    for fact in facts:
        for pattern in (_RECORD, _EVAL):
            m = pattern.match(fact.strip())
            if m is None:
                continue
            key = venue_key(m["name"])
            row = latest.setdefault(key, {"ym": m["ym"]})
            if m["ym"] < row["ym"]:
                continue
            if m["ym"] > row["ym"]:
                row.clear()
                row["ym"] = m["ym"]
            if pattern is _RECORD:
                row |= {"pp": m["pp"], "within": m["b"] == "内"}
            else:
                row["rating"] = float(m["avg"])
                if m["reuse"]:
                    row["reuse"] = "yes" if m["reuse"] == "使いたい" else "no"
    return {key: _record(row) for key, row in latest.items()}


def _record(row: dict) -> MemoryRecord:
    parts = [f"前回（{row['ym']}）このチームで利用"]
    if "pp" in row:
        parts.append(f"1人あたり{row['pp']}円で予算{'内' if row['within'] else '超過'}")
    if "rating" in row:
        parts.append(f"満足度{row['rating']:.1f}")
    if "reuse" in row:
        again = row["reuse"] == "yes"
        parts.append("幹事は次回も使いたい" if again else "幹事は次回は使いたくない")
    return MemoryRecord(
        within_budget=bool(row.get("within")),
        rating=row.get("rating"),
        reuse_intent=row.get("reuse"),
        note="。".join(parts) + "。",
    )


def is_template_fact(text: str) -> bool:
    """定型のテンプレートの形の文か（Policy Gate 6.4。それ以外の文は、記憶に書かない）。"""
    return bool(_RECORD.match(text) or _EVAL.match(text))


def has_breakdown(text: str) -> bool:
    return "良かった点は" in text or "気になった点は" in text


def draft_facts(
    retro: Retrospective, *, event_type: str, year: int, month: int
) -> list[MemoryFact]:
    """振り返りの記録から、事実の下書きを作る。値は、集計済み・検証済みのものだけ。"""
    if not retro.venue_name:
        return []  # 店が決まっていないイベントは、覚えさせる事実が無い
    facts: list[MemoryFact] = []
    base = {"event_type": event_type, "year": year, "month": month, "venue_name": retro.venue_name}
    if retro.party_size and retro.per_person_yen and retro.within_budget is not None:
        facts.append(
            MemoryFact(
                kind="venue_record",
                text=record_fact(
                    **base,
                    party_size=retro.party_size,
                    per_person_yen=retro.per_person_yen,
                    course_price_yen=retro.course_price_yen,
                    within_budget=retro.within_budget,
                ),
            )  # fmt: skip
        )
    if retro.response_count and retro.avg_rating is not None:
        facts.append(
            MemoryFact(
                kind="venue_evaluation",
                text=evaluation_fact(
                    **base,
                    avg_rating=retro.avg_rating,
                    response_count=retro.response_count,
                    reuse_intent=retro.reuse_intent,
                    # 回答が3件未満のときは、集計の時点で内訳が空になっている（個人の特定を避ける）
                    liked=sorted(retro.liked_counts, key=lambda k: (-retro.liked_counts[k], k)),
                    concerns=sorted(
                        retro.concern_counts, key=lambda k: (-retro.concern_counts[k], k)
                    ),
                ),
            )  # fmt: skip
        )
    return facts
