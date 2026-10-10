"""イベントと参加者の記録（SPEC 3章）。ここでは按分・承認者の決定に必要なものを定義する。

金額は円の整数（AP2 の最小単位と同じ。日本円は 3300 = 3,300円）。
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field

from src.models.policy import PolicySnapshot
from src.models.split import BudgetEscalation


class EventStatus(StrEnum):
    PLANNING = "planning"
    RSVP = "rsvp"
    VENUE = "venue"
    BOOKED = "booked"
    DAY_OF = "day_of"
    RECEIPT = "receipt"
    SPLIT = "split"
    APPROVAL = "approval"
    PAYMENT = "payment"
    COMPLETED = "completed"
    RETRO = "retro"
    CLOSED = "closed"


class ParticipantRole(StrEnum):
    PARTICIPANT = "participant"
    ORGANIZER = "organizer"
    GUEST_OF_HONOR = "guest_of_honor"
    APPROVER = "approver"


class RsvpStatus(StrEnum):
    PENDING = "pending"
    ATTENDING = "attending"
    DECLINING = "declining"


class Participant(BaseModel):
    user_id: str = Field(min_length=1)
    display_name: str = ""
    # 規程の区分の判定に使う（`services/split.classify_member`）
    job_title: str = Field(min_length=1)  # 例: 部長・課長・一般
    hire_date: dt.date
    employee_id: str = Field(min_length=1)  # 承認者の決定の最後の比較（小さいほうが優先）
    employment_type: str = Field(min_length=1)  # 正社員・契約社員・業務委託 など
    role: ParticipantRole = ParticipantRole.PARTICIPANT
    attendance_confirmed: bool = False
    # 出欠の回答（Slack の同意ボタン。署名検証済みの操作だけが書く。SPEC 7.2）
    rsvp_status: RsvpStatus = RsvpStatus.PENDING
    # 委任状（payment-api が署名）。幹事・主役は持たない
    mandate_id: str | None = None
    # Slack 上の本人（承認者の本人確認に使う。署名検証済みの Slack 操作の ID と突き合わせる）
    slack_user_id: str | None = None
    # 幹事の口座に、この人の負担額の入金を確認した時刻（`confirm_incoming_payments`。SPEC 8.6）。
    # 支払いエージェント側の完了の確認（payment-api）とは独立に記録する
    collection_confirmed_at: dt.datetime | None = None


class Event(BaseModel):
    event_id: str
    event_type: str = "welcome_farewell"
    title: str = ""
    datetime: dt.datetime
    organizer_user_id: str
    # 幹事の Web 上の本人（Firebase の UID）。領収書の金額を確定できるのは、この UID だけ
    # （SPEC 7.3）
    organizer_web_uid: str = ""
    guests_of_honor: list[str] = []
    status: EventStatus = EventStatus.PLANNING
    total_amount_yen: int | None = Field(default=None, gt=0)
    policy_id: str = ""
    policy_version: str = ""
    # 企画時に規程から取り出し、コードで検証した値（SPEC 9.7）。以後の計算はこの写しだけを使う
    policy_snapshot: PolicySnapshot | None = None
    # 予算超過の確認フロー（SPEC 9.1）の記録。按分の承認（Approval）より前に起きるので Event に持つ
    budget_escalation: BudgetEscalation | None = None


class Receipt(BaseModel):
    """店の領収書（SPEC 3章）。金額は読み取りまたは手入力で、**幹事が確定したものだけ**使う。"""

    event_id: str
    total_amount_yen: int = Field(gt=0)
    source: str = "upload"  # upload / manual
    confirmed_by: str | None = None  # 確定した人の Firebase の UID
    confirmed_at: dt.datetime | None = None
