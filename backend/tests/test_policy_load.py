from src.services.policy import load_snapshot


def test_company_rules_yaml_loads_into_a_validated_snapshot():
    p = load_snapshot()
    assert (p.policy_id, p.version) == ("sample-co-social-event", "1.0.0")
    assert [(c.id, c.weight, c.rank, c.consent_cap_yen) for c in p.member_classes] == [
        ("director", 2.0, 4, 12000),
        ("manager", 1.5, 3, 9000),
        ("new_hire", 0.5, 1, 3000),
        ("staff", 1.0, 2, 6000),
    ]
    assert p.subsidy.per_attendee_yen == 3000 and p.subsidy.max_per_event_yen == 60000
    assert p.subsidy.include_guests_of_honor is True
    assert (p.rounding_unit_yen, p.rounding_method, p.shortfall_to) == (100, "floor", "approver")
    assert p.approver_selection == [
        "highest_weight",
        "highest_rank",
        "earliest_hire_date",
        "lowest_employee_id",
    ]
    assert p.hard_limit_per_person_yen == 7000


def test_unknown_approver_rule_or_duplicate_class_is_rejected():
    import pytest
    from pydantic import ValidationError

    base = load_snapshot().model_dump()
    with pytest.raises(ValidationError):
        type(load_snapshot()).model_validate(base | {"approver_selection": ["random"]})
    dup = base | {"member_classes": base["member_classes"] + base["member_classes"][:1]}
    with pytest.raises(ValidationError):
        type(load_snapshot()).model_validate(dup)
