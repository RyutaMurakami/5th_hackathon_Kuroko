# Agent Platform: あなたがやること（学びながら進めるチェックリスト）

> エージェントへ: 本書は、Agent Platform（Agent Gateway・Agent Registry・Model Armor・Agent Runtime・Memory Bank・RAG Engine）のうち、**ユーザーが学びながら自分の手で行う作業だけ**を、順番に並べたチェックリスト（2026-10-01 ユーザー指定）。画面の入力値などの詳しい手順は各手順書に置き、本書には「何を・どの順で・終わったら AI に何を返すか」だけを書く。ユーザーが項目を終えたら、AI はチェックを付け、[human_task.md](../human_task.md) の該当項目にも結果を書く。

- 作成日: 2026-10-01
- 対象プロジェクト: `kuroko-509311`／リージョン: `us-central1`
- **進め方**: 上から順に進める。「待ち」と書いた項目は、AI の準備ができたら AI から声をかける。それまでは先の項目に進んでよい
- **AI に返すのは、リソース名・エンジンID など秘密でない値だけ**。キーやトークンは貼らない

## 0. 最初に: Slack で本物のエージェントと話す（Gateway なしの先行デプロイ。2026-10-06 追加）

Gateway・Registry の設定（下の 1〜6）を待たず、`kuroko-agent` だけを先に Agent Runtime へ置き、Slack の DM の返答を本物のエージェントに切り替える。Gateway と Agent identity は、あとで付け足す（付けるときは、エージェントを作り直す。Gateway とリビジョンは併用できないため）。

- [x] **0-1. 認証を確かめる**（⌨）— `gcloud auth application-default login` 済みで、`gcloud config get-value project` が `kuroko-509311`
- [x] **0-2. `kuroko-agent` をデプロイする**（⌨。5〜10分。**2026-10-06 完了**。エンジン: `projects/1054683553459/locations/us-central1/reasoningEngines/2398800395150295040`）

  ```bash
  cd kuroko_agent
  agents-cli deploy --service-name kuroko-agent --min-instances 0 \
    --project kuroko-509311 --region us-central1 --no-confirm-project
  ```

  - `--min-instances 0`: 使っていないときの課金を避ける（最初の1回は起動に数十秒かかる）
  - 終わると `kuroko_agent/deployment_metadata.json` ができ、`remote_agent_runtime_id` にエンジンの名前（`projects/<番号>/locations/us-central1/reasoningEngines/<ID>`）が入る
  - タイムアウトしたら `agents-cli deploy --status` で進み具合を見る（サーバー側では続いている）
  - **学ぶこと**: Dockerfile からイメージが作られ、Agent Runtime に載る流れ。`agents-cli deploy --dry-run` で、何が実行されるかを事前に見られる

- [x] **0-3. 単体で動くことを確かめる**（⌨）— 次のコマンドで、日本語の返答が返ること

  ```bash
  agents-cli run --url https://us-central1-aiplatform.googleapis.com/v1/<0-2 のエンジンの名前> --mode adk "10/30に営業1課で歓迎会をやりたい"
  ```

- [x] **0-4. AI に、エンジンの名前（`remote_agent_runtime_id` の値）を伝える**（秘密ではない）
  - AI が `kuroko-api` の環境変数に渡し（`terraform apply`。承認が要る）、バックエンドのコード（B22）をデプロイ（P5。PR → マージ → CD）する
- [ ] **0-5. Slack で KUROKO に DM して、返答が来ることを確かめる**
  - 返答の文体が、これまでの仮のエージェントと変わっていれば、本物のエージェントにつながっている（`kuroko-api` のログにも出る）

## 全体の流れ

```
[1 準備] → [2 Model Armor] → [3 Gateway 2つ] → (待ち: AI の /mcp) → [4 Registry 登録]
                                            → (待ち: AI のエージェント) → [5 デプロイ] → [6 確かめる]
[7 Memory Bank] [8 RAG コーパス] … 1〜6 と並行してよい
[9 payment 側を足す] … AI の payment-api /mcp と payment_agent ができてから
```

