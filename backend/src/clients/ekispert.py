"""駅すぱあと API MCP のクライアント（帰りやすさの計算。SPEC 4.1・9.9。TASKS B18）。

エンドポイントは MCP（Streamable HTTP）。呼ぶのは `kuroko-api` のコードだけで、LLM は直接呼ばない
（`search_accessible_stations` などは、コードが決まった回数だけ呼ぶ）。アクセスキーは Secret Manager
から環境変数で渡る。応答は外部入力として扱い、必要な値（駅名・分・料金）だけを取り出す。
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

URL = "https://api-mcp.ekispert.jp/mcp"
PROTOCOL = "2025-06-18"


class EkispertError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StationCheck:
    valid: bool  # 鉄道の駅として、1つに決まった
    canonical_name: str | None = None
    station_code: int | None = None
    candidates: tuple[str, ...] = ()  # 決まらなかったときの候補（駅名だけ）


@dataclass(frozen=True)
class RouteSummary:
    minutes: int  # 乗車 + 乗換・待ち + 徒歩
    transfers: int
    fare_yen: int | None


@dataclass(frozen=True)
class ReachableStation:
    name: str
    code: int
    minutes: tuple[int, ...]  # 起点ごとの所要時間（baseList の順）
    transfers: tuple[int, ...]


def _as_list(value: Any) -> list[Any]:
    """駅すぱあと API は、1件のときは配列でなくオブジェクトで返す。"""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _station_type(station: dict[str, Any]) -> str:
    t = station.get("Type")
    return t.get("text", "") if isinstance(t, dict) else str(t or "")


def parse_stations(result: dict[str, Any]) -> list[dict[str, Any]]:
    """鉄道（train）の駅だけ。バス・飛行機・船は使わない。"""
    points = _as_list((result.get("ResultSet") or {}).get("Point"))
    return [
        p["Station"]
        for p in points
        if isinstance(p.get("Station"), dict) and _station_type(p["Station"]) == "train"
    ]


def check_station(name: str, result: dict[str, Any]) -> StationCheck:
    stations = parse_stations(result)
    exact = [s for s in stations if s.get("Name") == name.removesuffix("駅")]
    pick = exact if len(exact) == 1 else (stations if len(stations) == 1 else [])
    if len(pick) == 1:
        s = pick[0]
        return StationCheck(True, s.get("Name"), int(s["code"]))
    return StationCheck(False, candidates=tuple(dict.fromkeys(s.get("Name", "") for s in stations)))


def parse_route(result: dict[str, Any]) -> RouteSummary | None:
    courses = _as_list((result.get("ResultSet") or {}).get("Course"))
    if not courses:
        return None
    course = courses[0]
    route = course.get("Route") or {}
    try:
        minutes = sum(int(route.get(k, 0)) for k in ("timeOnBoard", "timeOther", "timeWalk"))
        transfers = int(route.get("transferCount", 0))
    except (TypeError, ValueError):
        return None
    fare = next(
        (int(p["Oneway"]) for p in _as_list(course.get("Price")) if p.get("kind") == "FareSummary"),
        None,
    )
    return RouteSummary(minutes=minutes, transfers=transfers, fare_yen=fare)


def parse_ranges(result: dict[str, Any]) -> list[ReachableStation]:
    out = []
    for p in _as_list((result.get("ResultSet") or {}).get("Point")):
        station = p.get("Station") or {}
        if _station_type(station) != "train":
            continue
        costs = sorted(_as_list(p.get("Cost")), key=lambda c: int(c.get("baseIndex", 0)))
        try:
            out.append(
                ReachableStation(
                    name=station["Name"],
                    code=int(station["code"]),
                    minutes=tuple(int(c["Minute"]) for c in costs),
                    transfers=tuple(int(c.get("TransferCount", 0)) for c in costs),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _tool_error_code(text: str) -> str:
    """ツールのエラーの種類（本文は持たない）。あいまいな駅名は、駅コードで指定し直す必要がある。"""
    try:
        err = json.loads(text)
    except ValueError:
        return "tool_error"
    if "駅名が見つかりません" in str(err.get("message", "")):
        return "station_not_found"
    return f"tool_error_{err.get('status', '')}"


class EkispertClient:
    def __init__(self, *, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._http = http or httpx.AsyncClient(timeout=60)
        self._session: str | None = None

    def _headers(self) -> dict[str, str]:
        h = {
            "ekispert-api-access-key": self._key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session:
            h["mcp-session-id"] = self._session
        return h

    @staticmethod
    def _parse(res: httpx.Response) -> dict[str, Any]:
        if res.headers.get("content-type", "").startswith("text/event-stream"):
            for line in res.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:])
            raise EkispertError("empty_event_stream")
        return res.json()

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        try:
            return await self._http.post(URL, headers=self._headers(), json=body)
        except httpx.HTTPError as e:
            raise EkispertError(f"unreachable:{type(e).__name__}") from None

    async def _ensure_session(self) -> None:
        if self._session:
            return
        res = await self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "kuroko-api", "version": "0"},
                },
            }
        )
        if res.status_code != 200:
            raise EkispertError(
                f"initialize_{res.status_code}"
            )  # 本文（キーの断片を含みうる）は持たない
        self._session = res.headers.get("mcp-session-id")
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_session()
        res = await self._post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }
        )
        if res.status_code in (400, 404):  # セッション切れ。作り直して1回だけやり直す
            self._session = None
            await self._ensure_session()
            res = await self._post(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                }
            )
        if res.status_code != 200:
            raise EkispertError(f"tools_call_{res.status_code}")
        result = self._parse(res).get("result") or {}
        text = "".join(p.get("text", "") for p in result.get("content") or [])
        if result.get("isError"):
            raise EkispertError(_tool_error_code(text))
        try:
            return json.loads(text)
        except ValueError:
            raise EkispertError("unparsable_result") from None

    # ---- 公開 ----
    async def verify_station(self, name: str) -> StationCheck:
        return check_station(name, await self._call("ekispert_api_get_stations", {"name": name}))

    async def search_routes(self, origin: str, destination: str) -> RouteSummary | None:
        result = await self._call(
            "ekispert_api_search_routes",
            {"viaList": f"{origin}:{destination}", "sort": "time", "answerCount": 1},
        )
        return parse_route(result)

    async def search_ranges(
        self, bases: list[str], upper_minutes: list[int], limit: int | None = None
    ) -> list[ReachableStation]:
        if not 1 <= len(bases) <= 5 or len(bases) != len(upper_minutes):
            raise ValueError("bases は1〜5件で、upper_minutes と同じ数")
        # 起点は駅コード（`verify_station` で一意に決めたもの）を渡す。
        # あいまいな駅名は探索が失敗する
        args: dict[str, Any] = {"baseList": bases, "upperMinutes": upper_minutes}
        if limit:
            args["limit"] = limit
        return parse_ranges(await self._call("ekispert_api_search_ranges", args))
