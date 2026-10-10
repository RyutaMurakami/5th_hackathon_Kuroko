"""Web ダッシュボードの API（B14）: 権限の分離・入力の検査・Slack との境界。"""

import datetime as dt

import pytest
from fastapi import HTTPException

from src.config import get_settings
from src.db.events import MemoryEventStore
from src.main import app
from src.models.dashboard import Actor, Role, UploadKind
from src.models.event import EventStatus
from src.routers import dashboard as router
from src.services import dashboard_auth
from src.services.dashboard import (
    DashboardError,
    DashboardService,
    validate_plan,
    validate_reservation,
)
from tests.sample_company import demo_participants
from tests.test_tasks import _token

DASH_SA = "sa-dashboard@test.iam.gserviceaccount.com"
NOW = dt.datetime(2026, 10, 10, 12, 0, tzinfo=dt.UTC)
ORG = Actor(uid="u-org", email="org@example.com", role=Role.ORGANIZER)
ORG2 = Actor(uid="u-org2", email="org2@example.com", role=Role.ORGANIZER)
G1 = Actor(uid="g1", email="g1@example.com", role=Role.GUEST)
G2 = Actor(uid="g2", email="g2@example.com", role=Role.GUEST)
PLAN = {
    "title": "歓送迎会", "datetime": "2026-10-23T19:00:00+09:00", "area": "渋谷",
    "party_size": 8, "budget_per_person_yen": 5000, "required_tags": ["個室", "ほげ"],
}  # fmt: skip


class Signer:
    def __init__(self):
        self.sizes: dict[str, int] = {}
        self.blobs: dict[str, bytes] = {}

    def signed_put_url(self, path, content_type, ttl_seconds):
        return f"https://storage.test/{path}?ct={content_type}&ttl={ttl_seconds}"

    def object_size(self, path):
        return self.sizes.get(path)

    def read_bytes(self, path):
        return self.blobs.get(path)


class Dispatcher:
    def __init__(self):
        self.started: list[str] = []

    async def start_rsvp(self, event_id):
        self.started.append(event_id)


def make(chat=None):
    async def default(key, text):
        return f"了解: {text}"

    store, signer, disp = MemoryEventStore(), Signer(), Dispatcher()
    svc = DashboardService(store=store, chat=chat or default, signer=signer, dispatcher=disp,
                           now=lambda: NOW)  # fmt: skip
    return svc, store, signer, disp


async def new_event(svc, actor=ORG):
    return (await svc.send_message(actor, None, "来週金曜に飲み会"))["event_id"]


def mark_receipt_extracted(svc, store, eid):
    up = svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 10)
    store.save_upload(store.get_upload(eid, up["upload_id"]).model_copy(
        update={"status": "registered", "extraction_status": "done"}))  # fmt: skip


# ---------------- 権限の分離 ----------------
async def test_first_message_creates_a_planning_event_owned_by_the_sender():
    svc, store, *_ = make()
    out = await svc.send_message(ORG, None, "来週金曜、チーム8人で飲みたい")
    e = store.get_event(out["event_id"])
    assert e.status is EventStatus.PLANNING and e.organizer_web_uid == "u-org" and not e.sandbox
    assert out["reply"]["role"] == "kuroko" and out["reply"]["text"].startswith("了解")


async def test_other_peoples_events_look_nonexistent_for_every_operation():
    svc, store, *_ = make()
    eid = await new_event(svc)
    for actor in (ORG2, G1):
        calls = [
            lambda a=actor: svc.get_event(a, eid),
            lambda a=actor: svc.issue_upload_url(a, eid, UploadKind.RECEIPT, "image/png", 10),
            lambda a=actor: svc.confirm_extraction(a, eid, UploadKind.RECEIPT, {}, "extracted"),
            lambda a=actor: svc.select_venue(a, eid, "p", "n"),
        ]
        for call in calls:
            with pytest.raises(DashboardError) as e:
                call()
            assert (e.value.code, e.value.status) == ("event_not_found", 404)
        with pytest.raises(DashboardError):
            await svc.send_message(actor, eid, "のっとり")
        with pytest.raises(DashboardError):
            await svc.confirm_event_plan(actor, eid, PLAN)
    assert svc.list_events(ORG2) == [] and svc.list_events(G1) == []
    assert len(store.list_messages(eid)) == 2  # 他人の発言は入らない


