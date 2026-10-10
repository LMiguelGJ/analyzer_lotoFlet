"""Canonical history bytes, pure merge, parity cache helper and extended run sources."""

import hashlib
import json

import numpy as np
import pytest

from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.engine.adapter import DataError, parity_votes_for, parse_history
from laboratorio.engine.history_merge import (
    MAX_DRAWS,
    HistoryConflict,
    canonical_history_bytes,
    merge_histories,
)
from laboratorio.engine.run_data import (
    RunStrategy,
    build_run_rows,
    source_from_history,
    source_from_lab,
)


def upload_bytes(entries):
    """Raw upload JSON from ``[(date, hora, [numbers])]`` (not canonical, on purpose)."""
    by_date = {}
    for day, hora, numbers in entries:
        by_date.setdefault(day, []).append({"hora": hora, "numeros": [f"{n:02d}" for n in numbers]})
    return json.dumps({"sorteos_por_fecha": by_date}, indent=2).encode()


def small_history(entries):
    return parse_history(upload_bytes(entries))


NEW_DRAWS = [
    ("2026-10-01", "10:00", [1, 2, 3, 4, 5]),
    ("2026-10-01", "15:00", [6, 7, 8, 9, 10]),
    ("2026-10-02", "10:00", [11, 12, 13, 14, 15]),
]


def test_canonical_bytes_round_trip_and_sha():
    history = small_history(NEW_DRAWS[::-1])
    raw = canonical_history_bytes(history.labels, history.nums)
    parsed = parse_history(raw)
    assert parsed.labels == history.labels
    assert np.array_equal(parsed.nums, history.nums)
    assert parsed.sha256 == hashlib.sha256(raw).hexdigest()
    document = json.loads(raw)
    assert document["metadata"] == {
        "schema_version": 1,
        "juego": "Quiniela 80",
        "origen": "laboratorio",
    }
    assert document["sorteos_por_fecha"]["2026-10-01"][0] == {
        "hora": "10:00",
        "numeros": ["01", "02", "03", "04", "05"],
    }
    assert b" " not in raw.replace(b"Quiniela 80", b"")


def test_canonical_bytes_are_deterministic():
    a = small_history(NEW_DRAWS)
    b = small_history(NEW_DRAWS[::-1])
    assert canonical_history_bytes(a.labels, a.nums) == canonical_history_bytes(b.labels, b.nums)


def test_merge_partial_upload_adds_only_new():
    base = small_history(NEW_DRAWS[:2])
    upload = small_history(NEW_DRAWS[1:])
    result = merge_histories(base, upload)
    assert (result.added, result.total) == (1, 3)
    assert result.history.labels == small_history(NEW_DRAWS).labels
    assert result.history.sha256 == hashlib.sha256(result.history_bytes).hexdigest()


def test_merge_identical_upload_adds_nothing():
    base = small_history(NEW_DRAWS)
    result = merge_histories(base, small_history(NEW_DRAWS))
    assert result.added == 0
    assert result.history_bytes == canonical_history_bytes(base.labels, base.nums)


def test_merge_conflict_lists_labels_up_to_five():
    base_entries = [("2026-10-01", f"{h:02d}:00", [1, 2, 3, 4, 5]) for h in range(7)]
    other = [(d, h, [9, 9, 9, 9, 9]) for d, h, _ in base_entries]
    with pytest.raises(HistoryConflict) as err:
        merge_histories(small_history(base_entries), small_history(other))
    message = str(err.value)
    assert "2026-10-01 00:00" in message and "2026-10-01 04:00" in message
    assert "2026-10-01 05:00" not in message
    assert isinstance(err.value, ValueError)


def test_merge_accepts_earlier_than_first_draw_and_dedupes():
    base = small_history(NEW_DRAWS[1:])
    upload = small_history([("2020-01-01", "10:00", [0, 0, 0, 0, 0]), *NEW_DRAWS])
    result = merge_histories(base, upload)
    assert result.added == 2
    assert result.history.labels[0] == "2020-01-01 10:00"
    assert len(set(result.history.labels)) == len(result.history.labels) == 4


def test_merge_enforces_total_cap(monkeypatch):
    monkeypatch.setattr("laboratorio.engine.history_merge.MAX_DRAWS", 2)
    base = small_history(NEW_DRAWS[:2])
    with pytest.raises(ValueError, match="draws"):
        merge_histories(base, small_history(NEW_DRAWS[1:]))
    assert MAX_DRAWS == 400_000


def test_invalid_upload_is_a_data_error():
    with pytest.raises(DataError):
        parse_history(b"not json")


# ------------------------------------------------------------------------- real frozen data


def test_parity_votes_for_matches_lab_cache(lab_data):
    direct = parity_votes_for(lab_data.history, lab_data.settings)
    assert np.array_equal(direct, lab_data.parity_votes())
    assert direct.dtype == np.int8


def test_source_from_history_equals_source_from_lab(lab_data):
    expected = source_from_lab(lab_data)
    got = source_from_history(lab_data.history, lab_data.history, lab_data.rankings)
    assert got.labels == expected.labels
    assert got.sha256 == expected.sha256
    for name in ("minutes", "results", "rank_pos"):
        assert np.array_equal(getattr(got, name), getattr(expected, name))
        assert getattr(got, name).dtype == getattr(expected, name).dtype


@pytest.fixture(scope="module")
def extended(lab_data):
    entries = [
        ("2026-09-26", "10:00", [1, 2, 3, 4, 5]),
        ("2026-09-26", "15:00", [10, 20, 30, 40, 50]),
        ("2026-09-27", "10:00", [60, 70, 80, 90, 99]),
    ]
    merged = merge_histories(lab_data.history, small_history(entries))
    assert merged.added == 3
    return merged


def test_extended_source_marks_new_draws_unranked(lab_data, extended):
    base = source_from_lab(lab_data)
    source = source_from_history(extended.history, lab_data.history, lab_data.rankings)
    assert len(source.labels) == len(base.labels) + 3
    assert source.sha256 == extended.history.sha256
    assert np.array_equal(source.rank_pos[: len(base.labels)], base.rank_pos)
    assert list(source.rank_pos[-3:]) == [-1, -1, -1]
    assert int((source.rank_pos >= 0).sum()) == len(lab_data.rankings.row_ids)


def test_extended_history_runs_with_parity_and_mix(lab_data, extended):
    source = source_from_history(extended.history, lab_data.history, lab_data.rankings)
    votes = parity_votes_for(extended.history, lab_data.settings)
    assert len(votes) == len(source.labels)
    parity = build_run_rows(
        source, lab_data.rankings, RunStrategy("parity", (), 50), parity_votes=votes
    )
    assert all(row.order is not None for row in parity.rows[-3:])
    system = next(iter(SYSTEMS))
    mix = build_run_rows(source, lab_data.rankings, RunStrategy("mix", ((system, 100),), 50))
    assert all(row.order is None for row in mix.rows[-3:])
    assert mix.ranked_draws == len(lab_data.rankings.row_ids)
    config = RunConfig(
        capital=2000, goal=2800, coverage=50, positions=5, prizes=(80, 8, 4, 2, 1), minimum_stake=1
    )
    assert run_sessions(config, parity.rows).totals.sessions > 0
    assert run_sessions(config, mix.rows).totals.sessions > 0
