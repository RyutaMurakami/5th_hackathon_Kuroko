# GitHub Actions の Variables に登録する値（infra/terraform/README.md「Apply後の作業」）。
# どれも秘密ではない。

output "project_id" {
  value = var.project_id
}

output "project_number" {
  value = local.project_number
}

output "region" {
  value = var.region
}

output "workload_identity_provider" {
  description = "GitHub Variables: GCP_WORKLOAD_IDENTITY_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "GitHub Variables: GCP_DEPLOY_SERVICE_ACCOUNT"
  value       = google_service_account.deploy.email
}

output "artifact_registry_repository" {
  description = "GitHub Variables: GCP_ARTIFACT_REGISTRY（docker push 先）"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "service_urls" {
  value = { for k, v in google_cloud_run_v2_service.this : k => v.uri }
}

output "runtime_service_accounts" {
  value = local.sa
}

output "upload_bucket" {
  value = google_storage_bucket.uploads.name
}

output "claims_bucket" {
  value = google_storage_bucket.claims.name
}
