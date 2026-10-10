"""請求の作成（Policy Gate 6.2 → 署名 → payment-api）と、幹事口座の入金の確認（B13）。"""

import base64
import hashlib
import json
from datetime import UTC, date, datetime

import pytest

from src.clients.bank_adapter import IncomingEntry
from src.clients.claim_signer import LocalClaimSigner
from src.clients.payment_api import PaymentApiError, PaymentOutcome
from src.db.events import MemoryEventStore
from src.db.payments import MemoryPaymentReader
from src.models.event import Receipt
from src.models.split import Approval, ApprovalStatus
from src.services.billing import BillingService, UnknownEvent, payment_id_for
from src.services.policy import load_snapshot
from src.services.policy_gates import Gate
from src.services.split import calculate_split
from tests.sample_company import demo_event, demo_participants

POLICY = load_snapshot()
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


class FakePaymentApi:
    def __init__(self, fail_for=()):
        self.calls: list[dict] = []
        self.fail_for = set(fail_for)

    async def start_payment(self, **body):
        self.calls.append(body)
        if body["payer_user_id"] in self.fail_for:
            raise PaymentApiError("payment_api_502")
        return PaymentOutcome(body["payment_id"], "awaiting_bank_approval", None)


class FakeBank:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.asked: list[tuple] = []

    async def incoming(self, *, user_id, date_from, date_to):
        self.asked.append((user_id, date_from, date_to))
        return self.entries


def build(approved=True, **kw):
    store = MemoryEventStore()
    event = demo_event().model_copy(update={"policy_snapshot": POLICY, "organizer_web_uid": "uid"})
    people = [
        p.model_copy(update={"slack_user_id": f"U_{p.user_id.upper()}"})
        for p in demo_participants()
    ]
    store.save_event(event)
    for p in people:
        store.save_participant(event.event_id, p)
    store.save_receipt(
        Receipt(event_id="ev-demo", total_amount_yen=60_300, confirmed_by="uid", confirmed_at=NOW)
    )
    split = calculate_split(event, people, POLICY)
    store.save_split(split)
    if approved:
        store.save_approval(
            Approval(
                event_id="ev-demo",
                approver_user_id=split.approver_user_id,
                split_hash=split.hash,
                status=ApprovalStatus.APPROVED,
                approved_at=NOW,
                approved_by_slack_user_id="U_YAMADA",
            )
        )
    signer = LocalClaimSigner()
    api, bank = FakePaymentApi(kw.pop("fail_for", ())), FakeBank(kw.pop("entries", ()))
    svc = BillingService(
        store=store,
        signer=signer,
        payment_api=api,
        bank=bank,
        payments=kw.pop("payments", MemoryPaymentReader()),
        checkout_ttl_seconds=3 * 86400,
        now=lambda: NOW,
        today=lambda: date(2026, 11, 2),
    )
    return svc, store, api, bank, signer, split


def claims_of(token: str) -> dict:
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


# ---------------- create_checkouts ----------------
async def test_creates_one_signed_checkout_per_payer_and_passes_gate_6_2():
    svc, store, api, _, signer, split = build()
    run = await svc.create_checkouts("ev-demo")
    assert run.ok and run.failures == [] and run.errors == {}
    assert len(api.calls) == 7  # 山田・佐々木・伊藤・渡辺・中村・小林・加藤
    assert sorted(c["payer_user_id"] for c in api.calls) == sorted(
        ["yamada", "sasaki", "ito", "watanabe", "nakamura", "kobayashi", "kato"]
    )
    assert sum(c["amount_yen"] for c in api.calls) == 27_000  # 60,300−30,000−幹事 3,300
    assert {c["payee_user_id"] for c in api.calls} == {"takahashi"}
    assert all(r == "awaiting_bank_approval" for r in run.outcomes.values())
    assert store.get_event("ev-demo").status.value == "payment"


async def test_checkout_is_a_signed_jwt_bound_to_the_approved_split():
    svc, _, api, _, signer, split = build()
    await svc.create_checkouts("ev-demo")
    call = next(c for c in api.calls if c["payer_user_id"] == "yamada")
    claims = claims_of(call["checkout_jwt"])
    assert claims["sub"] == "yamada" and claims["payee"] == "takahashi"
    assert claims["amount_yen"] == 7_200 and claims["currency"] == "JPY"
    assert claims["split_hash"] == split.hash and claims["payment_reference"] == "ev-demo"
    assert (claims["iss"], claims["aud"]) == ("kuroko-api", "payment-api")
    assert claims["exp"] - claims["iat"] == 3 * 86400
    assert call["checkout_hash"] == hashlib.sha256(call["checkout_jwt"].encode()).hexdigest()
    assert call["payment_id"] == payment_id_for("ev-demo", "yamada")
    # 口座番号・トークン・名義の類を載せない
    assert not {"account", "token", "name"} & set(claims)


async def test_organizer_and_guests_of_honor_are_never_charged():
    svc, _, api, _, _, _ = build()
    await svc.create_checkouts("ev-demo")
    payers = {c["payer_user_id"] for c in api.calls}
    assert not payers & {"takahashi", "matsumoto", "inoue"}


