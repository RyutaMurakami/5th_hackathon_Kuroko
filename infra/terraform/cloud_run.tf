# Cloud Run 5サービス（ARCHITECTURE 2.2・6章・7章）。
# イメージの更新は CD（.github/workflows/deploy.yml）が行うので、Terraform は無視する。
# 公開するのは kuroko-gateway（Slack から呼ばれる）と kuroko-dashboard（Firebase Hosting の後ろ）だけ。
# 同じサービス内のルートごとの絞り込みは、アプリ層の ID トークン検証で行う（6章）。

locals {
  common_env = {
    GOOGLE_CLOUD_PROJECT = var.project_id
    GOOGLE_CLOUD_REGION  = var.region
  }

  bigquery_env = {
    BQ_DATASET            = google_bigquery_dataset.audit.dataset_id
    BQ_DECISION_LOG_TABLE = google_bigquery_table.decision_log.table_id
  }

  services = {
    "kuroko-gateway" = {
      sa     = "sa-gateway"
      public = true
      max    = 5
      env = {
        APP_MODULE            = "src.gateway:app"
        KUROKO_API_URL        = local.service_urls["kuroko-api"]
        PAYMENT_API_URL       = local.service_urls["payment-api"]
        TASKS_QUEUE_DEFAULT   = "kuroko-default"
        TASKS_QUEUE_MANDATES  = "kuroko-mandates"
        TASKS_SERVICE_ACCOUNT = local.sa["sa-gateway"]
      }
      invokers = []
    }
    "kuroko-api" = {
      sa     = "sa-api"
      public = false
      max    = 5
      env = merge(local.bigquery_env, {
        APP_MODULE                  = "src.main:app"
        KUROKO_API_URL              = local.service_urls["kuroko-api"]
        PAYMENT_API_URL             = local.service_urls["payment-api"]
        BANK_ADAPTER_URL            = local.service_urls["bank-adapter"]
        FIRESTORE_DATABASE          = google_firestore_database.default.name
        TASKS_QUEUE_DEFAULT         = "kuroko-default"
        TASKS_QUEUE_MANDATES        = "kuroko-mandates"
        TASKS_QUEUE_PAYMENTS        = "kuroko-payments"
        TASKS_SERVICE_ACCOUNT       = local.sa["sa-api"]
        DEMO_RUNNER_SERVICE_ACCOUNT = local.sa["sa-demo-runner"]
        GATEWAY_SERVICE_ACCOUNT     = local.sa["sa-gateway"]
        DASHBOARD_SERVICE_ACCOUNT   = local.sa["sa-dashboard"]
        SCHEDULER_SERVICE_ACCOUNT   = local.sa["sa-scheduler"]
        UPLOAD_BUCKET               = google_storage_bucket.uploads.name
        CLAIMS_BUCKET               = google_storage_bucket.claims.name
        KMS_CLAIM_SIGNING_KEY       = google_kms_crypto_key.claim_signing.id
        # 請求（Checkout）の署名（ES256）に使う鍵バージョン（TASKS B13）
        KMS_CLAIM_KEY_VERSION = "${google_kms_crypto_key.claim_signing.id}/cryptoKeyVersions/1"
        # /tasks/internal/*（請求の作成・入金の確認）を受け付ける呼び出し元（自分自身）
        API_SERVICE_ACCOUNT = local.sa["sa-api"]
        KUROKO_AGENT_ENGINE = var.kuroko_agent_engine
        # /mcp（エージェント用のツール）を呼べる身元。空のあいだは全て拒否（TASKS B21）
        AGENT_KUROKO_PRINCIPAL = var.agent_kuroko_principal
      })
      invokers = ["sa-gateway", "sa-api", "sa-dashboard", "sa-scheduler", "sa-demo-runner"]
    }
    "payment-api" = {
      sa     = "sa-payment-api"
      public = false
      max    = 3
      env = merge(local.bigquery_env, {
        PAYMENT_API_URL             = local.service_urls["payment-api"]
        BANK_ADAPTER_URL            = local.service_urls["bank-adapter"]
        FIRESTORE_DATABASE          = google_firestore_database.default.name
        TASKS_QUEUE_PAYMENTS        = "kuroko-payments"
        TASKS_SERVICE_ACCOUNT       = local.sa["sa-payment-api"]
        GATEWAY_SERVICE_ACCOUNT     = local.sa["sa-gateway"]
        API_SERVICE_ACCOUNT         = local.sa["sa-api"]
        DEMO_RUNNER_SERVICE_ACCOUNT = local.sa["sa-demo-runner"]
        SCHEDULER_SERVICE_ACCOUNT   = local.sa["sa-scheduler"]
        KMS_MANDATE_KEY_RING        = google_kms_key_ring.mandates.id
        KMS_PAYMENT_AGENT_KEY       = google_kms_crypto_key.payment_agent_signing.id
        # ES256 の署名・公開鍵の取得に使う鍵バージョン（payment_api の既定は本番側 = KMS・Firestore・http）
        # 請求の署名を検証する公開鍵（kuroko-api の claim-signing。署名はできない）
        KMS_CLAIM_KEY_VERSION         = "${google_kms_crypto_key.claim_signing.id}/cryptoKeyVersions/1"
        KMS_PARTICIPANT_KEY_VERSION   = "${google_kms_crypto_key.participant_signing.id}/cryptoKeyVersions/1"
        KMS_PAYMENT_AGENT_KEY_VERSION = "${google_kms_crypto_key.payment_agent_signing.id}/cryptoKeyVersions/1"
        SIGNER_MODE                   = "kms"
        STORE_BACKEND                 = "firestore"
        BANK_MODE                     = "http"
      })
      invokers = ["sa-gateway", "sa-api", "sa-payment-api", "sa-scheduler", "sa-demo-runner"]
    }
    "bank-adapter" = {
      sa     = "sa-bank-adapter"
      public = false
      max    = 3
      env = merge(local.bigquery_env, {
        FIRESTORE_DATABASE          = google_firestore_database.bank.name
        BANK_MODE                   = "sunabar"
        STORE_BACKEND               = "firestore"
        BANK_ADAPTER_URL            = local.service_urls["bank-adapter"]
        SUNABAR_TOKENS_SECRET       = google_secret_manager_secret.this["sunabar-tokens"].id
        API_SERVICE_ACCOUNT         = local.sa["sa-api"]
        PAYMENT_API_SERVICE_ACCOUNT = local.sa["sa-payment-api"]
      })
      invokers = ["sa-api", "sa-payment-api"]
    }
    "kuroko-dashboard" = {
      sa     = "sa-dashboard"
      public = true
      max    = 5
      env = {
        KUROKO_API_URL = local.service_urls["kuroko-api"]
      }
      invokers = []
    }
  }

  # サービスごとに、環境変数で渡すシークレット（wired_secrets に並べたものだけ）
  service_secrets = {
    for name, svc in local.services : name => {
      for id, s in local.secrets : s.env => id
      if s.env != null && contains(s.readers, svc.sa) && contains(var.wired_secrets, id)
    }
  }

  service_invokers = merge(concat(
    [for name, svc in local.services : { for sa in svc.invokers : "${name}/${sa}" => { service = name, member = "serviceAccount:${local.sa[sa]}" } }],
    [{ for name, svc in local.services : "${name}/allUsers" => { service = name, member = "allUsers" } if svc.public }],
  )...)
}

resource "google_cloud_run_v2_service" "this" {
  for_each = local.services

  name                = each.key
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = local.sa[each.value.sa]

    scaling {
      min_instance_count = 0
      max_instance_count = each.value.max
    }

    containers {
      image = var.placeholder_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = merge(local.common_env, each.value.env)
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.service_secrets[each.key]
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [
    google_project_service.enabled,
    google_secret_manager_secret_iam_member.accessor,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = local.service_invokers

  name     = google_cloud_run_v2_service.this[each.value.service].name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value.member
}
