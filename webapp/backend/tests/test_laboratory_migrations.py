import json
import sqlite3
import uuid

import pytest

from laboratorio.domain.laboratories import (
    create_laboratory_definition,
    initial_laboratory_definitions,
)
from laboratorio.storage.database import connection, initialize_database
from laboratorio.storage.quota import QuotaExceeded

_BOOTSTRAP_MARKER = "initial_laboratory_definitions_v1"


def _v16_database(path):
    from laboratorio.storage.database import _run_migrations

    with sqlite3.connect(path) as db:
        _run_migrations(db, 0, list(range(1, 17)))
        db.execute(
            "INSERT INTO reference_lab_runs "
            "(id, lab_id, contract_version, created_at, metadata_json, result_json) "
            "VALUES ('00000000-0000-0000-0000-000000000001', 'legacy-alias', 1, "
            "'2025-01-01T00:00:00.000000Z', '{\"legacy\":true}', '{\"result\":1}')"
        )
        db.execute(
            "INSERT INTO reference_lab_sessions VALUES "
            "('00000000-0000-0000-0000-000000000001', 0, '{\"session\":true}')"
        )
        db.execute("PRAGMA user_version=16")


def _raw_reference_run(db, run_id, lab_id, owner_id=None):
    db.execute(
        "INSERT INTO reference_lab_runs "
        "(id, lab_id, contract_version, created_at, metadata_json, result_json, "
        "owner_laboratory_id) VALUES (?, ?, 1, '2025-01-01T00:00:00.000000Z', '{}', '{}', ?)",
        (run_id, lab_id, owner_id),
    )
    db.execute(
        "INSERT INTO reference_lab_sessions VALUES (?, 0, '{}')",
        (run_id,),
    )


def _insert_definition(db, definition):
    snapshot = json.dumps(
        definition.to_mapping(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    db.execute(
        "INSERT INTO laboratory_definitions "
        "(id, name, name_key, definition_json, definition_bytes, created_at) "
        "VALUES (?, ?, ?, ?, ?, '2025-01-01T00:00:00.000000Z')",
        (
            definition.id,
            definition.name,
            definition.name.casefold(),
            snapshot,
            len(snapshot.encode("utf-8")),
        ),
    )


def _limited_quota(usage):
    return usage + max(1, usage // 19)


def test_fresh_database_bootstraps_version_17_and_fourteen_exact_seed_definitions(tmp_path):
    path = tmp_path / "fresh.db"
    initialize_database(path)

    with connection(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        rows = db.execute(
            "SELECT id, definition_json FROM laboratory_definitions ORDER BY rowid"
        ).fetchall()
        marker = db.execute(
            "SELECT state_value FROM storage_bootstrap_state WHERE state_key=?",
            (_BOOTSTRAP_MARKER,),
        ).fetchone()
        owners = db.execute(
            "SELECT DISTINCT owner_laboratory_id FROM reference_lab_runs"
        ).fetchall()

    expected = initial_laboratory_definitions()
    assert len(rows) == 14
    assert [(identifier, json.loads(snapshot)) for identifier, snapshot in rows] == [
        (definition.id, definition.to_mapping()) for definition in expected
    ]
    assert marker == ("complete",)
    assert owners == []
    with connection(path) as db:
        existing_key = db.execute("SELECT name_key FROM laboratory_definitions LIMIT 1").fetchone()[
            0
        ]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO laboratory_definitions "
                "(id, name, name_key, definition_json, definition_bytes, created_at) "
                "VALUES (?, ?, ?, '{}', 2, '2025-01-01T00:00:00.000000Z')",
                (str(uuid.UUID(int=999)), "Different Name", existing_key),
            )


def test_v16_upgrade_preserves_legacy_reference_run_session_and_null_owner(tmp_path):
    path = tmp_path / "v16.db"
    _v16_database(path)

    initialize_database(path)

    with connection(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 17
        assert db.execute(
            "SELECT id, lab_id, contract_version, created_at, metadata_json, result_json, "
            "owner_laboratory_id FROM reference_lab_runs"
        ).fetchall() == [
            (
                "00000000-0000-0000-0000-000000000001",
                "legacy-alias",
                1,
                "2025-01-01T00:00:00.000000Z",
                '{"legacy":true}',
                '{"result":1}',
                None,
            )
        ]
        assert db.execute(
            "SELECT run_id, ordinal, session_json FROM reference_lab_sessions"
        ).fetchall() == [("00000000-0000-0000-0000-000000000001", 0, '{"session":true}')]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_bootstrap_marker_prevents_reseeding_after_partial_or_total_user_deletion(
    tmp_path, monkeypatch
):
    path = tmp_path / "no-reseed.db"
    initialize_database(path)
    with connection(path) as db:
        db.execute(
            "DELETE FROM laboratory_definitions "
            "WHERE id=(SELECT id FROM laboratory_definitions LIMIT 1)"
        )
        db.commit()

    import laboratorio.storage.database as database

    monkeypatch.setattr(
        database,
        "initial_laboratory_definitions",
        lambda: (_ for _ in ()).throw(AssertionError("seed factory must not run again")),
    )
    initialize_database(path)
    with connection(path) as db:
        assert db.execute("SELECT count(*) FROM laboratory_definitions").fetchone()[0] == 13
        db.execute("DELETE FROM laboratory_definitions")
        db.commit()

    initialize_database(path)
    with connection(path) as db:
        assert db.execute("SELECT count(*) FROM laboratory_definitions").fetchone()[0] == 0
        assert db.execute(
            "SELECT state_value FROM storage_bootstrap_state WHERE state_key=?",
            (_BOOTSTRAP_MARKER,),
        ).fetchone() == ("complete",)


def test_bootstrap_backfill_failure_rolls_back_schema_seed_marker_and_version(
    tmp_path, monkeypatch
):
    path = tmp_path / "rollback.db"
    _v16_database(path)

    import laboratorio.storage.database as database

    definitions = initial_laboratory_definitions()

    def fail_after_two():
        yield from definitions[:2]
        raise RuntimeError("injected backfill failure")

    monkeypatch.setattr(database, "initial_laboratory_definitions", fail_after_two)
    with pytest.raises(RuntimeError, match="injected backfill failure"):
        initialize_database(path)

    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 16
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='laboratory_definitions'"
            ).fetchone()
            is None
        )
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='storage_bootstrap_state'"
            ).fetchone()
            is None
        )
        assert db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM reference_lab_sessions").fetchone()[0] == 1


