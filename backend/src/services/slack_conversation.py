"""Bot への DM に、統括エージェントで返答する（kuroko-api の後段。TASKS B16a・B22）。"""

import logging

from src.clients import slack
from src.models.schemas import SlackDirectMessage
from src.services import kuroko_chat
from src.services.container import get_retro

logger = logging.getLogger(__name__)

# エージェントが失敗・空応答のときの固定の文面（エージェントの出力を使わない。ARCHITECTURE 8章）
FALLBACK_TEXT = (
    "すみません、いまうまく返答できませんでした。少し時間をおいて、もう一度送ってください。"
)


async def handle_direct_message(message: SlackDirectMessage) -> None:
    # 満足度のあとの返信は、振り返りのコメント（語彙に落として原文は捨てる。LLM には渡さない）
    captured = await get_retro().try_capture_comment(message.user_id, message.text)
    if captured:
        await slack.post_message(message.channel_id, captured)
        return
    try:
        text = await kuroko_chat.reply(f"slack:{message.team_id}:{message.user_id}", message.text)
    except Exception:
        # 再試行すると同じ質問に二重に答えかねないので、固定の文面を返して終える
        logger.exception("agent failed: event_id=%s", message.event_id)
        text = ""
    await slack.post_message(message.channel_id, text or FALLBACK_TEXT)
