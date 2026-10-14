"""Web ダッシュボードの操作（SPEC 4.3・7.5・7.6。TASKS B14）。すべてコード。LLM のツールではない。

- 幹事は、自分のイベント（`organizer_web_uid` が一致）だけ。
  ゲストは、自分が作った `sandbox` イベントだけ。
  他人のイベントは「存在しない」と同じ応答にする（存在を漏らさない）
- **委任・承認・取り消し・振込の操作は、原則ここに無い**（Slack だけ。SPEC 4.3）。例外は、
  体験用（sandbox）のイベントを作った本人が、登場人物として押すカード（SPEC 7.7）
- 確定は幹事の操作でだけ起きる。読み取り・手入力の値は、同じ検査（型・範囲・語彙）を通る
- 判断ログに残すもの: 確定した人の uid、`source`（読み取り／手入力）
"""

import datetime as dt
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from src.clients.memory_bank import MemoryStore
from src.db.events import EventStore
from src.db.payments import PaymentReader
from src.models.dashboard import (
    ALLOWED_CONTENT_TYPES,
    GUEST_MAX_EVENTS,
    GUEST_MAX_MESSAGES_PER_EVENT,
    LIVE_MAX_EVENTS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOADS,
    PENDING_REPLY_TTL_SECONDS,
    SANDBOX_DAYS,
    Actor,
    Message,
    MessageStatus,
    Notification,
    NotificationKind,
    Role,
    Upload,
    UploadKind,
)
from src.models.event import Event, EventStatus, Receipt
from src.models.split import BudgetEscalation
from src.seed.sample_company import DEMO_ANSWERS
from src.services import slack_messages as msg
from src.services.agent_context import with_context
from src.services.lifecycle import Lifecycle
from src.services.policy_extract import PolicyReader
from src.services.receipt_ocr import ReceiptModel, ocr_receipt
from src.services.reservation_read import ReservationModel, ingest_reservation
from src.services.scenario_hint import hint_for, plan_example, start_hint
from src.services.slack_organizer import OrganizerDM
from src.services.vocab import REQUEST_TAGS, only_vocab

logger = logging.getLogger(__name__)

Chat = Callable[[str, str], Awaitable[str]]  # (会話の鍵, 発言) → 返答
EnqueueSelf = Callable[[str, dict, str], Awaitable[None]]  # (パス, 本文, タスクの ID)
FAILED_REPLY = "いま返答を作れませんでした。少し待って、もう一度送ってください。"


_PLAN_WORDS = (
    "歓迎会", "送別会", "歓送迎会", "飲み会", "宴会", "懇親会", "打ち上げ", "忘年会", "新年会",
    "ランチ会", "お疲れ様会", "お祝い", "開催", "幹事", "企画", "予約", "店を", "お店",
)  # fmt: skip
_PLAN_FACTS = re.compile(r"\d+\s*(?:月|/)\s*\d+|\d+\s*(?:時|:)|\d+\s*(?:人|名)")


def looks_like_plan_request(text: str) -> bool:
    """幹事の発言が、飲み会の企画の依頼か（あいさつ・雑談ではないか）。コードで決める。"""
    if any(w in text for w in _PLAN_WORDS):
        return True
    return len(_PLAN_FACTS.findall(text)) >= 2


_KINDS = "歓送迎会|歓迎会|送別会|飲み会|忘年会|新年会|懇親会|打ち上げ|ランチ会"
_DATE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日|(\d{1,2})\s*/\s*(\d{1,2})")
_TIME = re.compile(r"(\d{1,2})\s*時(?:\s*(\d{1,2})\s*分)?|(\d{1,2}):(\d{2})")
_HEADS = re.compile(r"(\d{1,3})\s*(?:人|名)")
_KIND_AT = re.compile(rf"([^\s、。,]*?)の?({_KINDS})")


def plan_from_text(text: str, now: dt.datetime) -> dict[str, Any]:
    """依頼文から、計画の案を読み取る（決まった書き方だけ。コードで決める）。

    読み取れない項目は、デモの既定の値（`plan_example`）にする。幹事が確かめて確定する。
    """
    base = plan_example()
    today = (now.astimezone(msg.JST) if now.tzinfo else now).date()
    when: dt.datetime | None = None
    m = _DATE.search(text)
    if m:
        month, day = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4))
        hour, minute = 19, 0
        t = _TIME.search(text[m.end():]) or _TIME.search(text)
        if t:
            hour, minute = int(t.group(1) or t.group(3)), int(t.group(2) or t.group(4) or 0)
        try:
            day_ = dt.date(today.year, month, day)
            if day_ < today:
                day_ = dt.date(today.year + 1, month, day)
            when = dt.datetime.combine(day_, dt.time(hour, minute))
        except ValueError:
            when = None
    party = None
    h = _HEADS.search(text)
    if h and 2 <= int(h.group(1)) <= 50:
        party = int(h.group(1))
    title = base["title"] if when is None and party is None else "飲み会"
    for clause in re.split(r"[、。,\n]", _HEADS.sub("", text)):
        k = _KIND_AT.search(clause)
        if k:
            lead = re.sub(r"^(?:に|で|を|は|が)+", "", k.group(1)).strip()
            title = f"{lead} {k.group(2)}".strip()
            break
    deadline = base["rsvp_deadline"]
    if when is not None:
        due = when.date() - dt.timedelta(days=7)
        deadline = max(due, today).isoformat()
    return {
        "title": title[:60],
        "datetime": (when or dt.datetime.fromisoformat(base["datetime"])).strftime(
            "%Y-%m-%dT%H:%M"
        ),
        "party_size": party or base["party_size"],
        "budget_per_person_yen": base["budget_per_person_yen"],
        "rsvp_deadline": deadline,
        "guests_of_honor": [],
    }


class DashboardError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code, self.status = code, status


class UploadSigner(Protocol):
    def read_bytes(self, path: str) -> bytes | None: ...

    def signed_put_url(self, path: str, content_type: str, ttl_seconds: int) -> str: ...

    def object_size(self, path: str) -> int | None:
        """アップロード済みのオブジェクトの実際のサイズ。無ければ None。"""


class PersonaActions(Protocol):
    """登場人物として、Web のカードのボタンを押す（`SlackActions.press_card`。SPEC 7.7）。"""

    async def press_card(self, event: Event, card_id: str, index: int, web_uid: str) -> None: ...

    async def approve_bank(self, event: Event, person: Any) -> bool:
        """体験用の承認待ちの振込を、承認済みにする（Slack のボタンと同じ処理）。"""

    async def send_event_notice(self, event_id: str) -> dict[str, Any]:
        """予約が確定したあと、参加者に開催の案内を届ける。"""

    async def send_approval_request(self, event_id: str) -> dict[str, Any]:
        """幹事が内訳を確かめたあと、承認者に按分の承認を依頼する。"""


class PreferenceForm(Protocol):
    """出欠のカードの入力欄（開催希望駅・苦手な食べ物）の取り込み（`PreferenceIntake`）。"""

    async def record_form(
        self, event_id: str, user_id: str, *, station: str, dislikes: str
    ) -> Any: ...


class RetroOps(Protocol):
    """振り返りの締切と、幹事の確認（`Retrospectives`。SPEC 7.4・9.8）。"""

    def close_now(self, event_id: str) -> str: ...

    async def confirm(
        self, event_id: str, web_uid: str, *, reuse_intent: str, include: list[str], save: bool
    ) -> Any: ...


class VenueFinder(Protocol):
    async def run(self, event_id: str) -> Any: ...


