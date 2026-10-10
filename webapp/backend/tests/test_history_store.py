"""History sources: migration 0014, repository accounting and the history catalog."""

import json
import sqlite3
import threading
from contextlib import closing

import numpy as np
import pytest

from laboratorio.engine.active_history import HistoryCatalog, HistoryImportError
from laboratorio.storage import database
from laboratorio.storage.database import initialize_database
from laboratorio.storage.quota import QuotaExceeded


def upload_bytes(entries):
    by_date = {}
    for day, hora, numbers in entries:
        by_date.setdefault(day, []).append({"hora": hora, "numeros": [f"{n:02d}" for n in numbers]})
    return json.dumps({"sorteos_por_fecha": by_date}).encode()


QUOTA = 50 * 1024**2
SHA_A = "a" * 64
SHA_B = "b" * 64


def tables(path):
    with closing(sqlite3.connect(path)) as db:
        return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def version(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def test_fresh_database_reaches_15(tmp_path):
    path = tmp_path / "a.db"
    initialize_database(path)
    assert version(path) == database.SCHEMA_VERSION
    assert {"history_sources", "history_active"} <= tables(path)


def test_v13_database_upgrades_in_place(tmp_path):
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute("BEGIN IMMEDIATE")
        script = "\n".join(
            database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 14)
        )
        db.executescript(script)
        db.execute("PRAGMA user_version = 13")
        db.commit()
    before = tables(path)
    with closing(sqlite3.connect(path)) as db:
        profiles_before = db.execute("SELECT count(*) FROM game_profiles").fetchone()[0]
    initialize_database(path)
    assert version(path) == database.SCHEMA_VERSION
    assert tables(path) == before | {
        "history_sources",
        "history_active",
        "saved_runs",
        "saved_run_sessions",
    }
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM game_profiles").fetchone()[0] == profiles_before


def import_row(repo, sha=SHA_A, raw=b"x" * 100, **overrides):
    args = {
        "draws": 10,
        "added_draws": 2,
        "first_label": "2020-01-01 10:00",
        "last_label": "2026-10-01 10:00",
        "quota_bytes": QUOTA,
        "quota_explicit": False,
    }
    args.update(overrides)
    return repo.import_history_source(sha, raw, **args)


def test_repository_import_activate_and_list(repo):
    assert repo.get_active_history_sha() is None
    assert repo.get_history_source(SHA_A) is None
    assert import_row(repo) is True
    assert repo.get_active_history_sha() == SHA_A
    assert repo.get_history_source(SHA_A)["raw_bytes"] == b"x" * 100
    assert import_row(repo, SHA_B, b"y") is True
    assert repo.get_active_history_sha() == SHA_B
    # Existing sha only reactivates.
    assert import_row(repo, SHA_A) is False
    assert repo.get_active_history_sha() == SHA_A
    listed = repo.list_history_sources()
    assert [item["sha256"] for item in listed] == [SHA_B, SHA_A]
    assert all("raw_bytes" not in item for item in listed)
    assert listed[0]["draws"] == 10 and listed[0]["added_draws"] == 2


def test_quota_unchanged_without_history_rows(repo):
    status = repo.quota_status(QUOTA)
    assert status.history_artifact_bytes == 0
    assert repo.history_artifact_bytes() == 0
    assert repo.admission_logical_bytes() == (
        repo.logical_experiment_bytes()
        + repo.profile_artifact_bytes()
        + repo.dataset_artifact_bytes()
        + repo.strategy_artifact_bytes()
    )
    assert status.admission_logical_bytes == repo.admission_logical_bytes()


def test_history_bytes_count_in_admission(repo):
    before = repo.admission_logical_bytes()
    import_row(repo, raw=b"z" * 1000)
    grown = repo.history_artifact_bytes()
    assert grown >= 1000 + 64
    assert repo.admission_logical_bytes() == before + grown
    status = repo.quota_status(QUOTA)
    assert status.history_artifact_bytes == grown
    assert status.admission_logical_bytes == before + grown


def test_import_over_quota_raises_and_writes_nothing(repo):
    limit = repo.admission_logical_bytes() + 5_000
    with pytest.raises(QuotaExceeded):
        import_row(repo, raw=b"q" * 10_000, quota_bytes=limit, quota_explicit=True)
    assert repo.list_history_sources() == []
    assert repo.get_active_history_sha() is None
    # A payload that fits the same quota is admitted.
    assert import_row(repo, raw=b"q" * 100, quota_bytes=limit, quota_explicit=True) is True


