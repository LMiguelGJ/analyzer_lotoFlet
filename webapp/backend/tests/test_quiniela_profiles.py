from copy import deepcopy
from fractions import Fraction
from typing import Any, cast

import pytest

from laboratorio.domain.contracts import MAX_MONEY, PayoutMultiplier
from laboratorio.domain.quiniela_profiles import (
    QuinielaProfile,
    QuinielaRules,
    create_profile,
)


def valid_rules_mapping():
    return {
        "schema_version": 2,
        "universe": [0, 2, 80],
        "display_width": 2,
        "positions": 3,
        "played_positions": [0, 2],
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [
            {"numerator": 5, "denominator": 2},
            {"numerator": 3, "denominator": 1},
            {"numerator": 7, "denominator": 2},
        ],
        "payout_mode": "best",
        "currency": "DOP",
        "scale": 2,
        "minimum_stake": 2,
        "stake_increment": 2,
        "maximum_stake": 100,
        "max_coverage": 3,
        "max_exposure": 300,
    }


def test_create_profile_is_versioned_frozen_and_round_trips_canonically():
    source = valid_rules_mapping()
    original = deepcopy(source)
    rules = QuinielaRules.from_mapping(source)
    profile = create_profile("  Perfil pequeño  ", rules)

    assert source == original
    assert profile.name == "Perfil pequeño"
    assert profile.schema_version == 2
    assert profile.id == profile.id.lower()
    assert len(profile.id) == 36
    assert profile.rules is rules
    assert profile.to_mapping() == {
        "schema_version": 2,
        "id": profile.id,
        "name": "Perfil pequeño",
        "rules": rules.to_mapping(),
    }
    assert QuinielaProfile.from_mapping(profile.to_mapping()) == profile
    assert QuinielaRules.from_mapping(rules.to_mapping()) == rules
    mutable_rules = cast(Any, rules)
    with pytest.raises((AttributeError, TypeError, ValueError)):
        mutable_rules.positions = 4


def test_validation_rejects_noncanonical_and_unsafe_rules_without_mutation():
    base = valid_rules_mapping()
    invalid_changes = [
        {"universe": [0, 2, 2]},
        {"universe": [2, 0, 80]},
        {"universe": [0, 2, 2**53]},
        {"display_width": 1},
        {"played_positions": [2, 0]},
        {"played_positions": [3]},
        {"positions": 4},
        {"allows_repeats": 1},
        {"scale": 7},
        {"maximum_stake": 101},
        {"max_coverage": 4},
        {"minimum_stake": 3},
        {"unexpected": "not allowed"},
        {"minimum_stake": None},
        {"schema_version": 1},
    ]
    for change in invalid_changes:
        candidate = deepcopy(base)
        candidate.update(change)
        untouched = deepcopy(candidate)
        with pytest.raises((ValueError, TypeError)):
            QuinielaRules.from_mapping(candidate)
        assert candidate == untouched


def test_rational_payouts_are_exact_and_bounded_for_both_payout_modes():
    rules = QuinielaRules.from_mapping(valid_rules_mapping())
    assert all(isinstance(value, PayoutMultiplier) for value in rules.multipliers)
    actual = Fraction(rules.multipliers[0].numerator, rules.multipliers[0].denominator)
    assert actual == Fraction(5, 2)

    fractional = valid_rules_mapping()
    fractional["stake_increment"] = 1
    fractional["minimum_stake"] = 1
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(fractional)

    too_large = valid_rules_mapping()
    too_large["max_exposure"] = MAX_MONEY
    too_large["multipliers"] = [{"numerator": MAX_MONEY, "denominator": 1}] * 3
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(too_large)


def test_unordered_played_positions_require_equal_rational_payouts():
    mapping = valid_rules_mapping()
    mapping["played_positions"] = [0, 1]
    mapping["multipliers"][1] = {"numerator": 5, "denominator": 2}
    mapping["order_matters"] = False
    rules = QuinielaRules.from_mapping(mapping)
    assert rules.order_matters is False

    mapping["multipliers"][1] = {"numerator": 4, "denominator": 1}
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(mapping)


