"""Cloud Tasks への投入（OIDC の主体は投入した側の SA。ARCHITECTURE 6章・7章）。"""

import json
import logging
from functools import lru_cache

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _client() -> tasks_v2.CloudTasksAsyncClient:
    return tasks_v2.CloudTasksAsyncClient()


async def enqueue_kuroko_api(path: str, payload: dict, task_id: str) -> None:
    """kuroko-api の `path` を呼ぶタスクを積む。

    `task_id` が同じタスクは Cloud Tasks が重複として弾くので、
    Slack の再送が来ても1回しか処理しない。
    """
    s = get_settings()
    parent = _client().queue_path(
        s.google_cloud_project, s.google_cloud_region, s.tasks_queue_default
    )
    task = tasks_v2.Task(
        name=f"{parent}/tasks/{task_id}",
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{s.kuroko_api_url}{path}",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode(),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=s.tasks_service_account,
                audience=s.kuroko_api_url,
            ),
        ),
    )
    try:
        await _client().create_task(parent=parent, task=task)
    except AlreadyExists:
        logger.info("task already enqueued: %s", task_id)
