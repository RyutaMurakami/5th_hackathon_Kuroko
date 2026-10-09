"""Google Maps Platform（Places API (New)）の店舗検索（SPEC 4.1 `search_venues`・9.9。TASKS B18）。

呼ぶのは `kuroko-api` のコードだけ。キーは Secret Manager から環境変数で渡り、Places API だけに
制限してある。**口コミ本文は外部入力**（攻撃文が混ざりうる）なので、エージェントには原文を渡さず、
隔離抽出（`extract-agent`）を通した値だけを使う。ここは、取り出して持つだけ。
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ",".join(
    f"places.{f}"
    for f in (
        "id",
        "displayName",
        "formattedAddress",
        "rating",
        "userRatingCount",
        "priceLevel",
        "priceRange",
        "reviews.text.text",
        "googleMapsUri",
        "businessStatus",
    )
)


class MapsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Venue:
    place_id: str
    name: str
    address: str
    rating: float | None
    rating_count: int
    price_level: str | None  # PRICE_LEVEL_MODERATE など
    price_min_yen: int | None  # 1人あたりの目安（Google の推定。取れない店もある）
    price_max_yen: int | None
    maps_uri: str | None
    # 口コミ本文（**外部入力。原文のままエージェントに渡さない**。隔離抽出を通す）
    review_snippets: tuple[str, ...] = field(default=(), repr=False)


def _money(value: dict[str, Any] | None) -> int | None:
    try:
        return int(value["units"]) if value and value.get("currencyCode") == "JPY" else None
    except (KeyError, TypeError, ValueError):
        return None


def parse_venues(result: dict[str, Any]) -> list[Venue]:
    venues = []
    for p in result.get("places") or []:
        if p.get("businessStatus") not in (None, "OPERATIONAL"):
            continue  # 閉業・休業中の店は出さない
        price = p.get("priceRange") or {}
        venues.append(
            Venue(
                place_id=p["id"],
                name=(p.get("displayName") or {}).get("text", ""),
                address=p.get("formattedAddress", ""),
                rating=p.get("rating"),
                rating_count=int(p.get("userRatingCount") or 0),
                price_level=p.get("priceLevel"),
                price_min_yen=_money(price.get("startPrice")),
                price_max_yen=_money(price.get("endPrice")),
                maps_uri=p.get("googleMapsUri"),
                review_snippets=tuple(
                    t for r in p.get("reviews") or [] if (t := (r.get("text") or {}).get("text"))
                ),
            )
        )
    return venues


class MapsClient:
    def __init__(self, *, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._http = http or httpx.AsyncClient(timeout=30)

    async def search_venues(self, query: str, *, max_results: int = 10) -> list[Venue]:
        """「<駅名> 居酒屋 個室」のような検索。結果の足切り・順位づけはコード（B5）が行う。"""
        try:
            res = await self._http.post(
                URL,
                headers={
                    "X-Goog-Api-Key": self._key,
                    "X-Goog-FieldMask": FIELDS,
                    "Content-Type": "application/json",
                },
                json={
                    "textQuery": query,
                    "languageCode": "ja",
                    "regionCode": "JP",
                    "maxResultCount": max(1, min(max_results, 20)),
                },
            )
        except httpx.HTTPError as e:
            raise MapsError(f"unreachable:{type(e).__name__}") from None
        if res.status_code != 200:
            raise MapsError(f"places_{res.status_code}")  # 本文（キーの断片を含みうる）は持たない
        return parse_venues(res.json())
