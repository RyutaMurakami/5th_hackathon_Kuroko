"""デモの通しの各ステップを、kuroko-api の内部タスクとして起動する（TASKS B30・O7）。

kuroko-api の `/tasks/internal/*` は kuroko-api 自身（sa-api）だけが受け付けるので、Cloud Tasks に
「sa-api の身元で」タスクを積む（積める人は、sa-api を使う権限を持つ人＝プロジェクトの Owner）。

使い方（`backend/` で）:
  uv run python scripts/run_step.py rsvp       demo-1   # 出欠＋委任の依頼を、参加者の DM に送る
  uv run python scripts/run_step.py approval   demo-1   # 按分を計算し、承認者に承認依頼を送る
  uv run python scripts/run_step.py budget     demo-1   # 予算超過の最終確認を、承認者に送る
  uv run python scripts/run_step.py checkouts  demo-1   # （承認のあと自動で走る）請求を作る
  uv run python scripts/run_step.py collections demo-1  # 幹事口座の入金を確認する
"""

import json
import sys
import time

from google.cloud import tasks_v2

PROJECT, REGION = "kuroko-509311", "us-central1"
API_URL = "https://kuroko-api-1054683553459.us-central1.run.app"
SA = f"sa-api@{PROJECT}.iam.gserviceaccount.com"
PATHS = {
    "rsvp": "/tasks/internal/rsvp-requests",
    "approval": "/tasks/internal/approval-requests",
    "budget": "/tasks/internal/budget-requests",
    "checkouts": "/tasks/internal/checkouts",
    "collections": "/tasks/internal/collections",
}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in PATHS:
        raise SystemExit(__doc__)
    step, event_id = sys.argv[1:]
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT, REGION, "kuroko-default")
    task = tasks_v2.Task(
        # 名前を毎回変えて、同じステップを何度でも起動できる（本番の処理は冪等キーで守られている）
        name=f"{parent}/tasks/manual-{step}-{event_id}-{int(time.time())}",
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{API_URL}{PATHS[step]}",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"event_id": event_id}).encode(),
            oidc_token=tasks_v2.OidcToken(service_account_email=SA, audience=API_URL),
        ),
    )
    created = client.create_task(parent=parent, task=task)
    name = created.name.split("/")[-1]
    print(f"{step}: タスクを積みました（{name}）。結果は kuroko-api のログで見ます。")


if __name__ == "__main__":
    main()
