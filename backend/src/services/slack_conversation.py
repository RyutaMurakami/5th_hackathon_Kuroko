"""Bot への DM に、統括エージェントで返答する（kuroko-api の後段。TASKS B16a・B22）。"""

import logging

from src.clients import slack
from src.models.schemas import SlackDirectMessage
from src.services import kuroko_chat
from src.services.agent_context import event_for_slack_user, with_context
from src.services.container import get_event_store, get_retro

logger = logging.getLogger(__name__)

# エージェントが失敗・空応答のときの固定の文面（エージェントの出力を使わない。ARCHITECTURE 8章）
FALLBACK_TEXT = (
    "すみません、いまうまく返答できませんでした。少し時間をおいて、もう一度送ってください。"
)
# 返答ができるまでのあいだに出す文面（動いていることを伝える。SPEC 7.5）。固定の文で、LLM は使わない
THINKING_TEXT = ":hourglass_flowing_sand: KUROKO が考えています…（30秒ほどかかることがあります）"


async def _show_thinking(channel_id: str) -> str | None:
    """「考え中」を先に出す。出せなくても、返答は続ける（表示の工夫で、処理を止めない）。"""
    try:
        return await slack.post_message(channel_id, THINKING_TEXT)
    except Exception:
        logger.warning("could not post the thinking message")
        return None


async def _answer(channel_id: str, thinking_ts: str | None, text: str) -> None:
    """「考え中」を返答に書き換える。書き換えられなければ、新しいメッセージで返す。"""
    if thinking_ts:
        try:
            await slack.update_message(channel_id, thinking_ts, text)
            return
        except Exception:
            logger.warning("could not update the thinking message")
    await slack.post_message(channel_id, text)


async def handle_direct_message(message: SlackDirectMessage) -> None:
    # 満足度のあとの返信は、振り返りのコメント（語彙に落として原文は捨てる。LLM には渡さない）
    captured = await get_retro().try_capture_comment(message.user_id, message.text)
    if captured:
        await slack.post_message(message.channel_id, captured)
        return
    thinking_ts = await _show_thinking(message.channel_id)
    try:
        # いま話しているイベントを、コードが伝える（利用者にイベントの ID を聞き返さない。SPEC 7.5）
        found = event_for_slack_user(get_event_store(), message.user_id)
        asked = with_context(message.text, *found) if found else message.text
        text = await kuroko_chat.reply(f"slack:{message.team_id}:{message.user_id}", asked)
    except Exception:
        # 再試行すると同じ質問に二重に答えかねないので、固定の文面を返して終える
        logger.exception("agent failed: event_id=%s", message.event_id)
        text = ""
    await _answer(message.channel_id, thinking_ts, text or FALLBACK_TEXT)
