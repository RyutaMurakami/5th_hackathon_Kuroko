# Frontend Rules

## 構成
- `app/` — Next.js App Router のルート・ページ・レイアウト。
- `components/` — 再利用可能な UI コンポーネント。ページ固有のロジックは持たせない。
- `lib/` — Firebase クライアント初期化 (`firebase.ts`)、バックエンド API 呼び出し (`api-client.ts`) 等の共有ユーティリティ。

## デザイン
- 色・文字・余白・角丸・部品は リポジトリ直下の `DESIGN.md` のトークン（CSS 変数。`app/globals.css`）に従う。値を直接書かない。本書にない部品が必要になったら、先に `DESIGN.md` に追記する。
- Web Dashboard（Web アプリ）は**幹事と審査員（ゲスト）の主導線**（SPEC 7.3・7.5・7.6、ARCHITECTURE D19・D22・D23）。**Web が主導線で、Slack は Human-in-the-loop**。入力してよいのは、**チャットでの依頼（Chat Panel）、予約画面・領収書のアップロード（Upload Dropzone）、幹事の確認**（予約内容・領収書の金額・店舗候補・予算超過・振り返りのまとめ。Confirmation Card・Venue Choice Card・Retro Summary Card）だけ。**委任・承認・取り消し・振込の実行に当たる操作は作らない**（Slack で行う。ゲストの画面でも同じ）。Slack で人の対応が要る場面は、**Slack Handoff Card で待ち相手を出し、Slack を開くリンクを添える**。書き込みが許されるかは API 側で強制されるので、画面側で隠すだけにしない。
- **ゲストの画面には Guest Banner を常に出し、アップロードには「実在の個人情報を入れないでください」を添える。**アップロードの種類・サイズ・枚数は、画面でも検査するが、**API 側の検査が正**（SPEC 7.5）。
- **按分の内訳（Split Table）は表示専用**。数字は API の値をそのまま出し、Web で再計算しない（SPEC 7.3.1、D21）。
- **振り返りの個人ごとの回答と、Memory Bank の記憶の全件は、どの画面にも出さない。**記憶の文面を幹事が編集できる入力にしない（含める・含めないだけ。SPEC 9.8）。回答が3件未満のときは内訳を出さない。
- 送金の一覧には、常に「sunabar（サンドボックス）：銀行API経由で送金を実行。資金は仮想」を出す。「送金していない」「模擬」と読める文言にしない。口座番号・銀行のアクセストークンは、どの画面にも出さない。
- 役割（幹事・ゲスト。審査員と開発者は区別しない）ごとの見える範囲は API 側で強制される。画面側で隠すだけにしない。ゲストの画面は、サンドボックスの架空の名前だけを出す。

## 環境変数
- `NEXT_PUBLIC_` プレフィックスの変数はビルド時にクライアントへ埋め込まれる（公開情報のみ）。
- バックエンドの秘密情報は `NEXT_PUBLIC_` を付けず、サーバーサイド（Route Handler 等）からのみ参照する。

## 品質ゲート
- `npm run lint` / `npm run typecheck` / `npm run build` を通すこと。
- Firestore/Auth を使うローカル開発では、リポジトリルートで `firebase emulators:start` を起動し、`NEXT_PUBLIC_FIREBASE_EMULATOR=true` で接続する。
