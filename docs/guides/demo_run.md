# デモの通し（サンプル商事の歓送迎会）の実行手順

> エージェントへ: 本書は、Slack・銀行（sunabar）・請求・入金の確認を、実機で通して動かす手順（TASKS B30・O7）。**コードのデプロイ（PR → マージ → CD）と `terraform apply`（P1・P5 の承認）が済んでから**行う。結果は TASKS の O10（ストーリーの通しの確認）に書く。

- 作成日: 2026-10-09
- 前提: `kuroko-gateway`・`kuroko-api`・`payment-api`・`bank-adapter` が最新のコードで動いている／Slack App に `slack/manifest.yml` が取り込まれている（Interactivity の URL が有効）／sunabar の10口座に残高がある（[h25_sunabar_setup.md](h25_sunabar_setup.md)）

## 0. 準備（一度だけ）

1. **仮名の user_id → 口座ラベルの対応表を `bank-adapter` に入れる**（口座番号は入れない）。デモの登場人物 `yamada`・`sasaki`・`takahashi`（幹事）・`ito`・`watanabe`・`nakamura`・`kobayashi`・`kato` に、sunabar の口座 `acct02`〜`acct08`・`acct01` を割り当てる（[h25_sunabar_setup.md](h25_sunabar_setup.md) 1章。幹事 = `acct01`、山田 = `acct02`、佐々木 = `acct03`、…）:

   ```bash
   cd bank_adapter
   cat > accounts.local.json <<'JSON'
   {"takahashi":"acct01","yamada":"acct02","sasaki":"acct03","ito":"acct04","watanabe":"acct05",
    "nakamura":"acct06","kobayashi":"acct07","kato":"acct08"}
   JSON
   uv run python scripts/seed_accounts.py accounts.local.json   # Firestore の `bank` データベース
   ```
2. **登場人物 → Slack ユーザーID の対応表**を作る（コミット禁止。`*.local.json`）。**同じ Slack ユーザーが複数の登場人物を演じてよい**（ボタンは、押した人が宛先の本人のときだけ有効）。主役の `matsumoto`・`inoue` も書く:

   ```bash
   cd backend
   cat > slack_users.local.json <<'JSON'
   {"yamada":"U...","sasaki":"U...","takahashi":"U...","ito":"U...","watanabe":"U...",
    "nakamura":"U...","kobayashi":"U...","kato":"U...","matsumoto":"U...","inoue":"U..."}
   JSON
   ```
3. **デモのイベントを作る**（開催日は今日にする。銀行の明細の期間が開催日から始まるため）:

   ```bash
   uv run python scripts/seed_demo_event.py slack_users.local.json --event-id demo-1
   ```

### 1つの Slack アカウントだけで通す（2026-10-11。検証用）
10 人分の Slack アカウントは要らない。**登場人物 10 人を、すべて自分の Slack アカウント 1 つが演じる**。
- Firestore の `config/slack_users`: 10 人の `user_id`（`yamada`・`sasaki`・`takahashi`・`ito`・`watanabe`・`nakamura`・`kobayashi`・`kato`・`matsumoto`・`inoue`）を、すべて自分の Slack メンバー ID にする（**作成済み**）
- 出欠・委任のボタンは、DM に人数分（承認者・参加者の 7 通ほど）届く。**それぞれのカードのボタンを自分で押す**（ボタンの値は、誰の分かを持っている。押した人が記録上の本人（同じ ID）かを確かめる）
- 按分の承認は、規程で決まった承認者（部長 `yamada`）の分が届く。自分で承認する
- 銀行の口座: `bank` の `accounts` に、[h25_sunabar_setup.md](h25_sunabar_setup.md) 1章の割り当て（幹事 `takahashi → acct01`、`yamada → acct02`、`sasaki → acct03`、`ito → acct04`、`watanabe → acct05`、`nakamura → acct06`、`kobayashi → acct07`、`kato → acct08`）で登録済み（2026-10-11 に、名簿の順で入れていた誤りを直した）
- **銀行で実際に承認するのは1人だけ（既定は加藤 = `acct08`）**。ほかの6人の振込は `bank-adapter` が代行し、承認なしで「支払い済み」になる（SPEC 8.10）。加藤の口座のログインIDで sunabar のサービスサイトに入り、**1回だけ**承認する。加藤の負担額（1,600円ほど）以上の残高が `acct08` に要る

