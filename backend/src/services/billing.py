"""請求（Merchant 役）と、幹事口座の入金の確認（SPEC 4.1 `create_checkout`・
`confirm_incoming_payments`。TASKS B13）。**決定論的なコード。LLM は関与しない。**

- 請求は、**Policy Gate 6.2 を通ったときだけ**作る。金額表（承認済み）の各人の負担額から作り、
  KMS の鍵で署名して `payment-api` に渡す（`payment-api` は請求側を信用せず、6.3 で再検査する）
- 入金の確認は、支払いエージェント側の確認（`payment-api`）とは**独立に**、幹事口座の入金明細で行う
"""

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.clients.bank_adapter import BankAdapter
from src.clients.claim_signer import ClaimSigner
from src.clients.payment_api import PaymentApi, PaymentApiError, PaymentOutcome
from src.db.events import EventStore
from src.db.payments import PaymentReader
from src.models.dashboard import NotificationKind
from src.models.event import EventStatus
from src.models.split import Approval, SplitResult
from src.services.policy_gates import CheckoutLine, Gate, check_before_checkout

logger = logging.getLogger(__name__)

ISSUER = "kuroko-api"
AUDIENCE = "payment-api"
CURRENCY = "JPY"
JST = ZoneInfo("Asia/Tokyo")
MAX_STATEMENT_DAYS = 31  # bank-adapter が受ける明細の期間の上限


@dataclass
class CheckoutRun:
    ok: bool
    failures: list[Gate] = field(default_factory=list)  # ゲートが止めた項目（ok=False のとき）
    outcomes: dict[str, str] = field(default_factory=dict)  # user_id → 支払いの状態
    errors: dict[str, str] = field(default_factory=dict)  # user_id → 呼び出しの失敗コード


@dataclass
class CollectionRun:
    received: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    amount_mismatch: list[str] = field(default_factory=list)  # 入金はあるが、金額が違う人
    all_received: bool = False


def payment_id_for(event_id: str, payer_user_id: str) -> str:
    """同じ人への支払いの識別子。決定論的なので、再送しても二重の支払いにならない。"""
    return "pay_" + hashlib.sha256(f"{event_id}|{payer_user_id}".encode()).hexdigest()[:24]


class UnknownEvent(Exception):
    pass