class RsvpDispatcher(Protocol):
    async def start_rsvp(self, event_id: str) -> None: ...

    async def start_split_approval(self, event_id: str) -> None: ...

    async def start_checkouts(self, event_id: str, split_hash: str) -> None: ...


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class DashboardService:
    def __init__(
        self,
        *,
        store: EventStore,
        chat: Chat,
        signer: UploadSigner,
        dispatcher: RsvpDispatcher,
        upload_ttl_seconds: int = 300,
        ocr: ReceiptModel | None = None,
        lifecycle: Lifecycle | None = None,
        payments: PaymentReader | None = None,
        personas: PersonaActions | None = None,
        policy: PolicyReader | None = None,
        reservation_reader: ReservationModel | None = None,
        retro: RetroOps | None = None,
        venues: VenueFinder | None = None,
        enqueue_chat: EnqueueSelf | None = None,
        prefs: PreferenceForm | None = None,
        organizer: "OrganizerDM | None" = None,
        memory: "MemoryStore | None" = None,
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    ) -> None:
        self._org_dm = organizer  # 実演用の幹事への Slack の DM（SPEC 7.8）
        self._memory = memory  # 記憶（Memory Bank）。参照用（SPEC 7.9）
        self._personas, self._policy, self._retro = personas, policy, retro
        self._prefs = prefs
        self._reservation_reader = reservation_reader
        self._venues = venues
        self._enqueue_chat = enqueue_chat  # 無ければ（ローカル・テスト）、返答をその場で待つ
        self._store, self._chat, self._signer = store, chat, signer
        self._dispatcher, self._ttl, self._now = dispatcher, upload_ttl_seconds, now
        self._ocr = ocr
        self._life = lifecycle or Lifecycle(store=store, now=now)
        self._payments = payments

    # ------------------------------------------------------------ 権限
    def _own(self, actor: Actor, event_id: str) -> Event:
        """自分のイベントだけ。それ以外は「存在しない」（404）。"""
        event = self._store.get_event(event_id)
        if event is not None:
            event = self._adopt(actor, event)  # Slack から始めた、自分のイベント
            if actor.role is Role.ORGANIZER and event.organizer_web_uid == actor.uid:
                if not event.sandbox:
                    return event
            elif actor.role is Role.GUEST and event.sandbox and event.guest_owner_uid == actor.uid:
                return event
        raise DashboardError("event_not_found", 404)

    # ------------------------------------------------------------ 一覧・詳細
    def me(self, actor: Actor) -> dict[str, Any]:
        """利用者の役割と、実演用の画面を使えるか。はじめの進行ヒントも返す（イベントを作る前）。"""
        return {
            "role": actor.role.value,
            "live_allowed": self._live_allowed(actor),
            "start_hints": {m: start_hint(live=m == "live") for m in ("experience", "live")},
        }

    def _live_allowed(self, actor: Actor) -> bool:
        return actor.email.lower() in self._store.live_bank_emails()

    def list_events(self, actor: Actor, mode: str | None = None) -> list[dict[str, Any]]:
        self._adopt_all(actor)  # Slack から始めた実演用のイベントを、自分のものにする
        events = (
            self._store.list_events_for_organizer(actor.uid)
            if actor.role is Role.ORGANIZER
            else self._store.list_events_for_guest(actor.uid)
        )
        return [
            {"event_id": e.event_id, "title": e.title, "datetime": e.datetime.isoformat(),
             "status": e.status.value, "sandbox": e.sandbox, "ui_mode": e.ui_mode}
            for e in events
            if mode is None or e.ui_mode == mode
        ]  # fmt: skip

    def get_event(self, actor: Actor, event_id: str) -> dict[str, Any]:
        e = self._own(actor, event_id)
        people = self._store.list_participants(event_id)
        retro = self._retro_view(event_id)
        retro_ready = (retro or {}).get("status") == "awaiting_organizer"
        split = self._split_view(event_id)
        approved = bool(split and split["approval"]["status"] == "approved")
        return {
            "event_id": e.event_id, "title": e.title, "datetime": e.datetime.isoformat(),
            "status": e.status.value, "sandbox": e.sandbox, "plan": e.plan, "venue": e.venue,
            "ui_mode": e.ui_mode, "venue_candidates": e.venue_candidates,
            "venue_search": {"status": e.venue_search, "error": e.venue_search_error},
            "total_amount_yen": e.total_amount_yen,
            # 実名は返さない（表示名は仮名のまま。再識別は別の経路）。承諾の状況だけ
            "participants": [
                {"user_id": p.user_id, "display_name": p.display_name, "role": p.role.value,
                 "rsvp_status": p.rsvp_status.value, "mandate_signed": p.mandate_id is not None}
                for p in people
            ],
            "uploads": [u.model_dump(mode="json") for u in self._store.list_uploads(event_id)],
            "messages": [m.model_dump(mode="json") for m in self._messages(event_id)],
            "waiting_for": waiting_for(
                e, people, retro_ready=retro_ready, approved=approved, split_ready=split is not None
            ),
            "split": split,
            "budget_overrun": _budget_view(e),
            "payments": self._payments.list_payments(event_id) if self._payments else [],
            "bank_approval": e.bank_approval,
            "personas": self._personas_view(e, people),
            "retro": retro,
            "decision_log": [
                d.model_dump(mode="json") for d in self._store.list_decisions(event_id)
            ],
            "hint": _with_plan_draft(
                hint_for(
                    e, people, has_receipt=self._store.get_receipt(event_id) is not None,
                    retro_ready=retro_ready, split_ready=split is not None, approved=approved,
                ),
                e,
            ),
        }  # fmt: skip

    # ------------------------------------------------------------ 登場人物のチャット（SPEC 7.7）
    def _personas_view(self, event: Event, people: list) -> list[dict[str, Any]]:
        """登場人物ごとの、KUROKO から届いたカード（Slack の DM と同じ中身）。体験用だけ。"""
        if not event.sandbox:
            return []
        cards = self._store.list_cards(event.event_id)
        payments = self._payments.list_payments(event.event_id) if self._payments else []
        title = event.title or "飲み会"
        out = []
        for p in people:
            if not p.demo_persona:
                continue
            mine = [_card_view(c) for c in cards if c.user_id == p.user_id]
            # 体験用の「銀行で承認してください」は、届いたカード（Slack と同じもの）を出す。
            # 届いていないときだけ、支払いの状態から作る
            has_bank_card = any(c["kind"] == "bank" for c in mine)
            mine += [
                _payment_card(
                    pay, title, web=event.bank_approval == "web", requested=has_bank_card
                )
                for pay in payments
                if pay.get("payer_user_id") == p.user_id
            ]
            out.append({
                "user_id": p.user_id, "display_name": p.display_name, "job_title": p.job_title,
                "cards": [c for c in mine if c],
            })  # fmt: skip
        return out

    async def press_persona_card(
        self, actor: Actor, event_id: str, card_id: str, index: int,
        inputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:  # fmt: skip
        """登場人物として、カードのボタンを押す。体験用のイベントを作った本人だけ。

        `inputs` は、出欠のカードの入力欄（開催希望駅・苦手な食べ物。SPEC 7.7）。「参加」を押した
        ときだけ取り込む。駅は駅すぱあとで確かめた駅コード、食べ物は固定の語彙にして持ち、
        原文は保存しない。取り込めなくても、出欠の回答は止めない。
        """
        from src.services.slack_actions import CardError

        event = self._own(actor, event_id)
        # 実演用のイベントは、本人が Slack と銀行で操作する（Web からは押せない。SPEC 7.7）
        if not event.sandbox or event.ui_mode == "live" or self._personas is None:
            raise DashboardError("not_allowed", 403)
        await self._take_preferences(event_id, card_id, index, inputs or {})
        try:
            await self._personas.press_card(event, card_id, index, actor.uid)
        except CardError as e:
            raise DashboardError(str(e), 409) from None
        card = self._store.get_card(event_id, card_id)
        if card is None or card.resolved_text is None:
            raise DashboardError("action_rejected", 409)  # 本人でない・段階が違う、など
        return {"card_id": card_id, "resolved_text": card.resolved_text}

    async def _take_preferences(
        self, event_id: str, card_id: str, index: int, inputs: dict[str, str]
    ) -> None:
        card = self._store.get_card(event_id, card_id)
        station = str(inputs.get("station") or "").strip()[:40]
        dislikes = str(inputs.get("dislikes") or "").strip()[:200]
        if (
            self._prefs is None
            or card is None
            or card.kind != "consent"
            or card.resolved_text is not None
            or _button_action(card, index) != "consent"  # 「欠席する」では取り込まない
            or not (station or dislikes)
        ):
            return
        try:
            await self._prefs.record_form(
                event_id, card.user_id, station=station, dislikes=dislikes
            )
        except Exception:  # 原文はログに出さない
            logger.warning("could not record the preferences: event=%s", event_id)
            return
        self._life.log(
            event_id, "kuroko", "記録",
            "参加者1名の開催希望駅・苦手な食べ物を受け取りました（駅コードと固定の語彙に変換。"
            "原文は保存しません）",
        )  # fmt: skip

    async def approve_bank_transfer(
        self, actor: Actor, event_id: str, user_id: str
    ) -> dict[str, Any]:
        """体験用の「銀行で承認する」。登場人物の、承認待ちの代行の振込を承認済みにする。

        本物の銀行（sunabar）の振込には効かない（`bank-adapter` が、体験用の振込だけを受ける）。
        支払いを完了にするのは、これまでどおり、明細での確認（payment-api・kuroko-api）。
        """
        event = self._own(actor, event_id)
        person = next(
            (p for p in self._store.list_participants(event_id) if p.user_id == user_id), None
        )
        if (
            not event.sandbox
            or event.bank_approval != "web"
            or person is None
            or not person.demo_persona
            or self._personas is None
        ):
            raise DashboardError("not_allowed", 403)
        if not await self._personas.approve_bank(event, person):
            raise DashboardError("no_transfer_to_approve", 409)
        return {"user_id": user_id, "status": "approved"}

    # ---------------------------------------------- 按分の承認・振込の依頼（SPEC 7.5）
    async def request_approval(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """幹事が按分の内訳を確かめて、承認者に承認を依頼する（内訳を見せたあとに、依頼が届く）。

        金額は、すでに計算して保存した金額表のまま（ここでは変わらない・再計算しない）。
        """
        event = self._own(actor, event_id)
        if event.status not in (EventStatus.SPLIT, EventStatus.APPROVAL) or self._personas is None:
            raise DashboardError("invalid_state", 409)
        out = await self._personas.send_approval_request(event_id)
        if not out.get("ok"):
            raise DashboardError("invalid_state", 409)
        self._life.log(event_id, "human", "確認", "幹事が按分の内訳を確かめ、承認を依頼しました")
        return {"event_id": event_id, "status": "approval"}

    async def approve_transfers(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """承認者が按分を承認したあと、幹事が「参加者に振込の依頼を送る」ことを承認する。

        ここで初めて請求（Policy Gate 6.2）に進み、参加者に、銀行で承認する依頼が届く。
        押すのは幹事（イベントの持ち主）だけ。承認者の承認がなければ受け付けない。
        """
        event = self._own(actor, event_id)
        approval = self._store.get_approval(event_id)
        split = self._store.get_split(event_id)
        if (
            event.status is not EventStatus.APPROVAL
            or approval is None or split is None
            or approval.status.value != "approved"
            or approval.split_hash != split.hash
        ):  # fmt: skip
            raise DashboardError("invalid_state", 409)
        # 同じ金額表の請求は1回だけ（タスクの ID が同じ。押し直しても二重にならない）
        await self._dispatcher.start_checkouts(event_id, split.hash)
        self._life.log(
            event_id, "human", "署名", "幹事が、参加者への振込の依頼を送ることを承認しました（Web）"
        )
        self._life.say(
            event_id,
            "振込の依頼を作成しています。参加者に、銀行での承認のお願いをお送りします。"
            "各自が銀行で承認すると、振込が実行されます。",
        )
        return {"event_id": event_id, "status": "payment_requested"}

    # ------------------------------------------------------------ 振り返り（SPEC 7.4・9.8）
    def _retro_view(self, event_id: str) -> dict[str, Any] | None:
        """振り返りの集計と、覚えさせる事実の下書き。**個人ごとの回答は出さない**（集計だけ）。"""
        r = self._store.get_retro(event_id)
        if r is None:
            return None
        return {
            "status": r.status.value,
            "invited_count": r.invited_count,
            "response_count": r.response_count,
            "avg_rating": r.avg_rating,
            "liked_counts": r.liked_counts,
            "concern_counts": r.concern_counts,
            "venue_name": r.venue_name,
            "party_size": r.party_size,
            "per_person_yen": r.per_person_yen,
            "within_budget": r.within_budget,
            "reuse_intent": r.reuse_intent,
            "memory_facts": [
                {"kind": f.kind, "text": f.text, "include": f.include, "saved": f.ref is not None}
                for f in r.memory_facts
            ],
            "saved_at": r.saved_at.isoformat() if r.saved_at else None,
        }

    def close_retro(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """幹事が、回答を待たずに振り返りを締め切る（その時点の回答で集計する）。"""
        self._own(actor, event_id)
        if self._retro is None or self._retro.close_now(event_id) != "closed":
            raise DashboardError("invalid_state", 409)
        return {"event_id": event_id, "status": "awaiting_organizer"}

    async def confirm_retro(
        self, actor: Actor, event_id: str, reuse_intent: str, include: list[str], decision: str
    ) -> dict[str, Any]:
        """振り返りのまとめの確認（SPEC 4.3）。保存するのは、定型の事実だけ（Policy Gate 6.4）。

        画面から受けるのは、選択だけ（事実の文面は受けない。コードが作り直す）。
        """
        from src.services.retrospective import RetroError

        self._own(actor, event_id)
        if self._retro is None or decision not in ("save", "skip"):
            raise DashboardError("invalid_state", 409)
        kinds = [k for k in include if k in ("venue_record", "venue_evaluation")]
        try:
            retro = await self._retro.confirm(
                event_id, actor.uid, reuse_intent=reuse_intent, include=kinds,
                save=decision == "save",
            )  # fmt: skip
        except RetroError as e:
            unavailable = str(e) in ("memory_unavailable", "memory_not_configured")
            raise DashboardError(str(e), 503 if unavailable else 409) from None
        return {"event_id": event_id, "status": retro.status.value}

    def _split_view(self, event_id: str) -> dict[str, Any] | None:
        """按分の内訳。保存された SplitResult の値をそのまま返す（Web で再計算しない。7.3.1）。"""
        split = self._store.get_split(event_id)
        if split is None:
            return None
        approval = self._store.get_approval(event_id)
        event = self._store.get_event(event_id)
        snap = event.policy_snapshot if event else None
        return {
            **split.model_dump(mode="json"),
            # 根拠の規程（どこから取った値か・条。SPEC 9.7）
            "policy": {
                "policy_id": snap.policy_id, "version": snap.version, "source": snap.source,
                "citations": snap.citations,
            } if snap else None,
            "approval": {
                "approver_user_id": split.approver_user_id,
                "status": approval.status.value if approval else "pending",
                "approved_at": approval.approved_at.isoformat()
                if approval and approval.approved_at
                else None,
                "split_hash": split.hash,
            },
        }

    # ------------------------------------------------------------ チャット
    async def send_message(
        self, actor: Actor, event_id: str | None, text: str, mode: str = "experience"
    ) -> dict[str, Any]:
        text = text.strip()
        if not text or len(text) > 2000:
            raise DashboardError("invalid_text")
        now = self._now()
        if event_id is None:
            # 最初の発言で planning のイベントを作る
            event = self._create_event(actor, now, mode)
        else:
            event = self._own(actor, event_id)
            if any(m.status is MessageStatus.PENDING for m in self._messages(event.event_id)):
                raise DashboardError("reply_pending", 409)  # 返答が出るまで、次は受けない
        if actor.role is Role.GUEST:
            sent = sum(
                1 for m in self._store.list_messages(event.event_id) if m.role == "organizer"
            )
            if sent >= GUEST_MAX_MESSAGES_PER_EVENT:
                raise DashboardError("guest_message_limit", 429)
        self._store.save_message(
            Message(message_id=_id("m"), event_id=event.event_id, role="organizer", text=text,
                    created_at=now)
        )  # fmt: skip
        if self._enqueue_chat is None:
            answer = await self._answer(event, actor.uid, text, None)
            return {"event_id": event.event_id, "reply": answer.model_dump(mode="json")}
        # 返答は待たない（Hosting の応答は60秒で切られる。SPEC 7.5）。「考え中」を保存して返し、
        # 返答の生成は Cloud Tasks で行う
        # 発言のすぐあとに並ぶよう、時刻を少しだけ後ろにする（同じ時刻だと、順が ID で決まる）
        pending = Message(
            message_id=_id("m"), event_id=event.event_id, role="kuroko", text="",
            status=MessageStatus.PENDING, created_at=now + dt.timedelta(milliseconds=1),
        )  # fmt: skip
        self._store.save_message(pending)
        try:
            await self._enqueue_chat(
                "/tasks/internal/chat-replies",
                {"event_id": event.event_id, "message_id": pending.message_id, "uid": actor.uid,
                 "text": text},
                f"chat-{pending.message_id}",
            )  # fmt: skip
        except Exception:  # 投入できない。待たせずに、失敗として返す
            logger.exception("could not enqueue the chat reply: event=%s", event.event_id)
            pending = pending.model_copy(
                update={"status": MessageStatus.FAILED, "text": FAILED_REPLY}
            )
            self._store.save_message(pending)
        return {"event_id": event.event_id, "reply": pending.model_dump(mode="json")}

    async def _answer(
        self, event: Event, uid: str, text: str, pending: Message | None
    ) -> Message:
        """エージェントの返答を作り、KUROKO のメッセージとして保存する（失敗は固定の文面）。"""
        status, reply = MessageStatus.DONE, ""
        try:
            # いま開いているイベントを、コードが伝える（ID を聞き返さない。SPEC 7.5）
            asked = with_context(text, event, "幹事", web=True)
            reply = await self._chat(f"web:{event.event_id}:{uid}", asked)
        except Exception:  # Gateway のブロックも含む。理由・本文はログに出さない
            status, reply = MessageStatus.FAILED, FAILED_REPLY
        # 計画のカードは、企画の依頼に答えた発言の位置に出す（あいさつ・雑談には出さない）
        plan_card = (
            "plan"
            if status is MessageStatus.DONE
            and event.status is EventStatus.PLANNING
            and looks_like_plan_request(text)
            else None
        )
        answer = Message(
            message_id=pending.message_id if pending else _id("m"), event_id=event.event_id,
            role="kuroko", text=reply[:2000], status=status, card=plan_card,
            created_at=pending.created_at if pending else now_after(self._now()),
        )  # fmt: skip
        self._store.save_message(answer)
        return answer

    async def run_chat_reply(self, event_id: str, message_id: str, uid: str, text: str) -> str:
        """Cloud Tasks から呼ばれ、返答待ちのメッセージを返答に更新する。例外は出さない。"""
        pending = self._store.get_message(event_id, message_id)
        if pending is None:
            return "gone"  # クリアされた（イベントごと消えた）
        if pending.status is not MessageStatus.PENDING:
            return "skipped"  # 再配信・重複。すでに処理した
        event = self._store.get_event(event_id)
        if event is None:
            return "gone"  # 孤児のメッセージを残さない
        await self._answer(event, uid, text, pending)
        return "done"

    def _messages(self, event_id: str) -> list[Message]:
        """メッセージの一覧。長く返答待ちのままのものは、失敗として返す（入力を塞がない）。"""
        now = self._now()
        out = []
        for m in self._store.list_messages(event_id):
            if m.status is MessageStatus.PENDING and (
                (now - m.created_at).total_seconds() > PENDING_REPLY_TTL_SECONDS
            ):
                m = m.model_copy(update={"status": MessageStatus.FAILED, "text": FAILED_REPLY})
            out.append(m)
        return out

    def _create_event(self, actor: Actor, now: dt.datetime, mode: str = "experience") -> Event:
        guest = actor.role is Role.GUEST
        live_ok = self._live_allowed(actor)
        if mode not in ("experience", "live"):
            raise DashboardError("invalid_mode")
        if mode == "live" and not live_ok:
            # 実演用の画面（本物の銀行に振込を依頼する）は、登録したアカウントだけ
            raise DashboardError("live_not_allowed", 403)
        limit = LIVE_MAX_EVENTS if live_ok else GUEST_MAX_EVENTS
        if guest and len(self._store.list_events_for_guest(actor.uid)) >= limit:
            raise DashboardError("guest_event_limit", 429)
        event = Event(
            event_id=_id("ev"), datetime=now, organizer_user_id=actor.uid, ui_mode=mode,
            organizer_web_uid=actor.uid, status=EventStatus.PLANNING, sandbox=guest,
            organizer_email=actor.email.lower() if mode == "live" else "",
            guest_owner_uid=actor.uid if guest else None,
            expires_at=now + dt.timedelta(days=SANDBOX_DAYS) if guest else None,
        )  # fmt: skip
        self._store.save_event(event)
        return event

    # ------------------------------------------------------------ 計画の確認
    async def confirm_event_plan(
        self, actor: Actor, event_id: str, plan: dict[str, Any]
    ) -> dict[str, Any]:
        """幹事が確認した計画を確定し、出欠依頼（Slack）へ進める（planning のときだけ）。"""
        event = self._own(actor, event_id)
        return await self._confirm_plan(event, actor.email, plan)

    async def _confirm_plan(
        self, event: Event, owner_email: str, plan: dict[str, Any]
    ) -> dict[str, Any]:
        """計画を確定し、出欠依頼へ進める（Web の確定と、Slack の確定で共通）。"""
        event_id = event.event_id
        if event.status is not EventStatus.PLANNING:
            raise DashboardError("invalid_state", 409)
        clean = validate_plan(plan)
        event = event.model_copy(update={
            "title": clean["title"], "datetime": clean["datetime"], "plan": clean["plan"],
            "plan_required_tags": clean["required_tags"], "status": EventStatus.RSVP,
        })  # fmt: skip
        # 規程の写し（文書から読み取り、コードが検証した値。SPEC 9.7）と、参加者を用意する
        reading = await self._policy.read() if self._policy else None
        event = self._life.prepare_event(
            event, owner_email=owner_email, snapshot=reading.snapshot if reading else None,
            honorees=clean["honorees"],
        )  # fmt: skip
        self._store.save_event(event)
        await self._take_organizer_station(event, clean["station"])
        self._life.log(event_id, "human", "確認", "幹事が計画を確定しました")
        if reading is not None:
            self._life.log(
                event_id, "kuroko", "規程",
                "規程の文書から値を読み取り、検証しました" if reading.from_document
                else "規程の文書から読み取れなかったため、既定の値を使いました",
            )  # fmt: skip
        self._life.log(event_id, "kuroko", "送信", "参加者に出欠の依頼を送ります（Slack）")
        self._life.say(
            event_id,
            f"「{clean['title']}」の計画を確定しました。参加者に、出欠・支払いの委任・"
            "開催希望駅・苦手な食べ物の確認をお送りしました。回答がそろったら、みなさんの開催希望駅から"
            "帰りやすいお店を探します（場所は、こちらで調べます）。",
        )
        await self._dispatcher.start_rsvp(event_id)
        return {"event_id": event_id, "status": event.status.value}

    async def _take_organizer_station(self, event: Event, station: str) -> None:
        """幹事の開催希望駅を取り込む（駅すぱあとで確かめる。決まらなければ、名簿の既定の駅のまま）。"""
        if not station or self._prefs is None:
            return
        try:
            await self._prefs.record_form(
                event.event_id, event.organizer_user_id, station=station, dislikes=""
            )
        except Exception:  # 原文はログに出さない
            logger.warning("could not record the organizer station: event=%s", event.event_id)

    # ---------------------------------------- Slack から始める（実演用。SPEC 7.8）
    def slack_organizer_email(
        self, slack_user_id: str, slack_email: str | None = None
    ) -> str | None:
        """実演用の幹事なら、結びつけたアカウントのメール（そうでなければ None）。

        登録（`live_slack_users`）があればそれを使う。登録が無いときは、Slack が署名して返した
        プロフィールのメール（`slack_email`。呼び出し側が Slack から取る）が、実演用に登録した
        アカウントのメールと同じなら、同じ人として扱う（メールは Slack に確認済みのものだけ）。
        """
        live = self._store.live_bank_emails()
        email = self._store.live_slack_users().get(slack_user_id) or slack_email
        if email and email.lower() in live:
            return email.lower()
        return None

    def start_from_slack(
        self, slack_user_id: str, text: str, slack_email: str | None = None
    ) -> Event | None:
        """登録した幹事の Slack DM が企画の依頼なら、計画の案つきでイベントを作る。

        依頼でなければ None（ふつうの会話として答える）。Web の本人（UID）は、そのアカウントで
        Web にログインしたときに引き継ぐ（`_adopt`）。
        """
        email = self.slack_organizer_email(slack_user_id, slack_email)
        text = text.strip()
        if email is None or not text or len(text) > 2000 or not looks_like_plan_request(text):
            return None
        now = self._now()
        sandbox = self._store.dashboard_role(email) is None
        event = Event(
            event_id=_id("ev"), datetime=now, organizer_user_id=slack_user_id, ui_mode="live",
            status=EventStatus.PLANNING, sandbox=sandbox, organizer_email=email,
            organizer_slack_user_id=slack_user_id, plan_draft=plan_from_text(text, now),
            expires_at=now + dt.timedelta(days=SANDBOX_DAYS) if sandbox else None,
        )  # fmt: skip
        self._store.save_event(event)
        self._store.save_message(
            Message(message_id=_id("m"), event_id=event.event_id, role="organizer", text=text,
                    created_at=now)
        )  # fmt: skip
        self._life.say(
            event.event_id,
            "Slack で依頼を受け取りました。計画の案を作ったので、内容を確かめて進めてください"
            "（Slack のカードか、このカードのどちらからでも確定できます）。",
            card="plan",
        )
        return event

    async def confirm_slack_plan(
        self, event_id: str, slack_user_id: str, station: str = ""
    ) -> Event | None:
        """Slack のカードの「この内容で進める」。依頼した本人だけが確定できる。"""
        event = self._store.get_event(event_id)
        if (
            event is None
            or event.status is not EventStatus.PLANNING
            or not event.organizer_slack_user_id
            or event.organizer_slack_user_id != slack_user_id
        ):
            return None
        plan = {**event.plan_draft, **({"station": station} if station else {})}
        await self._confirm_plan(event, event.organizer_email, plan)
        return self._store.get_event(event_id)

    def _adopt(self, actor: Actor, event: Event) -> Event:
        """Slack から始めたイベントを、同じメールでログインした本人のものにする（1回だけ）。"""
        if (
            event.organizer_email != actor.email.lower()
            or (event.organizer_web_uid and not event.organizer_web_uid.startswith("slack:"))
            or not self._live_allowed(actor)
        ):
            return event
        update: dict[str, Any] = {"organizer_web_uid": actor.uid}
        if event.sandbox:
            update["guest_owner_uid"] = actor.uid
        event = event.model_copy(update=update)
        self._store.save_event(event)
        return event

    def _adopt_all(self, actor: Actor) -> None:
        if not self._live_allowed(actor):
            return
        for e in self._store.list_events_by_organizer_email(actor.email):
            self._adopt(actor, e)

    # ---------------------------------------- 実演用の幹事の操作を Slack で行う（SPEC 7.8）
    def _slack_actor(self, event: Event) -> Actor:
        """Slack の操作を、幹事本人（イベントの持ち主）の操作として扱うための利用者。

        Web の本人（UID）が決まるまでは、Slack ユーザーから作った仮の ID を持ち主にする。
        同じメールで Web にログインしたとき、本人の UID に引き継がれる（`_adopt`）。
        """
        uid = event.organizer_web_uid
        if not uid:
            uid = f"slack:{event.organizer_slack_user_id}"
            update: dict[str, Any] = {"organizer_web_uid": uid}
            if event.sandbox:
                update["guest_owner_uid"] = uid
            self._store.save_event(event.model_copy(update=update))
        return Actor(
            uid=uid, email=event.organizer_email,
            role=Role.GUEST if event.sandbox else Role.ORGANIZER,
        )  # fmt: skip

    def _slack_event(self, event_id: str, slack_user_id: str) -> Event | None:
        """この Slack ユーザーが幹事の、実演用のイベント（本人だけ）。"""
        event = self._store.get_event(event_id)
        if (
            event is None
            or event.ui_mode != "live"
            or not event.organizer_slack_user_id
            or event.organizer_slack_user_id != slack_user_id
        ):
            return None
        return event

    def latest_slack_event(self, email: str) -> Event | None:
        """この幹事（メール）の、いま進行中の実演用のイベント（いちばん新しいもの）。"""
        rows = [
            e for e in self._store.list_events_by_organizer_email(email)
            if e.ui_mode == "live" and e.status is not EventStatus.CLOSED
        ]  # fmt: skip
        return max(rows, key=lambda e: e.datetime, default=None)

    async def slack_op(
        self, event_id: str, slack_user_id: str, value: dict[str, Any]
    ) -> str | None:
        """Slack のカードの、幹事の操作（`Action.ORG`）。結果の文を返す（None: 受け付けない）。

        依頼した幹事の本人だけ（`organizer_slack_user_id`）。操作の中身は Web の操作と同じ
        （同じ検査を通る）。
        """
        event = self._slack_event(event_id, slack_user_id)
        if event is None:
            return None
        actor, op = self._slack_actor(event), str(value.get("o", ""))
        try:
            if op == "venue":
                place_id = str(value.get("p", ""))
                known = next(
                    (c for c in event.venue_candidates if c.get("place_id") == place_id), None
                )
                if known is None:
                    return "この候補は見つかりませんでした。"
                self.select_venue(actor, event_id, place_id, str(known["name"]))
                if self._org_dm is not None:
                    await self._org_dm.reservation_prompt(event, str(known["name"]))
                return f"「{known['name']}」を選びました。"
            if op == "held":
                self.mark_event_held(actor, event_id)
                if self._org_dm is not None:
                    await self._org_dm.receipt_prompt(self._store.get_event(event_id) or event)
                return "開催の終了を受け取りました。"
            if op == "extract":
                return await self._slack_confirm_extraction(actor, event_id, value)
            if op == "budget":
                await self.confirm_budget_overrun(actor, event_id)
                return "続行します。承認者に最終確認を依頼しました。"
            if op == "split":
                await self.request_approval(actor, event_id)
                return "承認者に、按分の承認を依頼しました。"
            if op == "transfers":
                await self.approve_transfers(actor, event_id)
                return "参加者に、振込の依頼を送ります。各自が銀行で承認すると、振込されます。"
            if op == "retro":
                decision = "save" if value.get("d") == "save" else "skip"
                await self.confirm_retro(
                    actor, event_id, str(value.get("ri", "unanswered")),
                    ["venue_record", "venue_evaluation"], decision,
                )  # fmt: skip
                return "記憶に残しました。" if decision == "save" else "記憶には残しませんでした。"
        except DashboardError as e:
            logger.info("slack op rejected: op=%s code=%s", op, e.code)
            return "この操作はできません（すでに済んでいるか、いまの段階ではありません）。"
        return None

    async def _slack_confirm_extraction(
        self, actor: Actor, event_id: str, value: dict[str, Any]
    ) -> str:
        kind = UploadKind.RECEIPT if value.get("kd") == "receipt" else UploadKind.RESERVATION
        up = self._store.get_upload(event_id, str(value.get("u", "")))
        if up is None or up.kind is not kind or up.extraction_status != "done":
            return "読み取った内容が見つかりませんでした。もう一度、画像を送ってください。"
        data = up.extraction or {}
        if kind is UploadKind.RECEIPT:
            values: dict[str, Any] = {"total_amount_yen": data.get("total_amount_yen")}
        else:
            values = {
                k: data.get(k) for k in ("venue_name", "datetime", "party_size", "course_price_yen")
            }
        try:
            await self.confirm_extraction(actor, event_id, kind, values, "extracted")
        except DashboardError:
            return "この内容は確定できませんでした。もう一度、画像を送ってください。"
        if kind is UploadKind.RECEIPT:
            return "領収書の金額を確定しました。按分を計算します。"
        return "予約の内容を確定しました。"

    async def ingest_slack_image(
        self, event: Event, data: bytes, content_type: str, file_id: str
    ) -> str:
        """Slack の DM で届いた画像を読み取る。画面の段階で、予約画面か領収書かを決める。

        結果は、幹事が確定するまで使われない（Web のアップロードと同じ）。読み取れたときは、
        確定のカードを DM で返す。結果は、幹事に伝える文を返す（空: カードで答えた）。
        """
        if content_type not in ALLOWED_CONTENT_TYPES or not 0 < len(data) <= MAX_UPLOAD_BYTES:
            return "この画像は受け取れませんでした（PNG・JPEG・WebP の10MBまで）。"
        actor = self._slack_actor(event)
        event = self._store.get_event(event.event_id) or event
        chosen = bool((event.venue or {}).get("place_id"))
        if event.status is EventStatus.VENUE and chosen:
            kind = UploadKind.RESERVATION
        elif event.status is EventStatus.RECEIPT:
            kind = UploadKind.RECEIPT
        else:
            return "いまは、画像を受け付ける段階ではありません。"
        mine = [u for u in self._store.list_uploads(event.event_id) if u.kind is kind]
        if sum(1 for u in mine if u.status != "rejected") >= MAX_UPLOADS[kind]:
            return "この画像は、これ以上受け取れません。"
        up = Upload(
            upload_id=_id("up"), event_id=event.event_id, kind=kind,
            object_path=f"slack/{file_id}", content_type=content_type,
            size_bytes_declared=len(data), source="upload", uploaded_by=actor.uid,
            created_at=self._now(), status="registered",
        )  # fmt: skip
        up = (
            await self._read_receipt(up, data)
            if kind is UploadKind.RECEIPT
            else await self._read_reservation(up, data)
        )
        self._store.save_upload(up)
        if up.extraction_status != "done":
            return "画像から読み取れませんでした。見やすい画像で、もう一度送ってください。"
        if self._org_dm is not None:
            await self._org_dm.extraction(
                event, "receipt" if kind is UploadKind.RECEIPT else "reservation",
                up.upload_id, up.extraction or {},
            )  # fmt: skip
        return ""

    # ------------------------------------------------------------ アップロード
    def issue_upload_url(
        self, actor: Actor, event_id: str, kind: UploadKind, content_type: str, size_bytes: int,
        source: Literal["upload", "paste"] = "upload",
    ) -> dict[str, Any]:  # fmt: skip
        self._own(actor, event_id)
        if kind is UploadKind.RECEIPT and source == "paste":
            raise DashboardError("paste_not_allowed")  # 領収書は貼り付けない
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise DashboardError("unsupported_type")
        if not 0 < size_bytes <= MAX_UPLOAD_BYTES:
            raise DashboardError("invalid_size")
        mine = [u for u in self._store.list_uploads(event_id) if u.kind is kind]
        if sum(1 for u in mine if u.status != "rejected") >= MAX_UPLOADS[kind]:
            raise DashboardError("upload_limit", 429)
        upload_id = _id("up")
        path = f"events/{event_id}/{kind.value}/{upload_id}"
        self._store.save_upload(Upload(
            upload_id=upload_id, event_id=event_id, kind=kind, object_path=path,
            content_type=content_type, size_bytes_declared=size_bytes, source=source,
            uploaded_by=actor.uid, created_at=self._now(),
        ))  # fmt: skip
        url = self._signer.signed_put_url(path, content_type, self._ttl)
        return {"upload_id": upload_id, "url": url, "expires_in": self._ttl}

    async def register_upload(self, actor: Actor, event_id: str, upload_id: str) -> dict[str, Any]:
        """アップロード後の登録。実際のサイズをサーバー側でも検査し、超過・無いものは却下する。"""
        self._own(actor, event_id)
        up = self._store.get_upload(event_id, upload_id)
        if up is None or up.uploaded_by != actor.uid or up.status != "issued":
            raise DashboardError("upload_not_found", 404)
        size = self._signer.object_size(up.object_path)
        if size is None or size > MAX_UPLOAD_BYTES:
            self._store.save_upload(up.model_copy(update={"status": "rejected"}))
            raise DashboardError("upload_rejected")
        up = up.model_copy(update={"status": "registered"})
        if up.kind is UploadKind.RECEIPT:
            up = await self._read_receipt(up)  # 登録後に ocr_receipt を起動する（SPEC 4.3）
        else:
            up = await self._read_reservation(up)  # 予約画面は ingest_reservation
        self._store.save_upload(up)
        return {"upload_id": upload_id, "status": "registered", "extraction": up.extraction_status}

    async def _read_receipt(self, up: Upload, data: bytes | None = None) -> Upload:
        """読み取れなければ failed（手入力に切り替えられる）。結果は確認するまで使われない。"""
        if data is None:
            data = self._signer.read_bytes(up.object_path) if self._ocr else None
        reading = await ocr_receipt(self._ocr, data) if self._ocr and data else None
        if reading is None or not reading.ok:
            return up.model_copy(update={"extraction_status": "failed"})
        return up.model_copy(update={
            "extraction_status": "done",
            "extraction": {
                "total_amount_yen": reading.total_amount_yen, "line_items": reading.line_items,
                "warnings": reading.warnings,
            },
        })  # fmt: skip

    async def _read_reservation(self, up: Upload, data: bytes | None = None) -> Upload:
        """読み取れなければ failed（手入力できる）。結果は、幹事が確定するまで使われない。"""
        model = self._reservation_reader
        if data is None:
            data = self._signer.read_bytes(up.object_path) if model else None
        reading = await ingest_reservation(model, data) if model and data else None
        if reading is None or not reading.ok:
            return up.model_copy(update={"extraction_status": "failed"})
        return up.model_copy(update={
            "extraction_status": "done",
            "extraction": {
                "venue_name": reading.venue_name, "datetime": reading.datetime,
                "party_size": reading.party_size, "course_price_yen": reading.course_price_yen,
                "warnings": reading.warnings,
            },
        })  # fmt: skip

    # ------------------------------------------------------------ 確定
    async def confirm_extraction(
        self, actor: Actor, event_id: str, kind: UploadKind, values: dict[str, Any],
        source: Literal["extracted", "manual"],
    ) -> dict[str, Any]:  # fmt: skip
        """読み取り結果・手入力を、幹事が確定する（Policy Gate 6.1「幹事により確定済み」）。"""
        event = self._own(actor, event_id)
        if kind is UploadKind.RECEIPT:
            if event.status is not EventStatus.RECEIPT:
                raise DashboardError("invalid_state", 409)
            amount = values.get("total_amount_yen")
            if not _is_int(amount) or not 0 < amount <= 10_000_000:
                raise DashboardError("invalid_amount")
            if source == "manual" and not self._receipt_extraction_failed(event_id):
                raise DashboardError("manual_not_allowed")  # 手入力は、読み取りに失敗したときだけ
            if source == "extracted" and not self._receipt_extraction_done(event_id):
                raise DashboardError("no_extraction")  # 読み取り結果が無いものは名乗れない
            self._store.save_receipt(Receipt(
                event_id=event_id, total_amount_yen=amount,
                source="manual" if source == "manual" else "upload",
                confirmed_by=actor.uid, confirmed_at=self._now(),
            ))  # fmt: skip
            self._store.save_event(
                event.model_copy(update={"total_amount_yen": amount, "status": EventStatus.SPLIT})
            )
            how = "手入力" if source == "manual" else "読み取り結果"
            self._life.log(event_id, "human", "確認", f"幹事が領収書の金額を確定しました（{how}）")
            self._life.log(event_id, "kuroko", "送信", "按分を計算し、承認者に承認を依頼します")
            self._life.say(
                event_id,
                f"領収書の金額（{amount:,}円）を確定しました。会社の規程（負担の係数・会社の補助・"
                "端数の扱い・承認者の決め方）を確認して、按分を計算します。",
            )
            await self._dispatcher.start_split_approval(event_id)
            return {"confirmed": "receipt", "total_amount_yen": amount, "source": source}
        if event.status is not EventStatus.VENUE:
            raise DashboardError("invalid_state", 409)
        if source == "extracted" and not self._extraction_done(event_id, UploadKind.RESERVATION):
            raise DashboardError("no_extraction")  # 読み取り結果が無いものは名乗れない
        venue = validate_reservation(values)
        limit = event.policy_snapshot.hard_limit_per_person_yen if event.policy_snapshot else None
        over = limit is not None and venue["course_price_yen"] > limit
        booked = EventStatus.VENUE if over else EventStatus.BOOKED
        # 選んだ店（候補から選んだ名前・place_id）は残す。振り返りの実績は、選んだ店の名前で残す
        chosen = {k: v for k, v in (event.venue or {}).items() if k in ("place_id", "name")}
        self._store.save_event(
            event.model_copy(
                update={"venue": {**chosen, **venue, "source": source}, "status": booked}
            )
        )
        how = "手入力" if source == "manual" else "読み取り結果"
        self._life.log(event_id, "human", "確認", f"幹事が予約の内容を確定しました（{how}）")
        if over:
            self._life.log(event_id, "kuroko", "規程", "コース単価が規程の上限を超えています")
            self._life.notify(
                event, NotificationKind.CONFIRM_NEEDED, "予算超過です。続行するか確認してください"
            )
            self._life.say(
                event_id,
                f"コース単価（{venue['course_price_yen']:,}円）が、規程の上限（{limit:,}円）を"
                "超えています。続行するか、下のカードで確認してください。",
            )
            if self._org_dm is not None and limit is not None:
                fresh = self._store.get_event(event_id)
                if fresh is not None:
                    await self._org_dm.budget(fresh, venue["course_price_yen"], limit)
        else:
            self._life.say(
                event_id,
                f"予約の内容を確定しました（{venue['venue_name']}・{venue['party_size']}名・"
                f"コース {venue['course_price_yen']:,}円）。",
            )
            await self._send_notice(event_id)
        return {"confirmed": "reservation", "source": source, "over_budget": over}

    async def _send_notice(self, event_id: str) -> None:
        """予約が確定したら、参加者に開催の案内を届ける。届けられなくても、確定は成立している。"""
        if self._personas is None:
            return
        try:
            await self._personas.send_event_notice(event_id)
        except Exception:
            logger.exception("could not send the event notice: event=%s", event_id)

    async def confirm_budget_overrun(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """予算超過の確認（幹事の側。SPEC 9.1）。承認者への最終確認は Slack で行う。"""
        event = self._own(actor, event_id)
        price = (event.venue or {}).get("course_price_yen")
        limit = event.policy_snapshot.hard_limit_per_person_yen if event.policy_snapshot else None
        if event.status is not EventStatus.VENUE or not _is_int(price) or limit is None:
            raise DashboardError("invalid_state", 409)
        if price <= limit:
            raise DashboardError("not_over_budget", 409)
        esc = event.budget_escalation
        if esc is not None and esc.organizer_confirmed_at is not None:
            raise DashboardError("already_confirmed", 409)
        people = [p for p in self._store.list_participants(event_id) if p.attendance_confirmed]
        self._store.save_event(event.model_copy(update={
            "budget_escalation": BudgetEscalation(organizer_confirmed_at=self._now()),
            "total_amount_yen": price * max(len(people), 1),  # 予約時点の見積り（領収書で置換）
        }))  # fmt: skip
        self._life.log(event_id, "human", "確認", "幹事が予算超過での続行を確認しました")
        self._life.log(event_id, "kuroko", "送信", "承認者に最終確認を依頼します（Slack）")
        await self._dispatcher.start_budget_request(event_id)
        return {"event_id": event_id, "status": "awaiting_approver"}

    def mark_event_held(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """幹事が「開催が終わった」と伝える。領収書のアップロードに進む。"""
        event = self._own(actor, event_id)
        if event.status is not EventStatus.BOOKED:
            raise DashboardError("invalid_state", 409)
        self._store.save_event(event.model_copy(update={"status": EventStatus.RECEIPT}))
        self._life.log(event_id, "human", "確認", "幹事が開催の終了を伝えました")
        self._life.say(
            event_id,
            "お疲れさまでした。お店の領収書の写真を、このチャットに送ってください。"
            "金額を読み取って、確認のカードをお出しします。",
        )
        self._life.notify(
            event, NotificationKind.CONFIRM_NEEDED, "領収書をアップロードしてください"
        )
        return {"event_id": event_id, "status": "receipt"}

    def _receipt_extraction_done(self, event_id: str) -> bool:
        return self._extraction_done(event_id, UploadKind.RECEIPT)

    def _extraction_done(self, event_id: str, kind: UploadKind) -> bool:
        ups = [u for u in self._store.list_uploads(event_id) if u.kind is kind]
        return any(u.extraction_status == "done" for u in ups)

    def _receipt_extraction_failed(self, event_id: str) -> bool:
        ups = [u for u in self._store.list_uploads(event_id) if u.kind is UploadKind.RECEIPT]
        return any(u.extraction_status == "failed" for u in ups)

    async def find_venues(self, actor: Actor, event_id: str) -> dict[str, Any]:
        """店の候補を出す（エージェントの `search_venues` と同じ検索。順位はコードが決める）。

        条件は保存済みのデータから取る。候補はイベントに保存し、幹事が画面で選ぶ。
        """
        event = self._own(actor, event_id)
        if event.status is not EventStatus.VENUE or self._venues is None:
            raise DashboardError("invalid_state", 409)
        candidates = await self._search_venues(event)
        return {"event_id": event_id, "venue_candidates": candidates}

    async def run_venue_search(self, event_id: str) -> str:
        """出欠が出そろったあと、Cloud Tasks から呼ばれて、店の候補を出す（SPEC 7.5）。

        幹事が「店の候補を出す」を押すのを待たない。失敗は、イベントに残して、幹事の画面の
        「もう一度探す」に任せる（例外は出さない。Cloud Tasks に再実行させない）。
        """
        event = self._store.get_event(event_id)
        if event is None:
            return "gone"
        if event.status is not EventStatus.VENUE or event.venue_candidates or self._venues is None:
            return "skipped"
        try:
            await self._search_venues(event)
        except DashboardError as e:
            return e.code
        return "done"

    async def _search_venues(self, event: Event) -> list[dict[str, Any]]:
        """店を探して、候補をイベントに保存する。失敗は、イベントに理由を残して例外にする。"""
        assert self._venues is not None
        event_id = event.event_id
        code, status = "", 409
        try:
            result = await self._venues.run(event_id)
            if not result.ok:
                code = f"venue_search_{result.reason or 'failed'}"
        except Exception:  # 外部 API（駅・地図）の失敗。本文・キーは出さない
            code, status = "venue_search_failed", 502
        event = self._store.get_event(event_id) or event  # 探しているあいだの変更を上書きしない
        if code:
            self._store.save_event(
                event.model_copy(update={"venue_search": "failed", "venue_search_error": code})
            )
            self._life.say(
                event_id,
                "すみません、お店を見つけられませんでした。下のカードの「もう一度探す」を"
                "押すか、候補に無いお店を名前で入れてください。",
            )
            raise DashboardError(code, status)
        candidates = [
            {
                "place_id": c.place_id, "name": c.name, "address": c.address,
                "nearest_station": c.nearest_station,
                "max_travel_minutes": c.max_travel_minutes,
                "avg_travel_minutes": c.avg_travel_minutes,
                "price_min_yen": c.price_min_yen, "price_max_yen": c.price_max_yen,
                "features": c.features, "rating": c.rating,
                "selection_reason": c.selection_reason, "memory_note": c.memory_note,
            }
            for c in result.proposals
        ]  # fmt: skip
        self._store.save_event(
            event.model_copy(
                update={
                    "venue_candidates": candidates, "venue_search": "done",
                    "venue_search_error": "",
                }
            )  # fmt: skip
        )
        self._life.log(
            event_id, "kuroko", "ツール",
            f"店の候補を{len(candidates)}件出しました（帰りやすさ・希望・過去の実績から）",
        )  # fmt: skip
        self._life.say(
            event_id,
            f"お店の候補を {len(candidates)}件見つけました。みなさんの開催希望駅からの帰りやすさ・"
            "苦手な食べ物・過去の実績から、決まった手順で順位を付けています。"
            "下のカードから1つ選んでください。",
            card="venues",
        )
        if self._org_dm is not None:
            fresh = self._store.get_event(event_id)
            if fresh is not None:
                await self._org_dm.venues(fresh)
        return candidates

    def select_venue(self, actor: Actor, event_id: str, place_id: str, name: str) -> dict[str, Any]:
        event = self._own(actor, event_id)
        if event.status not in (EventStatus.RSVP, EventStatus.VENUE):
            raise DashboardError("invalid_state", 409)
        if not place_id or len(place_id) > 200 or not name or len(name) > 100:
            raise DashboardError("invalid_venue")
        # 候補から選んだときは、店の名前を、保存した候補から取る（画面の値は使わない）
        known = next((c for c in event.venue_candidates if c.get("place_id") == place_id), None)
        if known is not None:
            name = str(known["name"])[:100]
        venue = {"place_id": place_id, "name": name, "selected": True}
        self._store.save_event(
            event.model_copy(update={"venue": venue, "status": EventStatus.VENUE})
        )
        self._life.log(event_id, "human", "確認", f"幹事が店を選びました（{name[:40]}）")
        self._life.say(
            event_id,
            f"「{name}」ですね。お店への予約をお願いします（予約は、幹事さんがお店で行います）。"
            "予約が済んだら、予約完了の画面（スクリーンショット）を、このチャットに送ってください。",
        )
        return {"event_id": event_id, "venue": venue}

    # ------------------------------------------------------------ 参照（記憶・規程。SPEC 7.9）
    async def reference(self, actor: Actor, event_id: str | None = None) -> dict[str, Any]:
        """KUROKO が参照している情報を見せる。記憶（Memory Bank）と、会社の規程（条文と値）。

        読むだけ。記憶は、定型の文だけが入っている（個人の名前・個人ごとの回答は入らない）。
        規程の値は、イベントの写しがあればそれ、なければ既定の値。
        """
        from src.clients.memory_bank import DisabledMemory
        from src.services.memory_facts import TEAM_SCOPE, read_scopes
        from src.services.policy import load_snapshot
        from src.services.policy_search import DocumentRetriever

        scopes = read_scopes(actor.role is Role.GUEST, actor.uid)
        labels = {
            TEAM_SCOPE: "第一開発チームの記憶（事前に入れたもの・保存したもの）",
        }
        memory: list[dict[str, Any]] = []
        available = self._memory is not None and not isinstance(self._memory, DisabledMemory)
        error = ""
        for scope in scopes:
            facts: list[dict[str, str]] = []
            if available and self._memory is not None:
                try:
                    rows = await self._memory.list_facts(scope)
                    facts = [
                        {"text": f.fact, "created": f.created}
                        for f in sorted(rows, key=lambda f: f.created, reverse=True)
                    ]
                except Exception:  # 記憶の読み取りに失敗しても、規程は見せる（理由は出さない）
                    error = "memory_unavailable"
            label = labels.get(scope, "あなたが保存した記憶（体験用）")
            memory.append({"label": label, "facts": facts})
        snap = None
        if event_id:
            try:
                snap = self._own(actor, event_id).policy_snapshot
            except DashboardError:
                snap = None
        snap = snap or load_snapshot()
        doc = DocumentRetriever()
        try:
            articles = [
                {"number": a.number, "heading": a.heading, "text": a.text} for a in doc.articles()
            ]
        except OSError:
            articles = []
        return {
            "memory": {"available": available, "error": error, "groups": memory},
            "policy": {
                "title": doc.title if articles else "規程", "policy_id": snap.policy_id,
                "version": snap.version, "source": snap.source, "articles": articles,
                "values": {
                    "member_classes": [
                        {"label": c.label, "weight": c.weight, "consent_cap_yen": c.consent_cap_yen}
                        for c in snap.member_classes
                    ],
                    "subsidy_per_attendee_yen": snap.subsidy.per_attendee_yen,
                    "subsidy_max_per_event_yen": snap.subsidy.max_per_event_yen,
                    "rounding_unit_yen": snap.rounding_unit_yen,
                    "hard_limit_per_person_yen": snap.hard_limit_per_person_yen,
                    "approver_selection": snap.approver_selection,
                    "venue_max_travel_minutes": snap.venue_max_travel_minutes,
                },
                "citations": snap.citations,
            },
        }

    # ------------------------------------------------------------ 通知
    def list_notifications(self, actor: Actor) -> list[dict[str, Any]]:
        return [n.model_dump(mode="json") for n in self._store.list_notifications(actor.uid)]

    def mark_read(self, actor: Actor, notification_id: str) -> None:
        n = self._store.get_notification(notification_id)
        if n is None or n.uid != actor.uid:
            raise DashboardError("notification_not_found", 404)  # 他人の通知は触れない
        self._store.save_notification(n.model_copy(update={"read": True}))

    def notify(self, uid: str, event_id: str, kind: NotificationKind, text: str) -> None:
        self._store.save_notification(Notification(
            notification_id=_id("nt"), uid=uid, event_id=event_id, kind=kind, text=text[:200],
            created_at=self._now(),
        ))  # fmt: skip

    # ------------------------------------------------------------ クリア（画面から。SPEC 7.7）
    def reset_scenario(self, actor: Actor, mode: str) -> dict[str, int]:
        """この画面（mode）で自分が作ったイベントと通知を削除し、シナリオを最初から始められる
        ようにする。他の利用者・もう一方の画面のイベントは触れない。"""
        if mode not in ("experience", "live"):
            raise DashboardError("invalid_mode")
        if mode == "live" and not self._live_allowed(actor):
            raise DashboardError("live_not_allowed", 403)
        ids = {e["event_id"] for e in self.list_events(actor, mode)}
        for event_id in ids:
            self._store.delete_event(event_id)
        self._store.delete_notifications(actor.uid, ids)
        return {"deleted": len(ids)}

    # ------------------------------------------------------------ 削除（Cloud Scheduler）
    def purge_expired_sandbox(self) -> int:
        expired = self._store.list_expired_sandbox(self._now())
        for e in expired:
            self._store.delete_event(e.event_id)
        return len(expired)


def _budget_view(e: Event) -> dict[str, Any] | None:
    """予約のコース単価が規程の上限を超えているか（超えていなければ None）。"""
    price = (e.venue or {}).get("course_price_yen")
    if e.policy_snapshot is None or not _is_int(price):
        return None
    limit = e.policy_snapshot.hard_limit_per_person_yen
    if price <= limit:
        return None
    esc = e.budget_escalation
    return {
        "course_price_yen": price,
        "limit_yen": limit,
        "organizer_confirmed": bool(esc and esc.organizer_confirmed_at),
        "approver_confirmed": bool(esc and esc.final_confirmed_at),
    }


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def waiting_for(
    event: Event, people: list, *, retro_ready: bool = False, approved: bool = False,
    split_ready: bool = False,
) -> dict[str, Any] | None:  # fmt: skip
    """次に誰の対応を待っているか（SPEC 7.5）。承認・振込は、承認者・参加者の本人の操作。"""
    if event.status is EventStatus.PLANNING:
        return {"who": "organizer", "where": "web", "what": "計画の確認"}
    if event.status is EventStatus.RSVP:
        pending = [p.user_id for p in people if p.rsvp_status.value == "pending"]
        return {"who": "participants", "where": "slack", "what": "出欠の回答", "users": pending}
    if event.status is EventStatus.SPLIT and split_ready:
        return {"who": "organizer", "where": "web", "what": "按分の内訳の確認"}
    if event.status is EventStatus.APPROVAL and approved:
        return {"who": "organizer", "where": "web", "what": "振込の依頼を送る承認"}
    if event.status is EventStatus.APPROVAL:
        approvers = [p.user_id for p in people if p.role.value == "approver"]
        return {"who": "approver", "where": "slack", "what": "按分の承認", "users": approvers}
    if event.status is EventStatus.PAYMENT:
        return {"who": "approver", "where": "bank", "what": "銀行での承認"}
    if event.status is EventStatus.RETRO and retro_ready:
        return {"who": "organizer", "where": "web", "what": "振り返りの確認"}
    if event.status is EventStatus.RETRO:
        return {"who": "participants", "where": "slack", "what": "振り返り（満足度）の回答"}
    return None


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """計画の検査（型・範囲・語彙）。LLM が整理した値でも、幹事の入力でも同じ。"""
    try:
        when = dt.datetime.fromisoformat(str(plan.get("datetime")))
    except ValueError:
        raise DashboardError("invalid_plan") from None
    # エリアは聞かない（店は、参加者の開催希望駅からコードが探す。SPEC 7.5）。来たら残すだけ
    title, area = str(plan.get("title", "")).strip(), str(plan.get("area") or "").strip()
    size, budget = plan.get("party_size"), plan.get("budget_per_person_yen")
    if not title or len(title) > 60 or len(area) > 40:
        raise DashboardError("invalid_plan")
    # 出欠の回答期限（任意。開催日より後にはできない）と、幹事が足す主役（名簿の user_id）
    deadline = str(plan.get("rsvp_deadline") or "")
    if deadline:
        try:
            due = dt.date.fromisoformat(deadline)
        except ValueError:
            raise DashboardError("invalid_plan") from None
        if due > (when.astimezone(msg.JST) if when.tzinfo else when).date():
            raise DashboardError("invalid_plan")
    honorees = plan.get("guests_of_honor") or []
    if not isinstance(honorees, list) or len(honorees) > 20:
        raise DashboardError("invalid_plan")
    if not _is_int(size) or not 2 <= size <= 50:
        raise DashboardError("invalid_plan")
    if not _is_int(budget) or not 1 <= budget <= 100_000:
        raise DashboardError("invalid_plan")
    tags = only_vocab(
        [t for t in plan.get("required_tags", []) if isinstance(t, str)], REQUEST_TAGS
    )
    # 幹事の開催希望駅（任意。駅すぱあとで確かめて、駅コードで持つ）。原文は計画に残さない
    station = str(plan.get("station") or "").strip()[:40]
    details: dict[str, Any] = {"party_size": size, "budget_per_person_yen": budget}
    if area:
        details["area"] = area
    if deadline:
        details["rsvp_deadline"] = deadline
    return {
        "title": title, "datetime": when, "required_tags": tags, "plan": details,
        "honorees": [h for h in honorees if isinstance(h, str)], "station": station,
    }  # fmt: skip


def _with_plan_draft(hint: dict[str, Any], event: Event) -> dict[str, Any]:
    """Slack の依頼文から読み取った計画の案があれば、計画のカードの初期値にする。"""
    example = hint.get("example")
    if event.plan_draft and event.status is EventStatus.PLANNING and isinstance(example, dict):
        plan = {**(example.get("plan") or {}), **event.plan_draft}
        hint = {**hint, "example": {**example, "plan": plan}}
    return hint


def now_after(now: dt.datetime) -> dt.datetime:
    """発言のすぐあとに並ぶ時刻（同じ時刻だと、並びが ID で決まってしまう）。"""
    return now + dt.timedelta(milliseconds=1)


def _button_action(card, index: int) -> str:  # noqa: ANN001
    """カードの `index` 番目のボタンの action_id（無ければ空）。"""
    buttons = [
        el for b in card.blocks if b.get("type") == "actions" for el in b.get("elements", [])
    ]
    return str(buttons[index].get("action_id", "")) if 0 <= index < len(buttons) else ""


def validate_reservation(values: dict[str, Any]) -> dict[str, Any]:
    name, size, price = (
        values.get("venue_name"),
        values.get("party_size"),
        values.get("course_price_yen"),
    )
    try:
        when = dt.datetime.fromisoformat(str(values.get("datetime")))
    except ValueError:
        raise DashboardError("invalid_reservation") from None
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise DashboardError("invalid_reservation")
    if not _is_int(size) or not 1 <= size <= 100 or not _is_int(price) or not 1 <= price <= 100_000:
        raise DashboardError("invalid_reservation")
    return {"venue_name": name.strip(), "datetime": when.isoformat(), "party_size": size,
            "course_price_yen": price}  # fmt: skip


def _card_view(card) -> dict[str, Any]:  # noqa: ANN001
    """Block Kit を、画面に出す形（本文と、ボタンの見出し）にする。ボタンの値は渡さない。"""
    sections, buttons = [], []
    for block in card.blocks:
        if block.get("type") == "section":
            sections.append(str((block.get("text") or {}).get("text", "")))
        elif block.get("type") == "actions":
            for el in block.get("elements", []):
                buttons.append({
                    "index": len(buttons),
                    "label": str((el.get("text") or {}).get("text", "")),
                    "style": el.get("style") or "default",
                })  # fmt: skip
    # 出欠のカードには、開催希望駅・苦手な食べ物の入力欄を出す（SPEC 7.7）。値はデモ用の候補
    fields = []
    if card.kind == "consent" and not card.resolved_text:
        demo = DEMO_ANSWERS.get(card.user_id, {})
        fields = [
            {"key": "station", "label": "開催希望駅", "value": demo.get("station", ""),
             "placeholder": "例: 渋谷"},
            {"key": "dislikes", "label": "苦手な食べ物・食べられないもの",
             "value": demo.get("dislikes", ""), "placeholder": "例: えびが苦手（無ければ空）"},
        ]  # fmt: skip
    return {
        "card_id": card.card_id, "kind": card.kind, "text": card.text, "sections": sections,
        "buttons": [] if card.resolved_text else buttons, "resolved_text": card.resolved_text,
        "created_at": card.created_at.isoformat(), "fields": fields,
        # 体験用の「銀行で承認する」。画面は、銀行の承認ページを模した確認を挟む（SPEC 7.7）
        "bank": card.kind == "bank" and not card.resolved_text,
    }  # fmt: skip


def _payment_card(
    pay: dict, title: str, *, web: bool, requested: bool = False
) -> dict[str, Any] | None:
    """支払いの状態から作る、銀行での承認の依頼・完了の通知（保存しない。SPEC 7.7）。"""
    status, amount = pay.get("status"), int(pay.get("amount_yen") or 0)
    base = {
        "card_id": f"pay-{pay.get('payment_id')}-{status}", "kind": "bank", "buttons": [],
        "resolved_text": None, "created_at": pay.get("updated_at") or "",
    }  # fmt: skip
    lead = f"「{title}」の負担額 *{amount:,}円*"
    if status == "awaiting_bank_approval":
        if web and requested:
            return None  # 届いたカード（Slack と同じもの）を出している
        if web:
            text = (
                f"{lead} の振込を、あなたの委任の範囲内で依頼しました。\n"
                "銀行の承認ページで承認すると、実際に振込が行われます。"
                "（体験用: 下のボタンが、銀行の承認ページの代わりです）"
            )
            buttons = [{"index": 0, "label": "銀行で承認する（体験用）", "style": "primary"}]
            return base | {"text": text, "sections": [text], "buttons": buttons, "bank": True}
        text = (
            f"{lead} の振込を、あなたの委任の範囲内で依頼しました。\n"
            "*10分以内に*、sunabar サービスサイトの「お知らせ」から承認してください。"
        )
        return base | {"text": text, "sections": [text]}
    if status == "completed":
        text = f"{lead} の入金を確認しました。お支払いありがとうございました。"
        return base | {"text": text, "sections": [text], "resolved_text": "支払い済み"}
    if status in ("failed", "blocked"):
        text = f"{lead} の支払いを完了できませんでした。幹事に報告しました。"
        return base | {"text": text, "sections": [text]}
    return None
