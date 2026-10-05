import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from laboratorio.domain.contracts import legacy_quiniela_80_profile
from laboratorio.domain.profile_archive import bind_archived_dataset
from laboratorio.engine.adapter import DataError
from laboratorio.importing.datasets import SavedDataset
from laboratorio.importing.records import ImportedRecord, ImportPreview
from laboratorio.settings import Settings


def archive(tmp_path, monkeypatch, rows, row_ids=(0, 2)):
    days = {}
    for day, time, numbers in rows:
        days.setdefault(day, []).append({"hora": time, "numeros": [f"{n:02d}" for n in numbers]})
    raw = json.dumps({"sorteos_por_fecha": days}).encode()
    history_sha = hashlib.sha256(raw).hexdigest()
    ranking_path = tmp_path / "rankings.npz"
    timestamps = np.asarray([f"{rows[i][0]} {rows[i][1]}" for i in row_ids])
    numbers = np.arange(100, dtype=np.uint8)
    ranks = {
        "cold": np.stack([np.roll(numbers, int(row_id) + 1) for row_id in row_ids]),
        "transition": np.stack([np.roll(numbers[::-1], int(row_id) + 2) for row_id in row_ids]),
        "freq_hist": np.stack([np.roll(numbers, int(row_id) + 3) for row_id in row_ids]),
        "topk": np.stack([np.roll(numbers[::-1], int(row_id) + 4) for row_id in row_ids]),
    }
    with ranking_path.open("wb") as stream:
        np.savez(
            stream,
            row_ids=np.asarray(row_ids, dtype=np.int64),
            timestamps=timestamps,
            ranking100__cold=ranks["cold"],
            ranking100__transition=ranks["transition"],
            ranking100__freq_hist=ranks["freq_hist"],
            ranking100__topk=ranks["topk"],
        )
    rankings_sha = hashlib.sha256(ranking_path.read_bytes()).hexdigest()
    monkeypatch.setattr("laboratorio.engine.adapter.HISTORY_SHA256", history_sha)
    monkeypatch.setattr("laboratorio.engine.adapter.RANKINGS_SHA256", rankings_sha)
    settings = Settings(tmp_path, tmp_path / "history.json", ranking_path, tmp_path / "dist")
    settings.history_path.write_bytes(raw)
    records = tuple(ImportedRecord(day, time, tuple(numbers)) for day, time, numbers in rows)
    canonical = json.dumps(
        {"profile": legacy_quiniela_80_profile().model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    dataset_sha = hashlib.sha256(canonical).hexdigest()
    preview = ImportPreview(records, history_sha, dataset_sha, len(rows), 0, (), 0, False, True)
    dataset = SavedDataset(dataset_sha, history_sha, canonical, raw, "now", preview)
    return settings, dataset


# B-STO-058: archive binding authenticates exact historical rows and rankings.
def test_binding_authenticates_source_and_exact_full_history_rows(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    bound = bind_archived_dataset(dataset, settings)
    assert bound.canonical_draw_count == 3
    assert bound.rank_row_ids == (0, 2)
    assert bound.canonical_draw_index(2) == 2
    assert bound.prior_cutoff(2) == "2025-01-01 01:00"
    assert bound.select("cold", 2, 3) == (97, 98, 99)
    assert bound.select("transition", 2, 3) == (3, 2, 1)
    assert bound.select("topk", 2, 2, system="freq_hist") == (95, 96)


# B-STO-059: incompatible embedded profiles are rejected despite matching source rows.
def test_binding_rejects_incompatible_profile_even_when_rows_and_source_match(
    tmp_path, monkeypatch
):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    incompatible = legacy_quiniela_80_profile().model_copy(update={"allows_repeats": False})
    canonical = json.dumps(
        {"profile": incompatible.model_dump(mode="json")}, sort_keys=True, separators=(",", ":")
    ).encode()
    rejected = replace(
        dataset,
        canonical_json=canonical,
        dataset_sha256=hashlib.sha256(canonical).hexdigest(),
    )
    with pytest.raises(DataError):
        bind_archived_dataset(rejected, settings)


# B-STO-060: imported draw values must match authenticated history at each label.
def test_binding_rejects_same_label_with_different_result(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    altered = replace(
        dataset,
        preview=replace(
            dataset.preview,
            records=(
                *dataset.preview.records[:1],
                ImportedRecord("2025-01-01", "01:00", (9, 1, 2, 3, 4)),
                *dataset.preview.records[2:],
            ),
        ),
    )
    with pytest.raises(DataError):
        bind_archived_dataset(altered, settings)


# B-STO-061: source hash and requested ranking row must be verified.
def test_binding_rejects_unverified_source_hash_and_missing_ranking_row(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    with pytest.raises(DataError):
        bind_archived_dataset(replace(dataset, source_sha256="0" * 64), settings)
    bound = bind_archived_dataset(dataset, settings)
    with pytest.raises(DataError, match="ranking"):
        bound.select("cold", 1, 3)


# B-STO-062: ranking timestamps bind to history; callers cannot supply asset paths.
def test_binding_rejects_timestamp_mismatch_and_forged_asset_path_argument(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    with np.load(settings.rankings_path) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    arrays["timestamps"][0] = "2025-01-01 09:00"
    with settings.rankings_path.open("wb") as stream:
        np.savez(stream, **arrays)
    monkeypatch.setattr(
        "laboratorio.engine.adapter.RANKINGS_SHA256",
        hashlib.sha256(settings.rankings_path.read_bytes()).hexdigest(),
    )
    with pytest.raises(DataError):
        bind_archived_dataset(dataset, settings)
    import inspect

    assert len(inspect.signature(bind_archived_dataset).parameters) == 2


# B-STO-063: ranking rows must be exact permutations of the universe.
def test_binding_rejects_nonpermutation_rankings(tmp_path, monkeypatch):
    rows = [("2025-01-01", f"0{i}:00", (i, 1, 2, 3, 4)) for i in range(3)]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    with np.load(settings.rankings_path) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    arrays["ranking100__cold"][0, 1] = arrays["ranking100__cold"][0, 0]
    with settings.rankings_path.open("wb") as stream:
        np.savez(stream, **arrays)
    monkeypatch.setattr(
        "laboratorio.engine.adapter.RANKINGS_SHA256",
        hashlib.sha256(settings.rankings_path.read_bytes()).hexdigest(),
    )
    with pytest.raises(DataError, match="permutation"):
        bind_archived_dataset(dataset, settings)


# B-STO-064: parity uses prior draws and does not require ranking rows.
def test_parity_selection_uses_prior_history_and_skips_no_rank_requirement(tmp_path, monkeypatch):

    rows = [("2025-01-01", f"0{i}:00", (first, 1, 2, 3, 4)) for i, first in enumerate((2, 3, 5))]
    settings, dataset = archive(tmp_path, monkeypatch, rows)
    bound = bind_archived_dataset(dataset, settings)
    assert bound.select("parity", 0, 50) == tuple(range(0, 100, 2))
    # Draw 2 is odd, but the causal vote sees the mixed even/odd prior history.
    assert bound.select("parity", 2, 50) == tuple(range(0, 100, 2))
    with pytest.raises(DataError):
        bound.select("cold", 1, 5)