async def test_a_guest_sees_only_their_own_sandbox_events_and_never_a_real_one():
    svc, store, *_ = make()
    real = await new_event(svc, ORG)
    mine = await new_event(svc, G1)
    assert store.get_event(mine).sandbox and store.get_event(mine).guest_owner_uid == "g1"
    assert [e["event_id"] for e in svc.list_events(G1)] == [mine]
    with pytest.raises(DashboardError):
        svc.get_event(G2, mine)  # 別のゲストには見えない
    with pytest.raises(DashboardError):
        svc.get_event(G1, real)
    # 幹事の一覧に sandbox は出ない（幹事 = 許可リストのアカウント）
    assert [e["event_id"] for e in svc.list_events(ORG)] == [real]
    # 開発者でも、幹事の画面は自分の本番のイベントだけ。sandbox は開けない
    store.get_event(mine).guest_owner_uid = "u-org"
    other = store.get_event(mine).model_copy(update={"guest_owner_uid": "u-org"})
    store.save_event(other)
    with pytest.raises(DashboardError):
        svc.get_event(ORG, mine)


async def test_guest_limits_two_events_and_thirty_messages():
    svc, *_ = make()
    e1 = await new_event(svc, G1)
    await new_event(svc, G1)
    with pytest.raises(DashboardError) as e:
        await new_event(svc, G1)
    assert e.value.status == 429
    for _ in range(29):  # 最初の1通と合わせて30通
        await svc.send_message(G1, e1, "続き")
    with pytest.raises(DashboardError) as e:
        await svc.send_message(G1, e1, "31通目")
    assert e.value.code == "guest_message_limit"
    await svc.send_message(G2, None, "別のゲストは影響を受けない")


async def test_sandbox_events_expire_after_seven_days_and_are_purged_with_their_data():
    clock = {"now": NOW}
    svc, store, *_ = make()
    svc._now = lambda: clock["now"]
    g = await new_event(svc, G1)
    real = await new_event(svc, ORG)
    assert store.get_event(g).expires_at == NOW + dt.timedelta(days=7)
    assert svc.purge_expired_sandbox() == 0
    clock["now"] = NOW + dt.timedelta(days=7, seconds=1)
    assert svc.purge_expired_sandbox() == 1
    assert store.get_event(g) is None and store.list_messages(g) == []
    assert store.get_event(real) is not None  # 本番のイベントは消さない


# ---------------- チャット ----------------
async def test_text_is_checked_and_an_agent_failure_becomes_a_fixed_reply_without_details():
    async def broken(key, text):
        raise RuntimeError("secret internal detail")

    svc, store, *_ = make(chat=broken)
    for bad in ("", "   ", "あ" * 2001):
        with pytest.raises(DashboardError):
            await svc.send_message(ORG, None, bad)
    out = await svc.send_message(ORG, None, "こんにちは")
    assert out["reply"]["status"] == "failed" and "secret" not in out["reply"]["text"]


async def test_conversation_key_is_per_event_and_user_not_shared():
    keys = []

    async def spy(key, text):
        keys.append(key)
        return "ok"

    svc, *_ = make(chat=spy)
    e = await new_event(svc, ORG)
    await svc.send_message(ORG, e, "もう一度")
    await new_event(svc, ORG2)
    assert keys[0] == keys[1] == f"web:{e}:u-org" and keys[2] != keys[0]


# ---------------- 計画の確認 ----------------
async def test_confirming_the_plan_starts_rsvp_once_and_only_from_planning():
    svc, store, _, disp = make()
    eid = await new_event(svc)
    out = await svc.confirm_event_plan(ORG, eid, PLAN)
    e = store.get_event(eid)
    assert out["status"] == "rsvp" and disp.started == [eid]
    assert e.plan_required_tags == ["個室"] and e.plan["party_size"] == 8  # 語彙外は捨てる
    with pytest.raises(DashboardError) as err:
        await svc.confirm_event_plan(ORG, eid, PLAN)
    assert err.value.status == 409 and disp.started == [eid]  # 二重に進めない


