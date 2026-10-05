import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta

import pytest
from test_import_records import options, profile, row
from test_queue import request as legacy_request

from laboratorio.domain.batch_admission import (
    ProfileBatchSubmission,
    StrategyReference,
    admit_profile_batch,
)
from laboratorio.domain.contracts import SettlementMode, legacy_quiniela_80_profile
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_session import ProfileConditions
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.importing.history import history_options
from laboratorio.storage.database import _run_migrations, initialize_database
from laboratorio.storage.quota import LOGICAL_MARGIN_BYTES, PendingRunsExceeded, QuotaExceeded
from laboratorio.storage.repository import (
    ExecutionPolicy,
    IdempotencyConflict,
    Repository,
)


def test_default_policy_is_conservative_and_workers_are_not_editable():
    """B-DOM-052: execution defaults stay conservative and worker count is fixed."""
    policy = ExecutionPolicy.defaults()
    assert policy.max_strategies_per_batch == 3
    assert policy.worker_count == 1
    assert policy.max_pending_runs == 10
    assert policy.max_bet_draws == 1_000
    assert policy.max_elapsed_draws == 10_000
    assert policy.run_timeout_seconds == 120
    with pytest.raises(ValueError):
        ExecutionPolicy.from_values({**policy.as_dict(), "worker_count": 2})


def test_policy_fields_are_bounded_not_arbitrary():
    """B-DOM-053: policy limits reject out-of-range values."""
    defaults = ExecutionPolicy.defaults().as_dict()
    with pytest.raises(ValueError):
        ExecutionPolicy.from_values({**defaults, "max_pending_runs": 101})
    with pytest.raises(ValueError):
        ExecutionPolicy.from_values({**defaults, "max_bet_draws": 10_001})
    with pytest.raises(ValueError):
        ExecutionPolicy.from_values({**defaults, "run_timeout_seconds": 3_601})


def _new_repo(tmp_path):
    path = tmp_path / "admission.db"
    initialize_database(path)
    return Repository(path)


def _saved_inputs(repo, *, row_count=2):
    game = profile(positions=3)
    repo.create_game_profile(game)
    records = [
        row((1, 2, 3), day=f"2025-09-{2 + index:02d}", hour="05:10") for index in range(row_count)
    ]
    raw = json.dumps(records, separators=(",", ":")).encode()
    dataset = repo.promote_dataset(raw, **options(positions=3, profile=game)).dataset
    definition = StrategyDefinition.static_numbers("Static low risk", (7,), stake=1)
    saved = repo.create_strategy(definition)
    assert saved is not None
    reference = StrategyReference(saved["id"], 1, saved["definition_sha256"])
    conditions = ProfileConditions(
        1,
        f"2025-09-{2:02d} 05:10",
        100,
        200,
        SettlementMode.ALL,
    )
    submission = ProfileBatchSubmission(
        (reference,),
        game.profile_id,
        game.revision,
        profile_sha256(game),
        dataset.dataset_sha256,
        conditions,
        2,
        "batch-test-1",
    )
    return game, dataset, definition, saved, submission


def test_admission_uses_exact_revision_persists_snapshot_and_is_idempotent(tmp_path):
    """B-DOM-054: batch admission freezes exact revisions and is idempotent."""
    repo = _new_repo(tmp_path)
    _, _, definition, saved_strategy, submission = _saved_inputs(repo)
    first = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(first)
    assert saved is not None
    assert isinstance(saved.request, ProfileBatchRequestV5)
    assert saved.batch_admission is not None
    assert saved.request_schema_version == 5
    assert saved.request.strategies == (definition,)
    assert saved.runs[0].ordinal == 0
    assert saved.batch_admission["strategy_refs"] == [
        {
            "id": saved_strategy["id"],
            "revision": 1,
            "definition_sha256": saved_strategy["definition_sha256"],
        }
    ]
    assert saved.batch_admission["source_identity"]["row_count"] == 2
    assert saved.batch_admission["policy_revision"] == 1
    assert saved_strategy is not None
    repo.append_strategy_revision(
        saved_strategy["id"], 1, StrategyDefinition.static_numbers("New head", (8,))
    )
    assert admit_profile_batch(repo, submission) == first
    changed = replace(
        submission,
        conditions=replace(submission.conditions, capital=101),
    )
    with pytest.raises(IdempotencyConflict):
        admit_profile_batch(repo, changed)
    revision, policy = repo.update_execution_policy({"max_pending_runs": 11}, expected_revision=1)
    assert revision == 2 and policy.max_pending_runs == 11
    stored = repo.get_experiment(first)
    assert stored is not None and stored.batch_admission is not None
    assert stored.batch_admission["policy_revision"] == 1
    assert stored.batch_admission["policy"]["max_pending_runs"] == 10


