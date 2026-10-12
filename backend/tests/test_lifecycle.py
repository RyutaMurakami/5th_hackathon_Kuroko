"""状態の進行・経緯・通知（B14）。進めるのは事実（出欠・確定・承認・入金）で、LLM ではない。"""

import pytest

from src.models.dashboard import NotificationKind, UploadKind
from src.models.event import EventStatus, RsvpStatus
from src.services.dashboard import DashboardError
from src.services.lifecycle import Lifecycle
from tests.test_dashboard import NOW, ORG, PLAN, at, make, mark_receipt_extracted, new_event

RES = {"venue_name": "炭火酒場 渋谷店", "datetime": "2026-10-23T19:00:00+09:00",
       "party_size": 8, "course_price_yen": 4500}  # fmt: skip


def set_rsvp(store, eid, answers: dict[str, RsvpStatus]):
    for p in store.list_participants(eid):
        if p.user_id in answers:
            store.save_participant(eid, p.model_copy(update={"rsvp_status": answers[p.user_id]}))


# ---------------- 計画の確定: 規程と参加者 ----------------
async def test_confirming_the_plan_attaches_the_policy_copy_and_the_roster_with_slack_ids():
    svc, store, _, disp = make()
    store.slack_users = {"kurao": "U-KURAO", "kanji": "U-TAKA"}
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    e = store.get_event(eid)
    assert e.policy_snapshot is not None and e.policy_id and e.policy_version
    assert e.organizer_user_id == "kanji"  # 銀行の口座の対応づけに使う名簿の幹事
    assert e.organizer_web_uid == "u-org" and set(e.guests_of_honor) == {"matsumoto", "inoue"}
    people = {p.user_id: p for p in store.list_participants(eid)}
    assert len(people) == 10 and people["kurao"].slack_user_id == "U-KURAO"
    assert people["kato"].slack_user_id is None  # 対応が無い人には DM を送れない
    assert disp.started == [eid]


async def test_the_decision_log_records_who_did_what_without_raw_text():
    svc, store, *_ = make()
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    log = svc.get_event(ORG, eid)["decision_log"]
    assert [d["actor"] for d in log] == ["human", "kuroko"]
    assert "計画を確定" in log[0]["summary"] and log[0]["action_type"] == "確認"
    assert "来週金曜に飲み会" not in str(log)  # チャットの原文は残さない


# ---------------- 出欠が出そろったら店の選択へ ----------------
async def test_rsvp_completion_moves_to_venue_selection_only_when_everyone_answered():
    svc, store, *_ = make()
    life = Lifecycle(store=store, now=lambda: NOW)
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    payers = [p.user_id for p in store.list_participants(eid) if p.role.value == "participant"]
    set_rsvp(store, eid, {u: RsvpStatus.ATTENDING for u in payers[:-1]})
    life.after_rsvp(eid)
    assert store.get_event(eid).status is EventStatus.RSVP  # 1人まだ
    set_rsvp(store, eid, {payers[-1]: RsvpStatus.DECLINING})
    life.after_rsvp(eid)
    assert store.get_event(eid).status is EventStatus.VENUE
    (n,) = [
        n for n in store.list_notifications("u-org") if n.kind is NotificationKind.CONFIRM_NEEDED
    ]
    assert "店を選んで" in n.text
    life.after_rsvp(eid)  # 二度呼んでも、通知が増えない
    assert len(store.list_notifications("u-org")) == 1


# ---------------- 予約 → 開催 → 領収書 → 按分 ----------------
async def test_reservation_within_budget_books_the_event_and_held_opens_the_receipt_step():
    svc, store, _, disp = make()
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    e = store.get_event(eid)
    store.save_event(e.model_copy(update={"status": EventStatus.VENUE}))
    out = await svc.confirm_extraction(ORG, eid, UploadKind.RESERVATION, RES, "manual")
    assert out["over_budget"] is False and store.get_event(eid).status is EventStatus.BOOKED
    svc.mark_event_held(ORG, eid)
    assert store.get_event(eid).status is EventStatus.RECEIPT
    with pytest.raises(DashboardError):
        svc.mark_event_held(ORG, eid)  # 二度は押せない


async def test_confirming_the_receipt_starts_the_split_approval_once():
    svc, store, _, disp = make()
    eid = await at(svc, EventStatus.RECEIPT)
    mark_receipt_extracted(svc, store, eid)
    await svc.confirm_extraction(
        ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 49500}, "extracted"
    )
    assert store.get_event(eid).status is EventStatus.SPLIT and disp.approvals == [eid]
    with pytest.raises(DashboardError) as e:  # 按分に進んだあとは、金額を変えられない
        await svc.confirm_extraction(
            ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 1}, "extracted"
        )
    assert e.value.status == 409 and disp.approvals == [eid]


