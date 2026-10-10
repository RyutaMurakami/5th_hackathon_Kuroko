# Firestore（ARCHITECTURE 4.6）。業務状態の正は (default)。
# bank-adapter の口座の対応表は、専用の名前付きデータベース bank に分ける。
# Firestore の IAM はデータベース単位なので、IAM の条件でデータベースごとに分ける。

resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.enabled]
}

resource "google_firestore_database" "bank" {
  name        = "bank"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.enabled]
}

locals {
  firestore_access = {
    "sa-api"          = google_firestore_database.default.name
    "sa-payment-api"  = google_firestore_database.default.name
    "sa-bank-adapter" = google_firestore_database.bank.name
  }
}

resource "google_project_iam_member" "firestore_user" {
  for_each = local.firestore_access

  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.sa[each.key]}"

  condition {
    title      = "only-${replace(replace(each.value, "(", ""), ")", "")}-db"
    expression = "resource.name == \"projects/${var.project_id}/databases/${each.value}\""
  }
}

# Web（ブラウザ）から Firestore を直接触らせない。両方のデータベースで、クライアントの読み書きを拒否する
resource "google_firebaserules_ruleset" "firestore" {
  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../../firestore.rules")
    }
  }

  depends_on = [google_firestore_database.default]
}

resource "google_firebaserules_release" "firestore_default" {
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }
}

resource "google_firebaserules_release" "firestore_bank" {
  name         = "cloud.firestore/bank"
  ruleset_name = google_firebaserules_ruleset.firestore.name

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }

  depends_on = [google_firestore_database.bank]
}

# App Home の表示で、Slack ユーザーから参加者を探す（events/*/participants を横断する検索。TASKS B16）。
# コレクショングループのクエリには、単一フィールドのインデックス（コレクショングループ）が要る
resource "google_firestore_field" "participants_slack_user" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "participants"
  field      = "slack_user_id"

  index_config {
    indexes {
      order       = "ASCENDING"
      query_scope = "COLLECTION_GROUP"
    }
  }
}
