# 出口 Gateway のアクセスポリシー（V7）

`kuroko-agent` の Agent identity だけに、出口 Gateway（`kuroko-agw-a2a`）を通って
Agent Registry の MCP サーバー（`kuroko-api-mcp`）へ行く権限（`iap.googleapis.com/resources.egressViaIAP`）を与える。
`extract-agent` には何も与えない（既定は拒否）。

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
