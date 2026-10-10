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


SA = "sa-agent-mcp@kuroko-509311.iam.gserviceaccount.com"
URL = "https://kuroko-api-1054683553459.us-central1.run.app"
LINE = "mcp caller claims={'aud': '%s', 'email': '%s'} allowed=%s"


def test_claims_and_the_decision_are_parsed_from_the_log_line_the_api_writes():
    assert v.parse_claims(LINE % (URL, SA, "True")) == ({"aud": URL, "email": SA}, True)
    assert v.parse_claims(LINE % (URL, SA, "False"))[1] is False
    assert v.parse_claims("no match") is None and v.parse_claims("mcp caller claims={bad allowed=True") is None


def test_the_identity_rule_matches_the_apis_email_then_sub_order():
    assert v.identity_of({"email": "a@x", "sub": "s"}) == "a@x"
    assert v.identity_of({"sub": "s"}) == "s" and v.identity_of({"aud": "x"}) is None


def test_v1_passes_only_for_the_invoker_sa_with_the_right_audience_and_when_the_api_let_it_in():
    ok = v.judge_v1([({"aud": URL, "email": SA}, True)], SA, URL)
    assert ok["ok"] and ok["principal"] == SA


def test_v1_names_the_reason_when_it_fails():
    cases = [
        ([], "no_call_seen"),
        ([({"aud": URL, "email": "other@x"}, True)], "identity_differs"),
        ([({"aud": "https://kuroko-api-hash-uc.a.run.app", "email": SA}, True)], "wrong_audience"),
        ([({"aud": URL, "email": SA}, False)], "rejected_by_api"),
    ]
    for seen, reason in cases:
        j = v.judge_v1(seen, SA, URL)
        assert not j["ok"] and j["reason"] == reason


def test_v1_judges_the_latest_call():
    seen = [({"aud": URL, "email": "x@y"}, False), ({"aud": URL, "email": SA}, True)]
    assert v.judge_v1(seen, SA, URL)["ok"]  # 設定を直したあとの最新の呼び出しで判定する


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
