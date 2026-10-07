"""Durable snapshots, lifecycle and schema boundaries (isolated SQLite only)."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from laboratorio.api.simulations import _validate_public_experiment
from laboratorio.domain.contracts import (
    Conditions,
    ExperimentRequest,
    ExperimentStatus,
    GameProfile,
    Outcome,
    RunStatus,
    SelectorKind,
    StakingStyle,
    Strategy,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.domain.strategy_library import definition_snapshot, seed_presets, strategy_payload
from laboratorio.settings import Settings
from laboratorio.storage.database import SCHEMA_VERSION, UnsupportedSchema, initialize_database
from laboratorio.storage.quota import LOGICAL_MARGIN_BYTES, QuotaExceeded
from laboratorio.storage.repository import Repository


def request():
    return ExperimentRequest(
        name="Trial",
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=200, seed=42),
        strategies=(
            Strategy(
                name="Cold",
                selector=SelectorKind.SYSTEM,
                system="cold",
                coverage=1,
                staking=StakingStyle.FLAT,
            ),
        ),
    )


def result():
    bets = (
        Bet("2025-01-01 05:10", (7,), 1, 1, (7, 7, 8, 9, 10), 80, 179),
        Bet("2025-01-01 05:15", (8,), 2, 2, (8, 8, 9, 10, 11), 160, 337),
    )
    return SessionResult(Outcome.GOAL, 2, 3, 240, 337, bets)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "private" / "laboratorio.db"
    initialize_database(path)
    return Repository(path)


def create(repo, config_id=None):
    return repo.create_experiment(
        request(),
        history_id="history-q80",
        history_sha256="a" * 64,
        rankings_id="rankings-pos1",
        rankings_sha256="b" * 64,
        code_version="engine-v1",
        configuration_ids=(config_id,),
    )


# B-STO-009: durable legacy result reads never invoke the engine.
def test_reopen_complete_result_without_engine_or_source_files(repo, monkeypatch):
    config = repo.create_configuration("Saved", request().strategies[0])
    experiment = create(repo, config)
    repo.start_run(experiment, 0)
    repo.complete_run(experiment, 0, result())
    repo.complete_experiment(experiment)
    monkeypatch.setattr(
        "laboratorio.domain.session.run_session", lambda *a: pytest.fail("recalculated")
    )
    reopened = Repository(repo.path)
    saved = reopened.get_experiment(experiment)
    assert saved is not None
    assert saved.status is ExperimentStatus.COMPLETED
    assert saved.request_kind == "legacy" and saved.runs[0].result_kind == "legacy"
    assert isinstance(saved.request, ExperimentRequest)
    assert saved.request == request()
    assert saved.history_id == "history-q80" and saved.history_sha256 == "a" * 64
    assert saved.rankings_id == "rankings-pos1" and saved.rankings_sha256 == "b" * 64
    assert saved.code_version == "engine-v1" and saved.request.conditions.seed == 42
    assert saved.runs[0].status is RunStatus.COMPLETED
    assert saved.runs[0].result == result()
    assert saved.runs[0].configuration_id == config
    assert repo.list_experiments()[0] == saved


# B-STO-010: reject versioned data on the legacy result wire.
def test_legacy_result_refuses_versioned_envelope_without_rewriting_wire(repo):
    identifier = create(repo)
    repo.start_run(identifier, 0)
    repo.complete_run(identifier, 0, result())
    with sqlite3.connect(repo.path) as db:
        raw = db.execute(
            "SELECT result_json FROM runs WHERE experiment_id = ?", (identifier,)
        ).fetchone()[0]
        db.execute(
            "UPDATE runs SET result_json = ? WHERE experiment_id = ?",
            (raw[:-1] + ',"kind":"profile","schema_version":2}', identifier),
        )
    with pytest.raises(ValueError, match="legacy result wire"):
        repo.get_experiment(identifier)


# B-STO-011: configuration edits/deletes do not rewrite saved experiment history.
def test_configuration_mutation_and_deletion_keep_history(repo):
    config = repo.create_configuration("Saved", request().strategies[0])
    experiment = create(repo, config)
    repo.update_configuration(
        config, "Changed", request().strategies[0].model_copy(update={"name": "New"})
    )
    assert repo.get_configuration(config).strategy.name == "New"
    repo.start_run(experiment, 0)
    repo.complete_run(experiment, 0, result())
    repo.complete_experiment(experiment)
    repo.delete_configuration(config)
    assert repo.get_configuration(config) is None
    saved = repo.get_experiment(experiment)
    assert saved is not None
    assert saved.runs[0].configuration_id is None
    assert saved.request.strategies[0].name == "Cold"
    assert saved.runs[0].result == result()
    repo.delete_experiment(experiment)
    assert repo.get_experiment(experiment) is None
    assert repo.delete_experiment(experiment) is False


# B-STO-012: completion validation is atomic and completed runs are immutable.
def test_immutable_completed_runs_and_atomic_validation(repo):
    experiment = create(repo)
    repo.start_run(experiment, 0)
    broken = replace(result(), paid=999)
    with pytest.raises(ValueError, match="paid"):
        repo.complete_run(experiment, 0, broken)
    assert repo.get_experiment(experiment).runs[0].status is RunStatus.RUNNING
    with pytest.raises(ValueError, match="incomplete runs"):
        repo.complete_experiment(experiment)
    repo.complete_run(experiment, 0, result())
    repo.complete_experiment(experiment)
    with pytest.raises(ValueError):
        repo.complete_run(experiment, 0, result())
    with pytest.raises(ValueError):
        repo.mark_run(experiment, 0, RunStatus.FAILED)
    assert repo.get_experiment(experiment).runs[0].result == result()


# B-STO-013: pending/interrupted/held states never expose a result.
def test_incomplete_states_never_claim_completion(repo):
    experiment = create(repo)
    assert repo.get_experiment(experiment).status is ExperimentStatus.PENDING
    assert repo.get_experiment(experiment).runs[0].result is None
    repo.start_run(experiment, 0)
    repo.mark_run(experiment, 0, RunStatus.INTERRUPTED)
    repo.mark_experiment(experiment, ExperimentStatus.INTERRUPTED)
    saved = repo.get_experiment(experiment)
    assert saved is not None
    assert saved.status is ExperimentStatus.INTERRUPTED
    assert saved.runs[0].result is None
    with pytest.raises(ValueError):
        repo.complete_experiment(experiment)
    held = create(repo)
    repo.mark_experiment(held, ExperimentStatus.HELD)
    assert repo.get_experiment(held).status is ExperimentStatus.HELD


# B-STO-014: missing links and source identifiers are rejected without persistence.
def test_missing_records_and_invalid_configuration_link(repo):
    assert repo.get_experiment("missing") is None
    assert repo.get_configuration("missing") is None
    assert repo.delete_configuration("missing") is False
    with pytest.raises(ValueError, match="configuration"):
        create(repo, "missing")
    assert repo.list_experiments() == []
    with pytest.raises(ValueError, match="source IDs"):
        repo.create_experiment(
            request(),
            history_id="",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
    assert repo.list_experiments() == []


def comparison_request():
    first = request().strategies[0]
    second = first.model_copy(update={"name": "Second"})
    return request().model_copy(update={"strategies": (first, second)})


# B-STO-015: completed comparison runs survive cancellation of a peer.
def test_comparison_retains_completed_run_when_another_is_cancelled(repo):
    comparison = comparison_request()
    experiment = repo.create_experiment(
        comparison,
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="ranking",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    repo.start_run(experiment, 0)
    with pytest.raises(ValueError, match="already running"):
        repo.start_run(experiment, 1)
    with pytest.raises(ValueError, match="running experiment"):
        repo.delete_experiment(experiment)
    repo.complete_run(experiment, 0, result())
    repo.mark_run(experiment, 1, RunStatus.NOT_RUN)
    repo.mark_experiment(experiment, ExperimentStatus.CANCELLED)
    saved = Repository(repo.path).get_experiment(experiment)
    assert saved is not None
    assert saved.status is ExperimentStatus.CANCELLED
    assert [run.status for run in saved.runs] == [RunStatus.COMPLETED, RunStatus.NOT_RUN]
    assert saved.runs[0].result == result() and saved.runs[1].result is None
    with pytest.raises(ValueError):
        repo.complete_experiment(experiment)


# B-STO-016: failure finalization requires terminal runs and preserves successes.
def test_local_failure_finalize_requires_all_terminal_and_preserves_results(repo):
    comparison = comparison_request()
    comparison = comparison.model_copy(
        update={
            "strategies": (
                *comparison.strategies,
                request().strategies[0].model_copy(update={"name": "Third"}),
            )
        }
    )
    identifier = repo.create_experiment(
        comparison,
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    with pytest.raises(ValueError, match="not running"):
        repo.fail_run(identifier, 0)
    repo.start_run(identifier, 0)
    repo.complete_run(identifier, 0, result())
    with pytest.raises(ValueError, match="not running"):
        repo.fail_run(identifier, 0)
    repo.start_run(identifier, 1)
    with pytest.raises(ValueError, match="nonterminal"):
        repo.fail_experiment_after_runs(identifier)
    repo.fail_run(identifier, 1)
    with pytest.raises(ValueError, match="nonterminal"):
        repo.fail_experiment_after_runs(identifier)
    with pytest.raises(ValueError, match="incomplete runs"):
        repo.complete_experiment(identifier)
    repo.start_run(identifier, 2)
    repo.complete_run(identifier, 2, result())
    repo.fail_experiment_after_runs(identifier)
    saved = Repository(repo.path).get_experiment(identifier)
    assert saved is not None
    assert saved.status is ExperimentStatus.FAILED
    assert [r.status for r in saved.runs] == [
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.COMPLETED,
    ]
    assert saved.runs[0].result == saved.runs[2].result == result()
    assert saved.runs[1].result is None
    with pytest.raises(ValueError):
        repo.fail_experiment_after_runs(identifier)


# B-STO-017: a failed child insert rolls back the whole experiment.
def test_insert_failure_rolls_back_experiment_and_runs(repo):
    with sqlite3.connect(repo.path) as db:
        db.execute("""CREATE TRIGGER reject_second BEFORE INSERT ON runs
                   WHEN NEW.ordinal = 1 BEGIN SELECT RAISE(ABORT, 'reject second'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="reject second"):
        repo.create_experiment(
            comparison_request(),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="ranking",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "laboratorio" / "storage" / "migrations"


def _bootstrap_v1_schema(db):
    db.executescript(_MIGRATIONS_DIR.joinpath("0001_initial.sql").read_text(encoding="utf-8"))
    db.execute("PRAGMA user_version = 1")


# B-STO-018: v1 rows survive migration with NULL created_at; migration is repeatable.
def test_migration_from_v1_preserves_data_and_adds_created_at(tmp_path):
    path = tmp_path / "legacy_v1.db"
    with sqlite3.connect(path) as db:
        _bootstrap_v1_schema(db)
        db.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "exp1",
                "completed",
                request().model_dump_json(),
                "history",
                "a" * 64,
                "ranking",
                "b" * 64,
                "v1",
            ),
        )
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        row = db.execute("SELECT created_at FROM experiments WHERE id = 'exp1'").fetchone()
        assert row[0] is None
        assert db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 1
    # Repeated migration run over an already-migrated database is a safe no-op.
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 1
        row = db.execute("SELECT created_at FROM experiments WHERE id = 'exp1'").fetchone()
        assert row[0] is None
    repo = Repository(path)
    saved = repo.get_experiment("exp1")
    assert saved is not None
    assert saved.created_at is None


