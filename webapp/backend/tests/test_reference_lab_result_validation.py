"""Pure contract tests for the private reference-lab validation helpers."""

import hashlib
import json

import pytest

from laboratorio.storage.reference_lab_store import (
    _validate_result,
    _validate_session_rows,
)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _result(lab_id="lab-a", capital=2000):
    session = {
        "outcome": "goal",
        "start_index": 0,
        "end_index": 0,
        "draws": 1,
        "final_balance": capital - 1,
        "wagered": 1,
        "paid": 0,
    }
    digest_rows = [("goal", 0, 0, 1, capital - 1, 1, 0)]
    digest = hashlib.sha256(json.dumps(digest_rows, separators=(",", ":")).encode()).hexdigest()
    return {
        "lab_id": lab_id,
        "sessions": [session],
        "totals": {
            "completed": 1,
            "incomplete": 0,
            "goals": 1,
            "ruins": 0,
            "sessions_total": 1,
            "total_wagered": 1,
            "total_paid": 0,
            "total_net": -1,
            "total_steps": 1,
            "mean_net_closed": -1.0,
        },
        "eligible_draws": 1,
        "gaps": 0,
        "first": "draw-1",
        "last": "draw-1",
        "session_sha256": digest,
    }


def test_validate_result_returns_canonical_envelope_and_session_rows():
    result = _result()
    envelope_json, session_json = _validate_result("lab-a", 2000, result)

    assert envelope_json == _canonical({"schema_version": 1, "result": result})
    assert session_json == [_canonical(result["sessions"][0])]


def test_validate_result_normalizes_tuple_sessions_without_mutating_input():
    result = _result()
    result["sessions"] = tuple(result["sessions"])
    original = result.copy()
    original_sessions = result["sessions"]

    envelope_json, session_json = _validate_result("lab-a", 2000, result)

    normalized = {**result, "sessions": list(original_sessions)}
    assert envelope_json == _canonical({"schema_version": 1, "result": normalized})
    assert session_json == [_canonical(original_sessions[0])]
    assert result == original
    assert result["sessions"] is original_sessions


@pytest.mark.parametrize(
    ("lab_id", "capital"),
    [("", 2000), (None, 2000), ("lab-a", True), ("lab-a", 2000.0), ("lab-a", 0)],
    ids=[
        "empty-lab-id",
        "non-text-lab-id",
        "boolean-capital",
        "float-capital",
        "nonpositive-capital",
    ],
)
def test_validate_result_checks_its_own_lab_id_and_capital(lab_id, capital):
    with pytest.raises((TypeError, ValueError)):
        _validate_result(lab_id, capital, _result())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(lab_id="other-lab"),
        lambda result: result.update(extra=True),
        lambda result: result["sessions"][0].update(draws=True),
        lambda result: result["totals"].update(total_steps=2),
        lambda result: result["totals"].update(mean_net_closed=-2.0),
        lambda result: result.update(session_sha256="0" * 64),
    ],
    ids=[
        "wrong-lab-id",
        "unknown-result-key",
        "boolean-session-integer",
        "inconsistent-totals",
        "wrong-mean",
        "wrong-digest",
    ],
)
def test_validate_result_rejects_malformed_result_components(mutate):
    result = _result()
    mutate(result)

    with pytest.raises((TypeError, ValueError)):
        _validate_result("lab-a", 2000, result)


def test_validate_result_checks_session_balance_against_capital():
    with pytest.raises((TypeError, ValueError)):
        _validate_result("lab-a", 2001, _result())


def test_validate_session_rows_accepts_matching_canonical_copy():
    result = _result()
    session_json = _canonical(result["sessions"][0])

    assert _validate_session_rows(result["sessions"], [(0, session_json)], 2000) is None


@pytest.mark.parametrize(
    ("sessions", "rows", "capital"),
    [
        ([], [(0, "{}")], 2000),
        ([{"outcome": "goal"}], [], 2000),
        (_result()["sessions"], [(True, _canonical(_result()["sessions"][0]))], 2000),
        (_result()["sessions"], [(1, _canonical(_result()["sessions"][0]))], 2000),
        (_result()["sessions"], [(0, _canonical({**_result()["sessions"][0], "paid": 1}))], 2000),
        (_result()["sessions"], [(0, '{"outcome":"goal","outcome":"goal"}')], 2000),
        (_result()["sessions"], [(0, "{")], 2000),
        (_result()["sessions"], [(0, _canonical(_result()["sessions"][0]))], False),
        (_result()["sessions"], [(0, _canonical(_result()["sessions"][0]))], 2000.0),
    ],
    ids=[
        "row-cardinality-excess",
        "row-cardinality-missing",
        "boolean-ordinal",
        "wrong-ordinal",
        "copy-mismatch",
        "duplicate-json-key",
        "invalid-json",
        "boolean-capital",
        "float-capital",
    ],
)
def test_validate_session_rows_rejects_bad_persisted_copies(sessions, rows, capital):
    with pytest.raises((TypeError, ValueError)):
        _validate_session_rows(sessions, rows, capital)


def test_validate_session_rows_does_not_mutate_caller_objects():
    sessions = _result()["sessions"]
    rows = [(0, _canonical(sessions[0]))]
    original_session = sessions[0].copy()
    original_rows = rows.copy()

    _validate_session_rows(sessions, rows, 2000)

    assert sessions == [original_session]
    assert rows == original_rows
