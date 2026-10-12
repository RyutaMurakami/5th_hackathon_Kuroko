"""登場人物に届けるカード（Slack の DM と、Web のチャット画面。SPEC 7.7）。

体験用（sandbox）のイベントの、デモの登場人物には、Slack に送るのと同じカードを保存して、
Web の画面にも出す。Slack のアカウントがあれば、DM も送る。
"""

import uuid
from datetime import datetime

from src.db.events import EventStore
from src.models.dashboard import PersonaCard
from src.models.event import Event, Participant
from src.services.slack_port import SlackPort

REPLACED = "新しい依頼に置き換わりました。"


def close_cards(store: EventStore, event_id: str, kind: str, user_id: str, text: str) -> None:
    """この人の、この種類の未回答のカードを、回答済み（結果の文面つき）にする。"""
    for card in store.list_cards(event_id):
        if card.kind == kind and card.user_id == user_id and card.resolved_text is None:
            store.save_card(card.model_copy(update={"resolved_text": text}))


def reachable(event: Event, person: Participant) -> bool:
    """この人にカードを届けられるか（Slack のアカウントがある、または Web の登場人物）。"""
    return bool(person.slack_user_id) or (event.sandbox and person.demo_persona)


async def deliver_card(
    store: EventStore, slack: SlackPort, event: Event, person: Participant, kind: str,
    text: str, blocks: list[dict], now: datetime,
) -> bool:  # fmt: skip
    """カードを届ける。Slack の DM と、体験用のイベントでは Web のチャット画面にも。"""
    delivered = False
    if event.sandbox and person.demo_persona:
        # 作り直したカード（按分のやり直しなど）は、古いほうを閉じる
        close_cards(store, event.event_id, kind, person.user_id, REPLACED)
        store.save_card(
            PersonaCard(
                card_id=f"cd_{uuid.uuid4().hex[:16]}", event_id=event.event_id,
                user_id=person.user_id, kind=kind, text=text, blocks=blocks,  # type: ignore[arg-type]
                created_at=now,
            )
        )  # fmt: skip
        delivered = True
    if person.slack_user_id:
        await slack.post_dm(person.slack_user_id, text, blocks)
        delivered = True
    return delivered
