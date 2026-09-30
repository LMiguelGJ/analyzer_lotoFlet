"""Frozen data access: history JSON, ranking NPZ and cached parity votes."""

import hashlib
import json

import numpy as np
import pytest

import laboratorio.engine.adapter as adapter
from laboratorio.engine.adapter import (
    DataError,
    load_history,
    load_rankings,
    open_lab_data,
    parse_history,
)
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256, Settings


def raw(days):
    return json.dumps({"sorteos_por_fecha": days}).encode()


def record(hora, numbers, url="https://premios.do/x"):
    return {"hora": hora, "numeros": [f"{n:02d}" for n in numbers], "source_url": url}


def test_parse_orders_days_and_hours_and_skips_empty_days():
    history = parse_history(
        raw(
            {
                "2025-01-02": [record("05:10", [1, 2, 3, 4, 5]), record("05:05", [6, 7, 8, 9, 0])],
                "2025-01-01": [record("21:55", [9, 9, 9, 9, 9])],
                "2025-01-03": [],
            }
        )
    )
    assert history.labels == ("2025-01-01 21:55", "2025-01-02 05:05", "2025-01-02 05:10")
    assert history.nums.tolist() == [[9] * 5, [6, 7, 8, 9, 0], [1, 2, 3, 4, 5]]
    assert history.nums.dtype == np.uint8


def test_identical_duplicates_merge_and_conflicts_stop_the_load():
    same = parse_history(
        raw(
            {
                "2025-01-01": [
                    record("05:05", [1, 2, 3, 4, 5]),
                    record("05:05", [1, 2, 3, 4, 5], "https://loteka.com.do/y"),
                ]
            }
        )
    )
    assert same.labels == ("2025-01-01 05:05",)
    with pytest.raises(DataError, match="Conflicting"):
        parse_history(
            raw(
                {"2025-01-01": [record("05:05", [1, 2, 3, 4, 5]), record("05:05", [1, 2, 3, 4, 6])]}
            )
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"2025-01-01": [{"hora": "5:05", "numeros": ["01"] * 5}]},
        {"2025-01-01": [{"hora": "05:05", "numeros": ["01"] * 4}]},
        {"2025-01-01": [{"hora": "05:05", "numeros": ["1", "02", "03", "04", "05"]}]},
        {"2025-02-30": [record("05:05", [1, 2, 3, 4, 5])]},
        {"2025-01-01": "not a list"},
    ],
)
def test_malformed_history_is_rejected(bad):
    with pytest.raises(DataError):
        parse_history(raw(bad))


