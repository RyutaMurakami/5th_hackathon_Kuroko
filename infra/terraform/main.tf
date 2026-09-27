# 共通の値。リソースはファイルごとに分けている（apis / service_accounts / iam_wif /
# firestore / storage / bigquery / kms / secrets / artifact_registry / tasks / cloud_run）。
# エージェント系（Agent Gateway・Agent Runtime・RAG Engine・Memory Bank。TASKS I7〜I9）は、
# 検証ゲート（O1〜O4）の結果を見てから追加する。

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.this.number

  # Cloud Run の URL は決まった形になるので、サービス同士の依存（循環）を作らずに参照できる
  service_names = ["kuroko-gateway", "kuroko-api", "payment-api", "bank-adapter", "kuroko-dashboard"]
  service_urls = {
    for name in local.service_names :
    name => "https://${name}-${local.project_number}.${var.region}.run.app"
  }
}
