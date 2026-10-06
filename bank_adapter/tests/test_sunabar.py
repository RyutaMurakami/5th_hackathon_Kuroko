import json
from datetime import date

import httpx
import pytest

from src.clients.bank import BankError
from src.clients.sunabar import SunabarBank

TOKENS = {"acct02": "token-payer", "acct01": "token-payee"}
ACCOUNTS = {
    "token-payer": {
        "accountId": "302010014786",
        "branchCode": "302",
        "accountNumber": "0014786",
        "accountNameKana": "ｽﾅﾊﾞ ﾏｻﾕｷ",
    },
    "token-payee": {
        "accountId": "301010014779",
        "branchCode": "301",
        "accountNumber": "0014779",
        "accountNameKana": "ｽﾅﾊﾞ ﾋﾛﾋﾄ",
    },
}


def make(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return SunabarBank(
        base_url="https://sunabar.test/v1",
        load_tokens=lambda: TOKENS,
        http=http,
        today=lambda: date(2026, 10, 6),
    )


def test_create_transfer_sends_the_verified_request_shape():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        tok = req.headers["x-access-token"]
        if req.url.path.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [ACCOUNTS[tok]]})
        seen["req"] = req
        seen["body"] = json.loads(req.content)
        return httpx.Response(201, json={"resultCode": "2", "applyNo": "2026100600000099"})

    bank = make(handler)
    apply_no = bank.create_transfer(
        payer_label="acct02",
        payee_label="acct01",
        amount_yen=7200,
        request_key="ABC-KEY",
        idempotency_key="idem-1",
    )
    assert apply_no == "2026100600000099"
    req, body = seen["req"], seen["body"]
    assert req.headers["x-access-token"] == "token-payer"
    assert req.headers["Idempotency-Key"] == "idem-1"
    assert body["accountId"] == "302010014786"
    assert body["transferDesignatedDate"] == "2026-10-06"
    item = body["transfers"][0]
    assert item["beneficiaryBankCode"] == "0310"  # サンプルの 0398 は通らない
    assert item["beneficiaryBranchCode"] == "301"
    assert item["beneficiaryBranchName"] == "ｳﾐ"  # 半角カナ
    assert item["accountNumber"] == "0014779"  # 7桁
    assert item["transferAmount"] == "7200"
    assert item["transferRequestKey"] == "ABC-KEY"


def test_status_is_processed_only_for_transfer_status_20():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [ACCOUNTS[req.headers["x-access-token"]]]})
        assert req.url.params["queryKeyClass"] == "1"
        details = {
            "A": [],  # 承認前は 0件で返る
            "B": [{"transferStatus": "10"}],
            "C": [{"transferStatus": "20"}],
        }[req.url.params["applyNo"]]
        return httpx.Response(200, json={"transferDetails": details})

    bank = make(handler)
    assert [bank.is_processed(payer_label="acct02", apply_no=a) for a in "ABC"] == [
        False,
        False,
        True,
    ]


def test_transactions_map_direction_and_never_expose_account_fields():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [ACCOUNTS[req.headers["x-access-token"]]]})
        return httpx.Response(
            200,
            json={
                "hasNext": "false",
                "transactions": [
                    {
                        "transactionDate": "2026-10-06",
                        "transactionType": "1",
                        "amount": "7200",
                        "remarks": "振込 スナバ　マサユキ",
                        "itemKey": "1",
                    },
                    {
                        "transactionDate": "2026-10-06",
                        "transactionType": "2",
                        "amount": "1",
                        "remarks": "振込 スナバ　カズコ",
                        "itemKey": "2",
                    },
                ],
            },
        )

    rows, has_next = make(handler).transactions(
        label="acct01", date_from=date(2026, 10, 6), date_to=date(2026, 10, 6)
    )
    assert [(r.direction, r.amount_yen) for r in rows] == [("in", 7200), ("out", 1)]
    assert not has_next


def test_bank_errors_do_not_leak_details_and_unknown_labels_fail():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [ACCOUNTS[req.headers["x-access-token"]]]})
        return httpx.Response(
            400,
            json={
                "errorCode": "220011",
                "errorDetails": [
                    {
                        "errorDetailsCode": "032002",
                        "errorDetailsMessage": "支店 0014779 token-payer",
                    }
                ],
            },
        )

    bank = make(handler)
    with pytest.raises(BankError) as e:
        bank.create_transfer(
            payer_label="acct02",
            payee_label="acct01",
            amount_yen=1,
            request_key="k",
            idempotency_key="i",
        )
    assert e.value.code == "bank_error_400"
    assert "0014779" not in str(e.value) and "token" not in str(e.value)
    assert not bank.has_account(label="acct99")
