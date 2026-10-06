"""按分の結果と承認（SPEC 3章 SplitResult・Approval）。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class SplitRow(BaseModel):
    user_id: str
    member_class_id: str
    weight: float
    # 負担割合（％）= 係数 ÷ 係数の合計（主役は0）。表示用で、小数第2位までに丸めている。
    # 金額（share_yen）は丸めた％からでなく、正確な分数から求める
    ratio_percent: float
    subsidy_eligible: bool
    share_yen: int  # 本人の負担額（承認者は端数の不足分を含む）


class SplitResult(BaseModel):
    event_id: str
    policy_id: str
    policy_version: str
    total_amount_yen: int
    base_amount_yen: int  # 会計金額 − 会社補助
    subsidy_yen: int  # 9.3節のルールを適用した実額
    weight_sum: float
    per_weight_yen: int  # 表示用（係数1あたりの金額の切り捨て）。各人の負担額は分数で計算する
    rows: list[SplitRow]  # user_id 順
    shortfall_yen: int
    shortfall_to: str  # 端数の不足分を負担する承認者の user_id
    approver_user_id: str
    hash: str  # 承認対象の金額表のハッシュ値。請求（Checkout）にも埋め込む（6.2）


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"


class Approval(BaseModel):
    event_id: str
    approver_user_id: str
    split_hash: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_at: datetime | None = None