# B-STO-019: concurrent v2 upgrades preserve records and empty quota preference.
def test_migration_from_v2_preserves_records_and_empty_preference(tmp_path):
    path = tmp_path / "legacy_v2.db"
    with sqlite3.connect(path) as db:
        _bootstrap_v1_schema(db)
        db.executescript(_MIGRATIONS_DIR.joinpath("0002_experiment_created_at.sql").read_text())
        db.execute("PRAGMA user_version = 2")
        db.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "exp2",
                "interrupted",
                request().model_dump_json(),
                "history",
                "a" * 64,
                "ranking",
                "b" * 64,
                "v2",
                "2025-01-01T00:00:00Z",
            ),
        )
        db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", ("exp2", 0, None, "not_run", None))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize_database, [path] * 8))
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT count(*) FROM settings_quota").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
    saved = Repository(path).get_experiment("exp2")
    assert saved is not None and saved.created_at == "2025-01-01T00:00:00Z"


# B-STO-020: partial DDL failure rolls back version and columns for retry.
def test_migration_rolls_back_all_ddl_if_second_step_fails(tmp_path, monkeypatch):
    from laboratorio.storage import database

    path = tmp_path / "legacy_failed.db"
    with sqlite3.connect(path) as db:
        _bootstrap_v1_schema(db)
    original = Path.read_text

    def broken_second_step(file, *args, **kwargs):
        if file.name == "0002_experiment_created_at.sql":
            return "ALTER TABLE experiments ADD COLUMN created_at TEXT; SELECT * FROM missing;"
        return original(file, *args, **kwargs)

    monkeypatch.setattr(database.Path, "read_text", broken_second_step)
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert "created_at" not in {row[1] for row in db.execute("PRAGMA table_info(experiments)")}
    monkeypatch.setattr(database.Path, "read_text", original)
    initialize_database(path)
    assert Repository(path)


