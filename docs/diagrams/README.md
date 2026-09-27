# 図（docs/diagrams）

| ファイル | 内容 |
|---|---|
| [KUROKO_GoogleCloud構成図_v1.0.drawio](KUROKO_GoogleCloud構成図_v1.0.drawio) | Google Cloud のサービス構成図（インフラ / L1）と、**Terraform での構築状況**（2026-09-26 時点）。draw.io（diagrams.net または VS Code の Draw.io Integration）で開く |

構成と権限の正は [ARCHITECTURE.md](../ARCHITECTURE.md)（2章・6章・7章・10章）。図は、その配置を「いま何ができているか」で色分けしたもの。構築が進んだら、図とこの表を一緒に更新する。

## 構築状況（2026-09-26。`terraform apply` 125件の後）

凡例は図と同じ。【TF】Terraform で構築済み ／【器のみ】Terraform で作成済みだが中身が未 ／【手動】Console で作成・設定済み（Terraform の管理外）／【未】未構築。

| 区分 | サービス | 状態 | 残り（TASKS / human_task） |
|---|---|---|---|
| Cloud Run | `kuroko-dashboard`（公開） | 器のみ（hello イメージ） | E6（Dockerfile）、F3〜、I11 のデプロイ |
| Cloud Run | `kuroko-gateway`（公開） | 器のみ | E2、B、I11 |
| Cloud Run | `kuroko-api`（非公開） | 器のみ | E2、B、I11 |
| Cloud Run | `payment-api`（非公開） | 器のみ | E3、B9・B10、I11 |
| Cloud Run | `bank-adapter`（非公開） | 器のみ | E3、B10、I11 |
| 非同期 | Cloud Tasks（`kuroko-default` / `kuroko-mandates` / `kuroko-payments`） | TF | — |
| 非同期 | Cloud Scheduler（5ジョブ） | 器のみ（一時停止中） | B17 の後に `scheduler_paused = false` |
| データ | Firestore `(default)` / `bank`、ルール（クライアント拒否） | TF | — |
| データ | Cloud Storage（`-uploads` / `-claims`） | TF | — |
| データ | BigQuery `kuroko_audit.decision_log` | TF | — |
| 鍵 | Cloud KMS（`kuroko-claims` / `kuroko-mandates`） | TF | 参加者ごとの鍵の持ち方は B9 |
| 鍵 | Secret Manager（7つ） | 器のみ（値が未登録） | P3 の後に `wire_secrets = true` |
| Firebase | Hosting（サイト `kuroko-509311`） | 手動 | rewrite のデプロイ（I6・I11） |
| Firebase | Authentication（Google・匿名） | 手動 | Console での有効化（H10） |
| Agent Platform | Agent Gateway ＋ Model Armor、Agent Registry | 未 | O2（G2）→ I7 |
| Agent Platform | Agent Runtime（`kuroko-agent` / `payment-agent` / `extract-agent`）と Agent identity | 未 | E4 → I8（P5） |
| Agent Platform | RAG Engine、Memory Bank | 未 | O3（G3）→ I9 |
| Agent Platform | Gemini（Vertex AI） | TF（API の有効化だけ） | — |
| デプロイ | WIF ＋ `sa-deploy`、Artifact Registry `kuroko` | TF | GitHub の Variables（P2） |
| 権限 | 実行SA 7つと IAM（7章） | TF | Agent identity の IAM（I8） |
| 運用 | Cloud Logging / Monitoring | TF（API の有効化） | — |
| 運用 | アラート（5xx・遅延） | 未 | I12 |
| 運用 | 予算アラート（Billing） | 手動 | — |
