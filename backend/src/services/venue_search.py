"""店の検索（`search_venues` ツールの本体。SPEC 4.1・9.9。TASKS B5・B18・B21）。

**コードが決まった手順で外部 API を呼ぶ**（LLM に何十回も呼ばせない）:
全員の最寄り駅（駅コード）→ 帰りやすさの計算（5駅ずつ）→ 候補駅ごとに Google Maps →
足切り・順位づけ。条件（人数・予算・食べられないもの・最寄り駅・幹事の条件）は、
**保存済みのデータだけ**から取る。ツールの引数（LLM が作る値）は、イベントの識別子だけで、
条件をすり替えられない。口コミ本文は、ここで捨てる（外部入力。隔離抽出を通すまで
エージェントに渡さない）。
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.clients.maps import Venue
from src.clients.memory_bank import MemoryStore
from src.db.events import EventStore
from src.models.event import Event, RsvpStatus
from src.models.venue import VenueCandidate
from src.services.access import AccessibleStation, RangeSearcher, search_accessible_stations
from src.services.memory_facts import read_scopes, records_by_venue, venue_key
from src.services.venue_ranking import (
    Constraints,
    MemoryRecord,
    Preferences,
    rank_venues,
)
from src.services.vocab import ATMOSPHERE_TAGS, GENRE_TAGS

logger = logging.getLogger(__name__)

MAX_STATIONS = 3  # 店を探す候補駅の数（最も遠い人の所要時間が短い駅から）
VENUES_PER_STATION = 10


class VenueFinder(Protocol):
    async def search_venues(self, query: str, *, max_results: int = 10) -> list[Venue]: ...


class EventNotFound(Exception):
    pass


@dataclass
class VenueSearchResult:
    ok: bool
    reason: str | None = None  # ok=False のとき: no_stations / no_common_station / no_venues
    proposals: list[VenueCandidate] = field(default_factory=list)
    used_max_minutes: int | None = None
    relaxed: bool = False
    excluded_count: int = 0
    excluded_reasons: list[str] = field(default_factory=list)  # 店名は出さず、理由の種類だけ

    def to_tool_result(self) -> dict[str, Any]:
        """エージェントに返す形。**口コミ本文・個人の情報は含まない**。"""
        return {
            "ok": self.ok,
            "reason": self.reason,
            "relaxed": self.relaxed,
            "used_max_minutes": self.used_max_minutes,
            "excluded_count": self.excluded_count,
            "proposals": [p.model_dump(mode="json") for p in self.proposals],
            "notice": (
                "アレルゲンは、店に確認してください。"
                "順位はコードが決めています（理由の文章だけを作ってください）。"
            ),
        }


class VenueSearch:
    def __init__(
        self,
        *,
        store: EventStore,
        stations: RangeSearcher,
        maps: VenueFinder,
        memory: dict[str, MemoryRecord] | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._store, self._stations, self._maps = store, stations, maps
        self._memory = memory or {}
        # 記憶（Memory Bank）。同じ店の過去の実績を引く（SPEC 9.8）
        self._memory_store = memory_store

    async def _recall(self, event: Event, venues: list[Venue]) -> dict[str, MemoryRecord]:
        """記憶から、候補の店と同じ名前の実績を引く。**順位の調整と、理由に添える文だけ**に使う。

        スコープは、イベントからコードが決める（LLM・利用者の値を使わない）。記憶が読めなくても、
        店の検索は続ける（記憶なしの順位になるだけ）。
        """
        if self._memory_store is None:
            return {}
        facts: list[str] = []
        try:
            for scope in read_scopes(event.sandbox, event.guest_owner_uid):
                facts += [f.fact for f in await self._memory_store.list_facts(scope)]
        except Exception:  # 記憶の失敗で、店の検索を止めない。本文はログに出さない
            logger.warning("memory recall failed; ranking without memory")
            return {}
        by_name = records_by_venue(facts)
        return {v.place_id: by_name[k] for v in venues if (k := venue_key(v.name)) in by_name}

    async def run(self, event_id: str) -> VenueSearchResult:
        event = self._store.get_event(event_id)
        if event is None or event.policy_snapshot is None:
            raise EventNotFound
        policy = event.policy_snapshot
        people = [
            p
            for p in self._store.list_participants(event_id)
            if p.attendance_confirmed or p.rsvp_status is RsvpStatus.ATTENDING
        ]
        codes = [
            p.preferences.nearest_station_code for p in people if p.preferences.nearest_station_code
        ]
        if not codes:
            return VenueSearchResult(False, "no_stations")

        access = await search_accessible_stations(
            self._stations,
            codes,
            max_min=policy.venue_max_travel_minutes,
            relax_step=policy.venue_relax_step_minutes,
            relax_limit=policy.venue_relax_limit_minutes,
            limit=MAX_STATIONS,
        )
        if not access.stations:
            return VenueSearchResult(
                False, "no_common_station", used_max_minutes=access.used_max_minutes, relaxed=True
            )

        wanted = Counter(t for p in people for t in p.preferences.request_tags)
        query_tag = next(
            (t for t, _ in wanted.most_common() if t in GENRE_TAGS + ATMOSPHERE_TAGS), ""
        )
        found: list[tuple[Venue, AccessibleStation]] = []
        for station in access.stations:
            query = " ".join(x for x in (station.name, "居酒屋", query_tag) if x)
            for venue in await self._maps.search_venues(query, max_results=VENUES_PER_STATION):
                # 口コミ本文は捨てる（外部入力）。ここから先に、原文は持ち越さない
                found.append((_without_reviews(venue), station))
        if not found:
            return VenueSearchResult(False, "no_venues", used_max_minutes=access.used_max_minutes)

        constraints = Constraints(
            party_size=len(people),
            hard_limit_per_person_yen=policy.hard_limit_per_person_yen,
            dietary_must=frozenset(d for p in people for d in p.preferences.dietary_must),
            required_tags=frozenset(event.plan_required_tags),
        )
        prefs = Preferences(
            request_tags=wanted,
            dietary_avoid=Counter(d for p in people for d in p.preferences.dietary_avoid),
        )
        ranked = rank_venues(
            found,
            constraints,
            prefs,
            memory=self._memory | await self._recall(event, [v for v, _ in found]),
            relaxed_to_minutes=access.used_max_minutes if access.relaxed else None,
        )
        if not ranked.proposals:
            return VenueSearchResult(
                False,
                "no_venues",
                used_max_minutes=access.used_max_minutes,
                relaxed=access.relaxed,
                excluded_count=len(ranked.excluded),
                excluded_reasons=sorted({r for _, r in ranked.excluded}),
            )
        return VenueSearchResult(
            True,
            proposals=ranked.proposals,
            used_max_minutes=access.used_max_minutes,
            relaxed=access.relaxed,
            excluded_count=len(ranked.excluded),
            excluded_reasons=sorted({r for _, r in ranked.excluded}),
        )


def _without_reviews(v: Venue) -> Venue:
    from dataclasses import replace

    return replace(v, review_snippets=())