### Web から通す場合の追加の準備
- Firestore の `config/slack_users` に、登場人物（`yamada`・`sasaki`・`takahashi`・`ito`…）→ Slack ユーザーID のドキュメントを作る（同じ Slack ユーザーが複数の登場人物を演じてよい）。幹事の `takahashi`・主役の `matsumoto`・`inoue` にも入れる。
- Web の `/verify`（または `NEXT_PUBLIC_DATA_SOURCE=api` のイベント詳細）で、依頼 → 計画の確定 → 出欠（Slack）→ 店 → 予約 → 開催が終わった → 領収書 → 按分の承認（Slack）→ 銀行での承認 → 入金の確認、の順に進む。**次にやることは、画面の「シナリオの進行」が示す**。

## 1. 通し

| 手順 | 操作 | 確かめること |
|---|---|---|
| 1 | `uv run python scripts/run_step.py rsvp demo-1` | 参加者7名に、出欠＋委任の DM が届く（上限・支払先・期限つき）。幹事・主役には届かない |
| 2 | 各 DM の「参加して、委任に同意する」を押す | メッセージが「同意しました」に変わる。`payment-api` の `mandates` に委任状ができる（App Home に「委任中」） |
| 3 | `uv run python scripts/run_step.py approval demo-1` | 承認者（山田）に、按分案（負担額・負担割合・端数）の承認依頼が届く |
| 4 | 山田の DM の「この按分を承認する」を押す（**山田本人の Slack ユーザーだけが有効**。他の人が押しても何も起きない） | 「承認しました」。続けて請求が作られ、**加藤の分だけ**「銀行で承認してください（10分以内）」の DM が届く |
| 5 | **加藤（`acct08`）の振込だけ**を、sunabar サービスサイトで承認する（**10分以内。取引パスワード**）。`acct08` のログインIDでログインする。ほかの6人は代行されるので、何もしない（SPEC 8.10） | 代行の6人には、1分以内（ポーリング）に「入金を確認しました」の DM が届く。加藤は、承認してから1分以内に届く |
| 6 | `uv run python scripts/run_step.py collections demo-1` | 幹事口座の入金明細で、7名分（27,000円）が「回収済み」になる |

- 承認の期限（10分）を過ぎた人は、自動で依頼が作り直され（最大2回）、再通知の DM が届く
- **Cloud Scheduler の `payment-poll` は、いま止めている**（`scheduler_paused = true`）。手順5の前に、`terraform.tfvars` の `scheduler_paused = false` にして `terraform apply` する（承認が必要）
- ログの見方: `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name=("kuroko-api" OR "payment-api" OR "bank-adapter")' --project=kuroko-509311 --freshness=30m`

## 2. うまくいかないとき

| 症状 | 見るところ |
|---|---|
| ボタンを押しても反応しない | Slack App の Interactivity の URL（`/slack/interactivity`）と、`kuroko-gateway` のログ（署名エラー・`rejected`）。押した人が、DM の宛先の本人か |
| 承認しても請求が作られない | `kuroko-api` のログの `policy gate 6.2 blocked ... failures=[...]`（止めた項目の一覧）。多いのは、承認者の `slack_user_id` の不一致・領収書が幹事の UID で確定していない |
| 請求が `invalid_checkout` で止まる | `payment-api` の `KMS_CLAIM_KEY_VERSION`、`kuroko-api` の請求の署名（`terraform apply` が済んでいるか）。承認済みの按分表が Firestore にあるか |
| 完了にならない | 「手続済」でも、本人の出金明細に確認できないと完了にしない。金額・振込先が一致しているか。`bank-adapter` の `counterparty_user_id` が解決できているか（口座名義が重複していないか） |
