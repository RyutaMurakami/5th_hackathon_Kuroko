# 判断ログ（SPEC 3章 DecisionLogEntry、ARCHITECTURE D4・9章）。各 API が直接 insert する。

resource "google_bigquery_dataset" "audit" {
  dataset_id  = "kuroko_audit"
  location    = var.region
  description = "KUROKO の判断ログ"

  depends_on = [google_project_service.enabled]
}

resource "google_bigquery_table" "decision_log" {
  dataset_id  = google_bigquery_dataset.audit.dataset_id
  table_id    = "decision_log"
  description = "DecisionLogEntry（SPEC 3章）"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }
  clustering = ["event_id"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "actor", type = "STRING", mode = "REQUIRED", description = "kuroko / payment_agent / human / demo-runner" },
    { name = "action_type", type = "STRING", mode = "REQUIRED" },
    { name = "summary", type = "STRING", mode = "NULLABLE" },
    {
      name = "policy_ref", type = "RECORD", mode = "NULLABLE",
      fields = [
        { name = "policy_id", type = "STRING", mode = "NULLABLE" },
        { name = "version", type = "STRING", mode = "NULLABLE" },
        { name = "path", type = "STRING", mode = "NULLABLE" },
      ]
    },
    { name = "related_entity_ref", type = "STRING", mode = "NULLABLE" },
  ])
}

# 書き込み: sa-api・sa-payment-api・sa-bank-adapter。読み取り: sa-api（7章）
resource "google_bigquery_table_iam_member" "decision_log_writer" {
  for_each = toset(["sa-api", "sa-payment-api", "sa-bank-adapter"])

  dataset_id = google_bigquery_table.decision_log.dataset_id
  table_id   = google_bigquery_table.decision_log.table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${local.sa[each.value]}"
}
