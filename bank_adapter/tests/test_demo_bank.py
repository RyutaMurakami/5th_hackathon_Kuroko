"""デモ用の銀行（SPEC 8.10）: 指定した1人だけが実機で承認し、残りの振込は代行する。"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.clients.demo_bank import DemoBank
from src.clients.stub_bank import StubBank
from src.config import Settings, get_settings
from src.main import create_app
from src.services import container
from src.services.container import get_service
from src.services.transfers import BankService
from tests.conftest import API_SA, PAYMENT_SA, URL, token

PAY, API = token(PAYMENT_SA), token(API_SA)


@pytest.fixture
def client(bank, store, clock):
    """`approver`（acct02）だけが実機。`member`（acct03）の振込は代行する。"""
    settings = Settings(
        bank_adapter_url=URL, api_service_account=API_SA, payment_api_service_account=PAYMENT_SA
    )
    # 日付はスタブの銀行（`date.today()`）に合わせる（本番は日本時間。実機の明細と同じ）
    demo = DemoBank(
        real=bank, store=store, live_payer_labels=frozenset({"acct02"}), today=date.today
    )
    service = BankService(
        store=store,
        bank=demo,
        approval_ttl_seconds=600,
        now=clock,
        is_simulated=demo.is_simulated,
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    get_settings.cache_clear()
    import src.services.caller_auth as ca

    ca.get_settings = lambda: settings
    return TestClient(app)


def transfer(client, payer, amount, key):
    body = {
        "payer_user_id": payer,
        "payee_user_id": "organizer",
        "amount_yen": amount,
        "idempotency_key": key,
    }
    return client.post("/transfers", json=body, headers=PAY)


def test_only_the_live_payer_reaches_the_bank_and_needs_approval(client, bank):
    live = transfer(client, "approver", 7200, "k-live").json()
    sim = transfer(client, "member", 5000, "k-sim").json()
    assert bank.create_calls == 1  # 代行ぶんは、銀行を呼ばない
    assert (live["simulated"], sim["simulated"]) == (False, True)
    assert sim["apply_no"].startswith("SIM")

    # 代行ぶんは、承認なしで手続済になる。実機ぶんは、銀行で承認するまで待つ
    assert client.get(f"/transfers/{sim['transfer_id']}", headers=PAY).json()["status"] == (
        "processed"
    )
    get_live = lambda: client.get(f"/transfers/{live['transfer_id']}", headers=PAY).json()  # noqa: E731
    assert get_live()["status"] == "awaiting_approval"
    bank.approve(live["apply_no"])
    assert get_live()["status"] == "processed"


def test_statements_merge_real_and_simulated_entries_with_counterparties(client, bank):
    live = transfer(client, "approver", 7200, "k-live").json()
    transfer(client, "member", 5000, "k-sim")
    today = date.today().isoformat()
    q = f"date_from={today}&date_to={today}"

    # 実機で承認する前は、幹事の入金は代行ぶんだけ（承認していない振込を、入金に数えない）
    before = client.get(f"/statements?user_id=organizer&{q}", headers=API).json()["entries"]
    assert [(e["counterparty_user_id"], e["amount_yen"]) for e in before] == [("member", 5000)]

    bank.approve(live["apply_no"])
    res = client.get(f"/statements?user_id=organizer&{q}", headers=API)
    got = sorted((e["counterparty_user_id"], e["amount_yen"]) for e in res.json()["entries"])
    assert got == [("approver", 7200), ("member", 5000)]
    assert "acct" not in res.text and "スタブ" not in res.text  # ラベル・名義は出さない

    # 支払った本人の出金明細にも載る（payment-api が、完了の確認に使う）
    out = client.get(f"/statements?user_id=member&{q}", headers=PAY).json()["entries"]
    assert [(e["direction"], e["amount_yen"], e["counterparty_user_id"]) for e in out] == [
        ("out", 5000, "organizer")
    ]


def test_a_resent_simulated_transfer_is_recorded_once_and_survives_a_restart(client, bank, store):
    first = transfer(client, "member", 5000, "k-sim").json()
    again = transfer(client, "member", 5000, "k-sim").json()
    assert first["transfer_id"] == again["transfer_id"] and len(store.simulated) == 1

    # 別のインスタンス（メモリを持たない）でも、記録から同じ明細が出る
    other = DemoBank(
        real=StubBank(), store=store, live_payer_labels=frozenset({"acct02"}), today=date.today
    )
    rows, _ = other.transactions(label="acct01", date_from=date.today(), date_to=date.today())
    assert [(r.direction, r.amount_yen) for r in rows] == [("in", 5000)]
    assert other.is_processed(payer_label="acct03", apply_no=first["apply_no"])
    assert not other.is_processed(payer_label="acct02", apply_no=first["apply_no"])  # 別人のもの


def test_simulated_entries_outside_the_period_are_not_returned(store):
    demo = DemoBank(
        real=StubBank(),
        store=store,
        live_payer_labels=frozenset({"acct02"}),
        today=lambda: date(2026, 10, 1),
    )
    demo.create_transfer(
        payer_label="acct03",
        payee_label="acct01",
        amount_yen=5000,
        request_key="R",
        idempotency_key="k",
    )
    rows, _ = demo.transactions(
        label="acct01", date_from=date(2026, 10, 2), date_to=date(2026, 10, 9)
    )
    assert rows == []


def test_simulation_is_off_unless_configured(monkeypatch):
    """設定が無ければ、全員が実機（代行は、明示したときだけ）。"""
    assert Settings(_env_file=None).demo_live_payer_labels == ""

    def build(labels):
        monkeypatch.setattr(
            container,
            "get_settings",
            lambda: Settings(
                _env_file=None, bank_mode="stub", store_backend="memory",
                demo_live_payer_labels=labels,
            ),
        )  # fmt: skip
        container.get_service.cache_clear()
        return container.get_service()

    assert isinstance(build("")._bank, StubBank)
    assert isinstance(build(" ,")._bank, StubBank)
    on = build("acct08")
    assert isinstance(on._bank, DemoBank)
    assert not on._bank.is_simulated("acct08") and on._bank.is_simulated("acct02")
    container.get_service.cache_clear()
