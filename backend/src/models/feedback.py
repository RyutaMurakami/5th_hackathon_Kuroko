"""振り返り（SPEC 3章 Feedback・Retrospective。9.8・7.4）。

個人ごとの回答・コメントは、幹事にも見せない（集計だけ）。**コメントの原文は保存しない**。
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.services.vocab import CONCERNS, LIKED, only_vocab


class Feedback(BaseModel):
    """参加者1人×イベント1件。必須は満足度だけ（Slack のボタン1タップ）。"""

    event_id: str
    user_id: str  # 二重回答の防止とリマインドの宛先だけに使う。画面には出さない
    rating: int = Field(ge=1, le=5)
    liked: list[str] = []  # 隔離抽出が読み取った固定の語彙だけ（コメントが無ければ空）
    concerns: list[str] = []
    comment_open: bool = False  # コメントを受け付け中（満足度のあと、DM への返信を待つ）
    submitted_at: datetime

    @model_validator(mode="after")
    def _only_vocabulary(self) -> "Feedback":
        self.liked = only_vocab(self.liked, LIKED)
        self.concerns = only_vocab(self.concerns, CONCERNS)
        return self


class RetroStatus(StrEnum):
    COLLECTING = "collecting"
    AWAITING_ORGANIZER = "awaiting_organizer"
    SAVED = "saved"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class MemoryFact(BaseModel):
    """記憶の事実の下書き（SPEC 9.8）。文面は定型のテンプレートからコードが作る。編集できない。"""

    kind: Literal["venue_record", "venue_evaluation"]
    text: str
    include: bool = True  # 幹事が、含める・含めないを選ぶ
    ref: str | None = None  # Memory Bank に書き込んだ記憶の名前（書き込みの冪等に使う）


class Retrospective(BaseModel):
    event_id: str
    status: RetroStatus = RetroStatus.COLLECTING
    invited_count: int = 0
    invited_user_ids: list[str] = []  # 依頼した人（リマインドの宛先。画面には出さない）
    response_count: int = 0
    retro_deadline: datetime
    reminded_at: datetime | None = None
    # 集計（回答が3件未満のときは、平均だけ。内訳は出さない）
    avg_rating: float | None = None
    liked_counts: dict[str, int] = {}
    concern_counts: dict[str, int] = {}
    # 実績（入力なし。イベントのデータから、コードが作る）
    venue_name: str = ""
    party_size: int = 0
    per_person_yen: int | None = None  # 会計金額 ÷ 出席者数
    course_price_yen: int | None = None
    within_budget: bool | None = None  # 1人あたりが、規程の上限以内か
    # 幹事の確認（Web。Policy Gate 6.4）
    reuse_intent: Literal["yes", "no", "unanswered"] = "unanswered"
    memory_facts: list[MemoryFact] = []
    confirmed_by: str | None = None  # 確認した幹事の Firebase の UID
    confirmed_at: datetime | None = None
    memory_refs: list[str] = []  # Memory Bank に書き込んだ記憶の名前
    saved_at: datetime | None = None
