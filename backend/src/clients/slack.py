"""Slack Web API への薄いラッパー（kuroko-api だけが Bot Token を持つ）。"""

from functools import lru_cache

from slack_sdk.web.async_client import AsyncWebClient

from src.config import get_settings


@lru_cache
def _client() -> AsyncWebClient:
    return AsyncWebClient(token=get_settings().slack_bot_token)


async def post_message(channel_id: str, text: str) -> str | None:
    """送ったメッセージの ts（あとで書き換えるときに使う）。"""
    res = await _client().chat_postMessage(channel=channel_id, text=text)
    return res.get("ts")


async def update_message(channel_id: str, ts: str, text: str) -> None:
    """自分が送ったメッセージを書き換える（「考え中」を返答に差し替える）。"""
    await _client().chat_update(channel=channel_id, ts=ts, text=text)


async def post_dm(slack_user_id: str, text: str, blocks: list[dict]) -> None:
    """ユーザーIDを宛先にして DM を送る（Bot とのDMが無ければ開く。im:write）。"""
    await _client().chat_postMessage(channel=slack_user_id, text=text, blocks=blocks)


async def respond(response_url: str, text: str, blocks: list[dict]) -> None:
    """押されたボタンのメッセージを置き換える（Slack の response_url。トークン不要）。"""
    import httpx

    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            response_url,
            json={"replace_original": True, "text": text, "blocks": blocks},
        )


async def publish_home(slack_user_id: str, view: dict) -> None:
    await _client().views_publish(user_id=slack_user_id, view=view)


async def user_email(slack_user_id: str) -> str | None:
    """Slack のプロフィールのメール（`users:read` と `users:read.email`。取れなければ None）。"""
    res = await _client().users_info(user=slack_user_id)
    email = ((res.get("user") or {}).get("profile") or {}).get("email")
    return str(email).lower() if email else None


async def download_file(url: str, max_bytes: int = 10 * 1024 * 1024) -> bytes | None:
    """DM に添えられたファイル（`url_private_download`）を、Bot Token で取得する（files:read）。

    Slack のドメイン以外・大きすぎるものは取らない。
    """
    import httpx

    if not url.startswith("https://files.slack.com/"):
        return None
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
        res = await http.get(
            url, headers={"Authorization": f"Bearer {get_settings().slack_bot_token}"}
        )
    if res.status_code != 200 or len(res.content) > max_bytes:
        return None
    return res.content


async def user_id_by_email(email: str) -> str | None:
    """メールから Slack ユーザーID（`users:read.email`。取れなければ None）。"""
    res = await _client().users_lookupByEmail(email=email)
    return (res.get("user") or {}).get("id")
