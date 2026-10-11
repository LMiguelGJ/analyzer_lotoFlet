"""Behavior and characterization tests for the consecutive-session run engine."""

import hashlib
import random
import time
from dataclasses import replace

import pytest

from laboratorio.domain.runs import (
    MAX_COVERAGE,
    MAX_POSITIONS,
    NUMBERS,
    OUTCOME_GOAL,
    OUTCOME_INCOMPLETE,
    OUTCOME_LIMIT,
    OUTCOME_RUIN,
    RunConfig,
    RunResult,
    _ratio,
    run_sessions,
)
from laboratorio.domain.selection import parity_numbers
from laboratorio.domain.session import Bet, Draw
from laboratorio.engine.adapter import open_lab_data
from laboratorio.settings import Settings

HIT = (7, 50, 51, 52, 53)
MISS = (90, 50, 51, 52, 53)
ORDER = (7, 8)


def config(**overrides):
    values = {
        "capital": 10,
        "goal": 20,
        "coverage": 2,
        "positions": 1,
        "prizes": (5,),
        "minimum_stake": 1,
    }
    values.update(overrides)
    return RunConfig(**values)


def row(index, results=MISS, order=ORDER):
    return Draw(f"d{index}", index, results, order)


def rows_from(results_list, order=ORDER):
    return [row(i, results, order) for i, results in enumerate(results_list)]


# --------------------------------------------------------------------------- constants


def test_constants():
    assert (OUTCOME_GOAL, OUTCOME_RUIN, OUTCOME_LIMIT, OUTCOME_INCOMPLETE) == (
        "goal",
        "ruin",
        "limit",
        "incomplete",
    )
    assert (NUMBERS, MAX_POSITIONS, MAX_COVERAGE) == (100, 5, 50)


# --------------------------------------------------------------------------- validation


