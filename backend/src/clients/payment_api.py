"""payment-api の呼び出し（`kuroko-api` = sa-api から。ARCHITECTURE 4.3）。

支払いの開始だけを呼ぶ。委任状の署名・取り消し・銀行の認可は Slack 由来の経路（sa-gateway）で、
ここからは呼べない。口座番号・トークンは扱わない。
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class PaymentApiError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PaymentOutcome:
    payment_id: str
    status: str  # awaiting_bank_approval / blocked / failed ...
    block_reason: str | None


class PaymentApi(Protocol):
    async def start_payment(
        self,
        *,
        payment_id: str,
        event_id: str,
        payer_user_id: str,
        payee_user_id: str,
        amount_yen: int,
        checkout_jwt: str,
        checkout_hash: str,
    ) -> PaymentOutcome: ...


async def _id_token(audience: str) -> str:
    import google.auth.transport.requests
    from google.oauth2 import id_token

    return await asyncio.to_thread(
        id_token.fetch_id_token, google.auth.transport.requests.Request(), audience
    )


class HttpPaymentApi:
    def __init__(self, *, base_url: str, http: httpx.AsyncClient | None = None, token=_id_token):
        self._base = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=60)
        self._token = token

    async def start_payment(self, **body: Any) -> PaymentOutcome:
        try:
            res = await self._http.post(
                f"{self._base}/payments",
                json=body,
                headers={"Authorization": f"Bearer {await self._token(self._base)}"},
            )
        except httpx.HTTPError as e:
            raise PaymentApiError(f"unreachable:{type(e).__name__}") from None
        if res.status_code != 201:
            raise PaymentApiError(f"payment_api_{res.status_code}")  # 本文は持たない
        data = res.json()
        return PaymentOutcome(
            payment_id=data["payment_id"],
            status=data["status"],
            block_reason=data.get("block_reason"),
        )
