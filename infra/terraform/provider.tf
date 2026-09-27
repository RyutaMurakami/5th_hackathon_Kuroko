terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.4"
    }
  }

  # 複数人で apply するようになったら有効化する（.agents/rules/infra.md 参照）
  # backend "gcs" {
  #   bucket = ""
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region

  default_labels = {
    app        = "kuroko"
    managed_by = "terraform"
  }
}