def test_valid_config_builds():
    built = config(max_draws=3)
    assert built.max_draws == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"capital": 0, "goal": 5},
        {"goal": 10},
        {"goal": 9},
        {"coverage": 0},
        {"coverage": 51, "capital": 1000, "goal": 2000},
        {"positions": 0, "prizes": ()},
        {"positions": 6, "prizes": (1, 1, 1, 1, 1, 1)},
        {"positions": 2, "prizes": (5,)},
        {"prizes": (0,)},
        {"prizes": (-3,)},
        {"minimum_stake": 0},
        {"capital": 3, "goal": 10, "minimum_stake": 2},
        {"capital": 9, "goal": 20, "minimum_stake": 5},
        {"max_draws": 0},
        {"max_draws": -1},
    ],
)
def test_invalid_config_rejected(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"capital": True},
        {"goal": True, "capital": 0},
        {"coverage": True, "capital": 5},
        {"positions": True, "prizes": (5,)},
        {"prizes": (True,)},
        {"minimum_stake": True},
        {"max_draws": True},
        {"capital": 10.0},
        {"coverage": 2.0},
        {"max_draws": 3.0},
    ],
)
def test_non_int_config_rejected(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_affordable_first_bet_boundary():
    assert config(capital=6, goal=7, coverage=3, minimum_stake=2).capital == 6
    with pytest.raises(ValueError):
        config(capital=5, goal=7, coverage=3, minimum_stake=2)


# --------------------------------------------------------------------------- outcomes


def test_goal_session():
    result = run_sessions(config(), rows_from([HIT] * 4))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_GOAL
    assert (session.ordinal, session.start_index, session.end_index) == (1, 0, 3)
    assert session.draws == 4
    assert session.final_balance == 22
    assert (session.wagered, session.paid) == (8, 20)
    assert [bet.balance for bet in session.bets] == [13, 16, 19, 22]
    assert result.totals.goal == 1
    assert result.draws == result.ranked_draws == 4


def test_bet_fields():
    result = run_sessions(config(), rows_from([HIT]))
    (bet,) = result.sessions[0].bets
    assert bet == Bet("d0", (7, 8), 1, 2, (7,), 5, 13)


def test_ruin_when_next_bet_unaffordable():
    result = run_sessions(config(capital=5, goal=100), rows_from([MISS, MISS]))
    session = result.sessions[0]
    assert session.outcome == OUTCOME_RUIN
    assert session.draws == 2
    assert session.final_balance == 1
    assert [bet.balance for bet in session.bets] == [3, 1]


def test_exactly_affordable_next_bet_keeps_playing():
    result = run_sessions(config(capital=4, goal=100), rows_from([MISS, MISS]))
    session = result.sessions[0]
    assert [bet.balance for bet in session.bets] == [2, 0]
    assert session.outcome == OUTCOME_RUIN
    # balance 2 after the first miss equals the cost of the next bet: still playable.
    assert session.draws == 2


def test_limit_session():
    result = run_sessions(config(goal=100, max_draws=3), rows_from([MISS] * 5))
    first = result.sessions[0]
    assert first.outcome == OUTCOME_LIMIT
    assert first.draws == 3
    assert first.final_balance == 4
    assert result.sessions[1].start_index == 3


def test_limit_counts_unranked_draws():
    rows = [row(0), row(1, order=None), row(2, order=None), row(3)]
    result = run_sessions(config(goal=100, max_draws=3), rows)
    first = result.sessions[0]
    assert first.outcome == OUTCOME_LIMIT
    assert (first.start_index, first.end_index, first.draws) == (0, 2, 3)
    assert len(first.bets) == 1
    assert first.final_balance == 8


def test_limit_closing_on_unranked_row_after_bet():
    # Limit is only reachable on an unranked row here, so the check applies to it too.
    rows = [row(0, HIT), row(1, order=None)]
    result = run_sessions(config(goal=100, max_draws=2), rows)
    assert result.sessions[0].outcome == OUTCOME_LIMIT
    assert result.sessions[0].end_index == 1


def test_goal_beats_limit_on_same_draw():
    result = run_sessions(config(goal=13, max_draws=1), rows_from([HIT]))
    assert result.sessions[0].outcome == OUTCOME_GOAL


def test_ruin_beats_limit_on_same_draw():
    result = run_sessions(config(capital=3, goal=100, max_draws=1), rows_from([MISS]))
    assert result.sessions[0].outcome == OUTCOME_RUIN


def test_no_limit_means_sessions_run_until_rows_end():
    result = run_sessions(config(goal=1000), rows_from([MISS, HIT] * 3))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE


# --------------------------------------------------------------------------- chaining


def test_restart_with_fresh_capital_and_chained_ordinals():
    rows = rows_from([MISS] * 5)
    result = run_sessions(config(capital=5, goal=100), rows)
    assert [s.ordinal for s in result.sessions] == [1, 2, 3]
    assert [s.outcome for s in result.sessions] == [OUTCOME_RUIN, OUTCOME_RUIN, OUTCOME_INCOMPLETE]
    assert [(s.start_index, s.end_index) for s in result.sessions] == [(0, 1), (2, 3), (4, 4)]
    # Every session begins from the initial capital again.
    assert [s.bets[0].balance for s in result.sessions] == [3, 3, 3]
    assert [s.final_balance for s in result.sessions] == [1, 1, 3]


def test_leading_unranked_rows_belong_to_no_session():
    rows = [row(0, order=None), row(1, order=None), row(2), row(3)]
    result = run_sessions(config(capital=5, goal=100), rows)
    first = result.sessions[0]
    assert first.start_index == 2
    assert first.draws == 2
    assert result.draws == 4
    assert result.ranked_draws == 2


def test_unranked_rows_between_sessions_are_skipped():
    rows = [row(0), row(1), row(2, order=None), row(3, order=None), row(4), row(5)]
    result = run_sessions(config(capital=5, goal=100), rows)
    first, second = result.sessions
    assert (first.outcome, first.start_index, first.end_index) == (OUTCOME_RUIN, 0, 1)
    assert (second.start_index, second.end_index, second.draws) == (4, 5, 2)
    assert second.outcome == OUTCOME_RUIN


def test_unranked_rows_inside_session_count_as_elapsed_but_do_not_bet():
    rows = [row(0), row(1, order=None), row(2)]
    result = run_sessions(config(capital=5, goal=100), rows)
    (session,) = result.sessions
    assert session.outcome == OUTCOME_RUIN
    assert session.draws == 3
    assert len(session.bets) == 2
    assert (session.start_index, session.end_index) == (0, 2)


def test_incomplete_tail_has_a_bet_and_stops_the_chain():
    result = run_sessions(config(goal=100), rows_from([MISS, HIT]))
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE
    assert len(session.bets) == 2
    assert result.totals.incomplete == 1
    assert result.totals.mean_net_closed is None


def test_trailing_unranked_rows_do_not_open_a_session():
    rows = [row(0, HIT), row(1, HIT), row(2, order=None)]
    result = run_sessions(config(goal=100), rows)
    (session,) = result.sessions
    assert session.outcome == OUTCOME_INCOMPLETE
    assert session.draws == 3


def test_no_ranked_rows_gives_no_sessions():
    result = run_sessions(config(), [row(0, order=None), row(1, order=None)])
    assert result.sessions == ()
    totals = result.totals
    assert (totals.sessions, totals.bets, totals.wagered, totals.paid, totals.net) == (0,) * 5
    assert totals.return_pct is None
    assert totals.mean_net_closed is None
    assert (result.draws, result.ranked_draws) == (2, 0)


def test_empty_rows():
    result = run_sessions(config(), [])
    assert result == RunResult(sessions=(), totals=result.totals, draws=0, ranked_draws=0)
    assert result.totals.sessions == 0


# --------------------------------------------------------------------------- payouts


def test_three_positions_hand_computed_with_repeated_number():
    cfg = RunConfig(
        capital=100,
        goal=1000,
        coverage=3,
        positions=3,
        prizes=(60, 10, 5),
        minimum_stake=2,
    )
    # Order picks 9, 4, 11. Results: 9 first and third (pays twice), 4 second, 50 uncovered;
    # the fifth result (11) is covered but lies beyond the three positions in play.
    draw = Draw("x", 0, (9, 4, 9, 50, 11), (9, 4, 11, 30))
    result = run_sessions(cfg, [draw])
    (session,) = result.sessions
    (bet,) = session.bets
    assert bet.numbers == (9, 4, 11)
    assert bet.per_number == 2
    assert bet.wagered == 6
    assert bet.results == (9, 4, 9)
    assert bet.paid == 2 * 60 + 2 * 10 + 2 * 5 == 150
    assert bet.balance == 100 + 150 - 6 == 244
    assert session.outcome == OUTCOME_INCOMPLETE


def test_positions_use_only_the_first_results():
    cfg = config(positions=1, prizes=(5,))
    # Only the first result counts: the covered 7 sits in the second slot.
    draw = Draw("x", 0, (90, 7, 7, 7, 7), ORDER)
    (bet,) = run_sessions(cfg, [draw]).sessions[0].bets
    assert bet.paid == 0
    assert bet.results == (90,)


def test_prize_by_position_not_by_number():
    cfg = config(positions=2, prizes=(50, 3))
    draw = Draw("x", 0, (90, 7, 7, 7, 7), ORDER)
    (bet,) = run_sessions(cfg, [draw]).sessions[0].bets
    assert bet.paid == 3


# --------------------------------------------------------------------------- totals


def test_totals_hand_computed():
    result = run_sessions(config(capital=5, goal=100), rows_from([MISS] * 5))
    totals = result.totals
    assert totals.sessions == 3
    assert (totals.goal, totals.ruin, totals.limit, totals.incomplete) == (0, 2, 0, 1)
    assert totals.bets == 5
    assert totals.wagered == 10
    assert totals.paid == 0
    assert totals.net == -10
    assert totals.return_pct == -100.0
    assert totals.mean_net_closed == -4.0


def test_return_pct_rounding():
    # hit (+5), miss, miss: wagered 6 (3 bets x 2), paid 5.
    cfg = config(goal=1000)
    result = run_sessions(cfg, rows_from([HIT, MISS, MISS]))
    assert result.totals.wagered == 6
    assert result.totals.paid == 5
    assert result.totals.net == -1
    assert result.totals.return_pct == -16.7


def test_ratio_rounds_half_up_away_from_zero():
    assert _ratio(1, 4) == 0.3
    assert _ratio(-1, 4) == -0.3
    assert _ratio(1, 3) == 0.3
    assert _ratio(7, 2) == 3.5
    assert _ratio(-1572, 1) == -1572.0


def test_mean_net_closed_excludes_incomplete_tail():
    # Ruin (net -4), goal (net +6), then an incomplete tail that is ignored by the mean.
    rows = rows_from([MISS, MISS, HIT, HIT, MISS])
    result = run_sessions(config(capital=5, goal=11), rows)
    assert [s.outcome for s in result.sessions] == [OUTCOME_RUIN, OUTCOME_GOAL, OUTCOME_INCOMPLETE]
    assert result.totals.mean_net_closed == 1.0


def _random_rows(seed, count, unranked_share, coverage=50):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        results = tuple(rng.randrange(100) for _ in range(5))
        order = None if rng.random() < unranked_share else tuple(rng.sample(range(100), coverage))
        rows.append(Draw(f"r{index}", index, results, order))
    return rows


def test_totals_reconcile():
    rows = _random_rows(7, 500, 0.3)
    cfg = RunConfig(
        capital=60,
        goal=90,
        coverage=10,
        positions=5,
        prizes=(80, 8, 4, 2, 1),
        minimum_stake=1,
        max_draws=8,
    )
    result = run_sessions(cfg, rows)
    totals = result.totals
    assert totals.sessions == len(result.sessions) > 3
    assert totals.sessions == totals.goal + totals.ruin + totals.limit + totals.incomplete
    assert sum(s.paid - s.wagered for s in result.sessions) == totals.net
    assert sum(s.wagered for s in result.sessions) == totals.wagered
    assert sum(s.paid for s in result.sessions) == totals.paid
    assert sum(len(s.bets) for s in result.sessions) == totals.bets
    for session in result.sessions:
        assert session.wagered == sum(bet.wagered for bet in session.bets)
        assert session.paid == sum(bet.paid for bet in session.bets)
        assert session.final_balance == cfg.capital + session.paid - session.wagered
        assert session.draws == session.end_index - session.start_index + 1
    ordinals = [s.ordinal for s in result.sessions]
    assert ordinals == list(range(1, len(ordinals) + 1))
    for earlier, later in zip(result.sessions, result.sessions[1:], strict=False):
        assert later.start_index > earlier.end_index
    assert {s.outcome for s in result.sessions} >= {OUTCOME_LIMIT}


def test_determinism():
    rows = _random_rows(11, 300, 0.3)
    cfg = RunConfig(
        capital=50,
        goal=80,
        coverage=10,
        positions=3,
        prizes=(60, 10, 5),
        minimum_stake=1,
        max_draws=25,
    )
    assert run_sessions(cfg, rows) == run_sessions(cfg, list(rows))


def test_accepts_any_iterable_of_rows():
    rows = rows_from([HIT] * 4)
    assert run_sessions(config(), iter(rows)) == run_sessions(config(), rows)


# --------------------------------------------------------------------------- invalid rows


@pytest.mark.parametrize(
    "bad",
    [
        "not a draw",
        Draw("a", 0, (1, 2, 3, 4), ORDER),
        Draw("a", 0, (1, 2, 3, 4, 100), ORDER),
        Draw("a", 0, (1, 2, 3, 4, -1), ORDER),
        Draw("a", 0, (1, 2, 3, 4, True), ORDER),
        Draw("a", 0, (1, 2, 3, 4, 5), (7,)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, 7)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, 100)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, -1)),
        Draw("a", 0, (1, 2, 3, 4, 5), (7, True)),
    ],
)
def test_invalid_rows_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        run_sessions(config(), [bad])


def test_non_chronological_rows_rejected():
    with pytest.raises(ValueError):
        run_sessions(config(), [row(1), row(1)])
    with pytest.raises(ValueError):
        run_sessions(config(), [row(2), row(1)])


def test_config_type_enforced():
    with pytest.raises(TypeError):
        run_sessions("config", [])  # type: ignore[arg-type]


