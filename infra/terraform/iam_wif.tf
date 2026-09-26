# Workload Identity Federation for GitHub Actions.
# デプロイ用サービスアカウントには最小権限のロールのみ付与する（.agents/rules/infra.md 参照）。
# Cloud Run の IAM（invoker・公開範囲）は Terraform が持つので、sa-deploy は run.admin ではなく
# run.developer にする（リビジョンは作れるが、IAM は変えられない）。
# エージェント（Agent Runtime）のデプロイに要るロールは TASKS I8 / I11 で足す。

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # このリポジトリの main ブランチからのデプロイだけを信頼する
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"refs/heads/main\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deploy" {
  account_id   = "sa-deploy"
  display_name = "sa-deploy"
  description  = "GitHub Actions からのデプロイ（WIF）。実行SAとは別"

  depends_on = [google_project_service.enabled]
}

resource "google_service_account_iam_member" "deploy_wif" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "deploy" {
  for_each = toset([
    "roles/run.developer",
    "roles/firebasehosting.admin",
    "roles/serviceusage.serviceUsageConsumer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Cloud Run のリビジョンを各実行SAで動かすため
resource "google_service_account_iam_member" "deploy_act_as_runtime" {
  for_each = toset(["sa-gateway", "sa-api", "sa-payment-api", "sa-bank-adapter", "sa-dashboard"])

  service_account_id = google_service_account.runtime[each.value].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
