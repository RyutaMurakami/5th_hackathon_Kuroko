"""振り返りのコメントを、固定の語彙に落とす（隔離抽出の `feedback` 用途。SPEC 4.1・10章）。

**仮実装**: 本来は、ツールを持たない `extract-agent`（B26）が行う。ここでは、決まったキーワードで
語彙に落とす決定論的な処理にして、`FeedbackExtractor` の形（コメント → `{liked, concerns}`）を
先に固定する。`extract-agent` ができたら、同じ形の実装に差し替える。
**出力は固定の語彙だけ**（語彙にない値は捨てる）。コメントの原文は、返さず、保存せず、ログに出さない。
"""

from dataclasses import dataclass, field
from typing import Protocol

from src.services.vocab import CONCERNS, LIKED, only_vocab

MAX_COMMENT_CHARS = 200

_LIKED_WORDS = {
    "food": ("美味", "おいしい", "料理が良", "料理がよ"),
    "atmosphere": ("雰囲気", "落ち着", "素敵", "おしゃれ"),
    "private_room": ("個室",),
    "access": ("駅近", "アクセスが良", "行きやす", "近くて"),
    "price": ("安い", "リーズナブル", "コスパ", "お得"),
    "service": ("接客", "親切", "丁寧", "対応が良"),
    "drinks": ("ドリンク", "飲み放題", "お酒が"),
}
_CONCERN_WORDS = {
    "noisy": ("うるさ", "騒がし", "声が聞こえ"),
    "slow_service": ("提供が遅", "待たされ", "料理が来な", "遅かった"),
    "pricey": ("高かった", "高い", "割高"),
    "small": ("狭", "窮屈"),
    "access_far": ("遠かった", "遠い", "不便", "分かりにくい"),
    "food_quality": ("まずい", "冷めて", "いまいち", "微妙"),
}


@dataclass(frozen=True)
class Extracted:
    liked: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


class FeedbackExtractor(Protocol):
    def extract(self, comment: str) -> Extracted: ...


class KeywordFeedbackExtractor:
    def extract(self, comment: str) -> Extracted:
        text = comment[:MAX_COMMENT_CHARS]
        liked = [k for k, words in _LIKED_WORDS.items() if any(w in text for w in words)]
        concerns = [k for k, words in _CONCERN_WORDS.items() if any(w in text for w in words)]
        return Extracted(only_vocab(liked, LIKED), only_vocab(concerns, CONCERNS))