# --------------------------------------------------------------------------- performance


def test_large_input_is_fast():
    rng = random.Random(5)
    base = tuple(range(10))
    rows = []
    for index in range(65_000):
        results = tuple(rng.randrange(100) for _ in range(5))
        rows.append(Draw("p", index, results, base))
    cfg = RunConfig(
        capital=100, goal=200, coverage=10, positions=5, prizes=(80, 8, 4, 2, 1), minimum_stake=1
    )
    started = time.perf_counter()
    result = run_sessions(cfg, rows)
    assert time.perf_counter() - started < 3.0
    assert result.totals.sessions > 0


# --------------------------------------------------------------------------- characterization

# Expected values below were frozen on 2026-10-10 (base commit 704a02d) from the legacy flat
# engine before its retirement. Per session: (outcome, final_balance, bets, wagered, paid,
# digest) where digest is the first 32 hex chars of a SHA-256 over every bet's
# (label, numbers, wagered, paid, balance, per_number).
FROZEN_SYNTHETIC = {
    (50, 200, 400): {
        "bets": 426,
        "wagered": 21300,
        "paid": 22352,
        "goal": 12,
        "ruin": 10,
        "incomplete": 1,
        "sessions": (
            ("ruin", 42, 15, 750, 592, "e19e49c2e3a85fe7da8efe20ce2b51db"),
            ("ruin", 14, 19, 950, 764, "573dd677b14d724b0c75ff54c3682b1c"),
            ("goal", 427, 6, 300, 527, "1fd14354c2dca4445d6074d670c7e777"),
            ("ruin", 23, 12, 600, 423, "f463681deaa013f0814ea37d261f39d2"),
            ("ruin", 41, 11, 550, 391, "07f40f19e636a5a6e6f573b767dcfae3"),
            ("ruin", 34, 4, 200, 34, "b6357c57572281fd5fb613417957f5cf"),
            ("goal", 434, 24, 1200, 1434, "a5e247983f8e5c1c7ef7cf0cd961afd9"),
            ("ruin", 36, 6, 300, 136, "8849b247d68e6f98c4b2282cffe92f24"),
            ("ruin", 40, 4, 200, 40, "69d274612b3fec93e2e8e631c1fb8578"),
            ("goal", 417, 28, 1400, 1617, "f3bbe627a60448d01a095c82fee1e9ad"),
            ("ruin", 17, 12, 600, 417, "aa5b6b9ab1dc896a8c52e72f3d6eccf8"),
            ("goal", 416, 61, 3050, 3266, "899370ff19f3814d8a99bd1c64beba3c"),
            ("goal", 420, 30, 1500, 1720, "8aaa90d2ea670b66c7c886c2a1e32973"),
            ("goal", 404, 30, 1500, 1704, "4d3e1c1581d19f33880162321b0e61b1"),
            ("goal", 423, 40, 2000, 2223, "2428fd3368ed828d18d777ef4cc2e832"),
            ("ruin", 33, 10, 500, 333, "d98b4681209d0432b5f060930f2ab6ed"),
            ("goal", 425, 18, 900, 1125, "8ae2048d3f44242d43f1154b52790c48"),
            ("goal", 431, 10, 500, 731, "29a087550d168d2ee98af856790986ef"),
            ("goal", 426, 42, 2100, 2326, "7a86d6c61dda5d159331c030609775b8"),
            ("goal", 431, 11, 550, 781, "f0a69e3281132dd6393b8ffda9647ba7"),
            ("ruin", 46, 15, 750, 596, "d046d0077dc17ea63e7612c8a477f053"),
            ("goal", 421, 12, 600, 821, "21bc6442b75972d3a5db04f5ab93c363"),
            ("incomplete", 251, 6, 300, 351, "92a17448b9c91ce46257e959783040b6"),
        ),
    },
    (10, 30, 60): {
        "bets": 426,
        "wagered": 4260,
        "paid": 3422,
        "goal": 34,
        "ruin": 107,
        "incomplete": 1,
        "sessions": (
            ("ruin", 0, 4, 40, 10, "457103543eb0efe87e0ed4c78617a142"),
            ("ruin", 0, 3, 30, 0, "d07d973f66d9d30401e4ac07794707bc"),
            ("ruin", 8, 4, 40, 18, "3815c57ce3b6e09840d711351039641e"),
            ("ruin", 4, 3, 30, 4, "5bc79f8d052b6b30b0f650a49ccd0c72"),
            ("ruin", 0, 3, 30, 0, "2e28e2b10aced72a7a8584e687caade7"),
            ("ruin", 8, 3, 30, 8, "af868730ab9e31cfae9f28a0b2aae166"),
            ("goal", 84, 3, 30, 84, "59f89dbdcbfe15594fecc2833b38a26c"),
            ("goal", 100, 1, 10, 80, "aec37139203dc5009f90d2dc5c506e3a"),
            ("ruin", 2, 3, 30, 2, "894faa64dffa21d8aff75cdcaaf09b63"),
            ("ruin", 0, 3, 30, 0, "3e1eb68f184b63cfa83f86cd3f5bf11b"),
            ("ruin", 1, 3, 30, 1, "68ba246143d7824a631be965a88965c5"),
            ("ruin", 2, 3, 30, 2, "a47cf94525cddb3d3354d04804f3d4e8"),
            ("ruin", 0, 3, 30, 0, "2e448f30d02f480a16df332c0987c345"),
            ("goal", 81, 3, 30, 81, "00c57afb670d2d8bd084d53619fe96ba"),
            ("ruin", 8, 3, 30, 8, "2ba91592e9081403b8d3ad181e3ea7bf"),
            ("ruin", 6, 4, 40, 16, "c013a50e48e28bd9c9868509d34d3f43"),
            ("ruin", 2, 3, 30, 2, "cc6424eae1673c038caac97a82453be8"),
            ("goal", 90, 2, 20, 80, "efc8d0241f0bfe35a5d3a3f25121e4de"),
            ("ruin", 8, 3, 30, 8, "40c5fd279d9620b8b2fe8a6b042c0a2c"),
            ("ruin", 5, 4, 40, 15, "cb1aae53a74a94e6b9d96948342d56fd"),
            ("ruin", 6, 4, 40, 16, "573bc3a65bc1b9fc3fe3a007c3261c68"),
            ("ruin", 0, 3, 30, 0, "65e05c4a5d891a9c149cb5651e5c9d56"),
            ("ruin", 2, 4, 40, 12, "437c90f97b82e9434df49b7ab5c75bd1"),
            ("goal", 94, 2, 20, 84, "27c574dc4783457f781a8b4f2cb11d89"),
            ("ruin", 1, 3, 30, 1, "24457365b4fcdff3fb5ce17814116e2f"),
            ("goal", 100, 1, 10, 80, "e7ec259200350a67e1a7b813b501f802"),
            ("ruin", 3, 3, 30, 3, "720512a4deee9af4efa14102015489ff"),
            ("goal", 81, 3, 30, 81, "1ee95b356baa4ef5205a7e6216e9549e"),
            ("ruin", 1, 4, 40, 11, "32d2c7f42e736c27eb01cea2ecf0a87c"),
            ("goal", 90, 2, 20, 80, "90fcbd91873664e96dae7dcae06255a3"),
            ("ruin", 9, 3, 30, 9, "aec09009beeff8c81f9f89876602af8b"),
            ("ruin", 9, 3, 30, 9, "506ef23eed91124aeddefd90fd4dae2a"),
            ("ruin", 0, 4, 40, 10, "f53a051475b75a5f20688cccd864e081"),
            ("ruin", 4, 3, 30, 4, "44c8ea6add85271ea4212a5cf55528a7"),
            ("ruin", 4, 3, 30, 4, "4bae023f11ebc838229c46214ed20809"),
            ("goal", 81, 3, 30, 81, "c838e72c502a927025e390d3185baa45"),
            ("ruin", 0, 3, 30, 0, "de6cf01c56a70b3e8df521c64180b1bf"),
            ("ruin", 4, 3, 30, 4, "ff0717b4e17c11f946987ef1cf7b0879"),
            ("ruin", 2, 3, 30, 2, "fabf51482d0a4430b5df0dcef90d80c9"),
            ("ruin", 5, 3, 30, 5, "3894b5db3fe5327989ef403a3a4777bb"),
            ("ruin", 5, 3, 30, 5, "73cff90d74040386736e2d08ea9ed840"),
            ("goal", 90, 2, 20, 80, "6e4032ddc83189995fbb500d29ab347f"),
            ("ruin", 8, 3, 30, 8, "976f85cc46722c95b876d7bfa457f8b8"),
            ("ruin", 1, 4, 40, 11, "e02c6a47b622e114199154155715ef34"),
            ("ruin", 1, 4, 40, 11, "701883d1472e7f8365851d147a53f08d"),
            ("ruin", 1, 4, 40, 11, "a8a68212f517da46bda9e958add16655"),
            ("ruin", 0, 4, 40, 10, "18e0f2922cb6a5c5e926583cd86bd27f"),
            ("goal", 81, 3, 30, 81, "f326d403bba3dc503c5d21d9045606ab"),
            ("ruin", 4, 3, 30, 4, "b8336ddebe321f0474b3bc63f3f8061a"),
            ("ruin", 2, 4, 40, 12, "62399213cfba8984f4380fa0abdab434"),
            ("ruin", 0, 3, 30, 0, "13cd4a61c8b04c636998ef0473915e81"),
            ("ruin", 0, 6, 60, 30, "926991d78c86249c872bf3c720ce6ea6"),
            ("ruin", 0, 3, 30, 0, "775941a87575aca6657d1d944a9518bb"),
            ("ruin", 4, 3, 30, 4, "765109f4ff29ea12aa34bd06cc19df45"),
            ("ruin", 1, 3, 30, 1, "fe69adf99f4dcba27c7f9a959b2c9638"),
            ("goal", 80, 3, 30, 80, "288659ad91f227f388574dff1b344f2d"),
            ("goal", 90, 2, 20, 80, "2be7a021402c1d5001d7a06287f5af8a"),
            ("ruin", 2, 3, 30, 2, "f36bd1b6c2fec911df3ab808e662b0b4"),
            ("goal", 89, 3, 30, 89, "d77a6538d73683b2503f5bbdebf88536"),
            ("goal", 84, 3, 30, 84, "715ac52ecb458b80f5010f99e234b516"),
            ("ruin", 9, 3, 30, 9, "122041c0222e3c9446922a2ba483887d"),
            ("goal", 100, 1, 10, 80, "a8401f9fb0beb8d5c926f86a59b43b67"),
            ("ruin", 8, 3, 30, 8, "026a1346b3992a3d4bdd13f4abb73f3e"),
            ("ruin", 4, 3, 30, 4, "b5263c6b22087fed65d6a28ce62a4892"),
            ("ruin", 6, 4, 40, 16, "afdebbc66817e4525c8c794c02f593bd"),
            ("goal", 84, 5, 50, 104, "e854e7d29a7b8f8156f5a819bc763ed2"),
            ("ruin", 0, 3, 30, 0, "20bb63a806b92864d509f2ade8111866"),
            ("ruin", 2, 3, 30, 2, "936731f5472a71d2a91ac9a533f04043"),
            ("ruin", 6, 4, 40, 16, "190ff37e874dde56d886dd556c84b882"),
            ("ruin", 8, 4, 40, 18, "78f3ee8888a54a4b5e1e874b8be8a50a"),
            ("goal", 83, 3, 30, 83, "28c5f528993115befd599f181bdbbbb5"),
            ("goal", 92, 2, 20, 82, "988b8d0c6e04762fafc715295aa0980b"),
            ("goal", 91, 2, 20, 81, "e55f085c6e012e4085c56c01f178188c"),
            ("ruin", 2, 4, 40, 12, "1613778f7693efd4c525f790a8c14eba"),
            ("ruin", 4, 3, 30, 4, "c81097a17699c0bcb110e8011533def7"),
            ("ruin", 1, 3, 30, 1, "220c2553a523db0bbd0453a1bb19baa6"),
            ("ruin", 8, 3, 30, 8, "e27754c8704ff7c55113804cf7807d63"),
            ("ruin", 0, 3, 30, 0, "348eb63096652458bdfb496407fbac7b"),
            ("ruin", 0, 3, 30, 0, "804e92701d5a83ee200dd77587b2018d"),
            ("ruin", 0, 3, 30, 0, "1fc07a56d1ef60846905b2fe1e49c4d5"),
            ("ruin", 3, 3, 30, 3, "e31c14a743e428d1bc0435cfd473d806"),
            ("ruin", 0, 3, 30, 0, "06a26a41a0f3c1a8a4435afe793d9c37"),
            ("ruin", 0, 4, 40, 10, "7d80cc7ee8033d11c9d8157dce9985f5"),
            ("ruin", 0, 3, 30, 0, "5d56854200c448f7081dccc0fc8031d9"),
            ("ruin", 4, 3, 30, 4, "f1b9559219c206597a0b0f40875c1ea7"),
            ("ruin", 2, 3, 30, 2, "637d52b0392fa182e835045ebaeaf114"),
            ("ruin", 7, 3, 30, 7, "8ee82b33f5dd0fa9247a93df3e96c7f6"),
            ("ruin", 7, 4, 40, 17, "0c3516ff5962f7e25de0d5869ef9e65b"),
            ("ruin", 1, 3, 30, 1, "7f3332fd67df2798129530420855963f"),
            ("ruin", 0, 4, 40, 10, "8937475a8ee6b0bcf25b0e4ffad98a89"),
            ("ruin", 9, 3, 30, 9, "93a112497e555c3ac9de160a9c590f07"),
            ("ruin", 2, 3, 30, 2, "d50d3b43776b6567271962f9af6cd079"),
            ("ruin", 9, 3, 30, 9, "cec40fa51036ee5c82a43b7ed84c2028"),
            ("ruin", 1, 4, 40, 11, "50f636c34e569c336ac634c0d4220c46"),
            ("ruin", 0, 3, 30, 0, "f3e19fd8e5256d6c77a72070b0c17c31"),
            ("ruin", 0, 3, 30, 0, "5749a38ecaa5679d8ee06468a53aa227"),
            ("ruin", 4, 3, 30, 4, "595ff461db99b6ff797da4036adf4d20"),
            ("ruin", 0, 4, 40, 10, "47d9de42931235af1c1c7562eb502042"),
            ("ruin", 0, 3, 30, 0, "0e88455cc92a0a58fcb9302c4d3c7c54"),
            ("ruin", 9, 3, 30, 9, "bb2980731ca795d8885ae03abcd865e3"),
            ("ruin", 0, 3, 30, 0, "d7d887f186e88167ba1b47bb5e043520"),
            ("ruin", 0, 3, 30, 0, "b5a5e8ea5916621560816a4e541acc6f"),
            ("goal", 100, 1, 10, 80, "04c1e2997ce30c271b9b33b6dcdc3754"),
            ("ruin", 0, 3, 30, 0, "27d2b52b4758c834a2f009347b66a68e"),
            ("ruin", 6, 4, 40, 16, "fdd87100f209a5ee6df6084b51c79d81"),
            ("ruin", 2, 4, 40, 12, "cc503fbb1c9b75a9fac15a62501f4cd4"),
            ("goal", 82, 3, 30, 82, "339bc2173d40e04b35f340d77ea3b8e4"),
            ("goal", 101, 1, 10, 81, "fe311f8c03ea29a3476bfae88023280e"),
            ("goal", 86, 3, 30, 86, "bfc0e53173a7e7772457b59e332aadd5"),
            ("ruin", 1, 3, 30, 1, "a420e1f99ced46bc7475f6e3e8c615c0"),
            ("goal", 92, 2, 20, 82, "d2df74799b1730b9e5694e7c4c6c3c32"),
            ("ruin", 0, 3, 30, 0, "8ccaeda584ce6a50b0994a1fd479aeaa"),
            ("goal", 82, 3, 30, 82, "4a952de25aeceac9b3c42a1ab349d77c"),
            ("goal", 100, 1, 10, 80, "57a21b6d3160fcdbf14b835c6eb59b4e"),
            ("ruin", 0, 3, 30, 0, "0fcb551b5e7dce06b3cf11d9433101a5"),
            ("goal", 90, 2, 20, 80, "dfcf47be849deccfddecd4364df6edae"),
            ("ruin", 2, 3, 30, 2, "49968a3d028fc44342ee7becd77851ea"),
            ("ruin", 0, 3, 30, 0, "aba7667a83c55098d6cf7721f3fdd8de"),
            ("ruin", 0, 3, 30, 0, "d38fdd7c15490b09166a03ddeee09f29"),
            ("ruin", 4, 3, 30, 4, "0dea288844209eb0b66d5ea70853a450"),
            ("ruin", 2, 3, 30, 2, "f208355674bcb52cce5cd3d56d4271f4"),
            ("ruin", 9, 3, 30, 9, "7386f152c4094f38a0e07ab4364f182f"),
            ("goal", 98, 2, 20, 88, "3f0a96dd137613f5a7f2975bad5e29e6"),
            ("goal", 102, 1, 10, 82, "cbdbdc4a1acaa1a607dd4289785ee42a"),
            ("ruin", 4, 3, 30, 4, "05d22cd8bd5f60718ac84612e767ffa8"),
            ("ruin", 1, 3, 30, 1, "bd8318bfbbb347bb277278807c184997"),
            ("goal", 96, 3, 30, 96, "76a33f776935f8e81959aee34ad46452"),
            ("ruin", 2, 4, 40, 12, "fdeebb1c6cb48847a36e47997cdfe44b"),
            ("ruin", 2, 3, 30, 2, "4d2393b73b6c80382438bcb29cba44b7"),
            ("ruin", 5, 3, 30, 5, "1c5efea5c60cb3c5a211e6cb25d177c7"),
            ("ruin", 6, 3, 30, 6, "ef4661534dec08acdfe1ead9bdbee356"),
            ("ruin", 9, 3, 30, 9, "a507de87e6f5d8e12750a484c130289b"),
            ("ruin", 0, 3, 30, 0, "685a5263f5db04126f0151396038bf3c"),
            ("ruin", 5, 3, 30, 5, "ff98f1daf8af1ee6f52ba6b790ff9e5c"),
            ("ruin", 8, 3, 30, 8, "dd9afc4d6d7e601ca8af79dded4b4028"),
            ("goal", 80, 3, 30, 80, "6263514f7d278c9a72c16aa3261db03a"),
            ("goal", 104, 1, 10, 84, "25f65b2b3b93c1220ed9b60ceb7f79f7"),
            ("ruin", 0, 3, 30, 0, "c8b018b158e2af28d54b7e663b40e1c4"),
            ("goal", 100, 1, 10, 80, "21a85a05b305967f97fda36b4982a9ea"),
            ("ruin", 4, 3, 30, 4, "8cff912b6d4fe304dd5608f1728ac563"),
            ("ruin", 3, 3, 30, 3, "b38fdac5344d8c73ff0e8cf474ed6e81"),
            ("incomplete", 20, 1, 10, 0, "69f69197c0f14b0604358ddf7707f46b"),
        ),
    },
    (25, 100, 180): {
        "bets": 426,
        "wagered": 10650,
        "paid": 11123,
        "goal": 29,
        "ruin": 30,
        "incomplete": 1,
        "sessions": (
            ("ruin", 16, 12, 300, 216, "c7498921a25da8afe1efd1485629666d"),
            ("ruin", 2, 4, 100, 2, "d7ffa57ce8978999347f5d79a93e823c"),
            ("goal", 195, 3, 75, 170, "e7c30fde3afb21f079997550eec442f6"),
            ("goal", 219, 5, 125, 244, "b071e56664dffda36d0a840bda22e25e"),
            ("ruin", 3, 4, 100, 3, "3f4907e43763f599c4634760e7cbd81d"),
            ("ruin", 3, 4, 100, 3, "ef9bbb17a8620d3b9fd2a3766424e6fd"),
            ("ruin", 16, 15, 375, 291, "1373bd77f3ea4666e92821be67cea4b0"),
            ("goal", 192, 10, 250, 342, "e3147175b7d3fe8abf621923feec602e"),
            ("ruin", 19, 8, 200, 119, "27c35be5ff401b070d51716e9ed0c36d"),
            ("ruin", 21, 4, 100, 21, "ef82aa027c981757cec6c017955eb404"),
            ("ruin", 17, 4, 100, 17, "4a4d72bf6b06f9e380867921d3303642"),
            ("goal", 192, 7, 175, 267, "290a7364ee3c354ed2ff68d5734ae8b6"),
            ("ruin", 3, 21, 525, 428, "22e785fe3490dae22f89a74e6599af52"),
            ("ruin", 10, 11, 275, 185, "1c5dc6ccb31f4afb55adf4fafaf07b90"),
            ("ruin", 5, 4, 100, 5, "4500129b7f79b45e94eaab4cce0fa472"),
            ("goal", 205, 3, 75, 180, "57b36fd645a20963cdc82d81f27614f2"),
            ("goal", 233, 8, 200, 333, "c1caf45e510322db7fc01fe524df7f4e"),
            ("goal", 202, 3, 75, 177, "696946a667c3a4b3069a972f11e02ed3"),
            ("ruin", 11, 4, 100, 11, "f3eff965f4fb614f12518e0b519324b2"),
            ("goal", 196, 4, 100, 196, "b10abb1dde086657211409981210f3a5"),
            ("ruin", 15, 4, 100, 15, "4477761e8c98d3c3909dc96968fc7fd2"),
            ("ruin", 21, 16, 400, 321, "fc26f5d5d83482e99996b5273fba4008"),
            ("ruin", 24, 4, 100, 24, "474c6ec75bcc8da0d8114f84b46b60f5"),
            ("goal", 234, 5, 125, 259, "c4b93f833d5fc720a470994197bf3fd3"),
            ("ruin", 24, 4, 100, 24, "76ad9a4e163ecf7854a64c316a0c9e0b"),
            ("goal", 191, 7, 175, 266, "f24f4fd9bc682cd4f30c78c1280f9a9d"),
            ("ruin", 3, 5, 125, 28, "2531d0b115a8e9151adac3583fdcece1"),
            ("goal", 201, 3, 75, 176, "bf1c274992e562ee2018893ae8628804"),
            ("ruin", 13, 12, 300, 213, "6cff094e4e54b0361772de008e74ab95"),
            ("goal", 185, 4, 100, 185, "21bfeb4dcded154ace9b865bc053685d"),
            ("goal", 220, 22, 550, 670, "4ea1e07562e51023bdc40df77d3c6037"),
            ("goal", 196, 3, 75, 171, "a499bb2e907708bd41ef5031ca47de8c"),
            ("goal", 187, 8, 200, 287, "0eabc52b287d3461a7110c78db9c7820"),
            ("goal", 218, 12, 300, 418, "31ab1888abdd0f06da97ea0f9c4f38fe"),
            ("goal", 226, 12, 300, 426, "04edd933d2f081f312a84e6328f6adc5"),
            ("ruin", 16, 4, 100, 16, "d429b8fccb01126e52a03bf167c6681d"),
            ("goal", 233, 8, 200, 333, "3c86d4352b1e94ec877202fbac3d683d"),
            ("ruin", 24, 4, 100, 24, "5a46f69fbb5e8fb33c55cbd305bb1713"),
            ("goal", 183, 4, 100, 183, "2b37580cd9d32096bbbd1ace3b40adae"),
            ("ruin", 16, 4, 100, 16, "eeedb420b394469992e5b194509ac32d"),
            ("ruin", 21, 7, 175, 96, "f535711ca4a3e24d6523472121fe1d1b"),
            ("goal", 211, 14, 350, 461, "05202ec6fff3726aaeafd3388a683a49"),
            ("ruin", 5, 9, 225, 130, "c60580c853d4e5917cf3a4197a4cfc56"),
            ("goal", 190, 16, 400, 490, "a63101b23786d2149f3b910a78959690"),
            ("ruin", 19, 4, 100, 19, "8ed8920a5039730582527199b0036100"),
            ("goal", 188, 3, 75, 163, "99f05748ba6f10d32793ecaf7b7bda50"),
            ("ruin", 21, 12, 300, 221, "3fc97644aafa0ebbd334c0f831535b2f"),
            ("goal", 224, 2, 50, 174, "68618a1164273ee9d07fcb1cd2527a5f"),
            ("goal", 218, 2, 50, 168, "f0fbea88f4889e5f72cf670f0884e8b6"),
            ("ruin", 14, 14, 350, 264, "0a72201558d64f9c5aabf8db046036e0"),
            ("ruin", 12, 4, 100, 12, "b4d7c5725890f4b442a56238dc65f6f9"),
            ("goal", 212, 7, 175, 287, "92b744ca61e531d0e27cfd6aeae4918c"),
            ("goal", 211, 6, 150, 261, "fb69d47c60d420d07e8e96527134e9af"),
            ("goal", 184, 11, 275, 359, "738978db022c03df9f7c5c103aff8ba1"),
            ("ruin", 19, 11, 275, 194, "d910807de1b7761af8ddc10647d5ccea"),
            ("ruin", 22, 7, 175, 97, "0e9439713b308eea92af51cefdb68a14"),
            ("goal", 209, 3, 75, 184, "84f8e240ab8f467c03cce50987641efa"),
            ("ruin", 21, 7, 175, 96, "1b17eb584e67e45e689e7cb2562f52de"),
            ("goal", 198, 3, 75, 173, "4704266c56dc6c2a841887fd1be27d04"),
            ("incomplete", 84, 1, 25, 9, "ecf143c25b23f8afa97c2d285adb77d8"),
        ),
    },
    (1, 5, 12): {
        "bets": 426,
        "wagered": 426,
        "paid": 269,
        "goal": 6,
        "ruin": 68,
        "incomplete": 0,
        "sessions": (
            ("ruin", 0, 5, 5, 0, "16203b1271373e93be76437a227664d4"),
            ("ruin", 0, 13, 13, 8, "34be1a8d4bada9de12f66fb086c10852"),
            ("ruin", 0, 5, 5, 0, "32d72158cbcd7d4f6837f1cd475c43c5"),
            ("ruin", 0, 5, 5, 0, "704ca629e3fa2b3530d488a874a84ab8"),
            ("ruin", 0, 5, 5, 0, "28d3e29a1cea99487c0148c26dbb78aa"),
            ("ruin", 0, 5, 5, 0, "ff5c95c280ae28b4ebb1841970230b87"),
            ("ruin", 0, 5, 5, 0, "35f28587b7a1740f4be89c4e8114c7b9"),
            ("ruin", 0, 13, 13, 8, "df42fb4d765c168e7dd8b67cb5cfc925"),
            ("ruin", 0, 5, 5, 0, "b75cf8616df5cc21bf459f4b51169eca"),
            ("ruin", 0, 7, 7, 2, "fe6cdcd90e674c64291946d3324e67b0"),
            ("ruin", 0, 9, 9, 4, "240a7aa94f486e9b22e5914a2519dde6"),
            ("ruin", 0, 5, 5, 0, "75e8d1db9babeec85828b4b0c7fe8822"),
            ("ruin", 0, 5, 5, 0, "631fc71d3a37abc7f0a9524b2dcbd085"),
            ("ruin", 0, 5, 5, 0, "1572f58576b7e59f59ad70d8ca27c867"),
            ("ruin", 0, 5, 5, 0, "a7af31adf6a238b53c5be61a2f9ca89f"),
            ("ruin", 0, 13, 13, 8, "1a231a854ba479d84668b004d8a5547d"),
            ("ruin", 0, 5, 5, 0, "9f03ae83f7852b425e0a4733b1e0ddb8"),
            ("ruin", 0, 5, 5, 0, "da4debdad0df05f8860546bc09ad1cc4"),
            ("ruin", 0, 5, 5, 0, "4199093a871973c70c7be799a6b0b9b0"),
            ("ruin", 0, 5, 5, 0, "c5a2807f02c9e8d35e8ef8194b372824"),
            ("ruin", 0, 5, 5, 0, "e7b4c64e53a41aaf522a2aea6aeead9d"),
            ("goal", 12, 1, 1, 8, "c149722ff072574d31a8144f6d661971"),
            ("ruin", 0, 5, 5, 0, "e70ffb8d441e509dfd7ec2fa03a2da46"),
            ("ruin", 0, 5, 5, 0, "60189af39bcf10c7ccadaeb37ec626bd"),
            ("ruin", 0, 6, 6, 1, "d0ef3e80da49d1c07cf023f79df131f3"),
            ("ruin", 0, 13, 13, 8, "345e6e8924b46736755437a4b4a50807"),
            ("ruin", 0, 5, 5, 0, "e689b1e17d27475295b9be78a90fcf84"),
            ("ruin", 0, 5, 5, 0, "e373b200fde8b6dd6e89e694ccfab635"),
            ("goal", 80, 9, 9, 84, "7dc5a10c78cf56e980007adc07224c83"),
            ("ruin", 0, 5, 5, 0, "68d83d88a87678d03473be144e0c332c"),
            ("ruin", 0, 6, 6, 1, "5e0c5f5c1b5f6db594a415ac8308d2f7"),
            ("ruin", 0, 5, 5, 0, "074a50d46faa01f62fa6819c01e1f41a"),
            ("ruin", 0, 5, 5, 0, "3c8c073ee5649818d29c7f0adce4af3f"),
            ("ruin", 0, 5, 5, 0, "f267d2e5297e326f1fc6b8ccb24e84c7"),
            ("ruin", 0, 5, 5, 0, "2052ce780ae37dee09ff5c91d62bade0"),
            ("goal", 85, 8, 8, 88, "d0f3d424702ebf53fa30252f6ee5058a"),
            ("ruin", 0, 5, 5, 0, "fd88f10c3721745547fb154adaad9ee7"),
            ("goal", 12, 5, 5, 12, "8c03c5238172ec8a46ce62496b4162fe"),
            ("ruin", 0, 5, 5, 0, "2b53b560279efca6bc39d8dbaeffd8be"),
            ("goal", 12, 1, 1, 8, "d30a11daf30299454c98c47b31c129f0"),
            ("ruin", 0, 5, 5, 0, "62556ee7672351cc85c1d22e18af16ed"),
            ("ruin", 0, 5, 5, 0, "2bd4178e7951bd30fc977c3594a2a329"),
            ("ruin", 0, 5, 5, 0, "c32fe6d5fb3847197199d759a912c466"),
            ("ruin", 0, 5, 5, 0, "bfb5a0a5adae4dfc2e88f0890671e95b"),
            ("ruin", 0, 5, 5, 0, "bc5fee7a996e2284429bd3dc58be346e"),
            ("ruin", 0, 5, 5, 0, "575d91c55ba2fe0dc68e2a44fcf315c7"),
            ("ruin", 0, 5, 5, 0, "4d816dd73f423608e8d1264629e8a1d0"),
            ("ruin", 0, 5, 5, 0, "734aa8653544443e8f667232e0fe1bc1"),
            ("ruin", 0, 6, 6, 1, "e5b818120f9c534f92baf566f80f7de0"),
            ("ruin", 0, 5, 5, 0, "e2151388ef85d6585e75653402dc1856"),
            ("ruin", 0, 5, 5, 0, "bd5e5bbda94a0f4051f2faa7d0344207"),
            ("ruin", 0, 5, 5, 0, "a380b973000ceb69ba5c67591e7f615a"),
            ("ruin", 0, 5, 5, 0, "0c7379144665896d748a2234afc30461"),
            ("ruin", 0, 5, 5, 0, "662df48e7af4fb1636dc146899577607"),
            ("ruin", 0, 5, 5, 0, "dd7494ca96886ba8b87452976e19d8cf"),
            ("ruin", 0, 5, 5, 0, "919fe8b8af1ca36a264b5ddd822a8af9"),
            ("ruin", 0, 5, 5, 0, "8df7f1630d136a3fdce5e4d2d812b25b"),
            ("ruin", 0, 17, 17, 12, "38c84545ce4189158cc2e96f3aa26d52"),
            ("ruin", 0, 5, 5, 0, "a098489d08b25900ee4ce4812de26258"),
            ("ruin", 0, 5, 5, 0, "9c1d064b7f3c6d3d8db08b0f920f4771"),
            ("ruin", 0, 5, 5, 0, "d158f76e19cb385d9b0fbc50e4ef452f"),
            ("ruin", 0, 5, 5, 0, "3bdaf9b3b1f0d38de244c3710d87b371"),
            ("ruin", 0, 5, 5, 0, "af105030bff56de558da4e299c9b8426"),
            ("ruin", 0, 5, 5, 0, "d7741f672d9bc47885f5e587c3df4a92"),
            ("ruin", 0, 13, 13, 8, "f6362d2d4553f87993fd2bfe0e6c3cf8"),
            ("goal", 12, 1, 1, 8, "19bf1809bb6cc038053e6f1d15680592"),
            ("ruin", 0, 5, 5, 0, "2ec2f88374e6c62438b624dae86a8862"),
            ("ruin", 0, 5, 5, 0, "1f5441f884e6605e50cb29ca94cf50cd"),
            ("ruin", 0, 5, 5, 0, "e899e75c8e8d98bb5e0f0b2d5b46c979"),
            ("ruin", 0, 5, 5, 0, "318a6e33280ec35f5919d8f6ccc6cb17"),
            ("ruin", 0, 5, 5, 0, "d3a176800f083742940f5d203de1d3b2"),
            ("ruin", 0, 5, 5, 0, "d79c335b841eeae0370906d4609bce88"),
            ("ruin", 0, 5, 5, 0, "74671b2a81cbea9913cc55f55d312d1d"),
            ("ruin", 0, 5, 5, 0, "f7837d77d7e8ac73aad2682e4bb39b85"),
        ),
    },
}

