# KUROKO 引き継ぎガイド

> エージェントへ: 本書は、**このアプリをほとんど知らないメンバー**が、作業を引き継ぐための入口。細部は書かず、「何があるか・誰が何をできるか・次に何をするか」と、詳しい文書への道案内に絞る。実装や運用の状態が変わったら、4章（いま動くもの）・5章（誰が何をできるか）・8章（残りの作業）を直す。仕様は [SPEC.md](SPEC.md)、構成は [ARCHITECTURE.md](ARCHITECTURE.md) が正。
>
> 最終更新: 2026-10-11（提出締切は **2026-10-15 23:59**）

## 1. 30秒でわかる KUROKO

KUROKO は、**会社の歓送迎会の幹事の仕事を、AIエージェントが引き受ける**アプリです。

1. 幹事が Web で「来週金曜、8人で渋谷で」と依頼する
2. KUROKO が参加者に Slack で出欠を聞き、店を提案する
3. 開催後、領収書の写真から、会社の規程に沿って割り勘（按分）を計算する
4. 承認者が Slack で承認すると、各自の銀行口座から幹事へ振込を依頼し、入金まで確認する

いちばん大事な設計は **「AIはお金に触れない」** です。AI（LLM）がするのは、聞く・探す・提案する・説明する、まで。金額の計算・承認者の決定・署名・振込は、すべてふつうのコードが行います。コードを直すときも、この線は越えないでください。

提出用の説明文は [submission.md](submission.md) にあります。全体像をつかむには、まずこれを読むのが早いです。

## 2. 登場人物（デモの物語）

架空の会社「サンプル商事」の歓送迎会です。10人が登場します。

| 役 | 人（システム上の ID） | すること |
|---|---|---|
| 幹事 | 高橋（`takahashi`） | Web で依頼する。店に立て替えて払い、あとで全員から振込を受け取る |
| 承認者（部長） | 山田（`yamada`） | 按分を Slack で承認する。自分も支払う |
| 参加者 | 佐々木・伊藤・渡辺・中村・小林・加藤 | Slack で出欠と委任に答える。支払う |
| 主役（歓迎・送別される人） | 松本・井上 | 負担は0円。支払わない |

- **支払うのは7人**（山田＋参加者6人）。受け取るのは幹事の高橋です。
- デモでは、この10人を**1つの Slack アカウント（オーナーのもの）がすべて演じます**。
- **実際に銀行で振込を承認するのは、加藤の1人ぶんだけ**です。残りの6人の振込は、システムが「承認済み」として代行します（6章）。

## 3. システムの全体像

```
幹事（Web）   ─▶ kuroko-dashboard ─┐
参加者（Slack）─▶ kuroko-gateway  ─┼─▶ kuroko-api ─▶ payment-api ─▶ bank-adapter ─▶ 銀行（sunabar）
                                    │        ▲
                                    │        │ MCP（AI が使ってよい道具だけ）
                                    └─▶ AIエージェント（kuroko-agent / extract-agent）
```

| 部品 | 置き場所（フォルダ） | 一言でいうと |
|---|---|---|
| `kuroko-dashboard` | `frontend/` | 幹事が使う Web 画面（Next.js） |
| `kuroko-gateway` | `backend/` | Slack からの通知の受付。すぐ受け取って後ろに流すだけ |
| `kuroko-api` | `backend/` | **本体**。按分の計算、検査（Policy Gate）、イベントの進行、Slack への送信 |
| `payment-api` | `payment_api/` | 支払いの係。委任状を確かめて、振込を依頼する。入金を確かめる |
| `bank-adapter` | `bank_adapter/` | 銀行の窓口。**口座番号と銀行のトークンは、ここにしかない** |
| `kuroko-agent` | `kuroko_agent/` | 会話を担当する AI（統括エージェント） |
| `extract-agent` | `extract_agent/` | 自由記述を決まった語彙に直すだけの AI（道具を持たない） |
| インフラ | `infra/terraform/`・`infra/agent_platform/` | Google Cloud の設定（Terraform）と、AI のデプロイ用スクリプト |

- 上の5つ（`kuroko-…`・`payment-api`・`bank-adapter`）は Cloud Run、AI の2つは Agent Platform の Agent Runtime で動いています。
- 銀行は **sunabar**（GMOあおぞらネット銀行の実験用の環境）です。**お金は仮想**で、実際のお金は動きません。
- Google Cloud のプロジェクトは `kuroko-509311`、リージョンは `us-central1`、Web の URL は <https://kuroko-509311.web.app> です。

