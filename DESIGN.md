# KUROKO Web Dashboard — Style Reference
> 黒子の衣装は黒でも、画面は明るく。アイコンの墨紺と月の黄をそのまま、クリームの白地に、墨紺の文字と、月の黄の合図を一点だけ。

> エージェントへ: 本書は **Web Dashboard（`frontend/`）の見た目と部品の規約**。何を表示するか（役割・画面の範囲・権限）の正は [SPEC.md](docs/SPEC.md) 7.3節、データの取り方と配置は [ARCHITECTURE.md](docs/ARCHITECTURE.md) 4.5節。UI を実装するときは、色・余白・角丸・部品を本書のトークンから選び、**値を直接書かない**（`frontend/app/globals.css` の CSS 変数として実装する）。本書にない部品が必要になったら、先に本書へ追記してから実装する。Slack の Block Kit は Slack 側の見た目に従うので対象外。
>
> 旧 `DESIGN.md`（API・データモデル・エージェント設計）は SPEC.md の 3〜4章に統合済みで、本書はそれとは別物（画面の見た目だけを扱う）。

- 作成日: 2026-09-19 / 状態: **合意済み**（2026-09-23。human_task.md H1b）
- 更新: 2026-09-27 **開発者ページ（`/dev`。SPEC 7.3.2）の部品（Doc Reader・Task Board・Diagram Viewer）と、App Header の「開発者」リンク・ログアウトを追加**。はじめる画面を Google ログインだけにした（匿名認証を使わない決定）
- 更新: 2026-09-25 配色をアプリアイコンに合わせた（墨紺・月の黄・クリーム）。**1画面の情報量を減らす構成**（イベント詳細を「概要＋タブ」にし、チャットを右から開くパネルへ）と、**動き（Motion）**を追加した
- 出自: [Refero Styles](https://styles.refero.design/) の DESIGN.md 形式（Sauce Labs のエントリを、ユーザーが書き直した版）を土台にし、**暗い基調と緑を、明るい基調と別のアクセントに置き換えた**。構成（Tokens / Components / Do・Don't / Surfaces / Elevation / Layout / Agent Prompt Guide / CSS）と、ピル型のボタン・大きめの角丸という言語は引き継ぐ。ブランド固有のもの（Aeonik フォント、等角イラスト、ロゴ帯、ヒーロー）は使わない
- 対象: **幹事とゲスト（審査員・開発者を区別しない）の主導線**（Web アプリ。SPEC 7.3・7.5・7.6）。**依頼と対話（チャット）、アップロード**、確認、閲覧、通知を持つ。入力部品は、幹事の作業（チャットでの依頼、予約画面・領収書のアップロード、予約内容・領収書の金額・店舗候補・予算超過・振り返りのまとめの確認）のためのもの（Chat Panel・Upload Dropzone・Text Input・Checkbox・Radio・Confirmation Card・Venue Choice Card・Retro Summary Card）だけを持つ。**委任・承認・取り消し・振込の実行に当たる操作の部品は持たない**（Slack で行う）
- 本書の文章は日本語で、見出しと Token 名は元の書式（英語）を保つ

**Theme:** light

このダッシュボードの役割は、次の4つが**ひと目でわかる**こと（SPEC 7.3）。あわせて、⑤**按分の内訳**と、⑥**振り返りと、KUROKOが覚えること**も見られる。

1. **誰が幹事か**
2. **飲み会の全体フローの中で、いまどこか**
3. **誰から誰へ、いくら送金されたか**
4. **まだ送金の承諾をしていない人は誰か**

**Web が主導線で、Slack は Human-in-the-loop**（人の判断・同意の場面）。この画面には、**Slack で人の対応が要る場面を「Slack Handoff Card」で示し、Slack を開くリンクを添える**。審査員が触って体験できることを狙うので、最初の画面から迷わず操作できることを優先する。幹事は基本的にこの画面を見るので、**幹事の事務の確認**（エージェントが読み取った予約内容・領収書の金額を見て、直して確定する。店舗候補を選ぶ。**振り返りのまとめを確認して、次回に覚えさせる内容を選ぶ**）も、この画面で行える（SPEC 7.3）。

そのため、見た目は「静かで、明るく、状態が読み取りやすい」ことを最優先にする。**配色はアプリアイコン（`frontend/images/kurko_v1.png`。墨紺の地、月のような黄の円、クリームの文字、黒子の黒）から取る**。アイコンは暗い地だが、**画面は暗くしない**（暗い地に明るい文字の組み合わせは視認性が落ちる）。クリームがかった白のキャンバス（`#F8F5EE`）に、白いカードを浮かべ、文字は黒ではなく墨紺（`#141D2E`。アイコンの地の色）にする。**黒い面・墨紺の大きな面は作らない**（墨紺は文字の色と、主ボタン・選択中のタブ・進行中の円・チェック・ロゴのような**小さな操作部品の塗り**にだけ使い、その上の文字はクリーム）。合図の色は、アイコンの月の黄（`#F8C450`）を**「人の対応を待っている」**（承諾待ち・承認待ち）にだけ使う。ボタンとタブは大きく丸く（56px のピル）、カードは 20px。明暗の対比ではなく、**白・墨紺の淡い帯・細い線**で階層を作る。

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Ink Navy | `#141D2E` | `--color-ink-navy` | 本文・見出しの主色（アイコンの地の色）。主ボタンなど小さな操作部品の塗り。**黒の代わり**（白地で約 17:1） |
| Slate Blue | `#435068` | `--color-slate-blue` | 表の本文、補助見出し |
| Steel Text | `#5A6478` | `--color-steel-text` | ラベル、キャプション、メタ情報（白地で約 6.0:1、Navy Tint の上で約 5.0:1。文字に使える最も薄い色） |
| Mist Blue | `#9AA1AF` | `--color-mist-blue` | プレースホルダー、無効な表示だけ。**文字の主色には使わない**（コントラスト不足） |
| Hairline | `#E6E2D8` | `--color-hairline` | カード・表・区切りの 1px の線 |
| Input Border | `#838DA1` | `--color-input-border` | 入力・副ボタンの枠線（白地で 3:1 以上。操作できることが見える線） |
| Cream Wash | `#F8F5EE` | `--color-cream-wash` | ページの背景（キャンバス） |
| Pure White | `#FFFFFF` | `--color-pure-white` | カード、表、入力の背景 |
| Cream Subtle | `#FBF9F4` | `--color-cream-subtle` | 表の見出し行、ホバー、入れ子の凹んだ面 |
| Navy Tint | `#E8ECF4` | `--color-navy-tint` | 「いまここ」の強調カード（ハイライトカード）、選択中の行、情報の帯、進行中のピルの背景 |
| Cream Text | `#FDFBF4` | `--color-cream-text` | 墨紺の塗りの上の文字（主ボタン・選択中のタブ・幹事バッジ。墨紺の上で約 16:1。アイコンの文字の色） |
| Navy Hover | `#2B3852` | `--color-navy-hover` | 主ボタンのホバー（クリームの文字とのコントラスト約 11:1） |
| Navy Text | `#2B3A5C` | `--color-navy-text` | リンク、Navy Tint の上の文字（白地で約 11:1、Navy Tint の上で約 9.5:1） |
| Sun Signal | `#F8C450` | `--color-sun-signal` | **人の対応待ち**（承諾待ち・承認待ち・確定待ち）の印。ドット、左の帯、進行中ステップの「待ち」チップ、ロゴの地。**白地では 1.6:1 しかないので、必ず文字とセットで使い、色だけで意味を伝えない** |
| Sun Soft | `#FFF3D6` | `--color-sun-soft` | 対応待ちのピルの背景、承諾待ちの行の薄い色 |
| Sun Text | `#7A4E00` | `--color-sun-text` | 対応待ちのピルの文字（Sun Soft の上で約 6.5:1） |
| Lagoon Done | `#12A594` | `--color-lagoon-done` | **完了・送金済み・承諾済み**のドットと進捗バーの完了部分。状態専用で、装飾やボタンには使わない |
| Lagoon Text | `#0B6B5E` | `--color-lagoon-text` | 完了のピルの文字 |
| Lagoon Soft | `#E0F8F3` | `--color-lagoon-soft` | 完了のピルの背景 |
| Coral Alert | `#E5484D` | `--color-coral-alert` | 失敗・ブロックのドット |
| Coral Text | `#B3261E` | `--color-coral-text` | 失敗・ブロックのピルの文字 |
| Coral Soft | `#FFEDEE` | `--color-coral-soft` | 失敗・ブロックのピルの背景 |

### 状態の意味（色の使い分け）

| 色 | 意味 | 例 |
|---|---|---|
| Navy（墨紺の淡い面＋墨紺の点） | システムが進めている（進行中） | 出欠収集中、送金中 |
| Sun（月の黄） | **人の対応を待っている**、または要注意 | 承諾待ち、承認待ち、領収書の確定待ち、取り消し済み |
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
| focus | `0 0 0 2px #FFFFFF, 0 0 0 4px #141D2E` | `--shadow-focus`（白い隙間＋墨紺の輪。白地でも墨紺の塗りの上でも見える） |

### Layout

- **Page max-width:** 1200px　**Section gap:** 48px　**Card padding:** 24px（幅 640px 以下は 16px）　**Element gap:** 16px（カードの中）／ 24px（カード同士）
- ページ左右の余白: 24px（幅 640px 以下は 16px）
- 表の行の高さ: 密 40px／通常 48px。**タッチで操作する要素は 44px 以上**
- ブレークポイント: 640px（スマホ）・1024px（詳細画面を2列から1列にする）

## Components

### Primary Pill Button
**Role:** 画面で最も大事な操作（例: 「Slack で開く」）。1画面に1つ。

背景 `--color-ink-navy`、文字 `--color-cream-text`（クリーム。墨紺の上で約 16:1）、16px/500、高さ 44px、余白 12px 24px、角丸 56px、枠なし。ホバーで `--color-navy-hover`。

### Secondary Pill Button
**Role:** 補助の操作（絞り込み、もう1つのリンク）。

背景 `--color-pure-white`、枠 1.5px `--color-input-border`、文字 `--color-ink-navy`、16px/500、高さ 44px、角丸 56px。ホバーで背景 `--color-cream-subtle`。

### Text Button / Link
**Role:** 折りたたみ、コピー、表の題名、関連への移動。

背景・枠なし、文字 `--color-navy-text`、14px/500。**下線を常に付ける**（文字色 `--color-navy-text` は本文の墨紺と近いので、色だけで区別しない）。無効は `--color-mist-blue` の文字に理由を近くに書く。**破壊的な操作（削除・取り消し・承認）のボタンは作らない。**

### Text Input
**Role:** 幹事の事務の確認で、読み取り結果を直す入力（例: 領収書の合計金額、店名、コース単価）。**Confirmation Card の中でだけ使う。**

背景 `--color-pure-white`、枠 1.5px `--color-input-border`、文字 `--color-ink-navy` 16px/400、高さ 44px、余白 0 12px、角丸 10px。金額は右揃え・tabular-nums で、単位「円」を右に添える。フォーカスで `--shadow-focus`。エラーは枠 `--color-coral-alert`、下に `--color-coral-text` の `caption`。ラベルは上に `label`（`--color-steel-text`）。プレースホルダーは `--color-mist-blue`（**値の代わりにしない**）。

### Info Banner
**Role:** 画面上部の注記（「委任・承認・取り消しは Slack で行います。予約内容と領収書の金額の確認は、この画面でできます。」）

全幅、背景 `--color-navy-tint`、文字 `--color-ink-navy` 14px、角丸 20px、余白 12px 16px、先頭に情報アイコン。操作が必要な状態（承認待ちなど）には、同じ帯かカードに「Slack で開く」の主ボタンを添える。

### App Header
**Role:** 画面上部のナビゲーション

背景 `--color-pure-white`、下に 1px `--color-hairline`、高さ 64px。左にロゴ（アプリアイコン `frontend/images/kurko_v1.png` を縮めた画像。角丸 10px・40px 四方。`public/avatars/kuroko-logo.png`）と `KUROKO`。ロゴの右にナビ（14px/500。「イベント」「開発者」。選択中は `--color-ink-navy`、ほかは `--color-steel-text`。幅 640px 以下は隠す）。右に、ログイン中の役割のピル（`幹事` / `ゲスト`）とアカウント（ゲストも Google ログインだが、**画面には実名・写真を出さず「ゲスト」だけ**表示する。2026-09-27決定）と、Text Button「ログアウト」。アカウントの部分にも、メールアドレスや名前をツールチップで出さない。

### Tab Pill Navigation
**Role:** 画面内の切り替え。**イベント詳細では、概要（Event Summary）の下を「送金・承諾／按分／振り返り／経緯」のタブで切り替え、1画面に出す量を絞る。**

ピルの並び。選択中: 角丸 56px、背景 `--color-ink-navy`、文字 `--color-cream-text`。非選択: 背景なし、文字 `--color-steel-text`、ホバーで `--color-cream-subtle`。余白 10px 20px、14px/500、高さ 44px。**選択中の塗りは、選び直すと次のタブへ滑って移る**（Motion の共有レイアウト。「Motion」節）。選んだタブは URL のクエリ（`?tab=`）に反映する。**最初に選ばれるタブは段階に合わせる**: `split`・`approval` は「按分」、`retro`・`closed` は「振り返り」、それ以外は「送金・承諾」。開発者の役割では「経緯」。まだ中身がないタブ（例: 按分の前の「按分」）も押せるようにし、Empty で「按分が確定すると、ここに出ます」と次に起きることを書く。タブの右に、件数や状態を小さく添えてよい（例:「送金・承諾 5/7」「按分 承認待ち」の Sun のドット）。キーボードでは ←→ で移動できる（`role="tablist"`）。スマホでは横にスクロールできる帯にする

### Eyebrow Label
**Role:** セクションの見出しの上の小さな分類（例: 「全体フロー」「送金」「承諾」）

12px/500、文字 `--color-steel-text`。英字を含む場合だけ `text-transform: uppercase; letter-spacing: 0.04em`。日本語には字間を付けない。

### Standard Card
**Role:** 情報のまとまり（幹事、送金の一覧、承諾の一覧）

背景 `--color-pure-white`、`1px solid --color-hairline`、角丸 20px、余白 24px、`--shadow-md`。見出しは `subheading`、その下に `caption`。カードの中にカードを入れない（入れ子は `--color-cream-subtle` の面にする）。

### Highlight Card
**Role:** 「いまここ」を伝える1枚（全体フローの現在地、承諾待ちの要約）

背景 `--color-navy-tint`、角丸 32px、余白 32px（スマホ 24px）、影なし、枠なし。**1画面に1〜2枚まで**。Standard Card の間に挟んで、視線の入口にする。

### Stat Block
**Role:** 数字で見せる要約（承諾済み ○ / ○名、送金済み ○ / ○円）

カード内。上に `label`（`--color-steel-text`）、下に数字（`stat`、`--color-ink-navy`、tabular-nums）、隣に単位や補足（`caption`）。状態があるときだけ隣にピルを置く。**数字そのものは色を付けない。**

### Organizer Card（誰が幹事か）
**Role:** 「誰が幹事か」を最初に伝える。**イベント詳細では単独のカードにせず、Event Summary の中の1行として出す**（下の記述は、その1行の中身）。

左に円のアバター（56px。`--color-navy-tint` の背景に、名前の頭文字を `--color-navy-text` で）、右に名前（`subheading`）と「幹事」のロールバッジ、その下に `caption` で「承認者: ○○さん ／ 主役: ○○さん」。

### Event Summary（イベント詳細の概要）
**Role:** イベント詳細の最初に、**①誰が幹事か ②全体フローのどこか ③次に誰を待っているか ④幹事がいますること**だけを1枚で伝える。**これ以外（送金の表・承諾の一覧・按分・振り返り・経緯）はタブへ回す。**

Highlight Card（角丸 32px、背景 `--color-navy-tint`）。上から、
1. **見出し行**: 題名（`heading`）と Event.`status` の Status Pill。下に `body-sm` で日時・店名・会社名（ゲストは「体験用（7日で削除）」の枠線ピル）
2. **幹事の行**: アバター（40px）・名前・「幹事」バッジ、`caption` で「承認者: ○○さん ／ 主役: ○○さん」（Organizer Card の中身）
3. **Flow Stepper**（下の節）
4. **Agent Status**（下の節。**いま誰が動いているか**）
5. **次にすること**（あるときだけ。上から順に）: Slack Handoff Card（人の対応待ち）→ 幹事の確認（Confirmation Card・Venue Choice Card。**幹事の役割で、その段階のときだけ**）。どちらもないときは `body-sm` で「いまは KUROKO が進めています。次は○○です」と書く
6. **小さな数字**: 承諾 ○/○名・送金済み ○/○円・人の対応待ち ○名 を、Stat Block の小さい版（`heading-sm`）で横に3つ。押すと該当のタブへ移る

確認の部品（Confirmation Card など）は Standard Card のまま、Highlight Card の**直下**に置く（カードの中にカードを入れない）。

### Agent Status（いま動いているもの）
**Role:** **どのエージェントが、どこで、何をしているか**を審査員に見せる（SPEC 7.3・PLAN 12章）。Event Summary の Flow Stepper の下に置く。**「エージェント」と「エージェントではない仕組み（コード）」を、見た目で区別する**（お金の計算は LLM ではなくコード、という点を伝えるため）。

`--color-pure-white` の小さな行を縦に並べる（角丸 10px、余白 8px 12px、行の間 8px）。上に Eyebrow「いま動いているもの」。1行の中身:
- **状態のドット**（8px）: 動いている＝`--color-ink-navy`（ゆっくり明滅。1.2秒）／待っている＝`--color-sun-signal`（人・相手の対応待ち）／済んだ＝`--color-lagoon-done`。**必ず文で状態が分かるようにする**（色だけで伝えない）
- **種類の印**: エージェントは Role Badge と同じ形の塗り（背景 `--color-ink-navy`・文字 `--color-cream-text`）で「Agent」。**仕組みは、背景なし・枠 1px `--color-input-border`・文字 `--color-slate-blue` で「コード」**（LLM を使わないもの。RAG Engine・Memory Bank のように LLM の外の仕組みも同じ）
- **文**（`body-sm`）: 「**KUROKO Agent** が、店舗を探しています」の形（名前を 700）。**エージェント名は仕様どおり**: `KUROKO Agent`（統括）・`支払い Agent`（参加者の代理）・`隔離抽出 Agent`（ツールなし）。**支払い Agent は参加者ごとに動くので、「小林さんの支払い Agent」と人ごとに出す**。済んだ人が多いときは「5名の支払い Agent が、入金を明細で確認しました」とまとめる。仕組みは「Policy Gate が、…を検査しています」「按分の計算が、…」のように名前を主語にする
- 名前の下に `caption` で役割を1行（「統括」「参加者の代理」「ツールを持たない」「LLM は使っていません」）

最大 5行。動いている・待っているものを先に、済んだものを後ろに置く。**段階が変わると、行が入れ替わる**（フェード＋8px。Motion の `--motion-base`）。空のとき（`closed` など動くものがないとき）は、何も出さず欄ごと隠す。**エージェント名はここだけでなく、Activity Timeline やトーストで新しく足さない**（画面のあちこちに出して情報を増やさない）。

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
- **いまの段階**: `--color-ink-navy` の塗りの円（数字は `--color-cream-text`）と、`--color-navy-tint` のラベル背景。段階の名前は 700。**その下に、待っている相手を `--color-sun-soft` のチップで書く**（例: 「承認者 ○○さんの対応待ち」「幹事の領収書の確定待ち」）。システムが進めている間は、チップを出さず「進行中」と書く
- **これからの段階**: `--color-hairline` の輪郭の円と、`--color-steel-text` の文字
- つなぐ線: 完了までは `--color-ink-navy`（2px）、先は `--color-hairline`（2px）
- 幅 1024px 以下は縦に並べる。**色だけで伝えない**（チェック・数字・文字を必ず付ける）
- **段階が進んだときは動かす**: つなぐ線が次の円まで伸び（400ms）、済んだ円はチェックに変わり（ばね）、いまの円は1回だけ `--shadow-focus` の輪が広がって消える。待ち相手のチップは差し替えのときにフェードする

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
**Role:** エージェントが読み取った結果（予約内容・領収書の金額）を、幹事が見て、直して、確定する。**幹事の役割で、自分のイベントの、該当するステージのときだけ出す**（ゲストは、自分の `sandbox` のイベントで幹事として操作する）。

Standard Card。上に Eyebrow Label（「予約内容の確認」「領収書の金額の確認」）と `subheading`。左に読み取り元の画像のサムネイル（角丸 10px、クリックで拡大。**幹事の自分のイベントだけ**）、右に項目ごとの Text Input（店名・日時・人数・コース単価／店名・日付・合計金額）。読み取った値が入った状態で表示し、**直した項目には「修正済み」のチップ**（`--color-navy-tint`）を付ける。下に Primary Pill Button「この内容で確定する」と Text Button「Slack で開く」。

- 確定の前に、金額の項目の下へ `caption` で「確定すると、承認者の按分の承認に進みます。承認は Slack で行われます」と書く（次の権限を誤解させない）
- **確定できない場合**（値が空・範囲外）は、ボタンを無効にせず、Text Input のエラーで理由を出す（**手入力でも同じ検査**）
- 確定後は入力を読み取り専用の表示に戻し、「確定済み（幹事・時刻）」の Status Pill（Lagoon）を出す。**手入力で確定したときは「確定済み（幹事・手入力・時刻）」**とし、画像が無いことが分かるようにする（判断ログにも「手入力」と残る）
- 委任・承認・取り消し・振込の実行に当たる操作は、この部品に置かない

### Chat Panel（依頼と対話）
**Role:** 幹事（審査員）が、自然文でイベントを依頼し、KUROKOの質問に答える（SPEC 7.5）。

**イベント詳細では KUROKO Panel（右から開くパネル）の中**、新規の依頼の画面（`/`）では中央の Standard Card。上から、①**メッセージの並び**（幹事の発言は右寄せ・背景 `--color-navy-tint`、KUROKOの発言は左寄せ・背景 `--color-pure-white` と 1px `--color-hairline`。角丸 20px、`body`）②**入力欄**（Text Input の複数行版。送信は Primary Pill Button「送る」。**Enter で改行、Ctrl/⌘+Enter で送信**）。KUROKOが処理中のときは、その発言の位置に Activity Timeline の小さい版を出す。**KUROKOが提案した内容（イベントの計画・店舗候補）は、チャットの中に Confirmation Card として出す**（確認は、文章の返事ではなくボタンで）。空のときは、入力例（「来週金曜、チーム8人で軽く飲みに行きたい」）を `--color-steel-text` で出す。`aria-live="polite"` で新しい発言を読み上げる。**動き**: 送ると自分の発言が下から入り、KUROKOの返事は「考えています…」の3点のドット（Navy）のあと、**文字が順に流れて出る**（1秒あたり約60文字。流れ終わるまで読み上げは待つ。`prefers-reduced-motion` では一度に出す）。返事の間、Activity Timeline に作業の項目が1件ずつ追加される

### DM Board（3人ぶんの KUROKO との DM。SPEC 7.7）
**Role:** 体験用・実演用の画面（`/verify`・`/demo`）で、幹事・参加者・承認者の3人ぶんのチャットを、DM のように並べて見せる。

**ページ全体は動かさず、各 DM の発言の流れだけをスクロールする**（画面の高さを、App Header・見出し・3つの DM で分け合う。`body` に `data-chat-page` の画面があるときだけ。1100px 以下では縦に積み、各 DM の高さを画面の中に収める）。1つの DM は、Standard Card と同じ面（`--color-pure-white`・1px `--color-hairline`・角丸 20px）で、上から ①**見出し**（アイコン 40px・名前 `body` 700・役割の caption・Status Pill）②**次にすることの帯**（`--color-sun-soft`。対応が無いときは `--color-cream-subtle`）③**発言の流れ**（背景 `--color-cream-subtle`。ここだけスクロール）④**入力欄**（幹事の DM だけ）。

- **KUROKO の発言**: 左に KUROKO のアイコン（40px の円。`public/avatars/kuroko.png`）、上に「KUROKO」（`body-sm` 700）・「アプリ」の印（`--color-navy-tint`）・時刻（caption・tabular-nums）。吹き出しは `--color-pure-white`・1px `--color-hairline`、角丸は左上だけ 6px・ほかは 20px。**入力欄・ボタンを持つ発言（操作のカード）は、横幅いっぱい**に取り、見出し（`body` 700）・本文（`body-sm`）・入力欄（高さ 40px）・ボタン（高さ 40px の Pill）を縦に並べる
- **自分の発言**: 右寄せ。吹き出しは `--color-ink-navy`・文字 `--color-cream-text`、角丸は右上だけ 6px。**送った画像**は、右寄せで最大 240×320px・角丸は同じ。読み直して画像が手元に無いときは、ファイルの印と「領収書の画像」の文字を出す
- **処理中**: KUROKO の発言の位置に、3つの点（Chat Panel と同じ）と「KUROKO が考えています…」「画像を読み取っています…」「お店を探しています…」を出し、3秒を過ぎたら経過の秒数を添える。**按分の計算中**は、確認していることを4行で出し、済んだ行を `--color-lagoon-text` と「✓」にする
- **入力欄**: 左に画像を送る丸ボタン（44px。送れない段階では薄くして押せなくする）、中央に1行から伸びる入力欄（角丸 20px）、右に Primary Pill Button「送る」。上に、入力の候補（Chat Panel と同じ札）。**Enter で改行、Ctrl/⌘+Enter で送信**。画像の貼り付けは、画像の送信として扱う
- **選べる札**（主役・はい／いいえ）: 高さ 36px の Pill。選んだものは `--color-navy-tint` と 1.5px `--color-ink-navy`
- **デモの終わり**: `--color-lagoon-soft` の面に 1px `--color-lagoon-done`、56px の円に「✓」、`subheading` の見出し、済んだことの箇条書き、Primary Pill Button「最初からやり直す」
- 待たせる操作のボタンは、押してから終わるまで押せなくして、文字を「送信中…」にする

### Upload Dropzone（アップロード・貼り付け）
**Role:** 予約画面・領収書の入力（SPEC 7.5）。**Confirmation Card の一部として使う。**

**入力の方法は、種類によって違う**:
- **予約情報**: Tab Pill Navigation の小さい版で「ファイル／スクリーンショット／手入力」を切り替える（3つ）。最初は「ファイル」
- **領収書**: **ファイルのアップロードだけ**（貼り付けはない）。**読み取れなかったときだけ**、下の「読み取れなかったとき」から手入力に切り替えられる（画像を残す原則を保つため）

**［スクリーンショット］タブ（予約情報だけ）**: 同じ入れ子の面・破線の枠。中央に「ここをクリックして、**Ctrl/⌘+V** で貼り付け」と `caption`「スクリーンショットをコピーしてから貼り付けてください」。枠は `tabindex=0` でフォーカスでき、フォーカスで `--shadow-focus`、貼り付けの準備ができている間は破線の色が `--color-ink-navy` になる。Secondary Pill Button「クリップボードから貼り付ける」も並べる（ブラウザの許可が出る。拒否・非対応のときは、Ctrl/⌘+V を案内）。**このタブでなくても、予約情報の確認カードが「入力待ち」のときは、ページのどこでも Ctrl/⌘+V で貼り付けられる**（入力欄・チャットの入力中は除く）。貼り付けた画像は、ファイルと同じ検査（種類・サイズ・件数）を通り、サムネイルには「貼り付けた画像」と出す。画像でないもの（文字など）を貼ったときは、「画像を貼り付けてください。文字は［手入力］タブへ」と具体的に書く（`--color-coral-soft` の帯）

**［手入力］タブ（予約情報だけ）**: 読み取りの結果と同じ Text Input（店名・日時・人数・コース単価）を、**空のまま**出す。プレースホルダーは入力例（`--color-mist-blue`。値の代わりにしない）。画像のサムネイルの代わりに、`caption` で「画像なしで、自分で入力します。読み取りと同じ検査を通ります」。

**読み取れなかったとき**（予約情報・領収書の共通）: `--color-coral-soft` の帯で「**読み取れませんでした**（○○.png）。画像が小さい・ぼやけているなどの可能性があります。別の画像を試すか、値を手で入力してください」。下に Secondary Pill Button「別のファイルにする」と、Primary Pill Button「手で入力する」を並べる。

--- 以下は、ファイルのアップロード（共通）---

`--color-cream-subtle` の入れ子の面、1.5px の破線の枠 `--color-input-border`、角丸 20px、余白 24px。中央に「ここに画像・PDF をドロップ、または［ファイルを選ぶ］」（Secondary Pill Button）と、`caption` で「JPEG・PNG・PDF／1ファイル 5MB まで」。**ドラッグ中は背景 `--color-navy-tint`**。アップロード後はサムネイル（角丸 10px）と、進み具合の Progress、続けて読み取り中の表示（「読み取っています…」）、完了したら Text Input に値が入る。**エラーは種類・サイズ・枚数を具体的に**書く（`--color-coral-soft` の帯）。**ゲストの画面では、`caption` で「実在の個人情報や領収書を入れないでください」を必ず出す**。サンプルのダウンロード（Text Button「サンプルの領収書をダウンロード」）を添える（審査員向け）。キーボードで操作できる（ファイル選択のボタンがフォーカスできる）。

### Activity Timeline（KUROKOがいましていること）
**Role:** エージェントが何をしていて、何を待っているかの可視化（SPEC 7.5。PLAN 13章）。

縦の細い線（`--color-hairline`）に沿って、時刻（`mono`）・**何をしたか**（`body-sm`。「店舗を探しています」「規程を確認しました（第3条）」「過去の記憶を参照しました」など、**平易な日本語**）・状態のドット（進行中＝Navy、待ち＝Sun、完了＝Lagoon、ブロック＝Coral）を並べる。**いま進行中の項目は先頭に置き、`--color-navy-tint` の背景**にする。「人の対応待ち」の項目は、Slack Handoff Card と同じ Sun の帯。開発者の画面では、判断ログのタイムライン（Decision Timeline）と統合してよい。**置き場所は KUROKO Panel の「いましていること」**。新しい項目は上から滑って入り、少し `--color-navy-tint` に光ってから通常の背景に戻る。長くなるので、最初は新しいものから6件だけ出し、Text Button「すべて表示（○件）」で残りを開く。**デモ用の代行が進めた項目には「デモ用の代行」の枠線ピルを付ける**

### Slack Handoff Card（Slack で人の対応が要る場面）
**Role:** **Human-in-the-loop の待ち相手**を伝え、Slack へ橋渡しする（SPEC 7.5）。

`--color-sun-soft` の背景、左に 4px の `--color-sun-signal` の帯、角丸 20px、余白 16px 24px。先頭に Status Pill「Slack で対応待ち」（Sun）、`body` で「**山田部長（承認者）**が、Slack で按分を承認する必要があります」、`caption` で「承認すると、7名の支払いエージェントが委任の範囲内で振込を依頼します」。右に Secondary Pill Button「Slack で開く」。**ゲストの画面で、デモ用の代行が有効なときは、`--color-navy-tint` の入れ子の帯で「デモ用の代行：架空の承認者が承認します」と明記し、［Slack に参加して承認する］の Text Button を添える**（SPEC 7.6）。**Web には、承認・委任・取り消し・振込を実行するボタンを置かない。** デモ用の代行が有効なとき（ゲストの `sandbox`）は、数秒後に代行が進め、Toast と Activity Timeline に「デモ用の代行」と明記して知らせる（Web のボタンでは進めない）。

### KUROKO Panel（右から開くパネル）
**Role:** イベント詳細で、**Chat Panel と Activity Timeline を本文から外に出し**、必要なときだけ開く（1画面の情報量を減らす）。

- **開くボタン（KUROKO Launcher）**: 画面の右下に固定した Primary Pill Button（墨紺・クリームの文字、高さ 56px、左にアプリアイコンの丸い切り抜き 32px と「KUROKO」）。Demo Toolbar があるときは、その上に浮かせる。**KUROKOに新しい返事や作業があり、パネルが閉じているときは、右上に件数のバッジ**（背景 `--color-cream-text`、文字 `--color-ink-navy`、枠 1.5px `--color-ink-navy`、高さ 20px、12px/700）。バッジが出るときに1回だけ弾む
- **パネル**: 右端から滑って出る（Motion のばね）。幅 `--panel-width`（440px。幅 640px 以下は全幅の下からのシート）、高さは画面いっぱい（ヘッダーの下から）。背景 `--color-pure-white`、左に 1px `--color-hairline`、`--shadow-popover`。本文の上に重ねる（本文は動かさない）。背景は暗くしない（視認性。薄い `--color-cream-wash` を 40% だけ重ねる）
- **中身**: 上に見出し「KUROKO」と閉じるボタン（×、`aria-label`）。その下に Tab Pill Navigation の小さい版で「チャット／いましていること」。いましていることのタブには、進行中・待ちのドットを添える
- **最初から開いている条件**: 段階が `planning`（依頼と計画の確認をチャットで行うため）。それ以外は閉じておく
- Esc で閉じる。開いたら入力欄にフォーカス、閉じたら開くボタンにフォーカスを戻す（`role="dialog"`、`aria-modal` は付けない＝本文も操作できる）

### Toast（操作の結果の短い通知）
**Role:** 幹事が画面で確定・選択・保存したとき、またはデモ用の代行・システムが段階を進めたときに、**結果を短く伝える**（「領収書の金額を確定しました」「デモ用の代行：山田さん（架空）が按分を承認しました」）。

画面の右下（KUROKO Launcher の上）に積む。幅 `--popover-width`（360px。スマホは全幅−32px）、背景 `--color-pure-white`、枠 1px `--color-hairline`、角丸 20px、`--shadow-popover`、余白 12px 16px。先頭に種類の Status Pill（完了＝Lagoon、Slack で対応待ち＝Sun、進行＝Navy、ブロック＝Coral）、`body-sm` の文。下から滑って入り、**5秒で消える**（ホバー・フォーカス中は止める。閉じるボタンあり）。同時に3件まで。**同じ内容をアプリ内通知（ベル）にも1件足す**。`role="status"`（Coral だけ `role="alert"`）。**トーストの中に、委任・承認・取り消し・振込に当たるボタンは置かない**

### Notification Bell（アプリ内通知）
**Role:** 幹事への通知（確認待ち・Slackで人の対応待ち・完了・ブロック・振り返り）（SPEC 7.5）。

App Header の右、アカウントの左。線画のベルのアイコン（20px）と、未読があるときだけ右上に 8px の `--color-ink-navy` のドット（**件数は数字で `aria-label` に**）。押すと Popover（`--shadow-popover`、幅 360px）に、通知を新しい順に最大10件。1件 = 種類の Status Pill（確認待ち＝Sun、Slack で対応待ち＝Sun、完了＝Lagoon、ブロック＝Coral）＋ 定型の文（`body-sm`）＋ 時刻（`caption`）。押すと該当のイベントの位置へ移る。未読は背景 `--color-cream-subtle`。

### Phase Stepper（チャット画面の全体の流れ）
**Role:** 実演・体験のチャット画面の上に、「いまどの段階か」を 5 段階で示す（SPEC 7.7）。

画面上部、操作の帯の下・3人ぶんのチャットの上。5 つの小さなカードを横に並べる（①依頼 ②提案 ③按分 ④承認 ⑤完了）。各カードは、番号つきの Pill・題名（`body-sm` bold）・1 行の説明（`caption`）。いまの段階は枠 `--color-ink-navy`・背景 `--color-sun-soft`・Pill は `--color-ink-navy` 地に `--color-cream-text`。終わった段階は Pill が `--color-lagoon-soft` 地に `--color-lagoon-text`（チェックつき）。1100px 以下は、番号つきの Pill だけにする。
状態との対応: ①`planning` `rsvp` ②`venue` `booked` ③`day_of` `receipt` `split` ④`approval` `payment` ⑤`completed` `retro` `closed`。

**なお、ゲストバナー（「審査員として体験中です…」）は廃止した（2026-10-13）。**

### Text Input の仲間: Checkbox / Radio
**Role:** Confirmation Card・Venue Choice Card・Retro Summary Card の中だけで使う選択の部品。

- **Checkbox**: 20px の四角（角丸 6px）、枠 1.5px `--color-input-border`、背景 `--color-pure-white`。選んだとき、背景 `--color-ink-navy`・チェックは `--color-cream-text`。右に `body` のラベル。行全体をクリックできる（高さ 44px 以上）。フォーカスで `--shadow-focus`
- **Radio**: 20px の円、同じ枠。選んだとき、内側に 10px の `--color-ink-navy` の円。同じ形で、複数から1つだけ選ぶとき
- 無効は `--color-mist-blue`。**色だけで伝えない**（チェックの形・ラベルの文字を必ず付ける）

### Split Table（按分の内訳）
**Role:** 「誰がいくら払うのか、なぜその金額か」（SPEC 7.3.1）。**表示専用。Web では再計算も編集もしない。**

Standard Card。`--color-cream-subtle` の入れ子の面を上に置き、**金額の流れ**を横に並べる: `会計金額 → 会社補助 → 按分の対象額 → 1係数あたり`（`label` と `stat` の小さい版。矢印は線画のアイコン。幅 640px 以下は縦）。その下に表。

- 列: **名前**（アバター＋名前。ゲストは架空のデモ参加者の名前）／**区分**（部長・マネージャー・メンバー・新入社員。テキスト、`--color-slate-blue`）／**係数**（「×1.5」。右揃え・tabular-nums）／**会社補助**（「対象」／「対象外」。テキストで）／**負担額**（右揃え・tabular-nums・`body` 500。「3,300円」）。**幹事本人と主役の行は、負担額の代わりに「請求なし」**（`caption`・`--color-steel-text`）を出す
- 下に合計行: 「負担額の合計 46,100円」と、端数があるときだけ `caption` で「端数の不足 ○円は ○○さんが負担します」
- **根拠**: `--color-cream-subtle` の入れ子の面に、適用した規程の条文の引用を、`caption` の「規程 第○条」の見出しと `body-sm` で出す（3行を超えたら Text Button「続きを読む」）
- **承認**: 下段に「承認者 ○○さん」と Status Pill（承認待ち＝Sun／承認済み＝Lagoon）、承認済みのときは日時と按分表のハッシュ値（`mono`、先頭8文字）
- 数字の列は右揃えで、`palt` を使わない。行の色分けはしない（承諾の Consent List と違って、状態を表す表ではない）
- 幅 640px 以下は、1行を1枚の小さなカードにして「○○さん（部長・×1.5）  6,300円」の形にする

### Retro Summary Card（振り返り）
**Role:** 「振り返りの集計」と、「KUROKOが次回に覚えること」（SPEC 7.4節・9.8節）。

Standard Card。上に Eyebrow「振り返り」と、Retrospective の Status Pill（`collecting`＝Navy「収集中」／`awaiting_organizer`＝Sun「幹事の確認待ち」／`saved`＝Lagoon「記憶に保存済み」／`skipped`・`expired`＝Slate）。

- **集計**: Stat Block を2つ横に並べる（「回答 6 / 8名」「満足度 4.3 / 5」）。その下に、**良かった点**と**気になった点**を、語彙ごとの件数の横棒（高さ 8px の Progress。色は `--color-ink-navy`。左に語彙の日本語ラベル、右に「4件」）で、上位3つまで出す。**回答が3件未満のときは内訳を出さず**、`--color-navy-tint` の Info Banner で「回答が3件未満のため、内訳は表示していません（平均のみ）」と書く
- **個人ごとの回答は出さない。**誰が何を書いたかが分かる表示・ツールチップ・エクスポートを作らない
- **記憶の確認**（`awaiting_organizer` のときだけ）: 見出し「次回に覚えさせる内容」と、`caption` で「覚えさせた内容は、次回の企画で店選びの根拠として表示されます。お金の計算には使われません。個人名・個人ごとの回答は含まれません」。下に**事実の行**を並べる。1行 = Checkbox（既定でチェックあり）＋種類のチップ（「店の評価」／「予算の傾向」。`--color-navy-tint`）＋定型の文（`body-sm`。**編集できない**）。下に Primary Pill Button「次回に覚えさせる」と Secondary Pill Button「覚えさせない」
- **保存後**（`saved`）: 事実の行を読み取り専用にして、Checkbox を外し、上に Status Pill「記憶に保存済み」と「○件・日時」。保存前の下書きと、そのイベントで保存した記憶だけを出す（Memory Bank の記憶の全件は出さない）

### Venue Choice Card（店舗候補の選択）
**Role:** 提示された店舗の候補から、幹事が1つ選ぶ（SPEC 7.3）。

Standard Card。候補ごとに1行（Radio ＋ 店名 `subheading` ＋ 価格帯 ＋ 帰りやすさ「最大 ○分・平均 ○分」（tabular-nums）＋ 特徴のチップ（「個室」など。`--color-cream-subtle`））。**記憶に基づく理由があるときは、その行の下に `--color-navy-tint` の帯**を置き、先頭に「記憶」のチップ、`body-sm` で理由（例: 「前回の歓送迎会で個室の評価が高かった」）、右に `caption` で時期（「2026/06」）。**理由がないときは、何も出さない**（空の帯を作らない）。選んだ行は背景 `--color-navy-tint`。下に Primary Pill Button「この店で進める」。金額・帰りやすさの数字は、記憶によって変えない（記憶は理由の表示だけ）。

### Status Pill
高さ 24px、余白 0 12px、角丸 999px、12px/500、**先頭に 6px のドット**（`currentColor`）。**必ず文字を付ける**。背景は `*-soft`、文字とドットは `*-text`（Sun は文字 `--color-sun-text`、ドット `--color-sun-signal`）。

| データ | 値 → 表示（色） |
|---|---|
| Event.`status` | `planning` 企画中（Slate）／`rsvp` 出欠収集中・`venue` 店舗選定中・`booked` 予約済み・`day_of` 開催当日（Navy）／`receipt` 領収書の確定待ち（Sun）／`split` 按分中（Navy）／`approval` 承認待ち（Sun）／`payment` 送金中（Navy）／`completed` 完了（Lagoon）／`retro` 振り返り中（Navy）／`closed` 終了（Lagoon） |
| 送金（Payment.`status` / Participant.`payment_status`） | `not_applicable` 対象外・`waiting` 待機（Slate）／`awaiting_bank_approval` 銀行での承認待ち（Sun。参加者の承認を待っている）／`completed` 送金済み（Lagoon）／`blocked` ブロック・`failed` 失敗（Coral） |
| 承諾の状況（SPEC 7.3 の表） | 承諾待ち・銀行の認可待ち（Sun）／承諾済み（Lagoon）／取り消し済み（Sun）／銀行での承認待ち（Sun）／送金済み（Lagoon）／止まっている（Coral）／期限切れ・辞退・対象外（Slate） |
| 振り返り（Retrospective.`status`） | `collecting` 収集中（Navy）／`awaiting_organizer` 幹事の確認待ち（Sun）／`saved` 記憶に保存済み（Lagoon）／`skipped` 保存しない・`expired` 期限切れ（Slate） |
| DecisionLogEntry.`action_type` | `ブロック`（Coral）／`待機`（Sun）／`署名`・`確認`（Lagoon）／`判断`・`規程`・`ツール`・`照会`（Navy）／`検査`・`マスキング`・`送信`・`更新`・`記録`（Slate） |

この表の対応は `frontend/lib/status.ts` の1か所に置く。

### Role Badge
Participant.`role`（幹事・承認者・参加者・主役）。高さ 22px、角丸 10px、12px/500。**幹事＝背景 `--color-ink-navy`・文字 `--color-cream-text`／承認者＝背景 `--color-navy-tint`・文字 `--color-navy-text`／参加者＝背景 `--color-cream-subtle`・文字 `--color-slate-blue`／主役＝背景なし・枠 `--color-hairline`**。状態のピルと混ざらないよう、ドットは付けない。

### Data Table（一覧の表）
コンテナは角丸 20px・`--color-hairline` の枠。見出し行は `--color-cream-subtle`・`label`。行の区切りは `--color-hairline`。ホバーは `--color-cream-subtle`。1列目は題名（リンク）と、その下に `caption` の補助。**数字の列は右揃え＋tabular-nums**。イベント一覧の列は「題名 ／ 日時 ／ 幹事 ／ いまの段階 ／ 承諾 ○/○ ／ 送金の進捗」。幅 640px 以下はカード形式の行に切り替える。

### Progress
高さ 8px、角丸 999px、背景 `--color-hairline`。進んだ部分は `--color-ink-navy`、**100% に達したら `--color-lagoon-done`**。「20,400 / 27,000円」を必ず添える。

### Decision Timeline（経緯）
折りたたみ（Text Button で開く。ゲストでは最初から開く）。縦の細い線（`--color-hairline`）に沿って、時刻（`mono`）・`actor`（文字とドット）・`action_type` のピル・`summary` を並べる。`ブロック` の項目は左に 3px の Coral の帯、`待機` は Sun の帯。

### Demo Toolbar（ダミーデータの切り替え。開発用）
**Role:** バックエンドにつなぐ前（TASKS F1）に、ダミーデータで**役割（幹事・ゲスト）とイベントの段階**を切り替えて画面を確かめる。**開発用で、本番のビルドでは出さない**（開発サーバー（`next dev`）か、`NEXT_PUBLIC_DEMO_TOOLBAR=true` のときだけ表示。API につないだら使わない）。

画面の下端に固定した帯。背景 `--color-pure-white`、上に 1px `--color-hairline`、`--shadow-popover`、余白 8px 16px。先頭に Eyebrow Label「DEMO（ダミーデータ）」、続けて Tab Pill Navigation の小さい版で「幹事／ゲスト」、`select`（Text Input と同じ見た目）で段階（Event.`status`）。選んだ値は URL のクエリ（`?role=` `&stage=`）に反映する。**ここに、委任・承認・取り消し・振込に当たる操作は置かない**（見え方を切り替えるだけ）。画面の内容と重ならないよう、表示中は `body` の下に帯の高さの余白を取る。

### Doc Reader（開発者ページの文書。SPEC 7.3.2）
**Role:** リポジトリの Markdown の文書（PLAN・SPEC・ARCHITECTURE など）を読む

2列。左に目次（幅 240px、`position: sticky`、ヘッダーの下に固定。見出し2・3段目だけ。14px、選択中の節は `--color-ink-navy`/500、ほかは `--color-steel-text`。幅 1024px 以下は本文の上に折りたたみ（Text Button「目次」）で置く）。右に本文を Standard Card に入れる（本文の幅は最大 820px）。
- 見出し: `#` は `heading`、`##` は `heading-sm`（上に 48px、下に 1px `--color-hairline` の線）、`###` は `subheading`、`####` は `body-lg`/700
- 本文は `body`、段落の間 16px。リストは左に 24px
- 表は Data Table の見た目（compact・`body-sm`・見出し行 `--color-cream-subtle`・行の区切り `--color-hairline`）。幅が足りなければ表だけ横にスクロールする
- インラインのコードは `mono`・背景 `--color-cream-subtle`・角丸 6px・余白 0 4px。コードのまとまりは `mono`・背景 `--color-cream-subtle`・枠 `--color-hairline`・角丸 10px・余白 16px・横スクロール
- 引用（`>`）は、左に 4px の `--color-navy-tint` の帯と背景 `--color-cream-subtle`、文字 `--color-slate-blue`
- Mermaid の図は、枠 `--color-hairline`・角丸 20px・背景 `--color-pure-white` の中に描き、はみ出したら横にスクロールする。描画に失敗したら、元のコードをそのまま出す
- 文書の間のリンクは、開発者ページの中の文書に張り替える。開発者ページにない文書（review など）は、GitHub のファイルへのリンクにする（別タブ）
- 上に Eyebrow Label（例: 「仕様」）と、元のファイル名（`mono`）と「GitHub で開く」の Text Button

### Task Board（開発者ページのタスク一覧。SPEC 7.3.2）
**Role:** TASKS.md（AI のタスク）と human_task.md（人間のタスク）の残りを、絞り込んで見る

上に Tab Pill Navigation の小さい版で「AI のタスク／人間のタスク」、その下に絞り込み（状態: 「未完了／完了／すべて」を Tab Pill の小さい版、観点・フェーズ: Chip の並び。既定は「未完了」）。一覧は Data Table の行で、各行に **ID（`mono`）・題名（本文の最初の一文。`body-sm`/500）・観点または節の名前（`caption`）・状態のピル**（完了＝Lagoon「完了」／未完了＝Slate「未完了」／**人間のタスクの未完了＝Sun「人の対応待ち」**）。行を押すと、その下に本文（依存・完了の条件・経過）を Doc Reader と同じ書式で開く。件数「未完了 ○ / 全体 ○」を一覧の上に添える。**編集の操作は置かない**（正は文書）

### Diagram Viewer（開発者ページの構成図。SPEC 7.3.2）
**Role:** draw.io の構成図・ユーザーフローを見る

1枚ずつ Standard Card に入れ、見出しは図の名前（`subheading`）と元のファイル名（`mono`・`caption`）。図は白地のままカードの幅に合わせて縮小し、はみ出す場合は横にスクロールする。Text Button「原寸で開く」で SVG を別タブに開く。図の色は元の図のまま（トークンに置き換えない）

### Empty / Loading / Error
- **空**: 中央に `subheading` の一言と、`--color-steel-text` の説明（次に何が起きるとここに出るか）。イラストは使わない
- **読み込み**: 表とカードの形をした `--color-hairline` のスケルトン（左から右へ薄い光が流れる。1.4秒）。`prefers-reduced-motion` ではアニメーションを止める
- **エラー**: `--color-coral-soft` の帯に、何が失敗したかと再読み込みのリンク。**ID・トークン・個人情報を出さない**
- **権限なし**: 「この画面を見る権限がありません」と、見られる画面へのリンク。存在するかどうかが推測できる文言にしない

## 画面の構成（案）

役割ごとの範囲は SPEC 7.3 が正。**幹事とゲストは同じ画面**で、範囲（幹事は自分のイベント・ゲストは自分の `sandbox` のイベント）と名前（実名／架空の名前）だけが違う。

| 画面 | 部品 | 「わかること」 |
|---|---|---|
| **はじめる（`/`）** | ログイン前: アプリアイコンの絵（最大 200px、角丸 32px）と一言、Primary Pill Button「Google でログイン」（**匿名認証は使わない**。2026-09-27）。ログイン後: Guest Banner、Chat Panel（依頼の入力）、ゲストは「使い方」 | 依頼から始められる |
| イベント一覧（`/events`） | Info Banner、Data Table、Status Pill、Progress | ②いまの段階、④承諾の数、③送金の進捗、（幹事の列で）①幹事 |
| イベント詳細（`/events/[id]`） | **Event Summary**（題名・幹事・Flow Stepper・次にすること・小さな数字）→ 直下に **Confirmation Card・Venue Choice Card（幹事の役割で、その段階のときだけ）** → **Tab Pill Navigation**: ［送金・承諾］Payment Table と Consent List（2列。幅 1024px 以下は1列）／［按分］Split Table／［振り返り］Retro Summary Card／［経緯］Decision Timeline。**右下の KUROKO Launcher から KUROKO Panel**（Chat Panel と Activity Timeline）を開く | ①幹事 ②全体フロー ③誰から誰へいくら ④承諾していない人 ⑤按分の内訳 ⑥振り返りと記憶（＋幹事の事務の確認） |
| **開発者（`/dev`。SPEC 7.3.2）** | 概要: Highlight Card（いまの状態）→ Stat Block と Progress（観点 E・I・F・B・O ごとの完了数）→ Standard Card（人間の未完了タスク。Sun のピル）→ Doc Reader の書式で「KUROKO の要約」「デプロイ単位の一覧」「構成図（Mermaid）」。その下に文書・タスク・構成図への入口。文書は Doc Reader、タスクは Task Board、構成図は Diagram Viewer。上に Tab Pill Navigation「概要／文書／タスク／構成図」 | システムの全体像・構成・残りのタスク（チーム内の共有） |

## Motion

**動きは「KUROKOが進めていること」と「操作の結果」を伝えるためだけに使う。**飾りの動き・ループし続ける動きは作らない（「考えています…」のドットとスケルトンを除く）。実装は **Motion**（旧 framer-motion。依存の理由は [PLAN.md](docs/PLAN.md) 17.2）。値は `frontend/lib/motion.ts` の1か所に置く。

| Token | Value | 使う場面 |
|---|---|---|
| `--motion-fast` | 150ms | ホバー、ピル・チップの差し替え、フォーカス |
| `--motion-base` | 240ms | タブの中身の切り替え（フェード＋8px 上へ）、トーストの出入り、カードの確定後の切り替え |
| `--motion-slow` | 400ms | Flow Stepper の線が伸びる、Progress が伸びる、数字のカウントアップ |
| `--ease-out` | `cubic-bezier(0.22, 1, 0.36, 1)` | 入ってくるもの全般 |
| spring（パネル） | stiffness 380 / damping 36 | KUROKO Panel の開閉、タブの選択中の塗りの移動、チェックの出現 |

- **動かすもの**: KUROKO Panel の開閉／タブの選択中の塗りの移動と中身の切り替え／Flow Stepper の進行／Progress と Stat Block の数字（前の値から新しい値へカウントアップ。**最後は必ず API の値そのもの**。金額を途中の値で読み上げない＝`aria-live` は最後の値だけ）／Activity Timeline とチャットの新しい項目／Confirmation Card の「読み取り中 → 入力 → 確定済み」の切り替え／Toast／KUROKO Launcher のバッジ
- **動かさないもの**: 表の行の並び替え（位置が飛ぶと金額を読み違える）、按分の数字（Split Table は表示専用で、カウントアップもしない）、Slack Handoff Card の出現以外の揺れ
- **`prefers-reduced-motion: reduce` では、移動・拡大・文字の逐次表示を止め、フェード（`--motion-fast`）だけにする**（Motion の `useReducedMotion`／`MotionConfig reducedMotion="user"`）
- 1回の操作で同時に動くのは3か所まで。段階が進むときは「トースト → Flow Stepper → タブの中身」の順に 120ms ずつずらす

## Do's and Don'ts

### Do
- **文字は墨紺（`#141D2E`）、面は白・クリーム・墨紺の淡い色**にする。暗い面を作らない（アイコンは暗い地だが、画面には持ち込まない）
- 墨紺の塗りは、主ボタン・選択中のタブ・進行中の円・進捗バー・チェック・ロゴの**小さな部品**にだけ使う。**その上の文字はクリーム**（白ではなくアイコンの文字色）。大きな面は墨紺にしない
- 黄（`#F8C450`）は「人の対応を待っている」ことにだけ使う。承諾待ちの人は、行の背景と左の帯でひと目でわかるようにする
- ボタンとタブは 56px のピル、カードは 20px、ハイライトカードは 32px
- 状態は必ず「ドット＋文字」。完了・送金済み・承諾済みは青緑（Lagoon）、失敗・ブロックは赤
- 金額・件数は tabular-nums で右揃え。「3,300円」の書き方で統一する。送金の一覧には常に「**sunabar（サンドボックス）**：銀行API経由で送金を実行。資金は仮想」を出す
- すべての操作できる要素にフォーカスの枠（`--shadow-focus`）を出す。キーボードだけで一通り操作できるようにする
- ゲストの画面の名前は、サンドボックスの架空のもの。「ゲスト」のピルと Guest Banner を出す
- **Slack で人の対応が要る場面は、Slack Handoff Card で待ち相手を出す。**「次に何をすればよいか」を、Web の画面だけで分かるようにする
- **ゲストの画面には Guest Banner を常に出し、アップロードには「実在の個人情報を入れないでください」を添える**
- **按分の内訳は表示専用**。数字は API の値をそのまま出し、Web で再計算しない。区分・係数・負担額・根拠の条文を、同じ表の中で読めるようにする
- 記憶に基づく理由は、`--color-navy-tint` の帯と「記憶」のチップで、**理由の表示だけ**に使う
- **1画面に出す量を絞る**: イベント詳細の最初の画面は Event Summary だけで「誰が幹事か・いまどこか・次に誰を待つか・自分がすること」が分かるようにし、詳しい表はタブへ、チャットはパネルへ回す
- 動きは「KUROKOが進めたこと」「操作の結果」を伝えるときだけ使い、`prefers-reduced-motion` を守る

### Don't
- **黒い背景・暗いテーマ・純黒（`#000000`）を使わない**（視認性を落とす）。暗い色は文字と小さな操作部品（墨紺）だけ
- **緑をアクセントにしない。**青緑（Lagoon）は「完了・送金済み・承諾済み」の状態専用で、ボタン・帯・装飾には使わない
- 新しい色相を足さない（墨紺・月の黄・青緑・赤と、クリーム・グレーだけ）。**空色・青は使わない**（アイコンにない色）。虹色のアバターにしない
- `--color-mist-blue` を文字の主色にしない（コントラスト不足）
- 影を `--shadow-md` より強くしない。グラデーションを使わない。カードの中にカードを入れない
- 本文のウェイトを 400 未満、見出しを 700 超にしない。日本語の字間を詰めない・数字の列に `palt` を使わない
- **Web に、委任・承認・取り消し・振込の実行に当たるボタンや入力を置かない**（Slack で行う。Human-in-the-loop）。入力は、チャット（Chat Panel）・アップロード（Upload Dropzone）・幹事の確認（Confirmation Card など）の中だけ。**ゲストの画面でも同じ**（デモ用の代行は、Web のボタンではなく、システム側の代行として表示だけする）
- ゲストの画面に、実在の人物の名前を出さない（サンドボックスの架空の名前だけ）。
- **振り返りの個人ごとの回答**（誰が何を書いたか）と、**Memory Bank の記憶の全件**を出さない。記憶の文面を、幹事が編集できる入力にしない（含める・含めないだけ）トークン・口座番号・署名の原文・好みの生データをどの画面にも出さない
- 「sunabar（サンドボックス）」の注記を、送金の一覧から外さない。**「送金していない」「模擬」と読める文言にしない**
- 1つのタブ・1つの画面に、カードを縦に何枚も積まない（タブの中は1〜2枚まで）。飾りのアニメーション、ループし続ける動き、金額の表のアニメーションを作らない

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| 0 | Cream Wash | `#F8F5EE` | ページの背景（キャンバス） |
| 1 | Pure White | `#FFFFFF` | Standard Card、表、入力 |
| 2 | Navy Tint | `#E8ECF4` | Highlight Card、Info Banner、選択中の行 |
| 3 | Cream Subtle | `#FBF9F4` | 表の見出し行、ホバー、カード内の入れ子の面 |

## Elevation

- **Standard Card:** `--shadow-md` ＋ 1px `--color-hairline`
- **Highlight Card / Info Banner:** なし（背景の色で区別する）
- **Popover:** `--shadow-popover`
- **Focus:** `--shadow-focus`（キーボードフォーカスは必ず見える）

## Imagery

写真・イラスト・グラデーションは使わない。アイコンは**線画（線の太さ 1.5px、16px または 20px）**で、色は文字と同じ。意味を文字なしで伝えるアイコンには `aria-label` を付ける。アイコンのライブラリを追加する場合は、依存を増やす前に [PLAN.md](docs/PLAN.md) に理由を書く。アバターは円に頭文字（`--color-navy-tint` の背景、`--color-navy-text` の文字）で、色を人ごとに変えない。ロゴは「黒」の1文字（`--color-sun-signal` の角丸 10px の正方形に、墨紺の字）。**アプリアイコン（`frontend/images/kurko_v1.png`。黒子がビールを運ぶ絵）は配色の元で、次の3か所で使う**: ①ファビコン（`frontend/app/icon.png`）②はじめる画面の絵（最大 200px、角丸 32px。ログイン前だけ）③KUROKO Launcher の丸い切り抜き（32px）。**アイコンの暗い地を、画面の大きな面に広げない**。それ以外の場所では写真・イラストを増やさない。

## Layout

ページの背景は Cream Wash で、内容は最大幅 1200px の中に、白いカードとして並べる。ヘッダーは白で、下に細い線。イベント詳細は、**最初の画面（スクロールなし）に Event Summary が収まる**ことを目安にし、上から「Event Summary（Highlight Card）→ 幹事の確認（あるときだけ）→ タブ（送金・承諾／按分／振り返り／経緯）」。**1つのタブに出すのは1〜2枚のカードまで**。チャットとタイムラインは本文に置かず、右下の KUROKO Panel に入れる。幅 1024px 以下は1列にし、幅 640px 以下は表をカード形式の行にする。カード同士の間隔は 24px、セクション間は 48px。Highlight Card の墨紺の淡い帯（Event Summary）が、視線の入口になる。

## Agent Prompt Guide

**Quick Color Reference**
- text: #141D2E（墨紺。純黒は使わない）／secondary text: #435068／muted: #5A6478
- canvas: #F8F5EE／card: #FFFFFF／highlight band: #E8ECF4／border: #E6E2D8
- primary action: #141D2E（文字は #FDFBF4）／waiting-on-human: #F8C450／done: #12A594／failed: #E5484D

**Example Component Prompts**

1. Primary Pill Button を作る: 背景 #141D2E、文字 #FDFBF4、16px/500、高さ 44px、余白 12px 24px、角丸 56px、枠なし。ホバーで #2B3852。
2. Consent List の行を作る: 高さ 56px、左にアバター（円 40px、背景 #E8ECF4、頭文字 #2B3A5C）と名前 16px/500 と Role Badge、右に承諾の状況の Status Pill と「上限 6,000円」（12px、tabular-nums、右揃え）。承諾待ちの行は背景 #FFF3D6、左に 4px の #F8C450 の帯。
3. Flow Stepper を作る: 7つの段階（出欠・承諾／店舗・予約／開催／精算／送金／完了／振り返り）を横に並べる。完了は #12A594 の円にチェック、いまは #141D2E の円（数字は #FDFBF4）とラベル背景 #E8ECF4・文字 700、その下に #FFF3D6 のチップで「承認者 ○○さんの対応待ち」。先は輪郭 #E6E2D8 の円。線は 2px。
4. Payment Table を作る: 上に「sunabar（サンドボックス）」のピルと「銀行API経由で送金を実行しています。資金は仮想です」。列は 送金元 → 送金先（幹事）／金額（右揃え、tabular-nums、16px/500）／状態のピル／日時（12px、右揃え）。下に「送金済み 20,400 / 27,000円」と Progress（高さ 8px、#141D2E、100% で #12A594）。
5. Highlight Card を作る: 角丸 32px、背景 #E8ECF4、余白 32px、影なし。上に Eyebrow Label（12px/500、#5A6478）、その下に 24px/700 の墨紺の見出し。
6. Confirmation Card を作る: Standard Card。上に Eyebrow「領収書の金額の確認」と 20px/700 の見出し。左に領収書のサムネイル（角丸 10px）、右に Text Input（高さ 44px、枠 1.5px #838DA1、角丸 10px。金額は右揃え・tabular-nums、右に「円」）。直した項目に「修正済み」チップ（#E8ECF4）。下に Primary Pill Button「この内容で確定する」と、`caption` で「確定すると、承認者の按分の承認に進みます。承認は Slack で行われます」。

## Light Rhythm

暗い面と明るい面の交互ではなく、**白いカードと、墨紺の淡い帯（Navy Tint）が、クリームがかった白の地（Cream Wash）に並ぶ**ことで階層を作る。暗い帯は作らない。Highlight Card は、白いカードが続く中で視線を止める「間」として使い、連続させない。同じ面の中に同じレベルの面を入れない（カードの中の凹みは Cream Subtle にする）。

## Quick Start

### CSS Custom Properties

```css
:root {
  /* Colors */
  --color-ink-navy: #141D2E;
  --color-slate-blue: #435068;
  --color-steel-text: #5A6478;
  --color-mist-blue: #9AA1AF;
  --color-hairline: #E6E2D8;
  --color-input-border: #838DA1;
  --color-cream-wash: #F8F5EE;
  --color-pure-white: #FFFFFF;
  --color-cream-subtle: #FBF9F4;
  --color-navy-tint: #E8ECF4;
  --color-cream-text: #FDFBF4;
  --color-navy-hover: #2B3852;
  --color-navy-text: #2B3A5C;
  --color-sun-signal: #F8C450;
  --color-sun-soft: #FFF3D6;
  --color-sun-text: #7A4E00;
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
  --radius-checkbox: 6px;

  /* Shadows */
  --shadow-md: 0 1px 2px rgba(18, 35, 63, 0.04), 0 4px 16px rgba(18, 35, 63, 0.06);
  --shadow-popover: 0 8px 24px -8px rgba(18, 35, 63, 0.18);
  --shadow-focus: 0 0 0 2px #FFFFFF, 0 0 0 4px #141D2E;

  /* Component sizes（Components 節の寸法を変数にしたもの） */
  --control-height: 44px;      /* ボタン・入力・タッチ操作の最小の高さ */
  --pill-height: 24px;         /* Status Pill */
  --badge-height: 22px;        /* Role Badge */
  --avatar-size: 56px;         /* Organizer Card */
  --avatar-size-sm: 40px;      /* 表・リストの行 */
  --icon-size: 20px;
  --icon-size-sm: 16px;
  --icon-stroke: 1.5px;
  --dot-size: 6px;             /* Status Pill のドット */
  --dot-size-lg: 8px;          /* 通知の未読・タイムラインのドット */
  --check-size: 20px;          /* Checkbox・Radio */
  --stepper-dot: 32px;         /* Flow Stepper の円 */
  --progress-height: 8px;
  --stripe-width: 4px;         /* 対応待ちの左の帯 */
  --stripe-width-sm: 3px;      /* Decision Timeline の帯 */
  --line-width: 2px;           /* Flow Stepper の線 */
  --border-width: 1px;
  --border-width-input: 1.5px;
  --popover-width: 360px;
  --demo-toolbar-height: 64px; /* Demo Toolbar の分の下余白 */
  --panel-width: 440px;        /* KUROKO Panel */
  --launcher-height: 56px;     /* KUROKO Launcher */

  /* Motion（JS 側の値は frontend/lib/motion.ts に同じ値を置く） */
  --motion-fast: 150ms;
  --motion-base: 240ms;
  --motion-slow: 400ms;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);

  /* Surfaces */
  --surface-canvas: #F8F5EE;
  --surface-card: #FFFFFF;
  --surface-band: #E8ECF4;
  --surface-subtle: #FBF9F4;
}

@media (max-width: 640px) {
  :root {
    --gutter: 16px;
    --card-padding: 16px;
  }
}
```

Tailwind は現状の `frontend/` に入っていない。導入する場合は、上の値を `@theme` にそのまま写す（値を変えない）。ダークテーマは作らない。テンプレートの `globals.css` にある `prefers-color-scheme: dark` の切り替えは削除する。
