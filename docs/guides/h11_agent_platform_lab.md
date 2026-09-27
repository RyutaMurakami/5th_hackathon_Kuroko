# H11 手順書: Agent Runtime・Agent Gateway・Agent Registry・Model Armor の最小構成を自分の手で構築する

> エージェントへ: 本書は [human_task.md](../human_task.md) H11 をユーザーが自分の手で進めるための手順書（ゲート G2。[TASKS.md](../TASKS.md) O2）。**Console で出来る操作はユーザーが行う**（2026-09-27 ユーザー指定）。AI は準備物（コード・IAM・検証スクリプト）を用意し、各ステップの「AI」印の作業だけを行う。手順が公式ドキュメントと食い違ったら、先に本書を直す。結果は [ARCHITECTURE.md](../ARCHITECTURE.md) 13章（V1〜V9）に書き戻す。

- 作成日: 2026-09-27
- 対象プロジェクト: `kuroko-509311`（プロジェクト番号 `1054683553459`、組織なし）／リージョン: `us-central1`（H12）
- 所要時間の目安: 半日（デプロイの待ち時間を含む）
- 課金: Agent Gateway・Model Armor・Agent Runtime（`min-instances` ぶん）が課金対象。**実験が終わったら 8章の後片付けを必ず行う**

## 0. この実験で確かめること

| ID | 確かめること | どこで分かるか |
|---|---|---|
| V1 | エージェントが Agent Gateway の出口を通って、Cloud Run の `/mcp` を呼べるか。`/mcp` 側で呼び出し元のエージェントを見分けられるか | 7章 手順7-2 |
| V2 | エージェント2つが別々の Agent identity で動き、別々の権限を持てるか | 手順5-3・7-2 |
| V3 | `us-central1` で全部品が作れるか | 各手順の成否 |
| V4 | Gateway・Model Armor を挟んだときのレイテンシ | 手順7-4 |
| V7 | MCP サーバーを載せた Cloud Run が動き、Gateway がツール名で絞れるか | 手順7-2・7-3 |
| V8 | Model Armor が日本語の攻撃文を入口・出口で検知するか | 手順7-5 |
| V9 | ADK のコールバックで「確認待ち」に止めて、同じセッションで再開できるか | 手順7-6 |

## 1. 全体像

```
[検証スクリプト(手元)] --stream_query--> [入口 Gateway: kuroko-agw-c2a] --(Model Armor)--> [Agent Runtime]
                                                                                 ├─ lab-agent-tools   (ツールあり。agent-kuroko の代わり)
                                                                                 └─ lab-agent-notools (ツールなし。agent-extract の代わり)
[lab-agent-tools] --MCP tools/call--> [出口 Gateway: kuroko-agw-a2a] --(Model Armor・IAP 認可)--> [Cloud Run: kuroko-mcp-lab /mcp]
                                                 └ Agent Registry に登録されたものにだけ到達できる
```

- **入口と出口は別の Gateway**（公式の構成。1つのプロジェクト・リージョンに、入口1つ・出口1つ）
- **既定は拒否**。出口は、Agent Registry に登録され、かつ `roles/iap.egressor` を付けた先にしか通さない
- 実験用の部品は、本番と名前を分ける（`lab-` / `-lab`）。**Gateway は本番（H32）でも使い回す**ので、名前は本番用にしておく（`kuroko-agw-c2a` / `kuroko-agw-a2a`）

## 2. 誰が何をするか

| 印 | 意味 |
|---|---|
| 🖱 **あなた（Console）** | Google Cloud Console の画面で操作する |
| ⌨ **あなた（コマンド）** | **Console が対応していない**操作。AI が用意したコマンド・スクリプトを、手元のターミナルで自分で実行する（AI に任せてもよい。その場合はそう伝える） |
| 🤖 **AI** | IAM の付与、コードの用意、検証スクリプトの実行など（2026-09-27 の決定で、IAM は AI の担当） |

