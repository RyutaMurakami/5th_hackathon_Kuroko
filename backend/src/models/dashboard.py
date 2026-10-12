"""Web ダッシュボードのデータ（SPEC 3章 Message・Notification・Upload。7.5・7.6）。"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Role(StrEnum):
    ORGANIZER = "organizer"  # 許可リスト（dashboard_users）にある Google アカウント
    GUEST = "guest"  # 許可リストに無い Google アカウント（審査員・開発者。sandbox だけ）


class Actor(BaseModel):
    """Firebase の ID トークンから決めた利用者（自己申告ではない）。"""

    uid: str
    email: str
    role: Role


class MessageStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"  # Agent Gateway が入口でブロックした


class Message(BaseModel):
    message_id: str
    event_id: str
    role: Literal["organizer", "kuroko", "system"]
    text: str = Field(max_length=2000)
    attachments: list[str] = []
    status: MessageStatus = MessageStatus.DONE
    created_at: datetime


class NotificationKind(StrEnum):
    CONFIRM_NEEDED = "confirm_needed"  # 幹事の確認待ち
    SLACK_WAITING = "slack_waiting"  # Slack で人の対応待ち
    COMPLETED = "completed"
    BLOCKED = "blocked"
    RETRO_READY = "retro_ready"


class Notification(BaseModel):
    notification_id: str
    uid: str  # 宛先（Firebase の UID）。この人にだけ返す
    event_id: str
    kind: NotificationKind
    text: str
    read: bool = False
    created_at: datetime


class UploadKind(StrEnum):
    RESERVATION = "reservation"
    RECEIPT = "receipt"


class Upload(BaseModel):
    upload_id: str
    event_id: str
    kind: UploadKind
    object_path: str  # Cloud Storage のパス（バケットは設定）
    content_type: str
    size_bytes_declared: int
    source: Literal["upload", "paste"] = "upload"  # 貼り付けも、同じ検査・保存の経路を通る
    status: Literal["issued", "registered", "rejected"] = "issued"
    extraction_status: Literal["pending", "done", "failed"] = "pending"
    # 読み取り結果（幹事が確認するまで使われない）。ocr_receipt の検証済みの値だけ
    extraction: dict | None = None
    uploaded_by: str  # Firebase の UID
    created_at: datetime


class DecisionEntry(BaseModel):
    """経緯（判断ログ）の1件。誰が・何をしたかの要約だけ（個人情報・原文は入れない。SPEC 10章）。"""

    at: datetime
    actor: Literal["kuroko", "payment_agent", "human"]
    action_type: Literal[
        "判断",
        "規程",
        "ツール",
        "送信",
        "照会",
        "ブロック",
        "検査",
        "記録",
        "更新",
        "待機",
        "確認",
        "署名",
    ]
    summary: str = Field(max_length=200)


# ---- 入力の検査（型・範囲） ----
ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png", "application/pdf")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 1ファイル 5MB まで
MAX_UPLOADS = {UploadKind.RESERVATION: 2, UploadKind.RECEIPT: 3}  # 1イベントあたり
GUEST_MAX_EVENTS = 2  # 1ゲストあたり
LIVE_MAX_EVENTS = 50  # 実演用に登録したアカウント（開発者）は、リハーサルを繰り返せる
GUEST_MAX_MESSAGES_PER_EVENT = 30
SANDBOX_DAYS = 7  # ゲストのイベントは、作成から7日で削除する


class PersonaCard(BaseModel):
    """登場人物に届いたカード（Slack の DM と同じ中身。Web のチャット画面に出す。SPEC 7.7）。"""

    card_id: str
    event_id: str
    user_id: str  # 宛先の参加者
    kind: Literal["consent", "approval", "budget", "bank", "feedback"]
    text: str
    blocks: list[dict]  # Slack に送ったものと同じ Block Kit（ボタンの値も、ここから取る）
    resolved_text: str | None = None  # 回答済みなら、その結果の文面
    created_at: datetime