class BillingService:
    def __init__(
        self,
        *,
        store: EventStore,
        signer: ClaimSigner,
        payment_api: PaymentApi,
        bank: BankAdapter,
        payments: PaymentReader,
        checkout_ttl_seconds: int,
        lifecycle=None,  # noqa: ANN001
        now=lambda: datetime.now(UTC),
        today=None,
    ) -> None:
        self._store, self._signer = store, signer
        self._payment_api, self._bank, self._payments = payment_api, bank, payments
        self._ttl = timedelta(seconds=checkout_ttl_seconds)
        self._now = now
        self._life = lifecycle
        self._today = today or (lambda: self._now().astimezone(JST).date())

    # ---- 請求 ----
    def _lines(self, split: SplitResult, organizer: str, guests: set[str]) -> list[CheckoutLine]:
        """金額表から、請求する各人を作る（幹事・主役・負担0円の人には作らない）。"""
        return [
            CheckoutLine(r.user_id, organizer, r.share_yen, split.hash)
            for r in split.rows
            if r.user_id != organizer and r.user_id not in guests and r.share_yen > 0
        ]

    async def create_checkouts(self, event_id: str) -> CheckoutRun:
        event = self._store.get_event(event_id)
        if event is None:
            raise UnknownEvent
        participants = self._store.list_participants(event_id)
        split = self._store.get_split(event_id)
        approval: Approval | None = self._store.get_approval(event_id)
        lines = (
            self._lines(split, event.organizer_user_id, set(event.guests_of_honor))
            if split is not None
            else []
        )
        result = check_before_checkout(event, participants, split, approval, lines, self._payments)
        if not result.ok:
            logger.info("policy gate 6.2 blocked event=%s failures=%s", event_id, result.failures)
            return CheckoutRun(ok=False, failures=result.failures)

        run = CheckoutRun(ok=True)
        now = self._now()
        for line in lines:
            claims = {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "sub": line.payer_user_id,
                "payee": line.payee_user_id,
                "event_id": event_id,
                "payment_reference": event_id,
                "amount_yen": line.amount_yen,
                "currency": CURRENCY,
                "split_hash": line.split_hash,
                "iat": int(now.timestamp()),
                "exp": int((now + self._ttl).timestamp()),
                "jti": uuid.uuid4().hex,
            }
            token = await asyncio.to_thread(self._signer.sign, claims)
            outcome = await self._start(event_id, line, token)
            if isinstance(outcome, PaymentOutcome):
                run.outcomes[line.payer_user_id] = outcome.status
            else:
                run.errors[line.payer_user_id] = outcome
        if run.outcomes:
            event.status = EventStatus.PAYMENT
            self._store.save_event(event)
            if self._life:
                self._life.log(
                    event_id,
                    "payment_agent",
                    "ツール",
                    f"{len(run.outcomes)}名の振込を依頼しました",
                )
        return run

    async def _start(self, event_id: str, line: CheckoutLine, token: str) -> PaymentOutcome | str:
        try:
            return await self._payment_api.start_payment(
                payment_id=payment_id_for(event_id, line.payer_user_id),
                event_id=event_id,
                payer_user_id=line.payer_user_id,
                payee_user_id=line.payee_user_id,
                amount_yen=line.amount_yen,
                checkout_jwt=token,
                checkout_hash=hashlib.sha256(token.encode()).hexdigest(),
            )
        except PaymentApiError as e:
            return e.code

    # ---- 入金の確認 ----
    async def poll_collections(self) -> dict[str, int]:
        """1分ごと（Cloud Scheduler）: 入金の確認が要るイベントだけを確認する（SPEC 8.6）。

        対象は、`payment` のイベントのうち、支払いが完了したのに、幹事口座の入金をまだ確認できて
        いない人がいるもの。支払いの完了は**確認を始めるきっかけ**で、回収済みにするかは明細で決める。
        """
        checked = completed = 0
        oldest = self._today() - timedelta(days=MAX_STATEMENT_DAYS)
        for event in self._store.list_events_by_status(EventStatus.PAYMENT.value):
            if _jst_date(event.datetime) < oldest:
                continue  # 明細を照会できる期間を過ぎた（人が確認する）
            confirmed = {
                p.user_id
                for p in self._store.list_participants(event.event_id)
                if p.collection_confirmed_at is not None
            }
            paid = {
                p["payer_user_id"]
                for p in self._payments.list_payments(event.event_id)
                if p.get("status") == "completed"
            }
            if not paid - confirmed:
                continue
            try:
                run = await self.confirm_incoming_payments(event.event_id)
            except Exception:  # 1件の失敗で、ほかのイベントの確認を止めない
                logger.exception("collection poll failed: event=%s", event.event_id)
                continue
            checked += 1
            completed += run.all_received
        return {"checked": checked, "completed": completed}

    async def confirm_incoming_payments(self, event_id: str) -> CollectionRun:
        event = self._store.get_event(event_id)
        split = self._store.get_split(event_id)
        if event is None or split is None:
            raise UnknownEvent
        guests = set(event.guests_of_honor)
        expected = {
            r.user_id: r.share_yen
            for r in split.rows
            if r.user_id != event.organizer_user_id and r.user_id not in guests and r.share_yen > 0
        }
        date_from = _jst_date(event.datetime)
        date_to = min(self._today(), date_from + timedelta(days=MAX_STATEMENT_DAYS))
        entries = await self._bank.incoming(
            user_id=event.organizer_user_id, date_from=date_from, date_to=date_to
        )
        used: set[str] = set()
        run = CollectionRun()
        for user_id, amount in sorted(expected.items()):
            # 体験用のイベントは、全員が同じ幹事口座の明細を見る。別のイベントの、同じ人・同じ金額の
            # 入金を取り違えないよう、このイベントの支払いが完了した人だけを照合する（SPEC 7.7）
            if event.sandbox and not self._payments.has_completed_payment(event_id, user_id):
                run.missing.append(user_id)
                continue
            match = next(
                (
                    e
                    for e in entries
                    if e.item_key not in used
                    and e.counterparty_user_id == user_id
                    and e.amount_yen == amount
                ),
                None,
            )
            if match is not None:
                used.add(match.item_key)  # 1件の入金は1人ぶんにしか使わない
                run.received.append(user_id)
            elif any(e.counterparty_user_id == user_id and e.item_key not in used for e in entries):
                run.amount_mismatch.append(user_id)
            else:
                run.missing.append(user_id)
        stamp = self._now()
        for p in self._store.list_participants(event_id):
            if p.user_id in run.received and p.collection_confirmed_at is None:
                self._store.save_participant(
                    event_id, p.model_copy(update={"collection_confirmed_at": stamp})
                )
        run.all_received = not run.missing and not run.amount_mismatch
        if run.all_received and expected and event.status is EventStatus.PAYMENT:
            event.status = EventStatus.COMPLETED  # 全員の入金を明細で確認した（SPEC 8.6）
            event.completed_at = stamp
            self._store.save_event(event)
            if self._life:
                self._life.log(event_id, "payment_agent", "確認", "全員の入金を明細で確認しました")
                self._life.notify(event, NotificationKind.COMPLETED, "全員の入金を確認しました")
        elif run.missing and self._life:
            self._life.log(
                event_id, "payment_agent", "待機", f"{len(run.missing)}名の入金を待っています"
            )
        return run


def _jst_date(value: datetime) -> date:
    """銀行の日付は日本時間。時刻に時差がなければ（ローカル・テスト）そのまま日付にする。"""
    return value.astimezone(JST).date() if value.tzinfo else value.date()