## 1. 準備

- [ ] **1-1. gcloud を最新にする**（⌨）— [H11 手順書](h11_agent_platform_lab.md) の 3-1
  - 確認: `gcloud network-services agent-gateways --help` と `gcloud agent-registry --help` がエラーにならない
- [x] **1-2. 不足 API の有効化を承認する**（2026-10-01 完了。AI が apply、6件追加）（AI が `terraform apply -target=google_project_service.enabled` を実行。`compute` `networksecurity` `iap` `serviceextensions` `observability` `telemetry`）
  - 有効にするだけでは課金されない
  - **学ぶこと**: Agent Gateway は、裏で Compute（ロードバランサ）・Network Security・IAP（出口の認可）・Service Extensions（Model Armor の呼び出し）の仕組みを使っている

## 2. Model Armor のテンプレート（🖱 Console）

- [ ] **2-1. `kuroko-ma-request`（要求用）を作る** — [H11 手順書](h11_agent_platform_lab.md) の 4-1
- [ ] **2-2. `kuroko-ma-response`（応答用）を作る** — 同上
  - 要点: リージョン `us-central1`、多言語 **オン**、**INSPECT_ONLY**（検査のみ）
  - **学ぶこと**: どのフィルタ（プロンプトインジェクション・機微情報・悪意のある URL・有害内容）が、どの強さで効くか。要求と応答で分ける理由
  - AI に返すもの: なし（名前が決まっているので）

## 3. Agent Gateway（🖱 Console。1-2 のあと）

- [ ] **3-1. 入口 `kuroko-agw-c2a`（Client-to-Agent）を作る** — [H11 手順書](h11_agent_platform_lab.md) の 4-3
- [ ] **3-2. 出口 `kuroko-agw-a2a`（Agent-to-Anywhere。Audit-only）を作る** — [H11 手順書](h11_agent_platform_lab.md) の 4-4
  - レジストリを選べず作れなかったら、4（Registry 登録）のあとに回す
  - AI に返すもの: **2つの Gateway のリソース名**（`projects/kuroko-509311/locations/us-central1/agentGateways/...`）
  - **学ぶこと**: 入口と出口の違い。「既定は拒否」と Audit-only / Enforce の違い

## 4. Agent Registry に MCP を登録する（🖱 Console。**待ち: AI が `kuroko-api` の `/mcp` をデプロイしてから**）

- [ ] **4-1. `kuroko-api-mcp` を登録する** — [H11 手順書](h11_agent_platform_lab.md) の 4-2
  - AI からもらうもの: `/mcp` の URL（`https://kuroko-api-…run.app/mcp/`。**末尾の `/` つき**）と、**`backend/mcp_toolspec.json`**（ツールは `get_event_summary`・`check_budget`・`search_venues` の3つ。2026-10-09 に AI が用意済み。ツールが増えたら AI が再生成する）
  - AI に返すもの: **登録したリソース名**（`.../mcpServers/...`）
  - ツールが増えたら、AI が新しい `toolspec.json` を渡すので更新する
  - **学ぶこと**: 「エージェントが話しかけてよい相手の名簿」。非公開の MCP を toolspec で登録する理由

## 5. エージェントのデプロイ（⌨ コマンド。**待ち: AI が `kuroko_agent`・`extract_agent` とデプロイスクリプトを用意してから**）

