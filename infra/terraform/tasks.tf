# 非同期の部品（ARCHITECTURE 6章・8章）。
# Cloud Tasks の OIDC 主体は「投入した側の SA」。投入の権限はキュー単位で付ける。

locals {
  queues = {
    # Slack の操作・後続タスク・リマインドなど。既定の再試行を使う
    "kuroko-default" = { max_attempts = 10, enqueuers = ["sa-gateway", "sa-api"] }
    # 委任状の署名・取り消し・銀行の認可（sa-gateway）、デモ用の代行（sa-api が sa-demo-runner で投入）
    "kuroko-mandates" = { max_attempts = 5, enqueuers = ["sa-gateway", "sa-api"] }
    # 支払い。再試行しない（二重の振込依頼を防ぐ。8章）
    "kuroko-payments" = { max_attempts = 1, enqueuers = ["sa-api", "sa-payment-api"] }
  }

  queue_enqueuers = merge([
    for q, v in local.queues : { for sa in v.enqueuers : "${q}/${sa}" => { queue = q, sa = sa } }
  ]...)
}

resource "google_cloud_tasks_queue" "this" {
  for_each = local.queues

  name     = each.key
  location = var.region

  retry_config {
    max_attempts = each.value.max_attempts
  }

  depends_on = [google_project_service.enabled]
}

resource "google_cloud_tasks_queue_iam_member" "enqueuer" {
  for_each = local.queue_enqueuers

  name     = google_cloud_tasks_queue.this[each.value.queue].name
  location = var.region
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${local.sa[each.value.sa]}"
}

# Cloud Scheduler（8章）。sa-scheduler は Cloud Run を呼ぶ権限だけを持つ。
# 開催前・確認待ちのリマインドは作らない（2026-10-12 ユーザー決定）。通しをしないあいだは scheduler_paused = true。
locals {
  scheduler_jobs = {
    "retrospective-requests" = {
      description = "振り返りの拾い直し（依頼は完了の直後に始まる）・リマインド・締切"
      schedule    = "0 10 * * *"
      service     = "kuroko-api"
      path        = "/tasks/scheduled/retrospectives"
    }
    "sandbox-cleanup" = {
      description = "ゲストの sandbox イベントを作成から7日で削除"
      schedule    = "0 4 * * *"
      service     = "kuroko-api"
      path        = "/tasks/scheduled/sandbox-cleanup"
    }
    "collection-poll" = {
      description = "幹事口座の入金の確認（支払いが完了したイベントだけ。SPEC 8.6）"
      schedule    = "* * * * *"
      service     = "kuroko-api"
      path        = "/tasks/scheduled/collections"
    }
    "payment-poll" = {
      description = "銀行での承認待ちの支払いのポーリング（sunabar に Webhook がないため）"
      schedule    = "* * * * *"
      service     = "payment-api"
      path        = "/tasks/internal/payments/poll"
    }
  }
}

resource "google_cloud_scheduler_job" "this" {
  for_each = local.scheduler_jobs

  name        = each.key
  description = each.value.description
  region      = var.region
  schedule    = each.value.schedule
  time_zone   = var.time_zone
  paused      = var.scheduler_paused

  http_target {
    http_method = "POST"
    uri         = "${local.service_urls[each.value.service]}${each.value.path}"

    oidc_token {
      service_account_email = local.sa["sa-scheduler"]
      audience              = local.service_urls[each.value.service]
    }
  }

  depends_on = [google_project_service.enabled]
}
