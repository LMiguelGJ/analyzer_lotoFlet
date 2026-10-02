"""Schema 6 profile requests and results are bound to immutable local artifacts."""

import json
import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_import_records import options
from test_import_records import profile as import_profile
from test_import_records import row as import_row

from laboratorio.domain.contracts import (
    ExperimentStatus,
    RunStatus,
    SettlementMode,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_request_v2 import (
    ProfileCyclingRequest,
    serialize_profile_cycling_request,
)
from laboratorio.domain.profile_result import serialize_profile_result
from laboratorio.domain.profile_result_v2 import (
    ProfileCyclingResult,
    serialize_profile_cycling_result,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileOutcome,
    ProfileSelector,
    ProfileStaking,
    Q80CyclingStaking,
    _minute,
    run_profile_session,
)
from laboratorio.domain.session import SessionResult
from laboratorio.storage.database import initialize_database
from laboratorio.storage.quota import LOGICAL_MARGIN_BYTES, QuotaExceeded
from laboratorio.storage.repository import Repository


def profile_request(profile):
    return ProfileExperimentRequest(
        "profile",
        1,
        "Profile trial",
        "a" * 64,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-01-01 05:10", 100, 200, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        ProfileStaking(1, "flat-per-number/v1", profile.minimum_stake),
        "all_rows/v1",
    )


@pytest.fixture
def prepared(tmp_path):
    path = tmp_path / "lab.db"
    initialize_database(path)
    profile = legacy_quiniela_80_profile()
    request = profile_request(profile)
    wire = serialize_profile_request(request)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
            "rankings_id, rankings_sha256, code_version, created_at, request_kind) "
            "VALUES (?, 'pending', ?, '', '', '', '', 'profile-v1', NULL, 'profile')",
            ("prepared", wire),
        )
        db.execute(
            "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
            ("prepared", profile.profile_id, profile.revision, profile.model_dump_json()),
        )
        db.execute(
            "INSERT INTO runs (experiment_id, ordinal, configuration_id, status, result_kind) "
            "VALUES ('prepared', 0, NULL, 'pending', 'profile')"
        )
    return Repository(path), request, wire


def test_prepared_profile_request_loads_typed_without_exposing_enqueue(prepared):
    repo, request, wire = prepared
    saved = repo.get_experiment("prepared")
    assert saved.request_kind == "profile"
    assert saved.request == request
    assert saved.runs[0].result_kind == "profile"
    assert saved.runs[0].result is None
    assert saved.status is ExperimentStatus.PENDING
    assert saved.runs[0].status is RunStatus.PENDING
    assert repo.search_experiments(0, 10, name_contains="Profile")[1] == [saved]
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT request_json FROM experiments").fetchone()[0] == wire
    with pytest.raises(ValueError, match="validated request"):
        repo.create_experiment(
            request,
            history_id="h",
            history_sha256="a" * 64,
            rankings_id="r",
            rankings_sha256="b" * 64,
            code_version="v1",
        )


@pytest.mark.parametrize(
    "column,value",
    [
        ("request_kind", "legacy"),
        ("request_json", "{}"),
        ("request_json", "not JSON"),
    ],
)
def test_request_discriminator_and_wire_must_agree(prepared, column, value):
    repo, _, _ = prepared
    with sqlite3.connect(repo.path) as db:
        db.execute(f"UPDATE experiments SET {column} = ? WHERE id = 'prepared'", (value,))
    with pytest.raises(ValueError):
        repo.get_experiment("prepared")


def test_snapshot_identity_and_full_hash_must_agree(prepared):
    repo, request, _ = prepared
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "UPDATE experiments SET request_json = ? WHERE id = 'prepared'",
            (serialize_profile_request(replace(request, profile_sha256="b" * 64)),),
        )
    with pytest.raises(ValueError, match="differs from experiment profile snapshot"):
        repo.get_experiment("prepared")