FROZEN_GOLDEN = {
    "bets": 65235,
    "wagered": 3261750,
    "paid": 3118481,
    "goal": 13,
    "ruin": 78,
    "incomplete": 1,
    "mean_net_closed": -1572.8,
    "sessions": (
        ("ruin", 27, 345, 17250, 15277, "bccda8f7d957b857d5f9c7c1a538f6f8"),
        ("ruin", 45, 543, 27150, 25195, "74790d4fdcf05657113b91e590d0452f"),
        ("ruin", 44, 1040, 52000, 50044, "185235b13e863870b0e05ea4baf9848f"),
        ("ruin", 22, 440, 22000, 20022, "06b58ada9628c9ba15e05839afa006a8"),
        ("ruin", 22, 448, 22400, 20422, "40117138546e5dec275a323be7250d13"),
        ("ruin", 49, 1409, 70450, 68499, "973880902eabf37f71a7040e7ec6b07f"),
        ("ruin", 31, 579, 28950, 26981, "a2e15ca0dd14a8e44e63bcd6e67787c9"),
        ("ruin", 10, 1268, 63400, 61410, "491312f46daebf21bef4ac62d7402d06"),
        ("ruin", 33, 475, 23750, 21783, "4c308694d937aa5a05021b9ec5a4cf43"),
        ("ruin", 26, 998, 49900, 47926, "5494302bbabb62577cb4821025bd0177"),
        ("ruin", 14, 444, 22200, 20214, "aa3cf101c095daff6ea0272f6263a5ec"),
        ("ruin", 49, 658, 32900, 30949, "51849444362c78d1608bd995e034b6b3"),
        ("ruin", 23, 378, 18900, 16923, "b975781b9d7c9356dc27f331d2d3db63"),
        ("ruin", 38, 479, 23950, 21988, "57fb53c6a7045efca035e690e3276a2c"),
        ("ruin", 39, 815, 40750, 38789, "a82a0581b8a5b93584b658540db746ba"),
        ("ruin", 38, 1310, 65500, 63538, "3474d602ffcdffdb087d4311430b2c9f"),
        ("ruin", 15, 1436, 71800, 69815, "488a64d870e71ed8aa9b4340e976dfc6"),
        ("ruin", 27, 2392, 119600, 117627, "8e18107db7402a966c8cdee441178940"),
        ("ruin", 47, 922, 46100, 44147, "2fdde3d46e5063edf0faf0fb4ebee42a"),
        ("ruin", 35, 730, 36500, 34535, "ca54ba6a208107693fa2311dbe102963"),
        ("ruin", 39, 556, 27800, 25839, "073e4d2b5612b492c673854b3d7e90a7"),
        ("ruin", 27, 672, 33600, 31627, "7e5d9a63972bd147e5ccf9eea4110100"),
        ("ruin", 27, 1378, 68900, 66927, "c5619b1f031ed2783fdab56459b9a42e"),
        ("ruin", 10, 1018, 50900, 48910, "310fcc349bb5c48187733e6fbf994817"),
        ("ruin", 32, 898, 44900, 42932, "c02212c57f7cc597da6374e9a30f1c22"),
        ("goal", 2805, 271, 13550, 14355, "a52ad5537b8f385b2cfdf123d17c4dd3"),
        ("ruin", 32, 621, 31050, 29082, "86daf8432c397ee869467b42ff2b73f9"),
        ("ruin", 46, 732, 36600, 34646, "aa074b5756ecb34a38be68823fa40aa7"),
        ("ruin", 36, 782, 39100, 37136, "b211320b5680fb99ed0200cc7891f94e"),
        ("goal", 2836, 115, 5750, 6586, "62976e60e34b9018f4a79362d6d6c4fd"),
        ("ruin", 40, 1312, 65600, 63640, "c4751d15ca08d5a7b47a7ea4df8603bc"),
        ("ruin", 23, 780, 39000, 37023, "69e0e09e0760ffd5aa806a6b8850842f"),
        ("ruin", 39, 483, 24150, 22189, "4782b11371a712fa0bf2fa5d24bd8476"),
        ("goal", 2820, 115, 5750, 6570, "e604f275d80f32beeeba696e1b4d0ec7"),
        ("goal", 2800, 409, 20450, 21250, "bdf67de1b8093870132a72900c3b921b"),
        ("ruin", 30, 260, 13000, 11030, "96f0526110d9ceed8fc9964eee638fe1"),
        ("ruin", 12, 639, 31950, 29962, "b3c168e7f77a7d7f7e39610b5cfc9905"),
        ("goal", 2805, 84, 4200, 5005, "d637edebdd45affd4642d965d22f9bc0"),
        ("ruin", 48, 491, 24550, 22598, "a0f70da9862d50e65f394e5ea3926fa2"),
        ("ruin", 21, 298, 14900, 12921, "891070c3c3587aaa2ee1e7026ecce7d0"),
        ("goal", 2818, 156, 7800, 8618, "c2174daf01b667678c6fa89e7e7cbe80"),
        ("ruin", 47, 201, 10050, 8097, "812cac56344d93c27b55d66e3bfb3d6d"),
        ("ruin", 12, 1213, 60650, 58662, "00efb278c9d7f38ab5a93a7c5b2d87ec"),
        ("ruin", 41, 1175, 58750, 56791, "6abde4984b6d56dc422e04b5dc24b4bc"),
        ("goal", 2826, 100, 5000, 5826, "3e9137ce1d23d1fca7d0f788c698394a"),
        ("ruin", 38, 352, 17600, 15638, "204ce66808151ce36103fa8040882aab"),
        ("ruin", 6, 891, 44550, 42556, "f96f972800595685c19a329f5ad0807f"),
        ("goal", 2841, 226, 11300, 12141, "0b96e19b684631546fb27e6dd1001c5a"),
        ("ruin", 16, 419, 20950, 18966, "7cc98414d5c678578fcaa9d52ab84bcb"),
        ("ruin", 4, 202, 10100, 8104, "e8eadae09d4a2cfde3543f79212200da"),
        ("ruin", 42, 689, 34450, 32492, "549337836b27bf709dcac1d0d4dba17f"),
        ("ruin", 18, 470, 23500, 21518, "ef852eec9d3e7b739cec2d65b6ef2f2d"),
        ("ruin", 39, 1282, 64100, 62139, "5f2626d9c6f98c68e96f33d07c5ab18a"),
        ("ruin", 14, 271, 13550, 11564, "7ac537d2ee7be4a75c781e7c79477ca9"),
        ("ruin", 46, 2278, 113900, 111946, "e3c04fca9b5b4e282bb7ff93109a3f07"),
        ("goal", 2829, 67, 3350, 4179, "ef2ec633fc053b81d2f286a5aa78eb18"),
        ("ruin", 45, 669, 33450, 31495, "eab02f4db6c8bc52cca78bdaa509cd52"),
        ("ruin", 49, 643, 32150, 30199, "c77d5512e1facad2c6c8172234425afe"),
        ("ruin", 4, 1162, 58100, 56104, "14ef6cdcf21c46cbf7c4e29d322ba3f5"),
        ("ruin", 16, 1570, 78500, 76516, "8329d0e90cbd21e632bcc7815d6a4388"),
        ("ruin", 48, 1057, 52850, 50898, "81ab9c4904270a9c4bf78199cfeaa759"),
        ("ruin", 24, 720, 36000, 34024, "8d88a371347f5a27c7d40a31285bc6e0"),
        ("ruin", 38, 1123, 56150, 54188, "f8cf98ca88d2bd5979d920d37c0769ad"),
        ("ruin", 25, 1426, 71300, 69325, "79c7f373da4d5c64d96cf7d0451c190f"),
        ("ruin", 9, 1302, 65100, 63109, "6fbfa1e6ff0bfd613a751091360ca023"),
        ("ruin", 44, 512, 25600, 23644, "76622f3362f472487f820da5430da149"),
        ("ruin", 7, 702, 35100, 33107, "97d8b8b04cccbdf75d1c6b94ab7aa96e"),
        ("goal", 2805, 286, 14300, 15105, "26c90014fc898c75d292f56486543e1c"),
        ("ruin", 29, 466, 23300, 21329, "f232d17f020901c47b7c6b27bcdc12b0"),
        ("ruin", 43, 959, 47950, 45993, "a6c0cff43904ff45756b741f11850f19"),
        ("ruin", 12, 927, 46350, 44362, "d9d76af0f10489a27ec08e42108ba30d"),
        ("ruin", 10, 444, 22200, 20210, "dfe7c8fe2923fb8720608ebae0ad5c67"),
        ("goal", 2811, 448, 22400, 23211, "7e6a0f2c077770b3c27d615045ce432f"),
        ("ruin", 23, 573, 28650, 26673, "665069c0765d37ffd5d30d3a3aa00206"),
        ("ruin", 38, 764, 38200, 36238, "4644cebf6853533bce16cd71d7319666"),
        ("goal", 2821, 199, 9950, 10771, "e78797d6730b0f1c2f762dd407a0f694"),
        ("ruin", 38, 686, 34300, 32338, "60e49e1bfd176470804cedc55e86779a"),
        ("ruin", 15, 712, 35600, 33615, "5c5b689b3757eaa6c83e22c62aa4e676"),
        ("ruin", 43, 656, 32800, 30843, "03059be2e04ad5112c0e16aa49a43fd6"),
        ("ruin", 36, 980, 49000, 47036, "079370528755796c1600e409e8a39d8c"),
        ("ruin", 9, 1024, 51200, 49209, "f7224e6d1d6f3ec5447c832edcaed024"),
        ("ruin", 16, 470, 23500, 21516, "b5ba24a4cc1860aa00d04aa86cb2e95d"),
        ("ruin", 39, 970, 48500, 46539, "bd0c1ee699bc20022de4e9c9d1dd0cfe"),
        ("ruin", 39, 371, 18550, 16589, "be2802e784e184cefb0565fc85e23c75"),
        ("goal", 2800, 602, 30100, 30900, "674f0b16d29bea5122ec3e301e2c869a"),
        ("ruin", 11, 927, 46350, 44361, "8ff4348ba3c258d470200562ffa700bf"),
        ("ruin", 43, 529, 26450, 24493, "c464c14be368e93786d6bdf05b4cb851"),
        ("ruin", 48, 530, 26500, 24548, "3b8477a3302fdce750ceb7d637b3ae51"),
        ("ruin", 18, 376, 18800, 16818, "1392c93e9695ef515d08e2900b239c5d"),
        ("ruin", 8, 1194, 59700, 57708, "6bc7e75636e7b0fc788c7c1934060b07"),
        ("ruin", 15, 217, 10850, 8865, "3c46b012f50ca009502f8d55b6d6282c"),
        ("incomplete", 1853, 24, 1200, 1053, "634cae5530f9d1756b8d4b43cfab4695"),
    ),
}


