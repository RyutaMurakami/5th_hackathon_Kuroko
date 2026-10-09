"""振り返り（SPEC 3章 Feedback・Retrospective。9.8・7.4）。

個人ごとの回答・コメントは、幹事にも見せない（集計だけ）。**コメントの原文は保存しない**。
"""

from datetime import datetime
from enum import StrEnum

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