def test_mixed_kind_and_completed_profile_results_fail_closed(prepared):
    repo, _, _ = prepared
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE runs SET result_kind = 'legacy' WHERE experiment_id = 'prepared'")
    with pytest.raises(ValueError, match="mixed request/result kind"):
        repo.get_experiment("prepared")
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "UPDATE runs SET result_kind = 'profile', status = 'completed', "
            "result_json = '{}', result_schema_version = 1 "
            "WHERE experiment_id = 'prepared'"
        )
    with pytest.raises(ValueError, match="result"):
        repo.get_experiment("prepared")


def test_legacy_completion_cannot_write_profile_run(prepared):
    repo, _, _ = prepared
    repo.start_run("prepared", 0)
    with pytest.raises(ValueError, match="profile completed results are not supported"):
        repo.complete_run("prepared", 0, SessionResult)  # rejected before legacy validation
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT status, result_json FROM runs").fetchone() == ("running", None)


def test_schema_discriminators_reject_unknown_values(prepared):
    repo, _, _ = prepared
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE experiments SET request_kind = 'unknown'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE runs SET result_kind = 'unknown'")


@pytest.fixture
def bound(tmp_path):
    path = tmp_path / "bound.db"
    initialize_database(path)
    repo = Repository(path)
    profile = import_profile()
    raw = json.dumps(
        [
            import_row(day="2025-09-01"),
            import_row(day="2025-09-02"),
            import_row(day="2025-09-03"),
        ]
    ).encode()
    dataset = repo.promote_dataset(raw, **options()).dataset
    request = replace(
        profile_request(profile),
        dataset_sha256=dataset.dataset_sha256,
        conditions=ProfileConditions(
            1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL, max_elapsed_draws=2
        ),
        selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 1)),
    )
    return repo, profile, dataset, request


def free(_):
    return SimpleNamespace(free=2 * 1024**3)


def draws(dataset):
    return tuple(
        ProfileDraw(1, f"{r.date} {r.time}", _minute(f"{r.date} {r.time}"), r.numbers, True)
        for r in dataset.preview.records
    )


def replay(request, profile, dataset):
    return run_profile_session(
        profile, request.conditions, request.selector, request.staking, draws(dataset)
    )


