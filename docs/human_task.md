# 人間が先にやるタスク（human_task）

> エージェントへ: AI が実装に着手する前に、人間が済ませておくタスクの一覧（**AI 側のタスクは [TASKS.md](TASKS.md)**。本書は人間のタスクだけ）。着手する作業に対応する項目（各項目の「止まる実装」）が完了しているかを、実装の前にユーザーへ確認する。未完了のまま仮実装で進めない。**トークン・キーなどの秘密の値は、ユーザーにチャットへ貼らせない**（置き場所は「受け渡し」節に従う）。項目が完了したらチェックを付け、日付と結果（ID・URLなど秘密でないもの）を書き込む。

- 作成日: 2026-09-19 / 最終更新: 2026-09-27（提出締切 2026-10-15 23:59 まで **残り18日**）
- 根拠: [SPEC.md](SPEC.md) 13章（要準備・要検証）、[ARCHITECTURE.md](ARCHITECTURE.md) 12章（D1〜D21）・13章（V1〜V12）、[DESIGN.md](../DESIGN.md)、ハッカソンの提出要件
- 2026-09-20 の更新内容（1回目）: ツールを MCP 経由にし API 自身が MCP サーバーを兼ねる構成、Agent Gateway × Model Armor への一本化、隔離抽出エージェント（`extract-agent`）、Web Dashboard を幹事・開発者向けの4点に絞ったこと、DESIGN.md の新設を反映した。**Agent Gateway が使えるかの確認（H21）を、Agent Runtime の実験（H11）より先にした**
- 2026-09-20 の更新内容（2回目）: **送金を、AP2 サンプルの模擬決済役から、KUROKO 自身が銀行API（sunabar）で実行する形に変えた**（D17。幹事Pay など外部の集金・決済サービスは使わない）。**規程の参照を RAG Engine にした**（D18）。**Web Dashboard を幹事の主導線にし、事務の確認を Web で行えるようにした**（D19）。これに伴い、**sunabar の口座開設と疎通（H22・H23・H25）、規程の文書の用意（H24）を追加**し、`ap2-mock` に関する項目（H16・P7・S4・S5）を差し替えた。**H22（口座開設）はリードタイムがあるので最優先**
- 2026-09-20 の更新内容（3回目）: **按分の内訳を Web に出す**（D21）、**振り返り・記憶を作る**（**Agent Platform の Memory Bank**。D20）、**Web の事務の確認**（振り返りのまとめの確認を含む）が決まった。これに伴い、**Memory Bank の疎通（H26。V12）と、過去のイベントの記憶（seed）の用意（H27）を追加**し、H1・H2 を更新した。**H2 の「要レビュー」から、決まった3点を外した**
- 2026-09-21 の更新内容（5回目）: **AI の実装タスクを [TASKS.md](TASKS.md) に分けた**（「人間の作業を待たずに AI が始められる実装」の節は TASKS.md の T1 へ移した）。PLAN=概要、SPEC=仕様、ARCHITECTURE=アーキテクチャ、TASKS=AI のタスク、human_task=人間のタスク、という分け方にした。
- 2026-09-21 の更新内容（4回目）: **思想の変更（Webが主導線、Slackは Human-in-the-loop）**。幹事の作業（依頼・領収書と予約画面のアップロード・確認）は Web で行い、**審査員が実際に触って体験できる**ことを狙う（D22・D23、SPEC 7.5・7.6）。これに伴い、**審査員向けの準備（H28：サンプルの領収書・予約画面と「サンプル商事」の初期データ、H29：デモ用 Slack の招待リンク）を追加**し、Firebase の匿名認証（H10）、H17・H18・H26・H27・P6・P8・P10・S1 を更新した。あわせて、**Memory Bank を統括エージェントにアタッチして読み取る**方式に変えた（D20。MCP ツール `recall_memory` は廃止）
- 2026-09-26 の更新内容: **審査員と開発者の役割を統合した**（ARCHITECTURE D25・SPEC 7.3/7.6）。Web の役割は幹事とゲストの2つで、許可リスト（P6）は幹事だけになった。認証はログイン不要を残し、将来は Google 認証だけにする
- **2026-09-27 の更新内容: 最小構成での実装順を決定した**（TASKS.md 参照）。**H11・H21（Agent Runtime・Agent Gateway の検証）と H22（sunabar 口座開設）を最優先で進める**（本実装はこの結果が出るまで着手しない）。**H24・H26・H27（RAG Engine・Memory Bank の準備）も、結果を待たず並行して優先的に進める**。**H17〜H20（Slack）は、間に合わなければ後回しでよい**（審査員向けデモは sandbox のデモ用代行で成立させる）
- **2026-09-27 の更新内容（2回目）**: H2・H3・H4・H5・H8・H9・H10・H16・H17・H18・H19・H20 にユーザーが回答。**H2 で審査員のログインを「匿名認証」から「審査員用アカウントでのログイン」に変更**（H10 の匿名ログイン不使用と整合）。これは SPEC.md 7.6・ARCHITECTURE.md D23 の前提を変えるため、**該当箇所の更新が別途必要**（下記 H2・H10 参照）。**9.8節の記憶の書き込みに、ユーザーの自由記述をバックログとして許す案を追加**（TASKS.md にバックログ項目として追記予定）
- **2026-09-27 の更新内容（3回目）**: 審査員のログイン方式を「**審査員は Google アカウントを使用します**」と確定（ユーザー確認）。**SPEC.md（7.3・7.6・11章・13章）・ARCHITECTURE.md（D23・D25・V14）・TASKS.md（I6・F4・O4）・DESIGN.md・PLAN.md・infra/terraform/README.md・docs/diagrams/README.md の匿名認証の記述を、Google ログイン（許可リストに載っていないアカウントはゲスト）に更新した**。匿名認証は使わない。役割の決め方（許可リスト照合）自体は変えない
- **2026-09-27 の更新内容（4回目）**: **Agent Platform（Agent Runtime・Agent Gateway・Agent Registry・Model Armor・RAG Engine・Memory Bank）のリソース作成・デプロイは、学習のためユーザーが Console で自分の手で行う**ことに決定（ユーザー指定）。AI はコード（エージェント本体・MCPサーバー）・IAM（Terraform）・Console 操作の手順書・作成後の検証スクリプトの用意に役割を絞る。**H11・H26 を「AI が用意して承認を得る（【承】）」から「ユーザーが Console で自分の手で行う（【人】）」に書き換え、本番デプロイ用の H31（Agent Runtime）・H32（Agent Gateway/Registry/Model Armor）と、RAG コーパス作成用の H30 を新設した**（TASKS.md の I7・I8・I9・O2・O3 も合わせて書き換え）

### 種別の見方

| 印 | 意味 |
|---|---|
| 【人】 | 人間だけができる（アカウント・課金・申請・Console操作） |
| 【承】 | AI が実行するが、人間の承認が必要（課金・デプロイなど。`agents-cli deploy` は毎回承認が前提） |
| 【決】 | 人間が決める（AI は選択肢と推奨を出す） |

### 進め方の目安（2026-09-27 改定）

> H1・H3・H4・H5・H6・H7・H8・H9・H10・H12・H16・H19・H20 は完了。**最優先は H11・H21（Agent 系の検証。H11 はユーザーが Console で自分の手で構築）と H22（sunabar 口座開設）**。**H24・H26・H27・H30（RAG・Memory Bank。H26・H30 はユーザーが Console で自分の手で作成）も、結果を待たず並行して優先的に進める**。**H17・H18（Slack のデモ用ワークスペース・ユーザー準備）は、間に合わなければ後回しでよい**（TASKS.md 参照）。**H2 は大半に回答済み。審査員のログイン方式の変更（匿名認証→Google ログイン）は、SPEC.md 7.6・ARCHITECTURE.md D23 などへの反映が完了した（2026-09-27）**。H2 の残りは 7.6節②（デモ用の代行を使うか）・③（(A)(B) の両方を用意するか）だけ。**H31・H32（Agent Runtime・Gateway 等の本番デプロイ）は、H11 のゲートが通り、対応するエージェント・MCP の本実装ができてから着手する**。

