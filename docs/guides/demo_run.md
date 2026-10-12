# デモの通し（サンプル商事の歓送迎会）の実行手順

> エージェントへ: 本書は、Slack・銀行（sunabar）・請求・入金の確認を、実機で通して動かす手順（TASKS B30・O7）。**コードのデプロイ（PR → マージ → CD）と `terraform apply`（P1・P5 の承認）が済んでから**行う。結果は TASKS の O10（ストーリーの通しの確認）に書く。

- 作成日: 2026-10-09
- 前提: `kuroko-gateway`・`kuroko-api`・`payment-api`・`bank-adapter` が最新のコードで動いている／Slack App に `slack/manifest.yml` が取り込まれている（Interactivity の URL が有効）／sunabar の10口座に残高がある（[h25_sunabar_setup.md](h25_sunabar_setup.md)）

## 0. 準備（一度だけ）

配役は [SPEC.md](../SPEC.md) 7.6・8.10 のとおり（2026-10-12 に変更）。**幹事 = Web にログインした人**、Slack に実在するのは **赤坂 くらお（`kurao`）と赤くら 花子（`hanako`）の2人だけ**。

1. **仮名の user_id → 口座ラベルの対応表を `bank-adapter` に入れる**（口座番号は入れない）。1番目の口座が幹事、2番目がくらお、3番目が花子。4番目以降の口座は予備で使わない。ほかの参加者は実機の口座を持たないので、代行用のラベル（`demo-<user_id>`）を入れる:

   ```bash
   cd bank_adapter
   cat > accounts.local.json <<'JSON'
   {"kanji":"acct01","kurao":"acct02","hanako":"acct03",
    "sasaki":"demo-sasaki","watanabe":"demo-watanabe","nakamura":"demo-nakamura",
    "kobayashi":"demo-kobayashi","kato":"demo-kato"}
   JSON
   uv run python scripts/seed_accounts.py accounts.local.json   # Firestore の `bank` データベース
   ```
2. **Slack ユーザーの対応表**: Firestore の `config/slack_users` に、**`kurao` と `hanako` の2人だけ**を入れる（値は、それぞれの Slack メンバー ID）。ほかの人は入れない（入れなかった人には、Slack のメッセージが届かず、出欠・委任はデモ用の代行になる）
3. **残高**: `acct02`（くらお）と `acct03`（花子）に、それぞれの負担額以上の残高が要る（会計 49,500円のとき、くらお 2,100円・花子 4,800円）
4. **定期実行を再開する**: `payment-poll`・`collection-poll`（1分ごと）は、ふだん止めている。`terraform.tfvars` の `scheduler_paused = false` にして `terraform apply` する（承認が必要）。終わったら `true` に戻す

## 1. 通し（Web から）

Web の `/verify` で進める。**次にやることは、画面の「シナリオの進行」が示す**。確かめる項目つきの詳しい手順は [e2e_scenario.md](e2e_scenario.md)。

| 手順 | だれが・どこで | 操作 | 確かめること |
|---|---|---|---|
| 1 | 幹事・Web | ログインして、チャットで依頼し、計画を確定する（**開催日は今日**） | 返答を待つあいだ「KUROKOが考えています…」と経過の秒数が出る。確定すると、出欠の依頼に進む |
| 2 | くらお・花子・Slack | DM の「参加して、委任に同意する」を押す（計2枚） | DM が届くのは2人だけ。ほかの5人は、経緯に「デモ用の代行」と出て、回答済みになる。2人が答えると、店の選択に進む |
| 3 | 幹事・Web | 店を選び、予約の内容を確定する | 予約済みになる |
| 4 | 幹事・Web | 「開催が終わった」を押し、領収書をアップロードして、金額を確定する | 按分が計算され、花子に承認依頼が届く |
| 5 | 花子・Slack | 「この按分を承認する」を押す（**花子本人の Slack ユーザーだけが有効**） | 請求が作られ、**くらおと花子にだけ**「銀行で承認してください（10分以内）」の DM が届く |
| 6 | くらお・花子・銀行 | それぞれの口座（`acct02`・`acct03`）で sunabar のサービスサイトに入り、振込を承認する（**10分以内。取引パスワード**） | 承認から1分ほどで「入金を確認しました」の DM。ほかの5人は代行で「支払い済み」 |
| 7 | （自動） | 1〜2分待つ | 幹事口座の入金を全員ぶん確認できると、イベントが「完了」になり、Web に通知が出る |

- 承認の期限（10分）を過ぎた人は、自動で依頼が作り直され（最大2回）、再通知の DM が届く
- 銀行で承認する人を1人に減らすときは、Terraform の `demo_live_payer_labels` を `acct02` だけにする（SPEC 8.10）
- ログの見方: `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name=("kuroko-api" OR "payment-api" OR "bank-adapter")' --project=kuroko-509311 --freshness=30m`

### スクリプトで一部だけ動かす（開発用）

`backend/scripts/seed_demo_event.py`（イベントを直接作る）と `scripts/run_step.py`（`rsvp`・`approval`・`checkouts`・`collections` を、sa-api の身元で Cloud Tasks に積む）は残してある。スクリプトで作るイベントは体験用（`sandbox`）ではないので、**デモ用の代行は働かない**（Slack の対応表に入れた人だけが回答できる）。

## 2. うまくいかないとき

| 症状 | 見るところ |
|---|---|
| ボタンを押しても反応しない | Slack App の Interactivity の URL（`/slack/interactivity`）と、`kuroko-gateway` のログ（署名エラー・`rejected`）。押した人が、DM の宛先の本人か |
| 承認しても請求が作られない | `kuroko-api` のログの `policy gate 6.2 blocked ... failures=[...]`（止めた項目の一覧）。多いのは、承認者の `slack_user_id` の不一致・領収書が幹事の UID で確定していない |
| 請求が `invalid_checkout` で止まる | `payment-api` の `KMS_CLAIM_KEY_VERSION`、`kuroko-api` の請求の署名（`terraform apply` が済んでいるか）。承認済みの按分表が Firestore にあるか |
| 完了にならない | 「手続済」でも、本人の出金明細に確認できないと完了にしない。金額・振込先が一致しているか。`bank-adapter` の `counterparty_user_id` が解決できているか（口座名義が重複していないか） |
