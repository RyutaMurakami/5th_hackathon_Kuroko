# Infra (Terraform)

シングル環境（dev/stg/prodを分けない）でGCPリソースを管理する。方針は `.agents/rules/infra.md` を参照。
構成と権限の正は `docs/ARCHITECTURE.md`（2章・4.6・6章・7章・10章）。リージョンは `us-central1`（D5）。

## 管理しているもの

| ファイル | 中身 |
|---|---|
| `apis.tf` | API の有効化 |
| `service_accounts.tf` | 実行SA 7つ（`sa-gateway` `sa-api` `sa-payment-api` `sa-bank-adapter` `sa-dashboard` `sa-demo-runner` `sa-scheduler`）と、プロジェクト単位でしか付けられない権限 |
| `iam_wif.tf` | GitHub Actions 用の Workload Identity Federation と `sa-deploy`（main ブランチだけを信頼） |
| `firestore.tf` | Firestore `(default)` と `bank`（`bank-adapter` 専用）、データベースごとの IAM、クライアントからの読み書きを拒否するルール（`/firestore.rules`） |
| `storage.tf` | アップロード用（CORS・7日で削除）と経費精算 PDF 用のバケット |
| `bigquery.tf` | 判断ログ `kuroko_audit.decision_log`（日付パーティション） |
| `kms.tf` | 署名鍵（請求: `kuroko-claims`、委任状・支払いエージェント: `kuroko-mandates`） |
| `secrets.tf` | Secret Manager の**入れ物だけ**（値は下の手順で人間が入れる） |
| `artifact_registry.tf` | イメージの置き場 `kuroko` |
| `tasks.tf` | Cloud Tasks のキュー3つ（支払いは再試行なし）と Cloud Scheduler 5ジョブ |
| `cloud_run.tf` | Cloud Run 5サービスと invoker（公開は `kuroko-gateway` `kuroko-dashboard` だけ） |

まだ無いもの（検証ゲートの結果を見て足す）: Agent Gateway・Agent Registry・Model Armor（TASKS I7）、Agent Runtime と Agent identity の IAM（I8）、RAG Engine・Memory Bank（I9）、監視とアラート（I12）。

## Usage

```
cp terraform.tfvars.example terraform.tfvars   # 値を埋める（コミットしない）
terraform init
terraform plan -out=kuroko.tfplan
terraform apply kuroko.tfplan                  # 承認が要る（human_task P1）
```

- Cloud Run は、最初は `var.placeholder_image`（Google の hello）で作る。以後のイメージ更新は CD（`.github/workflows/deploy.yml`）が行い、Terraform は無視する（`ignore_changes`）。
- `wire_secrets = false` のあいだは、Cloud Run にシークレットを渡さない。値のないシークレットを参照すると、リビジョンが起動しないため。値を登録したら `true` にして apply する。
- `scheduler_paused = true` のあいだは、Cloud Scheduler のジョブが止まっている。呼び先のルート（TASKS B17）ができたら `false` にする。
- KMS のキーリングと鍵は削除できない（`terraform destroy` しても GCP に残る）。

## Apply後の作業（人間）

### 1. GitHub の Variables に登録する（human_task P2）

リポジトリの Settings → Secrets and variables → Actions → **Variables**。どれも秘密ではない。

| Variable | 値 |
|---|---|
| `GCP_PROJECT_ID` | `terraform output -raw project_id` |
| `GCP_REGION` | `terraform output -raw region` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `terraform output -raw workload_identity_provider` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `terraform output -raw deploy_service_account` |
| `GCP_ARTIFACT_REGISTRY` | `terraform output -raw artifact_registry_repository` |
| `NEXT_PUBLIC_FIREBASE_*`（6つ） | Firebase Console の Web アプリの `firebaseConfig`（`frontend/lib/firebase.ts` の項目） |

`GCP_WORKLOAD_IDENTITY_PROVIDER` が未登録のあいだは、デプロイのワークフローは動かない。

`gh` CLI で登録する場合（リポジトリのルートで実行。値は画面に出さずにそのまま渡す）:

```
cd infra/terraform
gh variable set GCP_PROJECT_ID --body "$(terraform output -raw project_id)"
gh variable set GCP_REGION --body "$(terraform output -raw region)"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$(terraform output -raw workload_identity_provider)"
gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --body "$(terraform output -raw deploy_service_account)"
gh variable set GCP_ARTIFACT_REGISTRY --body "$(terraform output -raw artifact_registry_repository)"
cd ../..
# Firebase の設定値（frontend/.env.local と同じ値）を NEXT_PUBLIC_* の Variables に入れる
grep '^NEXT_PUBLIC_FIREBASE_' frontend/.env.local | grep -v EMULATOR | while IFS='=' read -r k v; do gh variable set "$k" --body "$v"; done
gh variable list
```

### 2. Secret Manager に値を入れる（human_task P3）

値はチャットに貼らない。手元のターミナルで、標準入力から入れる。

```
printf '%s' '<値>' | gcloud secrets versions add slack-signing-secret --data-file=- --project=<project_id>
```

入れ物: `slack-signing-secret` `slack-bot-token` `ekispert-api-key` `maps-api-key` `sunabar-client`（`sunabar-tokens` は `bank-adapter` が実行時に書くので、人間は入れない。**`hotpepper-api-key` は2026-09-27に不採用で削除済み**）。
値を入れたシークレットから順に、`terraform.tfvars` の `wired_secrets` に並べて apply する（値のないシークレットを並べると、そのサービスのリビジョンが起動しない）。

### 3. Firebase Authentication のプロバイダ（human_task H10。Terraform では管理しない）

Firebase Console → Authentication → Sign-in method で、**Google** を有効にする（**匿名は使わない。2026-09-27決定**。許可リストに載っていない Google アカウントはゲストとして扱う）。
承認済みドメインに `<project_id>.web.app` と `<project_id>.firebaseapp.com` があることを確認する。

### 4. Firebase Hosting

`firebase.json`（リポジトリ直下）の rewrite で、すべてのパスを `kuroko-dashboard`（`us-central1`）に向ける。
デプロイは CD が行う（`firebase deploy --only hosting`）。Firestore のルールは Terraform が持つので、`firebase deploy` で `firestore` を含めない。
