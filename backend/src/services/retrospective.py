"""振り返りの収集と、記憶への保存（SPEC 7.4・9.8）。決定論的なコード。LLM は使わない。

1. `collect_feedback`: 完了の直後、**出席者の全員**（幹事を除く）に依頼。体験用のイベントで、
   Slack を使わない架空の参加者のぶんは、デモ用の代行が答える（SPEC 7.4・7.6）
2. `record_rating`: 満足度（1〜5）。1人1回（二重回答は無視）。必須はこれだけ
3. `record_comment`: 任意のコメント（200字まで）。語彙に落とした値だけを残し、原文は保存しない
4. `tick`（Scheduler）: 2日後に1回だけリマインド、3日後に締切（全員が回答したら、その時点で締切）
5. `summarize`: 集計。回答が3件未満のときは、平均だけ（内訳は出さない）
6. `confirm`: 幹事が Web で確認し、定型の事実を Memory Bank に書き込む（Policy Gate 6.4）

個人ごとの回答・コメントは、画面・幹事・記憶に出さない（集計だけ）。ログにもコメントを出さない。
"""

import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from src.clients.memory_bank import MemoryStore
from src.db.events import EventStore
from src.models.dashboard import NotificationKind
from src.models.event import Event, EventStatus, ParticipantRole, RsvpStatus
from src.models.feedback import Feedback, MemoryFact, Retrospective, RetroStatus
from src.services import slack_messages as msg
from src.services.cards import close_cards, deliver_card, reachable
from src.services.feedback_extract import MAX_COMMENT_CHARS, FeedbackExtractor
from src.services.memory_facts import draft_facts, scope_for
from src.services.policy_gates import check_before_memory
from src.services.slack_port import SlackPort

logger = logging.getLogger(__name__)

DEADLINE_DAYS = 3  # 完了の3日後が締切（MVPは定数。SPEC 9.8）
REMIND_AFTER_DAYS = 2  # 未回答の人に、1回だけリマインドする
MIN_RESPONSES_FOR_BREAKDOWN = 3  # これ未満のときは、内訳を出さない（個人の特定を避ける）

# デモ用の代行の回答（体験用のイベントで、Slack を使わない架空の参加者のぶん。SPEC 7.6）。
# 決まった値を順に使う（乱数・LLM は使わない）。語彙は `services/vocab.py` のもの
PROXY_ANSWERS: tuple[tuple[int, tuple[str, ...], tuple[str, ...]], ...] = (
    (5, ("food", "access"), ()),
    (4, ("atmosphere",), ()),
    (4, ("food", "price"), ()),
    (5, ("access", "drinks"), ()),
    (3, ("food",), ("noisy",)),
    (4, ("service",), ()),
    (5, ("food", "atmosphere"), ()),
)

THANKS = (
    "ご回答ありがとうございました。コメントがあれば、このDMに返信してください"
    f"（{MAX_COMMENT_CHARS}字まで・任意）。原文は保存されません。"
)


class RetroError(Exception):
    """振り返りの操作を受け付けられない。message は画面に返すコード。"""


