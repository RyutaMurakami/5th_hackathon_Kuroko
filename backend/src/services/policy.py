"""規程の値の読み込み（`policies/company_rules.yaml` → `PolicySnapshot`。TASKS B1）。

yaml は、RAG が使えないときのフォールバックと、抽出結果を検証するテストの正解データ（SPEC 9.7）。
実行時の按分は、企画時に Event へ保存した `policy_snapshot` だけを使う。
"""

from pathlib import Path
from typing import Any

import yaml

from src.models.policy import PolicySnapshot

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "policies" / "company_rules.yaml"


def snapshot_from_rules(
    rules: dict[str, Any], event_type: str = "welcome_farewell"
) -> PolicySnapshot:
    event = rules["event_types"][event_type]
    subsidy = event["company_subsidy"]
    return PolicySnapshot.model_validate(
        {
            "policy_id": rules["policy_id"],
            "version": str(rules["version"]),
            "member_classes": [
                {
                    "id": c["id"],
                    "label": c["label"],
                    "role": c["match"]["role"],
                    "tenure_months_less_than": c["match"].get("tenure_months_less_than"),
                    "rank": c["rank"],
                    "weight": c["weight"],
                    "consent_cap_yen": c["consent_cap_yen"],
                }
                for c in rules["member_classes"]
            ],
            "subsidy": {
                "per_attendee_yen": subsidy["per_attendee_yen"],
                "include_guests_of_honor": subsidy["include_guests_of_honor"],
                "max_per_event_yen": subsidy["max_per_event_yen"],
                "eligible_employment_types": subsidy["eligible_employment_types"],
            },
            "rounding_unit_yen": rules["split"]["rounding"]["unit_yen"],
            "rounding_method": rules["split"]["rounding"]["method"],
            "shortfall_to": rules["split"]["shortfall_to"],
            "approver_selection": rules["approval"]["approver_selection"],
            "hard_limit_per_person_yen": event["budget"]["hard_limit_per_person_yen"],
            "mandate_valid_days_after_event": rules["payment"]["payer_mandate"][
                "expires_after_event_days"
            ],
            "venue_max_travel_minutes": event["venue_access"]["max_travel_minutes"],
            "venue_relax_step_minutes": event["venue_access"]["relax_step_minutes"],
            "venue_relax_limit_minutes": event["venue_access"]["relax_limit_minutes"],
        }
    )


def load_snapshot(
    path: Path = DEFAULT_RULES_PATH, event_type: str = "welcome_farewell"
) -> PolicySnapshot:
    with path.open(encoding="utf-8") as f:
        return snapshot_from_rules(yaml.safe_load(f), event_type)