## 4. いま動くもの・動かないもの（2026-10-11）

| 段階 | 状態 | 補足 |
|---|---|---|
| Web で依頼 → 計画の確定 | 動く | `/verify` の画面。「シナリオの進行」のカードが、次にすることを示す |
| Slack で出欠・委任 | 動く | 1つの Slack アカウントに、人数分のカードが届く |
| 店の提案（駅すぱあと・Google Maps） | 動く | 予約の読み取りは仮（手で入力する） |
| 領収書の読み取り → 按分 | 動く | 読み取りに失敗したら、手で入力できる |
| 按分の承認（Slack） | 動く | |
| 請求 → 振込の依頼 → 入金の確認 | **コードはそろった。実機での通しは未実施** | 6章。オーナーの操作が要る |
| 振り返り（満足度の収集） | 一部 | Slack での収集はある。Web での確認（`confirm_retro`）は未実装 |
| 規程の文書検索（RAG）・記憶（Memory Bank） | 未実装 | TASKS B27・B28 |
| 支払い専用の AI（`payment_agent`） | 未実装 | TASKS B25。いまは `payment-api` のコードが手順を進める |
| 審査員（ゲスト）向けの代行 | 未実装 | TASKS B15 |

**注意**: [TASKS.md](TASKS.md) のチェック欄（`[ ]`）は、完了していても付いていないものがあります。各行の末尾にある日付つきのメモ（「2026-10-09 完了…」など）のほうが正確です。

## 5. 誰が何をできるか（重要）

**オーナー（リポジトリと Google Cloud の持ち主。GitHub: `RyutaMurakami`）しかできない操作があります。** とくに、送金まわりはほとんどがそうです。作業を始める前に、ここを確かめてください。

| 操作 | できる人 | 理由 |
|---|---|---|
| コードを書く・ローカルでテストする・PR を出す | **全員** | リポジトリに招待されていれば可（リポジトリは private） |
| PR をマージする（マージすると自動でデプロイされる） | オーナー（承認する人） | `main` に入ると GitHub Actions が Cloud Run にデプロイする |
| Web の画面を触る（<https://kuroko-509311.web.app>） | **全員** | Google ログインで入れる。いまは全員が「ゲスト」扱い（自分で作った試し用のイベントだけ見える） |
| **sunabar にログインして、振込を承認する** | **オーナーだけ** | 口座・ログインID・取引パスワードは、オーナー個人の銀行口座にひもづく。**共有しない・聞かない** |
| **sunabar のトークンの登録・更新** | **オーナーだけ** | Secret Manager の `sunabar-tokens`。30日ログインしないと失効する |
| デモの Slack で、カードのボタンを押す | **オーナーだけ**（いまの設定） | 10人ぶんの宛先が、オーナーの Slack ID になっている（Firestore の `config/slack_users`） |
| `terraform apply`（Google Cloud の設定の変更） | オーナー（または権限をもらった人） | 止まっている定期実行の再開なども、これで行う |
| AI エージェントのデプロイ・Agent Platform の Console の操作 | オーナー | オーナーが自分で行う方針（[guides/agent_platform_next_steps.md](guides/agent_platform_next_steps.md)） |
| Google Cloud のログ・Firestore を見る | 権限をもらった人 | 自分に権限があるかは、オーナーに確認する |

**オーナーがいなくても進められる作業**

- コードの変更と、その単体テスト（銀行も Slack も、テストでは偽物に差し替わる）
- Web の画面（`frontend/`）の改善。`NEXT_PUBLIC_DATA_SOURCE` を `api` にしなければ、ダミーデータで動く
- 文書（提出用の説明文、README、図）
- ローカルでの支払いの流れの確認。`bank_adapter/.env.example` のとおり `BANK_MODE=stub` にすると、メモリ上の偽の銀行で動く

**オーナーに頼む必要がある作業**

- 実機での通し（Slack のボタン、sunabar での承認）
- デプロイが絡む確認（マージ、`terraform apply`、エージェントの再デプロイ）
- 秘密の値に触れること全般（**トークン・口座番号・パスワードは、チャットにも PR にも書かない**）

## 6. 送金のしくみと、デモでの扱い

### 流れ