> **調べて分かったこと（2026-09-27、公式ドキュメント）**
> - **Console でできる**: Model Armor のテンプレート作成、Agent Gateway の作成（入口・出口とも）、Agent Registry への MCP サーバーの登録、デプロイ済みエージェントの確認（Identity の列）、IAM の画面での権限付与
> - **Console でできない**: **ADK のエージェントを Agent Runtime にデプロイすること**（SDK・`agents-cli`・Terraform・REST だけ。Gateway への接続設定 `agent_gateway_config` も同じ）、Agent Registry のエントリへの `roles/iap.egressor` の付与（`gcloud iap web ...`）
> - **Agent identity はサービスアカウントではない**。デプロイ時にエージェントごとに自動で発行される `principal://agents.global.proj-1054683553459.system.id.goog/resources/aiplatform/projects/1054683553459/locations/us-central1/reasoningEngines/<ENGINE_ID>` という ID で、**エンジンIDが決まるまで（=デプロイ後まで）権限を付けられない**。そのため IAM は手順6（デプロイ後）で行う

## 3. 事前準備

### 3-1. ⌨ あなた: gcloud を最新にする

手元の `gcloud`（core 2026.01.23）には、`network-services agent-gateways` と `agent-registry` のコマンドがまだ無い。

```bash
gcloud components update
gcloud components install beta alpha   # 未導入なら
gcloud network-services agent-gateways --help   # エラーにならなければ OK
gcloud agent-registry --help
```

### 3-2. 🤖 AI: 準備物を用意する（**未作成。H11 に着手する前に AI が作る**）

| 準備物 | 置き場所 | 中身 |
|---|---|---|
| 不足している API の有効化 | `infra/terraform/apis.tf` | `compute` `networksecurity` `iap` `serviceextensions` `telemetry` `observability` を追加（公式の前提 API。P1 の承認を得て apply） |
| 実験用 MCP サーバー | `sandbox/agw_lab/mcp_server/` | FastAPI ＋ MCP SDK（Streamable HTTP）を `/mcp` に載せたもの。ツールは `get_event_summary`（読み取り）と `echo_review`（口コミ本文を返すだけ。V8 の出口検査用）の2つ。**呼び出し元の identity をログに出す**（V1） |
| 実験用 Cloud Run | `kuroko-mcp-lab`（非公開・`us-central1`） | 上の MCP サーバーを AI がデプロイし、URL をあなたに渡す |
| `toolspec.json` | `sandbox/agw_lab/mcp_server/toolspec.json` | Agent Registry に貼る、ツールの一覧（手順4で使う） |
| 実験用エージェント2つ | `sandbox/agw_lab/agent_tools/`・`agent_notools/` | ツールあり（MCP ツールセット＋`before_tool_callback`。V9）／ツールなし |
| デプロイスクリプト | `sandbox/agw_lab/deploy.py` | 手順5で**あなたが実行する**。`identity_type=AGENT_IDENTITY`、`agent_gateway_config`（入口・出口）、`min_instances=0` を指定 |
| 検証スクリプト | `sandbox/agw_lab/verify.py` | 手順7で AI が実行する（V1・V2・V4・V7・V8・V9） |

> `sandbox/` は git の管理外（実験用）。本実装（`kuroko_agent/` など）には、結果を見てから移す。

### 3-3. 🖱 あなた: 権限の確認

あなたはプロジェクトの Owner なので、追加の権限は要らない（H9）。

---

## 4. 🖱 Console で作る（あなた）

**順番が大事**: Model Armor のテンプレート → Agent Registry への登録 → Gateway の順（Gateway の作成画面で、テンプレートと Registry を選ぶため）。

### 手順4-1. Model Armor のテンプレートを2つ作る

入口・出口の「要求」用と「応答」用で分ける（ARCHITECTURE 4.8。応答用には機微情報・悪意のある URL を効かせる）。

1. Console で **Model Armor** のページを開く（上の検索窓に「Model Armor」）
2. **Create Template** を押す
3. 1つ目（要求用）を、次の値で作る

   | 項目 | 値 |
   |---|---|
   | Template ID | `kuroko-ma-request` |
   | Location type | Region → `us-central1`（**Gateway と同じリージョン**が必須） |
   | Select modality | テキスト |
   | Malicious URL detection | オン |
   | Prompt injection and jailbreak detection | オン。confidence は **Low and above**（実験では取りこぼしを見たいので低めにする。本番は P9 で決める） |
   | Sensitive Data Protection | Basic |
   | Responsible AI | 各フィルタ **Medium and above** |
   | Multi-language support | **オン**（日本語の検知のため） |
   | Configure logging | オン（検知の記録を Cloud Logging に出す） |
   | Enforcement mode | **INSPECT_ONLY**（検査のみ。ブロックへの切り替えは P9 の判断後） |

