"""規程の文書の検索（`retrieve_policy`。SPEC 4.1・9.7）。

文書を**条ごと**に分け、質問に合う条だけを返す（全文は返さない・LLM に渡さない）。
検索は、質問と条文の文字の重なり（2文字の並び）で決める決定論的なコード。RAG Engine の
コーパスを用意したら、`PolicyRetriever` を差し替える（返す形は同じ: 条番号・見出し・本文）。

**返す条文は、規程の文書由来の外部入力**。呼び出し側（エージェント）は、条文の中の文を
指示として扱わない。金額の計算・承認者の決定には使わない（コードが、検証済みの写しで行う）。
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.services.policy import DEFAULT_RULES_PATH

DEFAULT_DOCUMENT_PATH = DEFAULT_RULES_PATH.with_name("company_rules.md")
MAX_QUESTION_CHARS = 200
MAX_EXCERPT_CHARS = 1200

_HEADING = re.compile(r"^##\s*(第\d{1,3}条)（([^）]{1,40})）\s*$", re.MULTILINE)
_TITLE = re.compile(r"^#\s+(.{1,40})$", re.MULTILINE)


@dataclass(frozen=True)
class Article:
    number: str  # 第4条
    heading: str  # 負担区分と負担係数
    text: str

    def as_excerpt(self) -> dict[str, str]:
        return {
            "article": self.number,
            "heading": self.heading,
            "text": self.text[:MAX_EXCERPT_CHARS],
        }


def split_articles(document: str) -> list[Article]:
    """「## 第N条（見出し）」ごとに分ける。条の前の前書き・附則は、条に含めない。"""
    marks = list(_HEADING.finditer(document))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(document)
        body = document[m.end() : end]
        body = re.split(r"^##\s", body, maxsplit=1, flags=re.MULTILINE)[0].strip()
        out.append(Article(m.group(1), m.group(2), body))
    return out


def document_title(document: str) -> str:
    m = _TITLE.search(document)
    return m.group(1).strip() if m else "規程"


def _grams(text: str) -> set[str]:
    s = re.sub(r"\s+", "", text)
    return {s[i : i + 2] for i in range(len(s) - 1)}


class PolicyRetriever(Protocol):
    def retrieve(self, question: str, top_k: int = 2) -> list[Article]: ...


class DocumentRetriever:
    """同梱の規程の文書から、質問に合う条を探す。"""

    def __init__(self, path: Path = DEFAULT_DOCUMENT_PATH) -> None:
        self._path = path
        self._articles: list[Article] | None = None
        self.title = "規程"
        self.policy_id = self.version = ""  # 文書の前書きにある、規程番号と版

    def articles(self) -> list[Article]:
        if self._articles is None:
            document = self._path.read_text(encoding="utf-8")
            self._articles, self.title = split_articles(document), document_title(document)
            pid = re.search(r"^- 規程番号:\s*(\S+)", document, flags=re.MULTILINE)
            ver = re.search(r"^- 版:\s*(\S+)", document, flags=re.MULTILINE)
            self.policy_id, self.version = (pid.group(1) if pid else ""), (
                ver.group(1) if ver else ""
            )
        return self._articles

    def retrieve(self, question: str, top_k: int = 2) -> list[Article]:
        q = question[:MAX_QUESTION_CHARS]
        direct = re.search(r"第\s*(\d{1,3})\s*条", q)  # 「第7条は？」のような、条の指定
        if direct:
            hit = [a for a in self.articles() if a.number == f"第{direct.group(1)}条"]
            if hit:
                return hit
        grams = _grams(q)
        if not grams:
            return []
        scored = []
        for order, a in enumerate(self.articles()):
            # 見出しとの一致を重く見る（「承認者は誰？」→ 第9条（承認））
            score = 3 * len(grams & _grams(a.heading)) + len(grams & _grams(a.text))
            if score > 0:
                scored.append((-score, order, a))
        return [a for _, _, a in sorted(scored)[: max(1, min(top_k, 3))]]