| 時期 | やること |
|---|---|
| 9/27〜9/29 | **最優先**: H11（**Console で自分の手で** Agent Runtime・Gateway・Registry・Model Armor の最小構成を構築）・H21（Agent Gateway・Model Armor が使えるかの確認）・H22（sunabar の口座開設）。**並行して優先**: H24（規程PDFの内容確認）・H26（**Console で自分の手で** Memory Bank を作成）・H27（記憶 seed の内容を決める）・H30（**Console で自分の手で** RAG コーパスを作成。H24 の完成後） |
| 9/29 | ハッカソンのオフィスアワー（質問リストは P10） |
| 9/29〜10/5 | H23（デモ用 sunabar 口座）、H13（駅すぱあとキーの Secret Manager 登録は完了。あとは疎通確認）、**H17・H18（Slack。間に合わなければ後回しでよい）**、P1〜P3（apply の承認・シークレットの登録） |
| 10/6〜10/10 | H28・H29（審査員向け素材）、**H31・H32（本番の Agent Runtime・Gateway 設定。エージェント・MCP の本実装ができ次第）**、P4〜P9（デプロイの承認・許可リスト・確認） |
| 10/11〜10/14 | S1〜S9（提出物） |
| 10/15 23:59 | **参加登録とプロジェクト提出の両方**の締切** |

---

## AI の実装タスクは TASKS.md

AI が行う実装・検証の準備・文書の更新は、[TASKS.md](TASKS.md) に分けた。本書は**人間のタスクだけ**を持つ。人間の作業を待たずに AI が始められる実装は、TASKS.md の「B-A. 業務ロジック（先行可）」「B-B. 支払い・銀行」（B9・B10）と、E・F の先行可のタスクにある（**H1・H1b・H2 の合意さえ済めば着手できる**）。各タスクが依存する人間のタスクは、TASKS.md の「人間の依存」欄に H・P・S 番号で書いてある。

---

## Phase 0: これが終わらないと実装が始められない

### A. 決定・合意

- [x] **H1【決】ARCHITECTURE.md の D1〜D21 をレビューして合意する**
  - **2026-09-26: 合意（D1〜D25）。D16（`extract-agent` を分けるか）は保留のまま、I8 で決める**
  - **新しい決定（2026-09-20・21）**: **D17**（`ap2-mock` をやめ、`bank-adapter` から sunabar で送金する。外部の集金・決済サービスは使わない）、**D18**（規程を RAG Engine で参照。版管理なし）、**D19**（Web Dashboard を幹事の主導線にし、事務の確認の書き込みを許す）、**D20**（Memory Bank。**統括エージェントにアタッチして読み取る**（`load_memory`。読み取り専用のロール。企画・店舗提案の段階だけ）。**書き込みはコードだけ・幹事の確認のあと・定型の事実だけ**）、**D21**（按分の内訳を Web に出す）、**D22**（**Web が主導線、Slack は Human-in-the-loop**。チャット・アップロード・確認は Web）、**D23**（**審査員（ゲスト）が触れる導線**。匿名認証・サンドボックス・デモ用の代行）
  - 特に **D9**（エージェントを `backend/` から `kuroko_agent/` `payment_agent/` `extract_agent/` に分ける）、**D10**（支払いの手順を `payment-api` が強制する）、**D11**（ツールを MCP 経由にし、`kuroko-api` / `payment-api` 自身が MCP サーバー `/mcp` を兼ねる）、**D12・D13**（Agent Gateway × Model Armor。Model Armor の直接呼び出しは作らない）、**D14・D25**（Dashboard は幹事・ゲスト（審査員と開発者を区別しない）の2役割で、「誰が幹事か・全体フローのどこか・誰から誰へいくら送金されたか・まだ承諾していない人は誰か」の4点に、**按分の内訳と、振り返り・記憶**を加えた6点に絞る。権限は API で強制。D19・D21）
  - **判断が要る点**: **D16** 隔離抽出を、ツールを持たない別のエージェント（`extract-agent`）にするか。デプロイ対象が1つ増える。**簡略案**は、隔離抽出をやめて自由記述を統括エージェントに直接渡す（Gateway の入口の検査と Policy Gate だけで守る）。H11 のレイテンシの結果を見て決めてもよい
  - ~~`payment-agent` を Agent Runtime に置く価値があるか~~ → 「ADK エージェントは基本的にすべて Agent Runtime」の指定で決着（D6）
  - 止まる実装: すべて（ディレクトリ構成が決まらない）
- [x] **H1b【決】`DESIGN.md`（リポジトリ直下。UI デザインの仕様）をレビューして合意する**
  - 方向性: 明るい空色の基調＋墨紺の文字。**黒い面は作らない**。アクセントは空色1色、「人の対応待ち」だけ黄。ユーザーが書き直した版（Refero）を土台に、暗い基調と緑を置き換えた
  - **判断が要る点**: 完了・送金済み・承諾済みを**青緑（Lagoon）**で示す（状態専用）。緑系を避けたい場合は別の色を指定する。書体は Inter（英数字）＋ Noto Sans JP（日本語）
  - 止まる実装: `frontend/` の画面（ダミーデータでの実装を含む）
  - 2026-09-23: 合意（提案のとおり。青緑・Inter＋Noto Sans JP を含む）。開発用の Demo Toolbar を DESIGN.md に追記
- [ ] **H2【決】SPEC.md 13章「要レビュー」を決める**
  - 9.3節: 会社補助の対象外者の按分ルール
  - `company_rules.yaml` の委任状の有効期限（開催日＋7日）
  - **9.8節: Memory Bank を統括エージェントにアタッチして読み取る**（ADK の `load_memory`。`agent-kuroko` に読み取り専用のロール `memoryViewer` だけ。企画・店舗提案の段階だけ。書き込みは `kuroko-api` のコードだけ。2026-09-21 に、MCP ツール経由の案から変更）。エージェントが直接読むので実装は軽いが、**読み取りの結果が Agent Gateway の検査を通らない**。汚染への備えは書き込みの入口に集中させる
  - **7.6節: 審査員が体験できる導線**（**要レビュー**）: ①ログイン不要（匿名認証）でよいか ②**デモ用の代行**（`sandbox` のイベントだけ、Slack の署名検証済み操作の代わりに `sa-demo-runner` が参加者・承認者の HITL を代行）を入れてよいか。「署名検証済みの Slack 操作だけが委任に署名できる」原則の**唯一の例外**になる。入れない場合は、審査員が Slack に参加して全員分の HITL を行う必要があり、一人では完走できない ③(A) Web のみ（既定）と (B) Slack に参加（任意）の両方を用意するか
  - **9.8節: 記憶の書き込みは、幹事が Web で確認した定型の事実だけ。会話からの自動生成は使わない**（汚染に強いが、自由な要約は覚えられない）
  - **3章: 振り返りの回答が3件未満のときは内訳を出さない**（個人の特定を避ける。人数が少ないチームでは平均しか覚えられない）
  - **9.8節: デモでは、過去の記憶を事前に投入（seed）して見せる**（H27）
  - **決定済み（2026-09-20）**: 支払い方式の再変更（8章。参加者が銀行の承認ページで振込ごとに承認。KUROKO が銀行APIで実行。資金は仮想）／Web Dashboard を幹事の主導線にし事務の確認を Web で行う（7.3節）／**按分の内訳を Web に出す**（7.3.1。幹事は区分・係数から個人の役職を推測できるが承知の上）／**振り返り・記憶を作る**（9.8節。Memory Bank）
  - **2026-09-27: 6項目のうちユーザーが5項目に回答（1項目は変更を伴う決定なのでフォロー要）**
    - **9.3節（対象外者の按分ルール）**: **とりあえず決め打ちで作ってよい**（厳密な公平性は追求しない。AI が実装時に具体案を決めてよく、後で見直し可）
    - **委任状の有効期限**: 確認のみで解決。`policies/company_rules.yaml` の `payer_mandate.expires_after_event_days: 7`（開催日＋7日）として**既に実装済み**
    - **9.8節（Memory Bank アタッチ読み取り案）**: **その案で一旦OK**（提案どおり確定）
    - **9.8節（記憶の書き込み）**: **現状案（幹事が Web で確認した定型の事実だけ）でOK**。加えて、**バックログとしてユーザーによる自由記述の記憶書き込みも許す**方針にする（将来対応。TASKS.md にバックログ項目として追記する）
    - **3章（振り返り3件未満ルール）**: **今回は全員が回答することを想定してよい**（3件未満のケースはデモでは発生しない前提。ルール自体は保険として残す）
    - **9.8節（過去記憶の事前投入）**: **Yes（H27 で内容を決めて進める）**
    - **7.6節①（審査員のログイン方式）**: **匿名認証ではなく、審査員は Google アカウントでログインする**（ユーザー確認：「審査員はGoogleアカウントを使用します」。H10 の「今回は匿名ログインは使わない」と合わせた決定）。役割の決め方は変えない（幹事の許可リスト `dashboard_users` に載っている Google アカウントは `organizer`、載っていないアカウントは `guest`）。**2026-09-27: SPEC.md（7.3・7.6・11章・13章）・ARCHITECTURE.md（D23・D25・V14 など）・TASKS.md（I6・F4・O4）・DESIGN.md・PLAN.md・`infra/terraform/README.md`・`docs/diagrams/README.md` に反映済み**（②デモ用代行 `sa-demo-runner` を使うか、③(A)Web専用か(B)Slack参加も用意するかは未回答のまま。要レビューとして残す）
  - 止まる実装: 按分・委任状・記憶（読み取り・書き込み・seed）は着手可。**Web Dashboard の事務の確認・審査員の認証まわり**は、審査員ログイン方式の反映（SPEC.md/ARCHITECTURE.md 更新）を待つ
