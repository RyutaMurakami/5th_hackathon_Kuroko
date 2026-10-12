# KUROKO — 飲み会の幹事を、舞台裏で引き受ける AI エージェント

会社の歓送迎会の幹事の仕事（出欠、店探し、予約の確認、割り勘の計算、承認の取り付け、集金、振り返り）を、AI エージェントが引き受けます。**AI が担うのは、聞く・探す・調べる・説明することだけ**です。金額の計算、可否の判断、署名、振込は、決まった手順のコードと、本人の操作が担います。

Google Cloud の AI エージェントのハッカソン（第5回）の提出作品です。提出フォーム用の説明文は [docs/submission.md](docs/submission.md) にあります。

## 触ってみる（審査員の方へ）

**<https://kuroko-509311.web.app>** を開き、Google アカウントでログインして「体験をはじめる」を押してください。Slack や銀行の口座は要りません。1人で、最後まで通せます（15分ほど）。

画面には、3人ぶんの「KUROKO とのチャット」が並びます。左があなた（幹事）、真ん中と右が、参加者（赤坂 くらお）と承認者（赤くら 花子）です。2人に届くメッセージは、Slack に届くものと同じで、体験用に、あなたが2人の代わりにボタンを押せます。**幹事の列の先頭に、いつも「次にすること」が出ます。**

| 手順 | すること | 見どころ |
|---|---|---|
| 1 | 入力の候補を押して、歓送迎会を依頼する。チャットの中のカードで計画を確定する | 規程のことを聞くと、KUROKO が規程の文書を調べて、条番号を添えて答えます |
| 2 | くらお・花子の列で、「参加して、委任に同意する」を押す | 上限額と支払先を決めた、支払いの委任（AP2 の委任状）に署名されます |
| 3 | 「店の候補を出す」で店を選び、サンプルの予約画面をアップロードして確定する | 全員の帰りやすさで順位を決めます。過去の実績（記憶）がある店には、その理由が付きます |
| 4 | 「開催が終わった」を押し、サンプルの領収書をアップロードして金額を確定する | 規程に沿って、コードが按分を計算します。根拠の条が出ます |
| 5 | 花子の列で按分を承認し、2人の列で「銀行で承認する（体験用）」を押す | 委任の範囲を1円でも超える振込は、作られません |
| 6 | 1〜2分待つと、入金の確認が済み、振り返りが始まる。2人の満足度に答える | 入金は、銀行の明細で確認できたときだけ「完了」にします |
| 7 | 振り返りを確かめて、「次回に覚えさせる」を押す | 決まった形の文だけが、記憶に保存されます。もう一度依頼すると、店の候補に反映されます |

- サンプルの予約画面と領収書は、画面からダウンロードできます（架空の店です）。
- 銀行は、GMOあおぞらネット銀行の銀行 API の実験用の環境（sunabar）で、**資金は仮想です**。体験用の画面では、銀行の承認ページを模した画面で承認し、銀行には送りません。開発者の実演（デモ動画）では、本物の銀行 API に振込を依頼し、本人が銀行のサイトで承認しています。
- 入力した内容は、7日で削除されます。実在の個人情報や領収書は入れないでください。
- 会社「株式会社Akakura」・規程・登場人物は、すべて架空です。

詳しい手順と、期待する結果は [docs/guides/e2e_scenario.md](docs/guides/e2e_scenario.md) にあります。

## 何を作ったか

