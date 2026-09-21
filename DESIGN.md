# KUROKO Web Dashboard — Style Reference
> 黒子の衣装は黒でも、画面は明るく。空色の白地に、墨紺の文字と、澄んだ空色の合図を一点だけ。

> エージェントへ: 本書は **Web Dashboard（`frontend/`）の見た目と部品の規約**。何を表示するか（役割・画面の範囲・権限）の正は [SPEC.md](docs/SPEC.md) 7.3節、データの取り方と配置は [ARCHITECTURE.md](docs/ARCHITECTURE.md) 4.5節。UI を実装するときは、色・余白・角丸・部品を本書のトークンから選び、**値を直接書かない**（`frontend/app/globals.css` の CSS 変数として実装する）。本書にない部品が必要になったら、先に本書へ追記してから実装する。Slack の Block Kit は Slack 側の見た目に従うので対象外。
>
> 旧 `DESIGN.md`（API・データモデル・エージェント設計）は SPEC.md の 3〜4章に統合済みで、本書はそれとは別物（画面の見た目だけを扱う）。

- 作成日: 2026-09-19 / 状態: **提案**（合意が取れたら「提案」を外す）
- 出自: [Refero Styles](https://styles.refero.design/) の DESIGN.md 形式（Sauce Labs のエントリを、ユーザーが書き直した版）を土台にし、**暗い基調と緑を、明るい基調と別のアクセントに置き換えた**。構成（Tokens / Components / Do・Don't / Surfaces / Elevation / Layout / Agent Prompt Guide / CSS）と、ピル型のボタン・大きめの角丸という言語は引き継ぐ。ブランド固有のもの（Aeonik フォント、等角イラスト、ロゴ帯、ヒーロー）は使わない
- 対象: **幹事と審査員（ゲスト）の主導線**（Web アプリ。SPEC 7.3・7.5・7.6）と開発者向けの画面。**依頼と対話（チャット）、アップロード**、確認、閲覧、通知を持つ。入力部品は、幹事の作業（チャットでの依頼、予約画面・領収書のアップロード、予約内容・領収書の金額・店舗候補・予算超過・振り返りのまとめの確認）のためのもの（Chat Panel・Upload Dropzone・Text Input・Checkbox・Radio・Confirmation Card・Venue Choice Card・Retro Summary Card）だけを持つ。**委任・承認・取り消し・振込の実行に当たる操作の部品は持たない**（Slack で行う）
- 本書の文章は日本語で、見出しと Token 名は元の書式（英語）を保つ

**Theme:** light

このダッシュボードの役割は、次の4つが**ひと目でわかる**こと（SPEC 7.3）。あわせて、⑤**按分の内訳**と、⑥**振り返りと、KUROKOが覚えること**も見られる。

1. **誰が幹事か**
2. **飲み会の全体フローの中で、いまどこか**
3. **誰から誰へ、いくら送金されたか**
4. **まだ送金の承諾をしていない人は誰か**

**Web が主導線で、Slack は Human-in-the-loop**（人の判断・同意の場面）。この画面には、**Slack で人の対応が要る場面を「Slack Handoff Card」で示し、Slack を開くリンクを添える**。審査員が触って体験できることを狙うので、最初の画面から迷わず操作できることを優先する。幹事は基本的にこの画面を見るので、**幹事の事務の確認**（エージェントが読み取った予約内容・領収書の金額を見て、直して確定する。店舗候補を選ぶ。**振り返りのまとめを確認して、次回に覚えさせる内容を選ぶ**）も、この画面で行える（SPEC 7.3）。

そのため、見た目は「静かで、明るく、状態が読み取りやすい」ことを最優先にする。空色を帯びた白のキャンバス（`#F3F8FF`）に、白いカードを浮かべ、文字は黒ではなく墨紺（`#12233F`）にする。**黒い面は作らない**（黒は文字の色としてだけ、しかも純黒ではなく墨紺で使う）。合図の色は澄んだ空色（`#4DA3FF`）1色で、主ボタン・選択中・進行中にだけ使う。もう1色、陽だまりの黄（`#FFCD48`）を**「人の対応を待っている」**（承諾待ち・承認待ち）にだけ使う。ボタンとタブは大きく丸く（56px のピル）、カードは 20px。明暗の対比ではなく、**白・空色の薄い帯・細い線**で階層を作る。

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Ink Navy | `#12233F` | `--color-ink-navy` | 本文・見出しの主色。主ボタンの文字色。**黒の代わり**（白地で約 15:1） |
| Slate Blue | `#4A5B78` | `--color-slate-blue` | 表の本文、補助見出し |
| Steel Text | `#5B6B86` | `--color-steel-text` | ラベル、キャプション、メタ情報（白地で約 5.4:1。文字に使える最も薄い色） |
| Mist Blue | `#9AA8BE` | `--color-mist-blue` | プレースホルダー、無効な表示だけ。**文字の主色には使わない**（コントラスト不足） |
| Hairline | `#D9E4F2` | `--color-hairline` | カード・表・区切りの 1px の線 |
| Input Border | `#7A92B5` | `--color-input-border` | 入力・副ボタンの枠線（白地で 3:1 以上。操作できることが見える線） |
| Sky Wash | `#F3F8FF` | `--color-sky-wash` | ページの背景（キャンバス） |
| Pure White | `#FFFFFF` | `--color-pure-white` | カード、表、入力の背景 |
| Sky Subtle | `#F8FBFF` | `--color-sky-subtle` | 表の見出し行、ホバー、入れ子の凹んだ面 |
| Cloud Blue | `#E3F0FF` | `--color-cloud-blue` | 「いまここ」の強調カード（ハイライトカード）、選択中の行、情報の帯、進行中のピルの背景 |
| Azure Cue | `#4DA3FF` | `--color-azure-cue` | **アクセント**。主ボタン、選択中のタブ、進行中の印、進捗バー、フォーカスの枠 |
| Azure Hover | `#2F8FFF` | `--color-azure-hover` | 主ボタンのホバー（墨紺の文字とのコントラスト約 4.8:1） |
| Azure Text | `#1D5FC4` | `--color-azure-text` | リンク、Cloud Blue の上の文字（白地で約 6:1） |
| Sun Signal | `#FFCD48` | `--color-sun-signal` | **人の対応待ち**（承諾待ち・承認待ち・確定待ち）の印。ドット、左の帯、進行中ステップの「待ち」チップ |
| Sun Soft | `#FFF6D6` | `--color-sun-soft` | 対応待ちのピルの背景、承諾待ちの行の薄い色 |
| Sun Text | `#7A5200` | `--color-sun-text` | 対応待ちのピルの文字（Sun Soft の上で約 6.4:1） |
| Lagoon Done | `#12A594` | `--color-lagoon-done` | **完了・送金済み・承諾済み**のドットと進捗バーの完了部分。状態専用で、装飾やボタンには使わない |
| Lagoon Text | `#0B6B5E` | `--color-lagoon-text` | 完了のピルの文字 |
| Lagoon Soft | `#E0F8F3` | `--color-lagoon-soft` | 完了のピルの背景 |
| Coral Alert | `#E5484D` | `--color-coral-alert` | 失敗・ブロックのドット |
| Coral Text | `#B3261E` | `--color-coral-text` | 失敗・ブロックのピルの文字 |
| Coral Soft | `#FFEDEE` | `--color-coral-soft` | 失敗・ブロックのピルの背景 |

### 状態の意味（色の使い分け）

| 色 | 意味 | 例 |
|---|---|---|
| Azure（藍でなく空色） | システムが進めている（進行中） | 出欠収集中、送金中 |
| Sun（黄） | **人の対応を待っている**、または要注意 | 承諾待ち、承認待ち、領収書の確定待ち、取り消し済み |
| Lagoon（青緑） | 確定・完了 | 完了、送金済み、承諾済み |
| Coral（赤） | 止まった・失敗した | ブロック、失敗 |
| Slate（グレー） | 対象外・未着手・終了済みの記録 | 対象外、待機、期限切れ、辞退 |

## Tokens — Typography

**日本語の主書体は Noto Sans JP**、英数字と金額の数字は **Inter**（どちらも `next/font/google` で読み込み、外部の CSS を直接は読み込まない）。ウェイトは 400 / 500 / 700。ID・ハッシュは等幅。

- `--font-sans`: `"Inter", "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", Meiryo, system-ui, sans-serif`（英数字は Inter、日本語は Noto Sans JP に落ちる）
- `--font-mono`: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
- 日本語は**字間を詰めない**（`letter-spacing: 0`）。行間は本文で 1.7。見出し（24px 以上）にだけ `font-feature-settings: "palt"` を使う。表・本文・数字には使わない
- 金額・人数・件数・時刻は `font-variant-numeric: tabular-nums`。**表の数字の列は右揃え**。金額は SPEC に合わせて「3,300円」（`¥` は使わない）。日時は「10/30（金）19:00」
- 見出しは 700、本文は 400、強調は 500。**小さすぎる文字は作らない**（最小は 12px。9px の見出しラベルは使わない）

| Role | Size | Weight | Line Height | Token |
|------|------|--------|-------------|-------|
| caption | 12px | 400 | 1.5 | `--text-caption` |
| label | 12px | 500 | 1.5 | `--text-label` |
| body-sm | 14px | 400 | 1.6 | `--text-body-sm` |
| body | 16px | 400 | 1.7 | `--text-body` |
| body-lg | 18px | 400 | 1.6 | `--text-body-lg` |
| subheading | 20px | 700 | 1.5 | `--text-subheading` |
| heading-sm | 24px | 700 | 1.4 | `--text-heading-sm` |
| heading | 32px | 700 | 1.3 | `--text-heading` |
| stat | 40px | 500 | 1.15 | `--text-stat` |
| mono | 12px | 400 | 1.6 | `--text-mono` |

## Tokens — Spacing & Shapes

**Base unit:** 8px（半分の 4px も使う）　**Density:** comfortable（表は compact）

### Spacing Scale

| Name | Value | Token |
|------|-------|-------|
| 4 | 4px | `--spacing-4` |
| 8 | 8px | `--spacing-8` |
| 16 | 16px | `--spacing-16` |
| 24 | 24px | `--spacing-24` |
| 32 | 32px | `--spacing-32` |
| 40 | 40px | `--spacing-40` |
| 48 | 48px | `--spacing-48` |
| 56 | 56px | `--spacing-56` |
| 64 | 64px | `--spacing-64` |
| 80 | 80px | `--spacing-80` |

### Border Radius

| Element | Value |
|---------|-------|
| buttons | 56px（ピル） |
| tabs | 56px（ピル） |
| status pills / avatars / progress | 999px |
| cards | 20px |
| largeCards（ハイライトカード） | 32px |
| smallElements（バッジ・チップ・入力） | 10px |
| checkbox（Checkbox の四角） | 6px |
| radio（Radio の丸） | 999px |

### Shadows

| Name | Value | Token |
|------|-------|-------|
| md | `0 1px 2px rgba(18, 35, 63, 0.04), 0 4px 16px rgba(18, 35, 63, 0.06)` | `--shadow-md` |
| popover | `0 8px 24px -8px rgba(18, 35, 63, 0.18)` | `--shadow-popover` |
| focus | `0 0 0 3px rgba(77, 163, 255, 0.45)` | `--shadow-focus` |

### Layout

- **Page max-width:** 1200px　**Section gap:** 48px　**Card padding:** 24px（幅 640px 以下は 16px）　**Element gap:** 16px（カードの中）／ 24px（カード同士）
- ページ左右の余白: 24px（幅 640px 以下は 16px）
- 表の行の高さ: 密 40px／通常 48px。**タッチで操作する要素は 44px 以上**
- ブレークポイント: 640px（スマホ）・1024px（詳細画面を2列から1列にする）

## Components

### Primary Pill Button
**Role:** 画面で最も大事な操作（例: 「Slack で開く」）。1画面に1つ。

背景 `--color-azure-cue`、文字 `--color-ink-navy`（**白ではなく墨紺**。空色の上で約 6:1）、16px/500、高さ 44px、余白 12px 24px、角丸 56px、枠なし。ホバーで `--color-azure-hover`。

### Secondary Pill Button
**Role:** 補助の操作（絞り込み、もう1つのリンク）。

背景 `--color-pure-white`、枠 1.5px `--color-input-border`、文字 `--color-ink-navy`、16px/500、高さ 44px、角丸 56px。ホバーで背景 `--color-sky-subtle`。

### Text Button / Link
**Role:** 折りたたみ、コピー、表の題名、関連への移動。

背景・枠なし、文字 `--color-azure-text`、14px/500。下線はホバーのときだけ。無効は `--color-mist-blue` の文字に理由を近くに書く。**破壊的な操作（削除・取り消し・承認）のボタンは作らない。**

### Text Input
**Role:** 幹事の事務の確認で、読み取り結果を直す入力（例: 領収書の合計金額、店名、コース単価）。**Confirmation Card の中でだけ使う。**

背景 `--color-pure-white`、枠 1.5px `--color-input-border`、文字 `--color-ink-navy` 16px/400、高さ 44px、余白 0 12px、角丸 10px。金額は右揃え・tabular-nums で、単位「円」を右に添える。フォーカスで `--shadow-focus`。エラーは枠 `--color-coral-alert`、下に `--color-coral-text` の `caption`。ラベルは上に `label`（`--color-steel-text`）。プレースホルダーは `--color-mist-blue`（**値の代わりにしない**）。

### Info Banner
**Role:** 画面上部の注記（「委任・承認・取り消しは Slack で行います。予約内容と領収書の金額の確認は、この画面でできます。」）

全幅、背景 `--color-cloud-blue`、文字 `--color-ink-navy` 14px、角丸 20px、余白 12px 16px、先頭に情報アイコン。操作が必要な状態（承認待ちなど）には、同じ帯かカードに「Slack で開く」の主ボタンを添える。

### App Header
**Role:** 画面上部のナビゲーション

背景 `--color-pure-white`、下に 1px `--color-hairline`、高さ 64px。左にロゴ（角丸 10px の正方形、背景 `--color-azure-cue`、「黒」の字は `--color-ink-navy`）と `KUROKO`。右に、ログイン中の役割のピル（`幹事` / `開発者`）とアカウント。**開発者の役割では「仮名表示」のピルを必ず出す**（実名を出していないことを示す）。

### Tab Pill Navigation
**Role:** 画面内の切り替え（例: イベント詳細の「送金 / 承諾 / 経緯」をスマホで切り替える）

ピルの並び。選択中: 角丸 56px、背景 `--color-azure-cue`、文字 `--color-ink-navy`。非選択: 背景なし、文字 `--color-steel-text`。余白 10px 20px、14px/500。フィルタや選択は URL のクエリに反映する。

### Eyebrow Label
**Role:** セクションの見出しの上の小さな分類（例: 「全体フロー」「送金」「承諾」）

12px/500、文字 `--color-steel-text`。英字を含む場合だけ `text-transform: uppercase; letter-spacing: 0.04em`。日本語には字間を付けない。

### Standard Card
**Role:** 情報のまとまり（幹事、送金の一覧、承諾の一覧）

背景 `--color-pure-white`、`1px solid --color-hairline`、角丸 20px、余白 24px、`--shadow-md`。見出しは `subheading`、その下に `caption`。カードの中にカードを入れない（入れ子は `--color-sky-subtle` の面にする）。

### Highlight Card
**Role:** 「いまここ」を伝える1枚（全体フローの現在地、承諾待ちの要約）

背景 `--color-cloud-blue`、角丸 32px、余白 32px（スマホ 24px）、影なし、枠なし。**1画面に1〜2枚まで**。Standard Card の間に挟んで、視線の入口にする。

### Stat Block
**Role:** 数字で見せる要約（承諾済み ○ / ○名、送金済み ○ / ○円）

カード内。上に `label`（`--color-steel-text`）、下に数字（`stat`、`--color-ink-navy`、tabular-nums）、隣に単位や補足（`caption`）。状態があるときだけ隣にピルを置く。**数字そのものは色を付けない。**

### Organizer Card（誰が幹事か）
**Role:** 「誰が幹事か」を最初に伝える

Standard Card。左に円のアバター（56px。`--color-cloud-blue` の背景に、名前の頭文字を `--color-azure-text` で）、右に名前（`subheading`）と「幹事」のロールバッジ、その下に `caption` で「承認者: ○○さん ／ 主役: ○○さん」。**開発者の役割では、名前を仮名（`User_001`）にする。**

### Flow Stepper（全体フロー）
**Role:** 「飲み会の全体フローの中で、いまどこか」

SPEC 5章の状態（`planning` … `completed`）を、次の**7つの段階**にまとめて横に並べる。

| 段階 | 含む状態（Event.`status`） |
|---|---|
| ① 出欠・承諾 | `planning` `rsvp` |
| ② 店舗・予約 | `venue` `booked` |
| ③ 開催 | `day_of` |
| ④ 精算 | `receipt` `split` `approval` |
| ⑤ 送金 | `payment` |
| ⑥ 完了 | `completed` |
| ⑦ 振り返り | `retro` `closed` |

- **完了した段階**: `--color-lagoon-done` の円にチェック
- **いまの段階**: `--color-azure-cue` の塗りの円と、`--color-cloud-blue` のラベル背景。段階の名前は 700。**その下に、待っている相手を `--color-sun-soft` のチップで書く**（例: 「承認者 ○○さんの対応待ち」「幹事の領収書の確定待ち」）。システムが進めている間は、チップを出さず「進行中」と書く
- **これからの段階**: `--color-hairline` の輪郭の円と、`--color-steel-text` の文字
- つなぐ線: 完了までは `--color-azure-cue`（2px）、先は `--color-hairline`（2px）
- 幅 1024px 以下は縦に並べる。**色だけで伝えない**（チェック・数字・文字を必ず付ける）

### Payment Table（誰から誰へいくら）
**Role:** 「実際に誰から誰へ、いくら送金されたか」

Standard Card の中の表。上に「**sunabar（サンドボックス）**」のピル（枠 `--color-input-border`、文字 `--color-slate-blue`）と、`caption` で「銀行API経由で送金を実行しています。サンドボックス環境のため資金は仮想です」。**「送金していない」と読める文言にしない。**

- 列: **送金元**（アバター＋名前）→（矢印アイコン）**送金先**（幹事。名前＋「幹事」バッジ） ／ **金額**（右揃え・tabular-nums・`body` 500） ／ **状態**（ステータスピル） ／ **日時**（`caption`・右揃え）
- 状態は `送金済み`（Lagoon。**入出金明細で確認できたもの**）／`銀行での承認待ち`（Sun。残り時間と、作り直した回数を `caption` で）／`ブロック`・`失敗`（Coral。理由を `caption` で下に）／`待機`（Slate）
- 下に合計行: 「送金済み 20,400 / 27,000円」と、進捗バー（Progress）
- 幅 640px 以下は、1行を1枚の小さなカードにして「○○さん → ○○さん  3,300円  ［送金済み］」の形にする

### Consent List（まだ承諾していない人は誰か）
**Role:** 「まだ送金の承諾をしていない人は誰か」

Standard Card の中のリスト。上に「**承諾済み 6 / 8名**」（Stat Block の小さい版）。1行に、アバター＋名前＋ロールバッジ、承諾の状況のピル、右に「上限 6,000円 ／ 期限 11/6」（`caption`・tabular-nums）。

- **承諾待ち・銀行の認可待ちの人の行は、背景を `--color-sun-soft`、左に 4px の `--color-sun-signal` の帯**にして、リストの中でひと目でわかるようにする。並び順は「承諾待ち → 銀行の認可待ち → 取り消し済み → 承諾済み → 対象外」の順
- 署名の原文・口座番号・銀行のアクセストークンは出さない。上限額と期限だけ

### Confirmation Card（幹事の事務の確認）
**Role:** エージェントが読み取った結果（予約内容・領収書の金額）を、幹事が見て、直して、確定する。**幹事の役割で、自分のイベントの、該当するステージのときだけ出す**（開発者には出さない）。

Standard Card。上に Eyebrow Label（「予約内容の確認」「領収書の金額の確認」）と `subheading`。左に読み取り元の画像のサムネイル（角丸 10px、クリックで拡大。**幹事の自分のイベントだけ**）、右に項目ごとの Text Input（店名・日時・人数・コース単価／店名・日付・合計金額）。読み取った値が入った状態で表示し、**直した項目には「修正済み」のチップ**（`--color-cloud-blue`）を付ける。下に Primary Pill Button「この内容で確定する」と Text Button「Slack で開く」。

- 確定の前に、金額の項目の下へ `caption` で「確定すると、承認者の按分の承認に進みます。承認は Slack で行われます」と書く（次の権限を誤解させない）
- **確定できない場合**（値が空・範囲外）は、ボタンを無効にせず、Text Input のエラーで理由を出す
- 確定後は入力を読み取り専用の表示に戻し、「確定済み（幹事・時刻）」の Status Pill（Lagoon）を出す
- 委任・承認・取り消し・振込の実行に当たる操作は、この部品に置かない

### Chat Panel（依頼と対話）
**Role:** 幹事（審査員）が、自然文でイベントを依頼し、KUROKOの質問に答える（SPEC 7.5）。

Standard Card（イベント詳細の上部、または新規の依頼の画面の中央）。上から、①**メッセージの並び**（幹事の発言は右寄せ・背景 `--color-cloud-blue`、KUROKOの発言は左寄せ・背景 `--color-pure-white` と 1px `--color-hairline`。角丸 20px、`body`）②**入力欄**（Text Input の複数行版。送信は Primary Pill Button「送る」。**Enter で改行、Ctrl/⌘+Enter で送信**）。KUROKOが処理中のときは、その発言の位置に Activity Timeline の小さい版を出す。**KUROKOが提案した内容（イベントの計画・店舗候補）は、チャットの中に Confirmation Card として出す**（確認は、文章の返事ではなくボタンで）。空のときは、入力例（「来週金曜、チーム8人で軽く飲みに行きたい」）を `--color-steel-text` で出す。`aria-live="polite"` で新しい発言を読み上げる。

### Upload Dropzone（アップロード）
**Role:** 予約画面・領収書のアップロード（SPEC 7.5）。**Confirmation Card の一部として使う。**

`--color-sky-subtle` の入れ子の面、1.5px の破線の枠 `--color-input-border`、角丸 20px、余白 24px。中央に「ここに画像・PDF をドロップ、または［ファイルを選ぶ］」（Secondary Pill Button）と、`caption` で「JPEG・PNG・PDF／1ファイル 5MB まで」。**ドラッグ中は背景 `--color-cloud-blue`**。アップロード後はサムネイル（角丸 10px）と、進み具合の Progress、続けて読み取り中の表示（「読み取っています…」）、完了したら Text Input に値が入る。**エラーは種類・サイズ・枚数を具体的に**書く（`--color-coral-soft` の帯）。**ゲストの画面では、`caption` で「実在の個人情報や領収書を入れないでください」を必ず出す**。サンプルのダウンロード（Text Button「サンプルの領収書をダウンロード」）を添える（審査員向け）。キーボードで操作できる（ファイル選択のボタンがフォーカスできる）。

### Activity Timeline（KUROKOがいましていること）
**Role:** エージェントが何をしていて、何を待っているかの可視化（SPEC 7.5。PLAN 13章）。

縦の細い線（`--color-hairline`）に沿って、時刻（`mono`）・**何をしたか**（`body-sm`。「店舗を探しています」「規程を確認しました（第3条）」「過去の記憶を参照しました」など、**平易な日本語**）・状態のドット（進行中＝Azure、待ち＝Sun、完了＝Lagoon、ブロック＝Coral）を並べる。**いま進行中の項目は先頭に置き、`--color-cloud-blue` の背景**にする。「人の対応待ち」の項目は、Slack Handoff Card と同じ Sun の帯。開発者の画面では、判断ログのタイムライン（Decision Timeline）と統合してよい。

### Slack Handoff Card（Slack で人の対応が要る場面）
**Role:** **Human-in-the-loop の待ち相手**を伝え、Slack へ橋渡しする（SPEC 7.5）。

`--color-sun-soft` の背景、左に 4px の `--color-sun-signal` の帯、角丸 20px、余白 16px 24px。先頭に Status Pill「Slack で対応待ち」（Sun）、`body` で「**山田部長（承認者）**が、Slack で按分を承認する必要があります」、`caption` で「承認すると、7名の支払いエージェントが委任の範囲内で振込を依頼します」。右に Secondary Pill Button「Slack で開く」。**ゲストの画面で、デモ用の代行が有効なときは、`--color-cloud-blue` の入れ子の帯で「デモ用の代行：架空の承認者が承認します」と明記し、［Slack に参加して承認する］の Text Button を添える**（SPEC 7.6）。**Web には、承認・委任・取り消し・振込を実行するボタンを置かない。**

### Notification Bell（アプリ内通知）
**Role:** 幹事への通知（確認待ち・Slackで人の対応待ち・完了・ブロック・振り返り）（SPEC 7.5）。

App Header の右、アカウントの左。線画のベルのアイコン（20px）と、未読があるときだけ右上に 8px の `--color-azure-cue` のドット（**件数は数字で `aria-label` に**）。押すと Popover（`--shadow-popover`、幅 360px）に、通知を新しい順に最大10件。1件 = 種類の Status Pill（確認待ち＝Sun、Slack で対応待ち＝Sun、完了＝Lagoon、ブロック＝Coral）＋ 定型の文（`body-sm`）＋ 時刻（`caption`）。押すと該当のイベントの位置へ移る。未読は背景 `--color-sky-subtle`。

### Guest Banner（審査員として体験中）
**Role:** ゲストであることと、扱いの注意を、常に伝える（SPEC 7.6）。

画面上部、App Header の下に全幅。背景 `--color-cloud-blue`、`body-sm`、先頭に情報アイコン。「**審査員として体験中です**。ここのデータは架空で、**7日で削除されます**。送金は sunabar（銀行APIのサンドボックス）で、資金は仮想です。」右に Text Button「使い方」。閉じるボタンは付けない（常に見える）。

### Text Input の仲間: Checkbox / Radio
**Role:** Confirmation Card・Venue Choice Card・Retro Summary Card の中だけで使う選択の部品。

- **Checkbox**: 20px の四角（角丸 6px）、枠 1.5px `--color-input-border`、背景 `--color-pure-white`。選んだとき、背景 `--color-azure-cue`・チェックは `--color-ink-navy`。右に `body` のラベル。行全体をクリックできる（高さ 44px 以上）。フォーカスで `--shadow-focus`
- **Radio**: 20px の円、同じ枠。選んだとき、内側に 10px の `--color-azure-cue` の円。同じ形で、複数から1つだけ選ぶとき
- 無効は `--color-mist-blue`。**色だけで伝えない**（チェックの形・ラベルの文字を必ず付ける）

### Split Table（按分の内訳）
**Role:** 「誰がいくら払うのか、なぜその金額か」（SPEC 7.3.1）。**表示専用。Web では再計算も編集もしない。**

Standard Card。`--color-sky-subtle` の入れ子の面を上に置き、**金額の流れ**を横に並べる: `会計金額 → 会社補助 → 按分の対象額 → 1係数あたり`（`label` と `stat` の小さい版。矢印は線画のアイコン。幅 640px 以下は縦）。その下に表。

- 列: **名前**（アバター＋名前。開発者の役割では仮名）／**区分**（部長・マネージャー・メンバー・新入社員。テキスト、`--color-slate-blue`）／**係数**（「×1.5」。右揃え・tabular-nums）／**会社補助**（「対象」／「対象外」。テキストで）／**負担額**（右揃え・tabular-nums・`body` 500。「3,300円」）。**幹事本人と主役の行は、負担額の代わりに「請求なし」**（`caption`・`--color-steel-text`）を出す
- 下に合計行: 「負担額の合計 46,100円」と、端数があるときだけ `caption` で「端数の不足 ○円は ○○さんが負担します」
- **根拠**: `--color-sky-subtle` の入れ子の面に、適用した規程の条文の引用を、`caption` の「規程 第○条」の見出しと `body-sm` で出す（3行を超えたら Text Button「続きを読む」）
- **承認**: 下段に「承認者 ○○さん」と Status Pill（承認待ち＝Sun／承認済み＝Lagoon）、承認済みのときは日時と按分表のハッシュ値（`mono`、先頭8文字）
- 数字の列は右揃えで、`palt` を使わない。行の色分けはしない（承諾の Consent List と違って、状態を表す表ではない）
- 幅 640px 以下は、1行を1枚の小さなカードにして「○○さん（部長・×1.5）  6,300円」の形にする

### Retro Summary Card（振り返り）
**Role:** 「振り返りの集計」と、「KUROKOが次回に覚えること」（SPEC 7.4節・9.8節）。

Standard Card。上に Eyebrow「振り返り」と、Retrospective の Status Pill（`collecting`＝Azure「収集中」／`awaiting_organizer`＝Sun「幹事の確認待ち」／`saved`＝Lagoon「記憶に保存済み」／`skipped`・`expired`＝Slate）。

- **集計**: Stat Block を2つ横に並べる（「回答 6 / 8名」「満足度 4.3 / 5」）。その下に、**良かった点**と**気になった点**を、語彙ごとの件数の横棒（高さ 8px の Progress。色は `--color-azure-cue`。左に語彙の日本語ラベル、右に「4件」）で、上位3つまで出す。**回答が3件未満のときは内訳を出さず**、`--color-cloud-blue` の Info Banner で「回答が3件未満のため、内訳は表示していません（平均のみ）」と書く
- **個人ごとの回答は出さない。**誰が何を書いたかが分かる表示・ツールチップ・エクスポートを作らない
- **記憶の確認**（幹事の役割で、`awaiting_organizer` のときだけ。開発者には出さない）: 見出し「次回に覚えさせる内容」と、`caption` で「覚えさせた内容は、次回の企画で店選びの根拠として表示されます。お金の計算には使われません。個人名・個人ごとの回答は含まれません」。下に**事実の行**を並べる。1行 = Checkbox（既定でチェックあり）＋種類のチップ（「店の評価」／「予算の傾向」。`--color-cloud-blue`）＋定型の文（`body-sm`。**編集できない**）。下に Primary Pill Button「次回に覚えさせる」と Secondary Pill Button「覚えさせない」
- **保存後**（`saved`）: 事実の行を読み取り専用にして、Checkbox を外し、上に Status Pill「記憶に保存済み」と「○件・日時」。保存前の下書きと、そのイベントで保存した記憶だけを出す（Memory Bank の記憶の全件は出さない）

### Venue Choice Card（店舗候補の選択）
**Role:** 提示された店舗の候補から、幹事が1つ選ぶ（SPEC 7.3）。

Standard Card。候補ごとに1行（Radio ＋ 店名 `subheading` ＋ 価格帯 ＋ 帰りやすさ「最大 ○分・平均 ○分」（tabular-nums）＋ 特徴のチップ（「個室」など。`--color-sky-subtle`））。**記憶に基づく理由があるときは、その行の下に `--color-cloud-blue` の帯**を置き、先頭に「記憶」のチップ、`body-sm` で理由（例: 「前回の歓送迎会で個室の評価が高かった」）、右に `caption` で時期（「2026/06」）。**理由がないときは、何も出さない**（空の帯を作らない）。選んだ行は背景 `--color-cloud-blue`。下に Primary Pill Button「この店で進める」。金額・帰りやすさの数字は、記憶によって変えない（記憶は理由の表示だけ）。

### Status Pill
高さ 24px、余白 0 12px、角丸 999px、12px/500、**先頭に 6px のドット**（`currentColor`）。**必ず文字を付ける**。背景は `*-soft`、文字とドットは `*-text`（Sun は文字 `--color-sun-text`、ドット `--color-sun-signal`）。

| データ | 値 → 表示（色） |
|---|---|
| Event.`status` | `planning` 企画中（Slate）／`rsvp` 出欠収集中・`venue` 店舗選定中・`booked` 予約済み・`day_of` 開催当日（Azure）／`receipt` 領収書の確定待ち（Sun）／`split` 按分中（Azure）／`approval` 承認待ち（Sun）／`payment` 送金中（Azure）／`completed` 完了（Lagoon）／`retro` 振り返り中（Azure）／`closed` 終了（Lagoon） |
| 送金（Payment.`status` / Participant.`payment_status`） | `not_applicable` 対象外・`waiting` 待機（Slate）／`awaiting_bank_approval` 銀行での承認待ち（Sun。参加者の承認を待っている）／`completed` 送金済み（Lagoon）／`blocked` ブロック・`failed` 失敗（Coral） |
| 承諾の状況（SPEC 7.3 の表） | 承諾待ち・銀行の認可待ち（Sun）／承諾済み（Lagoon）／取り消し済み（Sun）／銀行での承認待ち（Sun）／送金済み（Lagoon）／止まっている（Coral）／期限切れ・辞退・対象外（Slate） |
| 振り返り（Retrospective.`status`） | `collecting` 収集中（Azure）／`awaiting_organizer` 幹事の確認待ち（Sun）／`saved` 記憶に保存済み（Lagoon）／`skipped` 保存しない・`expired` 期限切れ（Slate） |
| DecisionLogEntry.`action_type` | `ブロック`（Coral）／`待機`（Sun）／`署名`・`確認`（Lagoon）／`判断`・`規程`・`ツール`・`照会`（Azure）／`検査`・`マスキング`・`送信`・`更新`・`記録`（Slate） |

この表の対応は `frontend/lib/status.ts` の1か所に置く。

### Role Badge
Participant.`role`（幹事・承認者・参加者・主役）。高さ 22px、角丸 10px、12px/500。**幹事＝背景 `--color-azure-cue`・文字 `--color-ink-navy`／承認者＝背景 `--color-cloud-blue`・文字 `--color-azure-text`／参加者＝背景 `--color-sky-subtle`・文字 `--color-slate-blue`／主役＝背景なし・枠 `--color-hairline`**。状態のピルと混ざらないよう、ドットは付けない。

### Data Table（一覧の表）
コンテナは角丸 20px・`--color-hairline` の枠。見出し行は `--color-sky-subtle`・`label`。行の区切りは `--color-hairline`。ホバーは `--color-sky-subtle`。1列目は題名（リンク）と、その下に `caption` の補助。**数字の列は右揃え＋tabular-nums**。イベント一覧の列は「題名 ／ 日時 ／ 幹事 ／ いまの段階 ／ 承諾 ○/○ ／ 送金の進捗」。幅 640px 以下はカード形式の行に切り替える。

### Progress
高さ 8px、角丸 999px、背景 `--color-hairline`。進んだ部分は `--color-azure-cue`、**100% に達したら `--color-lagoon-done`**。「20,400 / 27,000円」を必ず添える。

### Decision Timeline（経緯）
折りたたみ（Text Button で開く。開発者の役割では最初から開く）。縦の細い線（`--color-hairline`）に沿って、時刻（`mono`）・`actor`（文字とドット）・`action_type` のピル・`summary` を並べる。`ブロック` の項目は左に 3px の Coral の帯、`待機` は Sun の帯。

### Empty / Loading / Error
- **空**: 中央に `subheading` の一言と、`--color-steel-text` の説明（次に何が起きるとここに出るか）。イラストは使わない
- **読み込み**: 表とカードの形をした `--color-hairline` のスケルトン。`prefers-reduced-motion` ではアニメーションを止める
- **エラー**: `--color-coral-soft` の帯に、何が失敗したかと再読み込みのリンク。**ID・トークン・個人情報を出さない**
- **権限なし**: 「この画面を見る権限がありません」と、見られる画面へのリンク。存在するかどうかが推測できる文言にしない

## 画面の構成（案）

役割ごとの範囲は SPEC 7.3 が正。**幹事と開発者は同じ画面**で、範囲（幹事は自分のイベントだけ・開発者は全イベント）と名前（実名／仮名）だけが違う。

| 画面 | 部品 | 「わかること」 |
|---|---|---|
| **はじめる（`/`）** | Guest Banner、Chat Panel（依頼の入力）、Primary Pill Button「ログイン不要で試す」／Secondary「Google でログイン」 | 依頼から始められる |
| イベント一覧（`/events`） | Info Banner、Data Table、Status Pill、Progress | ②いまの段階、④承諾の数、③送金の進捗、（幹事の列で）①幹事 |
| イベント詳細（`/events/[id]`） | **Chat Panel と Activity Timeline** → Organizer Card → Highlight Card（Flow Stepper と待ち相手）→ **Slack Handoff Card（人の対応待ちのときだけ）**→ **Confirmation Card（Upload Dropzone を含む）・Venue Choice Card（幹事の役割で、確認待ちのときだけ）**→ Stat Block ×3（承諾 / 送金 / 待ち）→ Payment Table と Consent List（2列。幅 1024px 以下は1列）→ **Split Table（按分の内訳。`split` 以降）**→ **Retro Summary Card（振り返り。`completed` 以降）**→ Decision Timeline（折りたたみ） | ①幹事 ②全体フロー ③誰から誰へいくら ④承諾していない人 ⑤按分の内訳 ⑥振り返りと記憶（＋幹事の事務の確認） |

## Do's and Don'ts

### Do
- **文字は墨紺（`#12233F`）、面は白と空色の薄い色**にする。暗い面を作らない
- 空色（`#4DA3FF`）は、主ボタン・選択中・進行中・進捗バー・フォーカスの枠にだけ使う。**主ボタンの文字は墨紺**（白ではない）
- 黄（`#FFCD48`）は「人の対応を待っている」ことにだけ使う。承諾待ちの人は、行の背景と左の帯でひと目でわかるようにする
- ボタンとタブは 56px のピル、カードは 20px、ハイライトカードは 32px
- 状態は必ず「ドット＋文字」。完了・送金済み・承諾済みは青緑（Lagoon）、失敗・ブロックは赤
- 金額・件数は tabular-nums で右揃え。「3,300円」の書き方で統一する。送金の一覧には常に「**sunabar（サンドボックス）**：銀行API経由で送金を実行。資金は仮想」を出す
- すべての操作できる要素にフォーカスの枠（`--shadow-focus`）を出す。キーボードだけで一通り操作できるようにする
- 開発者の画面は仮名のまま。「仮名表示」のピルを出す
- **Slack で人の対応が要る場面は、Slack Handoff Card で待ち相手を出す。**「次に何をすればよいか」を、Web の画面だけで分かるようにする
- **ゲストの画面には Guest Banner を常に出し、アップロードには「実在の個人情報を入れないでください」を添える**
- **按分の内訳は表示専用**。数字は API の値をそのまま出し、Web で再計算しない。区分・係数・負担額・根拠の条文を、同じ表の中で読めるようにする
- 記憶に基づく理由は、`--color-cloud-blue` の帯と「記憶」のチップで、**理由の表示だけ**に使う

### Don't
- **黒い背景・暗いテーマ・純黒（`#000000`）を使わない**（視認性を落とす）。暗い色は文字（墨紺）だけ
- **緑をアクセントにしない。**青緑（Lagoon）は「完了・送金済み・承諾済み」の状態専用で、ボタン・帯・装飾には使わない
- 新しい色相を足さない（空色・黄・青緑・赤とグレーだけ）。虹色のアバターにしない
- `--color-mist-blue` を文字の主色にしない（コントラスト不足）
- 影を `--shadow-md` より強くしない。グラデーションを使わない。カードの中にカードを入れない
- 本文のウェイトを 400 未満、見出しを 700 超にしない。日本語の字間を詰めない・数字の列に `palt` を使わない
- **Web に、委任・承認・取り消し・振込の実行に当たるボタンや入力を置かない**（Slack で行う。Human-in-the-loop）。入力は、チャット（Chat Panel）・アップロード（Upload Dropzone）・幹事の確認（Confirmation Card など）の中だけ。**ゲストの画面でも同じ**（デモ用の代行は、Web のボタンではなく、システム側の代行として表示だけする）
- 開発者の画面に実名を出さない。開発者の画面には Confirmation Card・Venue Choice Card・Retro Summary Card の確認部分も出さない。
- **振り返りの個人ごとの回答**（誰が何を書いたか）と、**Memory Bank の記憶の全件**を出さない。記憶の文面を、幹事が編集できる入力にしない（含める・含めないだけ）トークン・口座番号・署名の原文・好みの生データをどの画面にも出さない
- 「sunabar（サンドボックス）」の注記を、送金の一覧から外さない。**「送金していない」「模擬」と読める文言にしない**

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| 0 | Sky Wash | `#F3F8FF` | ページの背景（キャンバス） |
| 1 | Pure White | `#FFFFFF` | Standard Card、表、入力 |
| 2 | Cloud Blue | `#E3F0FF` | Highlight Card、Info Banner、選択中の行 |
| 3 | Sky Subtle | `#F8FBFF` | 表の見出し行、ホバー、カード内の入れ子の面 |

## Elevation

- **Standard Card:** `--shadow-md` ＋ 1px `--color-hairline`
- **Highlight Card / Info Banner:** なし（背景の色で区別する）
- **Popover:** `--shadow-popover`
- **Focus:** `--shadow-focus`（キーボードフォーカスは必ず見える）

## Imagery

写真・イラスト・グラデーションは使わない。アイコンは**線画（線の太さ 1.5px、16px または 20px）**で、色は文字と同じ。意味を文字なしで伝えるアイコンには `aria-label` を付ける。アイコンのライブラリを追加する場合は、依存を増やす前に [PLAN.md](docs/PLAN.md) に理由を書く。アバターは円に頭文字（`--color-cloud-blue` の背景、`--color-azure-text` の文字）で、色を人ごとに変えない。ロゴは「黒」の1文字（`--color-azure-cue` の角丸 10px の正方形に、墨紺の字）。

## Layout

ページの背景は Sky Wash で、内容は最大幅 1200px の中に、白いカードとして並べる。ヘッダーは白で、下に細い線。イベント詳細は、上から「Organizer Card → Highlight Card（全体フロー）→ Confirmation Card（幹事の役割で確認待ちのときだけ）→ Stat Block の並び → Payment Table と Consent List の2列 → Split Table → Retro Summary Card → 経緯（折りたたみ）」。幅 1024px 以下は1列にし、幅 640px 以下は表をカード形式の行にする。カード同士の間隔は 24px、セクション間は 48px。Highlight Card の空色の薄い帯が、白いカードの列の中で視線の入口になる。

## Agent Prompt Guide

**Quick Color Reference**
- text: #12233F（墨紺。純黒は使わない）／secondary text: #4A5B78／muted: #5B6B86
- canvas: #F3F8FF／card: #FFFFFF／highlight band: #E3F0FF／border: #D9E4F2
- primary action: #4DA3FF（文字は #12233F）／waiting-on-human: #FFCD48／done: #12A594／failed: #E5484D

**Example Component Prompts**

1. Primary Pill Button を作る: 背景 #4DA3FF、文字 #12233F、16px/500、高さ 44px、余白 12px 24px、角丸 56px、枠なし。ホバーで #2F8FFF。
2. Consent List の行を作る: 高さ 56px、左にアバター（円 40px、背景 #E3F0FF、頭文字 #1D5FC4）と名前 16px/500 と Role Badge、右に承諾の状況の Status Pill と「上限 6,000円」（12px、tabular-nums、右揃え）。承諾待ちの行は背景 #FFF6D6、左に 4px の #FFCD48 の帯。
3. Flow Stepper を作る: 7つの段階（出欠・承諾／店舗・予約／開催／精算／送金／完了／振り返り）を横に並べる。完了は #12A594 の円にチェック、いまは #4DA3FF の円とラベル背景 #E3F0FF・文字 700、その下に #FFF6D6 のチップで「承認者 ○○さんの対応待ち」。先は輪郭 #D9E4F2 の円。線は 2px。
4. Payment Table を作る: 上に「sunabar（サンドボックス）」のピルと「銀行API経由で送金を実行しています。資金は仮想です」。列は 送金元 → 送金先（幹事）／金額（右揃え、tabular-nums、16px/500）／状態のピル／日時（12px、右揃え）。下に「送金済み 20,400 / 27,000円」と Progress（高さ 8px、#4DA3FF、100% で #12A594）。
5. Highlight Card を作る: 角丸 32px、背景 #E3F0FF、余白 32px、影なし。上に Eyebrow Label（12px/500、#5B6B86）、その下に 24px/700 の墨紺の見出し。
6. Confirmation Card を作る: Standard Card。上に Eyebrow「領収書の金額の確認」と 20px/700 の見出し。左に領収書のサムネイル（角丸 10px）、右に Text Input（高さ 44px、枠 1.5px #7A92B5、角丸 10px。金額は右揃え・tabular-nums、右に「円」）。直した項目に「修正済み」チップ（#E3F0FF）。下に Primary Pill Button「この内容で確定する」と、`caption` で「確定すると、承認者の按分の承認に進みます。承認は Slack で行われます」。

## Light Rhythm

暗い面と明るい面の交互ではなく、**白いカードと、空色の薄い帯（Cloud Blue）が、空色を帯びた白の地（Sky Wash）に並ぶ**ことで階層を作る。暗い帯は作らない。Highlight Card は、白いカードが続く中で視線を止める「間」として使い、連続させない。同じ面の中に同じレベルの面を入れない（カードの中の凹みは Sky Subtle にする）。

## Quick Start

### CSS Custom Properties

```css
:root {
  /* Colors */
  --color-ink-navy: #12233F;
  --color-slate-blue: #4A5B78;
  --color-steel-text: #5B6B86;
  --color-mist-blue: #9AA8BE;
  --color-hairline: #D9E4F2;
  --color-input-border: #7A92B5;
  --color-sky-wash: #F3F8FF;
  --color-pure-white: #FFFFFF;
  --color-sky-subtle: #F8FBFF;
  --color-cloud-blue: #E3F0FF;
  --color-azure-cue: #4DA3FF;
  --color-azure-hover: #2F8FFF;
  --color-azure-text: #1D5FC4;
  --color-sun-signal: #FFCD48;
  --color-sun-soft: #FFF6D6;
  --color-sun-text: #7A5200;
  --color-lagoon-done: #12A594;
  --color-lagoon-text: #0B6B5E;
  --color-lagoon-soft: #E0F8F3;
  --color-coral-alert: #E5484D;
  --color-coral-text: #B3261E;
  --color-coral-soft: #FFEDEE;

  /* Typography — Font Families */
  --font-sans: "Inter", "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", Meiryo, system-ui, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  /* Typography — Scale */
  --text-caption: 12px;     --leading-caption: 1.5;
  --text-label: 12px;       --leading-label: 1.5;
  --text-body-sm: 14px;     --leading-body-sm: 1.6;
  --text-body: 16px;        --leading-body: 1.7;
  --text-body-lg: 18px;     --leading-body-lg: 1.6;
  --text-subheading: 20px;  --leading-subheading: 1.5;
  --text-heading-sm: 24px;  --leading-heading-sm: 1.4;
  --text-heading: 32px;     --leading-heading: 1.3;
  --text-stat: 40px;        --leading-stat: 1.15;
  --text-mono: 12px;        --leading-mono: 1.6;

  /* Typography — Weights */
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-bold: 700;

  /* Spacing */
  --spacing-unit: 8px;
  --spacing-4: 4px;
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-56: 56px;
  --spacing-64: 64px;
  --spacing-80: 80px;

  /* Layout */
  --page-max-width: 1200px;
  --section-gap: 48px;
  --card-padding: 24px;
  --element-gap: 16px;
  --gutter: 24px;
  --header-height: 64px;
  --row-height-dense: 40px;
  --row-height: 48px;

  /* Border Radius */
  --radius-buttons: 56px;
  --radius-tabs: 56px;
  --radius-full: 999px;
  --radius-cards: 20px;
  --radius-largecards: 32px;
  --radius-smallelements: 10px;

  /* Shadows */
  --shadow-md: 0 1px 2px rgba(18, 35, 63, 0.04), 0 4px 16px rgba(18, 35, 63, 0.06);
  --shadow-popover: 0 8px 24px -8px rgba(18, 35, 63, 0.18);
  --shadow-focus: 0 0 0 3px rgba(77, 163, 255, 0.45);

  /* Surfaces */
  --surface-canvas: #F3F8FF;
  --surface-card: #FFFFFF;
  --surface-band: #E3F0FF;
  --surface-subtle: #F8FBFF;
}

@media (max-width: 640px) {
  :root {
    --gutter: 16px;
    --card-padding: 16px;
  }
}
```

Tailwind は現状の `frontend/` に入っていない。導入する場合は、上の値を `@theme` にそのまま写す（値を変えない）。ダークテーマは作らない。テンプレートの `globals.css` にある `prefers-color-scheme: dark` の切り替えは削除する。