def test_create_requires_registered_exact_profile_and_dataset(bound):
    repo, profile, dataset, request = bound
    before = repo.admission_logical_bytes()
    with pytest.raises(ValueError, match="registered"):
        repo.create_profile_experiment(request)
    repo.create_game_profile(profile)
    with pytest.raises(ValueError, match="registered"):
        repo.create_profile_experiment(replace(request, profile_sha256="b" * 64))
    with pytest.raises(ValueError, match="dataset not found"):
        repo.create_profile_experiment(replace(request, dataset_sha256="a" * 64))
    with pytest.raises(ValueError, match="start draw"):
        repo.create_profile_experiment(
            replace(request, conditions=replace(request.conditions, start_draw="2025-09-04 05:10"))
        )
    assert repo.admission_logical_bytes() > before
    assert repo.list_experiments() == []
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        db.execute(
            "CREATE TRIGGER reject_snapshot BEFORE INSERT ON experiment_profiles "
            "BEGIN SELECT RAISE(ABORT, 'snapshot rejected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="snapshot rejected"):
        repo.create_profile_experiment(request)
    assert repo.list_experiments() == []
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER reject_snapshot")
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute(
            "UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?",
            (dataset.dataset_sha256,),
        )
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.create_profile_experiment(request)


def test_create_atomic_snapshot_provenance_and_exact_quota(bound):
    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    baseline = repo.admission_logical_bytes()
    identifier = repo.create_profile_experiment(request, disk_usage=free)
    delta = repo.admission_logical_bytes() - baseline
    saved = repo.get_experiment(identifier)
    assert saved.request == request and saved.profile == profile
    assert saved.request_kind == saved.runs[0].result_kind == "profile"
    assert (
        saved.history_id,
        saved.history_sha256,
        saved.rankings_id,
        saved.rankings_sha256,
        saved.code_version,
    ) == (dataset.dataset_sha256, dataset.dataset_sha256, "", "", "profile-v1")
    with sqlite3.connect(repo.path) as db:
        assert (
            db.execute(
                "SELECT profile_json FROM experiment_profiles WHERE experiment_id = ?",
                (identifier,),
            ).fetchone()[0]
            == profile.model_dump_json()
        )
        assert db.execute(
            "SELECT request_json FROM experiments WHERE id = ?", (identifier,)
        ).fetchone()[0] == serialize_profile_request(request)
    limit = next(
        n
        for n in range(baseline + delta, 2 * (baseline + delta) + 20)
        if n - min(LOGICAL_MARGIN_BYTES, max(1, n // 20)) == baseline + delta
    )
    with pytest.raises(QuotaExceeded):
        repo.create_profile_experiment(request, quota_bytes=limit, disk_usage=free)
    assert repo.list_experiments() == [saved]
    assert repo.admission_logical_bytes() == baseline + delta


@pytest.mark.parametrize("random", [False, True])
def test_complete_replays_all_rows_and_loads_typed_result(bound, monkeypatch, random):
    import laboratorio.storage.repository as storage

    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    if random:
        request = replace(
            request,
            selector=ProfileSelector(
                1, "seeded-random/hash-sha256-v1", 2, seed=17, algorithm_version="hash-sha256-v1"
            ),
        )
    identifier = repo.create_profile_experiment(request)
    result = replay(request, profile, dataset)
    seen = []
    original = storage.validate_profile_result

    def capture(result, request, profile, rows):
        seen.append(tuple(row.label for row in rows))
        return original(result, request, profile, rows)

    monkeypatch.setattr(storage, "validate_profile_result", capture)
    repo.start_run(identifier, 0)
    repo.complete_profile_run(identifier, 0, result)
    assert seen == [("2025-09-01 05:10", "2025-09-02 05:10", "2025-09-03 05:10")]
    saved = Repository(repo.path).get_experiment(identifier)
    assert saved is not None
    assert saved.runs[0].result == result
    assert saved.runs[0].status is RunStatus.COMPLETED
    assert result.bets[0].results == (0, 1, 2)
    with sqlite3.connect(repo.path) as db:
        assert db.execute(
            "SELECT result_json FROM runs WHERE experiment_id = ?", (identifier,)
        ).fetchone()[0] == serialize_profile_result(result)
    repo.complete_experiment(identifier)
    assert repo.get_experiment(identifier).status is ExperimentStatus.COMPLETED


def test_complete_rejects_forgery_wrong_owner_cancel_and_stale_replay(bound, monkeypatch):
    import laboratorio.storage.repository as storage

    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    first = repo.create_profile_experiment(request)
    other = repo.create_profile_experiment(request)
    result = replay(request, profile, dataset)
    with pytest.raises(ValueError, match="owned"):
        repo.complete_profile_run(first, 0, result)
    repo.start_run(first, 0)
    for identifier, ordinal in ((other, 0), (first, 1), (first, True)):
        with pytest.raises(ValueError, match="owned"):
            repo.complete_profile_run(identifier, ordinal, result)
    with pytest.raises(ValueError, match="replay"):
        repo.complete_profile_run(first, 0, replace(result, paid=result.paid + 1))
    cancelled = run_profile_session(
        profile,
        request.conditions,
        request.selector,
        request.staking,
        draws(dataset),
        cancel_after_elapsed_draws=1,
    )
    assert cancelled.outcome is ProfileOutcome.CANCELLED
    with pytest.raises(ValueError, match="cancelled"):
        repo.complete_profile_run(first, 0, cancelled)
    original = storage.validate_profile_result

    def cancel_during_replay(*args):
        validated = original(*args)
        repo.finish_incomplete(first, ExperimentStatus.CANCELLED)
        return validated

    monkeypatch.setattr(storage, "validate_profile_result", cancel_during_replay)
    with pytest.raises(ValueError, match="changed during replay"):
        repo.complete_profile_run(first, 0, result)
    assert repo.get_experiment(first).runs[0].result is None


@pytest.mark.parametrize("positions", [1, 5])
def test_profile_result_loading_preserves_variable_positions(tmp_path, positions):
    path = tmp_path / "positions.db"
    initialize_database(path)
    repo = Repository(path)
    profile = import_profile(positions=positions)
    dataset = repo.promote_dataset(
        json.dumps([import_row(numbers=tuple(range(positions)))]).encode(),
        **options(positions=positions),
    ).dataset
    repo.create_game_profile(profile)
    request = replace(
        profile_request(profile),
        dataset_sha256=dataset.dataset_sha256,
        conditions=ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL),
        selector=ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
    )
    identifier = repo.create_profile_experiment(request)
    result = replay(request, profile, dataset)
    repo.start_run(identifier, 0)
    repo.complete_profile_run(identifier, 0, result)
    saved = Repository(path).get_experiment(identifier)
    assert saved is not None and saved.runs[0].result == result
    assert result.bets[0].results == tuple(range(positions))


def test_replay_race_rechecks_request_and_dataset_binding(bound, monkeypatch):
    import laboratorio.storage.repository as storage

    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    identifier = repo.create_profile_experiment(request)
    repo.start_run(identifier, 0)
    result = replay(request, profile, dataset)
    original = storage.validate_profile_result

    def change_request(*args):
        validated = original(*args)
        with sqlite3.connect(repo.path) as db:
            db.execute(
                "UPDATE experiments SET code_version = 'swapped' WHERE id = ?", (identifier,)
            )
        return validated

    monkeypatch.setattr(storage, "validate_profile_result", change_request)
    with pytest.raises(ValueError, match="changed during replay"):
        repo.complete_profile_run(identifier, 0, result)
    assert repo.get_experiment(identifier).runs[0].result is None


def test_complete_quota_and_corrupt_dataset_fail_without_result(bound):
    repo, profile, dataset, request = bound
    repo.create_game_profile(profile)
    identifier = repo.create_profile_experiment(request)
    repo.start_run(identifier, 0)
    used = repo.admission_logical_bytes()
    with pytest.raises(QuotaExceeded):
        repo.complete_profile_run(
            identifier, 0, replay(request, profile, dataset), quota_bytes=used + 10, disk_usage=free
        )
    assert repo.get_experiment(identifier).runs[0].status is RunStatus.RUNNING
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute(
            "UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?",
            (dataset.dataset_sha256,),
        )
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.complete_profile_run(identifier, 0, replay(request, profile, dataset))
    assert repo.get_experiment(identifier).runs[0].result is None


@pytest.fixture
def cycling(tmp_path):
    path = tmp_path / "cycling.db"
    initialize_database(path)
    repo = Repository(path)
    profile = legacy_quiniela_80_profile()
    raw = json.dumps(
        [import_row(numbers=(0, 1, 2, 3, 4), day=f"2025-09-0{day}") for day in (1, 2, 3)]
    ).encode()
    dataset = repo.promote_dataset(raw, **options(positions=5, profile=profile)).dataset
    request = ProfileCyclingRequest(
        "profile",
        2,
        "Cycling private",
        dataset.dataset_sha256,
        profile.profile_id,
        profile.revision,
        profile_sha256(profile),
        ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL, max_elapsed_draws=2),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(7,)),
        Q80CyclingStaking(),
        "all_rows/v1",
    )
    repo.create_game_profile(profile)  # identical legacy snapshot is a no-op
    return repo, profile, dataset, request


