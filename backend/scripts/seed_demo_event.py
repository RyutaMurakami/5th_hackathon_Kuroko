"""デモ用のイベント「株式会社Akakura」の歓送迎会を Firestore に作る（TASKS B30・O7）。

`kuroko-api` の Slack の流れ（出欠の依頼 → 按分の承認 → 請求 → 銀行での承認 → 入金の確認）を
実機で通すための下準備。**架空の人物だけ**を入れ、口座番号・トークンは入れない。

使い方（リポジトリの `backend/` で）:
  uv run python scripts/seed_demo_event.py slack_users.local.json \
      [--event-id demo-1] [--date 2026-10-09]

`slack_users.local.json`（コミット禁止。`*.local.json`）: 登場人物の user_id → Slack ユーザーID。
Slack に実在する2人（`kurao`・`hanako`）だけを書く（SPEC 7.6）。書かなかった人には DM を送らない
（このスクリプトで作るイベントは sandbox ではないので、その人の出欠・委任は代行されない）。
  {"kurao": "U0123", "hanako": "U0456"}
"""

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta, timezone

from src.config import get_settings
from src.db.events import FirestoreEventStore
from src.models.event import Receipt
from src.seed.sample_company import demo_event, demo_participants
from src.services.policy import load_snapshot

JST = timezone(timedelta(hours=9))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slack_map", help="登場人物の user_id → Slack ユーザーID の JSON")
    ap.add_argument("--event-id", default="demo-1")
    ap.add_argument("--date", default=date.today().isoformat(), help="開催日（既定: 今日）")
    ap.add_argument("--total", type=int, default=60_300, help="会計金額（円）")
    ap.add_argument("--web-uid", default="demo-organizer-uid", help="幹事の Firebase の UID")
    args = ap.parse_args()

    mapping = json.load(open(args.slack_map, encoding="utf-8"))
    people = demo_participants()
    unknown = sorted(set(mapping) - {p.user_id for p in people})
    if unknown:
        raise SystemExit(f"名簿に無い登場人物: {unknown}")

    s = get_settings()
    store = FirestoreEventStore(project=s.google_cloud_project, database=s.firestore_database_id)
    held = datetime.combine(date.fromisoformat(args.date), time(19, 0), tzinfo=JST)
    event = demo_event(args.total).model_copy(
        update={
            "event_id": args.event_id,
            "title": "第一開発チーム 歓送迎会（デモ）",
            "datetime": held,
            "organizer_web_uid": args.web_uid,
            "policy_snapshot": load_snapshot(),
            "policy_id": load_snapshot().policy_id,
            "policy_version": load_snapshot().version,
        }
    )
    store.save_event(event)
    for p in people:
        store.save_participant(
            event.event_id,
            p.model_copy(
                update={"slack_user_id": mapping.get(p.user_id), "attendance_confirmed": True}
            ),
        )
    store.save_receipt(
        Receipt(
            event_id=event.event_id,
            total_amount_yen=args.total,
            source="manual",
            confirmed_by=args.web_uid,
            confirmed_at=datetime.now(UTC),
        )
    )
    print(
        f"イベント {event.event_id}（{held:%Y-%m-%d %H:%M} JST）に、{len(people)}名を登録しました。"
    )


if __name__ == "__main__":
    main()
