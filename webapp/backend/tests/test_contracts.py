"""Validation rules for experiment conditions and strategies."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from laboratorio.domain import contracts
from laboratorio.domain.contracts import (
    COVERAGES,
    GAME,
    MAX_MONEY,
    MAX_PROFILE_POSITIONS,
    MAX_PROFILE_SCALE,
    MAX_PROFILE_UNIVERSE,
    MAX_SEED,
    SYSTEMS,
    Conditions,
    ExperimentRequest,
    Game,
    GameProfile,
    Strategy,
    configure_game,
    legacy_quiniela_80_profile,
    make_game,
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


def test_default_game_is_quiniela_80():
    assert GAME.numbers == 100
    assert GAME.positions == 5
    assert GAME.prizes == (80, 8, 4, 2, 1)
    assert GAME.allows_repeats is True
    assert GAME.minimum_stake == 1
    assert COVERAGES == (1, 5, 10, 20, 25, 30, 40, 50)
    assert len(SYSTEMS) == 13
    assert "transition" in SYSTEMS and "logistic" not in SYSTEMS


@pytest.fixture
def restore_game():
    saved = Game(
        GAME.name,
        GAME.numbers,
        GAME.positions,
        GAME.prizes,
        GAME.allows_repeats,
        GAME.minimum_stake,
    )
    yield
    configure_game(saved)


def test_make_game_builds_a_three_position_game():
    game = make_game("Tres", 100, 3, [60, 10, 5], True, 2)
    assert game == Game("Tres", 100, 3, (60, 10, 5), True, 2)
    assert make_game("Q", 10, 1, (9,), False).minimum_stake == 1


@pytest.mark.parametrize(
    "args",
    [
        ("G", 100, 3, (60, 10), True, 1),
        ("G", 3, 4, (4, 3, 2, 1), False, 1),
        ("G", 1, 1, (5,), True, 1),
        ("G", 10, 0, (), True, 1),
        ("G", 10, 2, (5, 0), True, 1),
        ("G", 10, 2, (5, 1), True, 0),
    ],
)
def test_make_game_rejects_inconsistent_rules(args):
    with pytest.raises(ValueError):
        make_game(*args)


def test_configure_game_replaces_the_visible_game(restore_game):
    configure_game(make_game("Tres", 100, 3, [60, 10, 5], True, 5))
    assert contracts.GAME.positions == 3
    assert contracts.GAME.prizes == (60, 10, 5)
    assert contracts.GAME.minimum_stake == 5
    # modules that imported GAME by name see the change too
    assert GAME is contracts.GAME
    assert GAME.name == "Tres"


def profile(**overrides):
    base = {
        "schema_version": 1,
        "profile_id": "example-3",
        "revision": 1,
        "universe_size": 100,
        "positions": 3,
        "allows_repeats": True,
        "multipliers": [{"numerator": n, "denominator": 1} for n in (60, 10, 5)],
        "currency": "DOP",
        "scale": 0,
        "stake_increment": 1,
        "minimum_stake": 1,
        "maximum_stake": 100,
        "max_coverage": 10,
        "max_exposure": 1_000,
        "best_rule": "maximum-payout/v1",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("positions", [1, 3, 5])
def test_new_profiles_admit_explicit_position_counts(positions):
    parsed = GameProfile.model_validate(
        profile(positions=positions, multipliers=[{"numerator": 2, "denominator": 1}] * positions)
    )
    assert len(parsed.multipliers) == positions
    assert GameProfile.model_validate_json(parsed.model_dump_json()) == parsed


def test_new_profiles_allow_other_universes_and_exact_scaled_money():
    parsed = GameProfile.model_validate(
        profile(
            universe_size=7,
            positions=6,
            allows_repeats=False,
            max_coverage=7,
            scale=2,
            stake_increment=2,
            minimum_stake=2,
            maximum_stake=200,
            max_exposure=1_400,
            multipliers=[{"numerator": 3, "denominator": 2}] * 6,
        )
    )
    assert parsed.multipliers[0].numerator == 3
    assert '"minimum_stake":2' in parsed.model_dump_json()
    assert '"scale":2' in parsed.model_dump_json()


def test_profile_requires_every_field_and_rejects_extra_fields():
    for key in profile():
        incomplete = profile()
        incomplete.pop(key)
        with pytest.raises(ValidationError):
            GameProfile.model_validate(incomplete)
    with pytest.raises(ValidationError):
        GameProfile.model_validate(profile(unknown=123))


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("profile_id", "Legacy Profile"),
        ("revision", 0),
        ("revision", 1_000_001),
        ("universe_size", 0),
        ("universe_size", MAX_PROFILE_UNIVERSE + 1),
        ("positions", MAX_PROFILE_POSITIONS + 1),
        ("allows_repeats", 1),
        ("currency", "RD$"),
        ("scale", MAX_PROFILE_SCALE + 1),
        ("stake_increment", 0),
        ("minimum_stake", 0),
        ("maximum_stake", MAX_MONEY + 1),
        ("max_coverage", 0),
        ("max_exposure", MAX_MONEY + 1),
        ("best_rule", "custom"),
        ("universe_size", True),
        ("positions", 3.0),
        ("scale", "0"),
        ("minimum_stake", 1.0),
        ("maximum_stake", True),
        ("max_exposure", float("inf")),
    ],
)
def test_profile_rejects_malformed_scalar_fields(field, bad):
    with pytest.raises(ValidationError):
        GameProfile.model_validate(profile(**{field: bad}))


@pytest.mark.parametrize(
    "changes",
    [
        {"positions": 4},  # multiplier count
        {"positions": 2, "universe_size": 1, "allows_repeats": False},
        {"max_coverage": 101},
        {"minimum_stake": 101},
        {"minimum_stake": 3, "stake_increment": 2},
        {"maximum_stake": 101, "stake_increment": 2},
        {"max_exposure": 9},
        {"maximum_stake": 101, "max_exposure": 100},
        {"max_exposure": 1_000, "multipliers": [{"numerator": MAX_MONEY, "denominator": 1}] * 3},
        {"stake_increment": 1, "multipliers": [{"numerator": 3, "denominator": 2}] * 3},
        {"multipliers": [{"numerator": 1, "denominator": 0}] * 3},
        {"multipliers": [{"numerator": 1.5, "denominator": 1}] * 3},
        {"multipliers": [{"numerator": True, "denominator": 1}] * 3},
        {"multipliers": [{"numerator": 1}] * 3},
        {"multipliers": []},
    ],
)
def test_profile_rejects_inconsistent_or_inexact_terms(changes):
    with pytest.raises(ValidationError):
        GameProfile.model_validate(profile(**changes))


def test_profile_and_nested_multipliers_are_immutable_and_do_not_share_mutable_input():
    raw = profile()
    parsed = GameProfile.model_validate(raw)
    raw["multipliers"][0]["numerator"] = 999
    assert parsed.multipliers[0].numerator == 60
    with pytest.raises(ValidationError):
        parsed.positions = 4
    with pytest.raises(ValidationError):
        parsed.multipliers[0].numerator = 4


def test_legacy_descriptor_is_frozen_stable_and_distinct_from_new_best_rule():
    legacy = legacy_quiniela_80_profile()
    assert (legacy.universe_size, legacy.positions, legacy.allows_repeats) == (
        GAME.numbers,
        GAME.positions,
        GAME.allows_repeats,
    )
    assert tuple(p.numerator for p in legacy.multipliers) == GAME.prizes
    assert (legacy.currency, legacy.scale, legacy.stake_increment, legacy.minimum_stake) == (
        "DOP",
        0,
        1,
        1,
    )
    assert (legacy.best_rule, legacy.max_coverage) == ("first-match/v0", max(COVERAGES))
    assert legacy.maximum_stake <= legacy.max_exposure
    assert GameProfile.model_validate_json(legacy.model_dump_json()) == legacy
    assert legacy_quiniela_80_profile() == legacy
    with pytest.raises(ValidationError):
        GameProfile.model_validate(profile(best_rule="first-match/v0"))
    with pytest.raises(ValidationError):
        GameProfile.model_validate(profile(profile_id="legacy-quiniela-80"))


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
