"""bank-adapter（銀行への窓口）のクライアント。仮名の user_id・金額・冪等キーだけを渡す。

口座番号・アクセストークンは bank-adapter の中だけにあり、ここには届かない（SPEC 10章）。
"""

from dataclasses import dataclass
from datetime import date, datetime
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
    simulated: bool = False  # デモで代行した振込（本人の承認は要らない。SPEC 8.10）


@dataclass(frozen=True)
class OutgoingEntry:
    item_key: str
    date: date
    amount_yen: int
    counterparty_user_id: str | None  # 振込先。名義から bank-adapter が仮名IDに解決したもの


class BankAdapter(Protocol):
    def is_authorized(self, user_id: str) -> bool:
        """この参加者の銀行の利用の認可が有効か。"""

    def create_transfer(
        self, *, payer_user_id: str, payee_user_id: str, amount_yen: int, idempotency_key: str
    ) -> TransferInfo: ...

    def get_transfer(self, transfer_id: str) -> TransferInfo:
        """振込依頼の状況（awaiting_approval / processed / expired / failed）。"""

    def outgoing(self, user_id: str, date_from: date, date_to: date) -> list[OutgoingEntry]:
        """本人の口座の出金明細（入金の確認の元。SPEC 8.6）。"""


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
            simulated=bool(data.get("simulated")),
        )

    def get_transfer(self, transfer_id: str) -> TransferInfo:
        try:
            res = self._http.get(f"{self._base}/transfers/{transfer_id}", headers=self._headers())
        except httpx.HTTPError as e:
            raise BankAdapterError("bank_adapter_unreachable") from e
        if res.status_code != 200:
            raise BankAdapterError(f"bank_adapter_{res.status_code}")
        data = res.json()
        expires = data.get("approval_expires_at")
        return TransferInfo(
            transfer_id=data["transfer_id"],
            status=data["status"],
            approval_expires_at=datetime.fromisoformat(expires) if expires else None,
            simulated=bool(data.get("simulated")),
        )

    def outgoing(self, user_id: str, date_from: date, date_to: date) -> list[OutgoingEntry]:
        try:
            res = self._http.get(
                f"{self._base}/statements",
                params={
                    "user_id": user_id,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
                headers=self._headers(),
            )
        except httpx.HTTPError as e:
            raise BankAdapterError("bank_adapter_unreachable") from e
        if res.status_code != 200:
            raise BankAdapterError(f"bank_adapter_{res.status_code}")
        return [
            OutgoingEntry(
                item_key=e["item_key"],
                date=date.fromisoformat(e["date"]),
                amount_yen=int(e["amount_yen"]),
                counterparty_user_id=e.get("counterparty_user_id"),
            )
            for e in res.json()["entries"]
            if e["direction"] == "out"
        ]