- [x] **H3【決】役割分担を決める**
  - 最低限、「Slack ワークスペース」「GCP プロジェクトと課金」「各APIキー」の契約・管理の担当者を決める（SPEC 冒頭のとおり、機能の分担は固定しない）
  - **2026-09-27: 確定（ユーザー確認）**。ソロでの参加のため役割分担は実質単一。Slack ワークスペース・GCP プロジェクトと課金・各 API キーの契約・管理は、すべて村上（Murakami）が行う
- [x] **H4【人】未コミットの変更を整理してコミットする**
  - 対象: `DESIGN.md`（リポジトリ直下）、`docs/`（PLAN・SPEC・ARCHITECTURE・TASKS・human_task・mock・review）、`policies/`、`.claude/`、`backend/uv.lock`、`AGENTS.md` `CLAUDE.md` `GEMINI.md` `README.md`、`.agents/rules/`、`backend/src/db/firestore.py`
  - 止まる実装: なし（ただし AI が作業ブランチを切るために、`main` がきれいな状態であることが望ましい）。AI は依頼がない限りコミットしない
  - **2026-09-27: 確認（AI）**。`git status` はクリーンで、未コミットの変更はなし（対応不要。整理・コミットは既に済んでいる状態）

### B. ハッカソンへの登録

- [x] **H5【人】Zenn でエントリーし、プロジェクトを作成する**
  - 手順: 公式ページからエントリー → 規約に同意 → 参加者情報のフォーム入力 → ダッシュボードで「プロジェクトを新規作成」
  - 締切は **10/15 23:59。参加登録と提出の両方が必要**で、片方だけでは参加にならない。実装は止まらないが、忘れると失格になるので最初に済ませる
  - チームで参加する場合は、メンバーの Zenn ユーザー名を集めて招待する
  - **2026-09-27: 完了（ユーザー確認）**

### C. Google Cloud と開発環境

- [x] **H6【人】GCP プロジェクトを1つ作り、課金を有効にする**
  - シングル環境の方針（dev/stg/prod を分けない）。プロジェクトID を AI に伝える
  - あわせて**予算アラート**を設定する（Agent Runtime は `min-instances=1` が既定で、**3インスタンス**（`kuroko-agent` `payment-agent` `extract-agent`）が常時課金になり得る。ARCHITECTURE V5）。**RAG Engine・Memory Bank・Agent Gateway・Model Armor のテンプレート**も課金対象になり得るので、予算アラートの対象にする（sunabar は無料）
  - 公式ページの特典欄にクレジット提供があるかも確認する
  - 止まる実装: Terraform・デプロイ・Gemini を呼ぶ実装すべて
  - **2026-09-26: プロジェクト `kuroko-509311`（プロジェクト番号 1054683553459）。課金は有効、Owner を確認。Firebase は追加済み（Hosting のサイト `kuroko-509311`・Web アプリ登録済み）。予算アラートは設定済み（ユーザー確認）**
- [x] **H7【人】手元に CLI を入れ、ログインする**
  - 必要: `gcloud`（**最新版**。Agent Gateway・Agent Registry のコマンドを使うため、`gcloud components update` も実行する）、`terraform`、`uv`、`node`（npm）、`firebase-tools`、`agents-cli`（`uv tool install google-agents-cli`）
  - ログイン（対話が必要。Claude Code では `! ` を先頭に付けて実行できる）:
    - `gcloud auth login`
    - `gcloud auth application-default login`
    - `gcloud config set project <プロジェクトID>`
    - `firebase login`
  - 止まる実装: GCP に触れる作業すべて
  - 2026-09-26（途中）: `gcloud`・`uv`・`node`・`firebase-tools`・`agents-cli` は導入済み、ADC も有効。`terraform` は AI が Homebrew で導入（1.16.4）。`gcloud config set project kuroko-509311` も実施済み（2026-09-26 完了）
- [x] **H8【人】Terraform を回すための最初の API を有効にする**
  - `gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com`
  - 残りの API は AI が Terraform（`google_project_service`）で有効にする
  - **2026-09-27: 完了（ユーザー確認）**
- [x] **H9【人】権限と組織ポリシーを確認する**
  - 自分がプロジェクトの Owner か
  - **Cloud Run を未認証で公開できるか**（`kuroko-gateway` は Slack から呼ばれるため公開が必要。組織ポリシーで禁止されていると詰まる）
  - IAM のロールを付与できるか（Agent Gateway の `roles/iap.egressor`、Model Armor のロールなど。組織のポリシーで止まらないか）
  - Agent Runtime・Agent Gateway・Model Armor が使えるかは **H21** で確認する
  - 止まる実装: `kuroko-gateway` のデプロイ、Slack 連携
  - 2026-09-26（途中。AI が確認）: `kuroko-509311` は組織に属さず、あなたは Owner。組織ポリシーがないので、未認証の公開と IAM の付与は止まらない。**Agent Gateway・Model Armor のロールは H21 で確認する**
  - **2026-09-27: 確定（ユーザー確認）。自分がOwnerで組織なし。必要な権限は自由に設定可能**
- [x] **H10【人】Firebase を設定する**
  - GCP プロジェクトに Firebase を追加 → Hosting を有効化 → Authentication で **Google プロバイダと匿名プロバイダ**を有効化（幹事は Google ログイン＋許可リスト（P6）、**ゲスト（審査員・開発者）は匿名ログイン＝ログイン不要**。将来は Google 認証だけにする（SPEC 13章）。匿名が組織のポリシーで使えるかは ARCHITECTURE V14）→ Web アプリを登録
  - 表示される設定値（`firebaseConfig`）は、自分で `frontend/.env.local` に記入する（コミット禁止・チャットに貼らない）
  - 止まる実装: Web Dashboard のデプロイ・認証
  - **2026-09-27: Firebase の設定自体は完了（ユーザー確認）。ただし「今回は匿名ログインは使わない」という決定**（H2 の審査員ログイン方式の回答と整合。審査員は Google アカウントを使用する）。**匿名認証を前提にしていた上記の記述、SPEC.md 7.6、ARCHITECTURE.md D23・V14 は、Google ログイン（許可リストに載っていないアカウントはゲスト）に合わせて更新済み**

### D. Agent Runtime・Agent Gateway の検証（構成の根幹）

