"""Slack への送信の口（kuroko-api だけが Bot Token を持つ。テストでは偽物に差し替える）。"""

from typing import Protocol


class SlackPort(Protocol):
    async def post_dm(self, slack_user_id: str, text: str, blocks: list[dict]) -> None: ...

    async def respond(self, response_url: str, text: str, blocks: list[dict]) -> None: ...

    async def publish_home(self, slack_user_id: str, view: dict) -> None: ...
