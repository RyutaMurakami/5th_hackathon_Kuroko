"""出力の形（固定）。モード（用途）ごとに使う欄が決まっていて、使わない欄は空にする。"""

from pydantic import BaseModel, Field


class ExtractOutput(BaseModel):
    # preferences（参加者の自由記述・口コミ本文から）
    dislikes: list[str] = Field(
        default_factory=list, description="食べられない・苦手なもの（語彙のみ）"
    )
    preferences: list[str] = Field(default_factory=list, description="店の希望（語彙のみ）")
    nearest_station: str | None = Field(default=None, description="最寄り駅の名前（駅名だけ）")
    # feedback（振り返りの任意のコメントから）
    liked: list[str] = Field(default_factory=list, description="良かった点（語彙のみ）")
    concerns: list[str] = Field(default_factory=list, description="気になった点（語彙のみ）")