**順序は H21 → H12 → H11。** 先に「使えるか・どのリージョンか」を調べ（H21）、リージョンを仮決めし（H12）、そのうえで実際に動かす実験（H11）をする。H11 の結果でリージョンが外れたら H12 をやり直す。

- [ ] **H21【人】Agent Gateway・Agent Registry・Model Armor を、このプロジェクトで使えるか確認する**（ARCHITECTURE V6・V3）
  - 確認すること: 機能がプレビューかどうか・利用の申請の要否・必要な API の有効化（`networkservices` `agentregistry` `modelarmor` など）・必要なロール（組織のポリシーで止まらないか。H9 と連動）・**対応リージョン**・課金（ハッカソンのクレジットで賄えるか）
  - AI が公式ドキュメントで調べた内容と、Console の画面を突き合わせて、使えるかを判断する
  - 使えない場合の代替は ARCHITECTURE 13章 V6（Model Armor を API で直接呼ぶ形。`clients/model_armor.py` を復活させる）。**合否によって SPEC 10章の書き方が変わる**ので、H11 の前に確認する
  - 止まる実装: Agent Gateway・Agent Registry の Terraform、エージェントの Gateway 設定、`extract-agent`
  - **2026-09-27: 最優先で着手する（ユーザー確認）**
- [x] **H12【決】リージョンを決める**（ARCHITECTURE D5）
  - H21 で分かった対応リージョン（Agent Runtime・Agent Gateway・Model Armor のテンプレート。**Gateway の入口はエージェントと同一プロジェクト・同一リージョンが必須**）と、Gemini・Firestore との組み合わせで決める。日本国内のレイテンシも考慮する
  - **RAG Engine は東京リージョンに未対応の可能性がある**（ARCHITECTURE V3・V11）。未対応なら、RAG Engine だけ別リージョンに置く（`kuroko-api` から呼ぶだけなので Gateway の同一リージョン制約はかからない）。規程の文書は架空なので、データの所在は致命的ではないが、本番化の論点として説明文に書く
  - H11 の結果（V3・V4）で問題が出たら決め直す
  - 止まる実装: Terraform、すべてのデプロイ
  - **2026-09-26: 全体を `us-central1` に決定**（ARCHITECTURE D5）。Memory Bank が `us-central1` で作れなければ `us`。H11（V3）で外れたら決め直す
- [ ] **H11【人】Agent Runtime・Agent Gateway・Agent Registry・Model Armor の最小構成を、AI の手順書に沿って自分の手で Console から構築する**（**2026-09-27決定: Agent Platform のリソース作成・デプロイは学習を兼ねてユーザーが Console で自分の手で行う**。AI は承認を待って自分で実行するのではなく、コードと手順書を用意する側に回る）
  - **AI が用意するもの**: ①最小の ADK エージェント2つのコード（ツールあり／ツールなし。`agent-kuroko` と `agent-extract` の代わり）②最小の FastAPI に MCP サーバー（`/mcp`）を載せた Cloud Run（非公開。こちらは通常どおり Terraform・CI で AI がデプロイする）③エージェントのデプロイスクリプトと、**デプロイ後**の IAM（Agent identity は SA ではなく、デプロイ時に自動発行される principal なので、エンジンIDが決まってから付ける）④**手順書**（[guides/h11_agent_platform_lab.md](guides/h11_agent_platform_lab.md)。画面名・入力する値つき）⑤作成後に確かめることを検証するスクリプト
  - **ユーザーが行うこと**: 手順書に沿って、🖱Console で ①Model Armor のテンプレートを作成 ②Agent Registry に MCP エンドポイントを登録 ③Agent Gateway（入口・出口）を作成。⌨ ④Agent Runtime に最小のエージェント2つをデプロイ（**Console 非対応**のため、AI が用意したスクリプトを自分で実行する。確認は Console の Deployments で行う）
  - **確かめること**（ARCHITECTURE 13章。作成後に AI がスクリプトで検証する）:
    - **V1** エージェントが Agent Gateway 経由で、非公開の Cloud Run の `/mcp` を呼べるか。**`/mcp` が「どのエージェントの呼び出しか」を見分けられるか**（見分けられないと、エージェント間の分離が効かない）
    - **V2** エージェントを別々の Agent identity で動かし、別々の権限を付けられるか
    - **V7** API に MCP サーバーを載せて、非公開の Cloud Run で動くか（Gateway が MCP の `tools/call` を解釈し、ツール名で絞れるか）
    - **V3** 使えるリージョン ／ **V4** 入口・出口・Model Armor を挟んだレイテンシ（`extract-agent` の分を含む。D16 の判断材料）
    - **V8** Gateway の Model Armor が、入口の `stream_query` と出口の MCP の応答で日本語の攻撃文を検知するか
    - **V9** ADK のコールバックによる「確認待ち」と再開: `before_tool_callback` でツールを止めて state に書けるか（MCP ツールにも効くか）、`kuroko-api` が state を読み・更新して、同じセッションで新しいターンを呼べるか（Gateway の入口を通して）
  - デプロイは5〜10分かかる。Agent Gateway・Model Armor のテンプレートの作成は課金されるので、手順書には課金の見込みも書く
  - 結果を ARCHITECTURE 13章に反映する。V1・V2・V6・V7 が外れた場合の代替案は同章に書いてある
  - 止まる実装: `kuroko_agent/` `payment_agent/` `extract_agent/` のツール認証、`/mcp` の実装、Agent identity の分離
  - **2026-09-27: 最優先で着手する（ユーザー確認）。AI はコード・IAM・手順書の準備を先に進める**
  - **2026-09-27（2回目）: リソースの作成・デプロイ自体はユーザーが Console で自分の手で行う（学習のため。ユーザー指定）。本番の3エージェント・本番の Gateway 設定は別途 H31・H32 で行う**
  - **2026-10-01（ユーザー指定）: 開発と並行して設定する。実験用の部品（`kuroko-mcp-lab`・`lab-agent-*`）は作らず、本番の `kuroko-api` の `/mcp` と `kuroko_agent`・`extract_agent` で確かめる**（H31・H32 の前半を H11 に取り込んだ。`payment_agent` と `payment-api` の `/mcp` は、その実装ができてから H31・H32 で足す）。手順書は本番の名前に書き直した。**今すぐできるのは、gcloud の更新・Model Armor のテンプレート・Gateway 2つの作成**（Registry への登録とデプロイは、AI のコードが揃ってから）

### E. 外部 API・アカウントの申請（リードタイムあり。先に出す）

- [x] **H13【人】駅すぱあと API MCP のアクセスキーを申請する**
  - ハッカソン向けの提供枠の申請手順は、公式ページと Discord で確認する。ダイヤ探索は使えず、経路探索（`plain`）だけ（`company_rules.yaml` の記述どおり）
  - 止まる実装: 帰りやすさの計算（`search_accessible_stations` `search_routes`）
  - **2026-09-27: キー取得・Secret Manager への登録（`ekispert-api-key`）まで完了**（AI が `gcloud secrets versions list ekispert-api-key` で確認。有効なバージョンあり）
  - **2026-09-27（疎通確認。AI）: 認証エラーで失敗**。MCP（`https://api-mcp.ekispert.jp/mcp`、ヘッダー `ekispert-api-access-key`）は 400「不正なアクセスキーです」、REST（`https://api.ekispert.jp/v1/json/station`）も 403「認証エラー」。登録された値は英数字15文字で、前後の空白・改行・引用符はない。**キーの値そのもの（コピー漏れ・別の値）か、キーがまだ有効になっていないことを疑う**。駅すぱあとのマイページ（または申請時のメール）でキーを確かめ、`printf '%s' '<キー>' | gcloud secrets versions add ekispert-api-key --data-file=- --project=kuroko-509311` で新しいバージョンを登録する。登録したら AI が `sandbox/ekispert/smoke.py` で再確認する（`kuroko-api` は `latest` を読むので、新しいリビジョンのデプロイで反映される）
  - **2026-09-27: 疎通OK（ユーザーがキーを登録し直し、バージョン 2。AI が確認）**。MCP の `initialize`・`tools/list` が 200。ツールは6つ（`ekispert_api_get_stations` `ekispert_api_search_routes` `ekispert_api_search_ranges` `ekispert_api_generate_condition` `ekispert_api_get_stations_from_address` `ekispert_api_get_stations_from_geo`）。`search_routes`（`searchType` は `plain` だけ）で新宿→品川を1回探索し、「JR山手線 23分・乗換0・260円」ほか1件が返った。範囲探索（`search_ranges`。`baseList`・`upperMinutes` など）もツールとしてあるので、B18 の `search_accessible_stations` に使える
