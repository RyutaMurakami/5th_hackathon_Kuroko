# Backend Rules

## レイヤード構成
`backend/src/` は以下の役割で分離する。責務を混ぜない。

- `routers/` — FastAPI のエンドポイント定義のみ。ビジネスロジックは `services/` に委譲する。
- `agents/` — Google ADK エージェント定義（テンプレートの既定。**本プロジェクトでは使わない**。下記「本プロジェクトでのエージェントの置き場所」参照）。
- `clients/` — 外部サービス（Firestore, GCS 等）への薄いラッパー。
- `models/` — Pydantic スキーマ。
- `services/` — ビジネスロジック・エージェント（Agent Runtime）の呼び出し。
- `db/` — データアクセス層。

## 本プロジェクトでのエージェントの置き場所
ADK エージェントは Agent Runtime にデプロイするため、Cloud Run のコードとは別のデプロイ単位にする（詳細は `docs/ARCHITECTURE.md`）。

- `kuroko_agent/`（統括Agent）、`payment_agent/`（支払いエージェント）、`extract_agent/`（隔離抽出。ツールなし）— Agent Runtime。ツールは Cloud Run の API（`kuroko-api` / `payment-api`）の MCP エンドポイント（`/mcp`）だけにし、鍵・外部APIキー・Firestore・Slackには直接つなげない。エージェントの入出力は Agent Gateway を通る。
- `backend/`（`kuroko-gateway` / `kuroko-api`）、`payment_api/` — Cloud Run。決定論的なコードと、エージェント用の MCP サーバー（`routers/mcp.py`。`kuroko-api` / `payment-api` にだけ載せる）を置く。`audit.llm_must_not` に当たる処理（`policies/company_rules.yaml`）は MCP ツールに出さない。Model Armor は API から直接呼ばず、Agent Gateway に任せる。
- `bank_adapter/` — Cloud Run。**sunabar（銀行API）への窓口**。アクセストークンと、仮名 `user_id` ↔ 口座の対応表を持つのはここだけで、**引数にも応答にも口座番号を出さない**。エージェントからは到達できない（SPEC 8.2・10章、ARCHITECTURE D17）。送金はKUROKO自身がここを通じて実行する（外部の集金・決済サービスは使わない）。
- **記憶は Agent Platform の Memory Bank**（`backend/src/clients/memory_bank.py`、`services/memory.py`、`services/retrospective.py`）。**書き込み（`save_memory`）はコードだけ**で、Policy Gate 6.4（幹事の確認済み・定型テンプレートの事実だけ・個人情報なし・スコープ固定）を通ったときだけ、**直接書き込む**。会話（セッション）からの自動生成（`add_session_to_memory` など）は使わない。**読み取りは、統括エージェントにアタッチした ADK の `load_memory`**（読み取り専用の identity `roles/aiplatform.memoryViewer`）。`PreloadMemoryTool` は使わない。**エージェントのコード・コールバックに書き込みの API を書かない**（テストで固定）。`load_memory` は `before_tool` のコールバックで**企画・店舗提案の段階だけ**に制限する。スコープは、`kuroko-api` がセッション作成時に `user_id` へ入れるチームのスコープID。記憶は、金額・按分・承認者・支払先・委任・規程の値の計算に一切使わない（SPEC 4章冒頭・9.8、ARCHITECTURE D20）。
- **Web 向けの API（`routers/dashboard.py`）**は、チャット・アップロード・確認を受ける（SPEC 4.3・7.5、D22）。**Firebase の UID が Event の `organizer_web_uid` と一致するとき（ゲストは自分の `sandbox` イベントだけ）にだけ書き込める**（API で強制）。**委任・承認・取り消し・振込のルートは作らない**。チャットの発言は受け付けたらすぐに返し、処理は Cloud Tasks で非同期に行う。アップロードは短い期限の署名付きURLで、種類・サイズ・枚数を検査する。画像の中の文字は外部入力として扱い、読み取りの結果は値の検証を通して幹事が確認してから使う。
- **デモ用の代行（`routers/demo.py`。`/tasks/demo/*`、`payment-api` の `/demo/*`）**: **`sa-demo-runner` だけを受け付け、Event の `sandbox` が `true` でなければ拒否する**。Policy Gate 6.2・6.3 は省略しない。エージェントから呼べない。判断ログに `demo-runner` を残す（SPEC 7.6、D23）。
- **規程の参照は RAG Engine**（`backend/src/clients/rag_engine.py`）。抽出した値は `services/policy.py` が**コードで型と範囲を検証**してから Event の `policy_snapshot` に保存する。以後の按分はその写しだけを使う（SPEC 9.7、ARCHITECTURE D18）。`company_rules.yaml` は、抽出結果を検証するテストの正解データとフォールバック。`calculate_split` は決定論的なまま（LLM禁止）。
- `backend/src/agents/` は使わない。

## ADK エージェントの拡張（テンプレートの既定。上記の配置を優先する）
新しいエージェントを追加する場合:
1. マルチエージェント構成にする場合は `agents/sub_agents/` にサブエージェントを追加し、`agent.py` の `root_agent` に `sub_agents=[...]` で接続する。
2. エージェントが使うツール関数は `agents/` 配下か `services/` に置き、`tools=[...]` に渡す。
3. `tests/agents/` にエージェントのインスタンス化・ツール呼び出しの単体テストを追加する（実際の Gemini API 呼び出しはモックする）。

## 品質ゲート
- `uv run ruff check .` と `uv run pytest` を通すこと。
- 新しい依存関係は `pyproject.toml` に追加し、`uv sync` で `uv.lock` を更新する。
