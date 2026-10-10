"""sunabar（GMOあおぞらネット銀行の銀行APIサンドボックス）のクライアント。

実機で確かめた仕様（docs/guides/h25_sunabar_setup.md 4-0）:
- 認証は口座ごとのアクセストークン（`x-access-token`）。OAuth の認可の流れは無い
- 銀行コードは 0310、口座番号は7桁、支店名は半角カナ（301: ｳﾐ、302: ﾆｼﾞ）
- 振込依頼の受付は HTTP 201・resultCode "2"（未完了。承認は銀行のサービスサイトで人が行う）
- 同じ Idempotency-Key で再送しても別の受付番号が振られる（重複の防止は呼び出し側＝services/）
- 状況照会は承認前に 0件で返る。明細は 入金 transactionType "1"、出金 "2"
"""

import json
import logging
import threading
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from src.clients.bank import BankError, BankTransaction

logger = logging.getLogger(__name__)

BANK_CODE = "0310"
BANK_NAME_KANA = "ｼﾞ-ｴﾑｵ-ｱｵｿﾞﾗﾈﾂﾄ"
BRANCH_KANA = {"301": "ｳﾐ", "302": "ﾆｼﾞ"}
PROCESSED = "20"  # transferStatus: 手続済
JST = ZoneInfo("Asia/Tokyo")


class SunabarBank:
    def __init__(
        self,
        *,
        base_url: str,
        load_tokens: Callable[[], dict[str, str]],
        http: httpx.Client | None = None,
        today: Callable[[], date] | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._load_tokens = load_tokens
        self._http = http or httpx.Client(timeout=20)
        self._today = today or (lambda: datetime.now(JST).date())
        self._tokens: dict[str, str] | None = None
        self._accounts: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # --- 内部（トークン・口座情報はここから外に出さない）---
    def _token(self, label: str) -> str:
        with self._lock:
            if self._tokens is None:
                self._tokens = self._load_tokens()
        try:
            return self._tokens[label]
        except KeyError:
            raise BankError("unknown_account") from None

    def _request(
        self,
        label: str,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "x-access-token": self._token(label),
            "Accept": "application/json;charset=UTF-8",
        }
        if body is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            res = self._http.request(
                method,
                self._base + path,
                params=params,
                content=json.dumps(body).encode() if body is not None else None,
                headers=headers,
            )
        except httpx.HTTPError as e:
            raise BankError("bank_unreachable", type(e).__name__) from None
        try:
            data = res.json()
        except ValueError:
            data = {}
        if res.status_code >= 400:
            # エラーの本文に秘密は含まれないが、コードと詳細コードだけをログ・例外に残す
            detail = [d.get("errorDetailsCode") for d in data.get("errorDetails", [])]
            logger.warning(
                "sunabar error status=%s code=%s detail=%s",
                res.status_code,
                data.get("errorCode"),
                detail,
            )
            raise BankError(f"bank_error_{res.status_code}", str(data.get("errorCode", "")))
        return data

    def _account(self, label: str) -> dict[str, Any]:
        if label not in self._accounts:
            data = self._request(label, "GET", "/accounts")
            accounts = data.get("accounts") or []
            if not accounts:
                raise BankError("no_account")
            self._accounts[label] = accounts[0]
        return self._accounts[label]

    # --- BankClient ---
    def has_account(self, *, label: str) -> bool:
        try:
            self._account(label)
        except BankError:
            return False
        return True

    def holder_name(self, *, label: str) -> str:
        return str(self._account(label).get("accountNameKana", ""))

    def create_transfer(
        self,
        *,
        payer_label: str,
        payee_label: str,
        amount_yen: int,
        request_key: str,
        idempotency_key: str,
    ) -> str:
        payer = self._account(payer_label)
        payee = self._account(payee_label)
        branch = BRANCH_KANA.get(payee["branchCode"])
        if branch is None:
            raise BankError("unsupported_branch")
        body = {
            "accountId": payer["accountId"],
            "transferDesignatedDate": self._today().isoformat(),
            "transferDateHolidayCode": "1",
            "transfers": [
                {
                    "itemId": 1,
                    "transferAmount": str(amount_yen),
                    "beneficiaryBankCode": BANK_CODE,
                    "beneficiaryBankName": BANK_NAME_KANA,
                    "beneficiaryBranchCode": payee["branchCode"],
                    "beneficiaryBranchName": branch,
                    "accountTypeCode": "1",
                    "accountNumber": payee["accountNumber"],
                    "beneficiaryName": payee["accountNameKana"][:48],
                    "transferRequestKey": request_key,
                }
            ],
        }
        data = self._request(
            payer_label, "POST", "/transfer/request", body=body, idempotency_key=idempotency_key
        )
        apply_no = data.get("applyNo")
        if not apply_no:
            raise BankError("no_apply_no")
        return str(apply_no)

    def is_processed(self, *, payer_label: str, apply_no: str) -> bool:
        payer = self._account(payer_label)
        data = self._request(
            payer_label,
            "GET",
            "/transfer/status",
            params={"accountId": payer["accountId"], "queryKeyClass": "1", "applyNo": apply_no},
        )
        return any(d.get("transferStatus") == PROCESSED for d in data.get("transferDetails", []))

    def transactions(
        self, *, label: str, date_from: date, date_to: date
    ) -> tuple[list[BankTransaction], bool]:
        acct = self._account(label)
        data = self._request(
            label,
            "GET",
            "/accounts/transactions",
            params={
                "accountId": acct["accountId"],
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
            },
        )
        rows = [
            BankTransaction(
                item_key=str(t["itemKey"]),
                date=date.fromisoformat(t["transactionDate"]),
                direction="in" if t["transactionType"] == "1" else "out",
                amount_yen=int(t["amount"]),
                remarks=t.get("remarks", ""),
            )
            for t in data.get("transactions", [])
        ]
        return rows, str(data.get("hasNext", "false")).lower() == "true"


def secret_manager_tokens(secret_name: str) -> Callable[[], dict[str, str]]:
    """Secret Manager の最新版（口座ラベル → トークンの JSON）を読む。値はログに出さない。"""

    def load() -> dict[str, str]:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        res = client.access_secret_version(name=f"{secret_name}/versions/latest")
        return json.loads(res.payload.data.decode())

    return load
