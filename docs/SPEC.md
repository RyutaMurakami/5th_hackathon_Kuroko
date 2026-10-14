# KUROKO 実装仕様書（SPEC）

- 作成日: 2026-09-17（提出締切 2026-10-15 23:59 まで **残り約28日**）
- 位置づけ: [PLAN.md](PLAN.md) と [review/](review/) 配下の壁打ちレビュー（00〜04）、および壁打ちセッションでの確定事項を統合し、**実装に着手できる粒度**まで落とした仕様書。本書が最新かつ優先される。矛盾がある場合は本書の記述を正とする
- レビュー文書の使い道: 本書は「何を作るか」の仕様。レビュー00〜04は「なぜそうしたか」の経緯・比較検討・デモ台本として引き続き参照する
- 経験の記憶: **チームの宴会実績ナレッジ**として、自動記録した実績と最小の評価のうち、**幹事が確認した定型の事実だけ**を **Agent Platform の Memory Bank** に書き込み、次の企画で店舗の提案などに使う（9.8節）。金額・按分・承認者・支払先・委任・規程の値には使わない
- 会社規程の参照: 実行時は **Vertex AI RAG Engine**（Agent Platform）のコーパスに入れた規程文書を `retrieveContexts` で参照する（9.7節）。[`policies/company_rules.yaml`](../policies/company_rules.yaml)（v1.0.0）は、**抽出結果を検証するテストの正解データ**と、RAG が使えないときのフォールバックとして残す
- チーム運営方針: 人数・役割分担は固定せず、**ストーリーに沿った挙動を全部実装する**方針で進める（本書は分担表ではなく、機能一覧として使う）

### 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-09-17 | 初版 |
| 2026-09-17 | **支払い方式を変更**。レビュー03・04の案B-1（sunabarの銀行振込、振込ごとに本人が銀行で承認）をやめ、**参加者の支払いエージェントが、本人の委任状（AP2）の範囲内で幹事に支払う**形にした。決済役はAP2公式サンプル（human-not-present / cards）の模擬を使う。sunabarの口座準備・口座数の検証・承認ページの直リンク検証は不要になった |
| 2026-09-19 | [ARCHITECTURE.md](ARCHITECTURE.md) の作成に合わせ、2.1の図（Web Dashboard は KUROKO Agent の読み取りAPI経由、ファイル保存は KUROKO Agent が行う）と、2.3・11章のサービス分割の記述を修正。あわせて、**ADKエージェントは Agent Runtime にデプロイし、決定論的なコードは Cloud Run に置く**前提に修正（2.1の図、2.2、2.3、11章、13章）。機能・データモデル・支払いフローは変更なし |
| 2026-09-19 | ①エージェントのツールは **MCP** 経由にする。**KUROKO API・支払いAPI 自身が MCP サーバーを兼ね、Cloud Run にデプロイする**（2.3、4章、11章）。②インジェクション対策は **Agent Gateway × Model Armor** に一本化する。自由記述も Slack → KUROKO API（後段）→ エージェントの経路で渡し、Gateway の入口を通す。隔離抽出は、ツールを持たない別のエージェント（`extract-agent`）にして、同じ経路に載せる（10章）。③Web Dashboard は**幹事と開発者向け**（経理は対象外）で、「誰が幹事か・全体フローのどこか・誰から誰へいくら送金されたか・まだ承諾していない人は誰か」がわかる画面に絞る（1.2、7章、7.3、10章）。機能・データモデル・支払いフローは変更なし。画面のビジュアル規約は [DESIGN.md](../DESIGN.md) |
| 2026-09-20 | **差別化のための3点を反映**（幹事Pay との比較を踏まえた方針。[PLAN.md](PLAN.md) 16章）。①**支払い方式を再変更**。AP2サンプルの模擬決済役をやめ、**AP2 の委任状で権限を管理し、送金は銀行API（GMOあおぞらネット銀行の sunabar）で実行する**。銀行は振込ごとに口座の持ち主の承認を求めるため、「鍵3」は**銀行での本人承認**に戻る（8章、6.3節、2.2節、5章、3章 Payment、13章）。2026-09-17 に不要としたsunabarの準備・検証項目を復活させた。②**会社規程の参照を RAG Engine に変更**。規程文書を Vertex AI RAG Engine のコーパスに入れ、`retrieveContexts` で参照する。**文書の版管理は行わない**。`company_rules.yaml` はテストの正解データとフォールバックに役割を変える（9.7節、1.2、4.1、10章、11章、12章）。③**Web Dashboard を幹事の主導線にする**。読み取り専用をやめ、**幹事の事務の確認（予約内容・領収書の金額・店舗候補の選択）を Web でも行えるようにする**。委任・承認・取り消しは Slack のままにする（7章、7.3節。**要レビュー**: 13章）。④**見せ方の方針**: 幹事Pay を決済手段に置かず、**KUROKO自身が送金を実行する**（外部の集金・決済サービスに任せる説明をしない）。1.2・7.3・8.1 を直した |
| 2026-09-20 | **決定事項の反映（2回目）**。①**按分の内訳を Web に出す**（7.3.1。区分・係数・負担額・根拠条文。幹事は実名、開発者は仮名）。②**振り返り・記憶を作る**。**Agent Platform の Memory Bank** に、幹事が Web で確認した定型の事実だけを**直接書き込み**、次の企画で `recall_memory`（MCP・読み取り専用）で引く。会話からの自動生成は使わない（記憶の汚染対策。9.8節、6.4節、10章、3章 Feedback / Retrospective、4.1、5章、7.4節）。③**Web Dashboard を幹事の主導線にし、事務の確認（予約内容・領収書の金額・店舗候補・予算超過・振り返りのまとめ）を Web で行う**ことを確定した（7.3節）。④13章の「要レビュー」のうち、上の3点を「決定済み」に移した |
| 2026-09-21 | **思想の変更**。①**Web が主導線、Slack は Human-in-the-loop**（1.1・7章）。幹事の作業（依頼・対話、**領収書・予約画面のアップロード**、確認、状況の把握）は **Web アプリ**で行い、Slack は人の判断・同意が要る場面（出欠・委任・按分の承認・銀行での承認・予算超過の最終確認・振り返りの回答）とその通知に使う。お金の権限に触れる操作は Slack のまま。狙いは、**ハッカソンの審査員が実際に触って体験できること**。②**審査員が体験できる導線（ゲスト）**を追加（7.6節。匿名認証・サンドボックス・デモ用の代行。**要レビュー**）。③Web の本人確認を、Slack ユーザーIDの対応づけから **Firebase の UID（`organizer_web_uid`）**に変更（3章・7.3・6.4）。④**Web の操作の一覧**（4.3）、**Web のチャット・アップロード・アプリ内通知**（7.5・3章 Message / Notification）を追加。経費精算PDFは幹事が Web からダウンロードする（9.5）。⑤**Memory Bank を統括エージェントにアタッチして読み取る**方式に変更（`load_memory`。読み取り専用のロール。企画・店舗提案の段階だけ。書き込みは `kuroko-api` のコードだけ。9.8・10章）。MCP ツール `recall_memory` は廃止 |
| 2026-09-26 | **予約情報・領収書の入力経路を追加**（3章 Receipt・4.1・4.3・7.5）。①予約情報は、ファイルのアップロードに加えて、**スクリーンショットの貼り付け**（クリップボードの画像）と**手入力**でも確認カードに入れられる。②領収書は**アップロードだけ**（貼り付けなし）。**AI・OCR が読み取れなかったときだけ**、金額などを手入力できる。③手入力の値も、読み取りと同じ検査（型・範囲）と幹事の確定を通す。確定の記録に入力元（`upload` / `paste` / `manual`）を残す。手入力の領収書は画像が無いので、経費精算の記録にその旨を書く |
| 2026-09-26 | **[レビュー06（fukuoka）](review/2026-09-23_KUROKO_review_06_fukuoka.md)の指摘を反映**。①**店舗の選定ロジックを明文化**（**9.9節**）。段階式（ハード制約で足切り → 最も遠い人の所要時間で並べる → ソフト制約と実績で微調整）。足切りと順位づけはコード、LLM は希望の解釈と理由の文章化だけ。**選んだ理由**は、コードが作る `reason_facts` と、LLM が書く `selection_reason` で出す。3章の Participant（`dietary_must / dietary_avoid / request_tags`）・VenueCandidate、4.1 の `search_venues`、7.3、12章を更新。②**振り返りを「自動の実績＋最小のフィードバック」に見直し**（9.8節・7.4節）。参加者は**満足度の1タップ＋任意のコメント**だけ（良かった点・気になった点のチェックボックスは廃止）。幹事は Web で「次回もこの店を使いたいか」の1問。**実績（店・人数・1人あたり・予算内か・最も遠い人の所要時間）は入力なしで自動記録**。記憶の `kind` は `venue_record`（実績）と `venue_evaluation`（評価）にし、`budget_trend` は `venue_record` に統合した。記憶は**チームの宴会実績ナレッジ**（3章 Feedback・Retrospective、4.1、4.3、6.4、12章、13章）。③**AIとコードの役割の境界を10章に明記**（LLM が見るもの・触れないもの、マスキングと承認・送金の関係）。8.5 のシーケンスに、LLM が関与する箇所の注記を追加。**Policy Gate の中身・支払いフロー・金額の計算は変更なし** |
| 2026-09-26 | **審査員と開発者の役割を統合**（ユーザー決定）。①Web の役割を**幹事（`organizer`）とゲスト（`guest`。審査員・開発者を区別しない）の2つ**にした。開発者の役割（全イベント・仮名のみ・書き込み不可）を廃止（7.3・7.6・10章・12章）。②ゲストは**サンドボックス（自分の `sandbox` イベント）だけ**を見られる・書ける。名前は架空。経緯（判断ログ）もゲストに出す。③**参加者向けの Web 画面は作らない**（参加者は Slack のまま）。④認証は**ログイン不要（匿名）を残し、将来は Google 認証だけにする**（13章バックログ）。 |
| 2026-09-27 | **13章「要レビュー」6項目のうち5項目を決定**（human_task H2。ユーザー決定）。①**ゲストの認証を匿名認証から Google ログインに変更**（**匿名認証は使わない**。許可リストに載っていない Google アカウントはゲストとして扱う。役割の決め方は変えない。7.3・7.6・11章・13章）。②9.3節の按分ルールは決め打ちでよい。③Memory Bank のアタッチ読み取り案を確定。④記憶の書き込みは現状案でOK（バックログとして自由記述の書き込みも将来許す）。⑤3章の振り返り3件未満ルールは今回は発生しない前提でよい。⑥過去の記憶の事前投入（seed）はYes。**7.6節②（デモ用の代行）・③（(A)(B)の両方を用意するか）は引き続き要レビュー** |
| 2026-09-27 | **開発者ページ（`/dev`）を追加**（7.3.2。ユーザー決定）。チームメンバーが、システムの全体像・構成・残りのタスクを Web で確認できるようにする。内容はリポジトリの文書（デプロイ時に同梱）。**当面はログインした全員が見られ、最終的にはメールアドレスの許可リストで絞る**。役割（幹事・ゲスト）は増やさない（D25 は変えない） |
| 2026-10-11 | **デモでの振込の代行**（8.10節を追加。8.8節を修正）。参加者は10人のまま、実際に銀行で承認するのは1人（既定は加藤）だけにし、ほかの人の振込は `bank-adapter` が代行する。委任状・Policy Gate・明細での確認は全員ぶんが同じコードで動く |
| 2026-10-12 | **デモの配役を変更**（ユーザー決定）。①**幹事 = Web にログインした人**（審査員を含む）、Slack の実在の2人（**赤坂 くらお**＝一般、**赤くら 花子**＝部長・承認者）だけが、Slack と銀行で操作する。ほかの参加者は名前を前面に出さず、**出欠・委任はデモ用の代行**（`sa-demo-runner`。`sandbox` のイベントで、Slack のアカウントが無い人だけ）、振込は 8.10 の代行（7.6・8.10）。口座は 1番目=幹事、2番目=くらお、3番目=花子。②**幹事口座の入金の確認を Cloud Scheduler で自動化**（8.6）。③**返答を待つあいだ「考え中」を見せる**（Web のチャット・Slack の DM。7.5） |
| 2026-10-12 | **Web のチャット画面（3人ぶんを並べる）**（7.7節を追加。ユーザー決定）。審査員は Slack・銀行に入れないので、Web に幹事・くらお・花子の3人ぶんのチャットを並べ、**HITL の操作を Web のカードからも Slack からもできる**ようにした。Web から押せるのは、体験用（`sandbox`）のイベントを作った本人だけ（1.1 の原則の例外）。按分の承認に `approved_via`、銀行の承認に体験用のボタン（`bank-adapter` の「承認待ち」の代行）を追加。7.6節の「按分の承認は代行しない」は、「自動では代行しない（Web のカードで人が押す）」に読み替える |
| 2026-10-12 | **通しを最後まで閉じる**（ユーザー決定）。①**振り返りを、完了の直後に始める**（翌日を待たない）。くらお・花子の満足度は、Slack のボタンからも Web のカードからも答えられる。幹事は Web で振り返りを確認し、**Memory Bank に保存する**（7.4・9.8）。②**記憶の読み取りは、`kuroko-api` のコードが行う**（店の候補の順位と理由に使う。統括エージェントへのアタッチ（`load_memory`）は後回し。9.8）。③**規程は、文書（`policies/company_rules.md`）から Gemini が値を読み取り、コードが検証する**（RAG Engine のコーパスは使わず、文書の全文を渡す。9.7）。④**予約画面の読み取り**（`ingest_reservation`）を実装（7.5）。⑤**体験用の銀行の承認**に、銀行の承認ページを模した画面と、Slack のボタンを追加（7.7）。⑥**エージェントに、いま話しているイベントをコードが伝える**（イベントの ID を聞き返さない。7.5）。⑦完了時に参加者の好み・最寄り駅を削除（9.6）。⑧**リマインド（開催前・承諾の催促）は作らない**（定期実行から外す）。**支払い専用の LLM エージェント（`payment_agent`）は作らない**（AP2 の委任状の署名・検証・請求・領収書は `payment-api` のコードが実装済み。8.5 の注記のとおり、LLM が担う部分が無い） |
| 2026-10-12 | **画面を2つに分け、規程はエージェントが調べる**（ユーザー決定）。①**規程の文書は、エージェントが自分の判断でツール（`retrieve_policy`）を呼んで調べる**。ツールは、文書を条ごとに検索して、質問に合う条だけを返す。**Gemini に文書の全文は渡さない**（値の読み取りも、検索で見つけた条の抜粋だけを渡す。9.7）。RAG Engine のコーパスは、常時の費用（既定の構成は Spanner）があるため、まだ作っていない。②**チャットの画面を、審査員の体験用（`/verify`）と、開発者の実演用（`/demo`）の2つに分ける**（7.7）。実演用は、登録したアカウントだけが使え、振込を本物の銀行 API（sunabar）に依頼する。③**幹事の入力は、チャットの流れの中のカードで完結させる**（計画・店・予約・領収書・振り返り）。店の候補は、ボタンで出して選ぶ。入力欄には、デモ用の候補を出す（7.5）。④**進行ヒントは、どちらの画面でも、いつも出す**（イベントを作る前も。参加者・承認者の列にも「次にすること」を出す）。⑤3人ぶんのチャットは、最初から開いておく。⑥チームの想定を「営業1課」から「**第一開発チーム**」に変更（IT 企業の想定）。⑦経費精算の PDF は作らない |
| 2026-10-12 | **RAG Engine は使わない**（ユーザー決定）。規程は、いまの実装（エージェントがツール `retrieve_policy` で文書を条ごとに調べる。`kuroko-api` の自前の検索）で確定とする。本書の「RAG Engine」「`retrieveContexts`」「コーパス」の記述は、当初の設計として残すが、実装しない（9.7 の冒頭の注記が正）。あわせて、架空の会社の名前を「サンプル商事」から「**株式会社Akakura**」に変更（内部の識別子 `sample-co-social-event`・`team:sample-co:dev1` は変えない） |
| 2026-10-12 | **チャットの返答を非同期にし、画面に「クリア」を付ける**（ユーザー決定）。①Firebase Hosting は **60秒を超える応答を 504 で切る**。KUROKO の返答（エージェントの実行）は50〜70秒かかることがあり、審査員の画面にエラーが出ていた。そこで **`send_message` は発言と「考え中」の返答（`pending`）を保存してすぐ返し、返答の生成は Cloud Tasks（`kuroko-default`）で行う**。画面は一定間隔で読み直して、返答を拾う（2.2・4.3・7.5）。②体験用・実演用の画面に **「最初からやり直す（クリア）」** を追加。その画面で作った自分のイベント・通知を削除し、シナリオを最初から始める（`reset_scenario`。4.3・7.7） |
| 2026-10-12 | **チャットの画面を DM のように見せ、流れを見直す**（ユーザー指定。`docs/to_ai/2026-10-12-2325.md`）。①3人ぶんのチャットは、**ページ全体を動かさず、各チャットの中だけをスクロールする**。発言には KUROKO・くらお・花子の**アイコン**を付け、KUROKO から届いたことが分かる見た目にする（7.7）。②デモの開催日は **10月30日 19時**。最初の依頼は「10月30日の19時から、第一開発チーム10人の歓送迎会を行いたい」で、**KUROKO が確認したい項目（題名・日時・人数・予算・主役・出欠の回答期限）をカードで出し、幹事が埋める**。統括エージェントは、カードで入れる項目を文章で聞き返さない。**場所（エリア）は聞かない**（7.5）。③出欠のカードで、**最寄り駅と苦手な食べ物**を聞く（駅コードと固定の語彙にして持ち、原文は保存しない。7.7・10章）。④**出欠が出そろったら、KUROKO が自分で店を探す**（Cloud Tasks の `/tasks/internal/venue-searches`。「店の候補を出す」は、探し直しに残す）。候補と選んだ店は、Google マップで開ける。⑤予約の内容のカードは、**予約の画面を送ったあと**に出す。確定すると、**参加者の DM に開催の案内**が届く（7.5）。⑥予約の画面・領収書は、アップロードの欄ではなく、**チャットに画像を送って**渡す。⑦按分の計算中は、**何を確認して計算しているか**を順に見せる。⑧**振り返りは出席者の全員に送る**（体験用で Slack を使わない架空の参加者のぶんは、デモ用の代行が答える。7.4・7.6）。⑨すべて終わったら、**デモの終わり**を画面に出す。⑩進み具合は、KUROKO の発言（固定の文。LLM は使わない）として、幹事のチャットに残す。⑪入金の確認は、開催日が先の日付のままでも、今日からの明細で照合する（8.6） |
| 2026-10-13 | **チャットの流れの修正**（ユーザー指定）。①計画のカードは、**KUROKO の返答を出したあと**に出す。②出欠のカードの「苦手な食べ物」は、**語彙の語がそのまま書かれていれば、隔離抽出を待たない**（言い換えのときだけ隔離抽出に聞く。待ち時間の上限つき。駅の確認と同時に行う）。③**按分の内訳を先に見せ、幹事が確かめて承認者に承認を依頼する**（7.5）。承認者が承認したら、**幹事に知らせ、幹事が「振込の依頼を送る」ことを承認してから**、請求（Policy Gate 6.2）に進み、参加者に銀行での承認の依頼（DM）が届く（8.5）。④**状態つきのカード（店の候補・按分の内訳・振込の依頼・振り返り）は、発言の位置に出す**（`Message.card`）。時系列が崩れないようにするため。⑤**領収書は金額だけを読み取る**（店名・日付は読み取らない。4.1 `ocr_receipt`）。⑥**振り返りの依頼が重複する不具合を修正**: 5つの満足度ボタンの `action_id` が同じで、Slack が `invalid_blocks` で拒否していた（`rate:1`〜`rate:5` にした）。Slack の失敗でイベントの進行を止めず（`deliver_card`）、振り返りの記録を先に作ってからカードを送る（再実行で重複しない） |
| 2026-10-13 | **チャット画面の仕上げ**（ユーザー指定）。①銀行で振込を承認した人（くらお・花子）ごとに、**幹事に「〇〇さんからの支払いが承認され、振り込みが実行されました」を都度出す**。②承認の直後に、**支払いと入金の確認をすぐ行う**（`/tasks/internal/settle`。payment-api のポーリングは sa-api からも呼べる）。定期実行（1分ごと×2段）の待ちを省き、振り返りまでの時間を縮める（定期実行は拾い直しとして残す）。③満足度のボタンは、**1〜5 すべて同じ見た目**にする。④**計画のカードは、企画の依頼（日時・人数・会の種類など）に答えた発言にだけ**付ける（あいさつ・雑談では出さない。コードの判定 `looks_like_plan_request`）。⑤**ゲストバナーを廃止**した（7.6）。⑥チャット画面の上に、**全体の流れ（依頼・提案・按分・承認・完了）の 5 段階**を示す |
| 2026-10-13 | **実演用は、Slack の DM から依頼を始められる**（ユーザー決定。7.8）。登録した Slack ユーザーが DM で企画の依頼を送ると、KUROKO がイベントを作り、**計画の案を Slack のカードで返す**。「この内容で進める」で確定すると、参加者に出欠・委任の依頼が届く。続き（お店選び・予約・領収書・承認）は、Web の実演用の画面で進める。Slack ユーザーと Google アカウントの結びつけは、`config/demo.live_slack_users`（人が登録） |
| 2026-10-13 | **幹事の操作を Slack に寄せ、Web で記憶・規程を参照する**（ユーザー指定）。①実演用は、お店選び・予約画面と領収書の画像・各確認・承認依頼を **Slack の DM** で行う（7.8）。Web の実演用の画面は見るだけにし、**幹事のチャット画面は出さない**。②**記憶（Memory Bank）と会社の規程・按分ルールを、Web で参照**できる（体験用・実演用の両方。7.9） |

---

## 目次