- [x] **H14【人】ホットペッパー API のキーを申請し、規約を確認する**
  - SPEC 13章の要検証: ハッカソン用途に利用規約が適合するか。**申請できない、または規約に合わない場合**は、Google Maps だけにするか（個室・収容人数の補完をあきらめる）を【決】する
  - 止まる実装: `search_venues` の補完部分
  - **2026-09-27: 利用しないと決定**（ユーザー確認。「ホットペッパーのAPIは利用できないので諦めます」）。`search_venues` は Google Maps だけで進め、個室・収容人数の補完はあきらめる。SPEC・ARCHITECTURE・TASKS・PLAN と `infra/terraform/secrets.tf`（`hotpepper-api-key` の入れ物を削除・apply 済み）に反映済み
- [x] **H15【人】Google Maps Platform（Places API）を有効にし、API キーを作る**
  - キーは Places API だけに制限する。Secret Manager に登録する（P3）
  - 止まる実装: `search_venues`
  - **2026-09-27: 取得・Secret Manager への登録（`maps-api-key`）まで完了**（ユーザー確認）
- [x] **H16【決】AP2 SDK・サンプルを動かす認証方式を決める**（SPEC 13章「要準備」。`ap2_mock/` はやめたが、委任状・請求の署名と検証には AP2 SDK を使う）
  - 推奨: API キーを増やさず、Vertex AI（ADC）で動かす
  - 止まる実装: `payment_api/` の AP2 委任状・請求の検証
  - **2026-09-27: 確定（ユーザー確認）。推奨どおり Vertex AI（ADC）で進める**

### E2. 銀行API（sunabar）と規程の文書（リードタイムあり。先に出す）

- [x] **H22【人】GMOあおぞらネット銀行の個人口座を開設し、sunabar を使えるようにする**（最優先）
  - 個人口座があれば、審査なし・無料で sunabar を使える。口座開設は最短当日（マイナンバーカードの読み取りか自撮り動画で本人確認。**平日14時までの申し込みなどの条件がある**。詳細は [SPEC.md](SPEC.md) 14章のリンク）
  - AI に伝える: 開設したこと（口座番号・パスワードは**貼らない**）。sunabar のクライアント情報は Secret Manager に自分で登録する（P3）
  - 止まる実装: `bank_adapter/` の本実装、H25、支払いのデモすべて
  - **2026-09-27: 申請中（ユーザー確認）。まだ使える状態ではない**。O1（sunabar 疎通ゲート）と B11（銀行本実装）は、この申請が通るまで着手しない。開設でき次第、口座番号・パスワードを貼らずに AI に伝える
  - **2026-10-01: まだ取得中（ユーザー確認）**。エージェントまわりの実装は、`bank_adapter` をダミー（B10 のスタブ）にして先に進める
  - **2026-10-01（2回目）: 完了（ユーザー確認）。sunabar が使えるようになり、口座を10個用意した**。ダミーはやめ、O1・B11 を本線に戻す。次の手順は [guides/h25_sunabar_setup.md](guides/h25_sunabar_setup.md)（口座の割り当て → トークンの登録（P3）→ 疎通の確認（H25））
- [ ] **H23【人】デモ用の sunabar 口座を用意する**（参加者役・幹事役）
  - **2026-10-01: 口座は10個用意済み（ユーザー確認）**。必要なのは幹事1＋振込元7の8口座で、2つは予備（ゲストのデモ用・差し替え用）。**残り**: 口座と登場人物の割り当て（[guides/h25_sunabar_setup.md](guides/h25_sunabar_setup.md) 1章）と、振込元の残高の確認
  - sunabar は **1ユーザーあたり最大10口座**まで追加できる（初期は個人・法人の各1口座）。**振込先も sunabar 内の口座に限る**ので、**幹事の口座も sunabar 口座**にする。デモの参加者10名分は、チームメンバーで分担して用意する。足りなければ参加者を8名に減らす（SPEC 13章）
  - **全口座を1人が持つと、振込ごとの承認も実際には1人が行う**。デモでは「承認する人が数名いる」形にして、残りは早送りにする（H18 のデモ用ユーザーと、どの口座を誰が持つかを対応させる）
  - 止まる実装: 支払いのデモ、`bank-adapter` の口座の対応表の初期データ
- [ ] **H24【人】架空の規程の文書（PDF）を作る**（RAG Engine のコーパスに入れる。SPEC 9.7）
  - **`policies/company_rules.yaml` と同じ内容**にする（抽出結果の正解データとして使うため）。表・段組を含めると、日本語PDFの抽出精度（V11）を確かめられる。AI が下書きを作れる
  - 止まる実装: `retrieve_policy` / `extract_policy_values`、規程の抽出のテスト
  - **2026-09-27: 検証結果を待たず優先して進める（ユーザー確認）**
- [ ] **H25【承】AI が用意する sunabar の疎通実験を承認する**（ARCHITECTURE V10。**最初の1〜2日で通しで確かめる**）
  - **2026-10-01: 手順は [guides/h25_sunabar_setup.md](guides/h25_sunabar_setup.md) 4章**。サンドボックスでは OAuth の流れがなく、口座ごとのトークンをポータルから登録する（下の①の「OAuth の認可」は、トークンの登録に置き換わる）
  - **用意するもの**（AI が sandbox で作る）: 最小のスクリプトと、Cloud Run（`bank-adapter` の試作）
  - **確かめること**: ①OAuth の認可 → 振込依頼 → 承認ページでの承認 → 入出金明細での確認が一通り動くか ②口座を必要な数だけ用意できるか（H23） ③Slack DM のリンクから承認ページへ直接遷移できるか ④承認前に期限が切れた依頼の状態の照会方法と、作り直すときの冪等キー・nonce の扱い ⑤ポーリングの間隔（10分の承認期限に対して十分か）
  - 秘密の値（クライアント情報・トークン）はチャットに貼らない。結果を ARCHITECTURE 13章 V10 と SPEC 13章に反映する
  - **外れた場合**: `bank-adapter` を AP2 サンプルの模擬決済役に差し替えられる形にしてある（V10）。その場合は SPEC 8章・ピッチの言い方を書き換える。**代替は外部の集金・決済サービスではない**
  - 止まる実装: `bank_adapter/` の本実装（先に銀行APIのスタブで `payment_api/` を組める）

- [ ] **H26【人】Memory Bank を、AI の手順書に沿って自分の手で Console から作成し、疎通を確認する**（ARCHITECTURE V12。H25 と並行してよい。**アタッチして読み取る方式**の確認。**2026-09-27決定: リソース作成は学習を兼ねてユーザーが Console で行う**）
  - **AI が用意するもの**: `sa-api` に `memoryEditor`、`agent-kuroko` に `memoryViewer` だけを付与する IAM（Terraform）、**Console 操作の手順書**（リージョン・設定値つき。課金される可能性があるので、作成前に手順書の内容を確認する）、作成後に確かめることを検証する最小のスクリプト
  - **ユーザーが Console で行うこと**: 手順書に沿って Memory Bank を作成する
  - **確かめること**（作成後に AI がスクリプトで検証する）: ①**対応リージョン**（公式ドキュメントでは `global / us / eu`。東京の記載なし。H12・V3・V11 と連動） ②**アタッチ**: ADK の `VertexAiMemoryBankService` を Agent Runtime のエージェントで使えるか（既定か、明示の指定が要るか）。**`agent-kuroko` の identity に読み取り専用のロール `roles/aiplatform.memoryViewer` だけで `load_memory` が動くか**。書き込みができないこと ③**スコープ**: `user_id` = `team:{company_id}:{team_id}` で分離できるか。**`kuroko-api` が直接書いた記憶を、ADK の検索が引けるか**（スコープの指定が一致しないと見つからない） ④**直接書き込み**（会話からの自動生成を使わずに定型の事実を書けるか）と**類似検索**（日本語の品質） ⑤**既存の記憶との統合が、定型の事実を勝手に書き換えないか** ⑥`before_tool` のコールバックで `load_memory` を止められるか
  - 結果を ARCHITECTURE 13章 V12 と SPEC 13章に反映する。**外れた場合**: 統括エージェントに `recall_memory`（MCP ツール。`kuroko-api` が Memory Bank を読んで返す）を持たせる（当初の案）。それも難しければ、Firestore に事実を保存し、読み取りだけを Firestore の検索に差し替える（V12）。その場合は Memory Bank の利用を説明できなくなるので、SPEC 9.8 と提出の説明を書き換える
  - 止まる実装: `backend/src/clients/memory_bank.py` の本実装（書き込み）、`kuroko_agent/` の `load_memory` のアタッチ、`save_memory`（先に Memory Bank のスタブで組める）
  - **2026-09-27: 検証結果を待たず優先して進める（ユーザー確認）**
  - **2026-09-27（2回目）: Memory Bank の作成自体はユーザーが Console で自分の手で行う（学習のため。ユーザー指定）。AI は IAM・手順書・検証スクリプトの準備に専念する**