def test_owner_foreign_key_deletes_only_owned_runs_and_cascades_sessions(tmp_path):
    path = tmp_path / "owners.db"
    initialize_database(path)
    seed_config = initial_laboratory_definitions()[0].config
    removed_definition = create_laboratory_definition("Owner to delete", seed_config)
    retained_definition = create_laboratory_definition("Retained owner", seed_config)
    removed_lab = removed_definition.to_reference_lab()
    retained_lab = retained_definition.to_reference_lab()
    assert removed_lab.lab_id == removed_definition.id
    assert retained_lab.lab_id == retained_definition.id

    with connection(path) as db:
        _insert_definition(db, removed_definition)
        _insert_definition(db, retained_definition)
        deleted_run = str(uuid.UUID(int=101))
        retained_run = str(uuid.UUID(int=102))
        legacy_run = str(uuid.UUID(int=103))
        trial_run = str(uuid.UUID(int=104))
        _raw_reference_run(db, deleted_run, removed_lab.lab_id, removed_definition.id)
        _raw_reference_run(db, retained_run, retained_lab.lab_id, retained_definition.id)
        _raw_reference_run(db, legacy_run, "legacy-static-id")
        _raw_reference_run(db, trial_run, "custom-trial-id")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            missing_id = str(uuid.UUID(int=999))
            _raw_reference_run(db, missing_id, missing_id, missing_id)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _raw_reference_run(db, str(uuid.UUID(int=106)), "wrong-alias", retained_definition.id)
        db.execute("DELETE FROM laboratory_definitions WHERE id=?", (removed_definition.id,))
        db.commit()

    with connection(path) as db:
        assert db.execute("SELECT id FROM reference_lab_runs ORDER BY id").fetchall() == [
            (retained_run,),
            (legacy_run,),
            (trial_run,),
        ]
        assert db.execute(
            "SELECT run_id FROM reference_lab_sessions ORDER BY run_id"
        ).fetchall() == [(retained_run,), (legacy_run,), (trial_run,)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_definition_json_utf8_bytes_are_counted_once_without_changing_run_metric(repo):
    from laboratorio.storage.repository import _laboratory_definition_bytes

    with connection(repo.path) as db:
        unicode_snapshot = json.dumps(
            {"name": "Prueba ñ"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        db.execute(
            "INSERT INTO laboratory_definitions "
            "(id, name, name_key, definition_json, definition_bytes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.UUID(int=1000)),
                "Prueba ñ",
                "prueba ñ",
                unicode_snapshot,
                len(unicode_snapshot.encode("utf-8")),
                "2025-01-01T00:00:00.000000Z",
            ),
        )
        db.commit()
        rows = db.execute(
            "SELECT definition_json, definition_bytes FROM laboratory_definitions"
        ).fetchall()
        expected = sum(len(snapshot.encode("utf-8")) for snapshot, _ in rows)
        assert any(len(snapshot.encode("utf-8")) != len(snapshot) for snapshot, _ in rows)
        assert all(size == len(snapshot.encode("utf-8")) for snapshot, size in rows)
        assert _laboratory_definition_bytes(db) == expected
        assert repo.admission_logical_bytes() == (
            repo.logical_experiment_bytes()
            + repo.profile_artifact_bytes()
            + repo.dataset_artifact_bytes()
            + repo.strategy_artifact_bytes()
            + repo.history_artifact_bytes()
            + repo.quota_status().run_artifact_bytes
            + expected
        )
    status = repo.quota_status()
    assert status.laboratory_definition_bytes == expected
    assert status.run_artifact_bytes == 0
    assert status.admission_logical_bytes == repo.admission_logical_bytes()


def test_seed_bootstrap_ignores_below_seed_quota_but_saved_run_write_is_rejected(repo, tmp_path):
    from laboratorio.storage.repository import Repository, _laboratory_definition_bytes

    config = {
        "name": "Demo",
        "rules": {"minimum_stake": 1, "positions": 1, "prizes": [3]},
        "strategy": {"coverage": 2},
        "conditions": {"capital": 10, "goal": 11},
        "window": {},
        "history": {},
    }
    summary = {
        "totals": {
            "sessions": 0,
            "goal": 0,
            "ruin": 0,
            "limit": 0,
            "incomplete": 0,
            "bets": 0,
            "wagered": 0,
            "paid": 0,
            "net": 0,
        },
        "detail": {
            "status": "complete",
            "total_sessions": 0,
            "stored_sessions": 0,
            "total_bets": 0,
            "stored_bets": 0,
        },
    }
    old_path = tmp_path / "persisted-low-quota.db"
    _v16_database(old_path)
    with sqlite3.connect(old_path) as db:
        db.execute("INSERT INTO settings_quota (id, quota_bytes) VALUES (1, 1)")
    initialize_database(old_path)
    upgraded = Repository(old_path)
    assert upgraded.admission_logical_bytes() > 1

    with connection(repo.path) as db:
        seed_bytes = _laboratory_definition_bytes(db)
    limit = _limited_quota(seed_bytes)
    with pytest.raises(QuotaExceeded):
        repo.create_run(
            "new-saved-run",
            "Demo",
            config,
            summary,
            [],
            quota_bytes=limit,
            quota_explicit=True,
        )
    assert repo.quota_status().run_artifact_bytes == 0


def test_reference_run_write_charges_seed_json_without_charging_run_metric(repo, monkeypatch):
    import laboratorio.storage.reference_lab_store as store
    from laboratorio.storage.repository import _laboratory_definition_bytes

    monkeypatch.setattr(store, "_validate_input", lambda *args: ("{}", "{}", []))
    with connection(repo.path) as db:
        seed_bytes = _laboratory_definition_bytes(db)
    with pytest.raises(QuotaExceeded):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "custom-trial",
            {},
            {},
            {},
            quota_bytes=_limited_quota(seed_bytes),
            quota_explicit=True,
        )
    assert repo.quota_status().run_artifact_bytes == 0

    run_id = str(uuid.UUID(int=2000))
    repo.create_reference_lab_run(
        run_id, "custom-trial", {}, {}, {}, quota_bytes=10**9, quota_explicit=True
    )
    with connection(repo.path) as db:
        assert db.execute(
            "SELECT owner_laboratory_id FROM reference_lab_runs WHERE id=?", (run_id,)
        ).fetchone() == (None,)