@pytest.mark.parametrize("status", [s for s in EventStatus if s is not EventStatus.RECEIPT])
async def test_a_receipt_can_only_be_confirmed_at_the_receipt_step(status):
    svc, store, _, disp = make()
    eid = await at(svc, status)
    mark_receipt_extracted(svc, store, eid)
    with pytest.raises(DashboardError) as e:
        await svc.confirm_extraction(
            ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 100}, "extracted"
        )
    assert e.value.status == 409 and store.get_receipt(eid) is None and disp.approvals == []


async def test_a_reservation_can_only_be_confirmed_while_choosing_the_venue():
    svc, store, *_ = make()
    for status in (EventStatus.PLANNING, EventStatus.RSVP, EventStatus.BOOKED, EventStatus.RECEIPT):
        eid = await at(svc, status)
        with pytest.raises(DashboardError):
            await svc.confirm_extraction(ORG, eid, UploadKind.RESERVATION, RES, "manual")


# ---------------- 予算超過（SPEC 9.1） ----------------
async def over_budget_event():
    svc, store, _, disp = make()
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    limit = store.get_event(eid).policy_snapshot.hard_limit_per_person_yen
    store.save_event(store.get_event(eid).model_copy(update={"status": EventStatus.VENUE}))
    out = await svc.confirm_extraction(
        ORG, eid, UploadKind.RESERVATION, {**RES, "course_price_yen": int(limit) + 1}, "manual"
    )
    return svc, store, disp, eid, out


async def test_an_over_budget_reservation_waits_for_the_two_step_confirmation():
    svc, store, disp, eid, out = await over_budget_event()
    assert out["over_budget"] is True and store.get_event(eid).status is EventStatus.VENUE
    await svc.confirm_budget_overrun(ORG, eid)  # 幹事の確認 → 承認者へ（Slack）
    e = store.get_event(eid)
    assert e.budget_escalation.organizer_confirmed_at is not None and disp.budgets == [eid]
    assert e.status is EventStatus.VENUE  # 承認者の最終確認までは進まない
    with pytest.raises(DashboardError) as err:
        await svc.confirm_budget_overrun(ORG, eid)
    assert err.value.code == "already_confirmed" and disp.budgets == [eid]
    # 承認者の最終確認（Slack）が済んだら、予約が確定する
    life = Lifecycle(store=store, now=lambda: NOW)
    life.after_budget_final(eid)
    assert store.get_event(eid).status is EventStatus.VENUE  # まだ最終確認が無い
    esc = store.get_event(eid).budget_escalation
    store.save_event(store.get_event(eid).model_copy(update={
        "budget_escalation": esc.model_copy(update={"final_confirmed_at": NOW})}))  # fmt: skip
    life.after_budget_final(eid)
    assert store.get_event(eid).status is EventStatus.BOOKED


async def test_budget_overrun_confirmation_is_refused_when_not_over_or_out_of_step():
    svc, store, *_ = make()
    eid = await new_event(svc)
    await svc.confirm_event_plan(ORG, eid, PLAN)
    store.save_event(store.get_event(eid).model_copy(update={"status": EventStatus.VENUE}))
    with pytest.raises(DashboardError):  # 予約がまだ無い
        await svc.confirm_budget_overrun(ORG, eid)
    await svc.confirm_extraction(
        ORG, eid, UploadKind.RESERVATION, RES, "manual"
    )  # 上限以内 → BOOKED
    with pytest.raises(DashboardError):
        await svc.confirm_budget_overrun(ORG, eid)


async def test_other_people_cannot_confirm_the_overrun_or_mark_the_event_held():
    from tests.test_dashboard import G1, ORG2

    svc, store, disp, eid, _ = await over_budget_event()
    for actor in (ORG2, G1):
        with pytest.raises(DashboardError) as e:
            await svc.confirm_budget_overrun(actor, eid)
        assert e.value.status == 404
        with pytest.raises(DashboardError):
            svc.mark_event_held(actor, eid)
    assert disp.budgets == []


async def test_event_detail_exposes_the_overrun_state_and_clears_it_when_within_budget():
    svc, store, disp, eid, _ = await over_budget_event()
    b = svc.get_event(ORG, eid)["budget_overrun"]
    assert b["course_price_yen"] > b["limit_yen"] and not b["organizer_confirmed"]
    await svc.confirm_budget_overrun(ORG, eid)
    b = svc.get_event(ORG, eid)["budget_overrun"]
    assert b["organizer_confirmed"] is True and b["approver_confirmed"] is False
    svc2, *_ = make()
    ok = await new_event(svc2)
    assert svc2.get_event(ORG, ok)["budget_overrun"] is None
