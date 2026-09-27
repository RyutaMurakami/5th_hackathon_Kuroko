from pydantic import BaseModel


class SlackDirectMessage(BaseModel):
    """kuroko-gateway が Cloud Tasks で kuroko-api に渡す、Bot への DM 1件。"""

    event_id: str
    team_id: str
    user_id: str
    channel_id: str
    text: str
    ts: str
