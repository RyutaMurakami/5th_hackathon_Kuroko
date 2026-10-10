"""エージェントを、Agent Gateway と Agent identity つきで Agent Runtime にデプロイする（TASKS I7・I8）。

`agents-cli deploy` には Gateway を付けるオプションが無いので、同じ経路（Dockerfile からのコンテナ
ビルド）に `agent_gateway_config` と Agent identity を足したもの。**ユーザーが自分で実行する**
（中で何をしているかを読んでから実行すること）。

使い方（リポジトリのルートから。`kuroko_agent`・`extract_agent` の仮想環境で動かす）:

  cd kuroko_agent
  uv run --with pathspec python ../infra/agent_platform/deploy_agent.py --agent kuroko --dry-run
  uv run --with pathspec python ../infra/agent_platform/deploy_agent.py --agent kuroko

  cd ../extract_agent
  uv run --with pathspec python ../infra/agent_platform/deploy_agent.py --agent extract --dry-run

要点:
- **両方のエージェントを、入口（Client-to-Agent）と出口（Agent-to-Anywhere）の Gateway につなぐ**。
  入口の Model Armor が、`kuroko-api` からの `streamQuery` の入力を検査する（プロンプトインジェクションの検知）
- Agent identity は**作成時にだけ**決められる。既存のエンジン（identity なし）は更新できないので、
  **別の表示名で新しく作る**（旧エンジンは動いたまま。切り替えて確かめてから `--delete-old` で消す）
- 作る前に、Gateway が存在し、種類（入口・出口）が合っているかを確かめる
- `GOOGLE_CLOUD_PROJECT` は Agent Runtime が予約している（渡すと失敗する）ので外す
- IAM は、Agent identity に**最小の4つだけ**を付ける（Gemini・ログ・メトリクス）。ほかの権限
  （`kuroko-api` への `run.invoker`・Registry の `iap.egressor`）は、V1 のあと Terraform で付ける
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT = "kuroko-509311"
LOCATION = "us-central1"
INGRESS = "kuroko-agw-c2a"
EGRESS = "kuroko-agw-a2a"
KUROKO_MCP_URL = "https://kuroko-api-nbymkfmzpq-uc.a.run.app/mcp"  # Registry の登録 URL と同じ
# kuroko-agent の Agent identity が偽装して ID トークンを作る SA（Terraform: sa-agent-mcp）。秘密ではない
KUROKO_MCP_INVOKER_SA = "sa-agent-mcp@kuroko-509311.iam.gserviceaccount.com"

# Agent identity に付ける権限（Gemini の呼び出し・ログ・メトリクスだけ）
BASE_ROLES = (
    "roles/aiplatform.user",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
)

AGENTS: dict[str, dict[str, Any]] = {
    "kuroko": {"display_name": "kuroko-agent", "dir": "kuroko_agent", "env": {"KUROKO_MCP_URL": KUROKO_MCP_URL, "KUROKO_MCP_INVOKER_SA": KUROKO_MCP_INVOKER_SA}},
    "extract": {"display_name": "extract-agent", "dir": "extract_agent", "env": {}},
}

RESERVED_ENV = frozenset({"GOOGLE_CLOUD_PROJECT"})  # Agent Runtime が自分で入れる（渡すと失敗する）


class DeployError(Exception):
    pass


# ---------------------------------------------------------------- 設定の組み立て（純粋な関数）
def gateway_path(project: str, location: str, name: str) -> str:
    return f"projects/{project}/locations/{location}/agentGateways/{name}"


def gateway_config(project: str, location: str, ingress: str, egress: str) -> dict[str, Any]:
    """入口（Client-to-Agent）と出口（Agent-to-Anywhere）を、両方つなぐ。"""
    return {
        "client_to_agent_config": {"agent_gateway": gateway_path(project, location, ingress)},
        "agent_to_anywhere_config": {"agent_gateway": gateway_path(project, location, egress)},
    }


def read_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("'\"")
    return env


def build_env(agent_dir: Path, extra: dict[str, str], existing: dict[str, str] | None = None) -> dict[str, str]:
    """実行時の環境変数。`.env` → 追加分の順に重ね、予約された変数を外し、既定値を足す。"""
    env = read_dotenv(agent_dir / ".env")
    env.update(extra)
    for key in RESERVED_ENV & env.keys():
        del env[key]
    if "AGENT_VERSION" not in env:
        with open(agent_dir / "pyproject.toml", "rb") as f:
            env["AGENT_VERSION"] = tomllib.load(f)["project"]["version"]
    if "GEMINI_API_KEY" not in env and "GOOGLE_API_KEY" not in env:
        env.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        env.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    env.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")
    env.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "NO_CONTENT")
    env.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")  # 本文を記録に残さない
    for key, value in (existing or {}).items():  # 更新のときは、外で設定された値を消さない
        env.setdefault(key, value)
    return env


def packaged_files(root: Path) -> list[str]:
    """アップロードするファイル（`.gitignore` に載っているものと `.git` は除く）。"""
    import pathspec

    lines = [".git", ".gcloudignore", ".gitignore", ".env", "deployment_metadata.json", ".venv"]
    ignore = root / ".gcloudignore"
    ignore = ignore if ignore.exists() else root / ".gitignore"
    if ignore.exists():
        lines += ignore.read_text(encoding="utf-8").splitlines()
    spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        dirnames[:] = sorted(d for d in dirnames if not spec.match_file((rel_dir / d).as_posix() + "/"))
        for name in sorted(filenames):
            rel = (rel_dir / name).as_posix()
            if not spec.match_file(rel):
                files.append(f"./{rel}")
    return files


def build_config(
    *, display_name: str, files: list[str], env: dict[str, str], gateways: dict[str, Any],
    min_instances: int = 0, root_certificates: list[str] | None = None,
) -> dict[str, Any]:  # fmt: skip
    return {
        "display_name": display_name,
        "source_packages": files,
        "env_vars": env,
        "identity_type": "AGENT_IDENTITY",  # Agent Gateway には必須（`service_account` とは併用しない）
        "agent_gateway_config": gateways,
        "min_instances": min_instances,  # 開発中は常時課金しない（V5）
        # 出口 Gateway の TLS 検査のルート CA を、イメージのビルドで信頼ストアに入れる（Dockerfile が受ける）
        "image_spec": (
            {"build_args": {"AGENT_GATEWAY_ROOT_CERTIFICATES": "\n".join(root_certificates)}}
            if root_certificates
            else {}
        ),
        "agent_framework": "google-adk",
    }


def plan_action(existing: list[dict[str, str]], display_name: str) -> str:
    """`create`（新規）か `update`（Agent identity つきの既存を更新）。作り直しが必要なら理由つきで止める。

    existing: 同じ表示名のエンジン `[{"name": ..., "identity_type": ...}]`
    """
    if not existing:
        return "create"
    if len(existing) > 1:
        raise DeployError(f"同じ表示名のエンジンが {len(existing)} 件ある。Console で整理してから再実行する: {display_name}")
    if str(existing[0].get("identity_type", "")).upper().endswith("AGENT_IDENTITY"):
        return "update"
    raise DeployError(
        f"既存の「{display_name}」は Agent identity ではない（identity は作成時にしか決められない）。\n"
        f"  旧エンジンは動かしたまま、別の表示名で新しく作る:  --display-name {display_name}-gw\n"
        "  切り替えて確かめたあと、旧エンジンを --delete-old <エンジンの名前> で消す。"
    )


# ---------------------------------------------------------------- 事前の確認
def check_gateway(name: str, expected_path: str, project: str, location: str) -> None:
    """Gateway が存在し、種類（入口・出口）が合っているかを確かめる（gcloud を使う）。"""
    res = subprocess.run(
        ["gcloud", "network-services", "agent-gateways", "describe", name,
         f"--location={location}", f"--project={project}", "--format=json"],
        capture_output=True, text=True,
    )  # fmt: skip
    if res.returncode != 0:
        raise DeployError(f"Gateway「{name}」が見つからない（Console で作ったか、名前が合っているか）:\n{res.stderr.strip()[:300]}")
    text = res.stdout.upper().replace("-", "_")
    if expected_path not in text:
        raise DeployError(f"Gateway「{name}」の種類が違う（{expected_path} のはず）。入口と出口を取り違えていないか")


def extract_root_certificates(describe_json: str) -> list[str]:
    """出口 Gateway の `agentGatewayCard.rootCertificates`（TLS 検査のルート CA）。"""
    try:
        card = json.loads(describe_json).get("agentGatewayCard") or {}
    except ValueError:
        return []
    return [c for c in card.get("rootCertificates", []) if "BEGIN CERTIFICATE" in c]


def fetch_root_certificates(name: str, project: str, location: str) -> list[str]:
    out = _run_gcloud(["gcloud", "network-services", "agent-gateways", "describe", name,
                       f"--location={location}", f"--project={project}", "--format=json"])  # fmt: skip
    return extract_root_certificates(out)


def _run_gcloud(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise DeployError(f"gcloud が失敗した: {res.stderr.strip()[:300]}")
    return res.stdout


def grant_base_roles(project: str, principal: str) -> None:
    """Agent identity に、最小の権限（Gemini・ログ・メトリクス）を付ける。すでにあるものは足さない。"""
    from google.cloud import resourcemanager_v3
    from google.iam.v1 import iam_policy_pb2, policy_pb2

    client = resourcemanager_v3.ProjectsClient()
    policy = client.get_iam_policy(request=iam_policy_pb2.GetIamPolicyRequest(resource=f"projects/{project}"))
    changed = False
    for role in BASE_ROLES:
        existing = next((b for b in policy.bindings if b.role == role and not b.condition.expression), None)
        if existing is None:
            policy.bindings.append(policy_pb2.Binding(role=role, members=[principal]))
            changed = True
        elif principal not in existing.members:
            existing.members.append(principal)
            changed = True
    if changed:
        client.set_iam_policy(request=iam_policy_pb2.SetIamPolicyRequest(resource=f"projects/{project}", policy=policy))


# ---------------------------------------------------------------- 実行
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", choices=sorted(AGENTS), required=True)
    ap.add_argument("--display-name", help="既定: kuroko-agent / extract-agent")
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--location", default=LOCATION)
    ap.add_argument("--ingress", default=INGRESS, help="入口の Gateway の名前")
    ap.add_argument("--egress", default=EGRESS, help="出口の Gateway の名前")
    ap.add_argument("--min-instances", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="何もデプロイせず、内容だけ表示する")
    ap.add_argument("--yes", action="store_true", help="確認を省く")
    ap.add_argument("--skip-gateway-check", action="store_true")
    ap.add_argument("--delete-old", metavar="ENGINE", help="切り替えて確かめたあとに、旧エンジンを消す")
    args = ap.parse_args(argv)

    spec = AGENTS[args.agent]
    agent_dir = Path.cwd()
    if agent_dir.name != spec["dir"] or not (agent_dir / "Dockerfile").exists():
        raise DeployError(f"{spec['dir']}/ の中で実行する（今: {agent_dir}）")
    display_name = args.display_name or spec["display_name"]

    ingress_path = gateway_path(args.project, args.location, args.ingress)
    egress_path = gateway_path(args.project, args.location, args.egress)
    if not args.skip_gateway_check:
        check_gateway(args.ingress, "CLIENT_TO_AGENT", args.project, args.location)
        check_gateway(args.egress, "AGENT_TO_ANYWHERE", args.project, args.location)

    import vertexai
    from vertexai._genai.types import IdentityType

    client = vertexai.Client(project=args.project, location=args.location, http_options={"api_version": "v1beta1"})
    same = [
        {"name": a.api_resource.name, "identity_type": str(getattr(a.api_resource.spec, "identity_type", ""))}
        for a in client.agent_engines.list()
        if a.api_resource.display_name == display_name
    ]
    action = plan_action(same, display_name)

    existing_env: dict[str, str] = {}
    if action == "update":
        got = client.agent_engines.get(name=same[0]["name"])
        dep = getattr(got.api_resource.spec, "deployment_spec", None)
        existing_env = {v.name: (v.value or "") for v in (getattr(dep, "env", None) or []) if getattr(v, "name", None)}

    env = build_env(agent_dir, dict(spec["env"]), existing_env)
    files = packaged_files(agent_dir)
    if "./Dockerfile" not in files:
        raise DeployError("Dockerfile がアップロードの対象から外れている（.gitignore を確認）")
    gateways = gateway_config(args.project, args.location, args.ingress, args.egress)
    certs = [] if args.skip_gateway_check else fetch_root_certificates(args.egress, args.project, args.location)
    if not args.skip_gateway_check and not certs:
        raise DeployError("出口 Gateway からルート CA を取得できなかった（agentGatewayCard.rootCertificates が空）")
    config = build_config(
        display_name=display_name, files=files, env=env, gateways=gateways,
        min_instances=args.min_instances, root_certificates=certs,
    )  # fmt: skip

    print(f"\n【{action}】{display_name}  （{args.project} / {args.location}）")
    print(f"  入口（Client-to-Agent）: {ingress_path}")
    print(f"  出口（Agent-to-Anywhere）: {egress_path}")
    print("  identity: AGENT_IDENTITY（最小の権限だけ付ける:", ", ".join(r.split("/")[-1] for r in BASE_ROLES) + "）")
    print(f"  min_instances: {args.min_instances}  / アップロードするファイル: {len(files)} 件")
    print(f"  出口 Gateway のルート CA: {len(certs)} 件（ビルド引数で Dockerfile に渡す）")
    print("  環境変数:", ", ".join(f"{k}={'(値は表示しない)' if 'KEY' in k or 'TOKEN' in k else v}" for k, v in sorted(env.items())))
    if same:
        print(f"  既存: {same[0]['name']}")
    if args.dry_run:
        print("\n--dry-run のため、ここまで（何もデプロイしていない）")
        return 0
    if not args.yes and input("\nデプロイしてよいか [y/N] ").strip().lower() != "y":
        print("中止した")
        return 1

    from vertexai._genai import _agent_engines_utils

    if action == "create":
        bare = client.agent_engines.create(
            config={"identity_type": IdentityType.AGENT_IDENTITY, "display_name": display_name}
        )
        name = bare.api_resource.name
        principal = f"principal://{bare.api_resource.spec.effective_identity}"
    else:
        name = same[0]["name"]
        principal = None
    if principal:
        print(f"\nAgent identity: {principal}\n  最小の権限を付ける…")
        grant_base_roles(args.project, principal)

    api_config = client.agent_engines._create_config(
        mode="update",
        display_name=config["display_name"],
        source_packages=config["source_packages"],
        env_vars=config["env_vars"],
        min_instances=config["min_instances"],
        identity_type=IdentityType.AGENT_IDENTITY,
        agent_framework=config["agent_framework"],
        agent_gateway_config=config["agent_gateway_config"],
        image_spec=config["image_spec"],
    )
    op = client.agent_engines._update(name=name, config=api_config)
    print(f"デプロイ中（5〜10分）… operation: {op.name}")
    _agent_engines_utils._await_operation(operation_name=op.name, get_operation_fn=client.agent_engines._get_agent_operation)
    done = client.agent_engines._get_agent_operation(operation_name=op.name)
    if done.error:
        raise DeployError(f"デプロイに失敗: {done.error}")
    got = client.agent_engines.get(name=name)

    meta = {
        "remote_agent_runtime_id": got.api_resource.name,
        "deployment_target": "agent_runtime",
        "is_a2a": True,
        "agent_directory": "app",
        "agent_gateway": {"ingress": ingress_path, "egress": egress_path},
        "effective_identity": getattr(got.api_resource.spec, "effective_identity", None),
        "deployment_timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    (agent_dir / "deployment_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n✅ 完了")
    print(f"  エンジン: {got.api_resource.name}")
    print(f"  identity: principal://{meta['effective_identity']}")
    print("  → この2つを AI に伝える（IAM・V1・tfvars の更新は AI が行う）")
    if args.delete_old:
        print(f"\n旧エンジンを削除する: {args.delete_old}")
        client.agent_engines.delete(name=args.delete_old, force=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DeployError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(2)