def test_batch_ordinals_and_policy_limits_are_frozen_as_explicit_conditions(tmp_path):
    """B-DOM-055: strategy ordinals and effective policy constraints are persisted."""
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo)
    second = repo.create_strategy(StrategyDefinition.static_numbers("Second", (8,)))
    assert second is not None
    submission = replace(
        submission,
        strategy_refs=(
            submission.strategy_refs[0],
            StrategyReference(second["id"], 1, second["definition_sha256"]),
        ),
        conditions=replace(
            submission.conditions,
            max_bet_draws=5_000,
            max_elapsed_draws=5_000,
        ),
        max_draws=5_000,
        client_request_id="ordered-batch",
    )
    repo.update_execution_policy({"max_bet_draws": 4, "max_elapsed_draws": 8})
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and isinstance(saved.request, ProfileBatchRequestV5)
    assert [run.ordinal for run in saved.runs] == [0, 1]
    assert [definition.name for definition in saved.request.strategies] == [
        "Static low risk",
        "Second",
    ]
    assert saved.request.max_draws == 8
    assert saved.request.conditions.max_bet_draws == 4
    assert saved.batch_admission is not None
    assert saved.batch_admission["requested_constraints"]["max_bet_draws"] == 5_000
    assert saved.batch_admission["effective_constraints"]["max_elapsed_draws"] == 8


def test_archived_strategy_requires_trusted_binding_context(tmp_path):
    """B-DOM-056: archived strategies require trusted binding context."""
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo)
    archived = repo.create_strategy(StrategyDefinition.reference_cold_25())
    assert archived is not None
    submission = replace(
        submission,
        strategy_refs=(StrategyReference(archived["id"], 1, archived["definition_sha256"]),),
        client_request_id="archive-without-trust",
    )
    with pytest.raises(ValueError, match="trusted Settings"):
        admit_profile_batch(repo, submission)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 0


def test_admission_rejects_unfunded_and_untrusted_revision_inputs(tmp_path):
    """B-DOM-057: admission verifies revision hashes and initial funding."""
    repo = _new_repo(tmp_path)
    _, _, _, saved_strategy, submission = _saved_inputs(repo)
    assert saved_strategy is not None
    bad_hash = replace(
        submission,
        strategy_refs=(replace(submission.strategy_refs[0], definition_sha256="f" * 64),),
    )
    with pytest.raises(ValueError, match="SHA-256"):
        admit_profile_batch(repo, bad_hash)
    larger = repo.create_strategy(StrategyDefinition.static_numbers("Two picks", (7, 8)))
    assert larger is not None
    unfunded = replace(
        submission,
        strategy_refs=(StrategyReference(larger["id"], 1, larger["definition_sha256"]),),
        conditions=replace(submission.conditions, capital=1),
    )
    with pytest.raises(ValueError, match="fund"):
        admit_profile_batch(repo, unfunded)
    assert repo.get_strategy_revision(saved_strategy["id"], 1)["definition"]


@pytest.mark.parametrize(
    "definition",
    [
        StrategyDefinition.static_numbers("Static low risk", (7,), stake=1),
        StrategyDefinition(
            1,
            "Seeded low risk",
            "seeded-random/hash-sha256-v1",
            1,
            "flat-per-number/v1",
            (("seed", 17),),
            (("per_number_stake", 1),),
        ),
    ],
    ids=("static", "seeded"),
)
def test_non_archived_start_must_match_one_saved_source_label_before_writes(tmp_path, definition):
    """B-DOM-058: unarchived start must resolve uniquely before any write."""
    repo = _new_repo(tmp_path)
    game, dataset, _, _, submission = _saved_inputs(repo)
    saved = repo.create_strategy(definition)
    assert saved is not None
    submission = replace(
        submission,
        strategy_refs=(StrategyReference(saved["id"], 1, saved["definition_sha256"]),),
        conditions=replace(submission.conditions, start_draw="2025-09-02 05:11"),
        client_request_id=f"missing-start-{definition.selector}",
    )

    with pytest.raises(ValueError, match="exactly one canonical source draw"):
        admit_profile_batch(repo, submission, quota_bytes=1_000_000)

    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM profile_batch_admissions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM settings_quota").fetchone()[0] == 0
    assert repo.logical_experiment_bytes() == 0
    assert dataset.dataset_sha256 == submission.dataset_sha256
    assert game.profile_id == submission.profile_id
    valid_submission = replace(
        submission,
        conditions=replace(submission.conditions, start_draw="2025-09-02 05:10"),
        client_request_id=f"valid-start-{definition.selector}",
    )
    identifier = admit_profile_batch(repo, valid_submission)
    saved_experiment = repo.get_experiment(identifier)
    assert saved_experiment is not None
    assert saved_experiment.request.conditions.start_draw == valid_submission.conditions.start_draw