- [ ] **5-1. `kuroko-agent` をデプロイし直す（`/mcp` のツールを使えるようにする）** — [H11 手順書](h11_agent_platform_lab.md) の 5-1
  - **`/mcp` を使うときは、環境変数 `KUROKO_MCP_URL`（`https://kuroko-api-…run.app/mcp/`）を付けてデプロイする**（`agents-cli deploy ... --update-env-vars KUROKO_MCP_URL=<URL>`）。付けなければ、これまでどおりツールなしで動く
  - **Gateway の出口を通すとき**: Registry に `kuroko-api-mcp` を登録し（4-1）、`kuroko-agent` の Agent identity に `roles/iap.egressor`（AI が付ける。6章）を与えてから確認する。**`/mcp` が agent-kuroko の身元を見分けられるか（V1）は、デプロイ後に AI が確かめ、結果を `AGENT_KUROKO_PRINCIPAL`（Terraform の変数 `agent_kuroko_principal`）に設定する**。それまで `/mcp` は全て拒否する（安全側）
- [ ] **5-2. `extract-agent` をデプロイする** — 同上
- [ ] **5-3. Console の Deployments で2つの Identity が別であることを確認する**（V2）
  - AI に返すもの: **2つのエンジンID**（末尾の数字）
  - **学ぶこと**: Agent identity（SA ではない principal）。`agent_gateway_config` と `identity_type` の関係。デプロイスクリプトの中身を読んでから実行する

## 6. 確かめる（🖱 Console。AI の検証スクリプトと一緒に）

- [ ] **6-1. Playground で `kuroko-agent` に話しかける** — [H11 手順書](h11_agent_platform_lab.md) の 7-1
- [ ] **6-2. 出口を Enforce policies に切り替える**（AI の合図で）— [H11 手順書](h11_agent_platform_lab.md) の 7-3
- [ ] **6-3. Logs Explorer で Model Armor の検知を見る**（AI が検索条件を渡す）— [H11 手順書](h11_agent_platform_lab.md) の 7-5
- [ ] **6-4. P9: 検知結果の合否と、INSPECT_ONLY からブロックへの切り替えを判断する**
  - **学ぶこと**: 日本語の攻撃文がどこで止まり、どこで素通りするか。多層防御（Gateway・隔離抽出・値の検証）の役割分担

## 7. Memory Bank（🖱 Console。1〜6 と並行してよい。H26）

- [ ] **7-1. AI の手順書を受け取る**（**未作成。AI が用意する**。リージョン・TTL 365日などの設定値つき）
- [ ] **7-2. Console で Memory Bank を作る**
  - AI に返すもの: **作成したリソース名**
- [ ] **7-3. H27: 記憶の seed（過去のイベント3件程度）の内容を確認する**（AI が下書きを出す）
  - **学ぶこと**: 記憶のスコープ（`user_id`）と、読み取り専用のロール（`memoryViewer`）で書き込みを防ぐ設計

## 8. RAG Engine のコーパス（🖱 Console。並行してよい。H24・H30）

- [ ] **8-1. H24: 規程の PDF の内容を確認する**（AI が `company_rules.yaml` から下書きを作る）
- [ ] **8-2. AI の手順書を受け取る**（**未作成。AI が用意する**。リージョン・埋め込みモデルなどの設定値つき）
- [ ] **8-3. Console でコーパスを作り、規程の PDF を取り込む**
  - AI に返すもの: **コーパスのリソース名**
  - **学ぶこと**: 取り込み（チャンク分割・埋め込み）と `retrieveContexts`。抽出した値をコードで検証する理由

## 9. 支払い側を足す（**待ち: AI が `payment-api` の `/mcp` と `payment_agent` を用意してから**。H31・H32）

- [ ] **9-1. Agent Registry に `payment-api-mcp` を登録する**（4-1 と同じ手順）
- [ ] **9-2. `payment-agent` をデプロイする**（5-1 と同じ手順）。エンジンIDを AI に返す
- [ ] **9-3. デモの前に `min_instances` を決める**（V5。常時課金と初回の待ち時間のトレードオフ）

## 片付け

- 数日使わないなら、Gateway と Model Armor は課金が続くので削除してよい（作り直すときは同じ名前にする）。エージェントは `min_instances=0` なら待機中の課金はほぼない