- [ ] **H27【決】デモ用の「過去のイベントの記憶」（seed）の内容を決める**（SPEC 9.8・13章「要準備」）
  - デモの企画の場面で `load_memory` が引く記憶を、**3件程度**用意する。**文面は定型テンプレートと同じ形**にする（**2026-09-26 に、種類を `venue_record`（実績）と `venue_evaluation`（評価）に変更**。SPEC 9.8。例: 実績「営業1課の歓送迎会（2026/06）で『○○』（渋谷・個室）を8名で利用。1人あたり5,300円（コース5,000円）で予算内。最も遠い人の所要時間は38分。」／評価「営業1課の歓送迎会（2026/06）の『○○』の満足度は平均4.3（7名回答）。幹事は次回も使いたい。良かった点は個室・料理。気になった点はドリンクの提供が遅い。」。**同じ店について、実績と評価を1組にして用意する**と、店舗提案の理由（SPEC 9.9）に実績を添えられる）
  - AI が下書きを作れる。**ストーリー（review 04）の店・金額・チームと矛盾しないこと**を人間が確認する。個人名は入れない
  - 止まる実装: 記憶を使った店舗提案のデモ
  - **2026-09-27: 優先して内容を決める（ユーザー確認）**
- [ ] **H30【人】RAG Engine のコーパスを、AI の手順書に沿って自分の手で Console から作成し、規程PDF（H24）を取り込む**（ARCHITECTURE V11。**2026-09-27新設。リソース作成は学習を兼ねてユーザーが Console で行う**）
  - **AI が用意するもの**: **Console 操作の手順書**（リージョン・埋め込みモデルなどの設定値つき）、コーパスへの取り込みスクリプト（作成済みのコーパスに H24 の規程PDFを流し込むだけ。TASKS.md B27・I9）、日本語PDFの抽出精度を測る検証スクリプト（`company_rules.yaml` を正解データにする）
  - **ユーザーが Console で行うこと**: 手順書に沿って RAG Engine のコーパスを作成し、H24 で作った規程PDFを取り込む
  - **確かめること**: ①**対応リージョン**（東京は未対応の可能性あり。H12・V3・V11 と連動。未対応なら RAG だけ別リージョンに置く） ②日本語PDFの抽出精度（表・段組を含む場合）
  - 結果を ARCHITECTURE 13章 V11 と SPEC 13章に反映する。**外れた場合**: `company_rules.yaml` を正解データ兼フォールバックとして使う（既存の方針どおり）
  - 止まる実装: `retrieve_policy` / `extract_policy_values` の本実装、規程の抽出のテスト
  - 依存: H24（規程PDFの完成）、H12（リージョン）
- [ ] **H31【人】本番の3エージェント（`kuroko_agent` `payment_agent` `extract_agent`）を、AI の手順書に沿って自分の手で Agent Runtime にデプロイする**（**2026-09-27新設**。H11 のゲート実験とは別に、本実装ができたあとの本番デプロイ）
  - **AI が用意するもの**: 3エージェントの本実装コード（B23・B25・B26）、デプロイスクリプトと手順書（`min-instances=1` の指定・Gateway の CA 証明書の組み込み・Memory Bank のアタッチ設定を含む）、**デプロイ後**の IAM（エンジンIDを受け取って Terraform で付ける）、検証スクリプト
  - **ユーザーが行うこと**: 手順書に沿ってデプロイスクリプトを自分で実行し（**Console 非対応**）、Console の Deployments で3つの Identity を確認して、エンジンIDを AI に伝える
  - 依存: H11（ゲート実験が Go であること）、TASKS.md B23・B25・B26（エージェント本実装）
  - 止まる実装: 本番の統括・支払い・抽出エージェントの提供開始
- [ ] **H32【人】本番用の Agent Gateway 設定・Agent Registry 登録・Model Armor テンプレートを、AI の手順書に沿って自分の手で Console から設定する**（**2026-09-27新設**。H11 のゲート実験とは別に、本番の MCP エンドポイントでの設定）
  - **AI が用意するもの**: 本番の MCP エンドポイント一覧（`kuroko-api` / `payment-api` の `/mcp`）、Model Armor テンプレートの内容（**日本語**。開発中は「検査のみ」で始め、P9 の判断後にブロックへ）、必要な IAM（Terraform。`roles/iap.egressor` `modelarmor.calloutUser` など。**`sa-api` に Model Armor の権限は付けない**）、**Console 操作の手順書**、設定後の疎通・検査を確認するテストスクリプト（O6）
  - **ユーザーが Console で行うこと**: 手順書に沿って、本番の MCP エンドポイント・エージェント3つを Agent Registry に登録し、エージェントごとの到達先を絞り込み、Model Armor テンプレートを設定する
  - 依存: H11（ゲート実験が Go であること）、TASKS.md B21（MCP エンドポイント本実装）
  - 止まる実装: 本番の Agent Gateway 経由の通信、P9（Model Armor の検知結果確認）

- [ ] **H28【人】審査員が触れるサンプルと、サンドボックスの初期データを用意する**（SPEC 7.6・13章「要準備」）
  - **サンプルの領収書と予約画面**（画像。**Web の画面からダウンロードできる**もの）。架空の店・金額を、ストーリー（review 04）と合わせる（会計60,300円、コース5,500円×10名など）。**サンプル自体に個人情報を入れない**
  - **サンドボックスの会社「サンプル商事」の初期データ**（架空の規程・デモ参加者・過去の記憶の seed（H27））。AI が下書きを作れる。人間は、ストーリーと矛盾しないことを確認する
  - 審査員向けの**使い方の説明**（画面の案内と、提出物の文章）。「ログイン不要で試せる」「7日で削除される」「送金は sunabar（資金は仮想）」「(B) Slack に参加して承認者を体験できる」を含める
  - 止まる実装: 審査員向けの体験のデモ、`sandbox` の初期データの投入
- [ ] **H29【人】デモ用 Slack ワークスペースの招待リンクを発行し、提出物に記載する**（H17。(B) の体験用）
  - 期限なしの招待リンクにし、審査員が参加できるようにする（Slack App がインストール済みであること）。**参加した審査員が、承認者として按分を承認できる**ように、承認者の割り当て方（審査員の Slack ユーザーを、`sandbox` のイベントの承認者にする方法）を AI と決める（SPEC 7.6・13章）
  - 止まる実装: (B) の体験

### F. Slack（**間に合わなければ後回しでよい**。2026-09-27）

- [ ] **H17【人】デモ用の Slack ワークスペースを作る**
  - 本物の業務ワークスペースは使わない
  - **審査員が参加できるように、招待リンクを発行する**（H29。(B) の体験用）
  - **2026-09-27: 間に合わなければ後回しでよい（ユーザー確認）**。TASKS.md B16 は Phase 2 に回せる。審査員向けデモは sandbox のデモ用代行（B15）で成立させる
  - **2026-09-27（再確認）: 上記の方針でOK（ユーザー確認）**
