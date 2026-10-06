"""Policy Gate 6.3: 通らなければ振込依頼を作らない（銀行アダプタを呼ばない）。"""

import pytest

from src.models.schemas import SignMandateRequest
from src.services.checkout import RejectAllCheckouts
from tests.conftest import API, GATEWAY, Env, make_client, pay_body, sign_body


def sign(client, **kw):
    assert client.post("/mandates", json=sign_body(**kw), headers=GATEWAY).status_code == 201


def pay(client, **kw):
    res = client.post("/payments", json=pay_body(**kw), headers=API)
    assert res.status_code == 201
    return res.json()


def test_happy_path_creates_transfer_request_and_awaits_bank_approval(client, env):
    sign(client)
    data = pay(client)
    assert data["status"] == "awaiting_bank_approval"
    assert data["block_reason"] is None
    assert data["transfer_id"] == "tr-1"
    assert len(env.bank.transfers) == 1
    t = env.bank.transfers[0]
    assert (t["payer"], t["payee"], t["amount"]) == ("member", "organizer", 3300)
    assert t["key"] == "p1:0"  # 冪等キー（銀行アダプタが二重依頼を防ぐ）


def test_closed_mandate_chain_is_signed_and_stored(client, env):
    sign(client)
    pay(client)
    chain = env.store.get_payment("p1")["closed_payment_mandate"]
    assert chain.count("~") >= 1  # Open → Closed のチェーン


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"amount": 5001}, "over_cap"),  # 上限を1円超える
        ({"payee": "someone_else"}, "payee_not_allowed"),  # 幹事以外
        ({"event": "ev2"}, "no_mandate"),  # 別イベントの請求
        ({"user": "stranger"}, "no_mandate"),  # 委任していない人
    ],
)
def test_out_of_range_requests_never_reach_the_bank(client, env, kwargs, reason):
    sign(client)
    data = pay(client, **kwargs)
    assert data["status"] == "blocked"
    assert data["block_reason"] == reason
    assert data["transfer_id"] is None
    assert env.bank.transfers == []


def test_amount_exactly_at_cap_passes(client, env):
    sign(client)
    assert pay(client, amount=5000)["status"] == "awaiting_bank_approval"


def test_payee_is_checked_against_the_signed_mandate_not_the_firestore_copy(client, env):
    sign(client)
    # Firestore の写しを書き換えられても、署名つきの委任状が正
    env.store.update_mandate("ev1:member", {"payee_user_id": "attacker", "cap_yen": 10**6})
    assert pay(client, payee="attacker")["block_reason"] == "payee_not_allowed"
    assert pay(client, payment_id="p2", amount=6000)["block_reason"] == "over_cap"
    assert env.bank.transfers == []


def test_tampered_or_swapped_mandate_signature_is_rejected(client, env):
    sign(client)
    sign(client, user="other")
    # 他人の委任状を、自分の委任状として差し込む（kid が合わない）
    other = env.store.get_mandate("ev1:other")["open_payment_mandate"]
    env.store.update_mandate("ev1:member", {"open_payment_mandate": other})
    assert pay(client)["block_reason"] == "bad_signature"
    # 中身を壊す
    tok = env.store.get_mandate("ev1:member")["open_payment_mandate"]
    env.store.update_mandate("ev1:member", {"open_payment_mandate": tok[:-10] + "AAAAAAAAAA"})
    assert pay(client, payment_id="p2")["block_reason"] == "bad_signature"
    assert env.bank.transfers == []


def test_mandate_signed_by_another_key_is_rejected(client, env):
    from src.clients.signers import LocalSigner
    from src.services.mandates import MandateService

    sign(client)
    forger = MandateService(
        store=env.store, participant_signer=LocalSigner(), agent_signer=env.agent, now=env.clock
    )
    # 偽の鍵で署名した委任状を、保存済みの委任状と入れ替える
    env.store.mandates.pop("ev1:member")
    forger.sign(SignMandateRequest(**sign_body()))
    assert pay(client)["block_reason"] == "bad_signature"
    assert env.bank.transfers == []


