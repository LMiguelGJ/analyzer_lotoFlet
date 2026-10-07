"""R2: native historical ledger capture, not reconstructed replay."""

import json

import pytest

from laboratorio.domain.backtest import BacktestConfig, run_backtest
from laboratorio.domain.contracts import StakingStyle
from laboratorio.domain.session import Draw
from laboratorio.storage import backtest_trace as trace


def execution():
    config = {
        "name": "Trace",
        "strategy": {
            "name": "Flat",
            "selector": "system",
            "system": "cold",
            "coverage": 1,
            "staking": "flat",
        },
        "game": {"numbers": 10, "positions": 5, "prizes": [80, 8, 4, 2, 1], "min_stake": 1},
        "conditions": {"capital": 10, "goal": 20},
        "inputs": {"history_sha256": "a" * 64, "rankings_sha256": "b" * 64},
    }
    rows = (
        Draw("2025-01-01 05:00", 0, (9, 8, 7, 6, 5), None),
        Draw("2025-01-01 05:10", 10, (0, 1, 2, 3, 4), (0,)),
        Draw("2025-01-01 05:20", 20, (9, 8, 7, 6, 5), (0,)),
    )
    native = BacktestConfig(10, 20, 10, 5, (80, 8, 4, 2, 1), 1, 1, StakingStyle.FLAT)
    result = run_backtest(native, rows)
    aggregate = {
        "reached_goal": result.reached_goal,
        "quiebres": result.quiebre,
        "completed": result.completed,
        "goal_rate": result.goal_rate,
        "neto_medio": result.neto_medio,
        "incomplete": result.incomplete,
        "window": {
            "bets": result.window.bets,
            "wagered": result.window.wagered,
            "paid": result.window.paid,
            "sessions": len(result.sessions),
            "incomplete": result.incomplete,
        },
    }
    return config, rows, result, aggregate


def test_native_trace_roundtrip_and_source_boundary_are_distinct():
    config, rows, result, aggregate = execution()
    saved = trace.build_trace(result, config, aggregate, rows)
    trace.validate_trace(saved, config, aggregate)
    assert saved["status"] == "complete"
    assert saved["source_window"]["first"]["label"] == rows[0].label
    first = saved["sessions"][0]
    assert first["ordinal"] == 0 and first["outcome"] == "reached_goal"
    assert first["bets"][0] == {
        "bet_index": 0,
        "label": result.sessions[0].bets[0].label,
        "source_index": 1,
        "minute": 10,
        "numbers": [0],
        "per_number": 1,
        "wagered": 1,
        "results": [0, 1, 2, 3, 4],
        "paid": 80,
        "balance": 89,
    }
    assert saved["sessions"][1]["outcome"] == "incomplete"


