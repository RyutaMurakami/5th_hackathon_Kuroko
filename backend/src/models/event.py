"""イベントと参加者の記録（SPEC 3章）。ここでは按分・承認者の決定に必要なものを定義する。

金額は円の整数（AP2 の最小単位と同じ。日本円は 3300 = 3,300円）。
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field

from src.models.policy import PolicySnapshot


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


class Event(BaseModel):
    event_id: str
    event_type: str = "welcome_farewell"
    title: str = ""
    datetime: dt.datetime
    organizer_user_id: str
    guests_of_honor: list[str] = []
    status: EventStatus = EventStatus.PLANNING
    total_amount_yen: int | None = Field(default=None, gt=0)
    policy_id: str = ""
    policy_version: str = ""
    # 企画時に規程から取り出し、コードで検証した値（SPEC 9.7）。以後の計算はこの写しだけを使う
    policy_snapshot: PolicySnapshot | None = None
