"""Slack の Events API のペイロードから、処理すべき入力を取り出す。

kuroko-gateway で使う。業務判断はしない。
"""

from typing import Any

from src.models.schemas import SlackDirectMessage


def extract_direct_message(payload: dict[str, Any]) -> SlackDirectMessage | None:
    """人から Bot への DM（新規の発言）だけを返す。

    それ以外（Bot 自身の発言・編集・削除など）は None。

    チャンネルでのメンションへの対応はバックログ（TASKS B16a）。
    """
    if payload.get("type") != "event_callback":
        return None
    event = payload.get("event") or {}
    if event.get("type") != "message" or event.get("channel_type") != "im":
        return None
    # subtype があるのは編集・削除・参加など。bot_id があるのは Bot（KUROKO 自身を含む）の発言
    if event.get("subtype") or event.get("bot_id"):
        return None
    text = (event.get("text") or "").strip()
    if not text or not event.get("user"):
        return None
    return SlackDirectMessage(
        event_id=payload["event_id"],
        team_id=payload.get("team_id", ""),
        user_id=event["user"],
        channel_id=event["channel"],
        text=text,
        ts=event.get("ts", ""),
    )
