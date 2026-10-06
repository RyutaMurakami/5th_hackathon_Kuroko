# serviceusage / cloudresourcemanager は、Terraform を回す前に有効になっている前提（human_task H8）

locals {
  apis = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudtasks.googleapis.com",
    "cloudscheduler.googleapis.com",
    "firestore.googleapis.com",
    "firebaserules.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "identitytoolkit.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    # Agent Gateway・Agent Registry・Model Armor（TASKS I7）。有効化だけでは課金されない
    "networkservices.googleapis.com",
    "agentregistry.googleapis.com",
    "modelarmor.googleapis.com",
    # Agent Gateway の前提 API（公式の Set up Agent Gateway。H11 手順書 3-2）。telemetry は Terraform 外で有効化済み
    "compute.googleapis.com",
    "networksecurity.googleapis.com",
    "iap.googleapis.com",
    "serviceextensions.googleapis.com",
    "observability.googleapis.com",
    "telemetry.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.apis)

  service            = each.value
  disable_on_destroy = false
}
