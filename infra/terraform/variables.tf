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

variable "wired_secrets" {
  type        = set(string)
  description = "Cloud Run の環境変数に渡すシークレット（secrets.tf の secret_id）。値の登録（human_task P3）が済んだものだけを並べる（値のないシークレットを参照するとリビジョンが起動しない）"
  default     = []
}

variable "kuroko_agent_engine" {
  type        = string
  description = "統括エージェント（kuroko-agent）の Agent Runtime のエンジン名（projects/<番号>/locations/<リージョン>/reasoningEngines/<ID>）。ユーザーがデプロイしたあとに設定する（human_task H11・TASKS B22）。空のあいだ、kuroko-api は仮のエージェントで返す"
  default     = ""
}

variable "agent_kuroko_principal" {
  type        = string
  description = "kuroko-api の /mcp を呼べる agent-kuroko の身元（Agent Gateway 経由の ID トークンの email か sub）。デプロイ後の V1 の確認で決める（TASKS B21）。空のあいだ、/mcp はすべて拒否する"
  default     = ""
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
