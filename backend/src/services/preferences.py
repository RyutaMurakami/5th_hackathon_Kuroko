"""参加者の好みの取り込み（SPEC 3章 Participant.preferences・9.9。TASKS B26）。

自由記述は、**統括エージェントに原文を渡さず**、隔離抽出（`extract_free_text`）で固定の語彙に変換する。
最寄り駅は、駅すぱあとで**一意の鉄道の駅に確かめ**、駅コードで持つ（あいまいな駅名は採用しない）。
入力欄の違い（食べられないもの／苦手）は、**コードが**ハード制約（`dietary_must`）・ソフト制約
（`dietary_avoid`）に振り分ける（LLM の出力からは決まらない）。原文は保存しない。
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from src.clients.ekispert import EkispertError, StationCheck
from src.db.events import EventStore
from src.models.event import Preferences
from src.services.extract import (
    ExtractRunner,
    PreferencesExtract,
    _clean_station,
    extract_free_text,
)
from src.services.vocab import DIETARY


class StationVerifier(Protocol):
    async def verify_station(self, name: str) -> StationCheck: ...


@dataclass(frozen=True)
class PreferencesResult:
    saved: bool
    station_status: Literal["verified", "ambiguous", "not_found", "not_given", "error"]
    candidates: tuple[str, ...] = ()  # あいまいなときの候補（駅名だけ）。本人に選び直してもらう


class PreferenceIntake:
    def __init__(
        self, *, store: EventStore, runner: ExtractRunner | None, stations: StationVerifier
    ):
        self._store, self._runner, self._stations = store, runner, stations

    async def record_form(
        self, event_id: str, user_id: str, *, station: str, dislikes: str
    ) -> PreferencesResult:
        """出欠のカードの入力欄（最寄り駅・苦手な食べ物の2欄）から取り込む（SPEC 7.7）。

        - 最寄り駅: 欄が分かれているので、LLM を通さない。駅名の形を検査し、駅すぱあとで
          **一意の駅に決まったときだけ**、駅コードで持つ（決まらなければ、いまの値のまま）
        - 苦手な食べ物: 自由記述なので、隔離抽出で固定の語彙に落とす。加えて、語彙の語が
          そのまま書かれていれば拾う（隔離抽出が使えないとき・失敗したときの補い。決定論的）
        - 原文は保存しない・ログに出さない・統括エージェントに渡さない
        """
        person = next(
            (p for p in self._store.list_participants(event_id) if p.user_id == user_id), None
        )
        if person is None:
            return PreferencesResult(False, "not_given")
        current = person.preferences
        code, status, candidates = current.nearest_station_code, "not_given", ()
        name = _clean_station(station)
        if station.strip() and name is None:
            status = "not_found"  # 駅名の形でない（文・記号・数字など）
        elif name:
            try:
                check = await self._stations.verify_station(name)
            except EkispertError:
                check, status = None, "error"
            if check is not None and check.valid:
                code, status = str(check.station_code), "verified"
            elif check is not None:
                status = "ambiguous" if check.candidates else "not_found"
                candidates = check.candidates
        found: list[str] = []
        if dislikes.strip():
            if self._runner is not None:
                extracted = await extract_free_text(self._runner, dislikes, "preferences")
                assert isinstance(extracted, PreferencesExtract)
                found += extracted.dislikes
            found += [w for w in DIETARY if w in dislikes]
        prefs = Preferences(
            nearest_station_code=code,
            dietary_must=list(current.dietary_must),
            dietary_avoid=[*current.dietary_avoid, *found],  # 「苦手」の欄なので、ソフト制約
            request_tags=list(current.request_tags),
        )  # 語彙にない値・重複は、モデルの検証が捨てる
        self._store.save_participant(event_id, person.model_copy(update={"preferences": prefs}))
        return PreferencesResult(True, status, candidates)  # type: ignore[arg-type]

    async def record(
        self,
        event_id: str,
        user_id: str,
        *,
        free_text: str,
        field: Literal["dietary_must", "dietary_avoid"],
    ) -> PreferencesResult:
        """`field` は、本人が書いた入力欄（食べられないもの欄／苦手欄）。コードが決める。"""
        person = next(
            (p for p in self._store.list_participants(event_id) if p.user_id == user_id), None
        )
        if person is None:
            return PreferencesResult(False, "not_given")
        if self._runner is None:
            return PreferencesResult(False, "not_given")
        extracted = await extract_free_text(self._runner, free_text, "preferences")
        assert isinstance(extracted, PreferencesExtract)
        current = person.preferences
        station_code, status, candidates = current.nearest_station_code, "not_given", ()
        if extracted.nearest_station:
            try:
                check = await self._stations.verify_station(extracted.nearest_station)
            except EkispertError:
                check, status = None, "error"
            if check is not None and check.valid:
                station_code, status = str(check.station_code), "verified"
            elif check is not None:
                status = "ambiguous" if check.candidates else "not_found"
                candidates = check.candidates
        merged = {
            "dietary_must": list(current.dietary_must),
            "dietary_avoid": list(current.dietary_avoid),
        }
        merged[field] = [*merged[field], *extracted.dislikes]  # 振り分けはコード（入力欄）が決める
        prefs = Preferences(
            nearest_station_code=station_code,
            dietary_must=merged["dietary_must"],
            dietary_avoid=merged["dietary_avoid"],
            request_tags=[*current.request_tags, *extracted.preferences],
        )  # 語彙にない値は、モデルの検証が捨てる
        self._store.save_participant(event_id, person.model_copy(update={"preferences": prefs}))
        return PreferencesResult(True, status, candidates)  # type: ignore[arg-type]
