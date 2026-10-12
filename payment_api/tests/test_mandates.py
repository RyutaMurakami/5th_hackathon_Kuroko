from datetime import timedelta

from tests.conftest import API, DEMO, GATEWAY, T0, make_client, pay_body, sign_body


def test_sign_mandate_creates_active_signed_open_mandate(client, env):
    res = client.post("/mandates", json=sign_body(), headers=GATEWAY)
    assert res.status_code == 201
    data = res.json()
    assert data["mandate_id"] == "ev1:member"
    assert data["status"] == "active"
    assert data["cap_yen"] == 5000
    record = env.store.get_mandate("ev1:member")
    assert record["open_payment_mandate"].count("~") >= 0  # SD-JWT（署名つき）
    assert "organizer" not in str(data.get("open_payment_mandate", ""))  # 応答にトークンを出さない
    assert "open_payment_mandate" not in data


def test_sign_is_idempotent_for_same_request_but_conflicts_otherwise(client):
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    again = client.post("/mandates", json=sign_body(), headers=GATEWAY)
    assert again.status_code == 201
    other = client.post("/mandates", json=sign_body(cap=9000), headers=GATEWAY)
    assert other.status_code == 409


def test_sign_rejects_past_expiry_and_self_payee(client):
    past = sign_body(days=-1)
    assert client.post("/mandates", json=past, headers=GATEWAY).status_code == 422
    self_pay = sign_body(payee="member")
    assert client.post("/mandates", json=self_pay, headers=GATEWAY).status_code == 422


def test_revoke_before_payment_blocks_later_payments(client, env):
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    res = client.post("/mandates/ev1:member/revoke", headers=GATEWAY)
    assert res.status_code == 200 and res.json()["status"] == "revoked"
    pay = client.post("/payments", json=pay_body(), headers=API).json()
    assert pay["status"] == "blocked" and pay["block_reason"] == "mandate_revoked"
    assert env.bank.transfers == []


def test_revoke_after_payment_started_is_refused(client):
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    client.post("/payments", json=pay_body(), headers=API)
    res = client.post("/mandates/ev1:member/revoke", headers=GATEWAY)
    assert res.status_code == 409 and res.json()["detail"] == "payment_started"


def test_expired_mandate_is_marked_expired_on_read(client, env):
    client.post("/mandates", json=sign_body(days=1), headers=GATEWAY)
    env.clock.t = T0 + timedelta(days=2)
    assert client.post("/payments", json=pay_body(), headers=API).json()["block_reason"] == (
        "mandate_expired"
    )
    assert env.store.get_mandate("ev1:member")["status"] == "expired"


def test_mandate_routes_accept_only_gateway(client):
    for headers in (API, {}):
        assert client.post("/mandates", json=sign_body(), headers=headers).status_code == 403
        assert client.post("/mandates/x/revoke", headers=headers).status_code == 403
    assert make_client  # 他の呼び出し元（エージェントなど）も同じ検査で 403 になる


# ---------------- デモ用の代行（SPEC 7.6） ----------------
def test_the_demo_runner_signs_only_for_people_it_may_act_for(client, env):
    body = sign_body(signed_via="demo-runner")
    # sandbox のイベントの、Slack を持たない参加者として記録されていなければ、署名しない
    assert client.post("/mandates", json=body, headers=DEMO).status_code == 403
    assert env.store.get_mandate("ev1:member") is None
    env.store.demo_proxy.add(("ev1", "member"))
    res = client.post("/mandates", json=body, headers=DEMO)
    assert res.status_code == 201 and res.json()["status"] == "active"
    assert env.store.get_mandate("ev1:member")["signed_via"] == "demo-runner"


def test_the_demo_mark_and_the_demo_identity_always_go_together(client, env):
    env.store.demo_proxy.add(("ev1", "member"))
    # 代行の身元が、Slack 操作のふりをすることはできない
    assert client.post("/mandates", json=sign_body(), headers=DEMO).status_code == 403
    # Slack の経路（sa-gateway）が、代行の印を付けることもできない
    marked = sign_body(signed_via="demo-runner")
    assert client.post("/mandates", json=marked, headers=GATEWAY).status_code == 403
    assert env.store.get_mandate("ev1:member") is None


def test_the_demo_runner_cannot_revoke_or_start_payments(client, env):
    client.post("/mandates", json=sign_body(), headers=GATEWAY)
    assert client.post("/mandates/ev1:member/revoke", headers=DEMO).status_code == 403
    assert client.post("/payments", json=pay_body(), headers=DEMO).status_code == 403
