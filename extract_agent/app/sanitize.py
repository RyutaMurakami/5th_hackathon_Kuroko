"""出力の検証（決定論的）。LLM の出力は、ここを通った固定の語彙・形だけが外に出る（SPEC 10章）。

`kuroko-api` 側でも、同じ規則で、もう一度検証する（正は API 側。ARCHITECTURE 4.2）。
"""

import json
import re
from typing import Any

from app.vocab import (
    CONCERNS,
    DIETARY,
    LIKED,
    MAX_INPUT_CHARS,
    MAX_STATION_CHARS,
    MODES,
    REQUEST_TAGS,
)

# 駅名として許す文字: ひらがな・カタカナ・漢字・英字・括弧（大宮(埼玉県) のため）・長音・ヶ（数字は不可）
_STATION = re.compile(r"^[ぁ-んァ-ヶー一-龥々A-Za-z()（）ヶ ]+$")
# 文に特有の語（駅名には出てこない）。最終的な判定は、API 側の駅すぱあとでの照合
_SENTENCE_WORDS = ("を", "して", "ください", "ます", "です", "ない", "こと", "ように", "から")
EMPTY: dict[str, Any] = {
    "dislikes": [],
    "preferences": [],
    "nearest_station": None,
    "liked": [],
    "concerns": [],
}


def only(values: Any, vocab: tuple[str, ...]) -> list[str]:
    if not isinstance(values, list):
        return []
    allowed = set(vocab)
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v in allowed))


def clean_station(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > MAX_STATION_CHARS or not _STATION.match(name):
        return None  # URL・記号・数字・長い文は、駅名として通さない
    if any(w in name for w in _SENTENCE_WORDS):
        return None  # 命令文・説明文は、駅名として通さない
    return name


def sanitize(raw: Any, mode: str) -> dict[str, Any]:
    """用途（mode）ごとの欄だけを、語彙の値だけで返す。形が違えば、空の結果。"""
    if mode not in MODES or not isinstance(raw, dict):
        return dict(EMPTY)
    out = dict(EMPTY)
    if mode == "preferences":
        out["dislikes"] = only(raw.get("dislikes"), DIETARY)
        out["preferences"] = only(raw.get("preferences"), REQUEST_TAGS)
        out["nearest_station"] = clean_station(raw.get("nearest_station"))
    else:
        out["liked"] = only(raw.get("liked"), LIKED)
        out["concerns"] = only(raw.get("concerns"), CONCERNS)
    return out


def parse_request(text: str) -> tuple[str, str]:
    """`kuroko-api` が組み立てた入力（JSON: mode と text）。mode は API が決め、入力からは変えられない。"""
    try:
        data = json.loads(text)
        mode, body = data["mode"], data["text"]
    except (ValueError, KeyError, TypeError):
        return "", ""
    if mode not in MODES or not isinstance(body, str):
        return "", ""
    return mode, body[:MAX_INPUT_CHARS]