@pytest.mark.parametrize("patch", [
    {"datetime": "来週"}, {"title": ""}, {"party_size": 1}, {"party_size": 51},
    {"party_size": True},
    {"budget_per_person_yen": 0}, {"budget_per_person_yen": 100001}, {"area": "あ" * 41},
])  # fmt: skip
async def test_invalid_plans_are_rejected_and_nothing_starts(patch):
    svc, store, _, disp = make()
    eid = await new_event(svc)
    with pytest.raises(DashboardError):
        await svc.confirm_event_plan(ORG, eid, {**PLAN, **patch})
    assert disp.started == [] and store.get_event(eid).status is EventStatus.PLANNING


# ---------------- アップロード ----------------
async def test_upload_flow_checks_type_size_count_and_the_real_size():
    svc, store, signer, _ = make()
    eid = await new_event(svc)
    for ct, size in (("text/html", 10), ("application/x-sh", 10), ("image/png", 0),
                     ("image/png", 5 * 1024 * 1024 + 1)):  # fmt: skip
        with pytest.raises(DashboardError):
            svc.issue_upload_url(ORG, eid, UploadKind.RESERVATION, ct, size)
    issued = svc.issue_upload_url(ORG, eid, UploadKind.RESERVATION, "image/png", 1000)
    assert (
        issued["url"].startswith("https://storage.test/events/") and "ct=image/png" in issued["url"]
    )
    up = store.get_upload(eid, issued["upload_id"])
    signer.sizes[up.object_path] = 999
    assert (await svc.register_upload(ORG, eid, up.upload_id))["status"] == "registered"
    with pytest.raises(DashboardError):  # 二重の登録はできない
        await svc.register_upload(ORG, eid, up.upload_id)


async def test_a_server_side_size_check_rejects_oversized_or_missing_objects():
    svc, store, signer, _ = make()
    eid = await new_event(svc)
    big = svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "application/pdf", 1000)
    signer.sizes[store.get_upload(eid, big["upload_id"]).object_path] = 6 * 1024 * 1024
    with pytest.raises(DashboardError):
        await svc.register_upload(ORG, eid, big["upload_id"])  # 申告より実際が大きい
    assert store.get_upload(eid, big["upload_id"]).status == "rejected"
    gone = svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 10)
    with pytest.raises(DashboardError):
        await svc.register_upload(ORG, eid, gone["upload_id"])  # 実際には置かれていない


async def test_upload_counts_are_limited_per_event_and_pasting_a_receipt_is_not_allowed():
    svc, *_ = make()
    eid = await new_event(svc)
    for _ in range(2):
        svc.issue_upload_url(ORG, eid, UploadKind.RESERVATION, "image/png", 1, "paste")
    with pytest.raises(DashboardError) as e:
        svc.issue_upload_url(ORG, eid, UploadKind.RESERVATION, "image/png", 1)
    assert e.value.status == 429
    for _ in range(3):
        svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 1)
    with pytest.raises(DashboardError):
        svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 1)
    with pytest.raises(DashboardError) as e:
        svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 1, "paste")
    assert e.value.code == "paste_not_allowed"


async def test_someone_elses_upload_id_cannot_be_registered():
    svc, store, signer, _ = make()
    a, b = await new_event(svc, ORG), await new_event(svc, ORG2)
    up = svc.issue_upload_url(ORG, a, UploadKind.RECEIPT, "image/png", 10)
    signer.sizes[store.get_upload(a, up["upload_id"]).object_path] = 10
    with pytest.raises(DashboardError):
        await svc.register_upload(ORG2, b, up["upload_id"])  # 別のイベントの upload_id
    with pytest.raises(DashboardError):
        await svc.register_upload(ORG2, a, up["upload_id"])


# ---------------- 確定（Policy Gate 6.1 の「幹事により確定済み」）----------------
async def test_confirming_a_receipt_records_who_confirmed_and_feeds_gate_6_1():
    svc, store, *_ = make()
    eid = await new_event(svc)
    mark_receipt_extracted(svc, store, eid)
    svc.confirm_extraction(ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 48000}, "extracted")
    r = store.get_receipt(eid)
    assert (r.total_amount_yen, r.source, r.confirmed_by) == (48000, "upload", "u-org")
    assert store.get_event(eid).total_amount_yen == 48000