def test_profile_mapping_rejects_noncanonical_ids_and_unknown_fields():
    profile = create_profile("Perfil", QuinielaRules.from_mapping(valid_rules_mapping()))
    mapping = profile.to_mapping()
    mapping["id"] = str(mapping["id"]).upper()
    with pytest.raises(ValueError):
        QuinielaProfile.from_mapping(mapping)

    mapping = profile.to_mapping()
    mapping["id"] = "not-a-uuid"
    with pytest.raises(ValueError):
        QuinielaProfile.from_mapping(mapping)

    mapping = profile.to_mapping()
    mapping["extra"] = True
    with pytest.raises(ValueError):
        QuinielaProfile.from_mapping(mapping)

    mapping = profile.to_mapping()
    del mapping["name"]
    with pytest.raises(ValueError):
        QuinielaProfile.from_mapping(mapping)


def test_schema_versions_require_the_exact_integer_two():
    for invalid_version in (2.0, "2", True, 1):
        mapping = valid_rules_mapping()
        mapping["schema_version"] = invalid_version
        with pytest.raises(ValueError):
            QuinielaRules.from_mapping(mapping)


def test_factory_accepts_rules_mapping_without_mutating_caller_input():
    mapping: dict[str, object] = {
        "schema_version": 2,
        "universe": list(range(100)),
        "display_width": 2,
        "positions": 5,
        "played_positions": [0, 1, 2, 3, 4],
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [{"numerator": prize, "denominator": 1} for prize in (80, 8, 4, 2, 1)],
        "payout_mode": "best",
        "currency": "DOP",
        "scale": 0,
        "minimum_stake": 10,
        "stake_increment": 10,
        "maximum_stake": 10_000,
        "max_coverage": 100,
        "max_exposure": 1_000_000,
    }
    original = deepcopy(mapping)
    profile = create_profile("Quiniela", mapping)
    assert profile.rules.universe == tuple(range(100))
    assert mapping == original


def test_profile_name_is_trimmed_and_limited_by_utf8_bytes():
    rules = QuinielaRules.from_mapping(valid_rules_mapping())
    first = create_profile("  A  ", rules)
    second = create_profile("  A  ", rules)
    assert first.name == "A"
    assert first.id != second.id
    with pytest.raises(ValueError):
        create_profile("é" * 61, rules)


def test_only_json_arrays_and_strict_integer_values_are_accepted():
    mapping = valid_rules_mapping()
    mapping["universe"] = (0, 2, 80)
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(mapping)

    mapping = valid_rules_mapping()
    mapping["played_positions"] = [False, 2]
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(mapping)

    mapping = valid_rules_mapping()
    mapping["multipliers"][0]["unexpected"] = 1
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(mapping)


def test_admission_boundaries_and_repeat_rules_are_explicit():
    smallest = valid_rules_mapping()
    smallest["universe"] = [0, 1]
    smallest["display_width"] = 1
    smallest["positions"] = 1
    smallest["played_positions"] = [0]
    smallest["multipliers"] = [{"numerator": 1, "denominator": 1}]
    smallest["max_coverage"] = 2
    assert QuinielaRules.from_mapping(smallest).universe == (0, 1)

    without_repeats = valid_rules_mapping()
    without_repeats["universe"] = [0, 2]
    without_repeats["max_coverage"] = 2
    without_repeats["allows_repeats"] = False
    with pytest.raises(ValueError):
        QuinielaRules.from_mapping(without_repeats)

    mapping = valid_rules_mapping()
    mapping["played_positions"] = [0, 1]
    mapping["order_matters"] = False
    mapping["multipliers"] = [
        {"numerator": 2, "denominator": 2},
        {"numerator": 1, "denominator": 1},
        {"numerator": 7, "denominator": 2},
    ]
    assert QuinielaRules.from_mapping(mapping).played_positions == (0, 1)
