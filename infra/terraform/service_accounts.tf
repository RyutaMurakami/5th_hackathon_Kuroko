# 実行SA（ARCHITECTURE 7章）。owner / editor は使わない。
# リソース単位で付けられる権限は、各リソースのファイル（firestore / storage / bigquery / kms /
# secrets / tasks / cloud_run）に書き、ここにはプロジェクト単位でしか付けられないものだけを置く。
# Agent identity（agent-kuroko / agent-payment / agent-extract）の IAM は TASKS I8 で足す。

locals {
  runtime_service_accounts = {
    "sa-gateway"      = "kuroko-gateway（Slack の窓口。署名検証・Ack・Cloud Tasks への投入）"
    "sa-api"          = "kuroko-api（後段。業務コード・MCP・エージェントの呼び出し）"
    "sa-payment-api"  = "payment-api（委任状・支払い）"
    "sa-bank-adapter" = "bank-adapter（sunabar への窓口）"
    "sa-dashboard"    = "kuroko-dashboard（Web）"
    "sa-demo-runner"  = "デモ用の代行（sandbox のイベントだけ。Cloud Tasks の OIDC 主体としてだけ使う）"
    "sa-scheduler"    = "Cloud Scheduler（Cloud Run を呼ぶ権限だけ）"
    "sa-agent-mcp"    = "agent-kuroko が kuroko-api の /mcp を呼ぶための身元（Agent identity だけが偽装して ID トークンを作る）"
  }
}

resource "google_service_account" "runtime" {
  for_each = local.runtime_service_accounts

  account_id   = each.key
  display_name = each.key
  description  = each.value

  depends_on = [google_project_service.enabled]
}

locals {
  sa = { for k, v in google_service_account.runtime : k => v.email }
}

# Cloud Tasks の OIDC 主体を「投入した側の SA」にするため、自分自身として動く権限を付ける（7章）
resource "google_service_account_iam_member" "self_act_as" {
  for_each = toset(["sa-gateway", "sa-api", "sa-payment-api"])

  service_account_id = google_service_account.runtime[each.value].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.sa[each.value]}"
}

# sa-api が sa-demo-runner を OIDC 主体にしてタスクを投入する（D23）
resource "google_service_account_iam_member" "api_act_as_demo_runner" {
  service_account_id = google_service_account.runtime["sa-demo-runner"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.sa["sa-api"]}"
}

# 署名付き URL（アップロード）を鍵なしで作るため、sa-api が自分の署名（signBlob）を使う
resource "google_service_account_iam_member" "api_sign_blob" {
  service_account_id = google_service_account.runtime["sa-api"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.sa["sa-api"]}"
}

# Gemini の呼び出しと Agent Runtime の呼び出し（7章）。Vertex AI はリソース単位で絞れない
resource "google_project_iam_member" "aiplatform_user" {
  for_each = toset(["sa-api", "sa-payment-api"])

  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${local.sa[each.value]}"
}

# 判断ログを読むクエリの実行（sa-api だけ。書き込みはテーブル単位の権限で足りる）
resource "google_project_iam_member" "api_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${local.sa["sa-api"]}"
}

# agent-kuroko（Agent identity）だけが、sa-agent-mcp を偽装して ID トークンを作れる。
# kuroko-api は、この SA のメールだけを /mcp に通す（AGENT_KUROKO_PRINCIPAL）。
# 空のあいだは、だれも偽装できない（/mcp は呼べない）。
resource "google_service_account_iam_member" "agent_kuroko_impersonates_mcp" {
  count = var.kuroko_agent_identity == "" ? 0 : 1

  service_account_id = google_service_account.runtime["sa-agent-mcp"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.kuroko_agent_identity
}