```
①参加者が Slack で「委任」に同意（上限額・支払先・期限）   … payment-api が委任状に署名して保存
②承認者が Slack で按分を承認
③kuroko-api が請求を作る（検査を通ったときだけ。鍵で署名）
④payment-api が委任状と請求を検査して、bank-adapter に振込を依頼
⑤本人が銀行（sunabar のサイト）で、10分以内に振込を承認        … ここだけ人が銀行で操作する
⑥payment-api が1分ごとに確認し、本人の出金明細で確かめて「完了」
⑦kuroko-api が幹事の入金明細で、全員ぶんを確かめてイベントを「完了」
```

### デモでは、⑤を1人ぶんだけにしている

7人ぶんを、口座ごとにログインし直して10分以内に承認するのは現実的でないので、こうしています（[SPEC.md](SPEC.md) 8.10）。

| | 加藤（`acct08`） | ほかの6人 |
|---|---|---|
| ④ 振込の依頼 | 本物の sunabar に送る | **銀行に送らず、`bank-adapter` が「承認済み」と記録する** |
| ⑤ 銀行での承認 | **オーナーが sunabar のサイトで承認する（1回）** | 不要 |
| Slack の通知 | 「銀行で承認してください」→「入金を確認しました」 | 「入金を確認しました」だけ |
| 画面の表示 | 支払い済み | 支払い済み（見た目は同じ） |
| ①〜④・⑥・⑦ の検査 | 行う | **同じコードで行う**（省略しない） |

- だれを実機にするかは、`bank-adapter` の環境変数 `DEMO_LIVE_PAYER_LABELS`（Terraform の `demo_live_payer_labels`。いまは `acct08`）で決まります。空にすると、全員が実機になります。
- 代行した振込は、Firestore（データベース `bank`）の `simulated_transfers` に残ります。**sunabar の画面には出ません**（出るのは加藤の1件だけ）。
- 人に説明するときは、**「銀行は実験用の環境で、お金は仮想」「実際に銀行で承認するのは1人ぶんで、残りは代行」**の2点を必ず伝えてください。

### 通すときに、オーナーがすること

手順の全体は [guides/demo_run.md](guides/demo_run.md) です。オーナーの操作だけを抜き出すと、こうなります。

1. 定期実行（`payment-poll`。1分ごとの確認）を再開する。いまは止めてある（`terraform.tfvars` の `scheduler_paused = false` → `terraform apply`）
2. Web で依頼し、計画を確定する
3. Slack に届くカード（出欠・委任）を、人数分押す
4. Web で店を選び、予約を確定し、「開催が終わった」を押し、領収書をアップロードして確定する
5. Slack で、按分を承認する（山田の分）
6. **加藤の口座のログインIDで sunabar のサイトに入り、10分以内に振込を承認する**（`acct08` に、加藤の負担額以上の残高が要る）
7. 1〜2分待つと、入金が確認されて、イベントが「完了」になる
8. 終わったら、定期実行を止める（`scheduler_paused = true`）

### うまくいかないとき

| 症状 | 見るところ |
|---|---|
| 「銀行で承認してください」が届かない | 委任（①）が全員ぶんそろっているか。按分の承認（②）が済んでいるか |
| 承認したのに完了にならない | 定期実行が止まったままではないか。10分を過ぎていないか（過ぎると自動で作り直され、もう一度通知が届く。最大2回） |
| 代行のはずの人が、いつまでも承認待ち | `bank-adapter` に新しいコードがデプロイされているか。`DEMO_LIVE_PAYER_LABELS` が入っているか |
| だれの入金かわからない、と出る | 口座の対応表（データベース `bank` の `accounts`）が、[guides/h25_sunabar_setup.md](guides/h25_sunabar_setup.md) 1章の割り当てと合っているか |

ログは、次のコマンドで見られます（権限が要ります）。

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name=("kuroko-api" OR "payment-api" OR "bank-adapter")' --project=kuroko-509311 --freshness=30m
```

## 7. 開発の始め方

### 進め方のルール（[AGENTS.md](../AGENTS.md)）

- **文書が先、コードが後。** 仕様を変えるときは、先に [SPEC.md](SPEC.md) などを直してから実装します。
- **秘密はコミットしない**（`.env`、`terraform.tfvars`、`*.local.json`、鍵のファイル）。
- 試し書きは `sandbox/`（Git の管理外）に置きます。
- `main` に直接 push せず、ブランチを切って PR を出します。PR では CI（lint・テスト・ビルド）が走ります。

### 手元で動かす

```bash
# Python の部品（backend / payment_api / bank_adapter / kuroko_agent / extract_agent）は、どれも同じ
cd backend            # ほかの部品も、フォルダ名を変えるだけ
uv sync
uv run ruff check .   # lint
uv run pytest         # テスト

