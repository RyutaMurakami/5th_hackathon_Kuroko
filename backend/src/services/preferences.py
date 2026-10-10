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
from src.services.extract import ExtractRunner, PreferencesExtract, extract_free_text


class StationVerifier(Protocol):
    async def verify_station(self, name: str) -> StationCheck: ...


@dataclass(frozen=True)
class PreferencesResult:
    saved: bool
    station_status: Literal["verified", "ambiguous", "not_found", "not_given", "error"]
    candidates: tuple[str, ...] = ()  # あいまいなときの候補（駅名だけ）。本人に選び直してもらう


class PreferenceIntake:
    def __init__(self, *, store: EventStore, runner: ExtractRunner, stations: StationVerifier):
        self._store, self._runner, self._stations = store, runner, stations

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
