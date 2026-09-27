"""Slack Web API への薄いラッパー（kuroko-api だけが Bot Token を持つ）。"""

from functools import lru_cache

from slack_sdk.web.async_client import AsyncWebClient

from src.config import get_settings


@lru_cache
def _client() -> AsyncWebClient:
    return AsyncWebClient(token=get_settings().slack_bot_token)


async def post_message(channel_id: str, text: str) -> None:
    await _client().chat_postMessage(channel=channel_id, text=text)
