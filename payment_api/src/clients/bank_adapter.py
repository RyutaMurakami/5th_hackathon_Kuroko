"""bank-adapter（銀行への窓口）のクライアント。仮名の user_id・金額・冪等キーだけを渡す。

口座番号・アクセストークンは bank-adapter の中だけにあり、ここには届かない（SPEC 10章）。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx


class BankAdapterError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TransferInfo:
    transfer_id: str
    status: str
    approval_expires_at: datetime | None


class BankAdapter(Protocol):
    def is_authorized(self, user_id: str) -> bool:
        """この参加者の銀行の利用の認可が有効か。"""

    def create_transfer(
        self, *, payer_user_id: str, payee_user_id: str, amount_yen: int, idempotency_key: str
    ) -> TransferInfo: ...


class HttpBankAdapter:
    def __init__(self, *, base_url: str, http: httpx.Client | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        import google.auth.transport.requests
        from google.oauth2 import id_token

        token = id_token.fetch_id_token(google.auth.transport.requests.Request(), self._base)
        return {"Authorization": f"Bearer {token}"}

    def _post(self, path: str, body: dict) -> httpx.Response:
        try:
            return self._http.post(self._base + path, json=body, headers=self._headers())
        except httpx.HTTPError as e:
            raise BankAdapterError("bank_adapter_unreachable") from e

    def is_authorized(self, user_id: str) -> bool:
        res = self._post("/authorizations", {"user_id": user_id})
        if res.status_code == 404:
            return False
        if res.status_code != 200:
            raise BankAdapterError(f"bank_adapter_{res.status_code}")
        return bool(res.json().get("authorized"))

    def create_transfer(
        self, *, payer_user_id: str, payee_user_id: str, amount_yen: int, idempotency_key: str
    ) -> TransferInfo:
        res = self._post(
            "/transfers",
            {
                "payer_user_id": payer_user_id,
                "payee_user_id": payee_user_id,
                "amount_yen": amount_yen,
                "idempotency_key": idempotency_key,
            },
        )
        if res.status_code != 201:
            raise BankAdapterError(f"bank_adapter_{res.status_code}")
        data = res.json()
        expires = data.get("approval_expires_at")
        return TransferInfo(
            transfer_id=data["transfer_id"],
            status=data["status"],
            approval_expires_at=datetime.fromisoformat(expires) if expires else None,
        )
