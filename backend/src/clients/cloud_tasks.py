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


async def enqueue_payment_api(
    path: str, payload: dict, task_id: str, *, as_service_account: str | None = None
) -> None:
    """payment-api の `path` を呼ぶタスクを積む（委任状の署名・取り消し。主体は sa-gateway）。

    `as_service_account` は、デモ用の代行（sa-demo-runner）を主体にするときだけ渡す。
    """
    s = get_settings()
    parent = _client().queue_path(
        s.google_cloud_project, s.google_cloud_region, s.tasks_queue_mandates
    )
    task = tasks_v2.Task(
        name=f"{parent}/tasks/{task_id}",
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{s.payment_api_url}{path}",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode(),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=as_service_account or s.tasks_service_account,
                audience=s.payment_api_url,
            ),
        ),
    )
    try:
        await _client().create_task(parent=parent, task=task)
    except AlreadyExists:
        logger.info("task already enqueued: %s", task_id)


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


async def enqueue_demo_mandate(path: str, payload: dict, task_id: str) -> None:
    """デモ用の代行で、委任状の署名を `payment-api` に依頼する（主体は sa-demo-runner。SPEC 7.6）。

    主体が設定されていなければ何もしない（sa-api の身元では、委任状に署名させない）。
    """
    runner = get_settings().demo_runner_service_account
    if not runner:
        logger.warning("demo runner is not configured; proxy mandate skipped")
        return
    await enqueue_payment_api(path, payload, task_id, as_service_account=runner)