# B-STO-021: concurrent v1 upgrade creates the current schema only once.
def test_concurrent_upgrade_from_v1_is_idempotent(tmp_path):
    path = tmp_path / "shared_v1.db"
    with sqlite3.connect(path) as db:
        _bootstrap_v1_schema(db)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize_database, [path] * 8))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = [row[1] for row in db.execute("PRAGMA table_info(experiments)")]
        assert columns.count("created_at") == 1


# B-STO-022: fresh databases migrate in order and seed only the legacy profile.
def test_fresh_database_applies_migrations_in_order(tmp_path):
    path = tmp_path / "fresh.db"
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row[1] for row in db.execute("PRAGMA table_info(experiments)")}
        assert "created_at" in columns
        assert db.execute("SELECT count(*) FROM game_profiles").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM experiment_profiles").fetchone()[0] == 0
    assert Repository(path).list_game_profiles() == [legacy_quiniela_80_profile()]


def _legacy_with_completed_result(path, version):
    """Seed real pre-v4 rows without passing through current repository admission."""
    with sqlite3.connect(path) as db:
        _bootstrap_v1_schema(db)
        for step in range(2, version + 1):
            db.executescript(
                _MIGRATIONS_DIR.joinpath(
                    f"000{step}_" + {2: "experiment_created_at", 3: "settings"}[step] + ".sql"
                ).read_text(encoding="utf-8")
            )
            db.execute({2: "PRAGMA user_version = 2", 3: "PRAGMA user_version = 3"}[step])
        request_bytes = request().model_dump_json()
        # A historical amount above new descriptor caps is still readable.
        result_bytes = (
            '{"outcome":"goal","bets_count":0,"wagered":1000000001,'
            '"paid":1000000001,"final_balance":100,"bets":[]}'
        )
        fields = (
            "old",
            "completed",
            request_bytes,
            "history",
            "a" * 64,
            "ranking",
            "b" * 64,
            "old-engine",
        )
        if version >= 2:
            db.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*fields, "2025-01-01T00:00:00Z"),
            )
        else:
            db.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)", fields)
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?)", ("old", 0, None, "completed", result_bytes)
        )
        db.execute(
            "INSERT INTO experiments SELECT 'pending-old', 'pending', request_json, "
            "history_id, history_sha256, rankings_id, rankings_sha256, code_version"
            + (", created_at" if version >= 2 else "")
            + " FROM experiments WHERE id = 'old'"
        )
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?)", ("pending-old", 0, None, "pending", None)
        )
    return request_bytes, result_bytes


@pytest.mark.parametrize("version", [1, 2, 3])
# B-STO-023: historical backfill preserves request/result wire bytes and pending state.
def test_upgrade_backfills_all_historical_rows_without_rewriting_bytes(tmp_path, version):
    path = tmp_path / f"legacy_v{version}.db"
    request_bytes, result_bytes = _legacy_with_completed_result(path, version)
    initialize_database(path)
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        original = db.execute(
            "SELECT request_json, status FROM experiments WHERE id = 'old'"
        ).fetchone()
        assert original == (request_bytes, "completed")
        result_row = db.execute(
            "SELECT result_json FROM runs WHERE experiment_id = 'old'"
        ).fetchone()
        assert result_row[0] == result_bytes
        assert db.execute("SELECT count(*) FROM experiment_profiles").fetchone()[0] == 2
        assert (
            db.execute("SELECT status FROM experiments WHERE id = 'pending-old'").fetchone()[0]
            == "pending"
        )
    saved = Repository(path).get_experiment("old")
    assert saved is not None
    assert saved.profile == legacy_quiniela_80_profile()
    assert isinstance(saved.runs[0].result, SessionResult)
    assert saved.runs[0].result.wagered == 1_000_000_001


# B-STO-024: failed historical profile backfill leaves DDL/version/data untouched.
def test_failed_backfill_rolls_back_ddl_and_version(tmp_path, monkeypatch):
    from laboratorio.storage import database

    path = tmp_path / "backfill_failure.db"
    request_bytes, result_bytes = _legacy_with_completed_result(path, 3)
    original = Path.read_text

    def failing_backfill(file, *args, **kwargs):
        text = original(file, *args, **kwargs)
        if file.name == "0004_game_profiles.sql":
            return (
                text + "\nCREATE TRIGGER reject_backfill BEFORE INSERT ON experiment_profiles "
                "BEGIN SELECT RAISE(ABORT, 'backfill rejected'); END;\n"
            )
        return text

    monkeypatch.setattr(database.Path, "read_text", failing_backfill)
    with pytest.raises(sqlite3.IntegrityError, match="backfill rejected"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name='game_profiles'").fetchone()
            is None
        )
        assert (
            db.execute("SELECT request_json FROM experiments WHERE id = 'old'").fetchone()[0]
            == request_bytes
        )
        assert (
            db.execute("SELECT result_json FROM runs WHERE experiment_id = 'old'").fetchone()[0]
            == result_bytes
        )
    monkeypatch.setattr(database.Path, "read_text", original)
    initialize_database(path)
    restored = Repository(path).get_experiment("old")
    assert restored is not None and restored.profile == legacy_quiniela_80_profile()


# B-STO-025: v4 upgrade preserves legacy snapshots without inventing datasets.
def test_upgrade_v4_to_v5_preserves_legacy_bytes_without_backfill(tmp_path):
    from laboratorio.storage import database

    path = tmp_path / "old_v4.db"
    with sqlite3.connect(path) as db:
        scripts = "\n".join(
            database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 5)
        )
        db.executescript(scripts)
        db.execute("PRAGMA user_version = 4")
        profile = legacy_quiniela_80_profile()
        raw_profile = profile.model_dump_json()
        db.execute(
            "INSERT INTO game_profiles VALUES (?, ?, ?)",
            (profile.profile_id, profile.revision, raw_profile),
        )
        request_bytes = request().model_dump_json()
        db.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("old", "pending", request_bytes, "h", "a" * 64, "r", "b" * 64, "v1", None),
        )
        db.execute(
            "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
            ("old", profile.profile_id, profile.revision, raw_profile),
        )
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize_database, [path] * 8))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT count(*) FROM game_profiles").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM experiment_profiles").fetchone()[0] == 1
        assert db.execute("SELECT request_json FROM experiments").fetchone()[0] == request_bytes
        assert (
            db.execute("SELECT profile_json FROM experiment_profiles").fetchone()[0] == raw_profile
        )
        assert db.execute("SELECT count(*) FROM datasets").fetchone()[0] == 0


