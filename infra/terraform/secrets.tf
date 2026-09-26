# Secret Manager の「入れ物」だけを作る。値は Terraform に入れない（state に平文で残るため）。
# 値は人間が `gcloud secrets versions add` で登録する（human_task P3、.agents/rules/infra.md）。

locals {
  # secret_id => { 読める SA, Cloud Run に渡すときの環境変数名 }
  secrets = {
    "slack-signing-secret" = { readers = ["sa-gateway"], env = "SLACK_SIGNING_SECRET" }
    "slack-bot-token"      = { readers = ["sa-api", "sa-payment-api"], env = "SLACK_BOT_TOKEN" }
    "ekispert-api-key"     = { readers = ["sa-api"], env = "EKISPERT_API_KEY" }
    "hotpepper-api-key"    = { readers = ["sa-api"], env = "HOTPEPPER_API_KEY" }
    "maps-api-key"         = { readers = ["sa-api"], env = "MAPS_API_KEY" }
    "sunabar-client"       = { readers = ["sa-bank-adapter"], env = "SUNABAR_CLIENT" }
    # 参加者・幹事のアクセストークン。bank-adapter が実行時に読み書きする（環境変数には渡さない）
    "sunabar-tokens" = { readers = ["sa-bank-adapter"], env = null }
  }

  secret_readers = merge([
    for id, s in local.secrets : { for r in s.readers : "${id}/${r}" => { secret = id, sa = r } }
  ]...)
}

resource "google_secret_manager_secret" "this" {
  for_each = local.secrets

  secret_id = each.key
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = local.secret_readers

  secret_id = google_secret_manager_secret.this[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.sa[each.value.sa]}"
}

# bank-adapter がトークンの新しい版を足し、破棄（redact_personal_data）する
resource "google_secret_manager_secret_iam_member" "bank_tokens_writer" {
  for_each = toset(["roles/secretmanager.secretVersionAdder", "roles/secretmanager.secretVersionManager"])

  secret_id = google_secret_manager_secret.this["sunabar-tokens"].id
  role      = each.value
  member    = "serviceAccount:${local.sa["sa-bank-adapter"]}"
}
