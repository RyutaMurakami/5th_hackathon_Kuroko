"""固定の語彙（SPEC 9.9・3章 Feedback）。`backend/src/services/vocab.py` と同じ値（テストで一致を固定）。

このエージェントが返してよい値は、ここにあるものだけ。語彙にない値は捨てる。
"""

GENRE_TAGS = ("居酒屋", "焼き鳥", "海鮮", "肉", "和食", "洋食", "中華")
ATMOSPHERE_TAGS = ("個室", "静か", "にぎやか", "禁煙", "掘りごたつ")
REQUEST_TAGS = GENRE_TAGS + ATMOSPHERE_TAGS
DIETARY = ("えび", "かに", "くるみ", "小麦", "そば", "卵", "乳", "落花生", "豚", "牛", "アルコール")
LIKED = ("food", "atmosphere", "private_room", "access", "price", "service", "drinks")
CONCERNS = ("noisy", "slow_service", "pricey", "small", "access_far", "food_quality", "other")

MODES = ("preferences", "feedback")
MAX_INPUT_CHARS = 500  # 入力の長さの上限（自由記述は短い。長い文は切る）
MAX_STATION_CHARS = 15