# B-STO-026: v5 wire bytes remain unchanged while receiving legacy discriminators.
def test_upgrade_v5_to_v8_keeps_request_and_result_bytes(tmp_path):
    from laboratorio.storage import database

    path = tmp_path / "old_v5.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "\n".join(database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 6))
        )
        db.execute("PRAGMA user_version = 5")
        profile = legacy_quiniela_80_profile()
        snapshot = profile.model_dump_json()
        db.execute(
            "INSERT INTO game_profiles VALUES (?, ?, ?)",
            (profile.profile_id, profile.revision, snapshot),
        )
        raw_request = request().model_dump_json()
        raw_result = (
            '{ "outcome":"goal", "bets_count":0,"wagered":0,"paid":0,'
            '"final_balance":100,"bets":[] }'
        )
        db.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("old", "completed", raw_request, "h", "a" * 64, "r", "b" * 64, "v1", None),
        )
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?)", ("old", 0, None, "completed", raw_result)
        )
        db.execute(
            "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
            ("old", profile.profile_id, profile.revision, snapshot),
        )
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute(
            "SELECT request_json, request_kind, request_schema_version FROM experiments"
        ).fetchone() == (raw_request, "legacy", 1)
        assert db.execute(
            "SELECT result_json, result_kind, result_schema_version FROM runs"
        ).fetchone() == (raw_result, "legacy", 1)
        assert db.execute("SELECT count(*) FROM experiment_profiles").fetchone()[0] == 1
    saved = Repository(path).get_experiment("old")
    assert saved is not None and saved.request_kind == "legacy"


# B-STO-027: migration 7 preserves profile wire and atomically rolls back.
def test_seventh_migration_preserves_schema6_wire_and_rollback(tmp_path, monkeypatch):
    from laboratorio.storage import database

    path = tmp_path / "old_v6.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "\n".join(database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 7))
        )
        db.execute("PRAGMA user_version = 6")
        profile = legacy_quiniela_80_profile()
        snapshot = profile.model_dump_json()
        db.execute(
            "INSERT INTO game_profiles VALUES (?, ?, ?)",
            (profile.profile_id, profile.revision, snapshot),
        )
        raw = ' { "name" : "preserved profile wire" } '
        db.execute(
            "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
            "rankings_id, rankings_sha256, code_version, request_kind) "
            "VALUES ('old', 'pending', ?, '', '', '', '', 'profile-v1', 'profile')",
            (raw,),
        )
        db.execute(
            "INSERT INTO runs (experiment_id, ordinal, status, result_kind) "
            "VALUES ('old', 0, 'pending', 'profile')"
        )
        db.execute(
            "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
            ("old", profile.profile_id, profile.revision, snapshot),
        )
    original = Path.read_text

    def broken(file, *args, **kwargs):
        if file.name == "0007_profile_cycling_storage.sql":
            return (
                "ALTER TABLE experiments ADD COLUMN request_schema_version INTEGER; "
                "SELECT * FROM missing;"
            )
        return original(file, *args, **kwargs)

    monkeypatch.setattr(database.Path, "read_text", broken)
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert "request_schema_version" not in {
            column[1] for column in db.execute("PRAGMA table_info(experiments)")
        }
        assert db.execute("SELECT request_json FROM experiments").fetchone()[0] == raw
    monkeypatch.setattr(database.Path, "read_text", original)
    initialize_database(path)
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute(
            "SELECT request_json, request_schema_version FROM experiments"
        ).fetchone() == (raw, 1)
        assert db.execute("SELECT result_json, result_schema_version FROM runs").fetchone() == (
            None,
            None,
        )


# B-STO-028: migrations 5/6 fail closed at their previous schema version.
def test_sixth_migration_failure_rolls_back_v5(tmp_path, monkeypatch):
    from laboratorio.storage import database

    path = tmp_path / "failed_v6.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "\n".join(database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 6))
        )
        db.execute("PRAGMA user_version = 5")
    original = Path.read_text

    def broken(file, *args, **kwargs):
        if file.name == "0006_profile_requests.sql":
            return "ALTER TABLE experiments ADD COLUMN request_kind TEXT; SELECT * FROM missing;"
        return original(file, *args, **kwargs)

    monkeypatch.setattr(database.Path, "read_text", broken)
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert "request_kind" not in {r[1] for r in db.execute("PRAGMA table_info(experiments)")}
    monkeypatch.setattr(database.Path, "read_text", original)
    initialize_database(path)
    assert Repository(path)


# B-STO-028: migrations 5/6 fail closed at their previous schema version.
def test_fifth_migration_failure_rolls_back_v4(tmp_path, monkeypatch):
    from laboratorio.storage import database

    path = tmp_path / "failed_v5.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "\n".join(database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 5))
        )
        db.execute("PRAGMA user_version = 4")
    original = Path.read_text

    def broken(file, *args, **kwargs):
        if file.name == "0005_datasets.sql":
            return "CREATE TABLE datasets (id TEXT); SELECT * FROM missing;"
        return original(file, *args, **kwargs)

    monkeypatch.setattr(database.Path, "read_text", broken)
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4
        assert db.execute("SELECT name FROM sqlite_master WHERE name='datasets'").fetchone() is None
    monkeypatch.setattr(database.Path, "read_text", original)
    initialize_database(path)
    assert Repository(path)


