"""イベントと参加者の記録（SPEC 3章）。ここでは按分・承認者の決定に必要なものを定義する。

金額は円の整数（AP2 の最小単位と同じ。日本円は 3300 = 3,300円）。
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from src.models.policy import PolicySnapshot
from src.models.split import BudgetEscalation
from src.services.vocab import DIETARY, REQUEST_TAGS, only_vocab


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


class Preferences(BaseModel):
    """参加者の好み（SPEC 3章）。隔離抽出を通した固定の語彙だけ。完了時に削除する（9.6節）。"""

    nearest_station_code: str | None = None  # `verify_station` で一意に決めた駅コード（開催希望駅）
    nearest_station_name: str = ""  # その駅の正式な名前（開催案内の所要時間に使う）
    dietary_must: list[str] = []  # 食べられないもの（ハード制約）
    dietary_avoid: list[str] = []  # 苦手なもの（ソフト制約）
    request_tags: list[str] = []  # 店の希望（ソフト制約）

    @model_validator(mode="after")
    def _only_vocabulary(self) -> "Preferences":
        self.dietary_must = only_vocab(self.dietary_must, DIETARY)
        self.dietary_avoid = only_vocab(self.dietary_avoid, DIETARY)
        self.request_tags = only_vocab(self.request_tags, REQUEST_TAGS)
        return self


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
    preferences: Preferences = Preferences()
    # Slack 上の本人（承認者の本人確認に使う。署名検証済みの Slack 操作の ID と突き合わせる）
    slack_user_id: str | None = None
    # デモの登場人物（Web のチャット画面に列がある人。SPEC 7.7）。体験用のイベントでは、
    # イベントを作った本人が、この人として Web のカードのボタンを押せる
    demo_persona: bool = False
    # 幹事の口座に、この人の負担額の入金を確認した時刻（`confirm_incoming_payments`。SPEC 8.6）。
    # 支払いエージェント側の完了の確認（payment-api）とは独立に記録する
    collection_confirmed_at: dt.datetime | None = None


class Event(BaseModel):
    event_id: str
    event_type: str = "welcome_farewell"
    title: str = ""
    datetime: dt.datetime
    organizer_user_id: str
    # ゲスト（審査員・開発者）の体験用のイベントか。true のときだけ、デモ用の代行を受け付ける
    sandbox: bool = False
    guest_owner_uid: str | None = (
        None  # sandbox のとき、作成したゲストの UID（他のゲストには見えない）
    )
    expires_at: dt.datetime | None = None  # sandbox の削除の期限（作成から7日）
    # 登場人物の振込を、どこで承認するか（SPEC 7.7）。bank: 本物の銀行（sunabar）。
    # web: 体験用（Web のカードの「銀行で承認する（体験用）」）。payment-api がこの値を読む
    bank_approval: str = "bank"
    # どの画面で作ったか（SPEC 7.7）。experience: 審査員の体験用（Web だけで進める）。
    # live: 開発者の実演用（Slack と本物の銀行で操作する。実演用に登録したアカウントだけ）
    ui_mode: str = "experience"
    # 店の候補（`search_venues` と同じ検索の結果。幹事が Web で選ぶ。口コミ本文は含まない）
    venue_candidates: list[dict] = []
    # 店の検索の進み具合（出欠が出そろうと、コードが自動で探す。SPEC 7.5）。
    # "": まだ / searching: 探している / done: 候補あり / failed: 失敗（理由は下の欄）
    venue_search: str = ""
    venue_search_error: str = ""
    # 幹事が確認して確定した計画（日時・人数・エリア・予算・主役など）と、選んだ店・予約の内容
    plan: dict = {}
    venue: dict | None = None
    # 幹事の Web 上の本人（Firebase の UID）。領収書の金額を確定できるのは、この UID だけ
    # （SPEC 7.3）
    organizer_web_uid: str = ""
    # Slack の DM から始めたイベント（実演用。SPEC 7.8）。Slack の本人と、登録したアカウントの
    # メール。Web にログインしたとき、このメールの本人のイベントとして引き継ぐ（UID が決まる）
    organizer_email: str = ""
    organizer_slack_user_id: str = ""
    # 計画の確定前の案（Slack の依頼文から読み取った値。幹事が確かめて確定する）
    plan_draft: dict = {}
    guests_of_honor: list[str] = []
    # 幹事が計画で決めた店の条件（例: 個室が必須）。幹事が確認した値だけ（LLM・希望ではない）
    plan_required_tags: list[str] = []
    status: EventStatus = EventStatus.PLANNING
    total_amount_yen: int | None = Field(default=None, gt=0)
    completed_at: dt.datetime | None = None  # 送金完了・経費記録済みになった時刻（振り返りの起点）
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
