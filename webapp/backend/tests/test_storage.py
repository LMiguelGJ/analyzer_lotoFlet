"""Durable snapshots, lifecycle and schema boundaries (isolated SQLite only)."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from laboratorio.domain.contracts import (
    Conditions,
    ExperimentRequest,
    ExperimentStatus,
    Outcome,
    RunStatus,
    Strategy,
)
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.settings import Settings
from laboratorio.storage.database import SCHEMA_VERSION, UnsupportedSchema, initialize_database
from laboratorio.storage.repository import Repository


def request():
    return ExperimentRequest(
        name="Trial",
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=200, seed=42),
        strategies=(
            Strategy(name="Cold", selector="system", system="cold", coverage=1, staking="flat"),
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
    assert saved.request == request()
    assert saved.history_id == "history-q80" and saved.history_sha256 == "a" * 64
    assert saved.rankings_id == "rankings-pos1" and saved.rankings_sha256 == "b" * 64
    assert saved.code_version == "engine-v1" and saved.request.conditions.seed == 42
    assert saved.runs[0].status is RunStatus.COMPLETED
    assert saved.runs[0].result == result()
    assert saved.runs[0].configuration_id == config
    assert repo.list_experiments()[0] == saved


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
    assert Repository(path).get_experiment("exp2").created_at == "2025-01-01T00:00:00Z"


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


def test_fresh_database_applies_migrations_in_order(tmp_path):
    path = tmp_path / "fresh.db"
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row[1] for row in db.execute("PRAGMA table_info(experiments)")}
        assert "created_at" in columns


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


def test_search_experiments_default_order_is_created_at_desc_with_id_tiebreak(repo):
    ids = [create(repo) for _ in range(3)]
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE experiments SET created_at = '2025-01-01T00:00:00.000000Z'")
    total, rows = repo.search_experiments(0, 20)
    assert total == 3
    # An explicit timestamp tie falls back to id descending, a deterministic tiebreak.
    assert [r.id for r in rows] == sorted(ids, reverse=True)


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


def test_concurrent_initialization_is_repeatable(tmp_path):
    path = tmp_path / "shared.db"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize_database, [path] * 8))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='runs'").fetchone()[0] == 1


def test_repository_does_not_initialize_implicitly(tmp_path):
    path = tmp_path / "missing" / "lab.db"
    with pytest.raises(FileNotFoundError):
        Repository(path)
    assert not path.exists()


def test_settings_default_not_under_repository(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/example/AppData/Local")
    monkeypatch.delenv("LABORATORIO_DATA_DIR", raising=False)
    assert (
        Settings.from_environment()
        .database_path.as_posix()
        .endswith("AppData/Local/LaboratorioQuiniela/laboratorio.db")
    )
