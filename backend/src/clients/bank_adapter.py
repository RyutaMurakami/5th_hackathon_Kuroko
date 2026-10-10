"""bank-adapter の呼び出し（`kuroko-api` = sa-api から。幹事口座の入金の明細だけ）。"""

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import httpx


class BankAdapterError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class IncomingEntry:
    item_key: str
    date: date
    amount_yen: int
    counterparty_user_id: str | None  # 振込元。解決できなければ None


class BankAdapter(Protocol):
    async def incoming(
        self, *, user_id: str, date_from: date, date_to: date
    ) -> list[IncomingEntry]: ...


async def _id_token(audience: str) -> str:
    import google.auth.transport.requests
    from google.oauth2 import id_token

    return await asyncio.to_thread(
        id_token.fetch_id_token, google.auth.transport.requests.Request(), audience
    )


class HttpBankAdapter:
    def __init__(self, *, base_url: str, http: httpx.AsyncClient | None = None, token=_id_token):
        self._base = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=60)
        self._token = token

    async def incoming(self, *, user_id: str, date_from: date, date_to: date):
        try:
            res = await self._http.get(
                f"{self._base}/statements",
                params={
                    "user_id": user_id,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
                headers={"Authorization": f"Bearer {await self._token(self._base)}"},
            )
        except httpx.HTTPError as e:
            raise BankAdapterError(f"unreachable:{type(e).__name__}") from None
        if res.status_code != 200:
            raise BankAdapterError(f"bank_adapter_{res.status_code}")
        return [
            IncomingEntry(
                item_key=e["item_key"],
                date=date.fromisoformat(e["date"]),
                amount_yen=int(e["amount_yen"]),
                counterparty_user_id=e.get("counterparty_user_id"),
            )
            for e in res.json()["entries"]
            if e["direction"] == "in"
        ]
