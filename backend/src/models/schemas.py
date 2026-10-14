from pydantic import BaseModel


class SlackFile(BaseModel):
    """DM に添えられたファイル（画像だけを扱う。SPEC 7.8）。"""

    file_id: str
    mimetype: str
    url: str  # url_private_download（Bot Token で取得する）
    size: int = 0


class SlackDirectMessage(BaseModel):
    """kuroko-gateway が Cloud Tasks で kuroko-api に渡す、Bot への DM 1件。"""

    event_id: str
    team_id: str
    user_id: str
    channel_id: str
    text: str
    ts: str
    files: list[SlackFile] = []
