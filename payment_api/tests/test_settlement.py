"""支払いの完了まで: 承認待ちの確認 → 出金明細での確認 → 領収書の署名 → 通知、期限切れ。"""

import base64
import json
from datetime import timedelta

import pytest

from src.clients.bank_adapter import OutgoingEntry
from src.services.notifier import NullNotifier, completed_text, failed_text, requested_text
from tests.conftest import API, GATEWAY, SCHEDULER, T0, Env, make_client, pay_body, sign_body


def started(env, client):
    assert client.post("/mandates", json=sign_body(), headers=GATEWAY).status_code == 201
    res = client.post("/payments", json=pay_body(), headers=API)
    assert res.status_code == 201 and res.json()["status"] == "awaiting_bank_approval"
    return env.payments


def outgoing(env, amount=3300, payee="organizer", key="k1", d=None):
    env.bank.outgoing_entries["member"] = [
        OutgoingEntry(key, d or (T0 + timedelta(hours=1)).date(), amount, payee)
    ]


@pytest.fixture
def env():
    e = Env()
    e.notifier = NullNotifier()
    e.payments._notifier = e.notifier
    return e


@pytest.fixture
def client(env):
    return make_client(env)


def status_of(env, pid="p1"):
    return env.store.get_payment(pid)["status"]


def test_start_notifies_the_payer_that_bank_approval_is_needed(env, client):
    started(env, client)
    assert env.notifier.sent == [("requested", "p1", "")]


def test_a_simulated_transfer_skips_the_approval_notice_but_still_needs_the_statement(env, client):
    """デモで代行した振込（SPEC 8.10）: 「銀行で承認して」は送らない。完了の条件は実機と同じ。"""
    env.bank.simulated_payers = {"member"}
    svc = started(env, client)
    assert env.notifier.sent == []
    assert env.store.get_payment("p1")["simulated"] is True
    env.bank.statuses["tr-1"] = "processed"
    assert svc.poll_one("p1") == "unverified"  # 明細で確認できるまで、完了にしない
    outgoing(env)
    assert svc.poll_one("p1") == "completed"
    assert env.notifier.sent == [("completed", "p1", "")]


def test_waiting_when_the_bank_has_not_approved_yet(env, client):
    svc = started(env, client)
    assert svc.poll_one("p1") == "waiting" and status_of(env) == "awaiting_bank_approval"