def cycling_result(request, profile, dataset):
    return ProfileCyclingResult(
        "profile",
        2,
        run_profile_session(
            profile, request.conditions, request.selector, request.staking, draws(dataset)
        ),
    )


def test_cycling_private_roundtrip_and_cross_version_fail_closed(cycling):
    repo, profile, dataset, request = cycling
    identifier = repo.create_profile_cycling_experiment(request)
    saved = Repository(repo.path).get_experiment(identifier)
    assert saved is not None
    assert saved.request == request and saved.request_schema_version == 2
    assert saved.runs[0].result is None and saved.runs[0].result_schema_version is None
    assert repo.search_experiments(0, 1) == (0, [])
    assert repo.page_experiments(0, 1) == (0, [])
    with sqlite3.connect(repo.path) as db:
        assert db.execute(
            "SELECT request_json FROM experiments WHERE id = ?", (identifier,)
        ).fetchone()[0] == serialize_profile_cycling_request(request)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "UPDATE experiments SET request_schema_version = 5 WHERE id = ?", (identifier,)
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE experiments SET request_kind = 'legacy' WHERE id = ?", (identifier,))
    repo.start_run(identifier, 0)  # internal-only setup, never through JobQueue
    result = cycling_result(request, profile, dataset)
    with pytest.raises(ValueError, match="owned"):
        repo.complete_profile_run(identifier, 0, result.session)
    repo.complete_profile_cycling_run(identifier, 0, result)
    completed = Repository(repo.path).get_experiment(identifier)
    assert completed is not None
    assert completed.runs[0].result == result
    assert completed.runs[0].result_schema_version == 2
    assert repo.search_experiments(0, 1) == (0, [])  # old callers retain v1-only default
    assert repo.search_experiments(0, 1, include_completed_cycling=True) == (
        1,
        [repo.get_experiment(identifier)],
    )
    repo.complete_experiment(identifier)
    assert repo.search_experiments(0, 1, include_completed_cycling=True) == (
        1,
        [repo.get_experiment(identifier)],
    )
    assert repo.search_experiments(1, 1, include_completed_cycling=True) == (1, [])
    with sqlite3.connect(repo.path) as db:
        assert db.execute(
            "SELECT result_json FROM runs WHERE experiment_id = ?", (identifier,)
        ).fetchone()[0] == serialize_profile_cycling_result(result)
        db.execute(
            "UPDATE runs SET result_schema_version = 1 WHERE experiment_id = ?", (identifier,)
        )
    with pytest.raises(ValueError, match="schema version"):
        repo.get_experiment(identifier)
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "UPDATE runs SET result_schema_version = 2, result_json = '{}' WHERE experiment_id = ?",
            (identifier,),
        )
    with pytest.raises(ValueError, match="result"):
        repo.get_experiment(identifier)
    with sqlite3.connect(repo.path) as db:
        db.execute(
            "UPDATE runs SET result_json = ?, result_schema_version = 2 WHERE experiment_id = ?",
            (serialize_profile_cycling_result(result), identifier),
        )
        db.execute(
            "UPDATE experiments SET request_json = ? WHERE id = ?",
            (serialize_profile_request(profile_request(profile)), identifier),
        )
    with pytest.raises(ValueError):
        repo.get_experiment(identifier)