# Web
cd frontend
npm install
npm run dev           # http://localhost:3000
npm run lint && npm run typecheck && npm run build   # PR の前に通す
```

テストは、銀行・Slack・Google Cloud を偽物に差し替えて動くので、**権限がなくても全部通せます**。

### コードの読み方

Cloud Run の部品は、どれも同じ層の作りです。

```
src/routers/    入口（URL）
src/services/   中身のロジック   ← まずここを読む
src/clients/    外部（銀行・Slack・Google の API）との通信
src/db/         データの保存と読み出し
src/models/     データの型
```

最初に読むとよいファイル:

| 知りたいこと | ファイル |
|---|---|
| イベントが、どの事実で次の段階に進むか | `backend/src/services/lifecycle.py` |
| 請求と、入金の確認 | `backend/src/services/billing.py` |
| お金を動かす前の検査 | `backend/src/services/policy_gates.py`、`payment_api/src/services/policy_gate.py` |
| 支払いの状態の進み方 | `payment_api/src/services/payments.py` |
| デモでの振込の代行 | `bank_adapter/src/clients/demo_bank.py` |
| Web の「次にすること」の案内 | `backend/src/services/scenario_hint.py` |

## 8. 残りの作業（提出まで）

優先の高い順です。詳しくは [TASKS.md](TASKS.md)（AI・開発のタスク）と [human_task.md](human_task.md)（人のタスク）にあります。

| 優先 | 作業 | できる人 | 参照 |
|---|---|---|---|
| 1 | **実機での通し**（依頼 → 入金の確認）と、見つかった不具合の修正 | オーナー（操作）＋全員（修正） | [guides/demo_run.md](guides/demo_run.md)、TASKS O10 |
| 2 | **デモ動画（3分）** の撮影と公開 | オーナー（操作）＋全員（台本・編集） | human_task S1 |
| 3 | **提出用の説明文**の仕上げ（実装に合わせて直す） | 全員 | [submission.md](submission.md) |
| 4 | **README** をテンプレートの文面から書き直す。OSS のライセンス表記 | 全員 | TASKS O17 |
| 5 | **アーキテクチャ図**を、いまの実装に合わせる | 全員 | TASKS O18、[diagrams/](diagrams/) |
| 6 | リポジトリの公開設定・Zenn との連携・提出前チェック・提出 | オーナー | human_task S6・S9 |
| 7 | 審査員向けの使い方の案内 | 全員（文面）＋オーナー（公開） | human_task H28・H29、TASKS F10 |
| 余力があれば | 振り返りの Web での確認、Slack でイベントを指定しなくても話せるようにする、攻撃文のテストの数字 | 全員 | TASKS B7・F7・O6・O11 |

時間が足りないときは、**1〜3 と 6 を優先**してください。RAG・Memory Bank・支払い専用の AI は、提出用の説明文では「今後の実装」としています。

## 9. 文書の地図

| 知りたいこと | 文書 |
|---|---|
| 何を作っているか・なぜか | [PLAN.md](PLAN.md)（冒頭の「現行版の要約」だけでよい） |
| 提出フォームに書く文章 | [submission.md](submission.md) |
| 仕様（データ・API・支払いの流れ） | [SPEC.md](SPEC.md)（支払いは8章、検査は6章） |
| システムの構成・権限 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 開発のタスクと進み具合 | [TASKS.md](TASKS.md) |
| 人がするタスク（アカウント・提出） | [human_task.md](human_task.md) |
| 実機で通す手順 | [guides/demo_run.md](guides/demo_run.md) |
| 銀行（sunabar）の準備 | [guides/h25_sunabar_setup.md](guides/h25_sunabar_setup.md) |
| AI エージェントまわりの設定と確認の結果 | [guides/agent_platform_next_steps.md](guides/agent_platform_next_steps.md) |
| 画面のデザインの決まり | [../DESIGN.md](../DESIGN.md) |

## 10. 困ったら

- **秘密の値が必要になったら、作業を止めてオーナーに頼む。** 自分で探したり、聞き出したりしない。
- **お金・承認者・支払先を AI に決めさせる変更は、しない。** 迷ったら、先にオーナーに相談する。
- 仕様がわからない・選択肢が複数あるときは、仮で作らずに確認する。