@pytest.mark.parametrize(
    "cap,value",
    [
        ("MAX_TRACE_BETS", 1),
        ("MAX_TRACE_SESSIONS", 1),
        ("MAX_TRACE_BYTES", 1100),
    ],
)
def test_caps_capture_only_whole_session_prefixes(monkeypatch, cap, value):
    config, rows, result, aggregate = execution()
    monkeypatch.setattr(trace, cap, value)
    saved = trace.build_trace(result, config, aggregate, rows)
    assert saved["status"] == "truncated" and saved["reason"] == "limit_exceeded"
    assert saved["total_sessions"] == 2 and saved["total_bets"] == 2
    assert saved["stored_sessions"] < 2
    assert [s["ordinal"] for s in saved["sessions"]] == list(range(saved["stored_sessions"]))
    trace.validate_trace(saved, config, aggregate)
    assert (
        len(
            json.dumps(saved, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        <= saved["limits"]["bytes"]
    )


def test_oversized_first_session_is_unavailable_not_empty_execution(monkeypatch):
    config, rows, result, aggregate = execution()
    monkeypatch.setattr(trace, "MAX_TRACE_BETS", 0)
    saved = trace.build_trace(result, config, aggregate, rows)
    assert saved["status"] == "truncated" and saved["stored_sessions"] == 0
    assert saved["total_bets"] == 2
    trace.validate_trace(saved, config, aggregate)


def test_genuine_empty_and_zero_bet_session_are_not_legacy():
    config, rows, _, _ = execution()
    native = BacktestConfig(1, 20, 10, 5, (80, 8, 4, 2, 1), 2, 1, StakingStyle.FLAT)
    for draws, expected in (((), 0), (rows[1:2], 1)):
        result = run_backtest(native, draws)
        config["conditions"]["capital"] = 1
        config["game"]["min_stake"] = 2
        aggregate = {
            "reached_goal": 0,
            "quiebres": expected,
            "completed": expected,
            "goal_rate": 0.0,
            "neto_medio": 0.0,
            "incomplete": 0,
            "window": {"bets": 0, "wagered": 0, "paid": 0, "sessions": expected, "incomplete": 0},
        }
        saved = trace.build_trace(result, config, aggregate, draws)
        trace.validate_trace(saved, config, aggregate)
        assert saved["status"] == ("empty" if not expected else "complete")
        if expected:
            assert saved["sessions"][0]["bets"] == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.update(version=99),
        lambda t: t.update(version=True),
        lambda t: t.update(status="not_stored"),
        lambda t: t.update(stored_bets=True),
        lambda t: t["sessions"][0].update(ordinal=1),
        lambda t: t["sessions"][0]["bets"][0].update(balance=90),
        lambda t: t["sessions"][0]["bets"][0].update(source_index=999),
        lambda t: t["sessions"][0]["bets"][0].update(paid=float("nan")),
        lambda t: t["sessions"][0]["bets"][0].update(numbers=[True]),
        lambda t: t["sessions"][1]["bets"][0].update(minute=5),
        lambda t: t.update(extra="untrusted"),
    ],
)
def test_malformed_trace_fails_closed_without_mutation(mutate):
    config, rows, result, aggregate = execution()
    saved = trace.build_trace(result, config, aggregate, rows)
    mutate(saved)
    # Re-seal valid JSON mutations: semantic validation must not rely on digest alone.
    try:
        core = {key: value for key, value in saved.items() if key != "sha256"}
        saved["sha256"] = trace._digest(core, config, aggregate)
    except ValueError:  # NaN cannot be represented by the canonical encoder.
        pass
    before = json.dumps(saved, sort_keys=True)
    with pytest.raises(ValueError):
        trace.validate_trace(saved, config, aggregate)
    assert json.dumps(saved, sort_keys=True) == before


def test_payload_integrity_binds_config_aggregates_and_ledger():
    config, rows, result, aggregate = execution()
    saved = trace.build_trace(result, config, aggregate, rows)
    config["inputs"]["history_sha256"] = "c" * 64
    with pytest.raises(ValueError):
        trace.validate_trace(saved, config, aggregate)


def test_ambiguous_labels_do_not_invent_source_positions():
    from dataclasses import replace

    config, rows, result, aggregate = execution()
    duplicate = replace(rows[-1], label=rows[1].label)
    bets = (replace(result.sessions[1].bets[0], label=rows[1].label),)
    sessions = (result.sessions[0], replace(result.sessions[1], bets=bets))
    saved = trace.build_trace(
        replace(result, sessions=sessions), config, aggregate, (*rows[:-1], duplicate)
    )
    assert saved["source_window"]["first"]["source_index"] == 0
    for session in saved["sessions"]:
        assert session["bets"][0]["source_index"] is None
        assert session["bets"][0]["minute"] is None
    trace.validate_trace(saved, config, aggregate)


def test_large_native_money_projects_exact_decimal_strings_without_cent_scaling():
    value = 2**53 + 1
    bet = {"per_number": 7, "wagered": 7, "paid": value, "balance": value + 10}
    projected = trace.bet_projection(bet)
    assert projected["paid"] == str(value) and projected["balance"] == str(value + 10)
    assert projected["per_number"] == 7
    assert bet["paid"] == value  # Storage remains native integer facts.
    assert trace.session_summary(
        {"ordinal": 0, "outcome": "reached_goal", "final_balance": value, "bets": []}
    )["final_balance"] == str(value)