def test_cycling_replay_ownership_digest_and_atomic_quota(cycling, monkeypatch):
    import laboratorio.storage.repository as storage

    repo, profile, dataset, request = cycling
    with pytest.raises(ValueError, match="dataset not found"):
        repo.create_profile_cycling_experiment(replace(request, dataset_sha256="a" * 64))
    baseline = repo.admission_logical_bytes()
    identifier = repo.create_profile_cycling_experiment(request)
    delta = repo.admission_logical_bytes() - baseline
    with pytest.raises(QuotaExceeded):
        repo.create_profile_cycling_experiment(
            request, quota_bytes=baseline + delta + 1, disk_usage=free
        )
    assert repo.admission_logical_bytes() == baseline + delta
    other = repo.create_profile_cycling_experiment(request)
    result = cycling_result(request, profile, dataset)
    with pytest.raises(ValueError, match="owned"):
        repo.complete_profile_cycling_run(identifier, 0, result)
    repo.start_run(identifier, 0)
    for wrong, ordinal in ((other, 0), (identifier, 1), (identifier, True)):
        with pytest.raises(ValueError, match="owned"):
            repo.complete_profile_cycling_run(wrong, ordinal, result)
    with pytest.raises(ValueError, match="replay"):
        repo.complete_profile_cycling_run(
            identifier, 0, replace(result, session=replace(result.session, paid=99))
        )
    used = repo.admission_logical_bytes()
    with pytest.raises(QuotaExceeded):
        repo.complete_profile_cycling_run(
            identifier, 0, result, quota_bytes=used + 10, disk_usage=free
        )
    assert repo.admission_logical_bytes() == used
    original = storage.validate_profile_cycling_result

    def change_binding(*args):
        admitted = original(*args)
        with sqlite3.connect(repo.path) as db:
            db.execute(
                "UPDATE experiments SET code_version = 'tampered' WHERE id = ?", (identifier,)
            )
        return admitted

    monkeypatch.setattr(storage, "validate_profile_cycling_result", change_binding)
    with pytest.raises(ValueError, match="changed during replay"):
        repo.complete_profile_cycling_run(identifier, 0, result)
    assert repo.get_experiment(identifier).runs[0].result is None
    monkeypatch.setattr(storage, "validate_profile_cycling_result", original)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE experiments SET code_version = 'profile-v2' WHERE id = ?", (identifier,))
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute(
            "UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?",
            (dataset.dataset_sha256,),
        )
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.complete_profile_cycling_run(identifier, 0, result)
    assert repo.get_experiment(identifier).runs[0].result is None


