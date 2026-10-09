"""駅すぱあと API MCP のクライアントと、帰りやすさの計算（B18）。応答の形は実機のもの。"""

import json

import httpx
import pytest

from src.clients.ekispert import (
    EkispertClient,
    EkispertError,
    ReachableStation,
    check_station,
    parse_ranges,
    parse_route,
)
from src.services.access import search_accessible_stations

SHIBUYA = {"ResultSet": {"Point": [
    {"Station": {"code": "22715", "Name": "渋谷", "Type": "train"}},
    {"Station": {"code": "859552", "Name": "渋谷／会津バス",
                 "Type": {"text": "bus", "detail": "local"}}},
]}}  # fmt: skip


def test_station_check_uses_trains_only_and_exact_names():
    ok = check_station("渋谷", SHIBUYA)
    assert ok.valid and ok.canonical_name == "渋谷" and ok.station_code == 22715
    assert check_station("渋谷駅", SHIBUYA).valid  # 末尾の「駅」は許す
    unknown = check_station("ほげほげ駅", {"ResultSet": {"apiVersion": "1"}})  # 実機: 0件
    assert not unknown.valid and unknown.candidates == ()
    two = {"ResultSet": {"Point": [
        {"Station": {"code": "1", "Name": "大宮", "Type": "train"}},
        {"Station": {"code": "2", "Name": "大宮", "Type": "train"}},
    ]}}  # fmt: skip
    assert not check_station("大宮", two).valid  # 一意に決まらなければ、推測しない


def test_a_single_result_comes_as_an_object_not_a_list():
    single = {"ResultSet": {"Point": {"Station": {"code": "1", "Name": "新宿", "Type": "train"}}}}
    assert check_station("新宿", single).valid


def test_route_summary_adds_on_board_transfer_and_walk_time_and_reads_the_fare():
    result = {"ResultSet": {"Course": [{
        "Price": [{"kind": "Fare", "Oneway": "260"}, {"kind": "FareSummary", "Oneway": "260"}],
        "Route": {"timeOnBoard": "19", "timeOther": "4", "timeWalk": "1", "transferCount": "2"},
    }]}}  # fmt: skip
    r = parse_route(result)
    assert (r.minutes, r.transfers, r.fare_yen) == (24, 2, 260)
    assert parse_route({"ResultSet": {}}) is None


def test_ranges_are_parsed_per_origin_in_base_order():
    result = {"ResultSet": {"Point": [
        {"Station": {"code": "22916", "Name": "原宿", "Type": "train"},
         "Cost": [{"baseIndex": "2", "Minute": "38", "TransferCount": "1"},
                  {"baseIndex": "1", "Minute": "7", "TransferCount": "0"}]},
        {"Station": {"code": "9", "Name": "バス停", "Type": "bus"}, "Cost": []},
    ]}}  # fmt: skip
    (s,) = parse_ranges(result)
    assert s.name == "原宿" and s.minutes == (7, 38) and s.transfers == (0, 1)


# ---------------- MCP クライアント ----------------
def mcp_server(tool_results: dict, calls: list, expire_once=False):
    state = {"expired": False}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((body.get("method"), request.headers.get("ekispert-api-access-key")))
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}},
                                  headers={"mcp-session-id": "S1"})  # fmt: skip
        if body["method"].startswith("notifications/"):
            return httpx.Response(202)
        if expire_once and not state["expired"]:
            state["expired"] = True
            return httpx.Response(404)
        name = body["params"]["name"]
        text = json.dumps(tool_results[name], ensure_ascii=False)
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"content": [{"type": "text", "text": text}]},
        }
        sse = f"event: message\ndata: {json.dumps(message)}\n\n"
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_client_handles_the_mcp_handshake_and_sse_responses():
    calls: list = []
    client = EkispertClient(
        api_key="KEY", http=mcp_server({"ekispert_api_get_stations": SHIBUYA}, calls)
    )
    assert (await client.verify_station("渋谷")).valid
    assert [c[0] for c in calls] == ["initialize", "notifications/initialized", "tools/call"]
    assert all(c[1] == "KEY" for c in calls)
    await client.verify_station("渋谷")  # セッションを使い回す
    assert [c[0] for c in calls].count("initialize") == 1


async def test_an_expired_session_is_recreated_once():
    calls: list = []
    client = EkispertClient(
        api_key="K",
        http=mcp_server({"ekispert_api_get_stations": SHIBUYA}, calls, expire_once=True),
    )
    assert (await client.verify_station("渋谷")).valid
    assert [c[0] for c in calls].count("initialize") == 2