def test_same_payment_id_is_idempotent_and_does_not_call_the_bank_twice(client, env):
    sign(client)
    first = pay(client)
    second = pay(client)
    assert second["status"] == first["status"] and second["transfer_id"] == first["transfer_id"]
    assert len(env.bank.transfers) == 1
    reuse = client.post("/payments", json=pay_body(amount=3400), headers=API)
    assert reuse.status_code == 409


def test_second_payment_for_same_participant_is_blocked_as_duplicate(client, env):
    sign(client)
    pay(client)
    dup = pay(client, payment_id="p2", checkout_hash="other-hash")
    assert dup["block_reason"] == "duplicate_payment"
    assert len(env.bank.transfers) == 1


def test_nonce_is_single_use_for_the_same_mandate_and_checkout(client, env):
    sign(client)
    first = pay(client)
    assert first["status"] == "awaiting_bank_approval"
    # 失敗扱いにして重複の検査を外しても、同じ委任状・同じ請求の nonce は使えない
    env.store.update_payment("p1", {"status": "failed"})
    again = pay(client, payment_id="p2")
    assert again["block_reason"] == "nonce_reused"
    assert len(env.bank.transfers) == 1


def test_bank_authorization_is_required(client, env):
    sign(client)
    env.bank.authorized = set()
    data = pay(client)
    assert data["block_reason"] == "bank_not_authorized"
    assert env.bank.transfers == []


def test_checkout_signature_is_required_fail_closed():
    env = Env(checkout=RejectAllCheckouts())
    client = make_client(env)
    sign(client)
    assert pay(client)["block_reason"] == "invalid_checkout"
    assert env.bank.transfers == []


def test_blocked_checks_do_not_burn_the_nonce(client, env):
    sign(client)
    env.bank.authorized = set()
    assert pay(client)["block_reason"] == "bank_not_authorized"
    env.bank.authorized = None
    # 別の payment_id で、同じ請求をやり直せる（検査で落ちた依頼は nonce を消費しない）
    assert pay(client, payment_id="p2")["status"] == "awaiting_bank_approval"


def test_bank_adapter_failure_marks_failed_and_surfaces_502(client, env):
    sign(client)
    env.bank.fail_next = True
    res = client.post("/payments", json=pay_body(), headers=API)
    assert res.status_code == 502
    assert env.store.get_payment("p1")["status"] == "failed"


def test_payment_routes_accept_only_sa_api(client):
    for headers in (GATEWAY, {}):
        assert client.post("/payments", json=pay_body(), headers=headers).status_code == 403
        assert client.get("/payments/p1", headers=headers).status_code == 403


def test_responses_never_contain_tokens_or_mandates(client, env):
    sign(client)
    text = client.post("/payments", json=pay_body(), headers=API).text
    for word in ("mandate", "token", "jwt", "account"):
        assert word not in text.lower().replace("block_reason", "")


def test_event_id_inside_the_signed_mandate_must_match_the_request(client, env):
    sign(client, event="ev1")
    # ev1 の署名つき委任状を、ev2 の委任状として差し込む（kid は本人で署名も正しい）
    token = env.store.get_mandate("ev1:member")["open_payment_mandate"]
    record = env.store.get_mandate("ev1:member") | {
        "mandate_id": "ev2:member",
        "event_id": "ev2",
        "open_payment_mandate": token,
    }
    env.store.put_mandate("ev2:member", record)
    data = pay(client, event="ev2")
    assert data["block_reason"] == "event_mismatch"
    assert env.bank.transfers == []


def test_health_uses_the_path_cloud_run_does_not_reserve(client):
    # Cloud Run では /healthz が Google 側に予約されていてアプリに届かない（404）
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/healthz").status_code == 404
