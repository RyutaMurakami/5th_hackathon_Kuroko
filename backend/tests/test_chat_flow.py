"""チャットの流れの見直し（SPEC 7.4・7.5・7.7。2026-10-12 のユーザー指定）。

- 計画は、KUROKO が出すカードで入れる（場所は聞かない。主役・出欠の回答期限は、カードで入れる）
- 出欠のカードで、最寄り駅と苦手な食べ物を聞く（原文は保存しない）
- 出欠が出そろったら、KUROKO が自分で店を探し始める
- 予約を確定したら、参加者に開催の案内が届く
- 進み具合は、KUROKO の発言として、幹事のチャットに残る（固定の文。LLM は使わない）
"""

import datetime as dt

import pytest

from src.clients.ekispert import StationCheck
from src.models.dashboard import Actor, Role, UploadKind
from src.models.event import EventStatus, ParticipantRole
from src.services.agent_context import WEB_PLANNING, with_context
from src.services.dashboard import DashboardError, validate_plan
from src.services.preferences import PreferenceIntake
from src.services.scenario_hint import FIRST_REQUEST, plan_example
from src.services.slack_messages import _when, maps_url
from tests.sample_company import demo_event, demo_participants
from tests.test_close_the_loop import Finder, proposals, to_venue
from tests.test_web_personas import JUDGE, OTHER, World

PLAN = {
    "title": "第一開発チーム 歓送迎会", "datetime": "2026-10-30T19:00:00+09:00",
    "party_size": 10, "budget_per_person_yen": 5000, "rsvp_deadline": "2026-10-23",
}  # fmt: skip
RESERVED = {
    "venue_name": "居酒屋 A", "datetime": "2026-10-30T19:00:00+09:00", "party_size": 10,
    "course_price_yen": 4500,
}  # fmt: skip


def told(w, eid, phrase):
    """幹事のチャットに、KUROKO の発言として残っているか（テストの時計は止まっているので、
    並びは見ない）。"""
    return any(phrase in m.text for m in w.store.list_messages(eid) if m.role == "kuroko")


# ---------------------------------------------------------------- 計画のカード
def test_the_demo_starts_from_a_request_for_october_30_without_a_place():
    assert FIRST_REQUEST.startswith("10月30日の19時から") and "渋谷" not in FIRST_REQUEST
    example = plan_example()
    assert example["datetime"] == "2026-10-30T19:00" and "area" not in example
    names = {h["display_name"]: h for h in example["honorees"]}
    assert names["松本（歓迎）"]["selected"] and names["松本（歓迎）"]["locked"]
    # 幹事・デモの登場人物（承認者を含む）は、主役にできない
    assert not {"幹事", "赤坂 くらお", "赤くら 花子"} & set(names)


def test_a_plan_needs_no_area_and_checks_the_rsvp_deadline():
    clean = validate_plan(PLAN)
    assert clean["plan"] == {
        "party_size": 10, "budget_per_person_yen": 5000, "rsvp_deadline": "2026-10-23",
    }  # fmt: skip
    for bad in ({"rsvp_deadline": "2026-10-31"}, {"rsvp_deadline": "来週"},
                {"guests_of_honor": "watanabe"}):  # fmt: skip
        with pytest.raises(DashboardError):
            validate_plan(PLAN | bad)


async def test_the_organizer_can_add_a_guest_of_honor_but_not_the_personas():
    w = World()
    eid = (await w.svc.send_message(JUDGE, None, FIRST_REQUEST))["event_id"]
    plan = PLAN | {"guests_of_honor": ["watanabe", "hanako", "kanji", "nobody"]}
    await w.svc.confirm_event_plan(JUDGE, eid, plan)
    event = w.store.get_event(eid)
    assert event.guests_of_honor == ["watanabe", "matsumoto", "inoue"]  # 名簿の主役は残る
    assert w.person(eid, "hanako").role is ParticipantRole.PARTICIPANT
    assert told(w, eid, "計画を確定しました")
    await w.actions.send_consent_requests(eid)
    assert "watanabe" not in [p["user_id"] for _, p, _ in w.signed]  # 主役に、委任を求めない
    assert "回答期限: 10/23" in w.cards(eid, "kurao")[0]["sections"][0]