@pytest.mark.parametrize("amount", [0, -5, 10_000_001, "48000", 480.5, None, True])
async def test_receipt_amounts_are_range_and_type_checked_for_manual_and_extracted_alike(amount):
    svc, store, *_ = make()
    eid = await new_event(svc)
    up = svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 1)
    store.save_upload(store.get_upload(eid, up["upload_id"]).model_copy(
        update={"extraction_status": "failed"}))  # fmt: skip
    for source in ("extracted", "manual"):
        with pytest.raises(DashboardError):
            svc.confirm_extraction(
                ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": amount}, source
            )
    assert store.get_receipt(eid) is None


async def test_manual_receipt_entry_is_only_allowed_after_a_failed_reading():
    svc, store, *_ = make()
    eid = await new_event(svc)
    with pytest.raises(DashboardError) as e:
        svc.confirm_extraction(ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 100}, "manual")
    assert e.value.code == "manual_not_allowed"
    up = svc.issue_upload_url(ORG, eid, UploadKind.RECEIPT, "image/png", 1)
    store.save_upload(store.get_upload(eid, up["upload_id"]).model_copy(
        update={"extraction_status": "failed"}))  # fmt: skip
    svc.confirm_extraction(ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": 100}, "manual")
    assert store.get_receipt(eid).source == "manual"


async def test_reservation_values_are_validated_and_the_source_is_recorded():
    svc, store, *_ = make()
    eid = await new_event(svc)
    ok = {"venue_name": "炭火 酒場", "datetime": "2026-10-23T19:00:00+09:00",
          "party_size": 8, "course_price_yen": 4500}  # fmt: skip
    svc.confirm_extraction(ORG, eid, UploadKind.RESERVATION, ok, "manual")
    assert store.get_event(eid).venue["source"] == "manual"
    for patch in ({"venue_name": ""}, {"party_size": 0}, {"course_price_yen": 0},
                  {"course_price_yen": "4500"}, {"datetime": "x"}):  # fmt: skip
        with pytest.raises(DashboardError):
            svc.confirm_extraction(ORG, eid, UploadKind.RESERVATION, {**ok, **patch}, "extracted")


# ---------------- 通知 ----------------
async def test_notifications_are_private_to_the_recipient():
    svc, *_ = make()
    svc.notify(
        "u-org",
        "ev",
        __import__("src.models.dashboard", fromlist=["x"]).NotificationKind.COMPLETED,
        "完了",
    )
    (n,) = svc.list_notifications(ORG)
    assert svc.list_notifications(ORG2) == []
    with pytest.raises(DashboardError) as e:
        svc.mark_read(ORG2, n["notification_id"])
    assert e.value.status == 404
    svc.mark_read(ORG, n["notification_id"])
    assert svc.list_notifications(ORG)[0]["read"] is True


# ---------------- Slack との境界 ----------------
async def test_event_detail_shows_who_we_wait_for_without_exposing_actions():
    svc, store, *_ = make()
    eid = await new_event(svc)
    assert svc.get_event(ORG, eid)["waiting_for"]["where"] == "web"
    for p in demo_participants():
        store.save_participant(eid, p)
    store.save_event(store.get_event(eid).model_copy(update={"status": EventStatus.APPROVAL}))
    w = svc.get_event(ORG, eid)["waiting_for"]
    assert (w["who"], w["where"]) == ("approver", "slack")
    assert "slack_user_id" not in str(svc.get_event(ORG, eid)["participants"])


def test_there_is_no_dashboard_route_for_mandates_approvals_revocation_or_transfers():
    paths = [r.path for r in router.router.routes]
    banned = ("mandate", "approve", "approval", "revoke", "transfer", "payment", "consent", "sign")
    assert not [p for p in paths if any(b in p for b in banned)]
    assert not [r for r in app.routes if "dashboard" in getattr(r, "path", "") and "demo" in r.path]


# ---------------- 利用者の確認（Firebase） ----------------
class Verifier:
    def __init__(self, claims=None, error=False):
        self.claims, self.error = claims, error

    def verify(self, token):
        if self.error:
            raise ValueError("bad")
        return self.claims


GOOD = {"sub": "u1", "email": "a@example.com", "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"}}  # fmt: skip


