# 図（docs/diagrams）

| ファイル | 内容 |
|---|---|
| [KUROKO_GoogleCloud構成図_v3.0.drawio](KUROKO_GoogleCloud構成図_v3.0.drawio) | **いまの構成図**（2026-10-15 に作り直し。提出・README・スライド用。サービス名は日本語の呼び名にし、各箱の左にアイコンを差し込む余白を空けてある。Agent Gateway は入口と出口を分けて描く）。draw.io で開いて直す。書き出しは [export/…v2.0.svg](export/KUROKO_GoogleCloud構成図_v3.0.svg)・[PNG](export/KUROKO_GoogleCloud構成図_v3.0.png)。デモ動画のスライド用の図は [../demo/figures/](../demo/figures/) |
| [KUROKO_GoogleCloud構成図_v1.0.drawio](KUROKO_GoogleCloud構成図_v1.0.drawio) | **古い図**（2026-09-28 時点の構築状況。支払いエージェント・RAG Engine など、作らないと決めたものを含む）。経緯として残す |

構成と権限の正は [ARCHITECTURE.md](../ARCHITECTURE.md)。**下の「構築状況」の表は 2026-09-28 時点のもので、いまの状態は [HANDOVER.md](../HANDOVER.md) 4章を見る。**

## 構築状況（2026-09-28。B16a・F4・F14 のデプロイの後）

凡例は図と同じ。【稼働】デプロイ済みで動作を確認（仮を含む）／【TF】Terraform で構築済み ／【器のみ】Terraform で作成済みだが中身が未 ／【手動】Console で作成・設定済み（Terraform の管理外）／【未】未構築。

| 区分 | サービス | 状態 | 残り（TASKS / human_task） |
|---|---|---|---|
| Cloud Run | `kuroko-dashboard`（公開） | 稼働（Next.js・ダミーデータ・Google ログイン・開発者ページ `/dev`） | F3〜（API 接続）、F4 の役割の判定（P6・B14） |
| Cloud Run | `kuroko-gateway`（公開） | 稼働（Slack の署名検証・Ack・Cloud Tasks 投入。DM だけ） | B16（モーダル・App Home・interactivity） |
| Cloud Run | `kuroko-api`（非公開） | 稼働・仮（`/tasks/slack/message` と仮のエージェント。B16a） | B14・B21（`/mcp`）ほか、仮のエージェントを Agent Runtime に差し替え（B22・B23） |
| Cloud Run | `payment-api`（非公開） | 器のみ | E3、B9・B10、I11 |
| Cloud Run | `bank-adapter`（非公開） | 器のみ | E3、B10、I11 |
| 非同期 | Cloud Tasks（`kuroko-default` / `kuroko-mandates` / `kuroko-payments`） | TF（`kuroko-default` は Slack の DM で使用中） | — |
| 非同期 | Cloud Scheduler（5ジョブ） | 器のみ（一時停止中） | B17 の後に `scheduler_paused = false` |
| データ | Firestore `(default)` / `bank`、ルール（クライアント拒否） | TF | — |
| データ | Cloud Storage（`-uploads` / `-claims`） | TF | — |
| データ | BigQuery `kuroko_audit.decision_log` | TF | — |
| 鍵 | Cloud KMS（`kuroko-claims` / `kuroko-mandates`） | TF | 参加者ごとの鍵の持ち方は B9 |
| 鍵 | Secret Manager（6つ） | TF（Slack 2つ・駅すぱあと・Maps は値を登録し、`wired_secrets` で Cloud Run に注入） | `sunabar-client`（H22）。値を入れたら `wired_secrets` に足す |
| Firebase | Hosting（サイト `kuroko-509311`） | 稼働（サイトは手動、rewrite は CD でデプロイ） | — |
| Firebase | Authentication（Google のみ。匿名は使わない） | 手動（有効化済み） | — |
| Agent Platform | Agent Gateway ＋ Model Armor、Agent Registry | 未 | O2（G2）→ I7 |
| Agent Platform | Agent Runtime（`kuroko-agent` / `payment-agent` / `extract-agent`）と Agent identity | 未 | E4 → I8（P5） |
| Agent Platform | RAG Engine、Memory Bank | 未 | O3（G3）→ I9 |
| Agent Platform | Gemini（Vertex AI） | 稼働・仮（`kuroko-api` の仮のエージェントが `gemini-3.8-flash`（`global`）を利用） | 本来は Agent Runtime の統括エージェントから呼ぶ（B23） |
| デプロイ | WIF ＋ `sa-deploy`、Artifact Registry `kuroko` | 稼働（Variables 登録済み。`main` へのマージで CD） | エージェントのデプロイ（I8） |
| 権限 | 実行SA 7つと IAM（7章） | TF | Agent identity の IAM（I8） |
| 運用 | Cloud Logging / Monitoring | TF（API の有効化） | — |
| 運用 | アラート（5xx・遅延） | 未 | I12 |
| 運用 | 予算アラート（Billing） | 手動 | — |

## 開発者ページ（`/dev/diagrams`）用の SVG の書き出し

Web の開発者ページ（SPEC 7.3.2、ARCHITECTURE D26）は、`docs/diagrams/export/*.svg` を表示する。**`.drawio` を直したら、SVG を書き出し直してコミットする**（CI では書き出さない）。draw.io のデスクトップ版（`brew install --cask drawio`）の CLI を使う。

```
mkdir -p docs/diagrams/export
for f in docs/diagrams/*.drawio docs/user_flow/*.drawio; do
  drawio -x -f svg --embed-svg-images -o "docs/diagrams/export/$(basename "$f" .drawio).svg" "$f"
done
```

図の題名はファイル名（`KUROKO_` と `_v1.0` を除いたもの）から作る。1ファイル1ページを前提にしている（複数ページの図は、先頭のページだけが書き出される）。