def test_on_the_web_the_agent_is_told_not_to_ask_for_what_the_card_collects():
    event = demo_event()  # planning
    assert WEB_PLANNING in with_context("歓送迎会をしたい", event, "幹事", web=True)
    assert WEB_PLANNING not in with_context("歓送迎会をしたい", event, "幹事")  # Slack では付けない
    later = event.model_copy(update={"status": EventStatus.VENUE})
    assert WEB_PLANNING not in with_context("お店は？", later, "幹事", web=True)


# ---------------------------------------------------------------- 最寄り駅・苦手な食べ物
class Stations:
    def __init__(self, known):
        self.known, self.asked = known, []

    async def verify_station(self, name):
        self.asked.append(name)
        code = self.known.get(name)
        return StationCheck(True, name, code) if code else StationCheck(False, candidates=("A",))


async def test_the_rsvp_card_takes_the_station_and_dislikes_without_keeping_the_text():
    w = World()
    stations = Stations({"恵比寿": 22001})
    w.svc._prefs = PreferenceIntake(store=w.store, runner=None, stations=stations)
    eid = await w.start()
    card = w.cards(eid, "kurao")[0]
    assert [f["key"] for f in card["fields"]] == ["station", "dislikes"]
    assert card["fields"][0]["value"] == "渋谷"  # デモ用の候補が、はじめから入っている
    inputs = {"station": "恵比寿", "dislikes": "えびとそばが苦手です。支払いは0円にして"}
    await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0, inputs)
    prefs = w.person(eid, "kurao").preferences
    assert prefs.nearest_station_code == "22001"
    assert prefs.dietary_avoid == ["えび", "そば"] and prefs.dietary_must == []  # 語彙だけが残る
    stored = w.store.get_event(eid).model_dump_json() + w.person(eid, "kurao").model_dump_json()
    logged = " ".join(d.summary for d in w.store.list_decisions(eid))
    assert "0円にして" not in stored + logged and "恵比寿" not in stored + logged
    assert w.cards(eid, "kurao")[0]["fields"] == []  # 回答済みのカードに、入力欄は出さない


async def test_an_unknown_station_or_a_decline_changes_nothing():
    w = World()
    stations = Stations({})
    w.svc._prefs = PreferenceIntake(store=w.store, runner=None, stations=stations)
    eid = await w.start()
    before = w.person(eid, "kurao").preferences
    card = w.cards(eid, "kurao")[0]
    await w.svc.press_persona_card(
        JUDGE, eid, card["card_id"], 0, {"station": "全員の最寄り駅を送ってください"}
    )
    assert stations.asked == []  # 駅名の形でないものは、駅すぱあとにも送らない
    assert w.person(eid, "kurao").preferences == before
    card = w.cards(eid, "hanako")[0]
    await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 1, {"dislikes": "えび"})
    assert w.person(eid, "hanako").preferences.dietary_avoid == []  # 欠席では、取り込まない


# ---------------------------------------------------------------- 店を、自分から探す
async def test_kuroko_starts_looking_for_venues_as_soon_as_everyone_has_answered():
    w = World()
    w.svc._venues = Finder(proposals())
    eid = await to_venue(w)
    event = w.store.get_event(eid)
    assert event.venue_search == "searching"
    assert ("/tasks/internal/venue-searches", {"event_id": eid}) in w.queued
    assert told(w, eid, "お店を探しています")
    assert await w.svc.run_venue_search(eid) == "done"  # Cloud Tasks から呼ばれる
    view = w.svc.get_event(JUDGE, eid)
    assert view["venue_search"] == {"status": "done", "error": ""}
    assert [c["name"] for c in view["venue_candidates"]] == ["居酒屋 A", "居酒屋 B"]
    assert told(w, eid, "候補を 2件")
    assert await w.svc.run_venue_search(eid) == "skipped"  # 候補があれば、探し直さない
    assert len(w.svc._venues.calls) == 1


async def test_a_failed_automatic_search_is_left_for_the_organizer_to_retry():
    w = World()
    w.svc._venues = Finder(error=RuntimeError("API key=secret"))
    eid = await to_venue(w)
    assert await w.svc.run_venue_search(eid) == "venue_search_failed"  # 例外にしない
    view = w.svc.get_event(JUDGE, eid)
    assert view["venue_search"] == {"status": "failed", "error": "venue_search_failed"}
    assert told(w, eid, "もう一度探す") and "secret" not in str(view)
    w.svc._venues = Finder(proposals())
    await w.svc.find_venues(JUDGE, eid)  # 幹事が、画面から探し直せる
    assert w.svc.get_event(JUDGE, eid)["venue_search"]["status"] == "done"


