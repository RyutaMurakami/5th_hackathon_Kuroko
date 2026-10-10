"""固定の語彙（SPEC 9.9・3章 Feedback）。語彙にない値は捨てる（隔離抽出の出力の検証と同じ）。

LLM・参加者の自由記述から来た値は、必ずここを通してから使う。
"""

from collections.abc import Iterable

# 店の希望（ジャンルと、雰囲気・設備）
GENRE_TAGS = ("居酒屋", "焼き鳥", "海鮮", "肉", "和食", "洋食", "中華")
ATMOSPHERE_TAGS = ("個室", "静か", "にぎやか", "禁煙", "掘りごたつ")
REQUEST_TAGS = GENRE_TAGS + ATMOSPHERE_TAGS

# 食べられないもの（特定原材料8品目のうち、店の名前から明らかに分かるもの＋宗教・信条上の除外）
DIETARY = ("えび", "かに", "くるみ", "小麦", "そば", "卵", "乳", "落花生", "豚", "牛", "アルコール")

# 振り返り（SPEC 3章 Feedback）
LIKED = ("food", "atmosphere", "private_room", "access", "price", "service", "drinks")
CONCERNS = ("noisy", "slow_service", "pricey", "small", "access_far", "food_quality", "other")


def only_vocab(values: Iterable[str], vocab: Iterable[str]) -> list[str]:
    """語彙にあるものだけを、順序を保って重複なしで返す。"""
    allowed = set(vocab)
    return list(dict.fromkeys(v for v in values if v in allowed))
