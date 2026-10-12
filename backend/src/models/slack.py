"""Slack の操作（ボタン）の中身。kuroko-gateway が署名を検証し、Cloud Tasks で後段に渡す。"""

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Action(StrEnum):
    """ボタンの action_id。値（value）は、DM を作った側（kuroko-api）が JSON で入れる。"""

    CONSENT = "consent"  # 出欠（参加）＋委任に同意
    DECLINE = "decline"  # 欠席
    REVOKE = "revoke"  # 委任の取り消し（振込依頼の前まで）
    APPROVE = "approve"  # 按分の承認（承認者）
    BUDGET = "budget"  # 予算超過の最終確認（承認者）
    RATE = "rate"  # 振り返りの満足度（1〜5。1タップ）
    BANK = "bank"  # 体験用の「銀行で承認する」（体験用の承認待ちの振込だけ。SPEC 7.7）

    @classmethod
    def parse(cls, action_id: str) -> "Action":
        """ボタンの action_id から操作を決める。Slack は1通のメッセージの中で action_id の重複を
        認めない（`invalid_blocks`）ので、同じ操作のボタンを並べるときは `rate:3` のように
        `:` のあとに印を付ける。印は無視する。"""
        return cls(action_id.split(":", 1)[0])


class SlackInteraction(BaseModel):
    """署名検証済みのボタン操作1件。`user_id` は Slack が署名したペイロードから取った本人の ID。"""

    interaction_id: str  # 決定論的な ID（同じ操作の再送・連打を1回にまとめる。タスク名にも使う）
    action: Action
    team_id: str
    user_id: str  # 押した人の Slack ユーザーID（自己申告ではない）
    channel_id: str | None = None
    message_ts: str | None = None
    response_url: str | None = None
    value: dict[str, Any]  # DM を作ったときに入れた値
    # Web のカードから押したとき（SPEC 7.7）だけ入る。**kuroko-api の中でだけ**設定する
    # （ゲートウェイから届いた値は捨てる）。だれとして押したか（参加者の user_id）と、押した人
    acting_for: str | None = None
    web_uid: str | None = None


class SlackHomeOpened(BaseModel):
    """App Home が開かれた（Home タブの再描画のきっかけ）。"""

    event_id: str
    team_id: str
    user_id: str


def encode_value(value: dict[str, Any]) -> str:
    """ボタンの value（2,000文字まで）。Slack がペイロードにそのまま入れて署名する。"""
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if len(raw) > 1900:
        raise ValueError("button value too long")
    return raw