| 段階 | KUROKO がすること | 人がすること |
|---|---|---|
| 依頼 | チャットで依頼を整理し、足りないことだけを聞く。規程を聞かれたら、文書を調べて答える | 幹事が計画を確かめて確定する |
| 出欠・委任 | 参加者に、出欠と、上限つきの支払いの委任を依頼する | 参加者が同意する（委任状への署名のきっかけは、本人の操作だけ） |
| 店 | 全員の最寄り駅から帰りやすい駅を探し、店を提案する。理由と、過去の実績を添える | 幹事が選び、予約する |
| 精算 | 予約画面・領収書を読み取り、規程に沿って按分する | 幹事が読み取り結果を確かめて確定する。承認者が按分を承認する |
| 送金 | 委任の範囲内で振込を依頼し、銀行の明細で入金を確認する | 参加者が、銀行で振込を承認する |
| 振り返り | 満足度を集め、実績と合わせて、次回に覚える内容をまとめる | 幹事が確かめて、覚えさせるかを決める |

**AI とコードの役割の境界**（これ自体を、最大の安全策にしています）

- AI が決めないもの: 金額の計算、承認者、支払先、規程の値、委任状への署名、店の順位、振込の作成、「完了」の判断
- AI が見ないもの: 実名（画面の表示を除く）、口座番号、銀行のトークン、署名鍵、個人ごとの回答
- 請求する側（`kuroko-api`）と、支払う側（`payment-api`）が、互いを信用せず、別々に検査します（Policy Gate）。銀行の口座とトークンは、`bank-adapter` だけが持ちます

## アーキテクチャ

![KUROKO の構成図](docs/diagrams/export/KUROKO_GoogleCloud構成図_v2.0.svg)

| 置き場所 | 名前 | 役割 |
|---|---|---|
| Firebase Hosting ＋ Cloud Run | `kuroko-dashboard`（`frontend/`） | Web の画面（Next.js）。Google ログイン |
| Cloud Run（公開） | `kuroko-gateway`（`backend/`） | Slack の入口。署名を検証して、Cloud Tasks に渡すだけ |
| Cloud Run（非公開） | `kuroko-api`（`backend/`） | 業務のコード。按分、Policy Gate、請求の署名、振り返り、記憶の読み書き。エージェント用のツール（MCP） |
| Cloud Run（非公開） | `payment-api`（`payment_api/`） | AP2 の委任状の署名と検証、振込の依頼、入金の確認、領収書の署名 |
| Cloud Run（非公開） | `bank-adapter`（`bank_adapter/`） | 銀行 API（sunabar）の窓口。口座とトークンは、ここだけ |
| Agent Runtime | `kuroko-agent`（`kuroko_agent/`） | 統括エージェント（ADK・Gemini）。ツールは `kuroko-api` の MCP の4つだけ |
| Agent Runtime | `extract-agent`（`extract_agent/`） | 自由記述を、決まった語彙に落とすだけのエージェント（ツールなし） |
| Agent Platform | Agent Gateway ＋ Model Armor、Agent Registry、Memory Bank | エージェントの入口・出口の検査、ツールの名簿、チームの宴会実績の記憶 |
| データ・鍵 | Firestore、Cloud Storage、Cloud KMS、Secret Manager | 業務の状態、アップロード、署名鍵、外部 API のキー |
| 非同期 | Cloud Tasks、Cloud Scheduler | Slack の操作の受け渡し、銀行の承認と入金の確認（1分ごと） |

エージェントが呼べるツールは、`get_event_summary`・`check_budget`・`search_venues`・`retrieve_policy` の4つです（[backend/mcp_toolspec.json](backend/mcp_toolspec.json)）。お金・承認・署名に当たるツールは、公開していません。

設計の詳細は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、仕様は [docs/SPEC.md](docs/SPEC.md) にあります。

## 実装の範囲（正直に書きます）