async def test_errors_never_contain_the_response_body_or_key():
    def handler(request):
        return httpx.Response(403, text="bad key SECRETKEY123")

    client = EkispertClient(
        api_key="SECRETKEY123", http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(EkispertError) as e:
        await client.verify_station("渋谷")
    assert "SECRETKEY123" not in str(e.value) and e.value.code == "initialize_403"


async def test_range_search_validates_its_arguments():
    client = EkispertClient(api_key="K", http=mcp_server({}, []))
    with pytest.raises(ValueError):
        await client.search_ranges(["a"] * 6, [30] * 6)  # 起点は5つまで
    with pytest.raises(ValueError):
        await client.search_ranges(["a", "b"], [30])


# ---------------- 帰りやすさの計算 ----------------
class FakeRanges:
    """起点ごとの所要時間の表から、範囲探索の応答を作る（分が上限以内の駅だけ）。"""

    def __init__(self, table: dict[str, dict[str, int]]):
        self.table, self.calls = table, []  # table[駅名][起点] = 分

    async def search_ranges(self, bases, upper_minutes, limit=None):
        self.calls.append((tuple(bases), upper_minutes[0]))
        out = []
        for code, (station, times) in enumerate(self.table.items(), start=1):
            if all(times[b] <= m for b, m in zip(bases, upper_minutes, strict=True)):
                out.append(ReachableStation(station, code, tuple(times[b] for b in bases),
                                            tuple(0 for _ in bases)))  # fmt: skip
        return out


ORIGINS = ["新宿", "横浜", "大宮", "千葉", "立川", "町田", "浦和"]  # 7駅 → 5 + 2 に分かれる
TABLE = {
    "渋谷": dict(zip(ORIGINS, [7, 25, 38, 40, 30, 35, 36], strict=True)),
    "東京": dict(zip(ORIGINS, [14, 30, 30, 35, 40, 50, 28], strict=True)),  # 町田が遠い
    "品川": dict(zip(ORIGINS, [20, 15, 40, 45, 50, 55, 44], strict=True)),
}


async def test_origins_are_split_into_groups_of_five_and_the_common_stations_are_taken():
    client = FakeRanges(TABLE)
    r = await search_accessible_stations(client, ORIGINS, max_min=45)
    assert [c[0] for c in client.calls] == [tuple(ORIGINS[:5]), tuple(ORIGINS[5:])]
    # 45分以内で全員が着くのは 渋谷（最大40分）だけ。東京は町田が50分、品川は立川が50分
    assert [(s.name, s.max_minutes) for s in r.stations] == [("渋谷", 40)]
    assert r.used_max_minutes == 45 and not r.relaxed


async def test_the_limit_is_relaxed_in_steps_when_no_station_is_common():
    tight = {k: v for k, v in TABLE.items() if k != "渋谷"}
    client = FakeRanges(tight)
    r = await search_accessible_stations(client, ORIGINS, max_min=45, relax_step=15, relax_limit=75)
    assert r.relaxed and r.used_max_minutes == 60  # 60分で 東京（最大50分）と 品川（最大55分）
    assert [s.name for s in r.stations] == ["東京", "品川"]  # 最も遠い人が近い順
    assert [s.max_minutes for s in r.stations] == [50, 55]


async def test_no_common_station_even_after_relaxing_returns_empty():
    impossible = {"遠い駅": {o: 200 for o in ORIGINS}}
    r = await search_accessible_stations(FakeRanges(impossible), ORIGINS, max_min=45)
    assert r.stations == [] and r.relaxed and r.used_max_minutes == 75


async def test_the_average_is_weighted_by_the_number_of_people_per_station():
    origins = ["新宿", "新宿", "新宿", "横浜"]  # 3人が新宿、1人が横浜
    table = {"渋谷": {"新宿": 7, "横浜": 25}}
    r = await search_accessible_stations(FakeRanges(table), origins, max_min=45)
    assert r.stations[0].avg_minutes == round((7 * 3 + 25) / 4, 1) == 11.5
    assert r.stations[0].max_minutes == 25


async def test_identical_calls_hit_the_cache_within_one_search():
    client = FakeRanges(TABLE)
    await search_accessible_stations(client, ORIGINS, max_min=45)
    assert len(client.calls) == 2  # グループごとに1回ずつ（緩める必要がなければ増えない）


async def test_empty_origins_return_nothing_without_calling_the_api():
    client = FakeRanges(TABLE)
    assert (await search_accessible_stations(client, [])).stations == []
    assert client.calls == []


async def test_tool_errors_are_classified_without_keeping_the_message():
    def server(message):
        def handler(request):
            body = json.loads(request.content)
            if body["method"] == "initialize":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})
            if body["method"].startswith("notifications/"):
                return httpx.Response(202)
            content = [{"type": "text", "text": json.dumps(message, ensure_ascii=False)}]
            err = {"jsonrpc": "2.0", "id": 2, "result": {"isError": True, "content": content}}
            return httpx.Response(200, json=err)

        return EkispertClient(
            api_key="K", http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )

    with pytest.raises(EkispertError) as e:
        await server({"status": 400, "message": "駅名が見つかりません。(大宮)"}).search_ranges(
            ["大宮"], [45]
        )
    assert e.value.code == "station_not_found" and "大宮" not in str(e.value)
    with pytest.raises(EkispertError) as e:
        await server({"status": 500, "message": "boom"}).search_ranges(["1"], [45])
    assert e.value.code == "tool_error_500"