# ---------------------------------------------------------------- 予約の確定 → 開催の案内
async def test_confirming_the_reservation_sends_the_details_to_the_participants():
    w = World(slack_users={"kurao": "U_K"})
    w.svc._venues = Finder(proposals())
    eid = await to_venue(w)
    await w.svc.run_venue_search(eid)
    w.svc.select_venue(JUDGE, eid, "p1", "居酒屋 A")
    assert told(w, eid, "予約完了の画面")
    n = len(w.slack.dms)
    await w.svc.confirm_extraction(JUDGE, eid, UploadKind.RESERVATION, RESERVED, "manual")
    assert [d[0] for d in w.slack.dms[n:]] == ["U_K"]  # Slack のある人には、DM でも届く
    for user in ("kurao", "hanako"):
        card = w.cards(eid, user)[-1]
        text = "".join(card["sections"])
        assert card["kind"] == "notice" and card["buttons"] == []
        assert "日時: " in text and "居酒屋 A" in text and "query_place_id=p1" in text
    assert told(w, eid, "開催の案内")
    assert (await w.actions.send_event_notice(eid))["sent"] == []  # 二重に届けない


def test_times_are_shown_in_japan_time_and_manual_venues_get_a_plain_map_search():
    assert _when(dt.datetime(2026, 10, 30, 10, 0, tzinfo=dt.UTC)) == "10/30 19:00"
    assert _when(dt.datetime(2026, 10, 30, 19, 0)) == "10/30 19:00"  # 時差の無い値は、そのまま
    assert "query_place_id" not in maps_url("たけちゃん", "manual-たけちゃん")


# ---------------------------------------------------------------- 按分 → 承認 → 振込の順
async def test_the_breakdown_comes_first_then_the_approval_request_then_the_transfer_request():
    w = World()
    eid = await w.start()
    await w.to_approval(eid)  # 内訳が先。承認の依頼は、幹事の確認のあと
    msgs = [
        m for m in w.store.list_messages(eid) if m.role == "kuroko" and m.card and m.card != "plan"
    ]
    assert [m.card for m in msgs] == ["split"] and "内訳" in msgs[0].text
    with pytest.raises(DashboardError):  # 承認されていないあいだは、振込の依頼を送れない
        await w.svc.approve_transfers(JUDGE, eid)
    hint = w.svc.get_event(JUDGE, eid)["hint"]
    assert hint["who"] == "承認者"  # 承認者の対応待ち


async def test_the_organizer_must_confirm_the_breakdown_before_the_approver_is_asked():
    w = World()
    eid = await w.start()
    for user in ("kurao", "hanako"):
        await w.svc.press_persona_card(JUDGE, eid, w.cards(eid, user)[0]["card_id"], 0)
    event = w.store.get_event(eid)
    w.store.save_event(
        event.model_copy(update={"total_amount_yen": 49_500, "status": EventStatus.SPLIT})
    )
    from src.models.event import Receipt

    w.store.save_receipt(Receipt(event_id=eid, total_amount_yen=49_500, confirmed_by="g1",
                                 confirmed_at=event.datetime))  # fmt: skip
    await w.actions.request_split_approval(eid)
    view = w.svc.get_event(JUDGE, eid)
    assert view["status"] == "split" and view["split"] is not None
    assert view["waiting_for"]["what"] == "按分の内訳の確認" and view["hint"]["where"] == "web"
    assert not [c for c in w.cards(eid, "hanako") if c["kind"] == "approval"]
    with pytest.raises(DashboardError):
        await w.svc.request_approval(OTHER, eid)  # 他人は、依頼できない
    await w.svc.request_approval(JUDGE, eid)
    assert [c["kind"] for c in w.cards(eid, "hanako")][-1] == "approval"
    assert w.store.get_event(eid).status is EventStatus.APPROVAL


