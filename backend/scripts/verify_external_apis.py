"""外部 API（駅すぱあと・Google Maps）の実機での確認（TASKS B18・O6。お金は動かない）。

キーは Secret Manager から読み、表示しない。
使い方（`backend/` で）: uv run python scripts/verify_external_apis.py
"""

import asyncio
import subprocess
import time

from src.clients.ekispert import EkispertClient
from src.clients.maps import MapsClient
from src.services.access import search_accessible_stations

PROJECT = "kuroko-509311"


def secret(name: str) -> str:
    return subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={name}",
         f"--project={PROJECT}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


async def timed(label: str, coro):
    t0 = time.time()
    result = await coro
    print(f"  [{time.time() - t0:5.2f}s] {label}")
    return result


async def main() -> None:
    eki = EkispertClient(api_key=secret("ekispert-api-key"))
    print("== 駅すぱあと")
    for name in ("渋谷", "新宿駅", "ほげほげ駅", "大宮"):
        c = await timed(f"verify_station({name})", eki.verify_station(name))
        print(f"      → valid={c.valid} 正式名={c.canonical_name} 候補={list(c.candidates)[:4]}")
    r = await timed("search_routes(新宿→品川)", eki.search_routes("新宿", "品川"))
    print(f"      → {r.minutes}分・乗換{r.transfers}回・{r.fare_yen}円")

    # 人ごとの最寄り駅。あいまいな駅名（大宮 = 埼玉県・京都府）は、都道府県つきで指定し直す
    names = ["新宿", "横浜", "大宮(埼玉県)", "千葉", "立川", "町田", "浦和"]
    codes = []
    for name in names:
        check = await eki.verify_station(name)
        assert check.valid, f"{name}: 駅を一意に決められない {check.candidates}"
        codes.append(str(check.station_code))
    print(f"  駅コードに変換: {dict(zip(names, codes, strict=True))}")
    res = await timed(
        f"search_accessible_stations({len(codes)}駅 → 45分以内。5駅ずつ2回に分けて共通駅を取る)",
        search_accessible_stations(eki, codes, max_min=45, limit=5),
    )
    print(f"      → 上限 {res.used_max_minutes}分（緩めた={res.relaxed}）")
    for s in res.stations:
        print(f"         {s.name}: 最も遠い人 {s.max_minutes}分・平均 {s.avg_minutes}分")

    print("== Google Maps（Places API）")
    maps = MapsClient(api_key=secret("maps-api-key"))
    venues = await timed(
        "search_venues(渋谷 居酒屋 個室)", maps.search_venues("渋谷 居酒屋 個室", max_results=5)
    )
    for v in venues:
        price = f"{v.price_min_yen}〜{v.price_max_yen}円" if v.price_min_yen else "価格不明"
        reviews = len(v.review_snippets)
        print(
            f"      {v.name} / 評価 {v.rating}（{v.rating_count}件）/ {price} / 口コミ {reviews}件"
        )


if __name__ == "__main__":
    asyncio.run(main())