1. [スコープ](#1-スコープ)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [データモデル](#3-データモデル)
4. [ツール（Function）契約](#4-ツールfunction契約)
5. [イベントのライフサイクル](#5-イベントのライフサイクル)
6. [Policy Gate](#6-policy-gate)
7. [WebアプリとSlack（HITL）の設計](#7-webアプリとslackhitlの設計)
8. [支払いフロー（AP2の委任と銀行APIでの送金）](#8-支払いフローap2の委任と銀行apiでの送金)
9. [個別設計判断](#9-個別設計判断)
10. [ガバナンス・セキュリティ](#10-ガバナンスセキュリティ)
11. [技術スタック](#11-技術スタック)
12. [テスト・評価](#12-テスト評価)
13. [未解決・要検証・バックログ](#13-未解決要検証バックログ)
14. [参考資料](#14-参考資料)

---

## 1. スコープ

### 1.1 方針

チームの人数・時間で機能を間引くのではなく、**レビュー04のストーリーに登場する挙動をすべて実装する**ことを基本方針とする。ただし支払いの場面は8章の形に置き換える。実装順の優先度は「デモの3分間で映る場面」を先に、「早送りで済む場面」を後にする。

**Web が主導線、Slack は Human-in-the-loop（2026-09-21 に決定）。**幹事の作業（イベントの依頼と対話、**領収書・予約画面のアップロード**、内容の確認、状況の把握）は、**Web アプリ**で行う。Slack は、**人の判断・同意が要る場面**（出欠・委任・按分の承認・銀行での承認・予算超過の最終確認・振り返りの回答）と、その通知に使う。狙いは、**ハッカソンの審査員が、提出した URL から実際に触って体験できること**（7.6節）。ただし、**お金の権限に触れる操作（委任・承認・取り消し・振込）は、これまでどおり Slack だけ**にする（Web から触れる経路を作らない）。**例外は、審査員が体験するための `sandbox` のイベントだけ**（7.7節。2026-10-12）。

### 1.2 作る／作らない

| 機能 | 区分 | 実装方針 |
|---|---|---|
| 概要の受付と不足情報の質問 | 作る | **Web のチャット**（幹事）→ ADK 統括Agent。確定した条件は「イベントの計画」カードで幹事が確認して進める（7.5節） |
| **規程文書の参照（RAG Engine）** | 作る | 会社規程の文書を Vertex AI RAG Engine のコーパスに入れ、`retrieveContexts` で参照する。**文書の版管理はしない**（9.7節） |
| 出欠アンケート（DM）とリマインド | 作る | Slack + Cloud Scheduler |
| 支払いの委任（委任状への署名と銀行APIの利用許可） | 作る | 出欠アンケートのモーダルで同意 → AP2のOpen Mandateに署名 ＋ 銀行API（sunabar）のOAuth認可（8.4節） |
| 好み・最寄り駅の収集とインジェクション対策 | 作る | **Agent Gateway × Model Armor** + 隔離抽出（ツールを持たない別のエージェント）+ 値の検証（日本語攻撃文の検知まで実装する。10章） |
| 帰りやすさの計算 | 作る | 駅すぱあと API MCP（範囲探索＋経路探索） |
| 店舗候補の提示 | 作る | Google Maps（**ホットペッパーAPIは不採用。個室・収容人数の補完はあきらめる。2026-09-27決定**）＋ Google Mapsの口コミ本文も判断材料に使う（要ガード、10章）＋ **過去の実績（Memory Bank）を根拠として添える**（9.8節）。**選び方は段階式**（ハード制約で足切り → 最遠の所要時間 → 希望・実績で微調整）で、**選んだ理由を各候補に出す**（9.9節） |
| 予約内容の取り込み | 作る（最小） | **予約画面を Web にアップロード** → Gemini で抽出 → **Web で幹事が確認**（7.5節） |
| 予算上限超過時の確認フロー | 作る | 9.1節 |
| 当日の出席確認 | 作る | Slack（当日欠席は発生しない前提） |
| 会計金額の確定 | 作る（最小） | **領収書を Web にアップロード** → Gemini で読み取り → **Web で幹事が確認**（7.5節） |
| 規程に沿った按分 | 作る | Pythonの決定論的関数＋ユニットテスト |
| 会社補助対象外者への対応 | 作る | 9.3節 |
| 承認者の決定と承認 | 作る | 規程で1名に決定。**Slack App Home**が主導線、DMは通知 |
| **支払いエージェントによる振込依頼** | 作る | AP2の委任状で範囲を検証してから、**銀行API（sunabar）に振込依頼を出す**（8章） |
| **銀行での本人承認と入金確認** | 作る | 参加者が銀行の承認ページで承認（依頼から10分以内）→ 入出金明細で入金を確認して完了にする（8.6節） |
| 承認期限切れの自動再依頼 | 作る | 10分以内に承認されなければ、前の依頼が未完了であることを確かめて作り直す（2回まで。8.7節） |
| 支払いの依頼・完了の通知 | 作る | 参加者へは Slack DM（振込依頼時に「銀行で承認してください」、入金確認後に完了）。幹事へは Web のアプリ内通知 |
| **幹事へのアプリ内通知** | 作る | 確認待ち・人の対応待ち・完了・ブロックを、Web のベル（未読件数）で伝える（7.5節）。Slack DM は補助 |
| **審査員が体験できる導線（ゲスト）** | 作る | **Google ログイン**で試せるサンドボックス（許可リストに載っていないアカウントはゲスト。**匿名認証は使わない**。2026-09-27決定）。自分のイベントだけ見える・書ける。デモ用の代行の要否は**要レビュー**（7.6節、13章） |
| 委任の取り消し | 作る | App Homeから、振込依頼の作成前まで |
| 判断ログ | 作る | Firestore/BigQuery。**Web Dashboard と Slack App Home の両方**に表示。Web では「KUROKOがいましていること」のタイムラインとして見せる（7.5節） |
| Web Dashboard（**幹事の主導線**。審査員・開発者は同じ画面をゲストとして使う） | 作る | 7.3節。幹事は基本的に Web を見る。**事務の確認（予約内容・領収書の金額・店舗候補の選択・予算超過・振り返りのまとめ）は Web で行う**。**按分の内訳も Web に出す**。委任・承認・取り消しは Slack のまま |
| **イベント後の振り返り（フィードバックの収集）** | 作る | 完了の翌日に Slack DM で依頼。参加者は**満足度の1タップ**（必須）と**任意のコメント**だけ。コメントは隔離抽出で語彙に落とし、**原文は保存しない**。**実績（店・人数・1人あたり・予算内か・最遠の所要時間）は入力なしで自動記録**し、幹事は Web で「次回もこの店を使いたいか」の1問に答える（9.8節） |
| **記憶（Agent Platform の Memory Bank）と次回への活用** | 作る | **チームの宴会実績ナレッジ**として、自動記録の実績と最小の評価のうち、**幹事が Web で確認したもの**だけを、検証済みの事実として Memory Bank に書き込む。次回の企画で店舗の提案（順位の微調整と理由）や質問の確認に使う。**金額・按分・承認者・支払先・委任・規程の値には一切使わない**（9.8節、10章） |
| 経費精算の記録 | 作る | PDF生成し幹事に配信（9.5節） |
| 個人情報の削除 | 作る（最小実装でよい） | 9.6節 |
| 主役への通知文面 | 作る | 状況に応じてLLMが生成（9.2節のガード付き） |
| 負担額が委任の上限を超えた場合の本人確認 | **バックログ** | MVPのストーリーでは全員が上限以内。上限超過は `blocked`（`over_cap`）にして幹事に報告する |
| 記憶の個別削除（Web から） | **バックログ** | MVP は TTL（365日）で消える。個別削除は開発者がコンソールで行う（9.8節） |
| eval（評価セット） | **バックログ** | 実施する想定だが今回のMVPには含めない |
| 振込手数料の表示 | **作らない（MVP）** | 按分・DMのどちらにも反映しない |
| 本番の銀行口座での実送金 | **MVPの範囲外** | 送金の処理（委任の検証・振込依頼・本人承認・入金確認）は、**KUROKOが実在の銀行API（sunabar）で実行する**。sunabar はサンドボックスなので資金は仮想（8.8節）。本番化の論点は8.9節 |
| 外部の集金・決済サービス（幹事Pay など）の組み込み | **作らない** | 送金はKUROKO自身が実行する。外部の集金・決済サービスに任せる構成・説明にしない（[PLAN.md](PLAN.md) 16.6） |
| AP2サンプルの模擬決済役（Credentials Provider / Payment Processor） | **作らない** | sunabar に置き換えたため不採用（8.2節） |
| 実店舗の予約代行 | 作らない | 幹事が予約する |
| 終電の考慮 | 作らない | ハッカソン用キーではダイヤ探索が使えない |

---

## 2. アーキテクチャ

### 2.1 全体構成

```mermaid
flowchart LR
    Kanji["幹事・審査員（ブラウザ）"]

    subgraph SlackWS["Slack（Human-in-the-loop）"]
        Member["参加者"]
        Approver["承認者（規程で1名に決定）"]
    end

    subgraph Gateway["Cloud Run: Slack Gateway"]
        Bolt["Slack Bolt for Python<br/>署名検証・3秒Ack・Block Kit"]
        Home["App Home<br/>承認待ち・委任状・進行状況"]
    end

    subgraph Async["非同期処理"]
        Tasks["Cloud Tasks<br/>長時間処理のキュー"]
        Sched["Cloud Scheduler<br/>期限・リマインドの起点"]
    end

    subgraph AgentRun["KUROKO Agent（ADK本体は Agent Runtime、決定論的なコードは Cloud Run）"]
        Agent["統括Agent<br/>観察・判断・行動"]
        Guard["入力ガード<br/>隔離抽出（ツールを持たないエージェント）・値の検証"]
        RouteCalc["帰りやすさ計算"]
        Split["按分計算（決定論的・LLM禁止）"]
        Gate["Policy Gate"]
        Checkout["請求（AP2のMerchant役）"]
        Claim["経費精算PDF生成"]
    end

    subgraph PayRun["支払いエージェント（ADK本体は Agent Runtime、検査・署名は Cloud Run・AP2）"]
        PayAgent["参加者の代理<br/>委任状の保管・検証・振込依頼・入金の確認"]
    end

    subgraph BankRun["Cloud Run: 銀行アダプタ"]
        BankAd["OAuth・振込依頼・依頼状況の照会・入出金明細"]
    end

    subgraph BankExt["GMOあおぞらネット銀行 sunabar（サンドボックス）"]
        BankAPI["銀行API"]
        BankApp["承認ページ<br/>口座の持ち主が承認（10分以内）"]
    end

    subgraph WebRun["Cloud Run: Web Dashboard"]
        Web["幹事の主導線（ゲストも同じ画面）<br/>進行・送金・承諾の状況＋幹事の事務の確認"]
    end

    subgraph GoogleAI["Google Cloud AI・セキュリティ"]
        Gemini["Gemini Flash"]
        RAG["RAG Engine<br/>会社規程の参照"]
        Mem["Memory Bank<br/>過去の経験の記憶（会社・チーム単位）"]
        Armor["Model Armor"]
        AGW["Agent Gateway<br/>ツール呼び出し・入出力の検査"]
        MCP["MCP エンドポイント（KUROKO API・支払いAPI が兼ねる）<br/>4.1の「LLM可」のツールだけを公開"]
    end

    subgraph ExtAPI["外部API"]
        Maps["Google Maps"]
        Eki["駅すぱあと API MCP"]
    end

    subgraph Store["データ"]
        FS["Firestore<br/>イベント状態・委任状・承認・支払い"]
        GCS["Cloud Storage<br/>領収書・予約画面・PDF"]
        BQ["BigQuery<br/>判断ログ"]
        SM["Secret Manager / Cloud KMS<br/>トークン・署名鍵"]
    end

    Member --> Bolt
    Approver --> Bolt
    Bolt <--> Home
    Bolt --> Tasks
    Sched --> Tasks
    Tasks --> Agent
    Agent --> Guard
    Guard -->|"呼び出し（入口の検査）"| AGW
    Agent -->|"ツール呼び出し（MCP）"| AGW
    AGW -->|"検査"| Armor
    AGW --> MCP
    Agent --> Gemini
    Agent -->|規程の参照| RAG
    Agent -->|"記憶の参照（アタッチ。読み取り専用）"| Mem
    API -->|"確認済みの事実の書き込み（コードのみ）"| Mem
    Member -->|"振り返りの回答"| Bolt
    Agent --> RouteCalc
    RouteCalc --> Eki
    Agent --> Maps
    Agent --> Split
    Split --> Gate
    Gate --> Checkout
    Checkout -->|請求| PayAgent
    PayAgent -->|振込依頼| BankAd
    BankAd --> BankAPI
    Member -->|銀行で承認| BankApp
    BankApp --> BankAPI
    PayAgent -->|入金の確認| BankAd
    Agent --> Claim
    Claim --> GCS
    Agent --> FS
    PayAgent --> FS
    Agent --> GCS
    Gate --> BQ
    Agent --> BQ
    PayAgent --> BQ
    Kanji -->|"依頼・アップロード・確認・閲覧"| Web
    Web -->|"チャット・アップロード・確認・閲覧"| Agent
    Agent -->|幹事口座の入金明細| BankAd
    Bolt --> SM
    Agent --> SM
    PayAgent --> SM
    BankAd --> SM
```

主な変更点（2026-09-20）: AP2サンプルの模擬決済役を外し、**銀行アダプタ（sunabar）**、**RAG Engine**、**Memory Bank**を追加。Memory Bank への矢印のうち、**エージェントが行うのは読み取りだけ**（ADK の `load_memory` を統括エージェントにアタッチ。`memoryViewer`）で、書き込みは幹事の確認のあとに**コード（`kuroko-api`）だけ**が行う（9.8節）。AP2 は「委任・請求・領収書の署名による権限の管理」を担い、**送金の処理はKUROKOが銀行APIを通じて実行する**（8.2節）。KUROKO本体はAP2のMerchant役（請求する側）を兼ねる。

図は機能の依存関係を示すもので、ADKのエージェントがツールを呼ぶ経路は `Agent → Agent Gateway → MCP サーバー` に限る（2.3節。**ADK の組み込みの記憶ツール `load_memory` を除く**。9.8節）。`Agent → RouteCalc / Maps / Split / Gate / Checkout …` の矢印は「その機能を使う」という意味で、エージェントが直接つながるという意味ではない。配置は [ARCHITECTURE.md](ARCHITECTURE.md) の構成図を見る。

### 2.2 Slackイベント・Webの依頼の非同期パターン（重要）

**Web のチャットや、アップロード後の読み取り（Gemini）も、数秒〜数十秒かかる。**Web の画面は、依頼を受け付けたらすぐに返し、処理の進み具合を **「KUROKOがいましていること」のタイムライン**（判断ログと、エージェントのイベントから作る）として更新する（7.5節）。長い処理の途中の状態は Firestore が正で、画面はそれを読む。Slack への対応は次のとおり。

SlackはSlackイベント／ボタン押下に対して**3秒以内の応答**を要求する。一方でKUROKOの処理（Gemini呼び出し、駅すぱあと・Mapsの外部API呼び出し、支払いエージェントとのやり取り）は数秒〜数十秒かかる。**Cloud Runは常駐しない**ため、Bolt側で重い処理をブロッキングで行うと確実にタイムアウトする。

```mermaid
sequenceDiagram
    participant Slack
    participant Bolt as Cloud Run (Slack Gateway)
    participant Tasks as Cloud Tasks
    participant Agent as Cloud Run (KUROKO API) + Agent Runtime

    Slack->>Bolt: イベント / ボタン押下
    Bolt-->>Slack: 200 OK（3秒以内、即時ack）
    Bolt->>Tasks: タスク投入（イベント内容）
    Tasks->>Agent: タスク配信
    Agent->>Agent: 判断・外部API呼び出し（数秒〜数十秒）
    Agent->>Slack: chat.update / DM送信（Slack Web API経由）
```

- 承認後の支払いは、**参加者1人につき1タスク**としてCloud Tasksに積む（1人の失敗が他の人の支払いを止めないようにするため）
- **銀行の振込は非同期**。振込依頼APIは依頼直後に「未完了」を返し、口座の持ち主が承認ページで承認して初めて完了する（依頼から10分以内）。**sunabar には Webhook がない**ため、依頼状況と入出金明細の照会は Cloud Tasks / Cloud Scheduler による**ポーリング**で行う（8.6節）
- Slack連携は **HTTPモード（Events API + Interactivity Endpoint）を推奨**。Socket Modeは常時接続が前提でCloud Runのスケールゼロと相性が悪いため使わない

### 2.3 サービス分割

| サービス | 役割 |
|---|---|
| Slack Gateway | **Human-in-the-loop の窓口**。署名検証、3秒Ack、App Home描画、Block Kitの送受信（出欠・委任・按分の承認・銀行での承認の依頼・振り返りの回答） |
| KUROKO Agent | ADKによる統括Agent本体。判断・外部API呼び出し・Policy Gate・請求（Merchant役）。**ADKのエージェントは Agent Runtime、それ以外の決定論的なコードと外部APIの呼び出しは Cloud Run の API（KUROKO API）**に置く |
| 支払いエージェント | 参加者の代理。委任状の保管・検証、Closed Mandateの作成、**銀行への振込依頼**、入金の確認。AP2サンプルの `shopping_agent_v2` を土台にする。**ADKのエージェントは Agent Runtime、検査・署名・鍵は Cloud Run の API（支払いAPI）**に置く |
| Memory Bank（Agent Platform。マネージド） | 会社・チーム単位の経験の記憶（9.8節）。**統括エージェントにアタッチして読み取る**（`load_memory`。読み取り専用の権限）。**書き込みは `kuroko-api`（コード）だけ**。支払いエージェント・隔離抽出エージェントは触れない |
| 銀行アダプタ | sunabar（GMOあおぞらネット銀行の銀行APIサンドボックス）への窓口。OAuthの認可、振込依頼、依頼状況の照会、入出金明細の照会。**参加者のアクセストークンを持つのはこのサービスだけ**で、LLMには渡さない（8.2節） |
| MCP エンドポイント（ツール） | エージェントが呼ぶツールの入口。**KUROKO API と支払いAPI が自分自身で MCP サーバーを兼ね、Cloud Run にデプロイする**。4章の「LLM可」のツールだけを MCP のツールとして公開する（KUROKO Agent は KUROKO API の分、支払いエージェントは支払いAPI の分だけ呼べる） |
| Agent Gateway（Agent Platform。Slack Gateway とは別物） | エージェントの入出力（KUROKO API→エージェント、エージェント→MCP エンドポイント）が必ず通る関所。Model Armor で検査し、エージェントごとに呼べる MCP サーバー・ツールを絞る（10章） |
| Web Dashboard（Web アプリ） | **幹事と審査員（ゲスト）の主導線**。**依頼と対話（チャット）、予約画面・領収書のアップロード**、確認（予約内容・領収書の金額・店舗候補・予算超過・振り返り）、進行・送金・承諾・按分の内訳の閲覧、アプリ内通知。審査員・開発者（ゲスト）も同じ画面を使う。委任・承認・取り消し・振込は扱わない（Slack）。7.3・7.5・7.6節 |

**ツールは MCP 経由で呼ぶ。** エージェントに渡すツールは、KUROKO API・支払いAPI が公開する MCP エンドポイントのうち、4章で「LLM可」としたものだけにする。**入力は、Slack → Slack Gateway（前段。Ackだけ）→ Cloud Tasks → KUROKO API（後段の処理）→ エージェント**の順に渡り、エージェントは必要なときだけ **API を MCP のツールとして呼び返す**。このため、エージェントへの入力も、エージェントが呼ぶツールも、すべて Agent Gateway を通る。4章で「コードのみ」とした処理は MCP のツールに出さない。

KUROKO Agent と支払いエージェントは**別サービス・別サービスアカウント**にする（10章の役割分離）。Slack Gateway と KUROKO Agent は、1サービスに統合することもできるが、[ARCHITECTURE.md](ARCHITECTURE.md) では公開範囲を分けるため**別サービス（同一イメージ・別サービスアカウント）として動かす**。Web Dashboard は Firestore・BigQuery に直接つながず、KUROKO API（読み取りと、幹事の依頼・アップロード・確認）を呼ぶ。ADKのエージェントは、4章のうち「LLM可」のツールだけを、Agent Gateway と API の MCP エンドポイントを通して呼ぶ（エージェント自身は鍵・外部APIのキー・Firestoreに触れない）。

---

## 3. データモデル

Firestoreのコレクション/ドキュメント想定。フィールド名は実装時にスネークケースへ統一してよい。

### Event

| フィールド | 型 | 内容 |
|---|---|---|
| event_id | string | 委任状の `payment_reference` にも使う |
| event_type | string | `welcome_farewell` 固定（MVP） |
| title | string | |
| datetime | timestamp | 開催日時 |
| channel_id | string | 出欠アンケートの送付先チャンネル |
| rsvp_deadline | timestamp | |
| organizer_user_id | string | 幹事（支払先。参加者としての user_id）。Slack との連携は任意（幹事は Web で作業する） |
| organizer_web_uid | string | 幹事の Web 上の本人（Firebase の UID）。**Web からの依頼・アップロード・確認の権限の根拠**（7.3節）。`organizer_user_id` とは別 |
| sandbox | bool | ゲスト（審査員）が作った体験用のイベントか。`true` のときだけ、デモ用の代行（7.6節）を受け付ける |
| guest_owner_uid / expires_at | string / timestamp | `sandbox` のとき、作成したゲストの UID（他のゲストからは見えない）と、削除の期限（作成から7日） |
| guests_of_honor | string[] | 主役のuser_id |
| policy_id / policy_version | string | 適用した規程の識別（RAG Engine のコーパスとファイル。9.7節） |
| budget_escalation | map | 予算超過の確認フロー（9.1節）の記録（`organizer_confirmed_at, escalated_to, escalated_at, final_confirmed_at`）。按分の承認より前に起きるので Event に持つ。Policy Gate 6.1 が、幹事・承認者の両方の確認と、承認者が今の `determine_approver` と同じことを確かめる |
| policy_snapshot | map | 企画時に RAG から抽出し、コードで検証した規程の値（係数・会社補助・上限・承認者の決め方・委任の期限）と、根拠の条文の引用。**このイベントの計算は、この写しだけを使う**（9.7節） |
| memory_scope | map | `{company_id, team_id}`。**企画時にコードが設定する**（ワークスペースの設定から。LLM・Slackの発言・Webの入力からは変更できない）。Memory Bank の読み書きのスコープになる（9.8節） |
| status | enum | `planning / rsvp / venue / booked / day_of / receipt / split / approval / payment / completed / retro / closed`（`completed` = 送金完了・経費記録済み、`retro` = 振り返りの収集と確認、`closed` = 終了） |
| venue | map | `name, address, datetime, party_size, course_price_yen` |
| total_amount_yen | int | 領収書確定後にセット |
| created_at / completed_at | timestamp | |

### Participant（Eventのサブコレクション）

| フィールド | 型 | 内容 |
|---|---|---|
| user_id | string | |
| display_name | string | 幹事・承認者へは実名、LLMへは仮名（10章） |
| member_class_id | string | `director / manager / staff / new_hire`（規程参照） |
| employment_type | string | 例: 正社員・契約社員・業務委託 等 |
| role | enum | `participant / organizer / guest_of_honor / approver` |
| rsvp_status | enum | `pending / attending / declining` |
| mandate_id | string | Mandateドキュメントへの参照（幹事・主役は不要） |
| bank_authorized | bool | 銀行API（sunabar）のOAuth認可が済んでいるか（8.4節） |
| preferences | map | `dietary_must[]`（**食べられないもの**: アレルギー・宗教上など。**ハード制約**）、`dietary_avoid[]`（苦手なもの。ソフト制約）、`request_tags[]`（店の希望。**固定の語彙**）、`nearest_station`。語彙と使い方は 9.9節。イベント完了時に削除対象（9.6節） |
| attendance_confirmed | bool | |
| slack_user_id | string \| null | Slack 上の本人。承認者の本人確認（Policy Gate 6.2）に使う。署名検証済みの Slack 操作の ID と突き合わせる |
| subsidy_eligible | bool | `eligible_employment_types` 判定結果（9.3節） |
| share_yen | int | 按分確定後にセット |
| payment_status | enum | `not_applicable / waiting / awaiting_bank_approval / completed / blocked / failed` |
| payment_id | string | Paymentドキュメントへの参照 |

### Mandate（支払いの委任。参加者1人×イベント1件）

| フィールド | 型 | 内容 |
|---|---|---|
| mandate_id | string | |
| event_id / user_id | string | |
| open_checkout_mandate | string | SD-JWT（参加者の鍵で署名）。請求元 = このイベントのKUROKO、品目 = 負担金×1 |
| open_payment_mandate | string | SD-JWT（参加者の鍵で署名）。制約は8.4節 |
| cap_yen | int | `consent_cap_yen` から設定した上限（表示・検索用の写し。正は委任状の中身） |
| payee | string | 幹事の user_id（表示用の写し）。**振込先の口座は銀行アダプタが解決する**（口座番号はLLMにもFirestoreの本文にも出さない。8.2節） |
| bank_authorization_ref | string | 銀行アダプタが保管する、本人のアクセストークンへの参照（トークン自体は持たない） |
| signed_at / expires_at | timestamp | `expires_at` = 開催日 + `expires_after_event_days` |
| status | enum | `active / used / revoked / expired` |
| revoked_at | timestamp | 取り消した場合 |
| signed_via | string | 署名のきっかけになった、署名検証済みのSlackインタラクションのID |

### VenueCandidate

| フィールド | 型 | 内容 |
|---|---|---|
| name, address, nearest_station | string | |
| max_travel_minutes, avg_travel_minutes | int | 帰りやすさスコアの元データ |
| price_per_person_min/max | int | |
| features | string[] | 例: `個室`, `半個室` |
| source | enum | `google_maps`（ホットペッパーAPIは不採用。2026-09-27決定） |
| review_snippet_used | bool | 口コミ本文を判断に使った場合 `true`。この場合10章の隔離抽出を必ず経由させたことを判断ログに残す |
| memory_note | string | 過去の実績に基づく理由（例: 「前回（2026/06）このチームで利用。個室・1人5,200円で予算内、満足度4.3」）。統括エージェントが `load_memory` の結果から作る。表示専用。**金額・帰りやすさの数値は変えない**。順位への影響は、9.9節の「記憶による調整」だけ（9.8節） |
| memory_refs | string[] | 根拠にした記憶の参照（Memory Bank の記憶名）。判断ログにも残す |
| stage_result | map | 9.9節の段階ごとの結果（コードが作る）: `{hard_passed, excluded_reason, band, preference_match: {tag: 希望した人数}, unmet_preferences[], memory_adjust}`。外れた店の理由も判断ログに要約を残す |
| reason_facts | map | **選んだ理由の元になる数値と事実**（**コードが作る**）: 最も遠い人の所要時間、通ったハード制約、反映した希望と人数、**反映できなかった希望**、緩めた条件、実績の参照。個人は特定しない（「最も遠い方」） |
| selection_reason | string | 選んだ理由の文章。**LLM が `reason_facts` から作る**。`reason_facts` にない数値・店名・人数を含めない（コードが検査し、外れたら定型の文に差し替える。9.9節） |
| role | enum | `overall`（総合の順位の候補）／`preference_first`（希望重視の候補。9.9節の5） |

### Receipt（店の領収書）

| フィールド | 型 | 内容 |
|---|---|---|
| image_ref | string \| null | Cloud Storageパス（**Web からのアップロード**。7.5節）。**手入力（`source = manual`）のときは null** |
| source | enum | 入力元。`upload`（ファイル）・`manual`（読み取れなかったときの手入力）。予約情報にはさらに `paste`（スクリーンショットの貼り付け。ファイルと同じ経路で保存する）がある。判断ログと確認済みの表示に出す |
| uploaded_by / uploaded_at / file_type | | アップロードした幹事の UID・時刻・種別（画像 / PDF） |
| venue_name, date, total_amount_yen | | Gemini抽出結果 |
| line_items | list | |
| confirmed_by, confirmed_at | | 幹事が確定した記録 |

### SplitResult

| フィールド | 型 | 内容 |
|---|---|---|
| policy_id / policy_version | string | |
| base_amount_yen | int | 会計金額 − 会社補助 |
| subsidy_yen | int | 9.3節のルールを適用した実額 |
| weight_sum | float | |
| per_weight_yen | int | |
| rows | list | `{user_id, member_class_id, weight, ratio_percent, subsidy_eligible, share_yen}`。**`ratio_percent` = 負担割合（％）= 係数 ÷ 係数の合計**（主役は0。小数第2位までの表示用）。`share_yen`（負担額）は、丸めた％ではなく、分数で正確に求めた 按分の対象額 × 係数 ÷ 係数の合計 を100円単位で切り捨てたもの（承認者は端数の不足分を含む） |
| shortfall_yen / shortfall_to | int / string | 端数の不足分と負担者 |
| hash | string | 承認対象の金額表のハッシュ値。請求（Checkout）にも埋め込む |

### Approval

| フィールド | 型 | 内容 |
|---|---|---|
| approver_user_id | string | `determine_approver` の結果 |
| split_hash | string | SplitResult.hash と一致確認 |
| status | enum | `pending / approved` |
| approved_at | timestamp | 支払いエージェントを動かすきっかけ |
| approved_by_slack_user_id | string | 実際に承認した人の Slack ユーザーID。**署名検証済みの Slack インタラクションから取った値**だけを入れる（自己申告では入れない）。Policy Gate 6.2 で、承認者本人の `slack_user_id` と一致を確かめる |

### Payment（参加者1人の支払い）

| フィールド | 型 | 内容 |
|---|---|---|
| payment_id | string | |
| event_id / payer_user_id / payee_user_id | string | 支払先は幹事 |
| amount_yen | int | 本人の負担額（AP2の金額は最小単位の整数。日本円は `3300` = 3,300円） |
| checkout_jwt | string | KUROKO（請求側）が署名した請求 |
| closed_checkout_mandate / closed_payment_mandate | string | 支払いエージェントが署名したSD-JWT |
| nonce | string | 使い回し防止。1回の振込依頼ごとに新しく作る |
| transfer_apply_no | string | 銀行の振込依頼の受付番号（sunabar の `applyNo`） |
| idempotency_key | string | 銀行APIの冪等キー。依頼を作り直すたびに新しくする |
| approval_deadline | timestamp | 銀行での本人承認の期限（依頼から10分） |
| retry_count | int | 期限切れで依頼を作り直した回数（最大2。8.7節） |
| bank_result_code | string | 銀行が返した結果（未完了・完了・失敗） |
| settlement_verified | bool | 入出金明細で入金を確認できたか（8.6節） |
| receipt | string | 入金の確認結果に支払いエージェントが署名したもの（AP2の領収書に相当。8.2節） |
| status | enum | `pending / awaiting_bank_approval / blocked / completed / failed` |
| block_reason | string | Policy Gateで止めた理由（例: `over_cap`, `mandate_revoked`） |
| created_at / completed_at | timestamp | |

### DecisionLogEntry

| フィールド | 型 | 内容 |
|---|---|---|
| event_id, timestamp | | |
| actor | enum | `kuroko / payment_agent / human` |
| action_type | enum | `判断 / 規程 / ツール / 送信 / 照会 / ブロック / 検査 / マスキング / 記録 / 更新 / 待機 / 確認 / 署名` |
| summary | string | |
| policy_ref | map | `{policy_id, version, path}` |
| related_entity_ref | string | 例: `participant/xxx`, `payment/yyy`, `mandate/zzz` |

BigQueryへはFirestoreからのエクスポート、またはツール実行時に直接ダブルライトする。Web DashboardとSlack App Homeはどちらもこのエントリを読む。

### Feedback（Eventのサブコレクション。参加者1人×イベント1件）

| フィールド | 型 | 内容 |
|---|---|---|
| user_id | string | 二重回答の防止とリマインドの宛先に使う。**幹事・ゲストの画面には、個人ごとの回答を出さない**（7.3節） |
| rating | int | 総合満足度（1〜5）。**必須。Slack のボタン1タップ** |
| liked | string[] | 良かった点。**任意のコメントから、隔離抽出が読み取った値だけ**（コメントが無ければ空）。**固定の語彙**: `food / atmosphere / private_room / access / price / service / drinks` |
| concerns | string[] | 気になった点。**同上**。**固定の語彙**: `noisy / slow_service / pricey / small / access_far / food_quality / other` |
| submitted_at | timestamp | |

> **見直し（2026-09-26。レビュー06）**: 参加者への質問は、**満足度の1タップだけを必須**にし、良かった点・気になった点のチェックボックスは廃止した（参加者の手間に対して、次回の店選びへの効きが薄いため）。代わりに、**自由にコメントを書ける欄（任意・200字まで）**を置く。
>
> **自由記述（コメント）の原文は保存しない。**コメントは、隔離抽出（`extract-agent`。10章）で上の語彙に落とした値だけを `liked` / `concerns` に加え、原文は破棄する。**個人ごとのコメント・回答は、幹事にも見せない**（集計だけ。7.3節）。

### Retrospective（Eventのサブコレクション。1件）

| フィールド | 型 | 内容 |
|---|---|---|
| status | enum | `collecting / awaiting_organizer / saved / skipped / expired` |
| invited_count / response_count | int | 依頼した人数と回答数 |
| retro_deadline | timestamp | 完了の翌日 + 3日（MVPは定数。9.8節） |
| avg_rating | float | 平均。**回答が3件未満のときは、良かった点・気になった点の内訳を出さず、平均だけ**にする（個人の特定を避ける） |
| liked_counts / concern_counts | map | 語彙ごとの件数 |
| venue_snapshot | map | `name, area, features, place_id`（店の情報。公開情報のみ） |
| party_size | int | 出席者数（**自動**。Participant の `attendance_confirmed` の集計） |
| budget_per_person_yen | int | 会計金額 ÷ 出席者数（1人あたり。**自動**。集計値） |
| within_budget | bool | 1人あたりの会計が、規程の予算の目安（`policy_snapshot`）以内か（**自動**。コードが比べる） |
| max_travel_minutes | int | 選んだ店（VenueCandidate）の、最も遠い人の所要時間（**自動**。個人は特定しない） |
| reuse_intent | enum | 幹事が Web で答える1問「**次回もこの店を使いたいか**」。`yes / no / unanswered` |
| memory_facts | list | **コードが検証済みの値から作った**事実の下書き（`{kind, text, include}`。`kind` は `venue_record`（実績。自動）／`venue_evaluation`（評価））。幹事が Web で含める・含めないを選ぶ（文面の編集はできない） |
| confirmed_by / confirmed_at | string / timestamp | 幹事が Web で確認した記録（Policy Gate 6.4） |
| memory_refs | string[] | Memory Bank に書き込んだ記憶の名前。**書き込みの冪等**に使う（[ARCHITECTURE.md](ARCHITECTURE.md) 8章） |
| saved_at | timestamp | |

### Message（Eventのサブコレクション。Web のチャット）

| フィールド | 型 | 内容 |
|---|---|---|
| message_id | string | |
| role | enum | `organizer / kuroko / system` |
| text | string | 本文。**LLM へは仮名化して渡す**（10章） |
| attachments | string[] | アップロードの参照（予約画面・領収書） |
| proposal_ref | string | このメッセージから作られた提案（イベントの計画・店舗候補など）の参照 |
| status | enum | `pending / done / failed / blocked`（エージェントの処理の状況。Agent Gateway が入口でブロックしたときは `blocked`） |
| created_at | timestamp | |

> 最初のメッセージで、Event を `planning` で作る（`organizer_web_uid` を設定）。

### Notification（幹事へのアプリ内通知）

| フィールド | 型 | 内容 |
|---|---|---|
| notification_id / event_id | string | |
| to_web_uid | string | 宛先（幹事の Firebase UID） |
| kind | enum | `confirm_needed / waiting_on_human / completed / blocked / retro_ready` |
| text / link | string | 定型の文と、Web 内のリンク |
| created_at / read_at | timestamp | |

### ClaimRecord

| フィールド | 型 | 内容 |
|---|---|---|
| pdf_ref | string | Cloud Storageパス |
| items | map | `event_date, venue_name, venue_address, attendees[], attendee_count, total_amount, receipt_image_ref, split_table_ref, approval_history_ref`（`company_rules.yaml` の `claim_record_items` と一致） |
| delivered_to | string | 幹事のuser_id（9.5節） |
| delivered_at | timestamp | |

---

## 4. ツール（Function）契約

`audit.llm_must_not`（`calculate_amounts`, `choose_approver`, `choose_payee`, `modify_policy`, `sign_mandates`）に反する呼び出し経路を作らないことを最優先とする。

**記憶（Memory Bank）は、上の5つに一切影響させない。** 統括エージェントが `load_memory` で読んだ記憶は、金額・按分・承認者・支払先・委任・規程の値の計算や決定に使わない（店舗の提案・質問の省略・説明文だけに使う。9.8節）。この境界は、ツールの引数・出力の型と、12章のテストで固定する。

**公開の仕方**: 「呼び出し元」が **LLM可** のツール（**ADK の組み込みツール `load_memory` を除く**。9.8節）だけを、KUROKO API・支払いAPI が持つ MCP エンドポイントの MCP ツールとして公開する。それ以外（**コード / コードのみ** の処理）は MCP に出さない。エージェントが呼べる MCP エンドポイントとツールは、Agent Gateway のポリシーでも絞る（10章）。

### 4.1 KUROKO Agent

| ツール | 呼び出し元 | 入力 | 出力 | 備考 |
|---|---|---|---|---|
| `retrieve_policy(question)` | LLM可 | 知りたいこと（自然文） | 条文の抜粋と出典 | **RAG Engine の `retrieveContexts`**（9.7節）。判断の根拠・説明文の生成・承認カードの引用に使う。**検索結果は規程文書由来の外部入力**なので、Agent Gateway × Model Armor の検査を通す（10章） |
| `extract_policy_values(event_type)` | コード（RAG検索 → Gemini抽出 → **コードで値を検証**） | event_type | `policy_snapshot`（係数・会社補助・上限・承認者の決め方・委任の期限＋条文の引用） | 企画時に**1回だけ**実行し、Event に保存する。以後の計算はこの写しだけを使う（9.7節） |
| `extract_free_text(raw_text, mode)` | コードが呼ぶ、**ツールを持たない別のエージェント**（`extract-agent`。Agent Runtime。Agent Gateway の入口を通る） | 自由記述と用途（`preferences` / `feedback`。コードが決める） | `preferences`: `{dislikes[], preferences[], nearest_station}`／`feedback`: `{liked[], concerns[]}`（**固定の語彙だけ**。3章 Feedback） | 参加者の回答・Google Mapsの口コミ本文・**振り返りの任意のコメント**に適用（10章）。振り返りの原文は保存しない（9.8節）。`preferences` の出力は、**コードが入力元の欄（食べられないもの／苦手）に従って `dietary_must` / `dietary_avoid` に振り分け**、`preferences[]` は固定の語彙の `request_tags` にする（9.9節）。語彙にない値は捨てる |
| `verify_station(name)` | コード | 駅名 | `{valid, canonical_name, station_code}` | 駅すぱあとAPI |
| `search_accessible_stations(origins[], max_min, relax_step, relax_limit)` | コード | 最寄り駅一覧 | 候補駅一覧 | 5駅ずつ分割して範囲探索 |
| `search_routes(origin, destination)` | コード | 駅ペア | `{minutes, transfers, fare}` | 経路探索（`plain`） |
| `search_venues(area, budget_range, party_size, constraints)` | ツールはコード、提案文はLLM可 | 条件一式（`constraints` = ハード制約とソフト制約。9.9節） | VenueCandidate[]（`reason_facts` つき） | **Google Maps だけ**（ホットペッパーAPIは不採用。個室・収容人数の補完はあきらめる。2026-09-27決定）。口コミ本文は`extract_free_text`経由。**足切り・順位づけ・`reason_facts` は、コードが決める**（9.9節。LLM は順位を決めない）。**選んだ理由の文章（`selection_reason`）だけ LLM が書く**。**過去の実績を根拠に添える場合は、統括Agentが `load_memory` の結果から `memory_note` を作る**（9.8節） |
| `load_memory(query)` | **LLM可**（**ADK の組み込みツール。MCP ではない**。読み取り専用） | 知りたいこと（自然文。例:「このチームが歓送迎会で重視していたこと」） | 記憶の事実（本文・作成時期） | **統括エージェントにアタッチした Memory Bank から類似検索**で引く（9.8節）。**検索のスコープは、`kuroko-api` がセッションの `user_id` として設定したチームのスコープに固定され、LLM は変えられない**。**企画・店舗提案の段階だけ呼べる**（`before_tool` のコールバックで決定論的に制限。ARCHITECTURE 4.9）。書き込みの記憶ツールはエージェントに持たせない |
| `collect_feedback(event_id)` | コード | event_id | 依頼した人数 | 完了の翌日に、出席者へ Slack DM で振り返り（**満足度の1タップ＋任意のコメント**）を依頼する（9.8節）。リマインドは Cloud Scheduler |
| `record_feedback(event_id, user_id, rating, free_text?)` | **コードのみ**（署名検証済みのSlackインタラクション） | 満足度（必須）と任意のコメント | Feedback | コメントは `extract_free_text`（`feedback` 用途）で語彙（`liked` / `concerns`）に落とし、**原文は保存しない** |
| `summarize_retrospective(event_id)` | **コードのみ**（LLM呼び出し禁止） | event_id | Retrospective（**自動記録の実績**・集計・`memory_facts` の下書き） | 実績（店・人数・1人あたり・予算内か・最も遠い人の所要時間）を**イベントのデータから作り**、件数・平均を集計し、**定型の文面テンプレート**から事実の下書き（`venue_record` / `venue_evaluation`）を作る。LLM は使わない |
| `save_memory(event_id)` | **コードのみ**（Policy Gate 6.4 通過後） | event_id | 記憶名の一覧 | 幹事が Web で含めると選んだ事実だけを、**Memory Bank に直接書き込む**（`memories.create` 相当。会話からの自動生成は使わない）。冪等（`memory_refs` があれば再実行しない） |
| `ingest_reservation(image_or_text)` | コード（Gemini抽出→**Web で幹事が確認**） | **Web にアップロードされた**（または**貼り付けられた**）予約画面。手入力のときは呼ばない | `{venue_name, datetime, party_size, course_price_yen}` | 画像内の文字は外部入力として扱う（10章） |
| `check_budget(course_price_yen)` | コード | コース単価 | `{ok, over_hard_limit}` | 超過時は9.1節のフローへ |
| `ocr_receipt(image)` | コード（Gemini抽出→**Web で幹事が確認**） | **Web にアップロードされた**領収書（貼り付けは受けない）。**読み取れなかったときだけ手入力に切り替えられる** | `{total_amount_yen, line_items[]}`（金額だけ。店名・日付は読み取らない） | 画像内の文字は外部入力として扱う（10章） |
| `calculate_split(event)` | **コードのみ**（LLM呼び出し禁止） | Event全データ | SplitResult | 決定論的。ユニットテスト必須（12章） |
| `determine_approver(participants, policy)` | **コードのみ** | 出席者一覧 | approver_user_id | 係数→役職ランク→入社日→社員番号 |
| `generate_guest_message(context)` | LLM可（9.2節のガード付き） | イベント情報（金額を含まない） | メッセージ文 | 送信前に金額関連キーワードの検査を通す |
| `create_checkout(event_id, user_id)` | **コードのみ**（Policy Gate 6.2 通過後） | 承認済みの按分 | 署名付き請求（checkout JWT） | AP2のMerchant役。金額・支払先・`payment_reference`・按分表のハッシュを入れる |
| `confirm_incoming_payments(event_id)` | **コードのみ** | event_id | 入金済みの一覧 | **幹事口座の入金明細**を銀行アダプタ経由で照会し、回収状況を更新する（支払いエージェント側の `verify_settlement` とは独立。8.6節） |
| `generate_claim_pdf(event)` | コード | SplitResult, Receipt, Approval, Payment | PDF（Cloud Storage） | 9.5節 |
| `redact_personal_data(event_id)` | コード | event_id | 削除実行ログ | 9.6節 |

### 4.2 支払いエージェント

AP2 SDK（`ap2.sdk`）とサンプル `shopping_agent_v2` の `mandate_tools.py` を土台にする。サンプルの呼び出し順（制約の確認 → 請求の受け取り → Closed Payment Mandate → Closed Checkout Mandate → 支払いの実行 → 領収書の検証）を使い、きっかけ（サンプルでは値下がり）を「按分の承認」に置き換える。**サンプルの「支払い用トークン → 模擬の決済役」の部分を、「銀行アダプタ経由の振込依頼 → 本人の銀行での承認 → 明細での確認」に差し替える**（8.2節）。

| ツール | 呼び出し元 | 入力 | 出力 | 備考 |
|---|---|---|---|---|
| `sign_open_mandates(user_id, event_id, cap_yen, payee)` | **コードのみ**（署名検証済みのSlackインタラクションが必須） | 本人が同意した条件 | Open Checkout / Payment Mandate | 参加者の鍵で署名。LLMは呼べない |
| `authorize_bank(user_id, code)` | **コードのみ**（本人のOAuth） | 認可コード | アクセストークンの参照 | sunabar の OAuth。トークンは銀行アダプタだけが保管し、LLMにも `payment-agent` にも渡さない |
| `revoke_mandate(mandate_id)` | コード（本人のSlack操作のみ） | mandate_id | status = revoked | **振込依頼の作成前まで** |
| `check_constraints_against_mandate(mandate, checkout)` | **コードのみ** | 委任状、請求 | `{meets_constraints, reasons[]}` | `ap2.sdk.constraints` を使う。6.3節 |
| `create_payment_presentation(checkout_hash, amount, nonce, payee)` | コード | 左記 | Closed Payment Mandate | エージェントの鍵で署名 |
| `create_checkout_presentation(checkout_jwt, checkout_hash, nonce)` | コード | 左記 | Closed Checkout Mandate | |
| `request_bank_transfer(payment_id)` | **コードのみ**（Policy Gate 6.3 通過後） | 確定した金額・振込先 | `{apply_no, result_code, approval_deadline}` | 銀行アダプタ経由で sunabar の振込依頼API。冪等キー付き。**口座番号はLLMに渡さず、銀行アダプタが仮名IDから解決する** |
| `check_transfer_status(payment_id)` | コード | payment_id | `{result_code}` | 依頼状況の照会（ポーリング。sunabar に Webhook がないため） |
| `recreate_transfer(payment_id)` | **コードのみ** | payment_id | 新しい依頼 | 承認の期限切れのとき、**前の依頼が未完了であることを照会で確かめてから**、新しい nonce と冪等キーで作り直す（最大2回。8.7節） |
| `verify_settlement(payment_id)` | **コードのみ** | payment_id | `{verified}` | **本人の口座の出金明細**で振込を確認し、確認結果に署名する。検証が通ったものだけ「完了」にする（8.6節） |
| `notify_payer(user_id, payment)` | コード（文面の一部はLLM可） | 支払いの状況 | Slack DM | 振込依頼時の「銀行で承認してください（10分以内）」と、完了の通知 |

### 4.3 Web アプリから呼ぶ操作（幹事。すべてコード。LLM のツールではない）

Web の画面からの操作は、`kuroko-api` の API が受ける（[ARCHITECTURE.md](ARCHITECTURE.md) 4.5節）。**LLM が呼ぶ MCP ツールではなく**、呼べるのは**幹事（`organizer_web_uid` が一致）だけ**（ゲストは自分の `sandbox` イベントだけ。7.6節）。

| 操作 | 内容 | 関連 |
|---|---|---|
| `send_message(event_id, text)` | チャットの発言を受け、統括Agent に渡す。最初の発言で Event を `planning` で作る。**返答は待たない**: 発言と、`status = pending` の KUROKO のメッセージを保存してすぐ返し、返答は Cloud Tasks で作って同じメッセージを `done` / `failed` に更新する（7.5節）。返答待ちのメッセージがあるあいだは、次の発言を受けない（409 `reply_pending`） | 7.5節 |
| `reset_scenario(mode)` | その画面（`experience` / `live`）で**自分が作ったイベントと、その通知をすべて削除**し、シナリオを最初から始められるようにする（7.7節）。他人・他の画面のイベントは触れない | 7.7節 |
| `confirm_event_plan(event_id)` | 統括Agent が整理した条件（日時・人数・エリア・予算・主役など）を幹事が確認して確定し、出欠依頼（Slack）へ進める | 5章、7.5節 |
| `issue_upload_url(event_id, kind)` / `register_upload(...)` | 予約画面・領収書の**アップロード**（短い期限の署名付きURLで Cloud Storage へ。種類・サイズを検査）。登録後に `ingest_reservation` / `ocr_receipt` を起動する | 7.5節、10章 |
| `confirm_extraction(event_id, kind, values, source)` | 読み取り結果、または**手入力した値**（予約内容・領収書の金額）を、幹事が確定する（Policy Gate 6.1 の「幹事により確定済み」）。**手入力でも、値の検査（型・範囲・語彙）は読み取りと同じ**。判断ログに `source` を残す | 6.1 |
| `select_venue(event_id, candidate)` | 店舗候補から選ぶ | 7.3節 |
| `confirm_budget_overrun(event_id)` | 予算超過の確認（幹事の側。承認者への最終確認は Slack） | 9.1 |
| `confirm_retro(event_id, include[], reuse_intent, decision)` | 振り返りのまとめの確認。**「次回もこの店を使いたいか」の1問**（`reuse_intent`）に答え、記憶へ保存するかを決める（Policy Gate 6.4） | 6.4、9.8 |
| `list_notifications()` / `mark_read(id)` | アプリ内通知 | 7.5節 |

**これらの操作には、委任・承認・取り消し・振込の実行は含まれない**（Slack だけ）。

---

> **2026-10-12 の追加**: `confirm_event_plan` の計画は、エリアを取らず、`rsvp_deadline`（出欠の回答期限。任意）と `guests_of_honor`（幹事が足す主役。名簿の `user_id`）を取る。登場人物のカードの操作（`persona-cards/{card_id}/actions`）は、出欠のカードの入力欄（`inputs.station`・`inputs.dislikes`）を受ける（7.7）。`get_event` は `venue_search`（店の検索の進み具合）を返す。店の検索は、出欠が出そろったときに `kuroko-api` が自分で始める（7.5）。

## 5. イベントのライフサイクル

```mermaid
stateDiagram-v2
    [*] --> 企画
    企画 --> 出欠収集: 幹事がWebで条件を確認して確定（出欠はSlack）
    出欠収集 --> 帰りやすさ計算: 出欠と委任状が揃う
    帰りやすさ計算 --> 店舗提案
    店舗提案 --> 予約確認: 幹事が予約し、予約画面をWebにアップロード
    予約確認 --> 予算超過確認: コース単価 > 7,000円
    予算超過確認 --> 開催前フォロー: 幹事・承認者が確認
    予約確認 --> 開催前フォロー: 上限内
    開催前フォロー --> 当日: 出席確認
    当日 --> 領収書確定: 幹事が領収書をWebにアップロードし、金額を確定
    領収書確定 --> 按分: 決定論的に計算
    按分 --> 承認: 承認者へ提示
    承認 --> 振込依頼: 承認をきっかけに支払いエージェントが依頼を作る
    振込依頼 --> 銀行での本人承認: 参加者へDM（10分以内）
    銀行での本人承認 --> 振込依頼: 期限切れ（作り直しは最大2回）
    銀行での本人承認 --> 入金確認: 本人が承認
    入金確認 --> 完了: 全員の入金を明細で確認
    完了 --> 振り返り収集: 翌日にSlack DMで依頼
    振り返り収集 --> 記憶の確認: 締切（完了+3日）または全員回答
    記憶の確認 --> 終了: 幹事がWebで確認して保存（または保存しない）
    終了 --> [*]
```

`予算超過確認` は9.1節のフローで、承認者はこの時点で `determine_approver` により仮決定できる（出欠確定時点で規程データが揃っているため、開催後の按分承認と同一人物になる）。

---

## 6. Policy Gate

按分計算の前後・支払いの前に、**コードで全項目を満たしたときだけ次に進む**。

### 6.1 按分確定前（KUROKO Agent）

- [ ] Event の `policy_snapshot` が存在し、値の検証を通っている（9.7節。RAG から取れていない状態では按分しない）
- [ ] 出席者・区分・雇用形態が確定している
- [ ] 会社補助の対象人数が `eligible_employment_types` で正しく判定されている（9.3節）
- [ ] 会計金額が幹事により確定済みである（**Web の確認カードで、`organizer_web_uid` が一致する幹事が確定**したもの）
- [ ] 1人あたりの会計単価が上限（7,000円）以内、または9.1節のフローで承認済みである

### 6.2 請求を出す前（KUROKO Agent）

- [ ] 按分案の承認が存在し、承認者のSlackユーザーIDが規程で決定した本人と一致する（署名検証済みのSlackイベントで判定。自己申告のメッセージでは判定しない）
- [ ] 承認された按分案のハッシュ値と、これから請求する金額表のハッシュ値が一致する
- [ ] 請求額の合計が「会計金額 − 会社補助 − 幹事本人の負担額」と一致する
- [ ] **支払先は幹事に固定**（LLMの出力やSlackの発言からは変更できない）
- [ ] 幹事本人と主役には請求を作らない
- [ ] 同じ参加者への完了済みの支払いがない

### 6.3 振込依頼を出す前（支払いエージェント）

KUROKO本体とは別のサービスで、もう一度検査する（請求側を信用しすぎない）。

- [ ] 委任状（Open Mandate）の署名が参加者本人の鍵で検証できる
- [ ] 委任状が有効（`status = active`、期限内、取り消されていない）
- [ ] 請求の `payment_reference` が委任状のイベントIDと一致する
- [ ] 請求の支払先が委任状の `payment.allowed_payees`（幹事）に含まれる
- [ ] 請求額が委任状の `payment.amount_range`（同意の上限）以内。**超えていれば依頼を作らず `blocked`（`over_cap`）にする**
- [ ] 請求にKUROKO（請求側）の有効な署名があり、按分表のハッシュ値を含む
- [ ] nonceが未使用（同じ委任状・同じ請求での二重の依頼を防ぐ）
- [ ] 本人の銀行API（sunabar）のOAuth認可が有効である
- [ ] **振込元は本人の口座、振込先は幹事の口座**。どちらも仮名IDから銀行アダプタが解決する。口座番号とアクセストークンはLLMに渡さない
- [ ] 同じ参加者への**完了済み・承認待ちの依頼がない**。期限切れで作り直す場合は、前の依頼が未完了であることを照会で確かめてから、新しい nonce と冪等キーを使う
- [ ] **入出金明細で入金を確認できたものだけを「完了」にする**（銀行APIの結果コードだけでは完了にしない。8.6節）

### 6.4 記憶を保存する前（KUROKO Agent。`save_memory`）

Memory Bank への書き込みは、**コードで全項目を満たしたときだけ**行う。

- [ ] Retrospective が `awaiting_organizer` で、**幹事が Web で確認済み**である（確認者の Firebase UID が Event の `organizer_web_uid` と一致。Google ログインまたはゲストの認証で判定）
- [ ] 保存する事実は、**`memory_facts` の定型テンプレートから作られたもの**である（LLM が書いた文、幹事が編集した文は保存しない。含める・含めないの選択だけ）
- [ ] 事実の中身は**検証済みの値だけ**で作られている（語彙・件数・平均・店名・エリア・1人あたり金額）。**自由記述（コメント）の原文、個人の氏名・Slack ユーザーID・役職、個人ごとの回答を含まない**
- [ ] **実績の事実（`venue_record`）は、イベントのデータ（VenueCandidate・領収書・出席者数・`policy_snapshot`）から、コードが作った値だけ**で作られている（幹事・参加者が入力した値ではない）
- [ ] 評価の事実（`venue_evaluation`）の「幹事は次回も使いたい／使いたくない」は、**幹事が Web で選んだ `reuse_intent`（`yes` / `no`）だけ**から作る。`unanswered` のときは、その文を含めない
- [ ] 書き込みの**スコープは Event の `memory_scope`**（コードが企画時に設定したもの）に固定されている。リクエストや LLM の出力からは変えられない
- [ ] 回答が3件未満のときは、良かった点・気になった点の事実を作らない（平均だけ。個人の特定を避ける）
- [ ] 同じ Event の記憶が保存済みでない（`memory_refs` が空。二重の書き込みの防止）

---

## 7. WebアプリとSlack（HITL）の設計

**Web が主導線、Slack は Human-in-the-loop（HITL）。**幹事は、依頼・対話・アップロード・確認・状況の把握を、すべて Web で行う。Slack は、**人の判断・同意が要る場面**（出欠、委任、按分の承認、銀行での承認、予算超過の最終確認、振り返りの回答）と、その通知に使う。**お金の権限に触れる操作（委任・承認・取り消し・振込）は Slack だけ**で、Web からは触れない。判断ログは Web Dashboard と Slack App Home の両方に出す。

| 面 | 役割 | 主な利用者 |
|---|---|---|
| **DM** | **参加者・承認者への**通知・リマインド・個別のやり取り（出欠依頼、按分結果、承認依頼、**銀行での承認の依頼**、支払い完了の通知、**振り返りの依頼**など）。幹事には、Slack と連携している場合だけ補助として送る | 参加者・承認者 |
| **Slack App Home**（Home tab） | **承認と委任の操作の主導線**。承認者には「承認待ち」、参加者には「委任中の支払い（上限・支払先・期限、取り消しボタン）」と「支払いの履歴」 | 承認者・参加者 |
| **Web Dashboard（Web アプリ）** | **幹事の主導線**。**依頼と対話（チャット）、予約画面・領収書のアップロード**、進行・送金・承諾の状況と**按分の内訳**の閲覧、**確認**（予約内容・領収書の金額・店舗候補の選択・予算超過・振り返りのまとめ）、**アプリ内通知**。委任・承認・取り消しは扱わない。**審査員が触って体験する画面**（7.6節） | 幹事、ゲスト（審査員・開発者） |
| **銀行の承認ページ**（sunabar） | 振込ごとの本人承認（依頼から10分以内）。KUROKOの画面ではない | 参加者 |

### 7.1 承認の導線

1. 按分確定時、KUROKOはDMで承認依頼を送る
2. 同時に、承認者のApp Homeに「承認待ち」カードを表示する（同じ内容・同じボタン）
3. どちらから承認しても同じ処理（`approval.status = approved`）に到達する。二重承認を避けるため、承認後は両方の面を更新する
4. 承認がそのまま振込依頼のきっかけになることを、承認カードに明記する（「承認すると、7名の支払いエージェントが委任の範囲内で振込を依頼し、各自が銀行で承認します」）

### 7.2 委任の導線（参加者）

> **2026-10-09 の実装方針（モーダルから DM のボタンへ）**: 出欠＋委任は、**モーダルではなく、DM のカードのボタン**（「参加して、委任に同意する」「欠席する」）で受ける。モーダルを開くには、押してから3秒以内に `views.open` を呼ぶ必要があるが、`kuroko-gateway` は Bot Token を持たず（最小権限）、Cloud Tasks を挟むと間に合わないことがあるため。同意の内容（上限・支払先・期限）はカードにそのまま表示し、署名検証済みの操作（押した人が宛先の本人であること）だけが委任状の署名のきっかけになる点は変わらない。

1. 出欠アンケートのモーダルで、出欠と一緒に「上限 ○円まで、幹事の○○さんへの振込を任せる」に同意する
2. 送信（署名検証済みのSlackインタラクション）をきっかけに、コードが委任状に署名する
3. 続けて、**銀行API（sunabar）の認可（OAuth）のリンク**をDMで送る。**委任状の署名と銀行の認可の両方がそろって「承諾済み」**になる（7.3節）
4. App Homeに「委任中」として、上限・支払先・期限・取り消しボタンを表示する
5. 按分の承認後、DMで「銀行で承認してください（10分以内）」と依頼する。本人が銀行の承認ページで承認する（8.6節）
6. 入金を確認したらDMで完了を伝え、App Homeの表示を「支払い済み」に変える

### 7.3 Web Dashboard（Web アプリ）のスコープ（MVP）

**幹事の主導線**。幹事は、**依頼（チャット）・アップロード・確認・状況の把握を、すべてこの画面で行う**（7.5節）。ただし**委任・承認・取り消し・振込は Slack のまま**にする（Web から金額の権限や委任状に触れる経路を作らない）。ビジュアルとコンポーネントの規約は [DESIGN.md](../DESIGN.md)。

**このダッシュボードでわかることは、次の6つに絞る。**（①〜④は当初からの中核、⑤⑥は2026-09-20 に追加）

1. **誰が幹事か**（あわせて、承認者・主役・参加者の役割）
2. **飲み会の全体フローの中で、いまどこか**（5章のステージ。次に誰の対応を待っているか）
3. **実際に誰から誰へ、いくら送金されたか**（送金元 → 送金先（幹事）、金額、状態、時刻。8章の支払い）
4. **まだ送金の承諾をしていない人は誰か**（委任状の署名と銀行の認可（7.2節）が済んでいない人。承認者の承認待ちも、フローの中で示す）
5. **按分の内訳**（誰がいくら払うのか、なぜその金額か。7.3.1）
6. **振り返りと、KUROKOが覚えること**（回答の集計、次回に覚えさせる内容。7.4節、9.8節）

**Web でできる操作（幹事だけ・自分のイベントだけ）**

| 操作 | 内容 | 関連 |
|---|---|---|
| **イベントの依頼と対話（チャット）** | 自然文で依頼し、KUROKOの質問に答え、整理された条件を確認して進める（`confirm_event_plan`） | 4.3、7.5 |
| **予約画面のアップロード** | 予約画面（画像・PDF）をアップロードする、**スクリーンショットを貼り付ける**（Ctrl/⌘+V）、または**手で入力する**。前の2つは `ingest_reservation` が読み取る | 4.1、7.5 |
| 予約内容の確認 | `ingest_reservation` の抽出結果を見て、直して確定する | 4.1 |
| **領収書のアップロード** | 領収書（画像・PDF）をアップロードする。`ocr_receipt` が読み取る。**貼り付けはない**。読み取れなかったときだけ手入力に切り替えられる | 4.1、7.5 |
| 領収書の金額の確認 | `ocr_receipt` の抽出結果を見て、直して確定する（Policy Gate 6.1 の「幹事により確定済み」） | 4.1、6.1 |
| 店舗候補の選択 | 提示された候補（**選んだ理由**と、**記憶に基づく理由**を添えたもの）から選ぶ | 4.1、9.8、9.9 |
| 予算超過の確認（幹事の側） | 9.1節の①。承認者相当への最終確認は Slack のまま | 9.1 |
| **振り返りのまとめの確認** | 自動記録の実績・集計・覚えさせる事実の下書きを見て、**「次回もこの店を使いたいか」の1問に答え**、**含める・含めないを選び**、「次回に覚えさせる」か「覚えさせない」を決める（Policy Gate 6.4） | 4.1、6.4、9.8 |

**Web でできない操作**（**Slack の Human-in-the-loop だけ**）: 委任状への署名と取り消し、按分の承認、予算超過の最終確認（承認者）、振込の実行と銀行での承認、参加者としてのやり取り（出欠・好み・振り返りの回答）。Web の画面には、**「次に Slack で ○○さんの対応が必要です」と待ち相手を表示し、Slack を開くリンクを添える**（7.5節）。

#### 7.3.1 按分の内訳（2026-09-20 に決定: Web に出す）

按分（`SplitResult`）の内訳を、幹事とゲストが Web で見られる。**按分の確定後（`split` 以降）に表示する。**

| 項目 | 内容 |
|---|---|
| 金額の流れ | 会計金額 → 会社補助（実額）→ 按分の対象額 → 係数の合計 → 1係数あたりの金額 → 端数の不足分と、その負担者 |
| 人ごとの表 | 名前（幹事は実名、ゲストは架空のデモ参加者の名前）／区分（部長・マネージャー・メンバー・新入社員）／**係数**／**負担割合（％）**（係数 ÷ 係数の合計。例: 部長 22.22%）／会社補助の対象か／**負担額**。幹事本人と主役の行は「請求なし」と表示する |
| 根拠 | 適用した規程の**条文の引用**（`policy_snapshot`。9.7節）。「区分ごとの係数は第○条による」と読める形 |
| 承認 | 承認者・承認の日時・承認された按分表のハッシュ値（短縮表示）。承認前は「承認待ち（○○さん）」 |

- 数字は `SplitResult` の値をそのまま出す。Web で再計算しない（計算は `calculate_split` だけ）
- **区分と係数が見えるので、幹事は個人の役職を推測できる。**この点は承知の上で表示する（ユーザー決定）。範囲は、**幹事は自分のイベントだけ・ゲストは自分の `sandbox` のイベントだけ**（API 側で強制）。他のイベントの按分は見せない
- 経費精算PDFは、幹事が Web からダウンロードする（9.5節）

> **確定の権威**: 幹事が Web で行う確認・確定（予約内容・領収書の金額・店舗候補・予算超過・振り返り）は、**Web の認証（Firebase の UID）が Event の `organizer_web_uid` と一致する幹事の操作**で担保する。Web の認証に Slack は要らない。金額そのものは、このあとで**承認者が按分表のハッシュ値つきで Slack から承認する**（Policy Gate 6.2）ため、二重に確かめられる。委任と承認は、引き続き **Slack の署名検証済みのインタラクション**だけで行う。

**役割は2つ（2026-09-26 に、審査員と開発者の役割を「ゲスト」に統合）。見られる画面は同じで、範囲と個人情報の扱いだけが違う。**

| 役割 | 見られるイベント | 個人情報の扱い |
|---|---|---|
| **幹事**（`organizer`） | 自分が `organizer_user_id` のイベントだけ | 実名 |
| **ゲスト**（`guest`。**審査員と開発者を区別しない**） | **自分が作った `sandbox` のイベントだけ**（7.6節。サンドボックスの会社「株式会社Akakura」（IT 企業の想定。チームは「第一開発チーム」）） | 架空のデモ参加者の名前（実在の個人情報は存在しない） |

**画面**
- **イベント一覧**: 題名、開催日時、幹事、いまのステージ、承諾の状況（○ / ○名）、送金の進捗（送金済み額 / 請求額）
- **イベント詳細**: 上から順に、①幹事と役割 → ②全体フロー（ステージと待ち相手） → **事務の確認（幹事の役割で、確認待ちのときだけ。予約内容・領収書の金額・店舗候補・予算超過・振り返りのまとめ）** → ③送金の一覧（誰から誰へいくら、状態、時刻） → ④承諾の状況（人ごと） → **⑤按分の内訳** → **⑥振り返り（集計と、覚えさせる内容・保存の状態）** → ⑦経緯（判断ログのタイムライン。折りたたみ。審査員・開発者が動作を確かめるために使う）
- **店舗候補の選択の画面**では、各候補に**選んだ理由**（`selection_reason`。ハード制約を通ったこと・最も遠い人でも○分・**反映した希望と、反映できなかった希望**・緩めた条件）を添える。加えて、**記憶に基づく理由**（`memory_note`）と根拠の記憶の時期を添える（例: 「前回（2026/06）このチームで利用。個室・1人5,200円で予算内、満足度4.3」）。記憶がなければ、記憶の理由は出さない。数値は `reason_facts` の値をそのまま出す（9.9節）

**承諾の状況の見え方**（Participant.`rsvp_status` / `bank_authorized`、Mandate.`status`、Payment.`status` から導く）

| 表示 | 条件 |
|---|---|
| 承諾待ち | 出欠が `pending`（まだ回答していない） |
| 銀行の認可待ち | Mandate が `active` だが、`bank_authorized` が false（7.2節の3） |
| 承諾済み | Mandate が `active` かつ `bank_authorized`（上限額と期限を表示する。署名の原文は出さない） |
| 取り消し済み | Mandate が `revoked` |
| 銀行での承認待ち | Payment が `awaiting_bank_approval`（残り時間と、作り直した回数を表示する） |
| 送金済み | Payment が `completed`（**入出金明細で確認済み**。Mandate は `used`） |
| 止まっている | Payment が `blocked` / `failed`（理由を表示する。8.7節） |
| 期限切れ | Mandate が `expired` |
| 辞退 | 出欠が `declining` |
| 対象外 | 幹事・主役（請求を作らない。6.2節） |

**画面に必ず出す注記**: 送金は **GMOあおぞらネット銀行の sunabar（銀行APIのサンドボックス）を通じて実行**しており、**環境の都合で資金は仮想**（8.8節）。送金の一覧の上に、この環境を明示する（「送金を実行していない」と読める文言にしない）。

**出さないもの**: 好み・最寄り駅などの個人ごとの回答、**振り返りの個人ごとの回答（誰が何を書いたか）**、委任状の署名の原文、**口座番号・銀行のアクセストークン**、エージェントの実行トレースやセキュリティの検知の一覧（必要なら Cloud Logging・Cloud Trace で確かめる）、**Memory Bank の記憶の全件一覧**（保存前の下書きと、そのイベントで保存した記憶だけを出す）。領収書・予約画面の画像は、**幹事が自分のイベントを確認するときだけ**表示する（上の「Web でできる操作」）。按分の内訳は 7.3.1 のとおり出す。

**認証と権限**
- 役割は2つ。どちらも**同じ Google ログイン**で入る（**匿名認証は使わない**。2026-09-27決定）: 幹事の許可リスト（`dashboard_users`）に載っている Google アカウントは**幹事（`organizer`）**、載っていないアカウントは**ゲスト（`guest`。審査員と開発者を区別しない）**（7.6節）。**幹事は Slack ユーザーIDを許可リストに持たなくてよい**（Web の本人確認は Firebase の UID）。Slack との連携は、幹事への補助のDMを送りたいときだけの任意
- 幹事は自分のイベントだけ、ゲストは自分の `sandbox` イベントだけ、という区別は **API 側で強制する**（画面を隠すだけにしない。[ARCHITECTURE.md](ARCHITECTURE.md) 4.5節）。**依頼・アップロード・確認（書き込み）のルートも同じく API 側で、幹事の役割と `organizer_web_uid` の一致を検査する（ゲストは、自分の `sandbox` イベントだけ）**
- Web からの確定の本人確認の根拠は、**Firebase の UID と Event の `organizer_web_uid` の一致**（Slack との対応づけは不要）
- 本格的な認証方式（社内IdP、細かい権限管理）は本番化の論点として明記に留める（13章）

#### 7.3.2 開発者ページ（`/dev`。チーム内の共有。2026-09-27 に決定）

チームメンバーが、**システムの全体像・構成・残りのタスク**を、リポジトリを開かずに Web で確認するための画面。イベント・参加者などの業務のデータは扱わない（`kuroko-api` を呼ばない）。

| 画面 | 内容 |
|---|---|
| 概要（`/dev`） | KUROKO の要約（PLAN.md「現行版の要約」）、いまの状態（TASKS.md 冒頭の「状態」）、**観点（E・I・F・B・O）ごとの進捗**（完了数 / 全体）、**人間の未完了タスク**（human_task.md）、構成の要点（ARCHITECTURE.md 2.2 デプロイ単位の一覧・2.3 構成図） |
| 文書（`/dev/docs/[slug]`） | PLAN・SPEC・ARCHITECTURE・DESIGN・TASKS・human_task・H11 手順書の本文（目次・Mermaid の図つき） |
| タスク（`/dev/tasks`） | TASKS.md と human_task.md の項目を、**状態（未完了・完了）と観点**で絞り込んで一覧する。各項目は開くと本文（依存・完了の条件・経過）が見える |
| 構成図（`/dev/diagrams`） | `docs/diagrams`・`docs/user_flow` の draw.io の図を SVG に書き出したもの |

- **内容の正はリポジトリの文書**。Web では編集しない。進捗は文書のチェック（`[x]`）から集計するので、文書を更新して `main` にマージし、デプロイされると反映される
- **見られる人**: **当面はログインした全員**（審査員を含む。ユーザー決定）。**最終的にはメールアドレスの許可リストで絞る**（バックログ。そのときはサーバー側で ID トークンを検証する）。当面は画面のガードがブラウザ側だけなので、**URL を知っていれば、ログインしなくても内容を取得できる**。そのため、文書に**秘密の値（キー・トークン・口座番号）と、個人のメールアドレスを書かない**（既存の原則。human_task「受け渡し」）
- 役割（幹事・ゲスト）は増やさない（D25 は変えない）。開発者ページはイベントのデータを持たないので、役割の判定と関係しない

### 7.4 振り返りの導線（参加者と幹事）

1. **完了の直後**（2026-10-12 に変更。全員の入金を明細で確認して `completed` になったとき、`kuroko-api` が自分にタスクを投入して `collect_feedback` を呼ぶ。翌日を待たない）、**出席者の全員（幹事を除く）**に「今回の会はいかがでしたか」と依頼する（2026-10-12 に変更。Slack を使える人と、デモの登場人物には、実際にカードが届く。**体験用のイベントで、Slack を使わない架空の参加者のぶんは、デモ用の代行が、決まった値で答える**（乱数・LLM は使わない。経緯に「デモ用の代行」と残す。体験用でないイベントでは、届けられる人にだけ依頼する）。Slack の DM。体験用のイベントでは、Web の登場人物の列にも同じカードを出し、**どちらからでも答えられる**。7.7節）。イベントは `retro` になる。Cloud Scheduler（1日1回）は、依頼が始まっていないイベントの拾い直しと、リマインド・締切だけを担う
> **2026-10-09 の実装方針（コメントは DM への返信）**: 満足度は DM のボタン（1〜5）の1タップで受ける。任意のコメントは、**満足度のあとに、その DM へ返信してもらう**形で受ける（Slack のボタンでは文字を入力できず、モーダルは3秒の制約があるため）。返信は、受け付け中のあいだだけコメントとして扱い、語彙に落として原文を捨てる。

2. 本人が答える（**1タップで終わる作り。必須は満足度だけ**）: **総合満足度**（1〜5のボタン）。**任意で、自由にコメントを書ける**（200字まで。書かなくてよい）。**良かった点・気になった点の選択欄は置かない**（コメントから、隔離抽出が語彙に落とす。3章 Feedback）。送信は署名検証済みのSlackインタラクション
3. **完了の3日後を締切**にする。未回答の人には、2日後に1回だけリマインドする。全員が回答したら、その時点で締切とする
4. 締切後、`summarize_retrospective` が集計と事実の下書きを作り、Retrospective を `awaiting_organizer` にして、**幹事にアプリ内通知で「振り返りがまとまりました。確認してください」と伝える**（`retro_ready`）
5. 幹事が Web で確認する（7.3節）。**自動記録の実績**（店・人数・1人あたり・予算内か）と集計を見て、**「次回もこの店を使いたいか」の1問**（はい／いいえ）に答え、含める事実を選ぶ。**保存を決めるのは幹事**（「次回に覚えさせる」／「覚えさせない」。どちらでもイベントは `closed` になる）。放置された場合は保存しない（`expired`）。**回答を待たずに進めたいとき、幹事は Web で「回答を締め切る」を押せる**（未回答の人がいても、その時点の回答で集計する。デモ・審査で3日待たないため）
6. 保存後、次回以降の企画で、統括エージェントが `load_memory` で引く（9.8節）

回答者には、「個人ごとの回答・コメントは幹事にも見えません。集計だけが使われ、コメントの原文は保存されません」とDMに明記する。

> **なぜ、参加者への質問を最小にしたか**（2026-09-26。レビュー06）: 店の感想は、店側の改善には役立つが、**次回の店選びには、客観的な実績（個室か・1人あたりいくらか・駅から近いか）のほうが直接効く**。実績は、参加者に聞かなくても、イベントのデータから取れる。そこで、参加者への質問は「満足度の1タップ＋任意のコメント」に絞り、実績は自動記録にした（9.8節）。

### 7.5 Web での依頼・対話・アップロード（幹事）

幹事は、Slack を使わずに、次の流れを Web で行う。

1. **依頼と対話**: チャット欄に自然文で依頼する（例:「来週金曜、チーム8人で軽く飲みに行きたい」）。統括Agent が不足情報（日時・エリア・予算・主役・個室の希望など）を質問し、幹事がチャットで答える。**最初の発言で Event が `planning` で作られる**
2. **イベントの計画の確認**: 条件が整ったら、統括Agent が「イベントの計画」（日時・人数・エリア・予算・主役・承認者の見込みなど）を提案し、Web の**確認カード**に出す。幹事が「この内容で進める」（`confirm_event_plan`）と、**出欠依頼が Slack で参加者に届く**
3. **店舗候補の選択**: 帰りやすさの計算と店舗検索の結果が、候補カードとして出る（**記憶に基づく理由つき**。9.8節）。幹事が選ぶ
4. **予約情報の入力**: 幹事が店で予約したあと、予約完了画面を、①ファイル（画像・PDF）のアップロード、②**スクリーンショットの貼り付け**（クリップボードの画像。どの画面からでも Ctrl/⌘+V）、③**手入力**（店名・日時・人数・コース単価を自分で入れる）のどれかで入れる。①②は読み取り結果（店名・日時・人数・コース単価）を確認カードで直して確定する。予算超過なら 9.1節
5. **領収書のアップロード**: 開催後、領収書（画像・PDF）をアップロードし、読み取った金額を確認カードで確定する。ここから按分に進む
6. **状況の把握と通知**: 「KUROKOがいましていること」のタイムライン、全体フロー、送金・承諾の状況、按分の内訳、振り返りを見る。確認待ち・Slack で人の対応待ち・完了・ブロックは、**アプリ内通知（ベル）**で知らせる

**Slack との境界（HITL）**: Web の画面は、Slack で人の対応が要る場面では「**次に Slack で ○○さん（承認者）の対応が必要です**」と待ち相手を出し、Slack を開くリンクを添える。**Web には、承認・委任・取り消し・振込を実行するボタンを置かない。**

**手入力・貼り付けの扱い**: 貼り付けた画像は、ファイルのアップロードと**同じ検査と保存の経路**（署名付きURL、種類・サイズ・件数）を通る。**手入力の値も、読み取りと同じ検査（空・型・範囲）を通り、幹事が確定してはじめて使われる**（確認の権威は「幹事の確認」。6.1）。手入力は、画像が無いので、確定済みの表示と判断ログに「手入力」と残し、領収書では経費精算の記録（ClaimRecord）に「領収書の画像なし（手入力）」と書く。**領収書の手入力は、読み取りに失敗したときに限る**（画像を残す原則を保つため）。

**アップロードの条件**: 種類は画像（JPEG・PNG）と PDF。1ファイル 5MB まで、1イベントあたり予約画面 2 件・領収書 3 件まで。署名付きURL（短い期限）で Cloud Storage に直接アップロードし、種類・サイズをサーバー側でも検査する。**読み取りの結果は、必ず幹事が確認してから使う**（画像の中の文字は外部入力。10章）。

**状態の進み方（2026-10-10 追加）**: 状態を進めるのは**事実**で、LLM ではない。計画の確定（規程の写しと参加者の名簿を用意し、出欠依頼を送る）→ **出欠が出そろう**と店の選択（`venue`）→ 店を選び、**予約の内容を確定**すると `booked`（コース単価が規程の上限を超えるときは、**幹事の確認 → 承認者の最終確認（Slack）**のあとに `booked`）→ 開催後に幹事が**「開催が終わった」**を押すと `receipt` → **領収書の金額を確定**すると `split`（按分の計算と承認依頼）→ 承認者の承認で `payment` → **全員の入金を明細で確認**すると `completed`。領収書は `receipt` の段階でだけ、予約は `venue` の段階でだけ確定できる。**参加者の名簿は、いまは株式会社Akakura（架空）のもの**で、Slack ユーザーは Firestore の `config/slack_users`（登場人物 → Slack ID）から入れる。各段階の遷移は**経緯（判断ログ）**に要約だけ残し（原文・個人情報は入れない）、確認待ち・Slack での待ち・完了は**アプリ内通知**を出す。

**シナリオの進行ヒント（2026-10-10 追加。検証・デモ用）**: Web には、**いまの段階で次に何をするか**を示す「進行ヒント」を出す。内容は `kuroko-api` が**イベントの状態から導いた固定の文**（どこで〔Web／Slack／銀行〕・誰が・何を・入力例）で、LLM は使わない。入力例は架空の値（領収書の金額など）。**ヒントは案内だけで、操作の代行や承認の近道ではない**（Slack で人が行う操作は、Slack で行うことを示すだけ）。チャットは、最終的には Slack に統合する前提で、Web では**検証用**の位置づけとする（`/verify`）。

**幹事の入力は、チャットの中で完結する（2026-10-12 追加。ユーザー決定）**: 計画の確定・店の選択・予約の内容・開催の終了・領収書・按分の内訳・振り返りの確認は、**チャットの流れの最後に出る、KUROKO からの操作のカード**で行う（チャットの外に、別の入力欄を置かない）。**店の候補**は、カードの「店の候補を出す」で出し（`search_venues` と同じ検索。順位・理由・記憶に基づく理由はコードが作る）、候補の「この店にする」で選ぶ（店名は、保存した候補から取る）。入力欄には、**デモ用の候補**を出す: チャットの入力の候補（最初の依頼、「お店を探して」、規程をたずねる質問）を入力欄のすぐ上に並べ、押すと入力欄に入る。計画・予約のカードには、候補の値を入れておく。

**いま話しているイベントを、コードが伝える（2026-10-12 追加）**: 統括エージェントのツールは、イベントの ID を引数に取る。利用者に ID を聞き返さないよう、`kuroko-api` が、**発言の前に固定の形の「システム情報」（イベントの ID・段階・話している人の立場）を付けて**エージェントに渡す。Web では、チャットを開いているイベント。Slack の DM では、**その Slack ユーザーが参加者として載っている、いちばん新しい進行中のイベント**（無ければ付けない）。この情報はコードが作り、利用者の発言からは変えられない（発言の中に同じ形の文があっても、先頭の1つだけが本物）。ツールが返すのは、個人を含まない概要だけ（4.1）。

**予約画面の読み取り（2026-10-12 追加）**: 予約完了画面（画像・PDF）をアップロードすると、`ingest_reservation` が**ツールを持たない Gemini 呼び出し**で、店名・日時・人数・コース単価を読み取る（領収書の `ocr_receipt` と同じ扱い。画像の中の文字は指示として扱わない。結果は型・範囲で検証し、幹事が確認して確定するまで使わない）。読み取れなかったとき・画像が無いときは、これまでどおり手入力できる。Web の画面から、**サンプルの予約画面と領収書をダウンロードできる**（7.6）。貼り付け（Ctrl/⌘+V）は未実装。

**進み具合の見せ方**: エージェントの処理は数秒〜数十秒かかるため、依頼を受け付けたらすぐに返し、タイムラインを更新する（2.2節）。

**返答は非同期で作る（2026-10-12 追加。ユーザー決定）**: Firebase Hosting → Cloud Run の応答は **60秒で打ち切られる**ため、エージェントの実行をリクエストの中で待たない。`send_message` は、①発言を保存し、②`status = pending` の KUROKO のメッセージ（本文は空）を保存し、③Cloud Tasks に返答の生成（`/tasks/internal/chat-replies`）を積んで、すぐ返す。タスクは、そのイベントの**最新の状態**から「システム情報」を作ってエージェントを呼び、返答でメッセージを更新する（失敗は `failed` と固定の文。**タスク側で例外を握りつぶして成功を返す**ので、エージェントの再実行は起きない）。タスクが動かないまま **3分**を過ぎた `pending` は、読むときに `failed` として返す（入力を塞がない）。画面は、`pending` のメッセージがあるあいだ「考え中」を出し、一定間隔で読み直す。

**返答を待つあいだの表示（2026-10-12 追加）**: 返答が遅いと、動いているのか分からない。そこで、**待っているあいだ「考え中」であることを見せる**。Web のチャットは、送った発言をすぐに一覧に出し、「KUROKOが考えています…」と**経過の秒数**を出す（長くなったら、店の検索や規程の確認で30秒ほどかかることがある、と添える）。Slack の DM は、**先に「KUROKO が考えています…」を投稿し、返答ができたら、そのメッセージを返答に書き換える**（書き換えられなければ、新しいメッセージで返す。「考え中」を出せなくても、返答は続ける）。どちらも固定の文で、LLM は使わない。

**チャットの流れの見直し（2026-10-12 追加。ユーザー指定。上の 1〜5 と食い違うところは、こちらが正）**:

- **計画は、KUROKO が出すカードで入れる**: 最初の依頼（デモの候補は「10月30日の19時から、第一開発チーム10人の歓送迎会を行いたい」）を送ると、KUROKO が、確認したい項目を**カード（入力欄）**で出す。項目は、題名・日時・人数・1人あたりの予算・**主役**・**出欠の回答期限**。**場所（エリア）は聞かない**（店は、参加者の最寄り駅から、コードが探す。9.9）。入力欄には、デモ用の値（10月30日 19時・10人・5,000円・回答期限 10月23日）を入れておく。統括エージェントには、`kuroko-api` が「システム情報」に**画面の案内**（カードで入れる項目を文章で質問しない。場所を聞かない）を足して伝える（Web の、`planning` の段階だけ）
- **主役**: 名簿の主役は外せない（名簿の主役は銀行の口座を持たないので、支払う側にしない）。幹事は、ほかの出席者を主役に足せる（幹事・デモの登場人物・承認者は足せない。サーバーが検査する）。**出欠の回答期限**は、開催日より後にできない。出欠のカードに「回答期限」として出す
- **店は、KUROKO が自分で探す**: **出欠が出そろったら**、`kuroko-api` が自分に Cloud Tasks（`/tasks/internal/venue-searches`）を積み、`search_venues` と同じ検索をして、候補をイベントに保存する（幹事が「店の候補を出す」を押すのを待たない）。進み具合は Event の `venue_search`（`searching` / `done` / `failed`）に持ち、画面は「探しています」を出す。失敗したとき・1分たっても終わらないときは、幹事が「もう一度探す」で探し直せる。**候補と、選んだ店は、Google マップで開ける**（公開の検索 URL。別のタブ）。選んだあとは、選んだ店だけを出し、ほかの候補はたたむ
- **予約の内容のカードは、予約の画面を送ったあとに出す**: 店を選んだ直後は、「お店に予約したら、予約完了の画面を、このチャットに送ってください」とだけ出す（幹事が、まず店に予約する）。画面を送る（または「画像なしで、手入力する」を選ぶ）と、読み取った内容を確かめるカードを出す
- **予約を確定すると、参加者に開催の案内が届く**: `booked` になったとき（予算超過のときは、承認者の最終確認のあと）、出席する人（幹事を除く。Slack を使える人と、デモの登場人物）の DM に、**日時・店・Google マップのリンク**を送る（ボタンの無いカード。`kind = notice`）。主役には、費用の話を書かない。やり直しても、同じ人に二重に送らない
- **予約の画面・領収書は、チャットに画像を送る**: アップロードの欄は置かない。入力欄の画像ボタン（または貼り付け）で送ると、送った画像が幹事の発言として出て、KUROKO が読み取りの結果を返す。**どちらとして受け取るかは、段階で決まる**（店を選んだあとは予約の画面、開催のあとは領収書。それ以外の段階では、送れない）。検査と保存の経路（署名付きURL・種類・サイズ・件数）は、これまでと同じ。**サンプルは、ボタン1つで送れる**（「サンプルの予約画面を送る」「サンプルの領収書を送る」。領収書は `frontend/images/sample_receipt.png` を縮めたもの）
- **按分の計算中を見せる**: 領収書の金額を確定してから承認依頼が出るまで、「規程と按分ルールを確認して、按分を計算しています」と、**何を確認しているか**（①会社の規程 ②負担の係数・会社の補助・端数の扱い ③決まった手順のコードでの計算 ④規程にもとづく承認者の決定）を順に出す。**表示だけで、計算はサーバーのコード**（画面で再計算しない。7.3.1）
- **進み具合は、KUROKO の発言として残す**: 計画の確定・出欠が出そろった・店の候補・店の選択・予約の確定・開催の案内・開催の終了・領収書の確定・按分の承認依頼・承認・振り返りの依頼・集計・完了のとき、`kuroko-api` が、**状態から決まる固定の文**を、KUROKO のメッセージ（`role = kuroko`）として保存する（LLM は使わない。個人ごとの回答・口座の情報は入れない）
- **待たせる操作は、ボタンを「送信中」にする**: 押してから応答が返るまで、ボタンを押せなくして「送信中…」と出す（計画の確定は、規程の読み取りと出欠の依頼で数秒〜十数秒かかる）
- **日時の表示**: Slack・Web のカードの日時は、日本時間で出す

**按分の承認から振込の依頼まで（2026-10-13 追加。ユーザー指定。幹事の確認が2回入る）**:

1. 領収書の金額を確定すると、`kuroko-api` が按分を計算し、**幹事のチャットに内訳を出す**（承認者にはまだ依頼しない。状態は `split`）
2. 幹事が内訳を確かめて、「（承認者）さんに承認を依頼する」を押すと、**承認者に承認の依頼が届く**（`POST /api/dashboard/events/{id}/request-approval`。状態は `approval`）。金額は変わらない（計算済みの金額表のまま）
3. 承認者（本人。Slack または体験用の Web のカード）が承認すると、**幹事のチャットに、承認があったことが知らされる**。このとき請求はまだ作らない
4. 幹事が「振込の依頼を送る」を押すと（`POST /api/dashboard/events/{id}/approve-transfers`。承認者の承認があるときだけ）、請求（Policy Gate 6.2）に進み、**参加者に、銀行で承認するお願い（DM。体験用では Web の列にも）が届く**。お金が動くのは、各自が銀行で承認したときだけ（8章）

> これは、1.2・7.5 冒頭の「Web には承認・委任・取り消し・振込を実行するボタンを置かない」の**例外ではなく、確認の追加**である。幹事の2つのボタンは、承認者の承認や、本人の銀行での承認の**代わりにはならない**（どちらも、本人の操作が先に要る）。Policy Gate 6.2 は変わらない。

### 7.6 審査員が体験できる導線（ゲスト。**要レビュー**）

**目的**: ハッカソンの審査員が、提出した URL から、**実際に触って体験できる**こと。

- **入口**: Web アプリの URL に「Google でログインして試す」を置く（Firebase の **Google 認証**。`guest`。**匿名認証は使わない。2026-09-27決定**）。幹事の入口と**同じ Google ログインボタン**で、許可リスト（`dashboard_users`）に載っていないアカウントはゲストとして扱う。**審査員と開発者は区別せず、どちらもこのゲストとして入る**
- **ゲストの権限**: **サンドボックスの会社**（架空の「株式会社Akakura」。架空の規程・過去の記憶（seed）・デモ参加者が入っている）で、**自分が作った `sandbox` イベントだけ**を見られる・書ける。他のゲストのイベント・実名のデータは見られない。**開発者も同じ扱い**で、経緯（判断ログのタイムライン）もゲストに出す（動作を確かめるため）。本番のイベントの調査は Console・BigQuery で行う。**参加者向けの Web 画面は作らない**（参加者は Slack）
- **体験できる流れ**: チャットで依頼 → 条件の確認 → 店舗候補（記憶に基づく理由つき）を選ぶ → 予約画面（**サンプルを画面からダウンロードできる**）をアップロード → 領収書（サンプル）をアップロードして金額を確認 → 按分の内訳 → 承認・委任・銀行での承認（HITL）→ 送金の状況 → 振り返りと記憶
- **デモの配役（2026-10-12。ユーザー決定。動画も審査員の体験も同じ流れ）**: 10人の歓送迎会のうち、**画面に出て操作する人は3人だけ**にする。残りの参加者は、物語の人数をそろえるための架空の人で、名前を前面に出さない
  - **幹事 = Web にログインした人**（審査員を含む）。名簿上の `kanji`。依頼・計画の確定・店の選択・予約の確定・開催後の連絡・領収書の金額の確定を、**そのつど自分で確認して進める**（ここが幹事の Human-in-the-loop）。銀行の口座は1番目（`acct01`。支払先）
  - **赤坂 くらお（一般。名簿上の `kurao`）**: Slack の実在のアカウント。出欠と委任に同意し、自分の振込を銀行で承認する。口座は2番目（`acct02`）
  - **赤くら 花子（部長。名簿上の `hanako`）**: Slack の実在のアカウント。出欠と委任に同意し、**規程で決まる承認者として按分を承認**し、自分の振込を銀行で承認する。口座は3番目（`acct03`）
  - **そのほかの参加者（5人）と主役（2人）**: Slack のアカウントを持たない。**出欠・委任の同意はデモ用の代行が行い**（下記）、振込は `bank-adapter` が代行する（8.10節）。この人たちには Slack のメッセージを送らない
  - 4番目以降の口座（`acct04`〜）は予備で、使わない
- **HITL の扱い（上の配役で決定。下の (A)(B) は検討時の案として残す）**: 参加者・承認者の操作は Slack で行うが、審査員が一人で最後まで体験できるように、次の2つを用意する
  - **(A) Web のみで体験（既定）**: 出欠・委任・銀行の認可と承認・按分の承認を、**デモ用の代行（デモランナー）が、架空の参加者・承認者として行う**。Web には、**「本来 Slack で起きること」**（誰に何を依頼し、誰が承認したか）を、**「デモ用の代行」のラベルつき**で表示する
  - **(B) Slack に参加して体験（任意）**: 審査員が、デモ用の Slack ワークスペース（招待リンクを提出物に記載）に参加し、**承認者として**按分を実際に承認する（本物の署名検証済みの Slack 操作）
- **デモ用の代行の実装（2026-10-12）**: 出欠の依頼を送るとき（`rsvp-requests`）、**Slack のアカウントを持たない参加者**について、`kuroko-api` が出欠を「参加」と記録し、`sa-demo-runner` を主体にした Cloud Tasks で `payment-api` の `POST /mandates` を呼んで、委任状に署名させる（`signed_via = demo-runner`）。`payment-api` は、**`sandbox` のイベントで、かつ Slack のアカウントを持たない参加者**のときだけ受け付ける（Slack のアカウントがある人の委任は、本人の Slack 操作でしか署名できない）。取り消しは代行しない。判断ログに「デモ用の代行」と残す。**按分の承認は代行しない**（承認者は必ず Slack の本人）
- **デモ用の代行の制約**: **`sandbox` のイベントだけ**で使える。Slack の署名検証済みの操作の代わりに、デモランナー専用の identity（`sa-demo-runner`）の操作を受け付ける専用のルートを持つ。**Policy Gate 6.2・6.3 は全項目を同じく検査する**（代行でも、上限・支払先・ハッシュ値・nonce が通らなければ進まない）。委任状の `signed_via` には `demo-runner` を記録し、判断ログにも残す。**`sandbox` が `false` のイベントでは、このルートは拒否する**。LLM はこのルートを呼べない
- **隔離・コスト**: ゲストのイベントは作成から7日で削除する（Cloud Scheduler）。1ゲストあたり、イベント2件・チャット30メッセージ／イベント・アップロード上限は7.5節のとおり。**全体のキルスイッチ**（Firestore の `guest_enabled`）と、Gemini・Agent Runtime の予算アラートを置く。アップロードの画面に「実在の個人情報や領収書を入れないでください」と明記する
- **共有の口座**: sunabar のデモ用の口座は共有なので、ゲストのイベントが同時に動くと明細の照合が混ざる。**振込の付加情報に `payment_id` を載せて突き合わせる**（要検証 V10）。同時に `payment` に入れるゲストのイベントは1件までとする（他は待たせる）
- **このモードで見せられないもの**: 本物の銀行での承認（サンドボックス）、実際のお金の移動（8.8節）。画面の注記で正直に示す

### 7.7 Web のチャット画面（3人ぶんを並べる。2026-10-12。ユーザー決定）

**目的**: 審査員は Slack にも銀行（sunabar）にも入れない。それでも、**1人で最後まで進められ、だれに何が届き、だれが何を承諾したかを、1画面で見渡せる**ようにする。

- **画面**: Web（`/verify`）に、**幹事・赤坂 くらお・赤くら 花子の3人ぶんの「KUROKO とのチャット」を横に並べる**（利用者を切り替えない）。幹事の列は、これまでのチャットと確認の操作。くらお・花子の列には、**Slack に届くのと同じカード**（出欠と委任、按分の承認、予算超過の確認、銀行での承認の依頼、完了の通知）が、同じ文面・同じボタンで出る。くらお・花子の列は、**カードとボタンだけ**（自由入力は付けない）
- **どちらからでも操作できる**: HITL の操作（出欠と委任の同意・欠席、按分の承認、予算超過の最終確認）は、**Web のカードのボタンからも、Slack のボタンからもできる**。先に押されたほうが有効で、もう一方のカードは結果の表示に変わる。Slack への DM は、これまでどおり全員のイベントで送る（くらお・花子のアカウントに届く）
- **Web から押せる人と範囲**: **体験用（`sandbox`）のイベントを作った本人**が、そのイベントの**デモの登場人物（くらお・花子）として**押せる。体験用でないイベントでは、Web から押せない（Slack の本人だけ。1.1節の原則は変えない）。カードの中身（上限・支払先・期限・金額表のハッシュ値）は、**サーバーに保存したカードから取る**（ブラウザから送られた値は使わない）
- **記録**: Web から押した操作は、Slack の操作と区別して残す。委任状は `signed_via = demo-runner`（`sa-demo-runner` の経路。7.6節）、按分の承認は `approved_via = web_demo` と、押した人の Web の UID。**Policy Gate 6.2 は、`web_demo` の承認を、体験用のイベントで、押した人がそのイベントを作った本人のときだけ通す**。それ以外の検査（金額表のハッシュ値・再計算との一致・委任状・上限・支払先）は、Slack のときと同じ
- **銀行での承認（体験用）**: 体験用のイベントでは、くらお・花子の振込を sunabar に送らず、`bank-adapter` が**「承認待ち」の代行の振込**として持つ。くらお・花子の列に「銀行で承認してください」のカードが出て、**「銀行で承認する（体験用）」を押したときだけ**、承認済みになる（押すまで、明細に載らず、支払いは完了しない。この振込は10分の期限で失効させない）。ほかの5人の振込は、これまでどおり自動の代行（8.10節）
  - **承認の体験（2026-10-12 追加）**: Web のボタンを押すと、**銀行の承認ページを模した画面**（振込先・金額・依頼人。「本物では、銀行のサービスサイトにログインし、取引パスワードで承認します」の注記つき）が開く。そこで「承認する」を押すと、承認済みになり、「承認が完了しました」を表示する。**ログインとパスワードの入力は再現しない**（成功したことだけを見せる）。同じ依頼を **Slack の DM にも送り**（くらお・花子）、DM の「銀行で承認する（体験用）」ボタンからも承認できる（署名検証済みの本人の操作だけ）。どちらで押しても同じ処理で、効くのは体験用の「承認待ち」の振込だけ
- **振り返り（2026-10-12 追加）**: 完了の直後に、満足度（1〜5）のカードが、くらお・花子の列と Slack の DM に届く。Web から押せるのは、ほかのカードと同じく、体験用のイベントを作った本人だけ。個人ごとの回答は、画面に出さない（カードは「回答済み」になるだけ）
- **実演用（動画）**: Firestore の `config/demo` の `live_bank_emails` に入れた Google アカウントが作ったイベントだけ、くらお・花子の振込を**本物の sunabar** に送る（8.10節のとおり、本人がサービスサイトで承認する）。このときの銀行のカードには、ボタンを出さない
- **共有の口座での取り違えの防止**: 体験用のイベントは、全員が同じ幹事口座（`acct01`）の明細を見る。別のイベントの同じ人・同じ金額の入金で回収済みにならないよう、**体験用のイベントでは、そのイベントの支払いが完了している人だけ**を、明細との照合の対象にする
- **変えないもの**: LLM は、これらの操作に関わらない（カードのボタンは決定論的なコードが処理する）。金額・承認者・支払先の決定も変わらない
- **画面は2つ（2026-10-12 追加。ユーザー決定）**: 作りは同じで、参加者・承認者が操作する場所だけが違う。どちらも、3人ぶんのチャットを**最初から開いて**並べる
  - **体験用（`/verify`。審査員）**: これまでの説明のとおり。くらお・花子の列のカードを、この画面から押せる。銀行は、承認ページを模した画面。**実演用に登録したアカウントでも、この画面から作ったイベントは体験用になる**（開発者が、審査員の見え方を確かめられる）
  - **実演用（`/demo`。開発者）**: くらお・花子は **Slack の DM と、本物の銀行（sunabar のサービスサイト）**で操作する。列は、届いたカードを映すだけ（ボタンは出さない。サーバーも、実演用のイベントでは Web からの操作を受け付けない）。振込は、本物の銀行 API に依頼する。**使えるのは、`config/demo` の `live_bank_emails` に入れたアカウントだけ**（それ以外は、イベントを作れない。API で強制）
  - どちらの画面で作ったかは、イベントの `ui_mode`（`experience` / `live`）に残し、一覧は画面ごとに分ける。実演用に登録したアカウントは、体験用のイベントの上限（2件）を受けない（リハーサルのため。50件まで）
- **クリア（最初からやり直す。2026-10-12 追加。ユーザー決定）**: どちらの画面にも、「最初からやり直す」ボタンを置く（押すと確認してから実行）。**その画面（`ui_mode`）で自分が作ったイベントと、その通知だけ**を削除する（イベントの下の参加者・メッセージ・カード・按分・アップロードの記録は、イベントごと消える。他人のイベント・もう一方の画面のイベントは触れない。サーバーが利用者の UID と `ui_mode` で絞る）。体験用ではイベント数の上限（2件）も、これで空く。**実演用で、すでに銀行に出した振込の依頼は取り消されない**（こちらの記録が消えるだけ。リハーサルの後始末用）。Cloud Storage に置いたアップロードの実体は、7日の自動削除に任せる
- **DM のように見せる（2026-10-12 追加。ユーザー指定）**: 3つの列は、それぞれ「KUROKO との DM」として出す（Slack・LINE のような見た目）。**KUROKO の発言は、左に KUROKO のアイコン・上に名前と時刻**、自分（幹事）の発言と送った画像は右寄せ。くらお・花子の列の見出しには、本人の顔のアイコンを出す（画像は `frontend/public/avatars`）。操作のカード（計画・店・予約・領収書・按分・振り返り）も、KUROKO の発言として出す。**ページ全体はスクロールさせず、各列の発言の流れだけをスクロールする**（狭い画面では縦に積み、各列の高さを画面の中に収める）
- **出欠のカードの入力欄（2026-10-12 追加）**: くらお・花子の出欠のカードに、**最寄り駅**と**苦手な食べ物**の入力欄を出す（デモ用の値を入れておく）。「参加して、委任に同意する」を押したときに取り込む（「欠席する」では取り込まない）。**最寄り駅**は、駅名の形を検査し、駅すぱあとで**一意の駅に決まったときだけ**、駅コードで持つ（LLM を通さない。決まらなければ、名簿の値のまま）。**苦手な食べ物**は、隔離抽出（`extract-agent`）で固定の語彙に落とし（加えて、語彙の語がそのまま書かれていれば拾う）、ソフト制約（`dietary_avoid`）として持つ。**書いた文そのものは、保存しない・ログに出さない・統括エージェントに渡さない**。開催の完了後に削除する（9.6）。Slack の DM のカードには、この入力欄はまだ無い（Slack で聞く導線は未実装。名簿の最寄り駅を使う）
- **デモの終わり（2026-10-12 追加）**: イベントが `closed` になったら、幹事の列に「デモは、ここまでです」と、済んだこと（依頼 → 出欠 → 店 → 予約 → 按分 → 承認 → 振込 → 振り返り）のまとめと、「最初からやり直す」を出す。画面の上と、イベントの札にも「デモ完了」「終了」を出す
- **進行ヒント（2026-10-12）**: 幹事の列の先頭に、**いつも**「次にすること」を出す（イベントを作る前も）。体験用では、Slack・銀行に行かせる案内をしない（すべて、この画面でできる）。くらお・花子の列にも、その人が次にすること（カードを押す／対応なし）を出す

---

### 7.8 Slack から依頼を始める（実演用。2026-10-13。ユーザー決定）
実演（動画）では、幹事が **Slack の DM から依頼を始められる**。Web の実演用の画面（`/demo`）でも、同じ依頼を始められる（どちらでもよい）。

- **対象**: Firestore の `config/demo.live_slack_users`（`{Slack ユーザーID: Google アカウントのメール}`）に登録した人だけ。メールは `live_bank_emails` にも入っていること（入っていなければ無効）。**登録が無くても**、Slack のプロフィールのメール（`users.info`。`users:read`・`users:read.email`）が `live_bank_emails` のアカウントと同じなら、同じ人として扱う。どちらでもない人の DM は、これまでどおり会話として答える。
- **依頼の判定**: 発言が企画の依頼か（会の種類・日時・人数など）を、**コードで**決める（`looks_like_plan_request`）。あいさつ・雑談は、依頼にしない（エージェントが答える）。依頼のときは、**エージェントを通さず**、イベントと計画の案を作る。
- **計画の案**: 依頼文から、日時・人数・題名を**決まった書き方だけ**で読み取る（`plan_from_text`）。読み取れない項目は、デモの既定の値にする（予算 5,000円。回答期限は開催の1週間前）。検証は、Web の計画のカードと同じ `validate_plan`。
- **確定**: Slack のカードの「この内容で進める」（`Action.PLAN`）。**依頼した本人だけ**が押せる（ゲートウェイが、押した人と宛先の一致を確かめる。サーバーも `organizer_slack_user_id` と照らす）。確定のあとは、Web で確定したときと同じ（規程の写しの用意・出欠の依頼）。Web の計画のカードからも確定できる（先に押したほうが有効）。
- **Web への引き継ぎ**: Slack から始めたイベントには、Web の本人（UID）がまだ無い。**同じメールで Web にログインしたとき**、そのイベントを本人のものとして引き継ぐ（メールは署名検証済みのトークンから取る。他のアカウントには、見えず・引き継がれない）。実演用の画面は、新しいイベントが現れたら、それを開く。
- **幹事の操作は、すべて Slack の DM で行う**（ユーザー決定。2026-10-13。Slack App に `files:read` が要る）。各場面で、KUROKO が DM のカード（ボタン）を送る。ボタンは `Action.ORG`（値の `o` で操作を分ける）で、**依頼した本人だけ**が押せる（`organizer_slack_user_id`）。中身は、Web の操作（`DashboardService`）と同じ検査を通る（`slack_op`）。

  | 場面 | Slack の DM | 押す・送るもの |
  |---|---|---|
  | お店の候補が出た | 候補（駅・移動・価格・Google マップ）のカード | 「この店にする」（候補ごとのボタン） |
  | 店を選んだ | 予約を促す文 | **予約完了の画面を画像で送る** → 読み取り結果のカード →「この内容で確定する」 |
  | 予算超過 | 上限と単価のカード | 「続行して、承認者に確認を依頼する」 |
  | 予約の確定 | 開催が終わったら押すカード | 「開催が終わった」 |
  | 領収書 | 画像を促す文 | **領収書を画像で送る** → 金額のカード →「この内容で確定する」 |
  | 按分の計算後 | 内訳のカード | 「承認者に承認を依頼する」 |
  | 承認者が承認 | 承認の連絡 | 「振込の依頼を送る」 |
  | 参加者が銀行で承認 | 「〇〇さんからの支払いが承認され、振り込みが実行されました」 | — |
  | 振り返りの集計 | 集計のカード | 「また使いたい／使わない（記憶に残す）」「記憶に残さない」 |

- **画像**: Slack の DM に添えた画像（`file_share`）を、Bot Token で取得し（Slack のドメインだけ・10MBまで）、**いまの段階**（店を選んだあとは予約画面、開催のあとは領収書）に合わせて読み取る。結果は、確定のボタンを押すまで使われない（Web のアップロードと同じ。Cloud Storage には保存しない）。
- **Web の実演用の画面は、見るだけ**: 進み具合（5段階）・次にすること・くらお／花子の2人ぶんの DM を映す。**幹事のチャット画面は出さない**（幹事の操作・入力欄は Slack の DM。2026-10-13）。
- **しないこと**: Slack から、お金を直接動かす操作はしない。振込は、これまでどおり、各自が銀行で承認する。

### 7.9 記憶・規程を Web で参照する（体験用・実演用の両方。2026-10-13。ユーザー決定）
KUROKO が根拠にしている情報を、Web の画面で確かめられるようにする。画面の操作の帯の「記憶・規程を見る」から開くダイアログで、読むだけ（変更はできない）。

- **記憶（Memory Bank）**: 次の企画のお店選びで、過去の実績として参照される事実の一覧。読むスコープは、お店選びが読むものと同じ（`read_scopes`）。体験用のゲストは、自分が保存したものと、事前に入れたチームの記憶だけ（ほかのゲストのものは見えない）。保存先が未設定・読めないときは、その旨を出して、規程は見せる。事実は定型の文だけで、個人の名前・個人ごとの回答は入っていない（9.8）。
- **会社の規程・按分ルール**: 規程の文書（`policies/company_rules.md`）の条文と、按分に使う値（負担区分と係数・委任の上限・会社の補助・端数・コース単価の上限・承認者の決め方・帰りやすさ）。値は、開いているイベントの規程の写しがあればそれ（文書から読み取った値か既定の値かも示す）、なければ既定の値。
- **API**: `GET /api/dashboard/reference?event_id=`。

## 8. 支払いフロー（AP2の委任と銀行APIでの送金）

### 8.1 世界観

参加者は出欠の回答時に、「この会の負担金を、**上限○円まで**、**幹事に**払うこと」を自分の支払いエージェントに委任する（AP2の委任状に本人の鍵で署名し、あわせて銀行APIの利用を認可する）。按分方針が承認されると、支払いエージェントは請求が委任の範囲内かを検証し、**銀行API（sunabar）に振込を依頼する**。銀行は振込ごとに口座の持ち主の承認を求めるため、参加者は銀行の承認ページで承認する（依頼から10分以内）。支払いエージェントは**入出金明細で入金を確認してから**「完了」にする。

> **ピッチでの言い方の例**: 「参加者は最初に『上限』と『支払先』だけを決めて任せます。エージェントは、準備から入金の確認まで全部やりますが、**その範囲の外では振込を作りません**。そして、お金を動かす最後の一押しだけは、口座の持ち主にしかできない設計にしています。」

> **言い方の注意**
> - **KUROKOは、送金を自分で実行する側**として説明する。「集金や決済は他のサービスに任せ、KUROKOは判断と承認だけを担う」とは言わない。幹事Pay のような外部の集金・決済サービスを、送金の手段として組み込まない（[PLAN.md](PLAN.md) 16.6）
> - 「AP2 で送金する」とは言わない。AP2 が担うのは**権限と証跡**（委任・請求・領収書の署名）で、送金の処理は**KUROKOが銀行APIを通じて実行する**（8.2節）
> - sunabar はサンドボックスなので、「実際のお金が動く」とは言わない。「実在の銀行APIで、依頼から入金確認まで実行する（資金は仮想）」と言う（8.8節）

### 8.2 AP2と銀行API（sunabar）の役割分担

**層が違うので共存する。**

| 層 | 担当 | 役割 |
|---|---|---|
| 権限と証跡 | **AP2** | 委任状（上限・支払先・期限）、請求、署名の連鎖。範囲外の依頼を止める |
| 送金の実行基盤 | **銀行API（sunabar）**。**KUROKO（支払いエージェントと銀行アダプタ）がここを通じて送金を実行する** | 振込依頼、口座の持ち主による承認、入出金明細 |

| AP2の役割 | KUROKOでの担当 | 実装 |
|---|---|---|
| ユーザー | 参加者 | Slack（モーダル・App Home）＋ **銀行の承認ページ** |
| Shopping Agent | **支払いエージェント**（参加者の代理） | ADK。AP2サンプル `shopping_agent_v2` を改修 |
| Merchant | **KUROKO本体**（イベントの請求を出す側）。支払先は幹事 | KUROKO Agent内のツール（サンプル `merchant_agent_mcp` を参考に実装） |
| Credentials Provider | 参加者の口座とアクセストークンの解決役 | **銀行アダプタ**。トークンは Secret Manager に置き、LLM にも `payment-agent` にも渡さない |
| Merchant Payment Processor | 幹事への入金処理役 | **銀行アダプタ**が sunabar の振込依頼APIを呼ぶ |
| 領収書（Receipt） | 入金の事実 | **入出金明細で確認した結果に、支払いエージェントが署名したもの**（決済事業者の署名付き領収書は使えないため） |

**噛み合わない点と対処**（AP2 v0.2 が正式に対応するのはカードなどの pull 型で、銀行振込のような push 型はロードマップ上の項目。この接続は公式サンプルの範囲外のカスタム実装になる）

| 点 | 対処 |
|---|---|
| AP2 の委任は本来「本人がその場にいなくても払ってよい」という許可だが、銀行は振込ごとに本人の承認を求める | 委任の意味を「**この範囲の振込依頼を作ってよい**」に読み替える。上限を超える依頼や、幹事以外への依頼を作れない歯止めは残る（6.3節） |
| サンプルは同期的に領収書まで返るが、銀行は非同期で承認待ちの状態がある | 状態遷移に `awaiting_bank_approval` を足し、ポーリングで追う（2.2節、8.6節） |
| 決済事業者の署名付き領収書がない | 支払いエージェントが**本人の口座の出金明細**を自分で確認して署名する。請求側の申告に頼らないので、役割分離としてはむしろ強い |

**役割分離**: KUROKO本体（請求側）は参加者の委任状に署名できない。支払いエージェントは按分の金額を変えられない。銀行アダプタだけがアクセストークンと口座番号を持つ。3者は別サービス・別サービスアカウントで動かす。

### 8.3 3つの鍵

| 鍵 | 誰が | いつ | 意味 |
|---|---|---|---|
| 1. 本人の委任 | 参加者 | 出欠回答時 | 上限・支払先・期限を決めて委任状に署名し、銀行APIの利用を認可する |
| 2. 按分方針の承認 | 承認者（規程で1名） | 開催後 | 誰がいくら払うかを確定する（按分表のハッシュ値） |
| 3. 銀行での本人承認 | 参加者 | 振込ごと | **お金を動かす最後の一押し**。依頼から10分以内に、銀行の承認ページで承認する |

2026-09-17 版の鍵3「委任状と領収書の検証（コード）」は、鍵3ではなく**全体にかかる検査**として残る（Policy Gate 6.3）。お金を動かす最後の判断は、口座の持ち主が銀行で行う。

### 8.4 委任状と請求の中身

| 種類 | 署名する鍵 | いつ | 主な内容 |
|---|---|---|---|
| Open Checkout Mandate | 参加者 | 出欠回答時 | 請求元 = このイベントのKUROKO、品目 = 「歓送迎会（10/30）の負担金」×1 |
| Open Payment Mandate | 参加者 | 出欠回答時 | `payment.allowed_payees` = 幹事、`payment.amount_range` = 上限まで（一般なら 6,000円）、`payment.payment_reference` = イベントID、`exp` = 開催日＋7日 |
| 銀行APIの認可（OAuth） | 参加者 | 出欠回答の直後 | sunabar のアクセストークン。**AP2の委任状とは別物**で、両方そろって「承諾済み」になる（7.2節） |
| 請求（Checkout） | KUROKO（請求側） | 按分の承認後 | 金額 = 本人の負担額、支払先 = 幹事、按分表のハッシュ値 |
| Closed Checkout / Payment Mandate | 支払いエージェント | 振込依頼時 | 確定した金額・支払先・nonce |
| 領収書（Receipt） | 支払いエージェント | 入金の確認後 | **入出金明細で確認した結果**に署名する（8.2節） |

- 金額はISO 4217の最小単位の整数で表す。日本円は小数がないので、3,300円は `3300`（サンプルは米ドル前提で `amount_cents` という名前を使っているため、改修時に注意）
- 上限は規程の `member_classes[].consent_cap_yen`、期限は `payment.payer_mandate.expires_after_event_days` から決める（値は Event の `policy_snapshot`。9.7節）
- **口座番号は委任状にも請求にも入れない。**仮名の `user_id` だけを載せ、口座は銀行アダプタが解決する（10章）

### 8.5 シーケンス

```mermaid
sequenceDiagram
    autonumber
    actor M as 参加者
    participant S as Slack
    participant P as 支払いエージェント
    participant K as KUROKO（請求側）
    actor A as 承認者
    participant BA as 銀行アダプタ
    participant B as sunabar（銀行API）
    actor O as 幹事

    M->>S: 出欠回答＋支払いの委任に同意（モーダル）
    S->>P: 署名検証済みの同意
    P->>P: Open Mandate に署名して保存
    M->>BA: 銀行APIの利用を認可（OAuth）
    BA->>BA: アクセストークンを保管（LLMには渡さない）
    Note over K: 開催・領収書のアップロード（幹事がWebで確定）・按分
    K->>A: 按分方針の承認依頼（App Home・DM）
    A->>K: 承認
    Note over K: Policy Gate 6.2
    K->>P: 請求（本人の負担額・支払先・按分表ハッシュ）
    Note over P: Policy Gate 6.3<br/>署名・期限・支払先・上限・nonce・認可
    P->>P: Closed Payment / Checkout Mandate を作成
    P->>BA: 振込依頼（仮名ID・金額・冪等キー）
    BA->>B: 振込依頼API（口座はここで解決）
    B-->>BA: 未完了（承認待ち。10分以内）
    P->>M: 「銀行で承認してください」（DM）
    alt 期限内に承認
        M->>B: 承認ページで承認（取引パスワード）
    else 期限切れ
        P->>BA: 前の依頼が未完了かを照会 → 作り直す（最大2回）
        P->>M: 再通知（DM）
    end
    P->>BA: 入出金明細を照会（本人の出金）
    BA->>B: 参照系API
    P->>P: 入金を確認して領収書に署名
    P->>M: 完了の通知（DM）
    K->>BA: 幹事口座の入金明細を照会
    K->>O: 回収状況を更新（Web Dashboard）
```

> **この図のどこに LLM が関与するか**（2026-09-26。レビュー06）: LLM が関与するのは、①按分の承認依頼に添える**説明文**と、②「銀行で承認してください」「完了」の**通知文**の作成だけ（送信前に、コードが検査する）。加えて、支払いエージェントが**次にどのツールを呼ぶか**を選ぶが、手順は固定で、順序違いの呼び出しは `payment-api` が拒否する（[ARCHITECTURE.md](ARCHITECTURE.md) D10）。**Policy Gate（6.2・6.3）、Open Mandate の署名、振込依頼の作成、期限切れの作り直し、入金の照合、領収書への署名、幹事口座の照会は、すべてコード**（`kuroko-api`・`payment-api`・`bank-adapter`）。図の「支払いエージェント」は AP2 の役割名（Shopping Agent）に合わせた呼び名で、金額や可否を判断する主体という意味ではない。LLM に渡るのは仮名（`User_001`）と区分だけで、**実名・口座番号・アクセストークンは渡さない**（10章）。

### 8.6 承認待ちと入金の確認

- 振込依頼APIは依頼直後に「未完了」を返す。この時点では**送金は成立していない**ので、`awaiting_bank_approval` にする
- **sunabar には Webhook がない**ため、依頼状況の照会と入出金明細の照会は、Cloud Tasks / Cloud Scheduler による**ポーリング**で行う（2.2節）
- 「完了」にしてよいのは、**入出金明細で入金を確認できたときだけ**。銀行APIの結果コードだけでは完了にしない（6.3節）
- 確認は2か所で独立して行う。**支払いエージェント**は本人のトークンで**本人の出金明細**を見て、支払いの完了を判断する。**KUROKO本体**は幹事のトークンで**幹事の入金明細**を見て、回収状況を更新する
- **幹事の入金明細の確認も、Cloud Scheduler のポーリングで自動で行う**（2026-10-12）。`kuroko-api` の `POST /tasks/scheduled/collections`（1分ごと。`sa-scheduler` だけ）が、`payment` のイベントのうち、**支払いが完了したのに、幹事口座の入金がまだ確認できていない人がいるもの**だけを対象に、`confirm_incoming_payments` を呼ぶ（待つ理由が無いあいだは銀行を呼ばない。開催日から31日を過ぎたイベントは対象外）。支払いの完了は**確認を始めるきっかけ**に使うだけで、回収済みにするかは、これまでどおり幹事口座の明細だけで決める。全員ぶんを確認できたら、イベントを `completed` にする
- 入金額が請求額と違う場合は、本人に差額を伝え、追加の依頼を作るかを幹事に確認する

> **2026-10-12 の追加**: 入金の明細は、開催日から照会する。**開催日が先の日付のまま精算まで進めたとき（デモ。10月30日の会を、その前に通す）は、今日からの明細で照合する**（照会の開始日が終了日を超えると、銀行に照会できないため）。

### 8.7 取り消し・期限切れ・範囲外の扱い

- 参加者は**振込依頼が作られるまで**、App Homeから委任を取り消せる。取り消された人の支払いは `blocked`（`mandate_revoked`）にし、幹事に報告する（その人の分の回収方法は幹事が決める）
- **銀行での承認が10分以内にされなかった場合**は、前の依頼が未完了であることを照会で確かめたうえで、新しい nonce と冪等キーで依頼を作り直し、再通知する（**最大2回**）。それでも承認されなければ `failed` にして幹事に報告する
- 請求額が委任の上限を超えた場合は依頼を作らず `blocked`（`over_cap`）にし、幹事に報告する。本人にSlackで確認して払う流れは**バックログ**。MVPのストーリーでは全員が上限以内
- 銀行APIがエラーを返した場合は `failed` にし、幹事に報告する（自動の再試行はしない。冪等キーがあるため、再試行してもよい場面はあるが、MVPでは人に返す）

### 8.8 sunabar の制約（MVPの前提）

| 制約 | 影響 |
|---|---|
| **サンドボックスで、資金は仮想**（実際のお金は動かない） | 「実際のお金が動く」とは言わない。API・OAuth・承認・明細照会は本物の銀行APIの仕様 |
| **振込先も sunabar 内の口座に限られる** | 幹事の口座も sunabar 口座にする |
| **1ユーザーあたり最大10口座**（初期は個人・法人の各1口座） | デモの参加者10名分の口座は、チームメンバーで分担して用意する（13章で検証） |
| **全口座を1人が持つと、振込ごとの承認も実際には1人が行う** | デモでは、**実際に銀行で承認するのは1人だけ**にして、残りの人の振込は代行する（8.10節） |
| **Webhook がない** | 状況の確認はポーリング（8.6節） |
| **アクセストークンは、ポータルに30日以上ログインしないと失効する** | 審査期間中（提出〜12/1）にログインを続ける |

### 8.9 本番化に向けた論点（説明文に書く）

- **sunabar は無料の銀行APIサンドボックスで、資金は仮想**。ただし OAuth・振込依頼・振込ごとの本人承認・入出金明細の照会は、本物の銀行APIの仕様どおりに実装している
- 参加者の依頼で振込の指図を銀行に伝える事業は、銀行法の**電子決済等代行業（更新系）の登録**が必要とされる。登録、または登録事業者・銀行との提携が要る。**法的な判断は専門家への確認が必要**であることもあわせて明記する
- 個人（幹事）が支払いを受け取る形は、規約や資金移動に関する規制の確認が必要（専門家に要確認）
- AP2（v0.2）が正式に対応する支払い手段はカードで、リアルタイムの口座振込のような push 型はロードマップ上の項目。本書の接続は公式サンプルの範囲外のカスタム実装であることを明記する（8.2節）
- 参加者の署名鍵は、本番では本人の端末（パスキーなど）に置く。MVPはサーバー側で管理する（10章）

### 8.10 デモでの振込の代行（2026-10-11。2026-10-12 に配役を変更。ユーザー決定）

ストーリーの参加者は10人のままにする。ただし、**実際に銀行（sunabar のサービスサイト）で振込を承認するのは、Slack に実在する2人（赤坂 くらお・赤くら 花子）だけ**にする。振込元の7人ぶんを、口座ごとにログインし直して10分以内に承認するのは、デモ・審査の場で現実的でないため。

- **口座の割り当て**: 1番目（`acct01`）= 幹事（Web にログインした人。支払先）、2番目（`acct02`）= 赤坂 くらお、3番目（`acct03`）= 赤くら 花子。4番目以降は予備で使わない。ほかの参加者は実機の口座を持たず、`bank` の対応表には代行用のラベル（`demo-<user_id>`）だけを置く
- **実機に通す人**: `bank-adapter` の設定 `DEMO_LIVE_PAYER_LABELS`（口座ラベル。既定は `acct02,acct03`）に入れた振込元だけ。この人の振込は、これまでどおり sunabar に依頼し、本人がサービスサイトで承認して、はじめて成立する。「銀行で承認してください」の Slack DM も、この2人にだけ届く
- **代行する人**: それ以外の振込元。`bank-adapter` が**銀行を呼ばずに「承認済み」として記録**し、明細（本人の出金・幹事の入金）にも実機と同じ形で載せる。受付番号は `SIM` で始まり、記録に `simulated: true` が付く。Slack のアカウントが無いので、通知は送られない
- **変えないもの**: 代行は銀行の窓口（`bank-adapter`）の内側だけで起きる。**委任状の署名と検証、Policy Gate 6.2・6.3、請求の署名、冪等性、「明細で確認できたときだけ完了」（8.6節）は、全員ぶんが同じコードで動く**。金額・支払先・承認者の決定にも関わらない
- **画面の表示**: 代行した人も、実機の人と同じく「支払い済み」と表示する。**代行があることは、提出物の説明と手順書に明記する**（[submission.md](submission.md)）。実機の明細（sunabar の画面）に載るのは、実機に通した2人ぶんだけ
- **切り替え**: `DEMO_LIVE_PAYER_LABELS` を1人だけ（例 `acct02`）にすると、銀行で承認する人を1人に減らせる。空にすると代行は無くなり、全員が実機になる（アプリの既定は空。Terraform の変数 `demo_live_payer_labels` で入れている）

---

## 9. 個別設計判断

### 9.1 予算超過時の確認フロー

`budget.hard_limit_per_person_yen`（7,000円）を超えるコース料金が予約完了画面から読み取られた場合:

1. KUROKOが**幹事**に超過額を伝え、続行してよいか確認する（**Web Dashboard**。7.3節。通知はアプリ内通知）
2. 幹事が確認したら、KUROKOは**承認者相当（規程のapprover_selectionで決まる、多くの場合部長など最上位者）**に転送し、最終確認を求める（**Slack**）
3. 幹事・承認者の両方の確認が揃って初めて、次のステップ（開催前フォロー）に進める
4. 承認者が確認しない場合は幹事に差し戻し、代替の店舗候補を再提示する（MVPでは簡易な差し戻しでよい）

この時点の承認者は、出欠確定時点のデータで`determine_approver`を実行した仮決定値でよい（開催後の按分承認と同一人物になる設計）。

### 9.2 主役への通知文面（LLM動的生成）

- 状況（歓迎か送別か、対象人数、日程）に応じてLLM（Gemini Flash）が都度生成する。主役には委任の依頼も送らない
- ガード: 生成後、金額・支払い・委任に関するキーワード（例:「円」「振込」「支払」「按分」「委任」）を含んでいないかを**決定論的なコードで検査**してから送信する。含まれていた場合は送信をブロックし、固定テンプレートにフォールバックしたうえで判断ログに記録する

### 9.3 会社補助対象外者の按分（要レビュー）

規程の `eligible_employment_types`（正社員・契約社員）に該当しない出席者がいた場合:

- **会社補助の対象人数**を「対象外の人を除いた人数」で数える（`subsidy_yen = per_attendee_yen × 対象人数`、上限は変わらず）
- **按分の対象額**（会計金額 − 会社補助）は、対象外の人を含めた**全出席者の係数で通常どおり按分**する
- 幹事向けの集計には「会社補助の対象外 n名」を表示する（個人名は出さない）
- 対象外の本人への通知には、「雇用区分の都合で会社補助の対象外です」と一言添える

### 9.4 振込手数料（MVPでは非表示）

`payment.fee_paid_by: payer` は規程データとしては保持するが、按分計算・DM表示のどちらにも反映しない。sunabar はサンドボックスなので実費も発生しない（8.8節）。

### 9.5 経費精算の記録（PDF配信）

`generate_claim_pdf` でPDFを生成し、**幹事が Web からダウンロードできるようにする**（Cloud Storage の署名付きURL。短い期限）。経理への提出は幹事が人手で行う（`company_rules.yaml` の `claimed_by: organizer` と整合）。PDFの承認履歴には、支払いごとの**入金の確認結果**（8.6節）も載せる。

### 9.6 個人情報の削除（デフォルト実装）

- **全参加者の支払いが完了（または `blocked` / `failed` で確定）したことを確認し、幹事への完了通知（アプリ内通知）を送るのと同じタイミング**で、Participantドキュメントの `preferences`（最寄り駅・苦手なもの）を削除する
- ドキュメント自体は残し、対象フィールドのみ削除する（判断ログや集計値は残ってよい）
- 使い終わった委任状は `used` / `expired` にする（監査のため原文は残す）
- **銀行APIのアクセストークンも、同じタイミングで銀行アダプタから破棄する**（口座番号の対応表も残さない。8.2節）。**デモでは行わない**（sunabar の口座は、全部のイベントで共有するデモ用の口座で、トークンは口座ごとに1つしか無いため。2026-10-12）
- **実装（2026-10-12）**: `kuroko-api` が、イベントを `completed` にするのと同時に、全参加者の `preferences` を空にする（`redact_personal_data`）。経緯には件数だけ残す
- 実装はCloud Tasksの完了処理チェーンの最終ステップとして組み込む（`redact_personal_data` を呼ぶ）
- **振り返りの回答（Feedback）**: 自由記述の原文は最初から保存しない（3章）。`Feedback.user_id` は、Event が `closed`（振り返りの終了）になった時点で削除する（集計値は Retrospective に残る）
- **Memory Bank の記憶**は、個人情報を含まない形（チーム単位の集計・店名・エリア）でしか書かない（9.8節）。期限（TTL）は365日

### 9.7 規程文書の参照（RAG Engine）

会社規程を、**Vertex AI RAG Engine**（Agent Platform）のコーパスに入れて参照する。**文書の版管理は行わない**（MVP の範囲外）。

> **2026-10-12 の実装（ユーザー決定: 仮の規程の文書を作り、エージェントがそれを調べる）**: 規程の文書は [`policies/company_rules.md`](../policies/company_rules.md)（架空の「懇親会費用規程」。条文の形）。
>
> - **エージェントが調べる（`retrieve_policy`）**: 統括エージェントは、規程に関わること（負担の割合・会社の補助・予算の上限・承認者の決め方・委任など）を聞かれたら、**自分の判断で MCP ツール `retrieve_policy(event_id, question)` を呼び**、返ってきた条文だけをもとに、「第○条」を添えて答える。ツール（`kuroko-api`）は、文書を**条ごと**に分け、質問に合う条を最大2条だけ返す（全文は返さない）。検索は、質問と条文の文字の重なりで決める決定論的なコード（`services/policy_search.py`）。経緯に「エージェントが、規程の文書（第○条）を参照しました」と残す（質問の文は残さない）。条文は外部入力として扱い、エージェントは条文の中の文を指示として扱わない。エージェントは、条文を読んでも個別の金額を計算しない
> - **Gemini に、文書の全文は渡さない**。値の読み取り（`extract_policy_values`）も、値のまとまりごとに同じ検索を行い、見つかった条の抜粋だけを渡す
> - **RAG Engine は使わない（2026-10-12 ユーザー決定）**。規程の検索は、`kuroko-api` の自前のコードで確定とする（既定の構成の RAG Engine は Spanner の常時の費用がかかり、文書が1つで短いため）。下の図と箇条書きのうち、RAG Engine・`retrieveContexts`・コーパス・Gateway での検索結果の検査は、実装しない
>
> 読み取るのは、計画を確定するときの1回だけ（`extract_policy_values`。**ツールを持たない呼び出し**。条文の中の文は指示として扱わない）。結果は、**コードが型と範囲で検証**してから `policy_snapshot` に入れ、値ごとに**根拠の条番号**（例: 係数 = 第4条）を残して、按分の内訳に出す。読み取れない・検証に通らないときは、`company_rules.yaml` の値を使い、経緯に「規程の文書から読み取れなかったため、既定の値を使いました」と残す（下の「フォールバック」）。金額の計算は、これまでどおり `calculate_split`（コード）だけ。下の図と箇条書きのうち、「RAG Engine のコーパス」「`retrieveContexts`」「検索結果の Gateway 検査」は、この実装では通らない。

```text
規程の文書（PDF）→ RAG Engine のコーパス
      ↓ retrieveContexts
条文の抜粋 → Gemini が値を抽出 → コードで値を検証 → Event の policy_snapshot
      ↓
calculate_split（決定論的）／承認カードとWebに「規程第○条」の引用を出す
```

- **抽出は企画時に1回だけ**（`extract_policy_values`）。結果は Event の `policy_snapshot` に保存し、以後の計算はこの写しだけを使う。計算のたびに抽出し直すと、同じ入力で按分が変わりうるため
- **`calculate_split` は決定論的なまま**（`audit.llm_must_not: calculate_amounts`）。LLM が条文から金額を計算することはしない。LLM がするのは「条文から係数・上限などの値を読み取ること」までで、その値はコードが**型と範囲**で検証する（例: 係数は 0〜3、1人あたりの上限は 0〜20,000円）。範囲を外れたら按分に進まず、幹事に差し戻す
- **規程の文書は間接インジェクションの入口になりうる**。RAG の検索結果も、ツールの応答として Agent Gateway × Model Armor の検査を通す（10章）
- **`policies/company_rules.yaml` の役割を変える**。実行時の正ではなく、①**抽出結果を検証するテストの正解データ**（12章）②RAG が使えないときのフォールバック、とする
- 規程文書の登録（コーパスへの取り込み）は、MVP では**開発者が事前に行う**。管理者の役割と取り込み画面は作らない
- 判断ログには、これまでどおり `policy_ref`（`policy_id`・`version`・参照した箇所）を残す（3章）
- **要検証**: RAG Engine の対応リージョン（東京リージョンに未対応の可能性があり、その場合は別リージョンに置く）と、日本語のPDF（表・段組）の抽出精度（13章）

### 9.8 振り返りと記憶（Agent Platform の Memory Bank）

PLAN.md の「会社専属の幹事として経験を蓄積する」（4.6・8章）を実装する。イベントの後に**実績を自動で記録し、最小の振り返りを集め**、**幹事が確認したものだけ**を Agent Platform の **Memory Bank**（エージェントの長期記憶）に書き込み、次の企画で使う。

> **2026-10-12 の実装**: 保存先は、**統括エージェントの Agent Runtime のインスタンスに付く Memory Bank**（`KUROKO_AGENT_ENGINE` と同じエンジン。設定は `MEMORY_BANK_ENGINE`）。**書き込みも読み取りも `kuroko-api` のコード**が行う（`memories.create` と、スコープを指定した取得）。読み取りは、**店の候補を探すとき**（`search_venues`）に、同じスコープの事実を取り、**同じ店名の実績**を、順位の調整（9.9節(c)）と `memory_note`（記憶に基づく理由）に使う。事実は定型の文なので、コードが値（店名・1人あたり・予算内か・満足度・幹事の「また使いたい」）を読み戻す。**統括エージェントへのアタッチ（`load_memory`）は、エージェントの再デプロイが要るので後回し**（下の「どう使うか」のうち、質問の確認・説明文は未実装）。スコープは、体験用のイベントでは**作ったゲストごと**（`team:sample-co:dev1:guest:<uid>`。ほかの審査員の記憶と混ざらない）で、読むときだけ、事前に入れた記憶（seed）のスコープ `team:sample-co:dev1` も合わせて読む。体験用でないイベントは `team:sample-co:dev1`。最も遠い人の所要時間は、選んだ店の候補を保存していないので、事実に入れない。`MEMORY_BANK_ENGINE` が空のあいだは、保存の操作を受け付けない（振り返りは確認待ちのまま）。
>
> **位置づけ（2026-09-26 の見直し。レビュー06）**: 記憶は、参加者の感想の集まりではなく、**チームの宴会実績ナレッジ**（客観的な事実の台帳）とする。理由: ①店の感想は、参加者に入力を求める手間に見合うほど、次回の店選びに効かない ②メンバーが入れ替わっても、**店の事実（個室か・1人あたりいくらか・予算内か・駅から近いか）は使える** ③個人の食べられないもの・苦手なもの・最寄り駅は、**毎回本人に聞いて、その会の店選びにだけ使い、終わったら削除する**（9.6節）ので、個人を記憶にひもづける必要がない。個人を記憶にひもづけないのは、LLM への仮名化（10章）とは別の、**プライバシーの設計判断**である。

```text
完了: コードが「実績」を自動で記録（店・人数・1人あたり・予算内か・最も遠い人の所要時間。入力なし）
      ↓
完了の翌日: 出席者にDMで振り返りを依頼（満足度の1タップ＋任意のコメント）
      ↓ コメントは隔離抽出で語彙に落とす（原文は捨てる）
締切: コードが集計し、定型テンプレートから「記憶の事実」の下書きを作る
      ↓
幹事がWebで確認: 「次回もこの店を使いたいか」の1問に答え、含める・含めないを選ぶ → 「次回に覚えさせる」（Policy Gate 6.4）
      ↓ 直接書き込み（会話からの自動生成は使わない）
Memory Bank（スコープ = 会社・チーム）
      ↓
次の企画: 統括エージェントが load_memory（アタッチ。読み取り専用）で引く → 店舗の提案・質問の確認に使う
```

**何を覚えるか（事実は2種類。文面は定型テンプレート。スロットに入るのは検証済みの値だけ）**

| kind | 由来 | 文面のテンプレート（例） |
|---|---|---|
| `venue_record`（**実績**） | **入力なし**。イベントのデータから、コードが作る | 「{チーム}の{イベント種別}（{年/月}）で『{店名}』（{エリア}・{特徴}）を{n}名で利用。1人あたり{金額}円（コース{金額}円）で予算{内／超過}。最も遠い人の所要時間は{分}分。」 |
| `venue_evaluation`（**評価**） | 参加者の満足度の1タップ、任意のコメントから読み取った語彙、幹事の1問 | 「{チーム}の{イベント種別}（{年/月}）の『{店名}』の満足度は平均{平均}（{n}名回答）。幹事は次回も{使いたい／使いたくない}。良かった点は{語彙}。気になった点は{語彙}。」 |

- **`venue_record` は、回答が0件でも作れる**（次の3件未満のルールの影響を受けない）。これが、振り返りの回答が少なくても、記憶が空にならない理由
- `venue_evaluation` は、**幹事が `reuse_intent` に答えていなければ、「幹事は…」の文を含めない**。回答が3件未満のときは、良かった点・気になった点の文を含めない（平均と幹事の回答だけ）
- 旧 `budget_trend`（1人あたりの会計）は、`venue_record` に統合した

**覚えないもの**: 参加者の氏名・Slack ユーザーID・役職、個人ごとの回答、自由記述の原文、個人の好み・最寄り駅（9.6節で削除対象）、個人の負担額、口座、規程の値。

**どう使うか（記憶が影響してよい範囲）**

- 店舗候補の提示: 候補に `memory_note`（記憶に基づく理由）と時期を添える。**順位への影響は、9.9節の「記憶による調整」だけ**（同じ帯の中で、同じ店の実績・幹事の「また使いたい」で加点、「使いたくない」で減点）。**候補の金額・帰りやすさの数値は変えない**
- 質問の確認: 例えば予算を聞くとき、「前回は1人あたり5,500円前後でした。今回も同程度でよいですか」と**確認する形**にする（記憶で勝手に決めない）
- 説明文: 「前回、個室の店で満足度が高かったので、今回も個室を優先しました」
- **影響させないもの**: 金額・按分・承認者・支払先・委任・規程の値・Policy Gate（4章冒頭）。予算の上限は規程（`check_budget`）が決め、記憶は過去の実績を示すだけ

**設計上の判断（ARCHITECTURE D20）**

- **書き込みは、コードだけが、検証済みの値から、幹事の確認のあとに、直接書き込む。**Memory Bank には会話（セッション）から事実を自動生成する機能もあるが、**使わない**。会話に混ざった攻撃文が長期記憶に残り、以後のイベントに影響し続ける（記憶の汚染）ことを避けるため
- **読み取りは、Memory Bank を統括エージェントにアタッチして行う**（ADK の `VertexAiMemoryBankService`＋**`load_memory`**）。**読み取り専用**にするため、①エージェントの identity には**読み取り専用のロール（`roles/aiplatform.memoryViewer`）だけ**を付ける（`agent-payment`・`agent-extract` には付けない）②エージェントとコールバックから、`add_session_to_memory` など**書き込みの API を呼ばない**（テストで固定）③スコープを絞る IAM Conditions を併用する（要検証）。`PreloadMemoryTool`（毎ターン自動で検索して注入する）は**使わない**。按分・承認の説明など、記憶を使わない場面にまで注入されるため
- **`load_memory` は、企画・店舗提案の段階だけ呼べる。**`before_tool` のコールバックが、セッションの state の段階（`planning` / `venue`）を見て、それ以外では実行を止める（決定論的。LLM の判断に頼らない）
- **スコープはコードが決める。**ADK の検索スコープは `app_name` と `user_id` で決まるので、`kuroko-api` がセッションを作るとき、**`user_id` に Event の `memory_scope`（3章）から作ったチームのスコープID（`team:{company_id}:{team_id}`）を入れる**。LLM は `user_id` を変えられない（呼び出しのパラメータ）。他のチーム・会社の記憶は引けない。**書き込み側（`kuroko-api`）も同じスコープで書く**（一致していないと、書いた記憶が引けない。要検証）
- **読み取りの結果（Memory Bank → エージェント）は、MCP を通らず直接返る**ので、その区間には Agent Gateway の検査（Model Armor）が掛からない。**一方、それを踏まえたエージェントの応答は、Agent Gateway の入口（`streamQuery` の応答）で Model Armor が検査する**（応答用のテンプレート。公式ドキュメントで、ADK エージェントの `streamQuery` の要求と応答が対象とされている）。**多層の役割分担**: ①記憶に攻撃文が混ざること自体は、**書き込みの入口**（定型・検証済み・幹事の確認）で防ぐ（主）②応答に出てくる有害な内容・機微情報・悪意のあるURLは、**Gateway の応答の検査**で止める（多層）。ただし、応答の検査は、記憶に混ざった攻撃文が**モデルの判断（ツールの呼び出しなど）に影響すること自体は防げない**ので、影響の範囲は「お金に届かない設計」（4章冒頭・Policy Gate）で固定する。応答側で効くフィルタの範囲は要検証（13章、ARCHITECTURE V8）
- **記憶を参照したことの記録**: `kuroko-api` が、`stream_query` が返すイベント（`load_memory` の呼び出しと結果）から、判断ログに「記憶を参照した」を書く（記憶の本文は残さない）
- **期限（TTL）は365日**。個別の削除は MVP ではバックログ（開発者がコンソールで行う）
- 回答が3件未満のときは、良かった点・気になった点の事実を作らない（3章 Retrospective、Policy Gate 6.4）
- **デモ**: 3分の中に「次回の企画」を通しで入れる時間はないので、**過去のイベントの記憶を事前に投入（seed）**しておき、企画の場面で引く。今回の会の振り返り → 幹事の確認 → 保存は、別の場面（または早送り）で見せる（13章「要準備」）
- **要検証**: Memory Bank の対応リージョン（`global / us / eu`。東京は記載なし）、会社・チーム単位のスコープの指定、直接書き込みと検索のAPI、日本語の検索の品質、既存記憶との統合の挙動、構造化された「プロファイル」（チームの傾向）の利用（13章、ARCHITECTURE V12）

### 9.9 店舗の選定ロジックと説明責任（2026-09-26。レビュー06）

PLAN.md 4.2節の「段階式」を、実装できる粒度にする。**足切りと順位づけは、コードが決める**（`backend/src/services/venue_ranking.py`。LLM を呼ばない。同じ入力なら同じ順位になる）。**LLM が担うのは、希望の解釈（固定の語彙への変換。隔離抽出）と、選んだ理由の文章化だけ**。

**入力（ハード制約とソフト制約）**

| 入力 | 種類 | 由来 |
|---|---|---|
| 人数（`party_size`） | ハード | Event（出欠の集計） |
| 予算 | ハード | 規程（`policy_snapshot` の上限。`check_budget`）。店の価格帯の**下限が上限を超える店**を外す。上限をまたぐ店は残し、予約時に超過したら 9.1節のフロー |
| 食べられないもの（`dietary_must[]`） | ハード | 参加者。ヒアリングの「食べられないもの（アレルギー・宗教上など）」欄 |
| 全員の所要時間の上限 | ハード | 既定 45分。全員が着ける駅が無ければ緩める（下の「条件の緩和」） |
| 幹事が計画で決めた条件（個室が必須 など） | ハード | Event の計画（`confirm_event_plan`。幹事の確認を経たもの）。**参加者の希望としての「個室」はソフト** |
| 苦手なもの（`dietary_avoid[]`） | ソフト | 参加者。「苦手なもの」欄 |
| 店の希望（`request_tags[]`） | ソフト | 参加者。自由記述は隔離抽出で固定の語彙に落とす |
| 過去の実績 | ソフト | Memory Bank（`load_memory`）。企画・店舗提案の段階だけ（9.8節） |

**固定の語彙**（実装時に確定する。ここでは方針）: `request_tags` は、ジャンル（例: 居酒屋・焼き鳥・海鮮・肉・和食・洋食・中華）と、雰囲気・設備（例: 個室・静か・にぎやか・禁煙・掘りごたつ）。`dietary_must` は、特定原材料8品目（えび・かに・くるみ・小麦・そば・卵・乳・落花生）と、宗教・信条上の除外（例: 豚・牛・アルコール）。**語彙にない値は捨てる**（隔離抽出の出力の検証と同じ。10章）。

**手順**

1. **候補駅の決定**: 全員の最寄り駅から、上限内に着ける駅の共通部分を求める（`search_accessible_stations`）。駅は最適化（全員が着ける駅を全部出し、最遠の所要時間で比べる）
2. **店の検索**: 候補駅ごとに `search_venues`（**Google Maps だけ**。ホットペッパーAPIは不採用）
3. **ハード制約で足切り**: 収容人数、価格帯、食べられないもの（ジャンル・特徴が**明らかに該当する店**を外す）、幹事が決めた条件。外した理由は `stage_result.excluded_reason` に残し、判断ログに要約を残す。**店のデータにアレルゲンの情報が無い限り、対応の保証はしない**。画面と理由に「アレルゲンは店に確認してください」を必ず添える
4. **並べ替え（辞書式）**: (a) 最も遠い人の所要時間を**5分刻みの帯**にして、小さい順 (b) 同じ帯の中で、**希望の一致度**（一致する `request_tags` ごとの「希望した人数」の合計）が大きい順 (c) **記憶による調整**（同じ店の実績で、予算内・満足度・幹事の「また使いたい」があれば加点。「使いたくない」は減点して、同じ帯の中で下げる） (d) 苦手なもの（`dietary_avoid`）に当たる人数が少ない順 (e) 平均所要時間の小さい順 (f) 口コミの評価の高い順。**店は、重みの足し合わせではなく、この優先度で並べる**（なぜこの店かを説明できるようにするため）
5. **提案の選び方**: 上位を最大3件。**総合の上位3件に、希望の一致度が最大の店が入らないとき**は、3件目をその店に置き換え、`role = preference_first` とする（「希望が無視された」に見えないため）
6. **理由**: コードが `reason_facts` を作り、LLM が `selection_reason` に文章化する。**コードは、`selection_reason` に含まれる数値・店名・人数が `reason_facts` と一致することを検査し、外れたら定型の文に差し替える**（LLM が数字を作らない）

**バラバラの希望の扱い**: 希望は固定のタグに落とし、**希望した人数**で集計する（例: 個室3名、焼肉1名）。多い希望から優先する。**反映できなかった希望は、`reason_facts.unmet_preferences` に残し、理由に明記する**（例: 「焼肉の希望1名は、この駅の範囲では条件に合う店が無く、反映できていません」）。

**条件の緩和**（PLAN 5.1 の場面1）: 全員が45分以内に着ける駅が無いとき、上限を緩めて探し直す（初期値は5分ずつ、60分まで。`search_accessible_stations` の `relax_step` / `relax_limit`）。緩めた場合は、**なぜ緩めたか**（何分にしたか、最も遠い方の最寄り駅が遠いため、など。**個人は特定しない**）を `reason_facts.relaxed` に残し、判断ログとカードに出す。60分でも見つからなければ、幹事に条件の見直しを求める。

**選んだ理由に含めるもの（`reason_facts`）**: ①ハード制約を通ったこと（人数・予算・食べられないもの）②帰りやすさ（最も遠い人でも○分。個人は特定しない）③反映した希望と人数、**反映できなかった希望** ④過去の実績（`memory_note`）⑤緩めた条件（あれば）。

**初期値として置く数値**（実装時に調整してよい定数）: 所要時間の上限 45分、帯の幅 5分、緩和の幅 5分・上限 60分、提案の件数 3件。

---

## 10. ガバナンス・セキュリティ

- **AIとコードの役割の境界**（2026-09-26。[PLAN.md](PLAN.md) 7.0、[ARCHITECTURE.md](ARCHITECTURE.md) 2.4）。**AI（LLM）は、お金と個人情報に直接触れない**。この構造そのものを、最大のガバナンスとする。
  - **LLM が見るもの**: 仮名（`User_001`）と区分、隔離抽出後の値（固定の語彙・型検証済み）、集計値、規程の条文の抜粋、記憶の事実（定型・検証済み）、店の公開情報
  - **LLM が見ないもの**: 実名（帳票・Web の再識別レイヤーを除く）、口座番号、銀行のアクセストークン、署名鍵、個人ごとの回答・コメントの原文（自由記述は、隔離抽出が語彙に落としたものだけが渡る）
  - **LLM が決めないもの**: `audit.llm_must_not`（`calculate_amounts`・`choose_approver`・`choose_payee`・`modify_policy`・`sign_mandates`）に加え、**店の順位づけ**（9.9節。理由の文章だけ書く）、Policy Gate の判定、振込依頼の作成、「完了」の判断
  - **マスキングと承認・送金の関係**: 仮名化は、**LLM に見せる範囲を絞る**処理で、システムから個人を消す処理ではない。承認・送金は、コードが本人のID（Slack ユーザーID・仮名ID）で処理し、実名への再識別は帳票・Web の生成レイヤーだけ、口座の解決は銀行アダプタの中だけで行う。LLM が仮名しか見なくても、承認・送金の流れは変わらない
- **多層防御**を、参加者の自由記述に加えて**Google Mapsの口コミ本文にも同じ経路で適用する**（`review_snippet_used: true` の場合は必ず`extract_free_text`（隔離抽出）を通す）
- **RAG Engine の検索結果も外部入力として扱う**。規程の文書に攻撃文が混ざっていても、ツールの応答として Agent Gateway × Model Armor の検査を通り、抽出した値はコードが型と範囲で検証する（9.7節）
- **記憶（Memory Bank）の汚染への対策**（9.8節）。長期記憶は、一度攻撃文が入ると以後のイベントに影響し続けるため、**入口と出口の両方**を絞る:
  1. **書き込みは、コードだけが、定型テンプレートと検証済みの値から作った事実を、幹事の確認のあとに直接書き込む**（Policy Gate 6.4）。会話（セッション）からの自動生成は使わない。自由記述の原文・LLM が書いた文・幹事が編集した文は、記憶にならない
  2. **読み取りは統括エージェントだけ**（`load_memory`。アタッチ）。identity には**読み取り専用のロール**だけを付け、書き込みの API はエージェントのコードに存在しない。読み取りの結果（Memory Bank → エージェント）の区間には Gateway の検査が掛からないので、**入口（書き込み）で中身を保証する**ことが主な対策になる。**それを踏まえたエージェントの応答は、Agent Gateway の入口（`streamQuery` の応答側）で Model Armor が検査する**（多層。応答用のテンプレート）。企画・店舗提案の段階でしか呼べない（コールバック）
  3. **記憶は、金額・按分・承認者・支払先・委任・規程の値に影響しない**（4章冒頭）。仮に汚染されても、お金に関わる決定には届かない
  4. スコープはコードが固定し（Event の `memory_scope`）、期限（TTL）は365日
- **インジェクション対策は、Agent Gateway × Model Armor を土台にした多層防御とする。エージェントの通信は、入力もツールも、すべて Agent Gateway を通す**（直接の Model Armor 呼び出しは使わない）。
  1. **Agent Gateway + Model Armor**: エージェントへの入力（KUROKO API・支払いAPI → エージェント）と、エージェントが呼ぶ MCP ツールの呼び出し・応答（エージェント → API の MCP エンドポイント）を、Gateway が必ず経由させ、Model Armor のテンプレートで検査する。Slack の自由記述も、KUROKO API（後段）が**エージェントに渡す**形にして Gateway の入口を通す。口コミ本文のような、ツールの応答に混ざった攻撃文もここで止める。あわせて、エージェントごとに呼べる MCP エンドポイントとツールを Gateway のポリシーで絞る
  2. **隔離抽出**: 参加者の自由記述と口コミ本文は、**ツールを持たない別のエージェント（`extract-agent`。Agent Runtime）**に渡し、構造化した値（`dislikes / preferences / nearest_station`）だけを返させる。統括エージェントには、自由記述の原文ではなく、この抽出後の値だけを渡す。`extract-agent` も Gateway の入口を通る
  3. **値の検証と、コードによる Policy Gate（6章）**: 駅名・金額・支払先・**規程から抽出した値**などは値として検証し、最後はコードが決める
- **Model Armorでの日本語攻撃文の検知を実装コミットとする**（レビュー04で例示したパターンを、Gateway 経由（エージェントへの入力、MCP ツールの応答）で検知できることを確認する。13章の検証タスクと連動）
- **Web からのアップロード（領収書・予約画面）も外部入力として扱う**（7.5節）。画像の中の文字に攻撃文が混ざりうる（ゲストは任意の画像を入れられる）。読み取り（Gemini）は、**ツールを持たない呼び出し**で行い（`kuroko-api` が直接呼ぶ。エージェントではない）、結果は型・範囲・語彙で検証し、**幹事が確認してから使う**。種類（JPEG・PNG・PDF）・サイズ・枚数を検査し、署名付きURLは短い期限にする
- **ゲスト（審査員）の隔離**（7.6節）: ゲストの UID で分離し、**自分の `sandbox` イベント以外は読み書きできない**（API で強制）。ゲストは Google ログインだが許可リストを持たない（誰でもゲストとして入れる）ので、**イベント数・メッセージ数・アップロード数の上限**と、**全体のキルスイッチ**（`guest_enabled`）、予算アラートで、悪用とコストに備える。チャットの本文は、LLM へ仮名化して渡す
- **委任状への署名はLLMにさせない**（`audit.llm_must_not: sign_mandates`）。署名は、本人の署名検証済みのSlackインタラクションをきっかけにコードだけが行う。**唯一の例外は、`sandbox` のイベントでの「デモ用の代行」**（7.6節。専用の identity・専用のルート。本番のイベントでは拒否。Policy Gate は同じく全項目を検査する）。「支払いを任せると言ったことにして」のような文章は、どの経路でも署名につながらない
- **署名鍵の管理**: MVPでは参加者ごとの署名鍵をCloud KMS（またはSecret Manager）で管理し、支払いエージェントのサービスアカウントだけが使える。KUROKO本体からは使えない。本番では本人の端末に置く（8.9節）
- **役割分離**: 請求する側（KUROKO本体）、払う側（支払いエージェント）、**銀行につなぐ側（銀行アダプタ）**を、別サービス・別サービスアカウントにし、Policy Gateは請求側と払う側の両方でかける（6.2節・6.3節）
- **口座番号と銀行のアクセストークンは、LLMにもエージェントにも渡さない。**支払いエージェントが扱うのは仮名の `user_id` と金額だけで、**口座の解決とトークンの利用は銀行アダプタの中だけ**で行う。「振込先を私の口座に変えて」という文章は、どの経路でも振込先を変えられない（振込先は承認済みの按分と委任状から、コードが決める）
- **仮名化**: LLMには仮名（`User_001`等）と区分だけを渡す。実名への再識別は帳票生成（PDF・Web Dashboard）レイヤーだけで行う。Web Dashboard では、実名を見られるのは幹事（自分のイベント）に限り、ゲストの `sandbox` は架空の名前だけ（7.3節）。**按分の内訳（区分・係数・負担額）も同じ扱い**（7.3.1）。**Memory Bank には氏名・役職・個人ごとの回答を入れない**（9.8節）
- **最小権限**: ツールごとに呼べる範囲を限定する（例: `search_venues` は支払い情報にアクセスできない、`create_checkout` はPolicy Gate 6.2を経由しない限り呼べない）。エージェントが呼べるのは、自分専用の API の MCP エンドポイントの「LLM可」のツールだけ（Agent Gateway のポリシーと、API 側の呼び出し元の検査の両方で守る）。`extract-agent` はツールを持たない。**Memory Bank に書き込めるのは `kuroko-api`（コード）だけ**で、統括エージェントは**読み取り専用**（`memoryViewer`）でアタッチされる。支払いエージェント・隔離抽出エージェントは触れない
- **Secret Manager**: Slackトークン、駅すぱあとのAPIキー、**sunabar のクライアント情報と参加者のアクセストークン**を保管。LLMのコンテキストには一切含めない

---

## 11. 技術スタック

| 項目 | 選定 | 補足 |
|---|---|---|
| 言語 | Python 3.12 | AP2サンプルの要件（3.11以上）を満たす |
| **Web アプリ** | **Next.js（App Router）＋ Firebase Auth（Google のみ。匿名認証は使わない）** | 幹事・審査員の主導線（7.3・7.5・7.6節）。チャット・アップロード・確認・閲覧。Cloud Run（SSR）の前段に Firebase Hosting。デザインは [DESIGN.md](../DESIGN.md) |
| エージェント | Google ADK | KUROKO本体と支払いエージェントの両方 |
| エージェント決済（権限・証跡） | **AP2（Agent Payments Protocol）v0.2** | Python SDK（`ap2.sdk`）と公式サンプル（human-not-present / cards）。Apache License 2.0。委任状はSD-JWT。AP2 自体は権限と証跡の層で、送金は銀行API（sunabar）を通じてKUROKOが実行する（8.2節） |
| 送金 | **GMOあおぞらネット銀行 sunabar**（銀行APIのサンドボックス） | OAuth 2.0 / OpenID Connect、振込依頼API（冪等キー対応）、参照系API（入出金明細）。**資金は仮想**（8.8節）。口座は審査なし・無料 |
| LLM | **Gemini Flash をデフォルト**とする | 多段の判断で精度不足が出た場合のみ、その処理に限定してPro系への切り替えを検討 |
| 規程の参照 | **Vertex AI RAG Engine**（Agent Platform） | コーパスに規程の文書を入れ、`retrieveContexts` で参照する（9.7節）。**文書の版管理はしない**。対応リージョンと日本語PDFの精度は要検証（13章） |
| 記憶 | **Agent Platform の Memory Bank** | 会社・チーム単位の経験の記憶（9.8節）。**書き込みはコードが検証済みの事実を直接書き込む（会話からの自動生成は使わない）。読み取りは統括エージェントにアタッチ（ADK の `load_memory`。読み取り専用）**。TTL 365日。リージョン（`global / us / eu`。東京は記載なし）とスコープの指定は要検証（13章） |
| Slack連携 | Slack Bolt for Python | **HTTPモード（Events API + Interactivity）を推奨** |
| 実行基盤 | **ADKエージェント（KUROKO Agent / 支払いエージェント / 隔離抽出エージェント）は Google Cloud の Agent Platform の Agent Runtime**。それ以外は Cloud Run（Slack Gateway / KUROKO API / 支払いAPI / 銀行アダプタ / Web Dashboard） | Cloud Run は5サービスに分ける（配置・権限は [ARCHITECTURE.md](ARCHITECTURE.md)）。Web Dashboard の前段に Firebase Hosting を置く。Agent Runtime は提出要件の「アプリケーション実行プロダクト」の一覧に載っていないため、Cloud Run も使う |
| ツール接続 | **MCP**。**KUROKO API・支払いAPI が自身で MCP サーバーを兼ね、Cloud Run にデプロイする**（Python の MCP SDK。`/mcp` に載せる） | エージェントのツールは、この MCP エンドポイントが公開する「LLM可」のものだけ。ADK の MCP ツールセットで接続する |
| ネットワーク・ガバナンス | **Agent Gateway**（Agent Platform）+ Agent Registry | エージェントの入出力の関所。Agent identity（エージェントごとの ID）で、呼べる MCP サーバー・ツールを絞る |
| 非同期処理 | Cloud Tasks | 3秒Ack対応、参加者ごとの支払いタスク |
| 定期起動 | Cloud Scheduler | リマインド・期限チェックなど分単位でよいもの |
| 状態管理 | Firestore | |
| ファイル | Cloud Storage | 領収書・予約画面・PDF |
| ログ | BigQuery | 判断ログ、Web Dashboardの読み出し元 |
| シークレット・鍵 | Secret Manager、Cloud KMS | 参加者の署名鍵は支払いエージェントだけが、銀行のアクセストークンは銀行アダプタだけが使える |
| セキュリティ | **Agent Gateway × Model Armor（必須実装）** | エージェントの入力とツールの呼び出し・応答を Gateway で検査する（10章）。必要に応じてSensitive Data Protectionを追加検討 |
| 依存管理 | uv | AP2サンプルと同じ |
| Lint/Format | ruff | |
| テスト | pytest | 按分計算・Policy Gate・委任状の検証は必須 |
| 外部API | 駅すぱあとAPI MCP、Google Maps、**sunabar（銀行API）**（ホットペッパーAPIは不採用。2026-09-27決定） | |

---

## 12. テスト・評価

### 12.1 必須（MVP）

- `calculate_split` のユニットテスト: 合計が按分対象額と一致する、主役0円、係数の大小関係と金額の大小関係が一致する、100円未満の切り捨てと端数の付与先、会社補助対象外者を含むケース（9.3節）
- `determine_approver` のユニットテスト: 係数最大者が一意に決まるケース、同係数で役職ランク・入社日・社員番号まで比較が必要なケース
- Policy Gate（6章）の各項目に対する通過・拒否のテスト
- **委任状の検証のテスト**（6.3節）: 次の請求ではすべて**振込依頼が作られない**こと
  - 上限を1円でも超える請求
  - 幹事以外を支払先にした請求
  - 別のイベントIDの請求
  - 期限切れ・取り消し済みの委任状
  - 使用済みのnonce
  - KUROKOの署名がない、または按分表のハッシュ値が承認時と違う請求
  - 銀行APIの認可がない参加者
- **規程の抽出のテスト**（9.7節）: `extract_policy_values` の結果が `policies/company_rules.yaml` の値と一致すること。値が範囲外・欠損のときに按分へ進まず差し戻すこと
- **記憶の保存のテスト**（6.4節。Memory Bank はスタブで）: 次の場合にすべて**書き込まれない**こと
  - 幹事が確認していない（または確認者が `organizer_user_id` と違う）
  - 事実が定型テンプレート以外（LLM の文、編集した文）
  - 事実に、自由記述の原文・氏名・Slack ユーザーID・役職・個人ごとの回答が含まれる
  - スコープが Event の `memory_scope` と違う
  - 回答が3件未満なのに、良かった点・気になった点の事実がある
  - 実績の事実（`venue_record`）が、イベントのデータ以外（幹事・参加者の入力）から作られている
  - 幹事が `reuse_intent` に答えていないのに、「幹事は次回も…」の文がある
  - すでに保存済み（二重の書き込み）
- **店舗の選定ロジックのテスト**（9.9節。LLM を呼ばず、決定論的に）: ハード制約で外れる（人数超過・価格帯の下限が上限超過・食べられないものに明らかに該当・幹事が決めた必須条件）／帯が違えば、希望の一致度より帰りやすさが優先される／同じ帯では、希望した人数が多い店が上になる／総合の上位3件に希望が最大の店が無いとき、3件目が `preference_first` に置き換わる／全員が着ける駅が無いとき、緩和の幅と理由が `reason_facts.relaxed` に残る／**反映できなかった希望が `unmet_preferences` に入る**／記憶による調整が、同じ帯の中の順位だけを動かし、金額・所要時間の数値を変えない／`selection_reason` に `reason_facts` にない数値・店名があれば、定型の文に差し替わる／**同じ入力なら同じ順位になる**
- **記憶が金額に影響しないことのテスト**（4章冒頭）: 同じ Event で、`load_memory` の結果を変えても、`calculate_split`・`determine_approver`・`create_checkout` の出力が変わらないこと。**統括エージェントのツールに書き込み系の記憶ツールが含まれず、コードに `add_session_to_memory` などの書き込み API の参照がない**こと。**`load_memory` が企画・店舗提案の段階以外では実行されない**こと（コールバック）
- **振り返りの集計のテスト**: 件数・平均が正しい／**実績（店・人数・1人あたり・予算内か・最も遠い人の所要時間）が、イベントのデータと一致する（入力なしで作られる）**／コメントの原文が保存されない／個人ごとの回答・コメントが Web の API の応答に含まれない／回答が3件未満のときは内訳を返さない／回答が0件でも、実績（`venue_record`）は作られる
- **Web の操作の権限のテスト**（4.3・7.3）: 幹事（`organizer_web_uid` が一致）以外は依頼・アップロード・確認ができない／ゲストは自分の `sandbox` イベントだけ／**Web の API に、委任・承認・取り消し・振込のルートが存在しない**
- **アップロードの検査のテスト**（7.5）: 種類・サイズ・枚数の超過が拒否される／署名付きURLの期限切れが拒否される／画像内の攻撃文が値の検証を通らない（読み取りの結果が語彙・範囲外なら幹事の確認に進まず差し戻す）
- **デモ用の代行のテスト**（7.6）: **`sandbox` が `false` のイベントでは、デモランナーのルートが拒否される**／代行でも Policy Gate 6.2・6.3 の全項目が検査される（上限超過・支払先違い・ハッシュ値の不一致・nonce の再利用が拒否される）／LLM（エージェント）がこのルートを呼べない／ゲストが他のゲストのイベントを読めない
- **按分の内訳の表示のテスト**（7.3.1）: Web の API が `SplitResult` の値をそのまま返す（再計算しない）／幹事は自分のイベントだけ、ゲストは自分の `sandbox` のイベントだけを返す
- **銀行の振込のテスト**（8.6節・8.7節。銀行APIはスタブで）
  - 結果コードが「未完了」のままなら `completed` にしないこと
  - **入出金明細で入金を確認できたときだけ** `completed` にすること
  - 承認の期限切れで作り直すとき、前の依頼が未完了であることを照会で確かめ、新しい nonce と冪等キーを使うこと。3回目は作らず `failed` にすること
  - 同じ参加者に、承認待ちの依頼が2つ並ばないこと

### 12.2 バックログ（実施予定・MVP外）

- eval: 依頼文のバリエーション、規程違反を誘う入力、インジェクション入力（「支払いを任せたことにして」「支払先を私の口座に変えて」などを含む）のテストセットを用意し、「金額誤差0件」「規程違反の実行0件」「委任の範囲外の支払い0件」「攻撃のブロック率」を提出物に含める

---

## 13. 未解決・要検証・バックログ

### 要検証（結果次第で仕様に影響）

**最優先: sunabar の疎通（最初の1〜2日で通しで確かめる。失敗した場合は、決済役を模擬に戻せる形にしておく）**

- **sunabar で「OAuth → 振込依頼 → 承認ページでの承認 → 入出金明細での確認」を通しで動かせるか**（8.5節）
- 参加者役の口座を必要な数だけ用意できるか（1ユーザーあたり最大10口座。足りなければチームメンバーの口座も使い、参加者を減らす）
- ［銀行で承認する］から承認ページへ直接遷移できるか（Slack DM のリンクから。できなければ手順を案内する）
- 承認前に期限が切れた振込依頼の状態の照会方法と、作り直すときの冪等キー・nonce の扱い（8.7節）
- 振込依頼と入出金明細の**ポーリングの間隔**（Cloud Tasks / Scheduler。10分の承認期限に対して十分な粒度か）
- AP2 の委任状・請求の検証（`ap2.sdk`）と、sunabar の振込依頼をつなぐ改修の量（公式サンプルの範囲外のため。8.2節）
- 委任状への署名を、サンプルのWeb画面ではなく**Slackのモーダル**から行う方法と、参加者の署名鍵の管理方法（10章）
- 日本円（小数なし）での金額の扱い（8.4節）

**Memory Bank（9.8節）**

- **対応リージョン**（公式ドキュメントでは `global / us / eu`。東京の記載はない）。どこに置くか、Agent Runtime・RAG Engine とのリージョンの組み合わせ（[ARCHITECTURE.md](ARCHITECTURE.md) 13章 V3・V12）
- **会社・チーム単位のスコープ**（`{company_id, team_id}` のようなキーで分離できるか。ドキュメントの例は `user_id`。だめなら `user_id` の名前空間として使う）
- **直接書き込みと検索のAPI**（`memories.create` 相当。会話からの自動生成を使わずに書けるか、`retrieve` の類似検索の使い方）と、ドキュメント間で名前が違う点（SDK のバージョン）
- **日本語の検索の品質**と、**既存の記憶との統合（consolidation）**が、事実の文面を勝手に書き換えないか
- **権限の分離**: `sa-api` には書き込み（`roles/aiplatform.memoryEditor`）だけ、`agent-kuroko` には読み取り専用（`roles/aiplatform.memoryViewer`）だけを付けて、それぞれ意図どおりに動くこと（`agent-kuroko` から書き込めないこと）。`agent-payment`・`agent-extract` が触れないこと
- **Memory Bank への入出力が Agent Gateway・Model Armor の検査対象になるか**（**確認済みの範囲**: ADK エージェントの `streamQuery` の要求と応答は、Gateway の入口で Model Armor が検査する。**`query` / `streamQuery` 以外のメソッド（`asyncQuery` など）は Gateway の対象外**なので、エージェントの呼び出しに**使わない**。**要検証**: 応答側で効くフィルタの範囲（有害内容・機微情報・悪意のあるURLは効く見込み。プロンプトインジェクション・ジェイルブレイクの検知が応答にも効くかは未確認）、Gateway を通さない直接の呼び出しを IAM で禁止できるか）
- **アタッチの仕方**: ADK の `VertexAiMemoryBankService` を Agent Runtime にデプロイしたエージェントで既定で使うのか、明示的な指定（`memory_service_uri` など）が要るのか（ドキュメントの記述が食い違っている）。**`agent-kuroko` の identity に `roles/aiplatform.memoryViewer` だけで `load_memory` が動くか**、IAM Conditions でスコープを絞れるか
- **`kuroko-api` が直接書いた記憶を、ADK の検索（`app_name` と `user_id` のスコープ）が引けるか**（スコープの指定が食い違うと、書いた記憶が見つからない）。ADK の `app_name` の扱い
- 構造化された「プロファイル」（チームの傾向: 予算・重視する点）を使うか（任意）

**RAG Engine（9.7節）**

- **RAG Engine の対応リージョン**。東京リージョン（`asia-northeast1`）に未対応の可能性があり、その場合は別リージョンに置くことになる（Agent Runtime・Agent Gateway とのリージョンの組み合わせに影響する。[ARCHITECTURE.md](ARCHITECTURE.md) 13章 V3）
- 日本語のPDF（表・段組）の抽出精度。`company_rules.yaml` を正解データにして測る（12章）
- 規程のコーパスへの取り込み手順（Cloud Storage からのインポート）と、更新したときの反映
- RAG の検索結果が Agent Gateway × Model Armor の検査対象になるか（MCP のツールの応答として通るか）

**振り返りのSlackモーダル**

- 満足度の1タップ（ボタン5つ）と、任意のコメント欄（200字）を、Slack のメッセージ・モーダルで無理なく出せるか。**良かった点・気になった点のチェックボックスは廃止した**（2026-09-26。7.4節）ので、選択肢の数の制約は無くなった
- フローの途中の確認（例: 按分確定後に、負担額が最大の人へ確認する）を、**ADK のコールバックとセッションの state で行い**、Slackのボタン押下のあとに同じセッションで新しいターンを呼んで再開する方法。承認・確認の権威は、これまでどおり Cloud Run 側のコード（Policy Gate 6.2）と Firestore の記録で、エージェントは導線だけを担う。ADK の `require_confirmation`（ツール確認）は、Agent Runtime のセッションに非対応・実験的・確認応答が偽造できる問題があるため使わない。詳細と検証は [ARCHITECTURE.md](ARCHITECTURE.md) 4.9節・13章 V9
- Agent Runtime に依存する点（Cloud Run の非公開APIの呼び出し、エージェントごとの実行SA、リージョン、レイテンシ、費用）は [ARCHITECTURE.md](ARCHITECTURE.md) 13章
- Model Armorでの日本語攻撃文の検知（10章で実装コミット済みだが、実際に検知できるかは検証が必要）。**Gateway 経由（入力の `streamQuery`、MCP の `tools/call`）**で確かめる。公式ドキュメントでは、ストリーミングの呼び出しの一部は検査を通らないとされているため、`stream_query` の入力が実際に検査されるかを含める
- Agent Gateway が Gemini（Vertex AI）への呼び出し自体を検査するかは、公式ドキュメントで確認できていない（検査対象として明記されているのは、エージェントへの `streamQuery`、MCP の `tools/call` などの呼び出し）。検査されない場合、Gemini への入力は「エージェントの入口」と「ツールの応答」の検査で守る
- KUROKO API・支払いAPI が MCP サーバーを兼ねるときの、Agent Gateway 経由の呼び出しと認証（Cloud Run の非公開のまま、エージェントの identity だけを許可できるか。[ARCHITECTURE.md](ARCHITECTURE.md) 13章 V1・V7）
- Agent Gateway・Agent Registry の利用条件（プレビューかどうか、組織の権限、リージョン）。使えない場合の代替は [ARCHITECTURE.md](ARCHITECTURE.md) 13章 V6
- 隔離抽出を「ツールを持たない別のエージェント」にすることの、レイテンシと費用（デプロイ対象が1つ増える）。重ければ、自由記述を統括エージェントに直接渡す形（隔離抽出をやめる）に簡略化する
- **Web の認証**: ゲストが**許可リストなしの Google ログイン**（誰でもゲストとして入れる。**匿名認証は使わない。2026-09-27決定**）で運用して問題にならないか。ゲストの悪用（大量のイベント作成・アップロード）への上限とキルスイッチの動作（7.6節、10章）
- **Web のチャットの進み具合の見せ方**（Firebase Hosting → Cloud Run の rewrite にはリクエストの時間の上限がある。長い処理を、受け付け即時応答＋タイムライン更新にできるか。[ARCHITECTURE.md](ARCHITECTURE.md) V13）
- **デモ用の代行（デモランナー）**: 署名検証済みの Slack 操作の代わりに `sa-demo-runner` の操作を受ける専用ルートを、`sandbox` のイベントだけに限定して安全に実装できるか（7.6節、10章）。sunabar の承認ページ（銀行での承認）を、デモランナーが代行できるか（V10 ③。できなければ、銀行での承認だけは人が行う）
- ~~ホットペッパーAPIの申請・利用規約がハッカソン用途に適合するか~~ → **2026-09-27 決定: 利用しない**（規約適合の確認が取れないため断念。`search_venues` は Google Maps だけで進め、個室・収容人数の補完はあきらめる。H14）

### 要準備

- **審査員向けの体験の準備**（7.6節）: **サンプルの予約画面・領収書**（画面からダウンロードできる。架空の店・金額はストーリーと合わせる）、**サンドボックスの会社「株式会社Akakura」の初期データ**（架空の規程・デモ参加者・過去の記憶の seed）、**デモ用の Slack ワークスペースの招待リンク**（(B) の体験用。提出物に記載）、審査員向けの**使い方の説明**（画面の案内と提出物）

- **GMOあおぞらネット銀行の個人口座の開設と sunabar の準備**（審査なし・無料。最短当日だが、平日14時までの申し込みなどの条件がある。**リードタイムがあるので最初に出す**）
- **参加者役・幹事役の sunabar 口座の用意**（チームで分担。8.8節）
- **規程の文書（架空のPDF）の作成と、RAG Engine のコーパスへの取り込み**（`company_rules.yaml` と同じ内容にして、正解データとして使えるようにする）
- **Memory Bank の作成**（Agent Platform。リージョンは V12 で決める）と、**過去のイベントの記憶の投入（seed。架空。3件程度）**。デモの企画の場面で `load_memory` が引けるようにする（9.8節）。文面は定型テンプレートと同じ形にする
- デモ用Slackワークスペースと参加者役アカウント（架空アカウント約6＋bot併用で10名分を賄う）
- 駅すぱあとAPIのアクセスキー申請
- Vertex AI（Gemini・RAG Engine）の設定

### 2026-09-20 の支払い方式の再変更で復活・不要になったもの

**復活したもの**（2026-09-17 に「不要」としていた項目）

- GMOあおぞらネット銀行の口座開設と sunabar の準備
- sunabar で1人が持てる口座数の検証
- ［銀行で承認する］から承認ページへ直接遷移できるかの検証
- 承認期限切れの自動再依頼（8.7節。**バックログではなく作る**）

**不要になったもの**

- AP2サンプルの模擬決済役（Credentials Provider / Payment Processor）を Cloud Run で動かすこと
- 支払い用トークン（`issue_payment_credential`）と、決済役の署名付き領収書の検証
- `ap2-mock` を1サービスにするか2サービスにするかの判断

### 対応しない・後回しにする事項

- 提出後〜12月1日までの運用継続（Cloud Runの費用、Slackトークン・**sunabar のアクセストークン**の有効期限管理）は今回は気にしない。ただし sunabar のトークンは30日で失効するため、ポータルへのログインだけは続ける（8.8節）
- Web Dashboardの本格的な認証方式は本番化の論点として説明文に書くに留める
- **Web Dashboard から、委任・承認・取り消し・振込の実行を行う機能は作らない**（Slack のみ。7.3節）
- 実際のお金の移動（8.9節）
- 規程の文書の版管理・取り込み画面・管理者の役割（9.7節）

### 決定済み（2026-09-26。ユーザー決定。役割の統合）

- **審査員と開発者を区別しない。Web の役割は「幹事」と「ゲスト」の2つ**（7.3・7.6節）。開発者の役割（全イベント・仮名のみ・書き込み不可）は廃止する
- **ゲストが見られるのは、サンドボックス（自分の `sandbox` イベント）だけ**。幹事の画面と同じ画面で、幹事として操作できる。名前は架空。**参加者向けの Web 画面は作らない**（参加者は Slack のまま）
- ~~認証は、ログイン不要（匿名）を残す。将来は Google 認証だけにする（バックログ）~~ → **2026-09-27 決定: Google ログインに統一する（匿名認証は使わない）。許可リストに載っていない Google アカウントはゲスト**（H2・H10）

### 決定済み（2026-09-26。ユーザー決定。レビュー06への対応）

- **店舗の選び方は「段階式」**（9.9節）。ハード制約で足切り → 最遠の所要時間 → ソフト制約と実績で微調整。重み付きスコアにはしない（理由を説明できるようにするため）
- **振り返りは「実績ナレッジ化」**（9.8節・7.4節）。実績は自動記録、参加者は満足度の1タップ＋**自由に書けるコメント欄（任意）**、幹事は「次回もこの店を使いたいか」の1問
- **支払いエージェントは現構成を維持し、AIとコードの境界を明記する**（10章、8.5節の注記、[PLAN.md](PLAN.md) 7.0）。3つのエージェントのまま。LLM が担うのは、通知文・説明文・次に呼ぶツールの選択（手順は固定）まで。**手順・金額・可否・署名・口座はコード**

### 決定済み（2026-09-20。ユーザー決定）

- **按分の内訳を Web に出す**（7.3.1）。幹事は区分・係数から個人の役職を推測できるが、承知の上で表示する。範囲は、幹事は自分のイベントだけ・ゲストは自分の `sandbox` のイベントだけ
- **振り返り・記憶を作る**（9.8節）。**Agent Platform の Memory Bank** を使う
- **Web Dashboard を幹事の主導線にし、事務の確認（予約内容・領収書の金額・店舗候補・予算超過）を Web でも行う**（7.3節）。あわせて、振り返りのまとめの確認も Web で行う
- 支払い方式の再変更（8章）。「本人の操作なしにエージェントが支払う」は失われるが、代わりに**実在の銀行APIで振込依頼から入金確認まで KUROKO が実行する**（資金は仮想）。審査基準③（主要機能がモックでないこと）への説明はこちらのほうが強い。デモには、銀行の承認ページへの切り替えが1回入る

### 決定済み（2026-09-27。ユーザー決定。human_task.md H2）

- **7.6節「審査員が体験できる導線」①**: **ログイン不要の匿名認証ではなく、審査員は Google ログインでログインする**（**匿名認証は使わない**。H10と整合）。役割の決め方は変えない: 幹事の許可リスト（`dashboard_users`）に載っている Google アカウントは `organizer`、載っていないアカウントは `guest`（審査員・開発者を区別しない）。②デモ用の代行を使うか、③(A) Web専用か (B) Slack参加も用意するかは、引き続き下記の「要レビュー」のまま
- **9.3節「会社補助対象外者の按分ルール」**: 厳密な公平性は追求せず、**とりあえず決め打ちのルールでよい**（実装時にAIが具体案を決めてよく、後で見直し可）
- `company_rules.yaml` に追加した委任状の有効期限（開催日＋7日）: 確認済み。`payer_mandate.expires_after_event_days: 7` として既に実装済み
- **9.8節「Memory Bank を統括エージェントにアタッチして読み取る（`load_memory`。読み取り専用のロール。企画・店舗提案の段階だけ）。書き込みは `kuroko-api` のコードだけ」**: **提案どおり確定**
- **9.8節「記憶の書き込みは、幹事が Web で確認した定型の事実だけ。会話からの自動生成は使わない」**: **現状案でOK**。加えて、**バックログとして、ユーザーによる自由記述の記憶書き込みも将来許す**方針にする（TASKS.md B28）
- **3章 Retrospective「回答が3件未満のときは、良かった点・気になった点の内訳を出さない」**: **今回は全員が回答することを想定してよい**（3件未満のケースはデモでは発生しない前提。ルールそのものは保険として残す。実績の事実（`venue_record`）は、回答数に関係なく覚えられる）
- **9.8節「デモでは、過去の記憶を事前に投入（seed）して見せる」**: **Yes**（H27で内容を決めて進める）

### 要レビュー（チームで確認してほしい決定）

- **7.6節「審査員が体験できる導線」②③**（ログイン方式は上記のとおり決定済み）: ②**デモ用の代行**（`sandbox` のイベントだけ、Slack の署名検証済み操作の代わりにデモランナーが参加者・承認者の HITL を代行する）を入れてよいか。**「署名検証済みの Slack 操作だけが委任に署名できる」原則の唯一の例外**になる。入れない場合は、審査員が Slack ワークスペースに参加して全員分の HITL を行う必要があり、一人では完走できない ③(A) Web のみ（既定）と (B) Slack に参加（任意）の両方を用意するか

- **9.8節・7.4節「振り返りを『自動の実績＋最小のフィードバック』に見直し」（2026-09-26。レビュー06への対応。ユーザー決定）**: 参加者への質問は満足度の1タップ＋任意のコメントだけ。**コメントの原文は保存せず、個人ごとのコメントは幹事にも見せない**（既存の方針を維持）。幹事にコメントを（匿名・3件以上のときだけ）見せるかは、未決
- **9.9節「店舗の選定ロジック」の初期値**: 所要時間の上限 45分、帯の幅 5分、緩和の幅 5分・上限 60分、提案3件、固定の語彙（ジャンル・雰囲気・食べられないもの）。実装時に、デモの条件に合わせて調整する

---

## 14. 参考資料

- [PLAN.md](PLAN.md) — 概要（課題・コンセプト・スコープ・競合との差分）
- [DESIGN.md](../DESIGN.md) — Web Dashboard のビジュアルデザインとコンポーネント規約（参考: [Refero Styles](https://styles.refero.design/)）
- [review/2026-09-13_KUROKO_review.md](review/2026-09-13_KUROKO_review.md) — 初回レビュー、審査基準ごとの見立て
- [review/2026-09-13_KUROKO_review_02_scenario.md](review/2026-09-13_KUROKO_review_02_scenario.md) — シナリオ、帰りやすさ・按分の設計、インジェクション対策、AP2の最初の検討
- [review/2026-09-13_KUROKO_review_03_payment.md](review/2026-09-13_KUROKO_review_03_payment.md) — 支払い方式の比較（銀行振込案）。**2026-09-20 の再変更で、案B-1 の内容が再び有効になった。**sunabar の調査（4章）、Policy Gate の項目（7章）、自律的な判断の一覧（9章）は本書8章の土台
- [review/2026-09-13_KUROKO_review_04_story.md](review/2026-09-13_KUROKO_review_04_story.md) — 確定ストーリー、3分デモ構成（支払いの場面は本書8章で置き換え）
- [policies/company_rules.yaml](../policies/company_rules.yaml) — 会社規程データ（**抽出結果を検証する正解データ**とフォールバック。9.7節）
- [docs/mock/kuroko_story_mock.html](mock/kuroko_story_mock.html) — 画面モック（支払いの場面は銀行振込版で、方式としては再び整合する。委任状と Web Dashboard の部分は要更新）
- AP2: [Agent Payments Protocol Documentation](https://ap2-protocol.org/)、[google-agentic-commerce/AP2（GitHub）](https://github.com/google-agentic-commerce/AP2)、[human-not-present / cards サンプル](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-not-present/cards)
- 銀行API（sunabar）: [sunabar はじめてガイド](https://gmo-aozora.com/sunabar/tutorial/01.html)、[銀行APIが体験できるsunabar](https://gmo-aozora.com/priv/contents/first-sunabar.html)、[API開発者ポータル](https://api.gmo-aozora.com/ganb/developer/api-docs/)、[振込依頼APIの結果コードが2（未完了）で返ってきます](https://help.gmo-aozora.com/faqs/6686541eefe214ffd6342ceb/)
- 規制（本番化の論点。8.9節）: [電子決済等代行業を営むみなさまへ（金融庁）](https://www.fsa.go.jp/common/shinsei/dendai/index.html)、[電子決済等代行業に該当しない行為について（三宅法律事務所）](https://www.miyake.gr.jp/notice/%E3%80%90%E3%82%AA%E3%83%BC%E3%83%97%E3%83%B3api%E3%80%91%E9%9B%BB%E5%AD%90%E6%B1%BA%E6%B8%88%E7%AD%89%E4%BB%A3%E8%A1%8C%E6%A5%AD%E3%81%AB%E8%A9%B2%E5%BD%93%E3%81%97%E3%81%AA%E3%81%84%E8%A1%8C/)
- RAG Engine（9.7節）: [RAG quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-quickstart)、[RAG Engine API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/rag-api)
- Memory Bank（9.8節）: [Agent Platform Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)、[Set up Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)、[Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)、[Memory Profiles](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/profiles)