4. 2つ目（応答用）: Template ID `kuroko-ma-response`。Prompt injection はオンのまま、Sensitive Data Protection・Malicious URL・Responsible AI を必ずオン。ほかは1つ目と同じ
5. 一覧に2つ並んだことを確認する

**学びのポイント**: テンプレートは「どのフィルタを・どの強さで・検査のみか止めるか」の設定の束。Gateway はこれを参照するだけなので、あとで強さを変えても Gateway を作り直す必要はない。

### 手順4-2. Agent Registry に MCP サーバーを登録する

前提: 🤖 AI が `kuroko-mcp-lab` をデプロイし、URL（`https://kuroko-mcp-lab-xxxxx-uc.a.run.app`）と `toolspec.json` を渡していること。

1. Console で **Agent Registry** を開き、**MCP servers** タブを選ぶ
2. **Add MCP server** を押す
3. **MCP server details**:

   | 項目 | 値 |
   |---|---|
   | Display name | `kuroko-mcp-lab` |
   | Description | `H11 実験用の MCP サーバー（kuroko-api の /mcp の代わり）` |
   | Region | `us-central1` |

4. **Tool specification**: エンドポイント URL に `https://<Cloud Run の URL>/mcp`、本文に `toolspec.json` の中身を貼る
   - 「URL からツールを取り込む」機能は、**公開されている MCP サーバーにしか使えない**。`kuroko-mcp-lab` は非公開なので、必ず `toolspec.json` を貼る
5. **Next** → **Select MCP tools** で2つのツールを選び、**Save**
6. 一覧に表示されたら、詳細画面で **リソース名（`.../mcpServers/...` などの ID）をメモして AI に伝える**（手順6の IAP の付与で使う。秘密ではない）

**学びのポイント**: Agent Registry は「エージェントが話しかけてよい相手の名簿」。出口の Gateway は、ここに載っていない宛先への通信を通さない。

### 手順4-3. 入口の Gateway（Client-to-Agent）を作る

1. Console で **Agent Platform** → **Gateways**（Agent Gateway のページ）を開く
2. **Add gateway** を押す
3. 次の値で作る

   | 項目 | 値 |
   |---|---|
   | Name | `kuroko-agw-c2a` |
   | Region | `us-central1` |
   | Deployment mode | **Google-managed**（既定のまま） |
   | Agent registry | 既定のまま（入口では使わない） |
   | Governed Access Path | **Client-to-Agent (ingress)** |
   | AI Security → Enable Model Armor | オン。要求のテンプレートに `kuroko-ma-request` |
   | Use same template for requests and responses | **外す**。応答のテンプレートに `kuroko-ma-response` |

4. **Add Gateway** を押す。作成には数分かかる

**学びのポイント**: 入口の Gateway は、`kuroko-api` からエージェントへの `query` / `streamQuery` を検査する。**それ以外のメソッド（`asyncQuery` など）は検査されない**ので、本実装でも `streamQuery` だけを使う。

### 手順4-4. 出口の Gateway（Agent-to-Anywhere）を作る

1. 同じページで **Add gateway**
2. 次の値で作る

   | 項目 | 値 |
   |---|---|
   | Name | `kuroko-agw-a2a` |
   | Region | `us-central1` |
   | Deployment mode | Google-managed |
   | Agent registries | `us-central1` のレジストリ（手順4-2で登録した先）を選ぶ |
   | Governed Access Path | **Agent-to-Anywhere (Agent Egress)** |
   | Access Authorization | **Audit-only**（まず「通したら何が起きるか」を記録で見る。手順7-3で **Enforce policies** に切り替えて比べる）。Policy model は **Unified Access Policy** |
   | AI Security → Enable Model Armor | オン。要求 `kuroko-ma-request`、応答 `kuroko-ma-response`（口コミ本文に混ざった攻撃文は**応答側**で検査される） |

3. **Add Gateway** を押す
4. 2つの Gateway が **Active** になったら、名前（`projects/kuroko-509311/locations/us-central1/agentGateways/...`）を AI に伝える