def test_completes_only_when_the_bank_processed_and_the_outgoing_statement_confirms(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    # 手続済でも、出金明細に確認できなければ完了にしない（銀行の結果コードだけでは完了にしない）
    assert svc.poll_one("p1") == "unverified" and status_of(env) == "awaiting_bank_approval"
    outgoing(env, amount=3200)  # 金額が違う
    assert svc.poll_one("p1") == "unverified"
    outgoing(env, payee="someone_else")  # 振込先が違う
    assert svc.poll_one("p1") == "unverified"
    outgoing(env)
    assert svc.poll_one("p1") == "completed"
    rec = env.store.get_payment("p1")
    assert rec["status"] == "completed" and rec["settlement_verified"] is True
    assert rec["completed_at"] == T0
    assert ("completed", "p1", "") in env.notifier.sent


def test_the_receipt_is_signed_by_the_payment_agent_and_has_no_account_data(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    svc.poll_one("p1")
    receipt = env.store.get_payment("p1")["receipt"]
    head, body, sig = receipt.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    claims = json.loads(base64.urlsafe_b64decode(pad(body)))
    assert claims["iss"] == "payment-api" and claims["amount_yen"] == 3300
    assert (claims["payer"], claims["payee"], claims["statement_item"]) == (
        "member", "organizer", "k1"
    )  # fmt: skip
    assert json.loads(base64.urlsafe_b64decode(pad(head)))["kid"] == "payment-agent"
    assert not {"account", "token", "name"} & set(claims)
    # 公開鍵で検証できる（エージェントの署名）
    from jwcrypto.jws import JWS

    jws = JWS()
    jws.deserialize(receipt)
    jws.verify(env.agent.public_key(), alg="ES256")


def test_one_statement_line_confirms_only_one_payment(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    svc.poll_one("p1")
    # 別の支払いが、同じ明細の1件を使い回して完了にすることはできない
    assert env.store.claim_settlement("k1", "p-other") is False
    assert env.store.claim_settlement("k1", "p1") is True  # 同じ支払いの再確認は問題ない


def test_completing_marks_the_mandate_as_used(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    svc.poll_one("p1")
    assert env.store.get_mandate("ev1:member")["status"] == "used"


def test_polling_does_not_touch_finished_payments(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    svc.poll_one("p1")
    assert svc.poll_one("p1") == "skipped"
    assert svc.poll_all() == {}


def test_a_bank_error_while_polling_does_not_change_the_payment(env, client):
    svc = started(env, client)
    env.bank.poll_error = True
    assert svc.poll_one("p1") == "bank_unreachable"
    assert status_of(env) == "awaiting_bank_approval"
    assert svc.poll_all() == {"bank_unreachable": 1}


# ---------------- 期限切れの作り直し ----------------
def test_an_expired_request_is_reissued_with_a_new_nonce_and_key(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "expired"
    assert svc.poll_one("p1") == "reissued"
    rec = env.store.get_payment("p1")
    assert rec["status"] == "awaiting_bank_approval" and rec["retry_count"] == 1
    assert rec["transfer_id"] == "tr-2"
    assert [t["key"] for t in env.bank.transfers] == ["p1:0", "p1:1"]  # 冪等キーは依頼ごとに新しい
    assert ("reissued", "p1", "") in env.notifier.sent  # 再通知


def test_after_two_reissues_the_payment_fails_and_the_organizer_is_told(env, client):
    svc = started(env, client)
    for n, expected in ((1, "reissued"), (2, "reissued"), (3, "failed")):
        env.bank.statuses[f"tr-{n}"] = "expired"
        assert svc.poll_one("p1") == expected
    assert status_of(env) == "failed" and len(env.bank.transfers) == 3  # 最大2回の作り直し
    assert env.notifier.sent[-1] == ("failed", "p1", "")


def test_reissue_runs_policy_gate_6_3_again(env, client):
    svc = started(env, client)
    client.post("/mandates/ev1:member/revoke", headers=GATEWAY)  # 払い始めたあとは取り消せない
    env.store.update_mandate("ev1:member", {"status": "revoked"})  # 万一、取り消されていたら
    env.bank.statuses["tr-1"] = "expired"
    assert svc.poll_one("p1") == "blocked"
    rec = env.store.get_payment("p1")
    assert rec["status"] == "blocked" and rec["block_reason"] == "mandate_revoked"
    assert len(env.bank.transfers) == 1  # 作り直しの依頼は作られない


def test_a_failed_bank_status_fails_the_payment(env, client):
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "failed"
    assert svc.poll_one("p1") == "failed" and status_of(env) == "failed"


def test_a_notification_failure_never_changes_the_payment(env, client):
    class Broken:
        def transfer_requested(self, p, *, reissued):
            raise RuntimeError("slack down")

        def completed(self, p):
            raise RuntimeError("slack down")

        def failed(self, p):
            raise RuntimeError("slack down")

    env.payments._notifier = Broken()
    svc = started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    assert svc.poll_one("p1") == "completed"


# ---------------- ポーリングの入口 ----------------
def test_only_the_scheduler_can_poll(env, client):
    assert client.post("/tasks/internal/payments/poll", headers=SCHEDULER).json() == {}
    for headers in (API, GATEWAY, {}):
        assert client.post("/tasks/internal/payments/poll", headers=headers).status_code == 403


def test_poll_returns_only_counts(env, client):
    started(env, client)
    env.bank.statuses["tr-1"] = "processed"
    outgoing(env)
    res = client.post("/tasks/internal/payments/poll", headers=SCHEDULER)
    assert res.json() == {"completed": 1}


# ---------------- 通知の文面 ----------------
def test_notification_texts_are_fixed_templates_without_secrets():
    t = requested_text("歓送迎会", 7200, reissued=False)
    assert "7,200円" in t and "10分以内" in t and "取引パスワード" in t
    assert "作り直しました" in requested_text("歓送迎会", 7200, reissued=True)
    assert "入金を確認" in completed_text("歓送迎会", 7200)
    assert "幹事に報告" in failed_text("歓送迎会", 7200)
    for text in (t, completed_text("x", 1), failed_text("x", 1)):
        assert not any(w in text for w in ("口座番号", "トークン", "accountId"))


def test_a_web_demo_event_asks_the_bank_to_hold_the_transfer_for_the_web_approval(client, env):
    """体験用のイベント（SPEC 7.7）: 銀行での承認は Web のカード。Slack の承認依頼は送らない。"""
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    env.store.web_bank_events.add("ev1")
    res = client.post("/payments", json=pay_body(), headers=API).json()
    assert res["status"] == "awaiting_bank_approval"
    assert env.bank.transfers[-1]["demo_hold"] is True
    assert client.post("/tasks/internal/payments/poll", headers=SCHEDULER).status_code == 200
    assert env.store.get_payment(res["payment_id"])["status"] == "awaiting_bank_approval"  # 待つ


def test_other_events_do_not_ask_for_a_hold(client, env):
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    client.post("/payments", json=pay_body(), headers=API)
    assert env.bank.transfers[-1]["demo_hold"] is False