class Retrospectives:
    def __init__(
        self,
        *,
        store: EventStore,
        slack: SlackPort,
        extractor: FeedbackExtractor,
        memory: MemoryStore | None = None,
        lifecycle=None,  # noqa: ANN001
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store, self._slack, self._extractor, self._now = store, slack, extractor, now
        self._memory, self._life = memory, lifecycle

    # ---------------------------------------------------------------- 依頼
    async def collect_feedback(self, event_id: str) -> dict[str, Any]:
        event = self._store.get_event(event_id)
        if event is None:
            return {"started": False, "reason": "event_not_found"}
        if self._store.get_retro(event_id) is not None:
            return {"started": False, "reason": "already_started"}  # 再実行しても二重に依頼しない
        if event.status not in (EventStatus.COMPLETED, EventStatus.RETRO):
            return {"started": False, "reason": "not_completed"}  # 全員の入金を確認したあとだけ
        # **記録を先に作り、そのあとでカードを送る**。送る途中の失敗でタスクが再実行されても、
        # 「すでに始まっている」で止まり、同じカードが重複しない（回答も、この記録に入る）
        invited = self._recipients(event, only=None)
        proxied = self._proxy_answers(event)  # 体験用: Slack を使わない架空の参加者のぶん
        now = self._now()
        retro = Retrospective(
            event_id=event_id,
            invited_count=len(invited) + len(proxied),
            invited_user_ids=invited + proxied,
            response_count=len(proxied),
            retro_deadline=(event.completed_at or now) + timedelta(days=DEADLINE_DAYS),
            **self._auto_record(event),
        )
        self._apply_summary(retro)
        self._store.save_retro(retro)
        self._store.save_event(event.model_copy(update={"status": EventStatus.RETRO}))
        await self._send_cards(event, invited, reminder=False)
        if self._life:
            self._life.log(
                event_id, "kuroko", "送信",
                f"出席者 {retro.invited_count}名に振り返り（満足度）を依頼しました",
            )  # fmt: skip
            if proxied:
                self._life.log(
                    event_id, "kuroko", "記録",
                    f"デモ用の代行: Slack を使わない {len(proxied)}名の振り返りを代行しました",
                )  # fmt: skip
            self._life.say(
                event_id,
                f"全員の入金を確認し、精算が完了しました。出席者の全員（{retro.invited_count}名）に、"
                "振り返り（満足度）のお願いをお送りしました。個人ごとの回答は、幹事にも見えません。"
                + (
                    f"（体験用: 架空の参加者 {len(proxied)}名のぶんは、デモ用の代行が回答済みです）"
                    if proxied
                    else ""
                ),
                card="retro",
            )
        if not invited:
            self._close(retro, event)  # 答えを待つ人がいない。その時点の集計で、幹事の確認に進む
        return {"started": True, "invited": retro.invited_count}

    def _proxy_answers(self, event: Event) -> list[str]:
        """体験用のイベントで、カードを届けられない出席者の満足度を、デモ用の代行が記録する。

        体験用でないイベントでは、何もしない（届けられる人にだけ依頼する）。主役・承認者を含む
        出席者が対象で、幹事は含めない（Web で確認する側）。
        """
        if not event.sandbox:
            return []
        now, done = self._now(), []
        for p in self._store.list_participants(event.event_id):
            if (
                not p.attendance_confirmed
                or p.rsvp_status is RsvpStatus.DECLINING
                or p.role is ParticipantRole.ORGANIZER
                or reachable(event, p)
            ):
                continue
            rating, liked, concerns = PROXY_ANSWERS[len(done) % len(PROXY_ANSWERS)]
            if self._store.get_feedback(event.event_id, p.user_id) is None:
                self._store.save_feedback(
                    Feedback(
                        event_id=event.event_id, user_id=p.user_id, rating=rating,
                        liked=list(liked), concerns=list(concerns), submitted_at=now,
                    )  # fmt: skip
                )
            done.append(p.user_id)
        return done

    def _auto_record(self, event: Event) -> dict[str, Any]:
        """実績（入力なし）。イベントのデータから、コードが作る（SPEC 9.8 `venue_record`）。"""
        venue = event.venue or {}
        people = [
            p
            for p in self._store.list_participants(event.event_id)
            if p.attendance_confirmed and p.rsvp_status is not RsvpStatus.DECLINING
        ]
        total, limit = event.total_amount_yen, None
        if event.policy_snapshot is not None:
            limit = event.policy_snapshot.hard_limit_per_person_yen
        per_person = total // len(people) if total and people else None
        course = venue.get("course_price_yen")
        return {
            "venue_name": str(venue.get("name") or venue.get("venue_name") or "")[:100],
            "party_size": len(people),
            "per_person_yen": per_person,
            "course_price_yen": course if isinstance(course, int) and course > 0 else None,
            "within_budget": per_person <= limit if per_person and limit else None,
        }

    def _recipients(self, event: Event, *, only: set[str] | None) -> list[str]:
        """振り返りを依頼する人（幹事を除く出席者のうち、カードを届けられる人）。"""
        out = []
        for p in self._store.list_participants(event.event_id):
            if (
                not p.attendance_confirmed
                or p.rsvp_status is RsvpStatus.DECLINING
                or p.role is ParticipantRole.ORGANIZER  # 幹事は Web で確認する側
                or not reachable(event, p)  # Slack を使える人と、デモの登場人物（SPEC 7.7）
                or (only is not None and p.user_id not in only)
            ):
                continue
            out.append(p.user_id)
        return out

    async def _send_cards(self, event: Event, user_ids: list[str], *, reminder: bool) -> None:
        people = {p.user_id: p for p in self._store.list_participants(event.event_id)}
        for user_id in user_ids:
            p = people[user_id]
            text, blocks = msg.feedback_request(
                event, p, slack_user_id=p.slack_user_id or "", reminder=reminder
            )
            await deliver_card(
                self._store, self._slack, event, p, "feedback", text, blocks, self._now()
            )

    # ---------------------------------------------------------------- 回答
    def record_rating(
        self, event_id: str, user_id: str, slack_user_id: str, rating: int, *, via_web: bool = False
    ) -> str:
        """満足度を記録する。結果: recorded / duplicate / not_allowed / closed / invalid。

        `via_web` は、Web のカードから押したとき（体験用のイベントを作った本人が、登場人物として
        押したことを、呼び出し側が確かめたあと。SPEC 7.7）。
        """
        person = next(
            (p for p in self._store.list_participants(event_id) if p.user_id == user_id), None
        )
        retro = self._store.get_retro(event_id)
        if person is None:
            return "not_allowed"
        if not via_web and (not person.slack_user_id or person.slack_user_id != slack_user_id):
            return "not_allowed"  # 記録上の本人だけ（ゲートウェイの確認に加えて、記録でも確かめる）
        if retro is not None and user_id not in retro.invited_user_ids:
            return "not_allowed"  # 依頼していない人の回答は受けない
        if retro is None or retro.status is not RetroStatus.COLLECTING:
            return "closed"
        if not 1 <= rating <= 5:
            return "invalid"
        if self._store.get_feedback(event_id, user_id) is not None:
            return "duplicate"  # 二重回答は、最初の回答を残す
        self._store.save_feedback(
            Feedback(
                event_id=event_id,
                user_id=user_id,
                rating=rating,
                comment_open=True,
                submitted_at=self._now(),
            )
        )
        retro.response_count += 1
        close_cards(self._store, event_id, "feedback", user_id, "回答済みです。")
        if retro.invited_count and retro.response_count >= retro.invited_count:
            event = self._store.get_event(event_id)
            self._close(retro, event)  # 全員が回答したら、その時点で締切
        else:
            self._apply_summary(retro)
            self._store.save_retro(retro)
        return "recorded"

    # ---------------------------------------------------------------- 締切・幹事の確認
    def _close(self, retro: Retrospective, event: Event | None) -> None:
        """締切。集計と、記憶の事実の下書きを作り、幹事の確認待ちにする。"""
        retro.status = RetroStatus.AWAITING_ORGANIZER
        self._apply_summary(retro)
        if event is not None:
            retro.memory_facts = self._draft(retro, event)
        self._store.save_retro(retro)
        for user_id in retro.invited_user_ids:
            close_cards(self._store, retro.event_id, "feedback", user_id, "回答を締め切りました。")
        if self._life and event is not None:
            self._life.log(
                retro.event_id, "kuroko", "記録",
                f"振り返りを集計しました（回答 {retro.response_count} / {retro.invited_count}名）",
            )  # fmt: skip
            self._life.notify(
                event, NotificationKind.RETRO_READY, "振り返りがまとまりました。確認してください"
            )
            self._life.say(
                retro.event_id,
                f"振り返りがまとまりました（回答 {retro.response_count} / "
                f"{retro.invited_count}名）。下のカードで集計を確認して、次回のために"
                "覚えさせる内容を選んでください。",
                card="retro",
            )

    def _draft(self, retro: Retrospective, event: Event) -> list[MemoryFact]:
        when = event.datetime
        return draft_facts(retro, event_type=event.event_type, year=when.year, month=when.month)

    def close_now(self, event_id: str) -> str:
        """幹事が、回答を待たずに締め切る。結果: closed / not_collecting。"""
        retro = self._store.get_retro(event_id)
        if retro is None or retro.status is not RetroStatus.COLLECTING:
            return "not_collecting"
        self._close(retro, self._store.get_event(event_id))
        return "closed"

    async def confirm(
        self, event_id: str, web_uid: str, *, reuse_intent: str, include: list[str], save: bool
    ) -> Retrospective:
        """幹事の確認（Web）。`save` なら、選んだ事実を Memory Bank に書き込む（Policy Gate 6.4）。

        事実の文面は、ここでコードが作り直す（画面から送られた文は使わない）。画面から受けるのは、
        「次回もこの店を使いたいか」と、含める事実の種類（`kind`）と、保存するかどうかだけ。
        """
        event = self._store.get_event(event_id)
        retro = self._store.get_retro(event_id)
        if event is None or retro is None:
            raise RetroError("retro_not_found")
        if reuse_intent not in ("yes", "no", "unanswered"):
            raise RetroError("invalid_reuse_intent")
        done = {f.kind: f.ref for f in retro.memory_facts if f.ref}  # 前回の途中まで書けたもの
        retro.reuse_intent = reuse_intent  # type: ignore[assignment]
        facts = [
            f.model_copy(update={"include": f.kind in include, "ref": done.get(f.kind)})
            for f in self._draft(retro, event)
        ]
        chosen = [f for f in facts if f.include] if save else []
        gate = check_before_memory(event, retro, web_uid, chosen)
        if not gate.ok:
            if self._life:
                self._life.log(event_id, "kuroko", "ブロック", "記憶の保存の前の検査で止まりました")
            raise RetroError(gate.failures[0].value)
        if save:
            if self._memory is None:
                raise RetroError("memory_not_configured")
            # スコープは、イベントからコードが決める（リクエスト・LLM の値を使わない）
            scope = scope_for(event.sandbox, event.guest_owner_uid)
            for fact in chosen:
                if fact.ref is None:
                    try:
                        fact.ref = await self._memory.create(scope, fact.text)
                    except Exception as e:
                        # 途中まで書けたものを残す（やり直しても、同じ事実を二重に書かない）
                        retro.memory_facts = facts
                        self._store.save_retro(retro)
                        logger.warning("save_memory failed: event=%s", event_id)
                        unset = getattr(e, "code", "") == "memory_not_configured"
                        raise RetroError(
                            "memory_not_configured" if unset else "memory_unavailable"
                        ) from None
        now = self._now()
        retro.memory_facts = facts
        retro.status = RetroStatus.SAVED if save else RetroStatus.SKIPPED
        retro.confirmed_by, retro.confirmed_at = web_uid, now
        if save:
            retro.memory_refs = [f.ref for f in chosen if f.ref]
            retro.saved_at = now
        self._store.save_retro(retro)
        self._store.save_event(event.model_copy(update={"status": EventStatus.CLOSED}))
        if self._life:
            self._life.say(
                event_id,
                (
                    f"{len(chosen)}件の事実を、記憶（Memory Bank）に保存しました。"
                    "次の企画で、同じお店が候補に出たときに、理由に添えます。"
                    if save
                    else "今回の内容は、記憶に保存しませんでした。"
                )
                + "これで、この会の幹事の仕事はすべて完了です。お疲れさまでした。",
                card="retro",
            )
            self._life.log(event_id, "human", "確認", "幹事が振り返りを確認しました")
            if save:
                self._life.log(
                    event_id, "kuroko", "記録",
                    f"次回のために、{len(chosen)}件の事実を記憶（Memory Bank）に保存しました",
                )  # fmt: skip
        return retro

    async def try_capture_comment(self, slack_user_id: str, text: str) -> str | None:
        """満足度のあとの、DM への返信をコメントとして受ける。受け付け中でなければ None。

        コメントは語彙に落とし、**原文は保存しない・ログに出さない**。
        """
        feedback = self._store.find_open_comment(slack_user_id)
        if feedback is None:
            return None
        extracted = await self._extractor.extract(text[:MAX_COMMENT_CHARS])
        feedback.liked, feedback.concerns = extracted.liked, extracted.concerns
        feedback.comment_open = False
        self._store.save_feedback(feedback)
        retro = self._store.get_retro(feedback.event_id)
        if retro is not None:
            self._apply_summary(retro)
            self._store.save_retro(retro)
        return "コメントを受け取りました。ありがとうございました。"

    # ---------------------------------------------------------------- 集計
    def summarize(self, event_id: str) -> dict[str, Any]:
        feedbacks = self._store.list_feedbacks(event_id)
        n = len(feedbacks)
        out: dict[str, Any] = {
            "response_count": n,
            "avg_rating": round(sum(f.rating for f in feedbacks) / n, 2) if n else None,
            "liked_counts": {},
            "concern_counts": {},
        }
        if n >= MIN_RESPONSES_FOR_BREAKDOWN:  # 3件未満は、平均だけ（個人の特定を避ける）
            out["liked_counts"] = dict(Counter(x for f in feedbacks for x in f.liked))
            out["concern_counts"] = dict(Counter(x for f in feedbacks for x in f.concerns))
        return out

    def _apply_summary(self, retro: Retrospective) -> None:
        s = self.summarize(retro.event_id)
        retro.avg_rating = s["avg_rating"]
        retro.liked_counts, retro.concern_counts = s["liked_counts"], s["concern_counts"]

    # ---------------------------------------------------------------- Scheduler
    async def tick(self) -> dict[str, int]:
        """1日1回（Cloud Scheduler）。依頼・リマインド・締切を進める。"""
        now = self._now()
        out = {"started": 0, "reminded": 0, "closed": 0}
        # 依頼は、完了の直後に始まる（SPEC 7.4）。ここは、始まらなかったものの拾い直し
        for event in self._store.list_events_by_status("completed"):
            if event.completed_at and self._store.get_retro(event.event_id) is None:
                if (await self.collect_feedback(event.event_id)).get("started"):
                    out["started"] += 1
        for retro in self._store.list_retros_by_status(RetroStatus.COLLECTING.value):
            event = self._store.get_event(retro.event_id)
            if event is None:
                continue
            if now >= retro.retro_deadline:
                self._close(retro, event)
                out["closed"] += 1
                continue
            started = retro.retro_deadline - timedelta(days=DEADLINE_DAYS)
            if retro.reminded_at is None and now >= started + timedelta(days=REMIND_AFTER_DAYS):
                answered = {f.user_id for f in self._store.list_feedbacks(retro.event_id)}
                pending = set(retro.invited_user_ids) - answered
                if pending:
                    await self._send_cards(
                        event, self._recipients(event, only=pending), reminder=True
                    )
                retro.reminded_at = now  # 1回だけ
                self._store.save_retro(retro)
                out["reminded"] += 1
        return out
