"""店舗候補（SPEC 3章 VenueCandidate・9.9）。順位と理由の元になる数値は、すべてコードが作る。"""

from typing import Literal

from pydantic import BaseModel, Field


class StageResult(BaseModel):
    """段階ごとの結果（コードが作る。判断ログに残す）。"""

    hard_passed: bool
    excluded_reason: str | None = None
    band: int  # 最も遠い人の所要時間を、帯の幅で割った値（小さいほど近い）
    preference_match: dict[str, int] = {}  # 反映できた希望 → 希望した人数
    unmet_preferences: dict[str, int] = {}  # 反映できなかった希望 → 希望した人数
    avoid_hits: int = 0  # 苦手なものに当たる人数の合計
    memory_adjust: int = 0  # 過去の実績による調整（同じ帯の中だけで効く）


class ReasonFacts(BaseModel):
    """選んだ理由の元になる数値と事実（コードが作る。個人は特定しない）。LLM は文章にするだけ。"""

    max_travel_minutes: int  # 最も遠い方でも○分
    avg_travel_minutes: float
    passed_checks: list[str]  # 通したハード制約（人数・予算・食べられないもの など）
    reflected: dict[str, int]  # 反映した希望 → 人数
    unmet_preferences: dict[str, int]  # 反映できなかった希望 → 人数
    relaxed_to_minutes: int | None = None  # 条件を緩めたなら、何分にしたか
    memory_note: str | None = None  # 過去の実績（表示専用）
    price_min_yen: int | None = None
    price_max_yen: int | None = None
    capacity_unknown: bool = True  # 収容人数が分からない（Google Maps に無い）。予約時に確認する


class VenueCandidate(BaseModel):
    place_id: str
    name: str
    address: str = ""
    nearest_station: str
    max_travel_minutes: int
    avg_travel_minutes: float
    price_min_yen: int | None = None
    price_max_yen: int | None = None
    features: list[str] = []  # 固定の語彙のタグ
    source: Literal["google_maps"] = "google_maps"
    review_snippet_used: bool = False  # 口コミ本文を判断に使った場合 true（隔離抽出を通す。10章）
    rating: float | None = None
    memory_note: str | None = None
    memory_refs: list[str] = []
    stage_result: StageResult
    reason_facts: ReasonFacts
    selection_reason: str = ""  # LLM が reason_facts から作る。検査を通らなければ定型の文
    role: Literal["overall", "preference_first"] = "overall"
    allergen_notice: str = Field(default="アレルゲンは、店に確認してください。")