- [ ] **H18【人】デモ用ユーザー10名を用意し、区分・雇用形態・入社日・社員番号を決める**
  - 内訳: 幹事1、承認者1、参加者6、主役2（[review 04](review/2026-09-13_KUROKO_review_04_story.md) の4章）
  - SPEC の方針: 架空アカウント約6名＋bot の併用で10名を賄う。実アカウントは、メールのエイリアス（例: `名前+yamada@gmail.com`）で作れるか試す
  - ストーリーの数字（会計60,300円、按分、承認者は山田部長など）を review 04 のまま使うなら、その旨を伝えるだけでよい
  - AI に伝える: 各ユーザーの Slack ユーザーID とワークスペースID（秘密ではない）。（幹事は Web で作業するので、**幹事の Slack ユーザーID は Dashboard の許可リストに要らない**。Slack との連携は任意）
  - **各ユーザーに、どの sunabar 口座を割り当てるか**も決める（H23。幹事の口座は sunabar 口座にする）
  - 止まる実装: 出欠・承認・按分のデモデータ、承認者決定のテスト
  - **2026-09-27: 方針でOK（ユーザー確認）**。SPEC の方針（架空アカウント約6名＋bot）とストーリー（review 04）の数字・役職をそのまま使う。実アカウントの作成・sunabar 口座の割り当てなど具体的な準備は H23 と合わせて進める（未着手のため止まる実装は残る）
- [x] **H19【人】Slack App を作る**
  - AI が `slack/manifest.yml`（必要なスコープ・イベント・Interactivity・App Home の設定を含む）を用意する。**Create New App → From an app manifest** で取り込む
  - Request URL（Events・Interactivity）は `kuroko-gateway` のデプロイ後でないと設定できないので、最初は仮の値でよい（P4 で直す）
  - ワークスペースにインストールし、**Bot Token と Signing Secret は自分で Secret Manager に登録する**（P3）。チャットには貼らない
  - 止まる実装: Slack 連携すべて
  - **2026-09-27: App は作成済み、Signing Secret は登録済み。Bot Token が見当たらない**（ユーザー確認。代わりに Client Secret・Verification Token を保有）。**Bot Token（`xoxb-`）は、Bot Token Scopes を設定して「Install to Workspace」を実行した後にだけ表示される**ので、まだその操作をしていない可能性が高い。手順:
    1. [`slack/manifest.yml`](../slack/manifest.yml)（今回用意した）を、そのアプリの **App Manifest** 画面（左メニュー）に貼り付けて保存する（Signing Secret・Client ID・Client Secret はこの操作で変わらない）
    2. **OAuth & Permissions** → 画面上部の **Install to Workspace**（既にインストール済みなら **Reinstall to Workspace**）を実行する
    3. 同じ画面に表示される **Bot User OAuth Token**（`xoxb-` で始まる）をコピーする
    4. 手元のターミナルで登録する（チャットに貼らない）: `printf '%s' 'xoxb-...' | gcloud secrets versions add slack-bot-token --data-file=- --project=kuroko-509311`
    - **Client Secret・Verification Token は今回の構成では使わない**（署名検証は Signing Secret で行う。複数ワークスペースへの配布もしない）。捨ててよい
  - **2026-09-27: 完了（ユーザー確認：「済み」）**。AI 側でも `gcloud secrets versions list slack-bot-token --project=kuroko-509311` で確認し、有効なバージョンが登録済みであることを確認した（作成: 2026-09-27T10:28:57Z）
  - **2026-09-27（追加の作業。P4 と一緒に行う）**: Bot への DM を受け取るため（TASKS B16a）、`slack/manifest.yml` に `im:history`・`message.im`・DM タブを足し、Request URL を `kuroko-gateway` の実 URL にした。**`kuroko-gateway` に B16a のコードがデプロイされてから**、App Manifest に貼り直して保存 → スコープが増えたので **Reinstall to Workspace** を行う（手順は P4）。インストール先のワークスペースがデモ用であることはユーザー確認済み

### G. GitHub

- [x] **H20【人】GitHub のリモートリポジトリを用意する**
  - 公開・非公開は問わない。デフォルトブランチは `main`。Actions を有効にする
  - `owner/name` を AI に伝える（Terraform の WIF 設定に使う）
  - 止まる実装: CI/CD、WIF デプロイ
  - **2026-09-27: 完了（ユーザー確認）。`RyutaMurakami/5th_hackathon_Kuroko`（`git remote -v` で確認済み）、デフォルトブランチ `main`**

---

## 受け渡し（秘密の扱い）

`.gitignore` により、`.env`・`.env.local`・`*.env`・`terraform.tfvars` は git に入らない（`*.example` だけがコミット対象）。

| 情報 | AI への渡し方 | 保存先 |
|---|---|---|
| GCP プロジェクトID・リージョン・GitHub の `owner/name` | チャットで伝えてよい（秘密ではない） | `infra/terraform/terraform.tfvars`、`backend/.env` |
| Firebase の設定値 | **貼らない**。自分で記入する | `frontend/.env.local` |
| Slack の Bot Token・Signing Secret | **貼らない** | Secret Manager に自分で登録。AI にはシークレットの名前だけ伝える |
| **sunabar のクライアント情報、口座番号・取引パスワード** | **貼らない** | クライアント情報は Secret Manager に自分で登録。**口座番号は `bank-adapter` の対応表**（デモ用の初期データは AI がスクリプトで投入するが、値はチャットに貼らず、ファイルで渡す。コミット禁止）。取引パスワードは AI に渡さない（サンドボックスでは任意の文字列でよい） |
| 駅すぱあと・Maps のキー | **貼らない** | 同上（**ホットペッパーは2026-09-27に不採用**） |
| Slack のユーザーID・ワークスペースID（デモ用） | チャットで伝えてよい | デモ用のシードデータ |
| **デモ用 Slack の招待リンク**（H29） | チャットで伝えてよい（秘密ではない。**公開してよいもの**として提出物に書く） | 提出物・Web の使い方の画面 |
| Dashboard の許可リスト（メールアドレス・役割） | 伝えてよい（メールは個人情報なので、コミットするファイルには書かない） | Firestore の `dashboard_users`（初期データは AI がデプロイ後に投入する） |

---

## Phase 1: 実装と並行して必要になる

- [x] **P1【承】`terraform apply` を承認する**（課金されるリソースを作る）
  - **2026-09-26: I1〜I6 の apply を承認・実行（125件の追加）**
  - **2026-09-27（2回目）: シークレットを Cloud Run に渡す apply を承認・実行**（`wire_secrets`（bool）を `wired_secrets`（値のあるシークレットの一覧）に変え、`slack-signing-secret` `slack-bot-token` `ekispert-api-key` `maps-api-key` を渡した。3サービスの変更のみ。`sunabar-client` は値がないので渡していない）
  - **2026-09-27: Agent Gateway・Agent Registry・Model Armor・RAG Engine・Memory Bank 本体のリソースは、Terraform ではなくユーザーが Console で自分の手で作成する（H11・H26・H30・H31・H32）ことに決定したため、P1 の対象から外れる。I7〜I9 で Terraform apply するのは、それらに関する IAM（Agent identity の権限など）だけ**
- [x] **P2【人】`terraform output` の値を GitHub の Variables / Secrets に登録する**（`infra/terraform/README.md` の手順）
  - **2026-09-27: ユーザーが行う（Web のデプロイを GitHub Actions で行うため。TASKS B16a・F4）**。Secrets は不要で、Variables（秘密ではない値）だけを登録する。手順は `infra/terraform/README.md` の「1. GitHub の Variables に登録する」
  - **2026-09-27: 完了（ユーザーがブラウザで登録）**。AI が `gh variable list` で、11個（`GCP_*` 5個・`NEXT_PUBLIC_FIREBASE_*` 6個）が `terraform output` と `frontend/.env.local` の値に一致し、余分な登録がないことを確認した
