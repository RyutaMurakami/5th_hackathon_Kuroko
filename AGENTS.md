# AGENTS.md

## Project Overview
モノレポのハッカソンテンプレート: Next.js フロントエンド + FastAPI/Google ADK バックエンド。
Cloud Run + Agent Runtime（ADKエージェント）+ Firebase Hosting に GitHub Actions (Workload Identity Federation) でデプロイする。
詳細は `docs/ARCHITECTURE.md` を参照。

## Workflow（ドキュメント駆動・対話開発）
このテンプレートは、エージェントがユーザーと対話しながら実装を進めることを前提にしている。コードを書く前に必ずこの順で進める。

1. `docs/PLAN.md` — **概要**。課題・想定ユーザー・コンセプト・競合との差分・実現構成の概要・前提とスコープ外を、ユーザーに確認しながら埋める。
2. `docs/SPEC.md` — **仕様**。機能要件・API・データモデル・ツール契約・エージェント設計をユーザーと合意する（旧 `DESIGN.md` は SPEC.md に統合済み）。あわせて Web Dashboard の見た目は リポジトリ直下の `DESIGN.md`（UI デザインの仕様。旧 `DESIGN.md` とは別物）でユーザーと合意する。PLAN.md と食い違う場合は SPEC.md が正。
3. `docs/ARCHITECTURE.md` — **アーキテクチャ**。上記を実際のシステム構成（サービス・コード配置・権限・デプロイ）に落とす。SPEC.md と食い違う場合は SPEC.md が正。
4. `docs/TASKS.md` — **エージェントの実装タスク**。上記の合意をタスクに分解し、実装を進めながら更新する（完了したらチェックを付ける）。**人間のタスク**（アカウント・申請・Slack App・課金・承認・提出など）は `docs/human_task.md` に分けてあり、TASKS.md の各タスクは、依存する人間のタスクを番号（H・P・S）で示す。
5. 実装は各ドキュメントの合意後に着手する。着手前に `docs/TASKS.md` で着手するタスクを確認し、`docs/human_task.md` で、そのタスクが依存する人間のタスクが完了しているかをユーザーに確認する。仕様や設計に不明点・複数の選択肢がある場合は、仮実装せずユーザーに確認する。
6. 実装中に仕様変更が発生したら、先に該当ドキュメントを更新してから実装に反映する（ドキュメントとコードを乖離させない）。

各 `docs/*.md` の先頭にエージェント向けの短い指示コメント（`> エージェントへ:`）がある。

## Core Rules
- 秘密情報・サービスアカウントキー・`.env` ファイルは絶対にコミットしない。
- `backend/.venv`、`frontend/node_modules`、`infra/terraform` の state/plan ファイルはコミットしない。
- 実験的・使い捨てのコードは `sandbox/`（gitignore 対象）に置き、`src/` には置かない。
- バックエンドの変更は `ruff check` と `pytest` を通してからマージする。
- フロントエンドの変更は `lint` / `typecheck` / `build` を通してからマージする。

## Commands
| タスク | コマンド |
|---|---|
| Backend dev | `cd backend && uv run uvicorn src.main:app --reload` |
| Backend test | `cd backend && uv run pytest` |
| Backend lint | `cd backend && uv run ruff check .` |
| Frontend dev | `cd frontend && npm run dev` |
| Frontend build | `cd frontend && npm run build` |
| Emulators | `firebase emulators:start`（リポジトリルートで実行） |
| Terraform check | `cd infra/terraform && terraform validate` |

## Code Style
- Python: ruff（line-length 100, py312 target）。Cloud Run 側（`backend/` `payment_api/` `bank_adapter/`）はレイヤード構成 `src/{routers,clients,models,services,db}`。ADK エージェントは `kuroko_agent/` `payment_agent/`（Agent Runtime）に置く（`docs/ARCHITECTURE.md`）。
- TypeScript: Next.js App Router 規約。コンポーネントは `frontend/components` に配置。UI の色・文字・余白・部品は、リポジトリ直下の `DESIGN.md` のトークンに従い、値を直接書かない。

## Further Reading
- `.agents/rules/backend.md` / `frontend.md` / `infra.md` に各領域の詳細規約がある。
- `CLAUDE.md`（Claude Code）/ `GEMINI.md`（Antigravity, Gemini CLI）は、それぞれのツールが自動で読むファイル名に合わせて用意した薄いラッパーで、`@AGENTS.md` でこのファイルをインポートしている。指示の実体は常にこの `AGENTS.md`。