@pytest.fixture
def store(monkeypatch):
    s = MemoryEventStore()
    s.users["org@example.com"] = "organizer"
    monkeypatch.setattr(dashboard_auth, "get_event_store", lambda: s)
    return s


def test_allow_list_makes_an_organizer_and_everyone_else_a_guest(store):
    org = dashboard_auth.resolve_actor(Verifier({**GOOD, "email": "Org@Example.com"}), "t")
    assert org.role is Role.ORGANIZER
    assert dashboard_auth.resolve_actor(Verifier(GOOD), "t").role is Role.GUEST


@pytest.mark.parametrize("claims", [
    {**GOOD, "email_verified": False}, {**GOOD, "email": None}, {**GOOD, "sub": None},
    {**GOOD, "firebase": {"sign_in_provider": "anonymous"}}, {"sub": "x"},
])  # fmt: skip
def test_unverified_anonymous_or_incomplete_tokens_are_rejected(store, claims):
    with pytest.raises(HTTPException) as e:
        dashboard_auth.resolve_actor(Verifier(claims), "t")
    assert e.value.status_code == 401


def test_missing_or_invalid_tokens_are_401_and_the_kill_switch_stops_guests_only(store):
    for v, tok in ((Verifier(error=True), "bad"), (Verifier(GOOD), None), (Verifier(GOOD), "")):
        with pytest.raises(HTTPException) as e:
            dashboard_auth.resolve_actor(v, tok)
        assert e.value.status_code == 401
    store.guest_switch = False
    with pytest.raises(HTTPException) as e:
        dashboard_auth.resolve_actor(Verifier(GOOD), "t")
    assert e.value.status_code == 403
    org = {**GOOD, "email": "org@example.com"}
    assert dashboard_auth.resolve_actor(Verifier(org), "t").role is Role.ORGANIZER


def test_unconfigured_firebase_project_rejects_everything():
    with pytest.raises(ValueError):
        dashboard_auth.GoogleFirebaseVerifier("").verify("any")


# ---------------- HTTP 層 ----------------
@pytest.fixture
def http(monkeypatch, store):
    svc, st, *_ = make()
    monkeypatch.setenv("DASHBOARD_SERVICE_ACCOUNT", DASH_SA)
    get_settings.cache_clear()
    monkeypatch.setattr(router, "get_dashboard", lambda: svc)
    monkeypatch.setattr(dashboard_auth, "get_firebase_verifier", lambda: Verifier(GOOD))
    return svc


async def test_only_the_dashboard_service_account_can_call_the_api(client, http):
    h = {"Authorization": _token(DASH_SA), "X-Firebase-Token": "t"}
    assert (await client.get("/api/dashboard/events", headers=h)).status_code == 200
    for bad in (_token("attacker@example.com"), _token("sa-gateway@test.iam.gserviceaccount.com")):
        res = await client.get("/api/dashboard/events", headers={**h, "Authorization": bad})
        assert res.status_code == 403
    assert (
        await client.get("/api/dashboard/events", headers={"X-Firebase-Token": "t"})
    ).status_code == 403


async def test_a_valid_service_call_without_a_user_token_is_unauthenticated(client, http):
    res = await client.get("/api/dashboard/events", headers={"Authorization": _token(DASH_SA)})
    assert res.status_code == 401


async def test_http_round_trip_chat_then_detail_and_error_codes(client, http):
    h = {"Authorization": _token(DASH_SA), "X-Firebase-Token": "t"}
    sent = await client.post("/api/dashboard/messages", json={"text": "来週飲みたい"}, headers=h)
    eid = sent.json()["event_id"]
    detail = await client.get(f"/api/dashboard/events/{eid}", headers=h)
    assert detail.status_code == 200 and len(detail.json()["messages"]) == 2
    assert (await client.get("/api/dashboard/events/nope", headers=h)).status_code == 404
    bad = await client.post("/api/dashboard/messages", json={"text": "あ" * 2001}, headers=h)
    assert bad.status_code == 422
    res = await client.post(
        f"/api/dashboard/events/{eid}/confirm-plan", json={"plan": {}}, headers=h
    )
    assert (res.status_code, res.json()["detail"]) == (400, "invalid_plan")


