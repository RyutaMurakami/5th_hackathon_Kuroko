"""verify_g2.py の、判定の部分（外部を呼ばない）。実行（`backend/` で）:
  uv run --with pytest python -m pytest ../infra/agent_platform/tests -q
"""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_g2", HERE / "verify_g2.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

API = "https://kuroko-api-xxxx-uc.a.run.app"
OWN = "agents.global.proj-1054683553459.system.id.goog/resources/aiplatform/projects/1054683553459/locations/us-central1/reasoningEngines/111"
LINE = "mcp caller claims={'aud': '%s', 'sub': 'principal://%s'} allowed=False"


def test_claims_are_parsed_from_the_log_line_the_api_writes():
    c = v.parse_claims(LINE % (API, OWN))
    assert c == {"aud": API, "sub": f"principal://{OWN}"}
    assert v.parse_claims("no match") is None and v.parse_claims("mcp caller claims={bad allowed=True") is None


def test_the_identity_rule_matches_the_apis_email_then_sub_order():
    assert v.identity_of({"email": "a@x", "sub": "s"}) == "a@x"
    assert v.identity_of({"sub": "s"}) == "s" and v.identity_of({"aud": "x"}) is None


def test_v1_passes_only_when_the_calling_identity_is_the_agents_own_and_the_audience_is_right():
    ok = v.judge_v1([{"aud": API, "sub": f"principal://{OWN}"}], OWN, API)
    assert ok["ok"] and ok["principal"] == f"principal://{OWN}"
    wrong_aud = v.judge_v1([{"aud": "https://other", "sub": f"principal://{OWN}"}], OWN, API)
    assert not wrong_aud["ok"] and wrong_aud["reason"] == "wrong_audience"


def test_v1_fails_when_gateway_or_another_identity_is_what_reaches_the_api():
    other = v.judge_v1([{"aud": API, "email": "gateway@proj.iam.gserviceaccount.com"}], OWN, API)
    assert not other["ok"] and other["reason"] == "identity_differs"
    assert other["principal"] == "gateway@proj.iam.gserviceaccount.com"  # 何が届いたかを返す
    none = v.judge_v1([], OWN, API)
    assert not none["ok"] and none["reason"] == "no_call_seen"


def test_v2_requires_distinct_identities_and_no_extra_roles_on_the_tool_less_agent():
    base = set(v.EXTRACT_ALLOWED_ROLES)
    assert v.judge_v2("k", "e", base)["ok"]
    assert not v.judge_v2("same", "same", base)["ok"]  # 同じ身元ではエージェント間の分離が効かない
    bad = v.judge_v2("k", "e", base | {"roles/run.invoker", "roles/datastore.user"})
    assert not bad["ok"] and bad["extract_extra_roles"] == ["roles/datastore.user", "roles/run.invoker"]
    assert not v.judge_v2("", "e", base)["ok"]


def test_the_attack_corpus_covers_the_review_scenarios_in_japanese():
    text = " ".join(t for _, t in v.ATTACKS)
    for phrase in ("指示を無視", "承認済み", "振込先", "管理者", "システムプロンプト"):
        assert phrase in text
    assert len({label for label, _ in v.ATTACKS}) == len(v.ATTACKS)