def test_quota_failure_does_not_reserve_a_batch_identity(tmp_path):
    """B-DOM-059: quota failure leaves batch identity available for retry."""
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo)
    with pytest.raises(QuotaExceeded):
        admit_profile_batch(repo, submission, quota_bytes=1)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM profile_batch_admissions").fetchone()[0] == 0
    identifier = admit_profile_batch(repo, submission)
    assert repo.get_experiment(identifier) is not None


def test_batch_quota_matches_measured_sqlite_delta_at_exact_boundary(tmp_path):
    """B-DOM-060: quota estimate matches SQLite delta at the exact boundary."""
    def seeded_repo(path):
        repo = _new_repo(path)
        _saved_inputs(repo)
        return repo

    measured = seeded_repo(tmp_path / "measured")
    _, _, _, _, measured_submission = _saved_inputs(measured)
    before = measured.admission_logical_bytes()
    measured_id = admit_profile_batch(measured, measured_submission, quota_bytes=10**8)
    measured_delta = measured.admission_logical_bytes() - before
    assert measured.get_experiment(measured_id) is not None
    assert before >= measured.dataset_artifact_bytes() + measured.strategy_artifact_bytes()

    exact = seeded_repo(tmp_path / "exact")
    _, _, _, _, exact_submission = _saved_inputs(exact)
    exact_before = exact.admission_logical_bytes()
    exact_usage = exact_before + measured_delta
    exact_bound = exact_usage + LOGICAL_MARGIN_BYTES + 1
    while True:
        margin = min(LOGICAL_MARGIN_BYTES, max(1, exact_bound // 20))
        adjusted_bound = exact_usage + margin + 1
        if adjusted_bound == exact_bound:
            break
        exact_bound = adjusted_bound
    exact_id = admit_profile_batch(exact, exact_submission, quota_bytes=exact_bound)
    assert exact.get_experiment(exact_id) is not None
    assert exact.admission_logical_bytes() - exact_before == measured_delta

    below = seeded_repo(tmp_path / "below")
    _, _, _, _, below_submission = _saved_inputs(below)
    below_before = below.admission_logical_bytes()
    with pytest.raises(QuotaExceeded):
        admit_profile_batch(below, below_submission, quota_bytes=exact_bound - 1)
    assert below.admission_logical_bytes() == below_before
    with sqlite3.connect(below.path) as db:
        assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM profile_batch_admissions").fetchone()[0] == 0


def test_global_pending_run_limit_is_atomic_for_old_submission_shapes(tmp_path):
    """B-DOM-061: legacy admission enforces the global pending-run limit atomically."""
    repo = _new_repo(tmp_path)
    request = legacy_request("legacy")
    for _ in range(10):
        repo.create_experiment(
            request,
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="test",
        )
    with pytest.raises(PendingRunsExceeded):
        repo.create_experiment(
            request,
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="test",
        )
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status = 'pending'").fetchone()[0] == 10


def test_pending_limit_is_shared_between_profile_v5_and_legacy_admission(tmp_path):
    """B-DOM-062: pending-run quota is shared across legacy and v5 admission."""
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo)
    legacy = legacy_request("legacy")
    for _ in range(9):
        repo.create_experiment(
            legacy,
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="test",
        )
    second = repo.create_strategy(StrategyDefinition.static_numbers("Second pending", (8,)))
    assert second is not None
    oversized = replace(
        submission,
        strategy_refs=(
            submission.strategy_refs[0],
            StrategyReference(second["id"], 1, second["definition_sha256"]),
        ),
    )
    with pytest.raises(PendingRunsExceeded):
        admit_profile_batch(repo, oversized)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status = 'pending'").fetchone()[0] == 9
        assert db.execute("SELECT count(*) FROM profile_batch_admissions").fetchone()[0] == 0
    batch = admit_profile_batch(repo, submission)
    assert batch
    with pytest.raises(PendingRunsExceeded):
        repo.create_experiment(
            legacy,
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="test",
        )
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM runs WHERE status = 'pending'").fetchone()[0] == 10
        assert db.execute("SELECT count(*) FROM profile_batch_admissions").fetchone()[0] == 1


def test_static_admission_keeps_full_dataset_above_legacy_ten_thousand_rows(tmp_path):
    """B-DOM-063: static admission preserves datasets larger than legacy ceiling."""
    repo = _new_repo(tmp_path)
    game = legacy_quiniela_80_profile()
    repo.create_game_profile(game)
    start = date(2020, 1, 1)
    days = {}
    for offset in range(3_334):
        day = (start + timedelta(days=offset)).isoformat()
        days[day] = [
            {"hora": f"05:{minute:02d}", "numeros": ["01", "02", "03", "04", "05"]}
            for minute in range(3)
        ]
    document = {
        "metadata": {
            "schema_version": 1,
            "juego": "Local fixture",
            "origen": "local fixture",
            "endpoint": "local fixture",
            "zona_horaria": "UTC",
            "cantidad_sorteos": 10_002,
            "rango_seleccionado": {
                "desde": start.isoformat(),
                "hasta": (start + timedelta(days=3_333)).isoformat(),
            },
        },
        "sorteos_por_fecha": days,
    }
    raw = json.dumps(document, separators=(",", ":")).encode()
    dataset = repo.promote_dataset(raw, **history_options(document, game)).dataset
    definition = StrategyDefinition.static_numbers("Short window", (7,), stake=1)
    saved_strategy = repo.create_strategy(definition)
    assert saved_strategy is not None
    submission = ProfileBatchSubmission(
        (StrategyReference(saved_strategy["id"], 1, saved_strategy["definition_sha256"]),),
        game.profile_id,
        game.revision,
        profile_sha256(game),
        dataset.dataset_sha256,
        ProfileConditions(1, f"{start.isoformat()} 05:00", 2_000, 2_800, SettlementMode.ALL),
        2,
        "large-source-1",
    )
    identifier = admit_profile_batch(repo, submission)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.batch_admission is not None
    assert saved.batch_admission["source_identity"]["row_count"] == 10_002
    assert len(dataset.preview.records) == 10_002
    assert isinstance(saved.request, ProfileBatchRequestV5)
    assert saved.request.max_draws == 2
    assert saved.request.conditions.start_draw == f"{start.isoformat()} 05:00"


def test_client_request_lookup_is_read_only_and_verifies_the_experiment(tmp_path, monkeypatch):
    """B-DOM-064: client identity lookup is read-only and validates its target."""
    repo = _new_repo(tmp_path)
    _, _, _, _, submission = _saved_inputs(repo)
    identifier = admit_profile_batch(repo, submission)
    before = repo.admission_logical_bytes()
    assert repo.get_profile_batch_request_id(submission.client_request_id) == identifier
    assert repo.get_profile_batch_request_id("unknown-client-id") is None
    assert repo.admission_logical_bytes() == before
    with pytest.raises(ValueError, match="invalid client request identity"):
        repo.get_profile_batch_request_id("x" * 129)
    monkeypatch.setattr(repo, "get_experiment", lambda _: None)
    with pytest.raises(ValueError, match="missing experiment"):
        repo.get_profile_batch_request_id(submission.client_request_id)


def test_migration_11_preserves_populated_v10_rows_and_foreign_keys(tmp_path):
    path = tmp_path / "v10.db"
    with sqlite3.connect(path) as db:
        _run_migrations(db, 0, list(range(1, 11)))
        db.execute(
            "INSERT INTO experiments VALUES (?, 'completed', '{}', 'h', ?, 'r', ?, 'v1', "
            "'created', 'legacy', 1)",
            ("old", "a" * 64, "b" * 64),
        )
        profile_id, revision, profile_json = db.execute(
            "SELECT profile_id, revision, profile_json FROM game_profiles "
            "ORDER BY profile_id, revision LIMIT 1"
        ).fetchone()
        db.execute(
            "INSERT INTO experiment_profiles VALUES ('old', ?, ?, ?)",
            (profile_id, revision, profile_json),
        )
        db.execute("INSERT INTO runs VALUES ('old', 0, NULL, 'completed', '{}', 'legacy', 1)")
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 12
        assert db.execute(
            "SELECT id, status, request_schema_version FROM experiments"
        ).fetchone() == (
            "old",
            "completed",
            1,
        )
        assert db.execute(
            "SELECT experiment_id, status, result_schema_version FROM runs"
        ).fetchone() == (
            "old",
            "completed",
            1,
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
