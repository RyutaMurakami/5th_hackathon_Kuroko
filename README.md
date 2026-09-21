# akakura-ai-web-template

AkakuraのAI Agentを活用したWeb開発のテンプレートリポジトリ。ハッカソン等で新規プロジェクトを立ち上げる際の初期構成として使う。

技術スタックは Next.js（frontend） + FastAPI/Google ADK（backend） + Firestore + Terraform（単一GCP環境） + GitHub Actions（WIFデプロイ）。

## 思想

このテンプレートは「**AIエージェントとユーザーが対話しながら実装を進める**」ことを前提に設計している。エージェントがいきなりコードを書き始めるのではなく、次の流れで進むことを想定する。

```
docs/SPEC.md          課題・ユーザー・要件をヒアリングしながら埋める
                      （API・データモデル・エージェント設計もここで合意する）
   ↓
docs/ARCHITECTURE.md  合意内容をシステム構成として整理する
   ↓
docs/PLAN.md          タスクに分解する
   ↓
実装（backend / frontend / infra）
```

各 `docs/*.md` はスケルトンの状態で、先頭に `> エージェントへ:` というコメントが入っている。エージェントはこれを読み、ユーザーに質問しながら中身を埋めていく。仕様が変わったら実装より先にドキュメントを更新する（ドキュメントとコードを乖離させない）。この流れの詳細は `AGENTS.md` の Workflow セクションを参照。

その他の技術的な方針:

- **モノレポ**: `frontend` と `backend` を1リポジトリで管理する。
- **シングル環境**: dev/stg/prodのような環境分割はしない。GCPプロジェクトは1つ、Terraform stateも1つ。
- **AIエージェントはADKに集約し、Agent Runtimeにデプロイする**: エージェントごとに独立したデプロイ単位（`kuroko_agent/` `payment_agent/` `extract_agent/`）に置き、決定論的なコード・鍵・外部APIは Cloud Run 側に置く（詳細は `docs/ARCHITECTURE.md`）。エージェントのツールは MCP（`kuroko-api` / `payment-api` が自分で MCP サーバーを兼ねる）経由で呼び、入出力は Agent Gateway × Model Armor で検査する。
- **デプロイはWIF経由**: サービスアカウントキーを発行せず、GitHub Actions → Workload Identity Federation → Cloud Run / Agent Runtime / Firebase Hosting でデプロイする。
- **レイヤード構成（backend）**: `routers → services → clients/db`。責務を混ぜない（詳細は `.agents/rules/backend.md`）。
- **秘密情報はコミットしない**: `.env` 系は `*.env.example` のみコミット。実際の値やサービスアカウントキーは対象外（`.gitignore` 参照）。
- **使い捨てコードは `sandbox/`**: 実験的なコードは `src/` に置かず `sandbox/`（gitignore対象）に置く。

## 使い方

1. このリポジトリをコピー（またはテンプレートとして使用）してプロジェクトを開始する。
2. Claude Code / Antigravity（Gemini CLI）などのAIコーディングエージェントを起動する。どのツールも `AGENTS.md` を読み込む前提（`CLAUDE.md` / `GEMINI.md` は `@AGENTS.md` で取り込む各ツール向けのラッパー。下記「エージェント向け設定ファイル」参照）。
3. エージェントと対話しながら `docs/SPEC.md` → `ARCHITECTURE.md` → `PLAN.md` を埋める。
4. 合意した設計をもとに `backend/` `frontend/` `infra/` を実装する。各ファイルの `TODO` コメントが実装対象の目印。
5. Getting Started（下記）でローカル起動して動作確認する。

## エージェント向け設定ファイル

| ファイル | 対象ツール | 役割 |
|---|---|---|
| `AGENTS.md` | 共通 | 指示の実体。Workflow・Core Rules・Commands・Code Styleを定義 |
| `CLAUDE.md` | Claude Code | `@AGENTS.md` で `AGENTS.md` を取り込むラッパー。Claude Code 固有の指示があればここに追記する |
| `GEMINI.md` | Antigravity / Gemini CLI | `@AGENTS.md` で `AGENTS.md` を取り込むラッパー。Gemini 固有の指示があればここに追記する |
| `.agents/rules/{backend,frontend,infra}.md` | 共通 | 各領域の詳細規約 |

## ディレクトリ構成

```
.
├── AGENTS.md / CLAUDE.md / GEMINI.md  # AIエージェント向け指示（上表参照）
├── DESIGN.md              # UI デザインの仕様（Web Dashboard の色・文字・余白・部品）
├── docs/                  # 企画・設計ドキュメント（対話で埋めるスケルトン）
│   ├── SPEC.md            # 課題・要件・API・データモデル・エージェント設計
│   ├── ARCHITECTURE.md    # システム構成（サービス・コード配置・権限・デプロイ）
│   ├── human_task.md      # AIが実装する前に人間がやるタスク（アカウント・申請・提出）
│   └── PLAN.md            # マイルストーン・タスク分解
├── frontend/               # Next.js (App Router)
│   ├── app/                # ルーティング・ページ
│   ├── components/         # UIコンポーネント
│   └── lib/                 # Firebaseクライアント・APIクライアント
├── kuroko_agent/           # Agent Runtime: 統括Agent（ADK）※追加予定。docs/ARCHITECTURE.md 参照
├── payment_agent/          # Agent Runtime: 支払いエージェント（ADK）※追加予定
├── extract_agent/          # Agent Runtime: 隔離抽出エージェント（ADK。ツールなし）※追加予定
├── payment_api/            # Cloud Run: 支払いAPI（委任状の署名・検証、振込依頼、入金の確認）※追加予定
├── bank_adapter/           # Cloud Run: 銀行アダプタ（sunabar。トークンと口座はここだけ）※追加予定
├── backend/                # Cloud Run: FastAPI（kuroko-gateway / kuroko-api）
│   ├── src/
│   │   ├── routers/         # エンドポイント定義
│   │   ├── services/        # ビジネスロジック・Agent Runtimeの呼び出し
│   │   ├── agents/          # （テンプレートの雛形。本プロジェクトでは使わない）
│   │   ├── clients/         # 外部サービスへの薄いラッパー
│   │   ├── db/               # データアクセス層
│   │   └── models/           # Pydanticスキーマ
│   ├── tests/
│   └── scripts/              # デプロイ等の運用スクリプト
├── infra/terraform/        # GCPリソース定義（シングル環境）
├── .github/workflows/      # CI / WIFデプロイ
└── sandbox/                 # 使い捨てコード（gitignore対象）
```

## Getting Started

```
# backend
cd backend && uv sync && uv run uvicorn src.main:app --reload

# frontend
cd frontend && npm install && npm run dev
```

その他コマンド・品質ゲートは `AGENTS.md` を参照。
