"""帰りやすさの計算 `search_accessible_stations`（SPEC 4.1・9.9。TASKS B18。**LLM は呼ばない**）。

みなさんの開催希望駅から、全員が所要時間の上限以内に着く駅（会場の候補になる駅）を探す。
駅すぱあと API の範囲探索は、起点を最大5つまでしか受けないので、**起点を5駅ずつに分けて探索し、
共通の駅を取る**。見つからなければ、規程（`venue_access`）の刻みで上限を緩める。
ツールの中で決まった回数だけ API を呼ぶ（LLM に何十回も呼ばせない）。
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from src.clients.ekispert import ReachableStation

GROUP_SIZE = 5


class RangeSearcher(Protocol):
    async def search_ranges(
        self, bases: list[str], upper_minutes: list[int], limit: int | None = None
    ) -> list[ReachableStation]: ...


@dataclass(frozen=True)
class AccessibleStation:
    name: str
    code: int
    max_minutes: int  # 最も遠い人の所要時間（「最も遠い人でも○分」）
    avg_minutes: float  # 人数で重みづけした平均


@dataclass
class AccessResult:
    stations: list[AccessibleStation] = field(default_factory=list)
    used_max_minutes: int = 0  # 実際に使った上限（緩めたなら、元より大きい）
    relaxed: bool = False  # 条件を緩めた（判断ログに残す）


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def search_accessible_stations(
    client: RangeSearcher,
    origins: list[str],
    *,
    max_min: int = 45,
    relax_step: int = 15,
    relax_limit: int = 75,
    limit: int = 20,
) -> AccessResult:
    """`origins` は、人ごとの開催希望駅の駅コード（同じ駅が複数いてよい）。

    `verify_station` で一意に決めたコードを渡す（あいまいな駅名は探索が失敗する）。
    """
    if not origins:
        return AccessResult()
    weights = Counter(origins)
    unique = list(dict.fromkeys(origins))
    groups = _chunks(unique, GROUP_SIZE)
    cache: dict[tuple[tuple[str, ...], int], list[ReachableStation]] = {}

    minutes = max_min
    while minutes <= relax_limit:
        per_group: list[dict[int, tuple[str, dict[str, int]]]] = []
        for group in groups:
            key = (tuple(group), minutes)
            if key not in cache:
                cache[key] = await client.search_ranges(group, [minutes] * len(group))
            per_group.append(
                {
                    s.code: (s.name, dict(zip(group, s.minutes, strict=False)))
                    for s in cache[key]
                    if len(s.minutes) == len(group)
                }
            )
        common = set.intersection(*(set(g) for g in per_group)) if per_group else set()
        if common:
            stations = []
            for code in common:
                name = per_group[0][code][0]
                times: dict[str, int] = {}
                for g in per_group:
                    times.update(g[code][1])
                total = sum(times[o] * weights[o] for o in unique)
                stations.append(
                    AccessibleStation(
                        name=name,
                        code=code,
                        max_minutes=max(times.values()),
                        avg_minutes=round(total / sum(weights.values()), 1),
                    )
                )
            stations.sort(key=lambda s: (s.max_minutes, s.avg_minutes, s.name))
            return AccessResult(stations[:limit], minutes, relaxed=minutes > max_min)
        if relax_step <= 0:
            break
        minutes += relax_step
    return AccessResult([], min(minutes, relax_limit), relaxed=True)
