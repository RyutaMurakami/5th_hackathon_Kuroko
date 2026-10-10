import json
from datetime import date

from tests.conftest import AGENT, API_SA, PAYMENT_SA, URL, token

PAY = token(PAYMENT_SA)
API = token(API_SA)


def body(key="k1", amount=7200, payer="approver", payee="organizer"):
    return {
        "payer_user_id": payer,
        "payee_user_id": payee,
        "amount_yen": amount,
        "idempotency_key": key,
    }


def test_create_transfer_awaits_bank_approval(client, bank):
    res = client.post("/transfers", json=body(), headers=PAY)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "awaiting_approval"
    assert data["apply_no"].startswith("STUB")
    assert data["approval_expires_at"]


def test_same_idempotency_key_calls_the_bank_once(client, bank):
    first = client.post("/transfers", json=body(), headers=PAY).json()
    second = client.post("/transfers", json=body(), headers=PAY)
    assert second.status_code == 201
    assert second.json()["transfer_id"] == first["transfer_id"]
    assert second.json()["apply_no"] == first["apply_no"]
    assert bank.create_calls == 1


def test_idempotency_key_reuse_with_other_payload_is_rejected(client, bank):
    client.post("/transfers", json=body(), headers=PAY)
    res = client.post("/transfers", json=body(amount=9999), headers=PAY)
    assert res.status_code == 409
    assert res.json()["detail"] == "idempotency_key_reuse"
    assert bank.create_calls == 1


def test_unknown_user_and_self_transfer(client, bank):
    assert client.post("/transfers", json=body(payer="nobody"), headers=PAY).status_code == 404
    res = client.post("/transfers", json=body(payer="organizer", payee="organizer"), headers=PAY)
    assert res.status_code == 422
    assert bank.create_calls == 0


def test_bank_error_marks_failed_and_does_not_retry_with_same_key(client, bank):
    bank.fail_next = "bank_error_400"
    res = client.post("/transfers", json=body(), headers=PAY)
    assert res.status_code == 502
    assert res.json()["detail"] == "bank_error_400"
    again = client.post("/transfers", json=body(), headers=PAY)
    assert again.json()["status"] == "failed"  # 銀行へ再送しない。新しい冪等キーで作り直す
    assert bank.create_calls == 1


def test_in_progress_record_is_not_sent_again(client, bank, store):
    first = client.post("/transfers", json=body(), headers=PAY).json()
    store.update_transfer(first["transfer_id"], {"status": "creating", "apply_no": None})
    res = client.post("/transfers", json=body(), headers=PAY)
    assert res.status_code == 409
    assert res.json()["detail"] == "in_progress"
    assert bank.create_calls == 1


def test_polling_moves_to_processed_after_bank_approval(client, bank):
    created = client.post("/transfers", json=body(), headers=PAY).json()
    pending = client.get(f"/transfers/{created['transfer_id']}", headers=PAY).json()
    assert pending["status"] == "awaiting_approval"
    bank.approve(created["apply_no"])
    done = client.get(f"/transfers/{created['transfer_id']}", headers=PAY).json()
    assert done["status"] == "processed"
    assert done["approval_expires_at"] is None


def test_unapproved_transfer_expires_after_ttl(client, clock):
    from datetime import timedelta

    created = client.post("/transfers", json=body(), headers=PAY).json()
    clock.t += timedelta(seconds=599)
    assert client.get(f"/transfers/{created['transfer_id']}", headers=PAY).json()["status"] == (
        "awaiting_approval"
    )
    clock.t += timedelta(seconds=2)
    assert client.get(f"/transfers/{created['transfer_id']}", headers=PAY).json()["status"] == (
        "expired"
    )


def test_statements_scope_by_caller(client, bank):
    created = client.post("/transfers", json=body(), headers=PAY).json()
    bank.approve(created["apply_no"])
    today = date.today().isoformat()
    q = f"date_from={today}&date_to={today}"

    organizer_in = client.get(f"/statements?user_id=organizer&{q}", headers=API).json()
    assert [(e["direction"], e["amount_yen"]) for e in organizer_in["entries"]] == [("in", 7200)]

    # kuroko-api（sa-api）は、出金（本人の明細）を見られない
    approver_via_api = client.get(f"/statements?user_id=approver&{q}", headers=API).json()
    assert approver_via_api["entries"] == []
    approver_via_payment = client.get(f"/statements?user_id=approver&{q}", headers=PAY).json()
    assert [(e["direction"], e["amount_yen"]) for e in approver_via_payment["entries"]] == [
        ("out", 7200)
    ]