def _bets_digest(bets):
    sha = hashlib.sha256()
    for bet in bets:
        record = (bet.label, tuple(bet.numbers), bet.wagered, bet.paid, bet.balance, bet.per_number)
        sha.update(repr(record).encode())
    return sha.hexdigest()[:32]


def _session_records(result):
    return tuple(
        (
            s.outcome,
            s.final_balance,
            len(s.bets),
            sum(bet.wagered for bet in s.bets),
            sum(bet.paid for bet in s.bets),
            _bets_digest(s.bets),
        )
        for s in result.sessions
    )


def _assert_matches_frozen(result, frozen):
    assert _session_records(result) == frozen["sessions"]
    totals = result.totals
    assert totals.sessions == len(frozen["sessions"]) > 1
    assert totals.bets == frozen["bets"]
    assert totals.wagered == frozen["wagered"]
    assert totals.paid == frozen["paid"]
    assert totals.goal == frozen["goal"]
    assert totals.ruin == frozen["ruin"]
    assert totals.incomplete == frozen["incomplete"]


@pytest.mark.parametrize(
    ("coverage", "capital", "goal"),
    [(50, 200, 400), (10, 30, 60), (25, 100, 180), (1, 5, 12)],
)
def test_matches_frozen_flat_engine_on_synthetic_rows(coverage, capital, goal):
    rng = random.Random(1234)
    rows = []
    for index in range(600):
        results = tuple(rng.randrange(100) for _ in range(5))
        order = None if rng.random() < 0.3 else tuple(rng.sample(range(100), 50))
        rows.append(Draw(f"s{index}", index, results, order))

    result = run_sessions(
        RunConfig(
            capital=capital,
            goal=goal,
            coverage=coverage,
            positions=5,
            prizes=(80, 8, 4, 2, 1),
            minimum_stake=1,
        ),
        rows,
    )

    _assert_matches_frozen(result, FROZEN_SYNTHETIC[(coverage, capital, goal)])


