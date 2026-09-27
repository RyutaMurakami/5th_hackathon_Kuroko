# Cloud Storage（ARCHITECTURE 4.6）。すべて非公開・均一なアクセス制御。
# 規程の文書（RAG のコーパスの元）のバケットは TASKS I9 で足す。

# 領収書・予約画面のアップロード。ブラウザが署名付き URL で直接 PUT する（CORS）。7日で削除
resource "google_storage_bucket" "uploads" {
  name                        = "${var.project_id}-uploads"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  cors {
    origin          = var.cors_allowed_origins
    method          = ["PUT", "GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled]
}

# 経費精算の PDF
resource "google_storage_bucket" "claims" {
  name                        = "${var.project_id}-claims"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.enabled]
}

resource "google_storage_bucket_iam_member" "api_object_admin" {
  for_each = {
    uploads = google_storage_bucket.uploads.name
    claims  = google_storage_bucket.claims.name
  }

  bucket = each.value
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.sa["sa-api"]}"
}
