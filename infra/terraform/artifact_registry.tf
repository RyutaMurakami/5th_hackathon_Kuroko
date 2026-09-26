resource "google_artifact_registry_repository" "images" {
  repository_id = "kuroko"
  location      = var.region
  format        = "DOCKER"
  description   = "Cloud Run のイメージ（kuroko-gateway / kuroko-api は同じイメージ）"

  # 古いイメージを溜めない（イメージごとに新しい10個を残す）
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "604800s"
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}