- 銀行は sunabar（実験用の環境）で、**資金は仮想**です。ただし、振込依頼・振込ごとの本人承認・入出金明細の照会は、本物の銀行 API の仕様どおりに実装しています。
- デモで、Slack と銀行を実際に操作するのは2人（くらお・花子）です。ほかの5人の出欠・委任・振込は、デモ用の代行が行います。**委任状の署名と検証、Policy Gate、請求の署名、明細での入金確認は、全員ぶんが同じコードで動きます。**
- 体験用の画面では、参加者・承認者の操作と銀行の承認を、Web から行えます。本来は、本人が Slack と銀行で行う操作です。Web から行った操作は、区別して記録しています。
- 規程は、架空の文書（[policies/company_rules.md](policies/company_rules.md)）です。エージェントは、ツールで文書を条ごとに調べます（検索は自前のコードです）。
- 記憶は、Agent Platform の Memory Bank に、幹事が確かめた決まった形の文だけを保存します。読み書きはコードが行います。
- 本番で使うには、制度面の確認が要ります（参加者の依頼で振込の指図を銀行に伝える事業は、電子決済等代行業の登録などが必要とされます。法的な判断は、専門家への確認が必要です）。

## 開発

```bash
# backend（kuroko-api / kuroko-gateway）
cd backend && uv sync && uv run uvicorn src.main:app --reload
cd backend && uv run ruff check . && uv run pytest

# frontend
cd frontend && npm install && npm run dev
cd frontend && npm run lint && npm run typecheck && npm run build

# インフラ
cd infra/terraform && terraform validate
```

- 進め方は、文書が先です（[docs/PLAN.md](docs/PLAN.md) → [docs/SPEC.md](docs/SPEC.md) → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) → [docs/TASKS.md](docs/TASKS.md)）。AI コーディングエージェント向けの指示は [AGENTS.md](AGENTS.md) にあります。
- `main` にマージすると、GitHub Actions が Workload Identity Federation で Cloud Run にデプロイします。エージェント（Agent Runtime）は、`infra/agent_platform/deploy_agent.py` でデプロイします。
- 秘密の値（キー・トークン・口座番号）は、コミットしません。Secret Manager に置きます。
- いまの状態と、引き継ぎの注意は [docs/HANDOVER.md](docs/HANDOVER.md) にあります。

## ディレクトリ

```
backend/        kuroko-api・kuroko-gateway（FastAPI。routers → services → clients / db）
payment_api/    payment-api（AP2 の委任状・Policy Gate 6.3・振込の依頼）
bank_adapter/   bank-adapter（銀行 API の窓口）
kuroko_agent/   統括エージェント（ADK。Agent Runtime）
extract_agent/  隔離抽出エージェント（ADK。ツールなし）
frontend/       Web の画面（Next.js App Router）
policies/       架空の規程（文書と、検証用の正解データ）
infra/          Terraform（Google Cloud）と、エージェントのデプロイ
docs/           企画・仕様・設計・タスク・手順書
```

## 利用している OSS とライセンス

このリポジトリが直接使っている主なものです。各パッケージの正確な版は、`uv.lock`・`package-lock.json` に固定しています。

| 名前 | 使っている場所 | ライセンス |
|---|---|---|
| [Agent Payments Protocol（AP2）](https://github.com/google-agentic-commerce/AP2) の SDK | `payment_api/`（委任状の作成・検証、制約の検査） | Apache License 2.0 |
| [Agent Development Kit（ADK）](https://github.com/google/adk-python) | `kuroko_agent/`・`extract_agent/` | Apache License 2.0 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | `backend/`（エージェント用のツールの入口） | MIT License |
| [FastAPI](https://github.com/fastapi/fastapi)・[Pydantic](https://github.com/pydantic/pydantic) | `backend/`・`payment_api/`・`bank_adapter/` | MIT License |
| [Next.js](https://github.com/vercel/next.js)・[React](https://github.com/facebook/react) | `frontend/` | MIT License |
| [Slack SDK for Python](https://github.com/slackapi/python-slack-sdk) | `backend/`・`payment_api/` | MIT License |

AP2 の SDK は、公式のリポジトリから取り込んでいます（`payment_api/pyproject.toml`）。AP2（v0.2）が正式に対応する支払い手段はカードで、銀行振込への接続は、公式のサンプルの範囲外の、このプロジェクト独自の実装です。