**学びのポイント**: 出口の Gateway は「既定は拒否」。通すには ①Registry に載っていること ②エージェントの identity に `roles/iap.egressor` があること、の両方が要る。Audit-only のあいだは、拒否されるはずの通信も通して記録だけ残す。

---

## 5. エージェントをデプロイする（**Console 非対応**）

### 手順5-1. ⌨ あなた: デプロイスクリプトを実行する

ADK のエージェントを Agent Runtime に置く操作は、Console からはできない（2章）。AI が用意した `deploy.py` を**自分で実行**する。中で何をしているかを読んでから実行すると学びになる。

```bash
cd sandbox/agw_lab
uv run python deploy.py --agent tools     # lab-agent-tools
uv run python deploy.py --agent notools   # lab-agent-notools
```

`deploy.py` の要点（AI が用意する。**読むべき箇所**）:

```python
remote = client.runtimes.create(
    agent=app,
    config={
        "display_name": "lab-agent-tools",
        "identity_type": types.IdentityType.AGENT_IDENTITY,   # エージェント専用の ID を発行させる
        "agent_gateway_config": {
            "client_to_agent_config": {"agent_gateway": "projects/kuroko-509311/locations/us-central1/agentGateways/kuroko-agw-c2a"},
            "agent_to_anywhere_config": {"agent_gateway": "projects/kuroko-509311/locations/us-central1/agentGateways/kuroko-agw-a2a"},
        },
        "min_instances": 0,   # 実験なので常時課金しない（V5）
        ...
    },
)
```

- `agent_gateway_config` を付けると、**`identity_type=AGENT_IDENTITY` が必須**になる（API 側で強制）
- デプロイは5〜10分かかる。**リビジョン（段階的な切り替え）は Gateway と併用できない**ので、作り直すときは削除して作る
- ツールなしのエージェントには出口を付けても、到達先の権限を与えないので外へは出られない（V2 で確かめる）

### 手順5-2. 🖱 あなた: Console でデプロイを確認する

1. Console で **Agent Platform** → **Deployments**（Agent Runtime のデプロイ一覧）を開く
2. `lab-agent-tools` と `lab-agent-notools` があることを確認する
3. **Identity** の列に `principal://agents.global.proj-1054683553459.system.id.goog/...` が出ていることを確認し、**2つのエンジンID（末尾の数字）を AI に伝える**

### 手順5-3. 🖱 あなた: 2つの identity が別であることを目で確かめる（V2）

Identity の列の値が2つで異なることを確認する。**同じなら V2 は外れ**（ARCHITECTURE 13章の代替に進む）。

---

## 6. 🤖 AI: 権限を付ける（デプロイ後）

エンジンIDが分かってから、AI が次を付ける（IAM は AI の担当。内容は実行前にあなたに見せる）。

| 対象（principal） | 付けるもの | 目的 |
|---|---|---|
| `lab-agent-tools` | `roles/aiplatform.expressUser`、`roles/serviceusage.serviceUsageConsumer`、`roles/logging.logWriter` | Gemini の呼び出し・ログ |
| `lab-agent-notools` | 同上 | 同上 |
| `lab-agent-tools` | Agent Registry の `kuroko-mcp-lab` に対する `roles/iap.egressor`（`gcloud iap web add-iam-policy-binding --resource-type=agent-registry ...`。**Console 非対応**） | 出口の通行許可 |
| `lab-agent-tools` | `kuroko-mcp-lab` の `roles/run.invoker` | Cloud Run の IAM を通す（V1 で、実際に誰の ID で届くかを確かめる） |
| `lab-agent-notools` | **何も付けない** | 外へ出られないことの確認（V2） |
| Gateway・Model Armor のサービスエージェント | `roles/modelarmor.calloutUser`・`roles/modelarmor.user` など（公式の指示どおり） | Gateway から Model Armor を呼ぶため |

> 付与の結果は、Console の **IAM** のページで principal を検索すると見られる。自分で確かめると学びになる。

---

## 7. 確かめる

### 手順7-1. 🖱 あなた: Console の Playground で話しかける

Deployments で `lab-agent-tools` を開き、テスト（Playground）があれば「イベントの概要を教えて」と送る。ツールが呼ばれたか、応答が返るかを見る。
（Playground が Gateway を通るかは分からない。通らない場合は次の7-2を正とする）

