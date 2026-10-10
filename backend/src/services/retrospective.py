"""振り返りの収集（SPEC 7.4・9.8）。決定論的なコード。

1. `collect_feedback`: 完了の翌日、出席者（主役・承認者を含む。幹事は Web で任意）に DM で依頼
2. `record_rating`: 満足度（1〜5）。1人1回（二重回答は無視）。必須はこれだけ
3. `record_comment`: 任意のコメント（200字まで）。語彙に落とした値だけを残し、原文は保存しない
4. `tick`（Scheduler）: 2日後に1回だけリマインド、3日後に締切（全員が回答したら、その時点で締切）
5. `summarize`: 集計。回答が3件未満のときは、平均だけ（内訳は出さない）

個人ごとの回答・コメントは、画面・幹事・記憶に出さない（集計だけ）。ログにもコメントを出さない。
"""

import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from src.db.events import EventStore
from src.models.event import Event, ParticipantRole
from src.models.feedback import Feedback, Retrospective, RetroStatus
from src.services import slack_messages as msg
from src.services.feedback_extract import MAX_COMMENT_CHARS, FeedbackExtractor
from src.services.slack_port import SlackPort

logger = logging.getLogger(__name__)

DEADLINE_DAYS = 3  # 完了の3日後が締切（MVPは定数。SPEC 9.8）
REMIND_AFTER_DAYS = 2  # 未回答の人に、1回だけリマインドする
MIN_RESPONSES_FOR_BREAKDOWN = 3  # これ未満のときは、内訳を出さない（個人の特定を避ける）

THANKS = (
    "ご回答ありがとうございました。コメントがあれば、このDMに返信してください"
    f"（{MAX_COMMENT_CHARS}字まで・任意）。原文は保存されません。"
)


class Retrospectives:
    def __init__(
        self,
        *,
        store: EventStore,
        slack: SlackPort,
        extractor: FeedbackExtractor,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store, self._slack, self._extractor, self._now = store, slack, extractor, now

    # ---------------------------------------------------------------- 依頼
    async def collect_feedback(self, event_id: str) -> dict[str, Any]:
        event = self._store.get_event(event_id)
        if event is None:
            return {"started": False, "reason": "event_not_found"}
        if self._store.get_retro(event_id) is not None:
            return {"started": False, "reason": "already_started"}  # 再実行しても二重に依頼しない
        invited = await self._send(event, only=None, reminder=False)
        now = self._now()
        self._store.save_retro(
            Retrospective(
                event_id=event_id,
                invited_count=len(invited),
                invited_user_ids=invited,
                retro_deadline=(event.completed_at or now) + timedelta(days=DEADLINE_DAYS),
            )
        )
        return {"started": True, "invited": len(invited)}

    async def _send(self, event: Event, *, only: set[str] | None, reminder: bool) -> list[str]:
        sent = []
        for p in self._store.list_participants(event.event_id):
            if (
                not p.attendance_confirmed
                or p.role is ParticipantRole.ORGANIZER  # 幹事は Web で任意に答える
                or not p.slack_user_id
                or (only is not None and p.user_id not in only)
            ):
                continue
            text, blocks = msg.feedback_request(
                event, p, slack_user_id=p.slack_user_id, reminder=reminder
            )
            await self._slack.post_dm(p.slack_user_id, text, blocks)
            sent.append(p.user_id)
        return sent

    # ---------------------------------------------------------------- 回答
    def record_rating(self, event_id: str, user_id: str, slack_user_id: str, rating: int) -> str:
        """満足度を記録する。結果: recorded / duplicate / not_allowed / closed / invalid。"""
        person = next(
            (p for p in self._store.list_participants(event_id) if p.user_id == user_id), None
        )
        retro = self._store.get_retro(event_id)
        if person is None or not person.slack_user_id or person.slack_user_id != slack_user_id:
            return "not_allowed"  # 記録上の本人だけ（ゲートウェイの確認に加えて、記録でも確かめる）
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
        if retro.invited_count and retro.response_count >= retro.invited_count:
            retro.status = RetroStatus.AWAITING_ORGANIZER  # 全員が回答したら、その時点で締切
        self._apply_summary(retro)
        self._store.save_retro(retro)
        return "recorded"

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
        for event in self._store.list_events_by_status("completed"):
            if (
                event.completed_at
                and now >= event.completed_at + timedelta(days=1)  # 完了の翌日
                and self._store.get_retro(event.event_id) is None
            ):
                if (await self.collect_feedback(event.event_id)).get("started"):
                    out["started"] += 1
        for retro in self._store.list_retros_by_status(RetroStatus.COLLECTING.value):
            event = self._store.get_event(retro.event_id)
            if event is None:
                continue
            if now >= retro.retro_deadline:
                retro.status = RetroStatus.AWAITING_ORGANIZER
                self._apply_summary(retro)
                self._store.save_retro(retro)
                out["closed"] += 1
                continue
            started = retro.retro_deadline - timedelta(days=DEADLINE_DAYS)
            if retro.reminded_at is None and now >= started + timedelta(days=REMIND_AFTER_DAYS):
                answered = {f.user_id for f in self._store.list_feedbacks(retro.event_id)}
                pending = set(retro.invited_user_ids) - answered
                if pending:
                    await self._send(event, only=pending, reminder=True)
                retro.reminded_at = now  # 1回だけ
                self._store.save_retro(retro)
                out["reminded"] += 1
        return out
