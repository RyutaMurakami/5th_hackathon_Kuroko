variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "Default region（ARCHITECTURE D5。Agent Gateway の入口はエージェントと同一リージョンが必須）"
  default     = "us-central1"
}

variable "github_repository" {
  type        = string
  description = "Workload Identity Federation で信頼する GitHub リポジトリ（owner/name）"
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "アップロード用バケットに署名付き URL で PUT してよいオリジン（Firebase Hosting のドメインと、ローカル開発）"
  default     = ["http://localhost:3000"]
}

variable "placeholder_image" {
  type        = string
  description = "Cloud Run の初回作成用イメージ。以後のイメージ更新は CD が行い、Terraform は無視する"
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "wire_secrets" {
  type        = bool
  description = "Secret Manager の値を Cloud Run の環境変数に渡すか。値の登録（human_task P3）が済むまで false にする（値のないシークレットを参照するとリビジョンが起動しない）"
  default     = false
}

variable "scheduler_paused" {
  type        = bool
  description = "Cloud Scheduler のジョブを止めておくか。呼び先のルート（TASKS B17）ができるまで true にする"
  default     = true
}

variable "time_zone" {
  type        = string
  description = "Cloud Scheduler のタイムゾーン"
  default     = "Asia/Tokyo"
}
