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
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from src.db.events import EventStore
from src.db.payments import PaymentReader
from src.models.dashboard import (
    ALLOWED_CONTENT_TYPES,
    GUEST_MAX_EVENTS,
    GUEST_MAX_MESSAGES_PER_EVENT,
    MAX_UPLOAD_BYTES,
    MAX_UPLOADS,
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
from src.services.agent_context import with_context
from src.services.lifecycle import Lifecycle
from src.services.policy_extract import PolicyReader
from src.services.receipt_ocr import ReceiptModel, ocr_receipt
from src.services.reservation_read import ReservationModel, ingest_reservation
from src.services.scenario_hint import hint_for
from src.services.vocab import REQUEST_TAGS, only_vocab

Chat = Callable[[str, str], Awaitable[str]]  # (会話の鍵, 発言) → 返答
FAILED_REPLY = "いま返答を作れませんでした。少し待って、もう一度送ってください。"


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


class RetroOps(Protocol):
    """振り返りの締切と、幹事の確認（`Retrospectives`。SPEC 7.4・9.8）。"""

    def close_now(self, event_id: str) -> str: ...

    async def confirm(
        self, event_id: str, web_uid: str, *, reuse_intent: str, include: list[str], save: bool
    ) -> Any: ...


class RsvpDispatcher(Protocol):
    async def start_rsvp(self, event_id: str) -> None: ...

    async def start_split_approval(self, event_id: str) -> None: ...


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
        now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    ) -> None:
        self._personas, self._policy, self._retro = personas, policy, retro
        self._reservation_reader = reservation_reader
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
            if actor.role is Role.ORGANIZER and event.organizer_web_uid == actor.uid:
                if not event.sandbox:
                    return event
            elif actor.role is Role.GUEST and event.sandbox and event.guest_owner_uid == actor.uid:
                return event
        raise DashboardError("event_not_found", 404)

    # ------------------------------------------------------------ 一覧・詳細
    def list_events(self, actor: Actor) -> list[dict[str, Any]]:
        events = (
            self._store.list_events_for_organizer(actor.uid)
            if actor.role is Role.ORGANIZER
            else self._store.list_events_for_guest(actor.uid)
        )
        return [
            {"event_id": e.event_id, "title": e.title, "datetime": e.datetime.isoformat(),
             "status": e.status.value, "sandbox": e.sandbox}
            for e in events
        ]  # fmt: skip

    def get_event(self, actor: Actor, event_id: str) -> dict[str, Any]:
        e = self._own(actor, event_id)
        people = self._store.list_participants(event_id)
        retro = self._retro_view(event_id)
        retro_ready = (retro or {}).get("status") == "awaiting_organizer"
        return {
            "event_id": e.event_id, "title": e.title, "datetime": e.datetime.isoformat(),
            "status": e.status.value, "sandbox": e.sandbox, "plan": e.plan, "venue": e.venue,
            "total_amount_yen": e.total_amount_yen,
            # 実名は返さない（表示名は仮名のまま。再識別は別の経路）。承諾の状況だけ
            "participants": [
                {"user_id": p.user_id, "display_name": p.display_name, "role": p.role.value,
                 "rsvp_status": p.rsvp_status.value, "mandate_signed": p.mandate_id is not None}
                for p in people
            ],
            "uploads": [u.model_dump(mode="json") for u in self._store.list_uploads(event_id)],
            "messages": [m.model_dump(mode="json") for m in self._store.list_messages(event_id)],
            "waiting_for": waiting_for(e, people, retro_ready=retro_ready),
            "split": self._split_view(event_id),
            "budget_overrun": _budget_view(e),
            "payments": self._payments.list_payments(event_id) if self._payments else [],
            "bank_approval": e.bank_approval,
            "personas": self._personas_view(e, people),
            "retro": retro,
            "decision_log": [
                d.model_dump(mode="json") for d in self._store.list_decisions(event_id)
            ],
            "hint": hint_for(
                e, people, has_receipt=self._store.get_receipt(event_id) is not None,
                retro_ready=retro_ready,
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
        self, actor: Actor, event_id: str, card_id: str, index: int
    ) -> dict[str, Any]:
        """登場人物として、カードのボタンを押す。体験用のイベントを作った本人だけ。"""
        from src.services.slack_actions import CardError

        event = self._own(actor, event_id)
        if not event.sandbox or self._personas is None:
            raise DashboardError("not_allowed", 403)
        try:
            await self._personas.press_card(event, card_id, index, actor.uid)
        except CardError as e:
            raise DashboardError(str(e), 409) from None
        card = self._store.get_card(event_id, card_id)
        if card is None or card.resolved_text is None:
            raise DashboardError("action_rejected", 409)  # 本人でない・段階が違う、など
        return {"card_id": card_id, "resolved_text": card.resolved_text}

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
    async def send_message(self, actor: Actor, event_id: str | None, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text or len(text) > 2000:
            raise DashboardError("invalid_text")
        now = self._now()
        if event_id is None:
            event = self._create_event(actor, now)  # 最初の発言で planning のイベントを作る
        else:
            event = self._own(actor, event_id)
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
        status, reply = MessageStatus.DONE, ""
        try:
            # いま開いているイベントを、コードが伝える（ID を聞き返さない。SPEC 7.5）
            asked = with_context(text, event, "幹事")
            reply = await self._chat(f"web:{event.event_id}:{actor.uid}", asked)
        except Exception:  # Gateway のブロックも含む。理由・本文はログに出さない
            status, reply = MessageStatus.FAILED, FAILED_REPLY
        answer = Message(
            message_id=_id("m"), event_id=event.event_id, role="kuroko", text=reply[:2000],
            status=status, created_at=self._now(),
        )  # fmt: skip
        self._store.save_message(answer)
        return {"event_id": event.event_id, "reply": answer.model_dump(mode="json")}

    def _create_event(self, actor: Actor, now: dt.datetime) -> Event:
        guest = actor.role is Role.GUEST
        if guest and len(self._store.list_events_for_guest(actor.uid)) >= GUEST_MAX_EVENTS:
            raise DashboardError("guest_event_limit", 429)
        event = Event(
            event_id=_id("ev"), datetime=now, organizer_user_id=actor.uid,
            organizer_web_uid=actor.uid, status=EventStatus.PLANNING, sandbox=guest,
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
            event, owner_email=actor.email, snapshot=reading.snapshot if reading else None
        )
        self._store.save_event(event)
        self._life.log(event_id, "human", "確認", "幹事が計画を確定しました")
        if reading is not None:
            self._life.log(
                event_id, "kuroko", "規程",
                "規程の文書から値を読み取り、検証しました" if reading.from_document
                else "規程の文書から読み取れなかったため、既定の値を使いました",
            )  # fmt: skip
        self._life.log(event_id, "kuroko", "送信", "参加者に出欠の依頼を送ります（Slack）")
        await self._dispatcher.start_rsvp(event_id)
        return {"event_id": event_id, "status": event.status.value}

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

    async def _read_receipt(self, up: Upload) -> Upload:
        """読み取れなければ failed（手入力に切り替えられる）。結果は確認するまで使われない。"""
        data = self._signer.read_bytes(up.object_path) if self._ocr else None
        reading = await ocr_receipt(self._ocr, data) if self._ocr and data else None
        if reading is None or not reading.ok:
            return up.model_copy(update={"extraction_status": "failed"})
        return up.model_copy(update={
            "extraction_status": "done",
            "extraction": {
                "venue_name": reading.venue_name, "date": reading.date,
                "total_amount_yen": reading.total_amount_yen, "line_items": reading.line_items,
                "warnings": reading.warnings,
            },
        })  # fmt: skip

    async def _read_reservation(self, up: Upload) -> Upload:
        """読み取れなければ failed（手入力できる）。結果は、幹事が確定するまで使われない。"""
        model = self._reservation_reader
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
        return {"confirmed": "reservation", "source": source, "over_budget": over}

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

    def select_venue(self, actor: Actor, event_id: str, place_id: str, name: str) -> dict[str, Any]:
        event = self._own(actor, event_id)
        if event.status not in (EventStatus.RSVP, EventStatus.VENUE):
            raise DashboardError("invalid_state", 409)
        if not place_id or len(place_id) > 200 or not name or len(name) > 100:
            raise DashboardError("invalid_venue")
        venue = {"place_id": place_id, "name": name, "selected": True}
        self._store.save_event(
            event.model_copy(update={"venue": venue, "status": EventStatus.VENUE})
        )
        self._life.log(event_id, "human", "確認", f"幹事が店を選びました（{name[:40]}）")
        return {"event_id": event_id, "venue": venue}

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


def waiting_for(event: Event, people: list, *, retro_ready: bool = False) -> dict[str, Any] | None:
    """次に誰の対応を待っているか（Web には実行ボタンを置かず、待ち相手だけを出す。SPEC 7.5）。"""
    if event.status is EventStatus.PLANNING:
        return {"who": "organizer", "where": "web", "what": "計画の確認"}
    if event.status is EventStatus.RSVP:
        pending = [p.user_id for p in people if p.rsvp_status.value == "pending"]
        return {"who": "participants", "where": "slack", "what": "出欠の回答", "users": pending}
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
    title, area = str(plan.get("title", "")).strip(), str(plan.get("area", "")).strip()
    size, budget = plan.get("party_size"), plan.get("budget_per_person_yen")
    if not title or len(title) > 60 or not area or len(area) > 40:
        raise DashboardError("invalid_plan")
    if not _is_int(size) or not 2 <= size <= 50:
        raise DashboardError("invalid_plan")
    if not _is_int(budget) or not 1 <= budget <= 100_000:
        raise DashboardError("invalid_plan")
    tags = only_vocab(
        [t for t in plan.get("required_tags", []) if isinstance(t, str)], REQUEST_TAGS
    )
    return {
        "title": title, "datetime": when, "required_tags": tags,
        "plan": {"area": area, "party_size": size, "budget_per_person_yen": budget},
    }  # fmt: skip


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
    return {
        "card_id": card.card_id, "kind": card.kind, "text": card.text, "sections": sections,
        "buttons": [] if card.resolved_text else buttons, "resolved_text": card.resolved_text,
        "created_at": card.created_at.isoformat(),
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