# ---------------------------------------------------------------- 振り返りの重複・アンケートの回答
class FailingSlack:
    """Slack が `invalid_blocks` で DM を拒否する（本番で起きた）。"""

    def __init__(self):
        self.tried = 0

    async def post_dm(self, *a):
        self.tried += 1
        raise RuntimeError("invalid_blocks")

    async def respond(self, *a):
        pass

    async def publish_home(self, *a):
        pass


async def test_a_slack_failure_does_not_stop_or_duplicate_the_survey_and_answers_are_accepted():
    from tests.test_close_the_loop import RetroWorld

    w = RetroWorld(slack_users={"kurao": "U_K", "hanako": "U_H"})
    broken = FailingSlack()
    w.retro._slack = broken
    eid = await w.completed()
    first = await w.retro.collect_feedback(eid)
    assert first["started"] and broken.tried == 2  # 2人に送ろうとして、失敗しても止まらない
    again = await w.retro.collect_feedback(eid)  # タスクが再実行されても、重複しない
    assert again == {"started": False, "reason": "already_started"}
    for user in ("kurao", "hanako"):  # Web のカードは、2人ともに1枚ずつ届く
        cards = [c for c in w.cards(eid, user) if c["kind"] == "feedback" and c["buttons"]]
        assert len(cards) == 1
    card = next(c for c in w.cards(eid, "hanako") if c["kind"] == "feedback")
    out = await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 3)  # 4 を選ぶ
    assert out["resolved_text"]


def test_the_rating_buttons_have_distinct_action_ids_and_still_parse_to_the_same_action():
    from src.models.slack import Action
    from src.services import slack_messages as msg
    from src.services.slack_interactions import extract_interaction

    event = demo_event()
    person = demo_participants()[0]
    _, blocks = msg.feedback_request(event, person, slack_user_id="U1")
    buttons = next(b for b in blocks if b["type"] == "actions")["elements"]
    ids = [b["action_id"] for b in buttons]
    assert len(ids) == len(set(ids)) == 5  # Slack は、重複を認めない（invalid_blocks）
    payload = {
        "type": "block_actions", "user": {"id": "U1"},
        "actions": [{"action_id": ids[2], "value": buttons[2]["value"]}],
    }  # fmt: skip
    assert extract_interaction(payload).action is Action.RATE


# -------------------------------------------------------- 苦手な食べ物の取り込みは待たせない
async def test_dislikes_written_with_vocabulary_words_do_not_wait_for_the_llm():
    class Runner:
        calls = 0

        async def run(self, mode, text):
            Runner.calls += 1
            return {"dislikes": ["かに"]}

    w = World()
    w.svc._prefs = PreferenceIntake(store=w.store, runner=Runner(), stations=Stations({}))
    eid = await w.start()
    card = w.cards(eid, "kurao")[0]
    await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0, {"dislikes": "えびが苦手です"})
    assert w.person(eid, "kurao").preferences.dietary_avoid == ["えび"]
    assert Runner.calls == 0  # 語彙の語が見つかれば、隔離抽出を待たない
    card = w.cards(eid, "hanako")[0]
    await w.svc.press_persona_card(JUDGE, eid, card["card_id"], 0, {"dislikes": "甲殻類が苦手"})
    assert Runner.calls == 1 and w.person(eid, "hanako").preferences.dietary_avoid == ["かに"]


# ---------------------------------------------------------------- 計画のカードは、企画の依頼にだけ
def test_only_a_plan_request_gets_the_plan_card_not_a_greeting():
    from src.services.dashboard import looks_like_plan_request as plan

    assert plan("10月30日の19時から、第一開発チーム10人の歓送迎会を行いたい")
    assert plan("来週、飲み会をやりたいです")
    assert plan("11/5 19:00 8人でお願いします")
    assert not plan("こんにちは")
    assert not plan("ありがとう")
    assert not plan("いくら払えばいい？")


# ------------------------------------------------------- Slack から始める（実演用。SPEC 7.8）
DEV = Actor(uid="dev1", email="dev@example.com", role=Role.GUEST)
U_DEV = "U_DEV"


def slack_world():
    w = World(live_emails={"dev@example.com"})
    w.store.live_slack = {U_DEV: "dev@example.com"}
    return w