def test_audaz_v3_persistence_replay_and_version_checks(bound):
    from laboratorio.domain.profile_request_v3 import (
        ProfileAudazRequest,
        serialize_profile_audaz_request,
    )
    from laboratorio.domain.profile_result_v3 import (
        ProfileAudazResult,
        serialize_profile_audaz_result,
    )
    from laboratorio.domain.profile_session import ProfileSelector, run_profile_session
    from laboratorio.domain.profile_staking import ProfileAudazStaking

    repo, profile, dataset, request = bound
    audaz = ProfileAudazRequest(
        "profile", 3, request.name, request.dataset_sha256, request.profile_id,
        request.profile_revision, request.profile_sha256, request.conditions,
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
        ProfileAudazStaking(), request.entry_policy,
    )
    repo.create_game_profile(profile)
    identifier = repo.create_profile_audaz_experiment(audaz)
    assert repo.get_experiment(identifier).request_schema_version == 3
    repo.start_run(identifier, 0)
    result = ProfileAudazResult(
        "profile",
        3,
        run_profile_session(
            profile, audaz.conditions, audaz.selector, audaz.staking, draws(dataset)
        ),
    )
    repo.complete_profile_audaz_run(identifier, 0, result)
    repo.complete_experiment(identifier)
    saved = repo.get_experiment(identifier)
    assert saved is not None and saved.runs[0].result == result
    assert saved.runs[0].result_schema_version == 3
    assert repo.search_experiments(0, 10, include_completed_cycling=True) == (1, [saved])
    with sqlite3.connect(repo.path) as db:
        request_wire, version = db.execute(
            "SELECT request_json, request_schema_version FROM experiments WHERE id = ?",
            (identifier,),
        ).fetchone()
        result_wire, result_version = db.execute(
            "SELECT result_json, result_schema_version FROM runs WHERE experiment_id = ?",
            (identifier,),
        ).fetchone()
        assert request_wire == serialize_profile_audaz_request(audaz) and version == 3
        assert result_wire == serialize_profile_audaz_result(result) and result_version == 3
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "UPDATE experiments SET request_schema_version = 5 WHERE id = ?", (identifier,)
            )


def test_audaz_initial_affordability_rejects_before_creating_rows(tmp_path):
    from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
    from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector
    from laboratorio.domain.profile_staking import ProfileAudazStaking

    path = tmp_path / "audaz.db"
    initialize_database(path)
    repo = Repository(path)
    profile = import_profile()
    profile = type(profile).model_validate(
        profile.model_dump(mode="python")
        | {"stake_increment": 2, "minimum_stake": 2, "maximum_stake": 10}
    )
    raw = json.dumps([import_row(day=f"2025-09-0{day}") for day in (1, 2, 3)]).encode()
    dataset = repo.promote_dataset(raw, **options(profile=profile)).dataset
    repo.create_game_profile(profile)
    request = ProfileAudazRequest(
        "profile", 3, "Unaffordable", dataset.dataset_sha256, profile.profile_id,
        profile.revision, profile_sha256(profile),
        ProfileConditions(1, "2025-09-02 05:10", 1, 2, SettlementMode.ALL),
        ProfileSelector(1, "static-numbers/v1", 1, numbers=(0,)),
        ProfileAudazStaking(), "all_rows/v1",
    )
    with pytest.raises(ValueError, match="initial capital"):
        repo.create_profile_audaz_experiment(request)
    assert repo.list_experiments() == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