def test_missing_files_and_changed_hashes_fail_with_clear_errors(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load_history(tmp_path / "missing.json", HISTORY_SHA256)
    changed = tmp_path / "history.json"
    changed.write_bytes(raw({"2025-01-01": [record("05:05", [1, 2, 3, 4, 5])]}))
    with pytest.raises(DataError, match="SHA-256"):
        load_history(changed, HISTORY_SHA256)
    history = load_history(changed, None)
    with pytest.raises(DataError, match="not found"):
        load_rankings(tmp_path / "missing.npz", RANKINGS_SHA256, history)


def synthetic_rankings(tmp_path, history, rows, systems=("transition", "cold")):
    rng = np.random.default_rng(1)
    arrays = {
        "row_ids": np.asarray(rows, dtype=np.int64),
        "timestamps": np.asarray([history.labels[r] for r in rows]),
    }
    for system in systems:
        arrays[f"ranking100__{system}"] = np.stack([rng.permutation(100) for _ in rows]).astype(
            np.uint8
        )
    path = tmp_path / "pos1.npz"
    np.savez(path, **arrays)
    return path


def small_history():
    days = {"2025-01-01": [record(f"05:{m:02d}", [m % 100, 1, 2, 3, 4]) for m in range(5, 60, 5)]}
    return parse_history(raw(days))


def test_rankings_align_with_history_rows(tmp_path):
    history = small_history()
    path = synthetic_rankings(tmp_path, history, [2, 3, 5])
    rankings = load_rankings(path, None, history)
    assert rankings.row_ids.tolist() == [2, 3, 5]
    family = rankings.family("transition")
    assert family.shape == (3, 100) and family.dtype == np.uint8
    with pytest.raises(DataError, match="unavailable"):
        rankings.family("logistic")


def test_rankings_use_the_verified_snapshot_after_path_replacement(tmp_path):
    history = small_history()
    path = synthetic_rankings(tmp_path, history, [2, 3])
    with np.load(path, allow_pickle=False) as archive:
        original = archive["ranking100__transition"].copy()
    rankings = load_rankings(path, None, history)

    replacement = tmp_path / "replacement.npz"
    np.savez(
        replacement,
        row_ids=np.asarray([2, 3], dtype=np.int64),
        timestamps=np.asarray([history.labels[2], history.labels[3]]),
        ranking100__transition=np.roll(original, 1, axis=1),
    )
    replacement.replace(path)
    assert np.array_equal(rankings.family("transition"), original)


def test_misaligned_or_invalid_rankings_are_rejected(tmp_path):
    history = small_history()
    path = tmp_path / "bad.npz"
    np.savez(
        path,
        row_ids=np.asarray([2, 3], dtype=np.int64),
        timestamps=np.asarray(["2025-01-01 05:15", "wrong"]),
    )
    with pytest.raises(DataError, match="timestamps"):
        load_rankings(path, None, history)

    np.savez(
        path,
        row_ids=np.asarray([3, 2], dtype=np.int64),
        timestamps=np.asarray([history.labels[3], history.labels[2]]),
    )
    with pytest.raises(DataError, match="increasing"):
        load_rankings(path, None, history)

    np.savez(
        path,
        row_ids=np.asarray([2], dtype=np.int64),
        timestamps=np.asarray([history.labels[2]]),
        ranking100__cold=np.zeros((1, 100), dtype=np.uint8),
    )
    with pytest.raises(DataError, match="permutation"):
        load_rankings(path, None, history).family("cold")


def parity_lab(tmp_path, data_dir):
    history = small_history()
    path = synthetic_rankings(tmp_path, history, [2, 3])
    rankings = load_rankings(path, None, history)
    return adapter.LabData(history, rankings, Settings.from_environment())


def test_parity_cache_is_reused_by_a_fresh_instance(tmp_path, data_dir, monkeypatch):
    lab = parity_lab(tmp_path, data_dir)
    original_compute = adapter.compute_parity_votes
    calls = []

    def count_compute(first_numbers):
        calls.append(True)
        return original_compute(first_numbers)

    monkeypatch.setattr(adapter, "compute_parity_votes", count_compute)
    expected = lab.parity_votes().copy()
    assert calls == [True]
    fresh = adapter.LabData(lab.history, lab.rankings, lab.settings)
    assert np.array_equal(fresh.parity_votes(), expected)
    assert calls == [True]


def test_parity_cache_recovers_from_shape_valid_changed_votes(tmp_path, data_dir, monkeypatch):
    lab = parity_lab(tmp_path, data_dir)
    expected = lab.parity_votes().copy()
    cache_path = next(lab.settings.cache_dir.glob("parity-*"))
    cached = np.load(cache_path, allow_pickle=False)
    if isinstance(cached, np.ndarray):
        altered = cached.copy()
        altered[0] = 1 - altered[0]
        np.save(cache_path, altered, allow_pickle=False)
    else:
        with cached as archive:
            arrays = {key: archive[key] for key in archive.files}
        arrays["votes"] = arrays["votes"].copy()
        arrays["votes"][0] = 1 - arrays["votes"][0]
        np.savez(cache_path, **arrays)

    original_compute = adapter.compute_parity_votes
    calls = []

    def count_compute(first_numbers):
        calls.append(True)
        return original_compute(first_numbers)

    monkeypatch.setattr(adapter, "compute_parity_votes", count_compute)
    fresh = adapter.LabData(lab.history, lab.rankings, lab.settings)
    assert np.array_equal(fresh.parity_votes(), expected)
    assert calls == [True]


@pytest.mark.parametrize("field", ["history_sha256", "algorithm"])
def test_parity_cache_recomputes_when_provenance_is_wrong(tmp_path, data_dir, monkeypatch, field):
    lab = parity_lab(tmp_path, data_dir)
    expected = lab.parity_votes().copy()
    cache_path = next(lab.settings.cache_dir.glob("parity-*.npz"))
    with np.load(cache_path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays[field] = np.asarray("wrong")
    np.savez(cache_path, **arrays)

    original_compute = adapter.compute_parity_votes
    calls = []

    def count_compute(first_numbers):
        calls.append(True)
        return original_compute(first_numbers)

    monkeypatch.setattr(adapter, "compute_parity_votes", count_compute)
    fresh = adapter.LabData(lab.history, lab.rankings, lab.settings)
    assert np.array_equal(fresh.parity_votes(), expected)
    assert calls == [True]


@pytest.mark.real_data
def test_frozen_history_matches_the_reference_loader():
    settings = Settings.from_environment()
    history = load_history(settings.history_path, HISTORY_SHA256)
    assert len(history.labels) == 105_426
    assert history.labels[0] == "2025-03-05 05:05"
    assert history.labels[-1] == "2026-09-25 18:20"
    # Fingerprint of the reference loader's (N, 5) int64 array.
    digest = hashlib.sha256(np.ascontiguousarray(history.nums.astype(np.int64)).tobytes())
    assert digest.hexdigest() == (
        "af0c827c84b2c995d836a4e66ff53e6a00687c67a21d798525c7fcbfe0973664"
    )


@pytest.mark.real_data
def test_frozen_rankings_and_parity_votes_match_the_reference(data_dir):
    lab = open_lab_data(Settings.from_environment())
    rows = lab.rankings.row_ids
    assert len(rows) == 65_235 and rows[0] == 33_648 and rows[-1] == 105_425
    assert lab.history.labels[rows[0]] == "2025-09-02 05:10"
    votes = lab.parity_votes()
    digest = hashlib.sha256(votes.astype(np.int8).tobytes()).hexdigest()
    assert digest == "5100eb5d81f2fe8c894741261a66c9674ac63d2dbb397db476458ef8164040ec"
    assert int(votes.sum()) == 76_369
    # A fresh instance can reuse the validated on-disk cache.
    assert np.array_equal(lab.parity_votes(), votes)
    assert any(data_dir.joinpath("cache").glob("parity-*.npz"))