- [ ] **P3【人】Secret Manager に値を登録する**（`gcloud secrets versions add ...`。Terraform には値を入れない。`.agents/rules/infra.md`）
  - 対象: Slack の Bot Token・Signing Secret、駅すぱあと・Maps のキー、**sunabar のクライアント情報**（H22。**参加者・幹事のアクセストークンは、`bank-adapter` が OAuth のあとに自分で書く**ので、人が登録するのはクライアント情報だけ。**ホットペッパーは2026-09-27に不採用のため対象外**）
  - **2026-09-27時点（AI が `gcloud secrets versions list` で確認）**: 登録済み — `slack-signing-secret`、`maps-api-key`、`slack-bot-token`（H19）、`ekispert-api-key`（H13。2026-09-27 にバージョン 2 で疎通OK）。未登録 — `sunabar-client`（H22 の申請待ち）
  - **2026-09-27: Terraform の管理外の `kuroko_slack_client_secret` `kuroko_slack_signing_secret` `kuroko_slack_verification_token` を削除した**（ユーザー承認。今の構成では使わない）
- [ ] **P4【人】`kuroko-gateway` のデプロイ後、Slack App の Request URL を設定する**
  - Events と Interactivity の URL、App Home の有効化。URL 検証（`url_verification`）が通ることを確認する
  - **2026-10-06（AI が確認）**: B16a のコードは `kuroko-gateway`・`kuroko-api` にデプロイ済みで、シークレット・キューも配線済み。**あとは Slack 側の操作だけ**（下の手順）
  - **2026-09-27**: `slack/manifest.yml` に実 URL（`https://kuroko-gateway-nbymkfmzpq-uc.a.run.app/slack/events`）を記入済み。**CD で `kuroko-gateway` に B16a のコードが載ったあとに**、App Manifest に貼り直して保存（「Verified」になることを確認）→ Reinstall to Workspace → Slack で KUROKO に DM して、返答が来るかを確かめる
- [ ] **P5【承】Cloud Run 5サービスのデプロイを承認する**（CI/CD 経由。**Agent Runtime のエージェント3つは、ユーザーが Console で自分の手でデプロイする（H31）ため、ここには含まない**。2026-09-27変更）
- [ ] **P6【決】Dashboard を見られる人の許可リストを決める**（ARCHITECTURE D8・D14）
  - 1件ごとに、メールアドレス・**役割（幹事のみ。開発者の役割は 2026-09-26 に廃止）**。**幹事の Slack ユーザーIDは要らない**（Web の本人確認は Firebase の UID と `organizer_web_uid` の一致。SPEC 7.3）。**審査員（ゲスト）は許可リストに載せない**（Google ログインだが許可リストなし。**匿名認証は使わない**。2026-09-27決定。SPEC 7.6）
  - 開発者は許可リストに載せない。**審査員も開発者も、ゲスト（許可リストに載っていない Google アカウント）として同じ画面を使う**（SPEC 7.6。サンドボックスの自分のイベントだけ）
- [ ] **P7【決】sunabar の疎通（H25）の結果を見て、送金を sunabar のまま進めるか、AP2 サンプルの模擬決済役に戻すかを決める**（ARCHITECTURE V10。戻す場合も、外部の集金・決済サービスは使わない。SPEC 8章とピッチの言い方を書き換える）
- [ ] **P8【人】デモ用の画像を用意する**（**H28 と同じもの**。審査員が Web でダウンロードして使う）
  - 架空の店舗の**領収書の写真**（会計60,300円）と、**予約完了画面のスクリーンショット**（コース5,500円×10名）
  - 止まる実装: `ocr_receipt` `ingest_reservation` のデモ
- [ ] **P9【人】Model Armor の検知結果を確認する**（SPEC 10章で実装コミット済みの、日本語攻撃文の検知。**Agent Gateway 経由**（エージェントの入口 `stream_query`、MCP の `tools/call` の応答（口コミ本文））。H11 の V8 の結果を踏まえ、AI がテスト結果を出すので、合否を判断する。**検査のみからブロックへの切り替え**もここで決める。検知できない経路があれば、隔離抽出・値の検証で補う（SPEC 10章）または API での直接呼び出しを足す）
- [ ] **P10【人】オフィスアワー（9/29）で確認したいことを整理する**
  - 例: 実行プロダクトの要件に対して、Cloud Run と Agent Runtime を併用する構成で問題ないか / 送金を銀行API（sunabar。サンドボックス）で実行する構成が審査基準③（主要機能がモックでないこと）でどう見られるか / RAG Engine・Memory Bank を使うことが「Google Cloud の AI 技術を使う」に数えられるか / **審査員が触れる形（Google ログイン・サンドボックス・デモ用の代行）が審査上どう見られるか。提出物に Web の URL と Slack の招待リンクをどう書くか** / **Agent Gateway・Agent Registry のハッカソンでの利用条件（プレビューか、クレジットの対象か）** / Agent Gateway 経由の構成が、審査上の「Google Cloud の AI 技術を使う」に数えられるか

---

## Phase 2: 提出前（すべて 10/15 23:59 まで）

- [ ] **S1【人】3分程度のデモ動画を作り、YouTube に公開して URL を控える**（画面録画・編集は人間。台本は review 04 の9章。**Web アプリ**（**チャットでの依頼、領収書のアップロード**、全体フロー・送金・承諾の状況・**按分の内訳**・**振り返りと記憶**）を映すか、映すなら幹事の画面（実名）かゲストの画面（架空の名前）かを決める。送金の画面には「sunabar（サンドボックス）」の注記が出る。**デモには銀行の承認ページへの切り替えが1回入る**。**振り返り・記憶の場面**（幹事が Web で確認して保存する。次の企画で、過去の記憶を根拠に店を提案する。H27 の seed を使う）を、3分の中のどこに置くかも決める（承認する人を数名にして、残りは早送りにする）。説明は「KUROKO が銀行API で送金を実行する」と言い、幹事Pay など外部の集金・決済サービスに任せる言い方をしない）
- [ ] **S2【人】システムアーキテクチャ図の画像を用意する**（ARCHITECTURE 2.3 の図が元になる。AI が画像に書き出せる形にする）
- [ ] **S3【人】プロジェクトの説明文（日本語）を書く**: 対象ユーザー像・課題・ソリューション・特徴。AI が下書きを作れる
- [ ] **S4【人】「主要機能がモックでない」ことの説明を確認する**: 委任状の署名・検証、**銀行API（sunabar）での振込依頼・本人承認・入出金明細での入金確認**、規程の RAG 参照は実装であること。**環境が sunabar のサンドボックスで資金が仮想であることを、正直に明記する**（SPEC 8.8・8.9）。あわせて、電子決済等代行業の登録が本番化に必要であることを書く（専門家への確認が必要）
- [ ] **S5【人】OSS のライセンス表記を確認する**: AP2 は Apache License 2.0。`payment_api/` に取り込む SDK・サンプル由来のコードの出典とライセンスが残っていること
- [ ] **S6【人】Zenn のダッシュボードで GitHub App をインストールし、リポジトリを連携する**
- [ ] **S7【人】デプロイした URL を登録し、アクセスできることを確認する**
- [ ] **S8【任意】Zenn 記事を書く**（カテゴリ「Idea」。URL をプロジェクトに登録する）
- [ ] **S9【人】提出前チェックを実行する**（`/gc-hackathon-vol5` の「提出前チェック」）→ ダッシュボードの提出タブから提出する

### 提出後（12/1 まで）

- デフォルトブランチは提出時点の状態を保つ（続きの開発は別ブランチ）
- リポジトリの連携解除・削除をしない。コンテンツ（リポジトリ・動画）の修正を控える
- **12/1 まで、デプロイしたサービスを止めない**（Cloud Run・Agent Runtime の費用と、Slack トークンの有効期限を含めて管理する）。**sunabar のアクセストークンは、ポータルに30日以上ログインしないと失効する**ので、審査期間中は定期的にログインする（SPEC 8.8）
- 10/28 のファイナリスト発表、10/29〜30 の Builder Day、12/1 の最終ピッチに備える