def test_statement_entries_resolve_the_counterparty_without_exposing_names(client, bank):
    created = client.post("/transfers", json=body(), headers=PAY).json()  # approver → organizer
    bank.approve(created["apply_no"])
    today = date.today().isoformat()
    q = f"date_from={today}&date_to={today}"
    incoming = client.get(f"/statements?user_id=organizer&{q}", headers=API)
    entry = incoming.json()["entries"][0]
    assert entry["counterparty_user_id"] == "approver"  # 摘要の名義から、仮名IDに解決
    assert "remarks" not in entry and "スタブ" not in incoming.text  # 名義は出さない
    outgoing = client.get(f"/statements?user_id=approver&{q}", headers=PAY).json()["entries"][0]
    assert outgoing["counterparty_user_id"] == "organizer"


def test_counterparty_is_none_when_the_name_matches_nobody_or_several(store):
    from src.services.transfers import _normalize_name, _resolve_counterparty

    names = {"a": _normalize_name("ｽﾅﾊﾞ ﾏｻﾕｷ"), "b": _normalize_name("ｽﾅﾊﾞ ﾄｼｵ")}
    assert (
        _resolve_counterparty("振込 スナバ\u3000マサユキ", names) == "a"
    )  # 全角・半角の違いを吸収
    assert _resolve_counterparty("振込 スナバ\u3000ハナコ", names) is None  # 知らない名義
    assert _resolve_counterparty("振込 スナバ\u3000マサユキ", names | {"c": names["a"]}) is None
    assert _resolve_counterparty("手数料", names) is None


def test_statement_range_is_validated(client):
    res = client.get(
        "/statements?user_id=organizer&date_from=2026-10-06&date_to=2026-01-01", headers=API
    )
    assert res.status_code == 422


def test_callers_are_restricted_per_route(client):
    for headers in (token(AGENT), token("x@example.com"), {}):
        assert client.post("/transfers", json=body(), headers=headers).status_code == 403
        assert (
            client.get(
                "/statements?user_id=organizer&date_from=2026-10-06&date_to=2026-10-06",
                headers=headers,
            ).status_code
            == 403
        )
    # sa-api は振込を作れない
    assert client.post("/transfers", json=body(), headers=API).status_code == 403
    # audience が違う・メール未検証のトークンは受け付けない
    assert (
        client.post(
            "/transfers", json=body(), headers=token(PAYMENT_SA, aud="https://other")
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/transfers", json=body(), headers=token(PAYMENT_SA, verified=False)
        ).status_code
        == 403
    )
    assert URL


def test_authorization_and_redaction(client):
    assert client.post("/authorizations", json={"user_id": "member"}, headers=PAY).json() == {
        "user_id": "member",
        "authorized": True,
    }
    nobody = {"user_id": "nobody"}
    assert client.post("/authorizations", json=nobody, headers=PAY).status_code == 404
    assert client.post("/redactions", json={"user_id": "member"}, headers=API).json()["redacted"]
    member = {"user_id": "member"}
    assert client.post("/authorizations", json=member, headers=PAY).status_code == 404
    # 破棄したあとは、この人宛・この人からの振込を作れない
    assert client.post("/transfers", json=body(payer="member"), headers=PAY).status_code == 404


def test_responses_never_contain_account_numbers_or_tokens(client, bank):
    created = client.post("/transfers", json=body(), headers=PAY)
    bank.approve(created.json()["apply_no"])
    today = date.today().isoformat()
    texts = [
        created.text,
        client.get(f"/transfers/{created.json()['transfer_id']}", headers=PAY).text,
        client.get(
            f"/statements?user_id=organizer&date_from={today}&date_to={today}", headers=PAY
        ).text,
    ]
    forbidden = ("accountNumber", "accountId", "account_number", "token", "branch")
    for text in texts:
        assert not any(w in text for w in forbidden)
        assert "acct0" not in json.dumps(text)  # 口座ラベルも出さない


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
