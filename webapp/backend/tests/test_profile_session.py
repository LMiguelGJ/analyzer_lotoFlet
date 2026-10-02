"""Independent fixtures for the bounded configurable profile session subset."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from laboratorio.domain.contracts import (
    MAX_MONEY,
    GameProfile,
    SettlementMode,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    load_profile_request,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_session import (
    CAPABILITIES,
    MAX_SESSION_ROWS,
    ProfileAudazStaking,
    ProfileConditions,
    ProfileDraw,
    ProfileOutcome,
    ProfileRecoveryLadderStaking,
    ProfileSelector,
    ProfileStaking,
    Q80CyclingStaking,
    run_profile_session,
)

START = "2025-01-01 05:10"


def profile(**changes):
    values = dict(
        schema_version=1,
        profile_id="example-three",
        revision=2,
        universe_size=100,
        positions=3,
        allows_repeats=True,
        multipliers=[{"numerator": n, "denominator": 1} for n in (60, 10, 5)],
        currency="DOP",
        scale=0,
        stake_increment=1,
        minimum_stake=1,
        maximum_stake=100,
        max_coverage=10,
        max_exposure=1000,
        best_rule="maximum-payout/v1",
    )
    values.update(changes)
    return GameProfile.model_validate(values)


def opts(**changes):
    values: dict[str, Any] = dict(
        schema_version=1, start_draw=START, capital=20, goal=100, settlement=SettlementMode.ALL
    )
    values.update(changes)
    return ProfileConditions(**values)


def static(*numbers):
    return ProfileSelector(1, "static-numbers/v1", len(numbers), numbers=tuple(numbers))


def random(k=1, seed=17):
    return ProfileSelector(
        1, "seeded-random/hash-sha256-v1", k, seed=seed, algorithm_version="hash-sha256-v1"
    )


def flat(amount):
    return ProfileStaking(1, "flat-per-number/v1", amount)


def draw(label=START, results=(7, 8, 9), enter=True):
    moment = datetime.strptime(label, "%Y-%m-%d %H:%M")
    minute = (moment - datetime(1970, 1, 1)).days * 1440 + moment.hour * 60 + moment.minute
    return ProfileDraw(1, label, minute, results, enter)


def run(rows, *, p=None, conditions=None, selector=None, staking=None, **kwargs):
    return run_profile_session(
        p or profile(),
        conditions or opts(),
        selector or static(7),
        staking or flat(2),
        rows,
        **kwargs,
    )


def test_one_three_five_and_custom_universe_with_exact_per_number_accounting():
    single = profile(positions=1, multipliers=[{"numerator": 3, "denominator": 1}])
    result = run([draw(results=(7,))], p=single, staking=flat(3))
    assert (result.wagered, result.paid, result.final_balance) == (3, 9, 26)
    assert (result.profile_id, result.profile_revision, result.schema_version) == (
        "example-three",
        2,
        1,
    )
    assert result.bets[0].stakes == ((7, 3),)

    three = run([draw(results=(7, 7, 8))], staking=flat(2))
    best = run(
        [draw(results=(7, 7, 8))], staking=flat(2), conditions=opts(settlement=SettlementMode.BEST)
    )
    assert (three.paid, best.paid) == (140, 120)
    assert (three.final_balance, best.final_balance) == (158, 138)
    assert three.outcome is ProfileOutcome.GOAL

    five = profile(
        universe_size=11,
        positions=5,
        allows_repeats=False,
        multipliers=[{"numerator": n, "denominator": 1} for n in (5, 4, 3, 2, 1)],
    )
    result = run([draw(results=(0, 1, 2, 3, 4))], p=five, selector=static(2, 4), staking=flat(3))
    assert (result.wagered, result.paid, result.final_balance) == (6, 12, 26)
    assert result.bets[0].stakes == ((2, 3), (4, 3))


def test_legacy_best_uses_first_match_via_shared_settlement():
    p = legacy_quiniela_80_profile()
    result = run(
        [draw(results=(7, 7, 8, 7, 8))],
        p=p,
        selector=static(7, 8),
        staking=flat(1),
        conditions=opts(settlement=SettlementMode.BEST),
    )
    assert result.paid == 84 and result.final_balance == 102


def test_explicit_funding_stake_limits_and_no_implicit_one_unit():
    with pytest.raises(ValueError, match="afford"):
        run([draw()], conditions=opts(capital=3, goal=10), selector=static(7, 8), staking=flat(2))
    with pytest.raises(TypeError):
        ProfileStaking.__init__(flat(1), 1, "flat-per-number/v1")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="increment"):
        run([draw()], p=profile(stake_increment=2, minimum_stake=2), staking=flat(3))
    with pytest.raises(ValueError, match="exposure"):
        run(
            [draw()],
            p=profile(max_exposure=10, maximum_stake=10),
            selector=static(0, 1),
            staking=flat(6),
        )
    with pytest.raises(ValueError, match="coverage"):
        run([draw()], p=profile(max_coverage=1), selector=static(0, 1))
    with pytest.raises(ValueError, match="universe"):
        run([draw()], p=profile(universe_size=10), selector=static(10))


def test_static_and_seeded_random_determinism_prefix_and_profile_universe():
    rows = [draw(), draw("2025-01-01 05:15")]
    a = run(rows, selector=random(3))
    b = run(rows, selector=random(3))
    assert a == b
    assert a.bets[0].stakes != a.bets[1].stakes
    short = run(rows, selector=random(1))
    assert [bet.stakes[0][0] for bet in a.bets] == [bet.stakes[0][0] for bet in short.bets]
    other_seed = run(rows, selector=random(3, seed=18))
    assert a.bets[0].stakes != other_seed.bets[0].stakes
    custom = profile(universe_size=7, max_coverage=7)
    full = run([draw(results=(0, 1, 2))], p=custom, selector=random(7), staking=flat(1))
    assert {n for n, _ in full.bets[0].stakes} == set(range(7))
    chosen = run([draw(results=(0, 1, 2))], p=custom, selector=random(1))
    assert chosen.bets[0].stakes[0][0] in range(7)
    with pytest.raises(ValueError, match="algorithm"):
        ProfileSelector(1, "seeded-random/hash-sha256-v1", 1, seed=1)


def test_future_results_do_not_affect_random_selection():
    first = run([draw(results=(1, 2, 3))], selector=random(3))
    second = run([draw(results=(4, 5, 6))], selector=random(3))
    assert first.bets[0].stakes == second.bets[0].stakes


def test_skipped_rows_consume_elapsed_but_not_bet_limit_and_start_is_included():
    rows = [
        draw(),
        draw("2025-01-01 05:15", enter=False),
        draw("2025-01-01 05:20"),
        draw("2025-01-01 05:25"),
    ]
    result = run(rows, selector=static(99), conditions=opts(max_elapsed_draws=3, max_bet_draws=3))
    assert (result.outcome, result.collisions, result.elapsed_draws, result.bet_draws) == (
        ProfileOutcome.LIMIT,
        ("max_elapsed_draws",),
        3,
        2,
    )
    assert [bet.label for bet in result.bets] == [START, "2025-01-01 05:20"]
    assert result.wagered == 4 and result.paid == 0
    assert run(rows, selector=static(99), conditions=opts(max_bet_draws=2)).collisions == (
        "max_bet_draws",
    )


def test_goal_ruin_and_bet_elapsed_collision_priority_after_settlement():
    winning = run(
        [draw(results=(7, 8, 9))], conditions=opts(goal=100, max_bet_draws=1, max_elapsed_draws=1)
    )
    assert winning.outcome is ProfileOutcome.GOAL
    assert winning.collisions == ("goal", "max_bet_draws", "max_elapsed_draws")
    lost = run(
        [draw(results=(1, 2, 3))],
        conditions=opts(capital=2, goal=100, max_bet_draws=1, max_elapsed_draws=1),
    )
    assert (lost.outcome, lost.collisions, lost.final_balance) == (
        ProfileOutcome.RUIN,
        ("ruin", "max_bet_draws", "max_elapsed_draws"),
        0,
    )
    cap = run([draw()], selector=static(99), conditions=opts(max_bet_draws=1, max_elapsed_draws=1))
    assert (cap.outcome, cap.collisions) == (
        ProfileOutcome.LIMIT,
        ("max_bet_draws", "max_elapsed_draws"),
    )


def test_exclusive_time_boundaries_and_collision_exclude_boundary_draw():
    rows = [draw(), draw("2025-01-01 05:15")]
    boundary = rows[1].minute
    result = run(
        rows, selector=static(99), conditions=opts(end_minute=boundary, duration_minutes=5)
    )
    assert result.outcome is ProfileOutcome.LIMIT
    assert result.collisions == ("end_minute", "duration_minutes")
    assert (result.elapsed_draws, result.bet_draws) == (1, 1)
    assert run(
        rows, selector=static(99), conditions=opts(end_minute=boundary + 1, duration_minutes=6)
    ).outcome is (ProfileOutcome.HISTORY_EXHAUSTED)


def test_cancellation_and_history_exhaustion_are_distinct():
    rows = [draw(), draw("2025-01-01 05:15")]
    assert run(rows, cancel_after_elapsed_draws=0).outcome is ProfileOutcome.CANCELLED
    cancelled = run(rows, selector=static(99), cancel_after_elapsed_draws=1)
    assert (cancelled.outcome, cancelled.elapsed_draws, cancelled.bet_draws) == (
        ProfileOutcome.CANCELLED,
        1,
        1,
    )
    exhausted = run(rows, selector=static(99))
    assert exhausted.outcome is ProfileOutcome.HISTORY_EXHAUSTED
    assert exhausted.collisions == () and exhausted.elapsed_draws == 2
    with pytest.raises(FrozenInstanceError):
        exhausted.__setattr__("final_balance", 0)


@pytest.mark.parametrize(
    "change",
    [
        {"start_draw": "2025-01-01 05:1"},
        {"capital": True},
        {"capital": 1.0},
        {"capital": MAX_MONEY + 1},
        {"goal": 20},
        {"settlement": "all"},
        {"max_elapsed_draws": 0},
        {"max_bet_draws": False},
        {"end_minute": True},
        {"end_minute": 0},
        {"duration_minutes": 0},
        {"schema_version": 2},
    ],
)
def test_conditions_reject_implicit_or_malformed_values(change):
    with pytest.raises(ValueError):
        opts(**change)


@pytest.mark.parametrize(
    "invalid",
    [
        lambda: ProfileSelector(1, "static-numbers/v1", 1, numbers=(True,)),
        lambda: ProfileSelector(1, "static-numbers/v1", 2, numbers=(1, 1)),
        lambda: ProfileSelector(1, "static-numbers/v1", 1, numbers=(1.0,)),  # type: ignore[arg-type]
        lambda: ProfileSelector(1, "static-numbers/v1", 1, numbers=(1,), seed=1),
        lambda: ProfileSelector(
            1, "seeded-random/hash-sha256-v1", 1, seed=True, algorithm_version="hash-sha256-v1"
        ),
        lambda: ProfileSelector(1, "system", 1),
        lambda: ProfileStaking(1, "flat-per-number/v1", True),
        lambda: ProfileStaking(1, "flat-per-number/v1", 1.0),  # type: ignore[arg-type]
        lambda: ProfileStaking(1, "ladder", 1),
        lambda: ProfileDraw(1, START, draw().minute + 1, (7, 8, 9), True),
        lambda: ProfileDraw(1, START, draw().minute, (7, 8, 9), 1),  # type: ignore[arg-type]
        lambda: ProfileDraw(1, START, draw().minute, (7, 8, 9.0), True),  # type: ignore[arg-type]
    ],
)
def test_typed_inputs_reject_bool_float_and_unsupported_capabilities(invalid):
    with pytest.raises(ValueError):
        invalid()


def test_capability_registry_retains_pending_families_and_has_no_eval():
    registered = dict(CAPABILITIES)
    assert registered["static-numbers/v1"] == "supported"
    assert registered["seeded-random/hash-sha256-v1"] == "supported"
    assert registered["kelly-binary"] == "pending"
    assert registered["blend"] == "pending"
    assert registered["freq_hist"] == registered["select_interpretable"] == "pending"
    assert registered["timid"] == registered["conditional-entry"] == "pending"
    for kind in ("blend", "parity", "freq_hist", "import-code"):
        with pytest.raises(ValueError, match="unsupported"):
            ProfileSelector(1, kind, 1)


def test_invalid_rows_rejected_even_when_after_terminal_event():
    rows = [draw(), draw("2025-01-01 05:15", results=(7, 8))]
    with pytest.raises(ValueError, match="positions"):
        run(rows, conditions=opts(max_bet_draws=1))
    for bad in ((-1, 1, 2), (100, 1, 2), (True, 1, 2), (1.0, 1, 2)):
        with pytest.raises(ValueError):
            run([draw(results=bad)])
    no_repeats = profile(allows_repeats=False)
    with pytest.raises(ValueError, match="repeat"):
        run([draw(results=(7, 7, 8))], p=no_repeats)
    with pytest.raises(ValueError, match="chronological"):
        run([draw("2025-01-01 05:15"), draw()])
    with pytest.raises(ValueError, match="chronological"):
        run([draw(), draw()])
    with pytest.raises(ValueError, match="start draw"):
        run([draw("2025-01-01 05:15")])
    with pytest.raises(TypeError, match="ProfileDraw"):
        run([draw(), object()])


def test_bounded_rows_no_generator_materialization_and_strict_budget():
    with pytest.raises(TypeError, match="bounded materialized"):
        run(draw() for _ in range(10**9))
    with pytest.raises(ValueError, match="budget"):
        run([draw()] * (MAX_SESSION_ROWS + 1))
    with pytest.raises(ValueError, match="budget"):
        run([draw()], row_budget=0)
    with pytest.raises(ValueError, match="budget"):
        run([draw(), draw("2025-01-01 05:15")], row_budget=1)
    with pytest.raises(ValueError, match="cancel_after"):
        run([draw()], cancel_after_elapsed_draws=True)


def test_mutated_frozen_profile_and_session_models_revalidated():
    p = profile().model_copy(update={"positions": 4})
    with pytest.raises(ValidationError):
        run([draw()], p=p)
    condition = opts()
    object.__setattr__(condition, "capital", True)
    with pytest.raises(ValueError, match="capital"):
        run([draw()], conditions=condition)
    row = draw()
    object.__setattr__(row, "results", (7, True, 9))
    with pytest.raises(ValueError, match="results"):
        run([row])
    with pytest.raises(ValueError):
        replace(flat(2), per_number_stake=2.0)


def q80_rows(*results, enter=True):
    return [
        draw(f"2025-01-01 05:{10 + 5 * i:02d}", values, enter=enter)
        for i, values in enumerate(results)
    ]


def test_private_q80_variant_validates_identity_without_registry_admission():
    assert Q80CyclingStaking() == Q80CyclingStaking(1, "q80-first-prize-cycling/v1")
    for variant in ((2, "q80-first-prize-cycling/v1"), (1, "flat-per-number/v1")):
        with pytest.raises(ValueError):
            Q80CyclingStaking(*variant)
    with pytest.raises(FrozenInstanceError):
        Q80CyclingStaking().__setattr__("capability", "flat-per-number/v1")
    forged = Q80CyclingStaking()
    object.__setattr__(forged, "capability", "flat-per-number/v1")
    with pytest.raises(ValueError, match="policy"):
        run(q80_rows((1, 2, 3, 4, 5)), p=legacy_quiniela_80_profile(), staking=forged)
    with pytest.raises(ValueError, match="unsupported"):
        ProfileStaking(1, "q80-first-prize-cycling/v1", 1)
    p = legacy_quiniela_80_profile()
    request = ProfileExperimentRequest(
        "profile",
        1,
        "Private boundary",
        "a" * 64,
        p.profile_id,
        p.revision,
        profile_sha256(p),
        opts(),
        static(7),
        flat(1),
        "all_rows/v1",
    )
    flat_wire = serialize_profile_request(request)
    assert load_profile_request(flat_wire) == request
    rejected_wire = json.loads(flat_wire)
    rejected_wire["staking"]["capability"] = "q80-first-prize-cycling/v1"
    with pytest.raises(ValueError, match="unsupported"):
        load_profile_request(json.dumps(rejected_wire))
    with pytest.raises(TypeError, match="ProfileStaking"):
        ProfileExperimentRequest(
            "profile",
            1,
            "Private boundary",
            "a" * 64,
            p.profile_id,
            p.revision,
            profile_sha256(p),
            opts(),
            static(7),
            Q80CyclingStaking(),  # type: ignore[arg-type]
            "all_rows/v1",
        )


def test_private_profile_audaz_settles_q80_coverage_fifty_in_all_and_best():
    p = legacy_quiniela_80_profile()
    rows = q80_rows((7, 7, 7, 8, 9), (1, 2, 3, 4, 5))
    selector = static(*range(50))
    all_rows = run(
        rows,
        p=p,
        conditions=opts(capital=2000, goal=2800),
        selector=selector,
        staking=ProfileAudazStaking(),
    )
    best = run(
        rows,
        p=p,
        conditions=opts(capital=2000, goal=2800, settlement=SettlementMode.BEST),
        selector=selector,
        staking=ProfileAudazStaking(),
    )
    assert all_rows.bets[0].stakes[0][1] == best.bets[0].stakes[0][1] == 27
    assert all_rows.bets[0].paid == 27 * 95
    assert best.bets[0].paid == 27 * 83
    assert all_rows.outcome is best.outcome is ProfileOutcome.GOAL
    assert (all_rows.bets[0].balance, best.bets[0].balance) == (
        2000 - 1350 + 27 * 95,
        2000 - 1350 + 27 * 83,
    )


def test_private_profile_audaz_q80_k1_matches_reference_oracle():
    result = run(
        q80_rows((7, 7, 7, 8, 9)),
        p=legacy_quiniela_80_profile(),
        conditions=opts(capital=2000, goal=2800),
        selector=static(7),
        staking=ProfileAudazStaking(),
    )
    assert result.bets[0].stakes == ((7, 11),)
    assert (result.bets[0].wagered, result.bets[0].paid, result.final_balance) == (11, 1012, 3001)
    assert result.outcome is ProfileOutcome.GOAL


def test_private_profile_audaz_is_profile_generic_and_recomputed_after_settlement():
    p = profile(
        universe_size=37,
        positions=1,
        multipliers=[{"numerator": 25, "denominator": 2}],
        scale=1,
        stake_increment=2,
        minimum_stake=2,
        maximum_stake=200,
        max_coverage=10,
        max_exposure=500,
    )
    result = run(
        [draw(results=(7,))],
        p=p,
        conditions=opts(capital=100, goal=200),
        selector=static(7, 8, 9),
        staking=ProfileAudazStaking(),
    )
    assert [bet.stakes[0][1] for bet in result.bets] == [12]
    assert (result.bets[0].wagered, result.bets[0].paid, result.final_balance) == (36, 150, 214)
    assert result.outcome is ProfileOutcome.GOAL


def test_private_profile_audaz_caps_stakes_and_ruins_with_positive_residual():
    p = profile(
        positions=5,
        multipliers=[{"numerator": n, "denominator": 1} for n in (80, 8, 4, 2, 1)],
        max_coverage=50,
        maximum_stake=1_000_000,
        max_exposure=1_000_000,
    )
    capped = run(
        q80_rows((1, 2, 3, 4, 5)),
        p=p,
        conditions=opts(capital=2000, goal=2800),
        selector=static(*range(50)),
        staking=ProfileAudazStaking(),
    )
    assert capped.bets[0].stakes[0][1] == 27
    ruin = run(
        q80_rows((1, 2, 3, 4, 5)),
        p=p,
        conditions=opts(capital=1399, goal=5000),
        selector=static(*range(50, 100)),
        staking=ProfileAudazStaking(),
    )
    assert (ruin.outcome, ruin.final_balance, ruin.bet_draws) == (ProfileOutcome.RUIN, 49, 1)
    # Initial unaffordability is rejected before a run is admitted; only a
    # later unaffordable next stake is represented as a session ruin.
    with pytest.raises(ValueError, match="initial capital cannot afford"):
        run(
            [draw(results=(7, 8, 9))],
            p=profile(minimum_stake=3),
            conditions=opts(capital=2, goal=100),
            selector=static(7),
            staking=ProfileAudazStaking(),
        )


def test_private_profile_audaz_skips_without_staking_and_rejects_negative_margin():
    skipped = run(
        [draw(enter=False), draw("2025-01-01 05:15", enter=False)], staking=ProfileAudazStaking()
    )
    assert (skipped.elapsed_draws, skipped.bet_draws, skipped.final_balance) == (2, 0, 20)
    incompatible = profile(positions=1, multipliers=[{"numerator": 1, "denominator": 1}])
    with pytest.raises(ValueError, match="greater than coverage"):
        run([draw(results=(7,))], p=incompatible, selector=static(7), staking=ProfileAudazStaking())


def test_private_recovery_ladder_q80_parameters_match_cycle_sequence_without_changing_q80():
    p = legacy_quiniela_80_profile()
    rows = [
        draw(
            f"2025-01-01 {5 + (10 + 5 * i) // 60:02d}:{(10 + 5 * i) % 60:02d}",
            (1, 2, 3, 4, 5),
        )
        for i in range(11)
    ]
    kwargs = dict(
        p=p,
        conditions=opts(capital=1_000_000, goal=2_000_000),
        selector=static(*range(50, 100)),
    )
    generic = run(rows, staking=ProfileRecoveryLadderStaking(10, 10, "cycle"), **kwargs)
    historical = run(rows, staking=Q80CyclingStaking(), **kwargs)
    assert generic == historical
    assert [bet.wagered for bet in generic.bets] == [
        50,
        100,
        300,
        800,
        2100,
        5600,
        14950,
        39850,
        106300,
        283450,
        50,
    ]


def test_private_recovery_ladder_binds_settlement_modes_and_result_hit():
    p = legacy_quiniela_80_profile()
    rows = q80_rows((7, 7, 7, 8, 9))
    args = dict(
        p=p,
        selector=static(*range(50)),
        staking=ProfileRecoveryLadderStaking(10, 10, "cycle"),
        conditions=opts(capital=2000, goal=1_000_000),
    )
    all_rows = run(rows, **args)
    best = run(
        rows,
        **{
            **args,
            "conditions": opts(capital=2000, goal=1_000_000, settlement=SettlementMode.BEST),
        },
    )
    assert all_rows.bets[0].paid == 95
    assert best.bets[0].paid == 83
    assert all_rows.bets[0].balance == 2045
    assert best.bets[0].balance == 2033


def test_private_recovery_ladder_secondary_advances_first_hit_resets_and_skip_consumes_only_time():
    p = profile(
        positions=3,
        multipliers=[{"numerator": n, "denominator": 1} for n in (4, 3, 2)],
        max_coverage=3,
        maximum_stake=100,
        max_exposure=1000,
    )
    rows = [
        draw(START, (0, 7, 0)),
        draw("2025-01-01 05:15", (7, 0, 0)),
        draw("2025-01-01 05:20", (0, 7, 0), enter=False),
        draw("2025-01-01 05:25", (0, 7, 0)),
    ]
    result = run(
        rows,
        p=p,
        selector=static(7, 8, 9),
        staking=ProfileRecoveryLadderStaking(10, 2, "cycle"),
        conditions=opts(capital=10_000, goal=20_000),
    )
    assert [(bet.stakes[0][1], bet.paid) for bet in result.bets] == [(10, 30), (40, 160), (10, 30)]
    assert (result.elapsed_draws, result.bet_draws) == (4, 3)


def test_private_recovery_ladder_stop_after_configured_misses_and_terminal_priority():
    p = profile(
        positions=3,
        multipliers=[{"numerator": n, "denominator": 1} for n in (4, 3, 2)],
        max_coverage=3,
        maximum_stake=100,
        max_exposure=1000,
    )
    rows = q80_rows(*([(0, 1, 2)] * 3))
    kwargs = dict(
        p=p,
        selector=static(7, 8, 9),
        staking=ProfileRecoveryLadderStaking(10, 2, "stop"),
        conditions=opts(capital=5000, goal=6000),
    )
    stopped = run(rows, **kwargs)
    assert (stopped.outcome, stopped.collisions, stopped.bet_draws) == (
        ProfileOutcome.LIMIT,
        ("recovery_round_limit",),
        2,
    )
    # A goal reached on the final rung wins priority over configured stop.
    first = run(
        q80_rows((0, 1, 2), (7, 0, 0)),
        **{**kwargs, "conditions": opts(capital=5000, goal=5010)},
    )
    assert first.outcome is ProfileOutcome.GOAL
    with pytest.raises(ValueError, match="initial capital cannot afford"):
        run(
            [draw(results=(0, 1, 2))],
            p=p,
            selector=static(7, 8, 9),
            staking=ProfileRecoveryLadderStaking(10, 2, "cycle"),
            conditions=opts(capital=29, goal=100),
        )


def test_private_recovery_ladder_next_stake_ruin_and_cycle_then_repeat():
    p = profile(
        positions=3,
        multipliers=[{"numerator": n, "denominator": 1} for n in (4, 3, 2)],
        max_coverage=3,
        maximum_stake=100,
        max_exposure=1000,
    )
    rows = q80_rows(*([(0, 1, 2)] * 3))
    result = run(
        rows,
        p=p,
        selector=static(7, 8, 9),
        staking=ProfileRecoveryLadderStaking(10, 2, "cycle"),
        conditions=opts(capital=30, goal=5000),
    )
    assert (result.outcome, result.final_balance, result.bet_draws) == (ProfileOutcome.RUIN, 0, 1)
    with pytest.raises(FrozenInstanceError):
        ProfileRecoveryLadderStaking(10, 2, "cycle").__setattr__("rounds", 4)


def test_private_profile_audaz_staking_remains_outside_v1_request_wire():
    p = legacy_quiniela_80_profile()
    with pytest.raises(ValueError, match="unsupported"):
        ProfileStaking(1, "profile-audaz/v1", 1)
    assert ProfileAudazStaking() == ProfileAudazStaking(1, "profile-audaz/v1")
    with pytest.raises(ValueError):
        ProfileAudazStaking(2, "profile-audaz/v1")
    with pytest.raises(ValueError):
        run(q80_rows((1, 2, 3, 4, 5)), p=p, staking=ProfileAudazStaking(1, "q80-cycling/v1"))


def test_q80_secondary_only_advances_then_first_hit_resets_from_same_draw():
    rows = q80_rows((1, 7, 2, 3, 4), (7, 7, 7, 8, 9), (1, 2, 3, 4, 5))
    result = run(
        rows,
        p=legacy_quiniela_80_profile(),
        conditions=opts(capital=2000, goal=2800),
        selector=static(7, *range(10, 59)),
        staking=Q80CyclingStaking(),
    )
    assert result.outcome is ProfileOutcome.HISTORY_EXHAUSTED
    assert result == run(
        rows,
        p=legacy_quiniela_80_profile(),
        conditions=opts(capital=2000, goal=2800),
        selector=static(7, *range(10, 59)),
        staking=Q80CyclingStaking(),
    )
    assert [(bet.stakes[0][1], bet.wagered, bet.paid, bet.balance) for bet in result.bets] == [
        (1, 50, 8, 1958),
        (2, 100, 184, 2042),  # all: first 80 + two repeated secondary 8 + 4
        (1, 50, 0, 1992),
    ]
    best = run(
        rows,
        p=legacy_quiniela_80_profile(),
        conditions=opts(capital=2000, goal=2800, settlement=SettlementMode.BEST),
        selector=static(7, *range(10, 59)),
        staking=Q80CyclingStaking(),
    )
    assert [(bet.stakes[0][1], bet.paid, bet.balance) for bet in best.bets] == [
        (1, 8, 1958),
        (2, 160, 2018),
        (1, 0, 1968),
    ]


def test_q80_ten_misses_cycle_and_skips_do_not_advance_round():
    rows = [
        draw(
            f"2025-01-01 {5 + (10 + 5 * i) // 60:02d}:{(10 + 5 * i) % 60:02d}",
            (1, 2, 3, 4, 5),
            i != 2,
        )
        for i in range(12)
    ]
    result = run(
        rows,
        p=legacy_quiniela_80_profile(),
        conditions=opts(capital=1_000_000, goal=2_000_000),
        selector=static(*range(50, 100)),
        staking=Q80CyclingStaking(),
    )
    assert result.outcome is ProfileOutcome.HISTORY_EXHAUSTED
    assert (result.elapsed_draws, result.bet_draws) == (12, 11)
    assert [bet.wagered for bet in result.bets] == [
        50,
        100,
        300,
        800,
        2100,
        5600,
        14950,
        39850,
        106300,
        283450,
        50,
    ]
    assert result.final_balance == 546_450


def test_private_reference_audaz_staking_is_distinct_and_settles_q80_k1():
    from laboratorio.domain.profile_staking import (
        ProfileAudazStaking,
        Q80ReferenceAudazStaking,
    )

    profile = legacy_quiniela_80_profile()
    reference = Q80ReferenceAudazStaking()
    assert reference.capability == "transition-1-audaz-reference/v1"
    assert reference.capability != ProfileAudazStaking().capability
    result = run(
        q80_rows((7, 7, 7, 8, 9)),
        p=profile,
        conditions=opts(capital=2_000, goal=2_800),
        selector=static(7),
        staking=reference,
    )
    assert result.bets[0].stakes == ((7, 11),)
    assert (result.bets[0].wagered, result.bets[0].paid, result.final_balance) == (11, 1_012, 3_001)
    assert result.outcome is ProfileOutcome.GOAL
    incompatible = profile.model_copy(
        update={
            "profile_id": "other-q80",
            "best_rule": "maximum-payout/v1",
            "multipliers": (*profile.multipliers[:4], profile.multipliers[0]),
        }
    )
    with pytest.raises(ValueError, match="payouts"):
        run(
            q80_rows((7, 8, 9, 10, 11)),
            p=incompatible,
            conditions=opts(capital=2_000, goal=2_800),
            selector=static(7),
            staking=reference,
        )


def test_q80_admission_checks_whole_ladder_and_initial_affordability():
    base = legacy_quiniela_80_profile().model_copy(
        update={"profile_id": "another-q80", "best_rule": "maximum-payout/v1"}
    )
    row = q80_rows((1, 2, 3, 4, 5))
    kwargs = dict(selector=static(*range(50, 100)), staking=Q80CyclingStaking())
    with pytest.raises(ValueError, match="Q80 positions"):
        run(row, p=profile(max_coverage=50), **kwargs)
    with pytest.raises(ValueError, match="maximum stake"):
        capped = base.model_copy(update={"maximum_stake": 5668})
        run(row, p=capped, **kwargs)
    with pytest.raises(ValueError, match="exposure"):
        capped = base.model_copy(update={"max_exposure": 283449})
        run(row, p=capped, **kwargs)
    with pytest.raises(ValueError, match="afford"):
        run(row, p=base, conditions=opts(capital=49, goal=100), **kwargs)


def test_q80_next_stake_ruin_with_positive_residual_and_goal_limit_priority():
    p = legacy_quiniela_80_profile()
    rows = q80_rows((1, 2, 3, 4, 5), (1, 2, 3, 4, 5))
    kwargs = dict(p=p, selector=static(*range(50, 100)), staking=Q80CyclingStaking())
    ruin = run(
        rows, conditions=opts(capital=99, goal=500, max_bet_draws=1, max_elapsed_draws=1), **kwargs
    )
    assert (ruin.outcome, ruin.collisions, ruin.final_balance, ruin.bet_draws) == (
        ProfileOutcome.RUIN,
        ("ruin", "max_bet_draws", "max_elapsed_draws"),
        49,
        1,
    )
    goal = run(
        q80_rows((50, 1, 2, 3, 4)),
        conditions=opts(capital=50, goal=80, max_bet_draws=1, max_elapsed_draws=1),
        **kwargs,
    )
    assert (goal.outcome, goal.collisions, goal.final_balance) == (
        ProfileOutcome.GOAL,
        ("goal", "max_bet_draws", "max_elapsed_draws"),
        80,
    )
    skipped = run(
        [draw(START, (1, 2, 3, 4, 5), False), *q80_rows((1, 2, 3, 4, 5))[1:]],
        conditions=opts(capital=99, goal=500, max_elapsed_draws=1),
        **kwargs,
    )
    assert (skipped.outcome, skipped.bet_draws, skipped.final_balance) == (
        ProfileOutcome.LIMIT,
        0,
        99,
    )


def test_q80_time_limits_cancellation_and_censored_history():
    p = legacy_quiniela_80_profile()
    rows = q80_rows((1, 2, 3, 4, 5), (1, 2, 3, 4, 5))
    kwargs = dict(
        p=p,
        selector=static(7),
        staking=Q80CyclingStaking(),
        conditions=opts(capital=200, goal=1000),
    )
    censored = run(rows, **kwargs)
    assert (censored.outcome, censored.collisions, censored.bet_draws) == (
        ProfileOutcome.HISTORY_EXHAUSTED,
        (),
        2,
    )
    cancelled = run(rows, cancel_after_elapsed_draws=1, **kwargs)
    assert (cancelled.outcome, cancelled.collisions, cancelled.bet_draws) == (
        ProfileOutcome.CANCELLED,
        (),
        1,
    )
    boundary = run(
        rows,
        conditions=opts(capital=200, goal=1000, end_minute=rows[1].minute, duration_minutes=5),
        p=p,
        selector=static(7),
        staking=Q80CyclingStaking(),
    )
    assert (boundary.outcome, boundary.collisions, boundary.bet_draws) == (
        ProfileOutcome.LIMIT,
        ("end_minute", "duration_minutes"),
        1,
    )


def test_q80_seeded_selection_and_draw_binding_are_deterministic():
    p = legacy_quiniela_80_profile()
    selection = random(1, seed=17)
    first = run(
        q80_rows((1, 2, 3, 4, 5)),
        p=p,
        selector=selection,
        staking=Q80CyclingStaking(),
        conditions=opts(capital=200, goal=1000),
    )
    number = first.bets[0].stakes[0][0]
    miss = next(n for n in range(100) if n != number)
    rows = q80_rows((miss, number, number, number, number), (number, miss, miss, miss, miss))
    a = run(
        rows,
        p=p,
        selector=selection,
        staking=Q80CyclingStaking(),
        conditions=opts(capital=200, goal=1000),
    )
    b = run(
        rows,
        p=p,
        selector=selection,
        staking=Q80CyclingStaking(),
        conditions=opts(capital=200, goal=1000),
    )
    assert a == b
    assert a.bets[0].stakes == first.bets[0].stakes
    assert a.bets[0].paid == 15  # selected number repeated in secondary positions
    # The second draw selects from its own label, not from the first draw's result.
    second_number = b.bets[1].stakes[0][0]
    assert b.bets[1].paid == (80 if second_number == number else 0)
    assert b.bets[1].stakes[0][1] == 1  # secondary only did not reset the round, k=1 rungs equal


def test_total_money_ceiling_after_multiple_draws():
    p = profile(
        multipliers=[{"numerator": 1, "denominator": 1}] * 3, maximum_stake=1, max_exposure=10
    )
    # A single bet cannot overflow; reject an unavailable goal beyond the safe ceiling.
    with pytest.raises(ValueError, match="goal"):
        opts(capital=MAX_MONEY, goal=MAX_MONEY + 1)
    result = run(
        [draw(), draw("2025-01-01 05:15")],
        p=p,
        conditions=opts(capital=MAX_MONEY - 2, goal=MAX_MONEY),
        staking=flat(1),
    )
    assert result.wagered == result.paid == 2
    overflow = profile(
        multipliers=[{"numerator": 3, "denominator": 1}] + [{"numerator": 0, "denominator": 1}] * 2,
        maximum_stake=1,
        max_exposure=10,
    )
    with pytest.raises(ValueError, match="session totals"):
        run(
            [draw()],
            p=overflow,
            conditions=opts(capital=MAX_MONEY - 1, goal=MAX_MONEY),
            staking=flat(1),
        )