async def test_without_an_approval_nothing_reaches_payment_api():
    svc, store, api, _, _, _ = build(approved=False)
    run = await svc.create_checkouts("ev-demo")
    assert not run.ok and Gate.APPROVAL_MISSING in run.failures
    assert api.calls == []
    assert store.get_event("ev-demo").status.value != "payment"


async def test_a_completed_payment_blocks_the_whole_run_not_just_one_person():
    svc, _, api, _, _, _ = build(payments=MemoryPaymentReader({("ev-demo", "ito")}))
    run = await svc.create_checkouts("ev-demo")
    assert run.failures == [Gate.DUPLICATE_PAYMENT] and api.calls == []


async def test_a_rewritten_split_is_not_billed():
    svc, store, api, _, _, split = build()
    rows = [
        r.model_copy(update={"share_yen": r.share_yen + 100}) if r.user_id == "ito" else r
        for r in split.rows
    ]
    store.splits["ev-demo"] = split.model_copy(update={"rows": rows})  # 承認後に書き換え
    run = await svc.create_checkouts("ev-demo")
    assert not run.ok and Gate.SPLIT_TAMPERED in run.failures and api.calls == []


async def test_one_failed_call_is_recorded_and_the_others_continue():
    svc, store, api, _, _, _ = build(fail_for={"ito"})
    run = await svc.create_checkouts("ev-demo")
    assert run.ok and run.errors == {"ito": "payment_api_502"}
    assert len(run.outcomes) == 6 and "ito" not in run.outcomes


async def test_resending_uses_the_same_payment_ids():
    svc, _, api, _, _, _ = build()
    await svc.create_checkouts("ev-demo")
    await svc.create_checkouts("ev-demo")
    ids = [c["payment_id"] for c in api.calls]
    assert len(ids) == 14 and len(set(ids)) == 7  # payment-api が同じ支払いとして受ける


async def test_unknown_event_is_an_error():
    svc, *_ = build()
    with pytest.raises(UnknownEvent):
        await svc.create_checkouts("nope")


# ---------------- confirm_incoming_payments ----------------
def entry(key, user, amount, d=date(2026, 10, 31)):
    return IncomingEntry(key, d, amount, user)


EXPECTED = {
    "yamada": 7_200, "sasaki": 5_000, "ito": 3_300, "watanabe": 3_300,
    "nakamura": 3_300, "kobayashi": 3_300, "kato": 1_600,
}  # fmt: skip


async def test_all_received_when_every_payer_has_a_matching_incoming_transfer():
    entries = [entry(f"k{i}", u, a) for i, (u, a) in enumerate(EXPECTED.items())]
    svc, store, _, bank, _, _ = build(entries=entries)
    run = await svc.confirm_incoming_payments("ev-demo")
    assert run.all_received and sorted(run.received) == sorted(EXPECTED) and run.missing == []
    # 幹事の口座の、開催日から今日（日本時間）まで
    assert bank.asked == [("takahashi", date(2026, 10, 30), date(2026, 11, 2))]
    marked = {p.user_id for p in store.list_participants("ev-demo") if p.collection_confirmed_at}
    assert marked == set(EXPECTED)


async def test_missing_and_mismatched_payments_are_reported_separately():
    entries = [
        entry(f"k{i}", u, a)
        for i, (u, a) in enumerate(EXPECTED.items())
        if u not in {"ito", "kato"}
    ]
    entries.append(entry("kx", "kato", 1_500))  # 金額が違う
    svc, store, *_ = build(entries=entries)
    run = await svc.confirm_incoming_payments("ev-demo")
    assert run.missing == ["ito"] and run.amount_mismatch == ["kato"] and not run.all_received
    marked = {p.user_id for p in store.list_participants("ev-demo") if p.collection_confirmed_at}
    assert "ito" not in marked and "kato" not in marked


async def test_an_incoming_transfer_counts_for_one_person_only():
    # 同じ金額 3,300円 が2人ぶんあっても、同じ人からの1件を2人ぶんには数えない
    entries = [entry("k1", "ito", 3_300)]
    svc, *_ = build(entries=entries)
    run = await svc.confirm_incoming_payments("ev-demo")
    assert run.received == ["ito"] and "watanabe" in run.missing


async def test_unresolved_or_unrelated_incoming_transfers_do_not_count():
    entries = [entry("k1", None, 7_200), entry("k2", "matsumoto", 7_200), entry("k3", "x", 7_200)]
    svc, *_ = build(entries=entries)
    run = await svc.confirm_incoming_payments("ev-demo")
    assert run.received == [] and "yamada" in run.missing


async def test_confirming_twice_keeps_the_first_confirmation_time():
    entries = [entry("k1", "ito", 3_300)]
    svc, store, *_ = build(entries=entries)
    await svc.confirm_incoming_payments("ev-demo")
    first = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    svc._now = lambda: datetime(2026, 11, 5, tzinfo=UTC)
    await svc.confirm_incoming_payments("ev-demo")
    again = next(p for p in store.list_participants("ev-demo") if p.user_id == "ito")
    assert again.collection_confirmed_at == first.collection_confirmed_at == NOW


async def test_a_payer_is_not_marked_received_without_a_split():
    svc, store, *_ = build()
    store.splits.clear()
    with pytest.raises(UnknownEvent):
        await svc.confirm_incoming_payments("ev-demo")