# ------------------------------------------------------------------------------ catalog


@pytest.fixture
def catalog(repo, lab_data):
    return HistoryCatalog(repo, lab_data, lab_data.settings)


UPLOAD = [
    ("2026-10-01", "10:00", [1, 2, 3, 4, 5]),
    ("2026-10-01", "15:00", [6, 7, 8, 9, 10]),
]


def test_active_defaults_to_frozen(catalog, lab_data):
    snap = catalog.active()
    assert snap.origin == "frozen" and snap.sha256 == lab_data.history.sha256
    assert snap.added_draws == 0 and snap.created_at is None
    assert snap.ranked_draws == len(lab_data.rankings.row_ids)
    assert catalog.snapshot(lab_data.history.sha256).origin == "frozen"
    assert catalog.snapshot("0" * 64) is None


def test_import_activates_merged_snapshot(catalog, lab_data):
    outcome = catalog.import_history(upload_bytes(UPLOAD))
    assert outcome.created is True and outcome.added == 2
    snap = outcome.snapshot
    assert snap.origin == "import" and snap.added_draws == 2
    assert len(snap.history.labels) == len(lab_data.history.labels) + 2
    assert snap.ranked_draws == len(lab_data.rankings.row_ids)
    assert list(snap.source.rank_pos[-2:]) == [-1, -1]
    assert catalog.active().sha256 == snap.sha256
    votes = catalog.parity_votes(snap)
    assert len(votes) == len(snap.history.labels) and votes.dtype == np.int8


def test_snapshot_persists_across_catalogs(catalog, repo, lab_data):
    sha = catalog.import_history(upload_bytes(UPLOAD)).snapshot.sha256
    fresh = HistoryCatalog(repo, lab_data, lab_data.settings)
    assert fresh.active().sha256 == sha
    snap = fresh.snapshot(sha)
    assert snap is not None and snap.history.sha256 == sha
    assert snap.history.labels[-2:] == ("2026-10-01 10:00", "2026-10-01 15:00")


def test_repeat_import_is_idempotent(catalog, repo):
    first = catalog.import_history(upload_bytes(UPLOAD))
    again = catalog.import_history(upload_bytes(UPLOAD))
    assert again.created is False and again.added == 0
    assert again.snapshot.sha256 == first.snapshot.sha256
    assert len(repo.list_history_sources()) == 1


def test_import_extends_the_active_import(catalog):
    catalog.import_history(upload_bytes(UPLOAD))
    outcome = catalog.import_history(upload_bytes([("2026-10-02", "10:00", [9, 8, 7, 6, 5])]))
    assert outcome.created and outcome.added == 1
    assert outcome.snapshot.added_draws == 1
    assert len(catalog.list_sources()) == 3  # frozen + two imports


def test_invalid_file_maps_to_invalid(catalog):
    with pytest.raises(HistoryImportError) as err:
        catalog.import_history(b"{}")
    assert err.value.kind == "invalid" and "formato" in err.value.message


def test_conflict_maps_to_conflict(catalog, lab_data):
    label = lab_data.history.labels[10]
    numbers = [int(n) for n in lab_data.history.nums[10]]
    changed = [(n + 1) % 100 for n in numbers]
    with pytest.raises(HistoryImportError) as err:
        catalog.import_history(upload_bytes([(label[:10], label[11:], changed)]))
    assert err.value.kind == "conflict" and label in err.value.message
    assert catalog.active().origin == "frozen"


def test_quota_maps_to_quota(repo, lab_data):
    from dataclasses import replace

    tiny = replace(lab_data.settings, quota_bytes=2 * 1024**2, quota_explicit=True)
    catalog = HistoryCatalog(repo, lab_data, tiny)
    with pytest.raises(HistoryImportError) as err:
        catalog.import_history(upload_bytes(UPLOAD))
    assert err.value.kind == "quota"


def test_list_sources_has_frozen_first(catalog, lab_data):
    catalog.import_history(upload_bytes(UPLOAD))
    listed = catalog.list_sources()
    assert listed[0]["origin"] == "frozen" and listed[0]["sha256"] == lab_data.history.sha256
    assert listed[0]["draws"] == len(lab_data.history.labels)
    assert listed[1]["origin"] == "import" and listed[1]["added_draws"] == 2


def test_concurrent_identical_imports_create_one(catalog):
    raw = upload_bytes(UPLOAD)
    results = []

    def worker():
        results.append(catalog.import_history(raw))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.created for r in results) == [False, True]
    assert len({r.snapshot.sha256 for r in results}) == 1