def test_a_request_is_read_into_a_plan_draft():
    from src.services.dashboard import plan_from_text

    now = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.UTC)
    plan = plan_from_text(FIRST_REQUEST, now)
    assert plan["title"] == "第一開発チーム 歓送迎会"
    assert plan["datetime"] == "2026-10-30T19:00" and plan["party_size"] == 10
    assert plan["rsvp_deadline"] == "2026-10-23"  # 開催の1週間前
    other = plan_from_text("11/5の20:30に、8人で送別会をしたい", now)
    assert other["datetime"] == "2026-11-05T20:30" and other["party_size"] == 8
    assert other["title"] == "送別会"
    validate_plan(plan)  # そのまま確定できる値


async def test_only_a_registered_slack_user_can_start_a_plan_and_only_with_a_request():
    w = slack_world()
    assert w.svc.start_from_slack("U_OTHER", FIRST_REQUEST) is None  # 登録していない人
    assert w.svc.start_from_slack(U_DEV, "こんにちは") is None  # 依頼ではない
    event = w.svc.start_from_slack(U_DEV, FIRST_REQUEST)
    assert event.ui_mode == "live" and event.status is EventStatus.PLANNING
    assert event.organizer_email == "dev@example.com" and event.plan_draft["party_size"] == 10


async def test_the_slack_plan_is_confirmed_only_by_the_requester_then_the_web_takes_it_over():
    from src.models.slack import Action
    from src.services.slack_messages import plan_request

    w = slack_world()
    event = w.svc.start_from_slack(U_DEV, FIRST_REQUEST)
    eid = event.event_id
    _, blocks = plan_request(event, slack_user_id=U_DEV)
    button = next(el for b in blocks if b["type"] == "actions" for el in b["elements"])
    assert button["action_id"] == Action.PLAN.value and f'"e":"{eid}"' in button["value"]
    # 引き継ぐ前は、だれにも見えない。別のアカウントには、引き継がれない
    assert w.svc.list_events(OTHER, "live") == []
    with pytest.raises(DashboardError):
        w.svc.get_event(OTHER, eid)
    # 依頼した本人以外は、確定できない
    assert await w.svc.confirm_slack_plan(eid, "U_OTHER") is None
    done = await w.svc.confirm_slack_plan(eid, U_DEV)
    assert done is not None and done.status is EventStatus.RSVP
    assert done.title == "第一開発チーム 歓送迎会" and done.bank_approval == "bank"
    assert await w.svc.confirm_slack_plan(eid, U_DEV) is None  # 二重に確定しない
    # 同じメールでログインすると、自分のイベントとして見える
    assert [e["event_id"] for e in w.svc.list_events(DEV, "live")] == [eid]
    assert w.svc.get_event(DEV, eid)["status"] == "rsvp"


def test_without_a_registration_the_slack_profile_email_identifies_the_organizer():
    w = World(live_emails={"dev@example.com"})  # live_slack_users は空
    assert w.svc.start_from_slack("U_X", FIRST_REQUEST) is None
    assert w.svc.start_from_slack("U_X", FIRST_REQUEST, "someone@example.com") is None
    event = w.svc.start_from_slack("U_X", FIRST_REQUEST, "Dev@Example.com")
    assert event is not None and event.organizer_email == "dev@example.com"


# ----------------------------------------- 幹事の操作を Slack で行う（実演用。SPEC 7.8）
async def _slack_event(w, **update):
    event = w.svc.start_from_slack(U_DEV, FIRST_REQUEST)
    await w.svc.confirm_slack_plan(event.event_id, U_DEV)
    event = w.store.get_event(event.event_id)
    candidates = [
        {"place_id": "p1", "name": "居酒屋 A", "nearest_station": "渋谷", "max_travel_minutes": 20,
         "selection_reason": "全員が乗り換えなしで行ける"},
        {"place_id": "p2", "name": "居酒屋 B"},
    ]  # fmt: skip
    event = event.model_copy(
        update={"status": EventStatus.VENUE, "venue_candidates": candidates} | update
    )
    w.store.save_event(event)
    return event


def _org_buttons(w, *, since=0):
    out = []
    for _, _, blocks in w.slack.dms[since:]:
        for b in blocks:
            if b.get("type") == "actions":
                out += [(el["action_id"], el["value"]) for el in b["elements"]]
    return out