# B-STO-029/030: immutable profile revisions and experiment snapshots round-trip/account exactly.
def test_profile_versions_are_inert_immutable_and_roundtrip(repo):
    legacy = legacy_quiniela_80_profile()
    custom = GameProfile.model_validate(
        {
            **legacy.model_dump(),
            "profile_id": "another-game",
            "best_rule": "maximum-payout/v1",
            "universe_size": 60,
            "positions": 3,
            "allows_repeats": False,
            "multipliers": legacy.model_dump()["multipliers"][:3],
            "max_coverage": 10,
            "maximum_stake": 100,
            "max_exposure": 100,
        }
    )
    base_profile_bytes = repo.profile_artifact_bytes()
    assert repo.create_game_profile(custom) == custom
    custom_bytes = len(custom.model_dump_json().encode("utf-8"))
    assert repo.profile_artifact_bytes() == base_profile_bytes + custom_bytes
    assert repo.create_game_profile(custom) == custom  # identical retries are no-ops
    assert repo.profile_artifact_bytes() == base_profile_bytes + custom_bytes
    second = GameProfile.model_validate({**custom.model_dump(), "revision": 2})
    assert repo.create_game_profile(second) == second
    assert Repository(repo.path).list_game_profiles() == [custom, second, legacy]
    assert repo.get_game_profile("another-game", 2) == second
    assert repo.get_game_profile("another-game", 3) is None
    conflict = GameProfile.model_validate({**custom.model_dump(), "universe_size": 61})
    with pytest.raises(ValueError, match="different content"):
        repo.create_game_profile(conflict)
    # Pydantic model_copy(update=...) skips validators; repository admission must not.
    with pytest.raises(ValueError, match="maximum stake exceeds"):
        repo.create_game_profile(custom.model_copy(update={"max_exposure": 10}))
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                "UPDATE game_profiles SET profile_json = ? WHERE profile_id = ?",
                (second.model_dump_json(), custom.profile_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("DELETE FROM game_profiles WHERE profile_id = ?", (custom.profile_id,))
    before_snapshot = repo.profile_artifact_bytes()
    identifier = create(repo)
    assert repo.get_experiment(identifier).profile == legacy
    assert repo.profile_artifact_bytes() == before_snapshot + len(
        legacy.model_dump_json().encode("utf-8")
    )
    repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                "UPDATE experiment_profiles SET profile_json = ? WHERE experiment_id = ?",
                (second.model_dump_json(), identifier),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM experiment_profiles WHERE experiment_id = ?", (identifier,))
    assert repo.delete_experiment(identifier)
    assert repo.profile_artifact_bytes() == before_snapshot
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM experiment_profiles").fetchone()[0] == 0
    assert repo.get_game_profile(custom.profile_id, 2) == second


# B-STO-031: bounded profile paging uses stable keys and validates row identity.
def test_profile_page_uses_stable_key_order_and_validates_stored_identity(repo, monkeypatch):
    legacy = legacy_quiniela_80_profile()
    custom = GameProfile.model_validate(
        {**legacy.model_dump(), "profile_id": "custom", "best_rule": "maximum-payout/v1"}
    )
    repo.create_game_profile(custom)
    repo.create_game_profile(GameProfile.model_validate({**custom.model_dump(), "revision": 2}))
    monkeypatch.setattr(repo, "get_game_profile", lambda *args: pytest.fail("per-row lookup"))
    monkeypatch.setattr(repo, "list_game_profiles", lambda: pytest.fail("load-all lookup"))
    assert repo.page_game_profiles(0, 1) == (3, [custom])
    assert repo.page_game_profiles(1, 1)[1][0].revision == 2
    assert repo.page_game_profiles(2, 1) == (3, [legacy])
    assert repo.page_game_profiles(3, 1) == (3, [])
    for offset, limit in ((-1, 1), (0, 0), (0, 101), (True, 1), (0, True)):
        with pytest.raises(ValueError, match="offset and limit"):
            repo.page_game_profiles(offset, limit)
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER game_profiles_no_update")
        db.execute(
            "UPDATE game_profiles SET profile_json = ? WHERE profile_id = 'custom'",
            (legacy.model_dump_json(),),
        )
    with pytest.raises(ValueError, match="corrupt game profile identity"):
        repo.page_game_profiles(0, 1)


# B-STO-032: missing snapshots cannot fall back to the legacy profile.
def test_missing_or_corrupt_snapshot_is_integrity_error(repo):
    identifier = create(repo)
    with sqlite3.connect(repo.path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("DROP TRIGGER experiment_profiles_no_delete")
        db.execute("DELETE FROM experiment_profiles WHERE experiment_id = ?", (identifier,))
    for read in (lambda: repo.get_experiment(identifier), lambda: repo.search_experiments(0, 20)):
        with pytest.raises(ValueError, match="missing or corrupt"):
            read()


@pytest.mark.parametrize("corruption", ["invalid-document", "different-version"])
# B-STO-032: invalid or revision-mismatched snapshots fail closed.
def test_corrupt_profile_snapshot_never_silently_falls_back_to_legacy(repo, corruption):
    identifier = create(repo)
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER experiment_profiles_no_update")
        if corruption == "invalid-document":
            db.execute(
                "UPDATE experiment_profiles SET profile_json = '{}' WHERE experiment_id = ?",
                (identifier,),
            )
        else:
            db.execute(
                "UPDATE experiment_profiles SET revision = 2 WHERE experiment_id = ?",
                (identifier,),
            )
    with pytest.raises(ValueError, match="missing or corrupt"):
        repo.get_experiment(identifier)


# B-STO-033: created_at is UTC ISO-8601 and immutable across lifecycle changes.
def test_create_experiment_sets_created_at_in_utc_iso8601(repo):
    identifier = create(repo)
    saved = repo.get_experiment(identifier)
    assert saved is not None
    assert saved.created_at is not None
    # UTC ISO 8601 with an explicit Z suffix; datetime.fromisoformat needs the offset spelled out.
    parsed = datetime.fromisoformat(saved.created_at.replace("Z", "+00:00"))
    offset = parsed.utcoffset()
    assert offset is not None and offset.total_seconds() == 0
    repo.start_run(identifier, 0)
    repo.finish_incomplete(identifier, ExperimentStatus.CANCELLED)
    assert repo.get_experiment(identifier).created_at == saved.created_at


# B-STO-034: experiment search literals, filters, sorting and pagination.
def test_search_experiments_filters_sorts_and_paginates(repo):
    first = repo.create_experiment(
        request().model_copy(update={"name": "Alpha"}),
        history_id="h",
        history_sha256="a" * 64,
        rankings_id="r",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    second = repo.create_experiment(
        request().model_copy(update={"name": "Beta%wild"}),
        history_id="h",
        history_sha256="a" * 64,
        rankings_id="r",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    third = repo.create_experiment(
        request().model_copy(update={"name": "Gamma_under"}),
        history_id="h",
        history_sha256="a" * 64,
        rankings_id="r",
        rankings_sha256="b" * 64,
        code_version="v1",
    )

    # Wildcard injection: a literal % or _ in the search term must not act as a SQL wildcard.
    total, rows = repo.search_experiments(0, 20, name_contains="%")
    assert total == 1 and [r.id for r in rows] == [second]
    total, rows = repo.search_experiments(0, 20, name_contains="_")
    assert total == 1 and [r.id for r in rows] == [third]

    # Case-insensitive contains.
    total, rows = repo.search_experiments(0, 20, name_contains="ALPHA")
    assert total == 1 and [r.id for r in rows] == [first]

    # Search is case-insensitive for names beyond SQLite's ASCII-only LIKE behavior.
    accent = repo.create_experiment(
        request().model_copy(update={"name": "Éclair"}),
        history_id="h",
        history_sha256="a" * 64,
        rankings_id="r",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    total, rows = repo.search_experiments(0, 20, name_contains="éCLAIR")
    assert total == 1 and [r.id for r in rows] == [accent]

    # Status filter with only real execution statuses.
    total, rows = repo.search_experiments(0, 20, status="pending")
    assert total == 4

    # Sort by name ascending.
    total, rows = repo.search_experiments(0, 20, sort="name", order="asc")
    assert [r.id for r in rows] == [first, second, third, accent]

    # Empty result for a name that matches nothing.
    total, rows = repo.search_experiments(0, 20, name_contains="nope-nothing-here")
    assert total == 0 and rows == []

    # Pagination with a filter: total reflects the filtered set, not the full table.
    total, rows = repo.search_experiments(0, 1, status="pending", sort="name", order="asc")
    assert total == 4 and [r.id for r in rows] == [first]
    total, rows = repo.search_experiments(1, 1, status="pending", sort="name", order="asc")
    assert total == 4 and [r.id for r in rows] == [second]


# B-STO-035: default search order deterministically breaks timestamp ties by id.
def test_search_experiments_default_order_is_created_at_desc_with_id_tiebreak(repo):
    ids = [create(repo) for _ in range(3)]
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE experiments SET created_at = '2025-01-01T00:00:00.000000Z'")
    total, rows = repo.search_experiments(0, 20)
    assert total == 3
    # An explicit timestamp tie falls back to id descending, a deterministic tiebreak.
    assert [r.id for r in rows] == sorted(ids, reverse=True)


# B-STO-034: combined search preserves literal escapes and stable pages.
def test_search_combined_filters_literal_escape_and_stable_page(repo):
    ids = {}
    for name in ("A\\B", "A%B", "A_B", "A plain"):
        ids[name] = repo.create_experiment(
            request().model_copy(update={"name": name}),
            history_id="h",
            history_sha256="a" * 64,
            rankings_id="r",
            rankings_sha256="b" * 64,
            code_version="v1",
        )
    repo.finish_incomplete(ids["A%B"], ExperimentStatus.CANCELLED)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE experiments SET created_at = '2025-01-01T00:00:00.000000Z'")
    total, rows = repo.search_experiments(0, 10, name_contains="\\")
    assert total == 1 and [row.id for row in rows] == [ids["A\\B"]]
    total, rows = repo.search_experiments(0, 10, name_contains="%", status="cancelled")
    assert total == 1 and [row.id for row in rows] == [ids["A%B"]]
    total, rows = repo.search_experiments(2, 1, sort="created_at", order="desc")
    assert total == 4 and [row.id for row in rows] == sorted(ids.values(), reverse=True)[2:3]
    total, rows = repo.search_experiments(8, 1, status="pending")
    assert total == 3 and rows == []
    assert repo.get_experiment(ids["A%B"]).created_at == "2025-01-01T00:00:00.000000Z"


# B-STO-036: search rejects invalid sort/order/status/pagination values.
def test_search_experiments_rejects_invalid_sort_or_status(repo):
    with pytest.raises(ValueError):
        repo.search_experiments(0, 20, sort="not_a_column")
    with pytest.raises(ValueError):
        repo.search_experiments(0, 20, order="sideways")
    with pytest.raises(ValueError):
        repo.search_experiments(0, 20, status="not_a_status")
    for offset, limit in ((-1, 20), (0, 0), (0, 101)):
        with pytest.raises(ValueError):
            repo.search_experiments(offset, limit)


# B-STO-037: initialization is idempotent and refuses unsupported/nonempty v0 files.
def test_initialization_repeat_and_unsupported_version(tmp_path):
    path = tmp_path / "private" / "lab.db"
    assert not path.exists()
    initialize_database(path)
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        db.execute("PRAGMA user_version = 99")
    with pytest.raises(UnsupportedSchema, match="99"):
        initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99
    with pytest.raises(UnsupportedSchema, match="99"):
        Repository(path)
    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as db:
        db.execute("CREATE TABLE legacy (id INTEGER)")
    with pytest.raises(UnsupportedSchema, match="version 0"):
        initialize_database(legacy)
    with sqlite3.connect(legacy) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='legacy'").fetchone()


# B-STO-038: concurrent initialization is safe and repeatable.
def test_concurrent_initialization_is_repeatable(tmp_path):
    path = tmp_path / "shared.db"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize_database, [path] * 8))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='runs'").fetchone()[0] == 1


# B-STO-038: Repository opens only an explicitly initialized database.
def test_repository_does_not_initialize_implicitly(tmp_path):
    path = tmp_path / "missing" / "lab.db"
    with pytest.raises(FileNotFoundError):
        Repository(path)
    assert not path.exists()


# B-STO-039: default database path is under local application data, not the repo.
def test_settings_default_not_under_repository(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/example/AppData/Local")
    monkeypatch.delenv("LABORATORIO_DATA_DIR", raising=False)
    assert (
        Settings.from_environment()
        .database_path.as_posix()
        .endswith("AppData/Local/LaboratorioQuiniela/laboratorio.db")
    )


# B-STO-040/B-FLAKY-010: preserve v7 bytes through v12 and verify the v9 rollback boundary.
def test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically(tmp_path, monkeypatch):
    from laboratorio.storage import database

    def v7_database(path):
        with sqlite3.connect(path) as db:
            db.executescript(
                "\n".join(database._MIGRATIONS[v].read_text(encoding="utf-8") for v in range(1, 8))
            )
            db.execute("PRAGMA user_version = 7")
            profile = legacy_quiniela_80_profile()
            snapshot = profile.model_dump_json()
            db.execute(
                "INSERT INTO game_profiles VALUES (?, ?, ?)",
                (profile.profile_id, profile.revision, snapshot),
            )
            request_bytes = '{ "legacy" : "request bytes" }'
            result_bytes = '{ "legacy" : "result bytes" }'
            db.execute(
                "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, request_kind, request_schema_version) "
                "VALUES ('legacy', 'completed', ?, 'h', 'a', 'r', 'b', 'v1', 'legacy', 1)",
                (request_bytes,),
            )
            db.execute(
                "INSERT INTO runs (experiment_id, ordinal, status, result_json, result_kind, "
                "result_schema_version) VALUES ('legacy', 0, 'completed', ?, 'legacy', 1)",
                (result_bytes,),
            )
            db.execute(
                "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
                ("legacy", profile.profile_id, profile.revision, snapshot),
            )
            db.execute("INSERT INTO configurations VALUES ('unrelated', 'kept', '{}')")
        return request_bytes, result_bytes, snapshot

    path = tmp_path / "v7.db"
    request_bytes, result_bytes, snapshot = v7_database(path)
    initialize_database(path)
    with sqlite3.connect(path) as db:
        # Initialization upgrades through the current schema, not the historical v9 target.
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 13
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            db.execute("SELECT request_json FROM experiments WHERE id='legacy'").fetchone()[0]
            == request_bytes
        )
        assert (
            db.execute("SELECT result_json FROM runs WHERE experiment_id='legacy'").fetchone()[0]
            == result_bytes
        )
        assert (
            db.execute(
                "SELECT profile_json FROM experiment_profiles WHERE experiment_id='legacy'"
            ).fetchone()[0]
            == snapshot
        )
        assert (
            db.execute("SELECT name FROM configurations WHERE id='unrelated'").fetchone()[0]
            == "kept"
        )
        db.execute(
            "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
            "rankings_id, rankings_sha256, code_version, request_kind, request_schema_version) "
            "VALUES ('audaz', 'pending', '{}', '', '', '', '', 'profile-v3', 'profile', 3)"
        )
        db.execute(
            "INSERT INTO runs (experiment_id, ordinal, status, result_kind) "
            "VALUES ('audaz', 0, 'pending', 'profile')"
        )
        db.execute("UPDATE experiments SET request_schema_version=4 WHERE id='audaz'")
        db.execute("UPDATE experiments SET request_schema_version=3 WHERE id='audaz'")
        # Schema 12 also stores v5 batches; v9's narrower CHECK is verified below
        # against the actual v7→v9 migration boundary, not the current schema.

    # The v7→v9 contract is checked at its migration boundary. The current
    # initializer continues to v12, where request schema 5 is valid for batches.
    boundary = tmp_path / "v7-to-v9.db"
    v7_database(boundary)
    with sqlite3.connect(boundary) as db:
        db.executescript(database._MIGRATIONS[8].read_text(encoding="utf-8"))
        db.executescript(database._MIGRATIONS[9].read_text(encoding="utf-8"))
        db.execute("PRAGMA user_version = 9")
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE experiments SET request_schema_version = 5 WHERE id = 'legacy'")

    failed = tmp_path / "v7-rollback.db"
    v7_database(failed)
    original = Path.read_text

    def broken(file, *args, **kwargs):
        text = original(file, *args, **kwargs)
        if file.name == "0009_profile_recovery_storage.sql":
            return text + "\nSELECT * FROM missing_migration_table;"
        return text

    monkeypatch.setattr(database.Path, "read_text", broken)
    with pytest.raises(sqlite3.OperationalError, match="missing_migration_table"):
        initialize_database(failed)
    with sqlite3.connect(failed) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 7
        assert (
            db.execute("SELECT request_json FROM experiments WHERE id='legacy'").fetchone()[0]
            == request_bytes
        )
        assert (
            db.execute("SELECT result_json FROM runs WHERE experiment_id='legacy'").fetchone()[0]
            == result_bytes
        )
        assert "experiments_v9" not in {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


# B-STO-001: exercise the populated v10→current path and verify the migration-11 columns.
def test_migration_11_preserves_populated_v10_rows_and_foreign_keys(tmp_path):
    from laboratorio.storage import database

    path = tmp_path / "populated-v10.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "\n".join(
                database._MIGRATIONS[version].read_text(encoding="utf-8")
                for version in range(1, 11)
            )
        )
        db.execute("PRAGMA user_version = 10")
        db.execute(
            "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
            "rankings_id, rankings_sha256, code_version, request_kind, request_schema_version) "
            "VALUES ('v10', 'pending', ?, 'h', 'a', 'r', 'b', 'v10', 'legacy', 1)",
            (request().model_dump_json(),),
        )
        db.execute(
            "INSERT INTO runs (experiment_id, ordinal, status, result_json, result_kind, "
            "result_schema_version) VALUES ('v10', 0, 'completed', ?, 'legacy', 1)",
            (
                '{"outcome":"goal","bets_count":0,"wagered":0,"paid":0,'
                '"final_balance":100,"bets":[]}',
            ),
        )
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute(
            "SELECT request_schema_version FROM experiments WHERE id='v10'"
        ).fetchone() == (1,)
        assert db.execute(
            "SELECT result_schema_version FROM runs WHERE experiment_id='v10'"
        ).fetchone() == (1,)


# B-STO-002: exact canonical strategy snapshot survives close/reopen.
def test_strategy_snapshot_hash_and_execution_state_survive_reopen(repo):
    definition = StrategyDefinition.static_numbers("Aurea", (7, 13))
    saved = repo.create_strategy(definition)
    assert saved["revision"] == 1
    assert saved["definition_sha256"] == definition_snapshot(definition)[1]
    assert repo.page_strategies(0, 10)[0] == 1
    reopened = Repository(repo.path).get_strategy(saved["id"])
    assert reopened == saved
    assert reopened["execution_available"] is False
    assert "ProfileBatchRequestV5" in reopened["execution_unavailable_reason"]


# B-STO-003: revision writes use compare-and-swap and preserve old wire.
def test_strategy_revision_compare_and_swap_preserves_old_snapshot(repo):
    first = repo.create_strategy(StrategyDefinition.static_numbers("First", (7,)))
    second = repo.append_strategy_revision(
        first["id"], 1, StrategyDefinition.static_numbers("Second", (8,))
    )
    assert second["revision"] == 2
    assert repo.get_strategy_revision(first["id"], 1)["definition_json"] == first["definition_json"]
    with pytest.raises(ValueError, match="revision conflict"):
        repo.append_strategy_revision(
            first["id"], 1, StrategyDefinition.static_numbers("Lost", (9,))
        )
    assert repo.get_strategy(first["id"])["latest_revision"] == 2


# B-STO-004: built-in presets are idempotent and originals are copy-only.
def test_strategy_presets_are_idempotent_protected_and_copyable(repo):
    first = seed_presets(repo)
    again = seed_presets(repo)
    assert len(first) == 3 and [row["id"] for row in first] == [row["id"] for row in again]
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE strategies SET latest_revision=2 WHERE id=?", (first[0]["id"],))
    with pytest.raises(ValueError, match="protected"):
        repo.append_strategy_revision(
            first[0]["id"], 1, StrategyDefinition.static_numbers("No", (1,))
        )
    copied = repo.create_strategy(StrategyDefinition.static_numbers("Copy", (1,)))
    assert copied["id"] not in {row["id"] for row in first}


# B-STO-005: invalid definitions and modified persisted wires fail closed.
def test_strategy_definition_tampering_fails_closed(repo):
    with pytest.raises(ValueError):
        strategy_payload({"definition_version": 1, "unknown": True})
    saved = repo.create_strategy(StrategyDefinition.static_numbers("Valid", (1,)))
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER strategy_revisions_no_update")
        db.execute(
            "UPDATE strategy_revisions SET definition_json='{}' WHERE strategy_id=?",
            (saved["id"],),
        )
    with pytest.raises(ValueError, match="corrupt"):
        repo.get_strategy(saved["id"])


# B-STO-006: UTF-8 strategy bytes are admitted exactly and failed transactions roll back.
def test_strategy_utf8_artifact_bytes_and_failed_write_rollback(repo):
    saved = repo.create_strategy(StrategyDefinition.static_numbers("ñ strategy", (7,)))
    expected = sum(len(saved[key].encode("utf-8")) for key in ("id", "name", "created_at"))
    expected += 9 + len(saved["id"].encode()) + 16
    expected += len(saved["definition_sha256"].encode()) + len(saved["definition_json"].encode())
    expected += len(saved["revision_created_at"].encode())
    assert repo.strategy_artifact_bytes() == expected
    other_path = repo.path.parent / "strategy-rollback.db"
    initialize_database(other_path)
    other = Repository(other_path)
    limit = next(
        value
        for value in range(expected + 1, expected * 2 + 100)
        if value - min(LOGICAL_MARGIN_BYTES, max(1, value // 20)) == expected
    )
    with pytest.raises(QuotaExceeded):
        other.create_strategy(
            StrategyDefinition.static_numbers("ñ strategy", (7,)), quota_bytes=limit
        )
    assert other.strategy_artifact_bytes() == 0
    with sqlite3.connect(other.path) as db:
        db.execute(
            "CREATE TRIGGER reject_strategy BEFORE INSERT ON strategies "
            "BEGIN SELECT RAISE(ABORT, 'reject'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="reject"):
        other.create_strategy(StrategyDefinition.static_numbers("Valid", (1,)))
    assert other.strategy_artifact_bytes() == 0


# B-STO-007: REPLACE must not evade immutable strategy-head triggers.
def test_replace_cannot_mutate_strategy_heads(repo):
    preset = seed_presets(repo)[0]
    own = repo.create_strategy(StrategyDefinition.static_numbers("Owned", (3,)))
    with sqlite3.connect(repo.path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for saved in (preset, own):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(
                    "INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        saved["id"],
                        "forged",
                        saved["created_at"],
                        int(saved["protected"]),
                        saved["preset_explanation"],
                        saved["latest_revision"],
                    ),
                )
    assert repo.get_strategy(preset["id"])["protected"] is True


# B-STO-008: protected flags and preset identities are authenticated on reads.
def test_unknown_or_forged_protected_strategy_is_rejected(repo):
    preset = seed_presets(repo)[2]
    own = repo.create_strategy(StrategyDefinition.static_numbers("Owned", (3,)))
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE strategies SET protected=1 WHERE id=?", (own["id"],))
    for read in (lambda: repo.get_strategy(own["id"]), lambda: repo.page_strategies(0, 10)):
        with pytest.raises(ValueError, match="protected preset"):
            read()
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER strategies_protected_update")
        db.execute("UPDATE strategies SET protected=0 WHERE id=?", (own["id"],))
        db.execute("DROP TRIGGER strategy_revisions_no_update")
        forged, digest = definition_snapshot(
            replace(preset["definition"], coverage=preset["definition"].coverage + 1)
        )
        db.execute(
            "UPDATE strategy_revisions SET definition_json=?, definition_sha256=? "
            "WHERE strategy_id=?",
            (forged, digest, preset["id"]),
        )
    for getter in (
        lambda: repo.get_strategy(preset["id"]),
        lambda: repo.get_strategy_revision(preset["id"], 1),
        lambda: repo.page_strategies(0, 10),
    ):
        with pytest.raises(ValueError, match="protected preset"):
            getter()


# R2: reopening and paging read only native saved bytes, never current sources.
def test_backtest_native_snapshot_roundtrip_and_bounded_projection(repo, monkeypatch):
    from test_backtest_trace import execution

    config, rows, result, aggregate = execution()
    identifier, _ = repo.create_backtest(config["name"], config, result, rows)
    monkeypatch.setattr(
        "laboratorio.domain.backtest.run_backtest", lambda *args: pytest.fail("re-execution")
    )
    reopened = Repository(repo.path)
    saved = reopened.get_backtest(identifier)
    assert saved is not None
    assert {key: saved[key] for key in aggregate} == aggregate
    assert saved["trace"]["status"] == "complete" and "sessions" not in saved["trace"]
    assert reopened.search_backtests(0, 20)[1][0] == saved
    assert (
        reopened.search_simulations(0, 20, validate_experiment=_validate_public_experiment)[1][0][2]
        == saved
    )
    sessions = reopened.page_backtest_trace(identifier, 1, 1)
    assert sessions is not None
    assert sessions["total"] == 2 and sessions["items"][0]["ordinal"] == 1
    assert sessions["items"][0]["first_bet"]["source_index"] == 2
    bets = reopened.page_backtest_trace(identifier, 0, 1, 0)
    assert bets is not None
    assert bets["total"] == 1 and bets["items"][0]["paid"] == 80
    empty = reopened.page_backtest_trace(identifier, 1, 1, 0)
    assert empty is not None and empty["items"] == []
    assert reopened.page_backtest_trace(identifier, 0, 20, 99) is None
    assert reopened.page_backtest_trace("missing", 0, 20) is None
    for offset, limit in ((-1, 1), (0, 101), (True, 1), (0, True)):
        with pytest.raises(ValueError):
            reopened.page_backtest_trace(identifier, offset, limit)


def test_legacy_backtest_read_keeps_exact_aggregates_and_does_not_rewrite(repo):
    from test_backtest_trace import execution

    config, _, _, aggregate = execution()
    raw = json.dumps(aggregate)
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "INSERT INTO backtests VALUES (?, ?, ?, ?, ?)",
            ("old", config["name"], json.dumps(config), raw, "2025-01-01T00:00:00Z"),
        )
    saved = repo.get_backtest("old")
    assert saved is not None
    assert {key: saved[key] for key in aggregate} == aggregate
    assert saved["trace"] == {"status": "not_stored", "reason": "legacy"}
    assert (
        repo.search_simulations(0, 20, validate_experiment=_validate_public_experiment)[1][0][2]
        == saved
    )
    page = repo.page_backtest_trace("old", 0, 20)
    assert page is not None and page["trace"]["status"] == "not_stored"
    with pytest.raises(ValueError, match="not stored"):
        repo.page_backtest_trace("old", 0, 20, 0)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT result_json FROM backtests WHERE id='old'").fetchone()[0] == raw


@pytest.mark.parametrize("malformed", [None, {}, {"version": 99}])
def test_invalid_backtest_trace_is_not_legacy_on_any_read(repo, malformed):
    from test_backtest_trace import execution

    config, rows, result, _ = execution()
    identifier, _ = repo.create_backtest(config["name"], config, result, rows)
    with sqlite3.connect(repo.path) as db:
        raw = json.loads(
            db.execute("SELECT result_json FROM backtests WHERE id=?", (identifier,)).fetchone()[0]
        )
        raw["trace"] = malformed
        corrupt = json.dumps(raw)
        db.execute("UPDATE backtests SET result_json=? WHERE id=?", (corrupt, identifier))
    for read in (
        lambda: repo.get_backtest(identifier),
        lambda: repo.search_backtests(0, 20),
        lambda: repo.page_backtest_trace(identifier, 0, 20),
        lambda: repo.search_simulations(0, 20, validate_experiment=_validate_public_experiment),
    ):
        with pytest.raises(ValueError, match="corrupt"):
            read()
    with sqlite3.connect(repo.path) as db:
        assert (
            db.execute("SELECT result_json FROM backtests WHERE id=?", (identifier,)).fetchone()[0]
            == corrupt
        )
