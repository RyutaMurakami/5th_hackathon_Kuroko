import datetime as dt

import pytest

from src.db.events import ApprovedSplitIsFinal, MemoryEventStore
from src.models.event import Event
from src.models.split import Approval, ApprovalStatus
from src.services.policy import load_snapshot
from src.services.split import calculate_split
from tests.sample_company import demo_event, demo_participants


def test_event_round_trip_keeps_the_policy_snapshot():
    store = MemoryEventStore()
    event = demo_event().model_copy(update={"policy_snapshot": load_snapshot()})
    store.save_event(event)
    got = store.get_event("ev-demo")
    assert got == event and got.policy_snapshot.version == "1.0.0"
    assert store.get_event("nope") is None


def test_schemas_serialize_to_firestore_friendly_json_and_back():
    # Firestore には model_dump(mode="json") の辞書を書く。往復で同じ値に戻ること
    event = demo_event().model_copy(update={"policy_snapshot": load_snapshot()})
    assert Event.model_validate(event.model_dump(mode="json")) == event
    p = demo_participants()[0]
    assert type(p).model_validate(p.model_dump(mode="json")) == p
    r = calculate_split(event, demo_participants(), load_snapshot())
    assert type(r).model_validate(r.model_dump(mode="json")) == r


def test_participants_are_listed_by_user_id():
    store = MemoryEventStore()
    for p in demo_participants():
        store.save_participant("ev-demo", p)
    ids = [p.user_id for p in store.list_participants("ev-demo")]
    assert ids == sorted(ids) and len(ids) == 10
    assert store.list_participants("other") == []


def test_split_can_be_recomputed_until_it_is_approved():
    store = MemoryEventStore()
    policy = load_snapshot()
    first = calculate_split(demo_event(), demo_participants(), policy)
    store.save_split(first)
    corrected = calculate_split(demo_event(61_000), demo_participants(), policy)
    store.save_split(corrected)  # 承認前なら、領収書の訂正で作り直せる
    assert store.get_split("ev-demo").hash == corrected.hash

    store.save_approval(
        Approval(
            event_id="ev-demo",
            approver_user_id=corrected.approver_user_id,
            split_hash=corrected.hash,
            status=ApprovalStatus.APPROVED,
            approved_at=dt.datetime(2026, 10, 31, tzinfo=dt.UTC),
        )
    )
    with pytest.raises(ApprovedSplitIsFinal):
        store.save_split(first)  # 承認された金額表は変えられない
    assert store.get_split("ev-demo").hash == corrected.hash


def test_receipt_and_budget_escalation_round_trip():
    from src.models.event import Receipt
    from src.models.split import BudgetEscalation

    store = MemoryEventStore()
    now = dt.datetime(2026, 10, 31, tzinfo=dt.UTC)
    receipt = Receipt(
        event_id="ev-demo", total_amount_yen=60_300, confirmed_by="uid", confirmed_at=now
    )
    store.save_receipt(receipt)
    assert store.get_receipt("ev-demo") == receipt and store.get_receipt("x") is None
    event = demo_event().model_copy(
        update={"budget_escalation": BudgetEscalation(organizer_confirmed_at=now)}
    )
    assert Event.model_validate(event.model_dump(mode="json")) == event
    assert type(receipt).model_validate(receipt.model_dump(mode="json")) == receipt
