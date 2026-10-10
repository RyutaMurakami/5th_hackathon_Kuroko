# 出口 Gateway のアクセスポリシー（V7）

`kuroko-agent` の Agent identity だけに、出口 Gateway（`kuroko-agw-a2a`）を通って
Agent Registry の MCP サーバー（`kuroko-api-mcp`）へ行く権限（`iap.googleapis.com/resources.egressViaIAP`）を与える。
**Enforce では、出口の通信すべて（Gemini など Google API を含む）が対象**。許可の無いエージェントは動かない。
`kuroko-agent` と `extract-agent` の 2 つに、それぞれルールを与えている。

```bash
# ポリシーの作成（permission は FQDN 形式。--details-rules はルールの配列）
gcloud iam access-policies create kuroko-agent-egress \
  --details-rules=infra/agent_platform/iam/kuroko-agent-egress.json \
  --display-name="kuroko-agent の出口（kuroko-api-mcp）の許可" \
  --project=kuroko-509311 --location=global

# プロジェクトへのバインド
gcloud iam policy-bindings create kuroko-agent-egress-binding \
  --policy="projects/kuroko-509311/locations/global/accessPolicies/kuroko-agent-egress" \
  --target-resource="//cloudresourcemanager.googleapis.com/projects/1054683553459" \
  --project=kuroko-509311 --location=global
```

エンジンを作り直して ID が変わったら、`principals` を更新する（`accessPolicies update`）。
Enforce の切り替えは、Console の Gateway の Access Authorization（拡張の `iamEnforcementMode`）で行う。

## 注意
- IAM の変更の反映には **1〜3 分**かかる。その間、返答が失敗することがある。
- エンジンを**作り直して ID が変わったら、先に** `principals` を更新する（古い ID のままだと、新しいエンジンは出口を通れず動かない）。
- 更新: `gcloud iam access-policies update kuroko-agent-egress --details-rules=infra/agent_platform/iam/kuroko-agent-egress.json --project=kuroko-509311 --location=global --quiet`
- 検証で許可を外すときは、必ずバインドを復旧する（`policy-bindings delete` は `--quiet` が無いと確認待ちで止まる）。
