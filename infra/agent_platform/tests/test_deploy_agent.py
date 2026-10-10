"""deploy_agent.py の、デプロイ前に決まる部分（設定の組み立て・事前の確認）。実際のデプロイはしない。

実行（`kuroko_agent/` で）:
  uv run --with pytest --with pathspec python -m pytest ../infra/agent_platform/tests -q
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deploy_agent", HERE / "deploy_agent.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def make_agent_dir(tmp_path, env_text="GOOGLE_CLOUD_PROJECT=p\nGOOGLE_CLOUD_LOCATION=global\n"):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="1.2.3"\n')
    (tmp_path / ".env").write_text(env_text)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "agent.py").write_text("x = 1\n")
    return tmp_path


# ---------------- Gateway の設定 ----------------
def test_both_ingress_and_egress_gateways_are_attached_with_full_resource_names():
    g = d.gateway_config("kuroko-509311", "us-central1", "kuroko-agw-c2a", "kuroko-agw-a2a")
    base = "projects/kuroko-509311/locations/us-central1/agentGateways/"
    assert g == {
        "client_to_agent_config": {"agent_gateway": base + "kuroko-agw-c2a"},
        "agent_to_anywhere_config": {"agent_gateway": base + "kuroko-agw-a2a"},
    }


def test_every_agent_goes_through_the_ingress_gateway_where_prompt_injection_is_detected():
    assert set(d.AGENTS) == {"kuroko", "extract"}  # 両方のエージェントが対象
    cfg = d.build_config(display_name="x", files=["./Dockerfile"], env={}, gateways=d.gateway_config("p", "l", "i", "e"))
    assert cfg["agent_gateway_config"]["client_to_agent_config"]["agent_gateway"].endswith("/agentGateways/i")


def test_the_config_uses_agent_identity_and_never_a_service_account():
    cfg = d.build_config(display_name="x", files=["./Dockerfile"], env={}, gateways={})
    assert cfg["identity_type"] == "AGENT_IDENTITY" and "service_account" not in cfg
    assert cfg["min_instances"] == 0 and cfg["agent_framework"] == "google-adk"


def test_only_the_minimal_base_roles_are_granted():
    assert d.BASE_ROLES == (
        "roles/aiplatform.user", "roles/serviceusage.serviceUsageConsumer",
        "roles/logging.logWriter", "roles/monitoring.metricWriter",
    )  # fmt: skip
    for broad in ("owner", "editor", "browser", "run.invoker", "iap", "datastore", "secretmanager"):
        assert not any(broad in r for r in d.BASE_ROLES)  # kuroko-api・Registry への権限は、V1 のあと別に付ける


def test_only_the_kuroko_agent_gets_the_mcp_url_and_it_matches_the_registry_entry():
    assert d.AGENTS["kuroko"]["env"]["KUROKO_MCP_URL"].endswith("/mcp")  # Registry の登録と同じ綴り
    assert d.AGENTS["extract"]["env"] == {}  # ツールなしのエージェントには渡さない


# ---------------- 環境変数 ----------------
def test_reserved_project_variable_is_dropped_and_defaults_are_safe(tmp_path):
    env = d.build_env(make_agent_dir(tmp_path), {})
    assert "GOOGLE_CLOUD_PROJECT" not in env  # 渡すと Agent Runtime が失敗する
    assert env["GOOGLE_GENAI_USE_VERTEXAI"] == "true" and env["GOOGLE_CLOUD_LOCATION"] == "global"
    assert env["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] == "false"  # 本文を記録に残さない
    assert env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "NO_CONTENT"
    assert env["AGENT_VERSION"] == "1.2.3"


def test_extra_values_win_over_dotenv_and_existing_values_are_preserved_on_update(tmp_path):
    root = make_agent_dir(tmp_path, "KUROKO_MCP_URL=old\n")
    env = d.build_env(root, {"KUROKO_MCP_URL": "new"}, existing={"OUTSIDE": "keep", "KUROKO_MCP_URL": "stale"})
    assert env["KUROKO_MCP_URL"] == "new" and env["OUTSIDE"] == "keep"  # 外で設定された値を消さない


def test_secrets_are_never_read_from_anywhere_but_dotenv_and_are_not_uploaded(tmp_path):
    root = make_agent_dir(tmp_path)
    (root / "deployment_metadata.json").write_text("{}")
    (root / ".venv").mkdir()
    (root / ".venv" / "x.py").write_text("")
    files = d.packaged_files(root)
    assert "./Dockerfile" in files and "./app/agent.py" in files
    assert all(not f.startswith(("./.env", "./.venv", "./.git")) for f in files)  # .env はアップロードしない
    assert "./deployment_metadata.json" not in files


# ---------------- 既存エンジンの扱い ----------------
def test_a_new_engine_is_created_and_an_agent_identity_engine_is_updated():
    assert d.plan_action([], "kuroko-agent") == "create"
    assert d.plan_action([{"name": "n", "identity_type": "IdentityType.AGENT_IDENTITY"}], "k") == "update"
    assert d.plan_action([{"name": "n", "identity_type": "AGENT_IDENTITY"}], "k") == "update"


@pytest.mark.parametrize("kind", ["IdentityType.SERVICE_ACCOUNT", "IDENTITY_TYPE_UNSPECIFIED", "None", ""])
def test_an_existing_engine_without_agent_identity_is_never_touched_and_a_new_name_is_suggested(kind):
    with pytest.raises(d.DeployError) as e:
        d.plan_action([{"name": "n", "identity_type": kind}], "kuroko-agent")
    assert "kuroko-agent-gw" in str(e.value) and "--delete-old" in str(e.value)


def test_duplicate_display_names_stop_the_deploy():
    two = [{"name": "a", "identity_type": "AGENT_IDENTITY"}, {"name": "b", "identity_type": "AGENT_IDENTITY"}]
    with pytest.raises(d.DeployError):
        d.plan_action(two, "k")


# ---------------- Gateway の事前確認 ----------------
def fake_run(stdout="", code=0, stderr=""):
    return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout, stderr)


def test_missing_gateway_stops_before_anything_is_deployed(monkeypatch):
    monkeypatch.setattr(d.subprocess, "run", fake_run(code=1, stderr="NOT_FOUND"))
    with pytest.raises(d.DeployError) as e:
        d.check_gateway("kuroko-agw-c2a", "CLIENT_TO_AGENT", "p", "us-central1")
    assert "見つからない" in str(e.value)


def test_swapped_ingress_and_egress_are_detected(monkeypatch):
    monkeypatch.setattr(d.subprocess, "run", fake_run('{"governedAccessPath": "AGENT_TO_ANYWHERE"}'))
    with pytest.raises(d.DeployError) as e:
        d.check_gateway("kuroko-agw-c2a", "CLIENT_TO_AGENT", "p", "us-central1")
    assert "取り違え" in str(e.value)
    monkeypatch.setattr(d.subprocess, "run", fake_run('{"governedAccessPath": "CLIENT_TO_AGENT"}'))
    d.check_gateway("kuroko-agw-c2a", "CLIENT_TO_AGENT", "p", "us-central1")  # 合っていれば通る


def test_running_from_the_wrong_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(d.DeployError):
        d.main(["--agent", "kuroko", "--dry-run", "--skip-gateway-check"])


# ---------------- 出口 Gateway のルート CA ----------------
CERT = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


def test_root_certificates_are_taken_from_the_egress_gateways_card():
    js = json.dumps({"agentGatewayCard": {"rootCertificates": [CERT, "not a cert"]}})
    assert d.extract_root_certificates(js) == [CERT]
    assert d.extract_root_certificates("{}") == [] and d.extract_root_certificates("bad") == []


def test_the_certificates_reach_the_image_build_only_when_present():
    cfg = d.build_config(display_name="x", files=[], env={}, gateways={}, root_certificates=[CERT, CERT])
    assert cfg["image_spec"] == {"build_args": {"AGENT_GATEWAY_ROOT_CERTIFICATES": CERT + "\n" + CERT}}
    assert d.build_config(display_name="x", files=[], env={}, gateways={})["image_spec"] == {}


def test_both_dockerfiles_install_the_gateway_ca_only_when_the_build_arg_is_given():
    for name in ("kuroko_agent", "extract_agent"):
        text = (HERE.parents[1] / name / "Dockerfile").read_text()
        assert "ARG AGENT_GATEWAY_ROOT_CERTIFICATES" in text
        assert 'if [ -n "$AGENT_GATEWAY_ROOT_CERTIFICATES" ]' in text  # 引数が無いビルドでは何もしない
        assert "update-ca-certificates" in text and "SSL_CERT_FILE" in text and "REQUESTS_CA_BUNDLE" in text
        assert text.index("update-ca-certificates") > text.index("uv sync")