def _ranked_parity_rows(data, coverage):
    history = data.history
    ranked = {int(row_id) for row_id in data.rankings.row_ids}
    votes = data.parity_votes()
    return [
        Draw(
            history.labels[index],
            int(history.minutes[index]),
            tuple(int(number) for number in numbers[:5]),
            tuple(int(n) for n in parity_numbers(int(votes[index]))[:coverage])
            if index in ranked
            else None,
        )
        for index, numbers in enumerate(history.nums)
    ]


@pytest.mark.real_data
@pytest.mark.golden
def test_real_history_parity_flat_golden(tmp_path):
    data = open_lab_data(replace(Settings.from_environment(), data_dir=tmp_path))
    result = run_sessions(
        RunConfig(
            capital=2000,
            goal=2800,
            coverage=50,
            positions=5,
            prizes=(80, 8, 4, 2, 1),
            minimum_stake=1,
        ),
        _ranked_parity_rows(data, 50),
    )
    totals = result.totals
    assert totals.sessions == 92
    assert totals.goal == 13
    assert totals.goal + totals.ruin == 91
    assert totals.ruin == 78
    assert totals.incomplete == 1
    assert totals.bets == 65235
    assert totals.mean_net_closed == -1572.8
    assert round(100 * totals.goal / (totals.goal + totals.ruin), 1) == 14.3
    _assert_matches_frozen(result, FROZEN_GOLDEN)
    assert totals.mean_net_closed == FROZEN_GOLDEN["mean_net_closed"]
