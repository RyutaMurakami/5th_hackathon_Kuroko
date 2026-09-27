from fastapi import APIRouter, Depends

from src.models.schemas import SlackDirectMessage
from src.services.slack_conversation import handle_direct_message
from src.services.task_auth import require_gateway

router = APIRouter(prefix="/tasks")


@router.post("/slack/message", dependencies=[Depends(require_gateway)])
async def slack_message(message: SlackDirectMessage) -> dict[str, str]:
    await handle_direct_message(message)
    return {"status": "ok"}
