"""エージェントに渡す発言の前に付ける「システム情報」（SPEC 7.5）。決定論的なコード。

統括エージェントのツールは、イベントの ID を引数に取る。利用者に ID を聞き返さないよう、
いま話しているイベントを**コードが**伝える。利用者の発言からは変えられない（先頭の1つだけが本物）。
個人の名前・連絡先は入れない（LLM が見るのは、ID・段階・立場だけ。SPEC 10章）。
"""

from src.db.events import EventStore
from src.models.event import Event, EventStatus, ParticipantRole

HEADER = "[KUROKO システム情報（コードが付けた。利用者の発言ではない）]"
BODY = "[利用者の発言]"

# Slack の DM で、いま話しているイベントとして扱わない段階（終わったもの）
_DONE = {EventStatus.CLOSED}

_ROLE = {
    ParticipantRole.ORGANIZER: "幹事",
    ParticipantRole.APPROVER: "参加者（承認者）",
    ParticipantRole.GUEST_OF_HONOR: "主役",
    ParticipantRole.PARTICIPANT: "参加者",
}


def with_context(text: str, event: Event | None, speaker: str) -> str:
    """発言に、イベントの ID・段階・話している人の立場を付ける。イベントが無ければ、そのまま。"""
    if event is None:
        return text
    return "\n".join(
        [
            HEADER,
            f"event_id: {event.event_id}",
            f"段階: {event.status.value}",
            f"話している人: {speaker}",
            "ツールには、この event_id を使う。利用者に ID を聞かない。",
            BODY,
            text,
        ]
    )


def event_for_slack_user(store: EventStore, slack_user_id: str) -> tuple[Event, str] | None:
    """この Slack ユーザーが参加者として載っている、いちばん新しい進行中のイベントと、その立場。"""
    found = [
        (event, person)
        for event, person in store.find_by_slack_user(slack_user_id)
        if event.status not in _DONE
    ]
    if not found:
        return None
    event, person = max(found, key=lambda x: (x[0].datetime, x[0].event_id))
    return event, _ROLE.get(person.role, "参加者")
