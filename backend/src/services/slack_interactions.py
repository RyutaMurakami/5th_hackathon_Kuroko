"""kuroko-gateway: 署名検証済みのボタン操作から、後段に渡すタスクを決める（業務判断はしない）。

- 委任の同意・取り消しは、**`payment-api` に直接**タスクを投入する。署名・取り消しは、署名検証
  済みの Slack 操作だけがきっかけで、kuroko-api を経由しない（ARCHITECTURE 4.1）。
  ゲートウェイは DB を持たないので、署名に必要な値（上限・支払先・期限）は DM のボタンの値から
  取る。ボタンの値は Slack が署名するペイロードに入っていて、押した人は書き換えられない。
  **押した人が、値に入れた本人である**ことは、ここで確かめる。
- 出欠の記録・按分の承認・予算超過の確認は、`kuroko-api` に渡す（Firestore が要る）。
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

from src.models.slack import Action, SlackHomeOpened, SlackInteraction


@dataclass(frozen=True)
class Task:
    target: str  # "kuroko-api" / "payment-api"
    path: str
    payload: dict[str, Any]
    task_id: str


class InvalidInteraction(Exception):
    pass


def parse_form_payload(body: bytes) -> dict[str, Any]:
    """`application/x-www-form-urlencoded` の `payload=<JSON>`。"""
    try:
        raw = parse_qs(body.decode())["payload"][0]
        return json.loads(raw)
    except (KeyError, IndexError, ValueError):
        raise InvalidInteraction from None


def extract_interaction(payload: dict[str, Any]) -> SlackInteraction | None:
    """ボタン操作（block_actions）の最初の1つ。KUROKO のボタンでなければ None。"""
    if payload.get("type") != "block_actions":
        return None
    actions = payload.get("actions") or []
    if not actions:
        return None
    first = actions[0]
    try:
        action = Action(first.get("action_id", ""))
        value = json.loads(first.get("value") or "{}")
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    user = (payload.get("user") or {}).get("id")
    if not user:
        return None
    digest_source = f"{action.value}|{json.dumps(value, sort_keys=True)}|{user}"
    return SlackInteraction(
        interaction_id=hashlib.sha256(digest_source.encode()).hexdigest()[:32],
        action=action,
        team_id=(payload.get("team") or {}).get("id", ""),
        user_id=user,
        channel_id=(payload.get("channel") or {}).get("id"),
        message_ts=(payload.get("message") or {}).get("ts"),
        response_url=payload.get("response_url"),
        value=value,
    )


def extract_home_opened(payload: dict[str, Any]) -> SlackHomeOpened | None:
    event = payload.get("event") or {}
    if payload.get("type") != "event_callback" or event.get("type") != "app_home_opened":
        return None
    if event.get("tab") != "home" or not event.get("user"):
        return None
    return SlackHomeOpened(
        event_id=payload["event_id"],
        team_id=payload.get("team_id", ""),
        user_id=event["user"],
    )


def plan_tasks(i: SlackInteraction) -> list[Task]:
    """この操作で投入するタスク。本人でなければ何も投入しない（空）。"""
    v = i.value
    # DM を受け取った本人だけが押せる（値の `s` = 宛先の Slack ユーザー）
    if v.get("s") != i.user_id:
        return []
    tid = f"slack-{i.action.value}-{i.interaction_id}"
    to_api = Task("kuroko-api", "/tasks/slack/interaction", i.model_dump(mode="json"), tid)

    if i.action is Action.CONSENT:
        try:
            body = {
                "user_id": v["u"],
                "event_id": v["e"],
                "payee_user_id": v["p"],
                "cap_yen": int(v["c"]),
                "expires_at": v["x"],
                "signed_via": i.interaction_id,
            }
        except (KeyError, TypeError, ValueError):
            return []
        return [Task("payment-api", "/mandates", body, f"sign-{i.interaction_id}"), to_api]
    if i.action is Action.REVOKE:
        mandate_id = v.get("m")
        if not mandate_id:
            return []
        return [
            Task(
                "payment-api",
                f"/mandates/{mandate_id}/revoke",
                {},
                f"revoke-{i.interaction_id}",
            ),
            to_api,
        ]
    return [to_api]  # decline・approve・budget は kuroko-api が Firestore で検証して処理する