async def test_the_organizer_picks_the_venue_and_sends_the_reservation_image_in_slack():
    import json

    w = slack_world()
    event = await _slack_event(w)
    n = len(w.slack.dms)
    await w.org.venues(event)
    buttons = _org_buttons(w, since=n)
    assert [a for a, _ in buttons] == ["org:venue1", "org:venue2"]
    value = json.loads(buttons[1][1])
    assert value["s"] == U_DEV and value["o"] == "venue" and value["p"] == "p2"
    # 依頼した本人以外・別の操作は受け付けない
    assert await w.svc.slack_op(event.event_id, "U_OTHER", value) is None
    text = await w.svc.slack_op(event.event_id, U_DEV, value)
    assert "居酒屋 B" in text
    assert w.store.get_event(event.event_id).venue["place_id"] == "p2"
    assert "画像で送って" in w.slack.dms[-1][1] or "画像で送って" in str(w.slack.dms[-1][2])

    # 予約の画面を画像で送ると、読み取って、確定のカードを返す。確定すると予約が確定する
    async def read(up, data=None):
        return up.model_copy(update={"extraction_status": "done", "extraction": {
            "venue_name": "居酒屋 B", "datetime": "2026-10-30T19:00:00+09:00",
            "party_size": 10, "course_price_yen": 4500, "warnings": []}})  # fmt: skip

    w.svc._read_reservation = read
    n = len(w.slack.dms)
    event = w.store.get_event(event.event_id)
    assert await w.svc.ingest_slack_image(event, b"png", "image/png", "F1") == ""
    ((action, raw),) = _org_buttons(w, since=n)
    assert action == "org"
    done = await w.svc.slack_op(event.event_id, U_DEV, json.loads(raw))
    assert "確定" in done
    assert w.store.get_event(event.event_id).venue["course_price_yen"] == 4500
    assert w.store.get_event(event.event_id).status is EventStatus.BOOKED


async def test_slack_images_are_only_taken_at_the_right_stage():
    w = slack_world()
    event = await _slack_event(w, status=EventStatus.RSVP)
    assert "受け付ける段階ではありません" in await w.svc.ingest_slack_image(
        event, b"png", "image/png", "F1"
    )
    assert "受け取れませんでした" in await w.svc.ingest_slack_image(
        event, b"gif", "image/gif", "F2"
    )


def test_an_image_message_from_slack_is_taken_as_a_direct_message_with_files():
    from src.services.slack_intake import extract_direct_message

    payload = {
        "type": "event_callback", "event_id": "Ev1", "team_id": "T1",
        "event": {
            "type": "message", "subtype": "file_share", "channel_type": "im", "user": U_DEV,
            "channel": "D1", "text": "", "ts": "1.0",
            "files": [
                {"id": "F1", "mimetype": "image/png", "url_private_download": "https://files.slack.com/x"},
                {"id": "F2", "mimetype": "application/pdf", "url_private_download": "https://files.slack.com/y"},
            ],
        },
    }  # fmt: skip
    message = extract_direct_message(payload)
    assert message is not None and [f.file_id for f in message.files] == ["F1"]  # 画像だけ
    payload["event"]["subtype"] = "message_changed"
    assert extract_direct_message(payload) is None


# ---------------------------------------------------------------- 参照（記憶・規程。SPEC 7.9）
async def test_the_memory_and_the_policy_can_be_read_from_the_web():
    from src.clients.memory_bank import InMemoryMemoryStore
    from src.services.memory_facts import TEAM_SCOPE

    w = World()
    memory = InMemoryMemoryStore()
    await memory.create(
        TEAM_SCOPE, "第一開発チームの歓送迎会（2026/05）で『居酒屋 A』を10名で利用。"
    )
    await memory.create(
        f"{TEAM_SCOPE}:guest:{JUDGE.uid}", "第一開発チームの歓送迎会（2026/10）で『B』を利用。"
    )
    await memory.create(f"{TEAM_SCOPE}:guest:{OTHER.uid}", "他のゲストの記憶")
    w.svc._memory = memory
    out = await w.svc.reference(JUDGE)
    texts = [f["text"] for g in out["memory"]["groups"] for f in g["facts"]]
    assert any("居酒屋 A" in t for t in texts) and any("『B』" in t for t in texts)
    assert "他のゲストの記憶" not in texts  # ほかのゲストの記憶は見えない
    policy = out["policy"]
    assert policy["articles"] and policy["articles"][0]["number"] == "第1条"
    assert policy["values"]["member_classes"][0]["weight"] > 0
