"""Validation rules for experiment conditions and strategies."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from laboratorio.domain.contracts import (
    COVERAGES,
    GAME,
    MAX_SEED,
    SYSTEMS,
    Conditions,
    ExperimentRequest,
    Strategy,
    normalize_strategy_name,
)

NAME_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "strategy_name_cases.json").read_text(encoding="utf-8")
)


def strategy(**overrides):
    base = {
        "name": "Transición 10",
        "selector": "system",
        "system": "transition",
        "coverage": 10,
        "staking": "bold",
    }
    base.update(overrides)
    return base


def conditions(**overrides):
    base = {
        "start_draw": "2025-09-02 05:10",
        "capital": 2000,
        "goal": 2800,
        "settlement": "all",
        "max_bets": None,
        "max_minutes": None,
        "seed": 7,
    }
    base.update(overrides)
    return base


def test_game_is_the_fixed_quiniela_80_profile():
    assert GAME.numbers == 100
    assert GAME.positions == 5
    assert GAME.prizes == (80, 8, 4, 2, 1)
    assert COVERAGES == (1, 5, 10, 20, 25, 30, 40, 50)
    assert len(SYSTEMS) == 13
    assert "transition" in SYSTEMS and "logistic" not in SYSTEMS


def test_individual_system_strategy_is_valid():
    parsed = Strategy.model_validate(strategy())
    assert parsed.system == "transition" and parsed.components is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"system": "logistic"},
        {"system": None},
        {"coverage": 7},
        {"staking": "martingale"},
        {"name": "   "},
        {"components": [{"system": "cold", "weight": 100}]},
    ],
)
def test_invalid_individual_strategies_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(**overrides))


def test_blend_requires_two_distinct_systems_with_integer_weights_summing_100():
    blend = strategy(
        selector="blend",
        system=None,
        components=[{"system": "transition", "weight": 60}, {"system": "cold", "weight": 40}],
    )
    assert Strategy.model_validate(blend).components[0].weight == 60

    for bad in (
        [{"system": "transition", "weight": 100}],
        [{"system": "transition", "weight": 60}, {"system": "cold", "weight": 30}],
        [{"system": "transition", "weight": 50}, {"system": "transition", "weight": 50}],
        [{"system": "transition", "weight": 0}, {"system": "cold", "weight": 100}],
        [{"system": "random", "weight": 50}, {"system": "cold", "weight": 50}],
    ):
        with pytest.raises(ValidationError):
            Strategy.model_validate(strategy(selector="blend", system=None, components=bad))


def test_parity_only_allows_coverage_50_and_random_uses_standard_coverages():
    assert Strategy.model_validate(strategy(selector="parity", system=None, coverage=50))
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(selector="parity", system=None, coverage=10))
    assert Strategy.model_validate(strategy(selector="random", system=None, coverage=5))
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(selector="random", system="cold", coverage=5))


def test_goal_is_final_balance_and_must_exceed_capital():
    assert Conditions.model_validate(conditions()).goal == 2800
    for bad in ({"goal": 2000}, {"capital": 0}, {"capital": -5}, {"goal": 10**13}):
        with pytest.raises(ValidationError):
            Conditions.model_validate(conditions(**bad))


def test_limits_are_optional_but_positive_when_present():
    parsed = Conditions.model_validate(conditions(max_bets=12, max_minutes=90))
    assert (parsed.max_bets, parsed.max_minutes) == (12, 90)
    for bad in ({"max_bets": 0}, {"max_minutes": 0}, {"max_minutes": -1}):
        with pytest.raises(ValidationError):
            Conditions.model_validate(conditions(**bad))


def test_start_draw_uses_the_historical_label_format():
    with pytest.raises(ValidationError):
        Conditions.model_validate(conditions(start_draw="2025-09-02T05:10"))
    with pytest.raises(ValidationError):
        Conditions.model_validate(conditions(start_draw="2025-13-02 05:10"))


def test_seed_is_bounded_to_the_max_safe_javascript_integer():
    assert MAX_SEED == 2**53 - 1
    assert Conditions.model_validate(conditions(seed=MAX_SEED)).seed == MAX_SEED
    with pytest.raises(ValidationError):
        Conditions.model_validate(conditions(seed=MAX_SEED + 1))
    with pytest.raises(ValidationError):
        Conditions.model_validate(conditions(seed=-1))


def test_experiment_has_one_to_five_uniquely_named_strategies():
    one = {"name": "Prueba", "conditions": conditions(), "strategies": [strategy()]}
    assert len(ExperimentRequest.model_validate(one).strategies) == 1

    many = [strategy(name=f"S{i}") for i in range(6)]
    with pytest.raises(ValidationError):
        ExperimentRequest.model_validate({**one, "strategies": many})
    with pytest.raises(ValidationError):
        ExperimentRequest.model_validate({**one, "strategies": []})
    with pytest.raises(ValidationError):
        ExperimentRequest.model_validate(
            {**one, "strategies": [strategy(name="Igual"), strategy(name=" igual ")]}
        )


def test_duplicate_name_error_is_located_on_the_offending_strategys_name_field():
    one = {
        "name": "Prueba",
        "conditions": conditions(),
        "strategies": [strategy(name="Una"), strategy(name="una")],
    }
    with pytest.raises(ValidationError) as excinfo:
        ExperimentRequest.model_validate(one)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("strategies", 1, "name")


@pytest.mark.parametrize("case", NAME_CASES, ids=[case["category"] for case in NAME_CASES])
def test_strategy_name_normalization_matches_the_shared_fixture(case):
    equal = normalize_strategy_name(case["a"]) == normalize_strategy_name(case["b"])
    assert equal is case["duplicate"]
    one = {
        "name": "Prueba",
        "conditions": conditions(),
        "strategies": [strategy(name=case["a"]), strategy(name=case["b"])],
    }
    if case["duplicate"]:
        with pytest.raises(ValidationError):
            ExperimentRequest.model_validate(one)
    else:
        assert len(ExperimentRequest.model_validate(one).strategies) == 2


def test_names_are_trimmed_and_bounded():
    parsed = Strategy.model_validate(strategy(name="  Fríos  "))
    assert parsed.name == "Fríos"
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(name="x" * 81))


def test_stored_name_uses_the_same_explicit_trim_charset_as_duplicate_detection():
    # U+FEFF and U+0085 are excluded from the shared trim charset on both sides, so the
    # stored name keeps them instead of one side trimming them and the other not.
    assert Strategy.model_validate(strategy(name="\ufeffName")).name == "\ufeffName"
    assert Strategy.model_validate(strategy(name="\x85Name")).name == "\x85Name"
    assert Strategy.model_validate(strategy(name="\tName\t")).name == "Name"


def test_seed_capital_goal_limits_coverage_and_weight_are_strict_integers():
    for bad in (
        conditions(seed="7"),
        conditions(seed=7.0),
        conditions(capital="2000"),
        conditions(capital=2000.0),
        conditions(goal="2800"),
        conditions(goal=2800.0),
        conditions(max_bets="12", max_minutes=None),
        conditions(max_bets=12.0, max_minutes=None),
        conditions(max_minutes="90"),
        conditions(max_minutes=90.0),
    ):
        with pytest.raises(ValidationError):
            Conditions.model_validate(bad)
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(coverage="10"))
    with pytest.raises(ValidationError):
        Strategy.model_validate(strategy(coverage=10.0))
    with pytest.raises(ValidationError):
        Strategy.model_validate(
            strategy(
                selector="blend",
                system=None,
                components=[
                    {"system": "transition", "weight": "60"},
                    {"system": "cold", "weight": 40},
                ],
            )
        )
    with pytest.raises(ValidationError):
        Strategy.model_validate(
            strategy(
                selector="blend",
                system=None,
                components=[
                    {"system": "transition", "weight": 60.0},
                    {"system": "cold", "weight": 40},
                ],
            )
        )