# ---------------- 進行ヒント ----------------
async def test_every_status_has_a_hint_that_only_guides_and_never_acts():
    svc, store, *_ = make()
    eid = await new_event(svc)
    seen = {}
    for status in EventStatus:
        store.save_event(store.get_event(eid).model_copy(update={"status": status}))
        h = svc.get_event(ORG, eid)["hint"]
        assert (
            h["total"] == 9
            and 1 <= h["step"] <= 9
            and h["where"] in ("web", "slack", "bank", "system")
        )
        assert h["title"] and h["do"]
        seen[status] = h
    assert (
        seen[EventStatus.PLANNING]["where"] == "web"
        and "chat" in seen[EventStatus.PLANNING]["example"]
    )
    # Slack・銀行で人が行う段階は、そこで行うことを示すだけ（Web の操作として案内しない）
    assert (
        seen[EventStatus.APPROVAL]["where"] == "slack"
        and seen[EventStatus.PAYMENT]["where"] == "bank"
    )
    steps = [seen[s]["step"] for s in EventStatus]
    assert steps == sorted(steps)  # 段階が進むほど番号が進む


async def test_the_planning_example_passes_the_same_plan_validation():
    svc, *_ = make()
    eid = await new_event(svc)
    plan = svc.get_event(ORG, eid)["hint"]["example"]["plan"]
    validate_plan({**plan, "datetime": "2026-10-23T19:00:00+09:00"})  # 例のまま確定できる


async def test_the_reservation_and_receipt_examples_are_valid_values():
    svc, store, *_ = make()
    eid = await new_event(svc)
    store.save_event(store.get_event(eid).model_copy(update={"status": EventStatus.BOOKED}))
    validate_reservation(svc.get_event(ORG, eid)["hint"]["example"]["reservation"])
    store.save_event(store.get_event(eid).model_copy(update={"status": EventStatus.RECEIPT}))
    amount = svc.get_event(ORG, eid)["hint"]["example"]["receipt"]["total_amount_yen"]
    mark_receipt_extracted(svc, store, eid)
    svc.confirm_extraction(ORG, eid, UploadKind.RECEIPT, {"total_amount_yen": amount}, "extracted")
    assert svc.get_event(ORG, eid)["hint"]["example"]["confirmed"] is True


async def test_me_returns_only_the_role(client, http):
    h = {"Authorization": _token(DASH_SA), "X-Firebase-Token": "t"}
    res = await client.get("/api/dashboard/me", headers=h)
    assert res.json() == {"role": "guest"}


async def test_event_detail_returns_the_stored_split_as_is_and_the_approval_state():
    from src.models.split import Approval, SplitResult, SplitRow

    svc, store, *_ = make()
    eid = await new_event(svc)
    assert svc.get_event(ORG, eid)["split"] is None
    split = SplitResult(
        event_id=eid, policy_id="p", policy_version="1", total_amount_yen=48000,
        base_amount_yen=40000, subsidy_yen=8000, weight_sum=10.0, per_weight_yen=4000,
        rows=[SplitRow(user_id="ito", member_class_id="staff", weight=1.0, ratio_percent=100.0,
                       subsidy_eligible=True, share_yen=4000)],
        shortfall_yen=0, shortfall_to="ito", approver_user_id="ito", hash="h" * 8,
    )  # fmt: skip
    store.save_split(split)
    store.save_approval(Approval(event_id=eid, approver_user_id="ito", split_hash=split.hash))
    out = svc.get_event(ORG, eid)["split"]
    assert out["rows"][0]["share_yen"] == 4000 and out["total_amount_yen"] == 48000
    assert out["approval"] == {"approver_user_id": "ito", "status": "pending",
                               "approved_at": None, "split_hash": "h" * 8}  # fmt: skip
    with pytest.raises(DashboardError):
        svc.get_event(ORG2, eid)  # 他人には按分も見えない
