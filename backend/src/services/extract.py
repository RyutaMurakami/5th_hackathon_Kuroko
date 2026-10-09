"""隔離抽出の呼び出しと、出力の検証（SPEC 4.1 `extract_free_text`・10章。TASKS B20・B26）。

参加者の自由記述・口コミ本文・振り返りのコメントは、**ツールを持たない別のエージェント**
（`extract-agent`。Agent Gateway の入口を通る）で、固定の語彙・形に変換する。
- 用途（`mode`: `preferences` / `feedback`）は**コードが決める**。入力からは変えられない
- 統括エージェントには、**原文ではなく、この抽出後の値だけ**を渡す。原文は保存せず、ログにも出さない
- エージェントの出力は、**API 側で、もう一度**型・語彙・長さを検証する（正は API 側）。
  外れた値は捨て、**失敗・ブロック・形の違いは「抽出結果なし」**（空の結果）にする
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from src.clients.agent_runtime import AgentRuntimeClient, AgentRuntimeError
from src.services.vocab import CONCERNS, DIETARY, LIKED, REQUEST_TAGS, only_vocab

logger = logging.getLogger(__name__)

Mode = Literal["preferences", "feedback"]
MAX_INPUT_CHARS = 500
MAX_STATION_CHARS = 15
# 駅名として許す文字（数字は許さない）。大宮(埼玉県) のような括弧つきの形を含む
_STATION = re.compile(r"^[ぁ-んァ-ヶー一-龥々A-Za-z()（）ヶ ]+$")
# 文に特有の語（駅名には出てこない）。命令文・説明文を駅名として通さない。
# **最終的な判定は、駅すぱあとでの照合（実在する一意の駅だけを採用）**で、これは手前の絞り込み
_SENTENCE_WORDS = ("を", "して", "ください", "ます", "です", "ない", "こと", "ように", "から")


@dataclass(frozen=True)
class PreferencesExtract:
    dislikes: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    nearest_station: str | None = None


@dataclass(frozen=True)
class FeedbackExtract:
    liked: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


def _clean_station(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > MAX_STATION_CHARS or not _STATION.match(name):
        return None
    if any(w in name for w in _SENTENCE_WORDS):
        return None
    return name


def _strings(value: Any) -> list[str]:
    """文字列だけの配列。配列でなければ、空。"""
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def validate_preferences(raw: Any) -> PreferencesExtract:
    if not isinstance(raw, dict):
        return PreferencesExtract()
    return PreferencesExtract(
        dislikes=only_vocab(_strings(raw.get("dislikes")), DIETARY),
        preferences=only_vocab(_strings(raw.get("preferences")), REQUEST_TAGS),
        nearest_station=_clean_station(raw.get("nearest_station")),
    )


def validate_feedback(raw: Any) -> FeedbackExtract:
    if not isinstance(raw, dict):
        return FeedbackExtract()
    return FeedbackExtract(
        liked=only_vocab(_strings(raw.get("liked")), LIKED),
        concerns=only_vocab(_strings(raw.get("concerns")), CONCERNS),
    )


class ExtractRunner(Protocol):
    async def run(self, mode: Mode, text: str) -> Any:
        """エージェントの出力（JSON をパースしたもの）。失敗は例外。"""


class AgentRuntimeExtractRunner:
    """`extract-agent` を、1回ごとに新しいセッションで呼ぶ（会話の記憶を持たせない）。"""

    def __init__(self, client: AgentRuntimeClient) -> None:
        self._client = client

    async def run(self, mode: Mode, text: str) -> Any:
        message = json.dumps({"mode": mode, "text": text[:MAX_INPUT_CHARS]}, ensure_ascii=False)
        session = await self._client.create_session("extract")
        reply = await self._client.stream_query(
            user_id="extract", session_id=session, message=message
        )
        return json.loads(reply)


async def extract_free_text(
    runner: ExtractRunner, raw_text: str, mode: Mode
) -> PreferencesExtract | FeedbackExtract:
    """自由記述を、固定の語彙・形に変換する。**どんな失敗も「抽出結果なし」**（空の結果）にする。"""
    empty = PreferencesExtract() if mode == "preferences" else FeedbackExtract()
    if not raw_text.strip():
        return empty
    try:
        raw = await runner.run(mode, raw_text[:MAX_INPUT_CHARS])
    except (AgentRuntimeError, ValueError):
        # 原文はログに出さない。ブロック（Gateway）・タイムアウト・壊れた出力は、すべて抽出結果なし
        logger.warning("extract failed: mode=%s", mode)
        return empty
    return validate_preferences(raw) if mode == "preferences" else validate_feedback(raw)