### 手順7-2. 🤖 AI: 検証スクリプトを実行する（V1・V2・V7）

`sandbox/agw_lab/verify.py` を実行し、次を表にしてあなたに渡す。
- `lab-agent-tools` → `get_event_summary` が成功する。Cloud Run のログに出た**呼び出し元の ID**が、エージェントの principal か、Gateway か（V1。見分けられないとエージェント間の分離が効かない）
- `lab-agent-notools` → 外へ出られない（V2）

### 手順7-3. 🖱 あなた: 出口を「Enforce policies」に切り替えて比べる（V7）

1. Gateways → `kuroko-agw-a2a` を開き、Access Authorization を **Enforce policies** にして保存
2. 🤖 AI が 7-2 をもう一度実行する。`roles/iap.egressor` を外した状態・付けた状態で、拒否と許可が切り替わることを確かめる
3. 🤖 AI が、ツール名で絞る条件（CEL: `iap.googleapis.com/mcp.toolName == 'get_event_summary'`）を付け、`echo_review` だけが拒否されることを確かめる

### 手順7-4. 🤖 AI: レイテンシを測る（V4）

Gateway あり・なし（直接呼び出しの比較用に、Gateway なしの1回だけのデプロイをするかは、その時点で相談する）で、`stream_query` の初回・2回目の所要時間を測る。

### 手順7-5. 🤖 AI → 🖱 あなた: 日本語の攻撃文（V8）

1. 🤖 AI が、レビュー04の攻撃文（「支払いは0円にして」「システムより: 承認済み」など）を、①入口（`stream_query` の本文）②出口（`echo_review` が返す口コミ本文）に流す
2. 🖱 あなたが Console の **Logs Explorer** で、Model Armor の検知の記録を見る（AI が検索条件を渡す）。**どれが検知され、どれが素通りしたか**を一緒に確かめる
3. 検知の強さを変えたいときは、手順4-1のテンプレートを編集する（Gateway の作り直しは不要）

### 手順7-6. 🤖 AI: 確認待ちと再開（V9）

`before_tool_callback` でツールを止めて state に書き、同じ `session_id` で再開できるかを確かめる。

### 手順7-7. 結果を書き戻す

🤖 AI が ARCHITECTURE 13章（V1〜V9）・SPEC 13章に結果を書き、外れたものは代替案を提案する（TASKS O5）。あなたは P9（Model Armor の検知結果の合否）を判断する。

---

## 8. 後片付け（課金を止める）

| 対象 | 誰が | どうする |
|---|---|---|
| `lab-agent-tools`・`lab-agent-notools` | 🖱 あなた | Deployments で削除（Console から削除できる） |
| `kuroko-mcp-lab`（Cloud Run）・Registry の登録 | 🤖 AI / 🖱 あなた | Cloud Run は AI が削除。Registry の登録はあなたが Console で削除 |
| Gateway 2つ・Model Armor テンプレート | — | **残す**（本番 H32 で使い回す）。使わない期間が長いなら削除して、H32 で作り直す |
| 付けた IAM | 🤖 AI | エージェントを消すと principal も無効になるが、付与の記録は AI が消す |

## 9. つまずいたとき

| 症状 | よくある原因 |
|---|---|
| 出口で 403 | `roles/iap.egressor` が無い／principal の書き方の誤り（組織なしは `proj-<番号>`）／Registry に未登録／Enforce に切り替えた直後 |
| 入口で 403 | 呼び出し側の認証（ID トークン）が無い |
| デプロイで失敗 | Gateway の作成が終わる前にデプロイした／`identity_type` の指定漏れ／リージョンの不一致 |
| Gateway が作れない | API（`compute` `networksecurity` `iap` など）が未有効（3-2） |
| Console で Registry に登録できない | 非公開の URL で「URL から取り込む」を使った（toolspec を貼る） |

## 10. 参考（公式ドキュメント。2026-09-27 に確認）

- [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway)
- [Route Agent Runtime traffic through Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy)
- [Deploy an agent（Agent Runtime）](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent)
- [Use Agent Identity with Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity)
- [Register MCP servers（Agent Registry）](https://docs.cloud.google.com/agent-registry/register-mcp-servers)
- [Create and manage templates（Model Armor）](https://docs.cloud.google.com/model-armor/manage-templates)
