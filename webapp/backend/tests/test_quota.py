"""Quota accounting is logical experiment data, not SQLite file size or source data."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import pytest

from laboratorio.domain.contracts import (
    Conditions,
    ExperimentRequest,
    SelectorKind,
    StakingStyle,
    Strategy,
)
from laboratorio.settings import DEFAULT_QUOTA_BYTES, Settings
from laboratorio.storage.database import initialize_database
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import QuotaBelowUsage, QuotaReadOnly, Repository


def request(name):
    return ExperimentRequest(
        name="Trial",
        conditions=Conditions(start_draw="2025-01-01 05:10", capital=100, goal=150, seed=42),
        strategies=(
            Strategy(
                name=name,
                selector=SelectorKind.SYSTEM,
                system="cold",
                coverage=1,
                staking=StakingStyle.FLAT,
            ),
        ),
    )


def disk(free):
    return SimpleNamespace(total=10 * 1024**3, used=10 * 1024**3 - free, free=free)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "laboratorio.db"
    initialize_database(path)
    return Repository(path)


def test_default_and_invalid_configured_quota(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "source.json", tmp_path / "rank.npz", tmp_path)
    assert settings.quota_bytes == DEFAULT_QUOTA_BYTES == 5 * 1024**3
    for invalid in (0, -1, True, 1.5, "5000000000", 2**63):
        with pytest.raises(ValueError, match="quota"):
            replace(settings, quota_bytes=invalid)
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", "2147483648")
    assert Settings.from_environment().quota_bytes == 2147483648
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", "invalid")
    with pytest.raises(ValueError, match="LABORATORIO_QUOTA_BYTES"):
        Settings.from_environment()


def test_preference_persists_and_effective_precedence(repo):
    initial = repo.effective_quota()
    assert (initial.effective_bytes, initial.persisted_bytes, initial.source, initial.writable) == (
        DEFAULT_QUOTA_BYTES,
        None,
        "default",
        True,
    )
    assert repo.set_quota_preference(2 * 1024**3) == 2 * 1024**3
    reopened = Repository(repo.path)
    assert reopened.get_quota_preference() == 2 * 1024**3
    assert reopened.effective_quota().source == "persisted"
    assert reopened.quota_status().limit_bytes == 2 * 1024**3
    capacity = reopened.require_capacity(disk_usage=lambda _: disk(2 * 1024**3))
    assert capacity.limit_bytes == 2 * 1024**3
    env = reopened.effective_quota(DEFAULT_QUOTA_BYTES, quota_explicit=True)
    assert (env.effective_bytes, env.persisted_bytes, env.source, env.writable) == (
        DEFAULT_QUOTA_BYTES,
        2 * 1024**3,
        "environment",
        False,
    )
    status = reopened.quota_status(DEFAULT_QUOTA_BYTES, quota_explicit=False)
    assert status.limit_bytes == 2 * 1024**3
    # Historical explicit callers retain their supplied override unless they pass provenance.
    assert reopened.quota_status(DEFAULT_QUOTA_BYTES).limit_bytes == DEFAULT_QUOTA_BYTES
    assert reopened.effective_quota(DEFAULT_QUOTA_BYTES).source == "override"
    with pytest.raises(QuotaReadOnly):
        reopened.set_quota_preference(3 * 1024**3, quota_explicit=True)
    assert reopened.get_quota_preference() == 2 * 1024**3


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "100", 2**63])
def test_preference_requires_strict_sqlite_int(repo, invalid):
    with pytest.raises(ValueError, match="quota"):
        repo.set_quota_preference(invalid)
    assert repo.get_quota_preference() is None
    with pytest.raises(ValueError, match="quota"):
        repo.effective_quota(invalid)


def test_preference_below_usage_rolls_back_and_equal_allowed(repo):
    identifier = repo.create_experiment(
        request("First"),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    used = repo.logical_experiment_bytes()
    assert used > 1
    repo.set_quota_preference(used)
    with pytest.raises(QuotaBelowUsage):
        repo.set_quota_preference(used - 1)
    assert Repository(repo.path).get_quota_preference() == used
    assert repo.get_experiment(identifier) is not None
    repo.set_quota_preference(2**63 - 1)
    assert repo.get_quota_preference() == 2**63 - 1


def test_write_boundary_rereads_preference_after_stale_preflight(repo):
    generous = 2 * 1024**3
    repo.set_quota_preference(generous)
    repo.require_capacity(disk_usage=lambda _: disk(generous))
    repo.set_quota_preference(1)
    with pytest.raises(QuotaExceeded):
        repo.create_experiment(
            request("First"),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
            quota_bytes=generous,
            quota_explicit=False,
            disk_usage=lambda _: disk(generous),
        )
    assert repo.list_experiments() == []
    # Legacy explicit override deliberately retains its prior semantics.
    identifier = repo.create_experiment(
        request("First"),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
        quota_bytes=generous,
        disk_usage=lambda _: disk(generous),
    )
    repo.start_run(identifier, 0)
    from laboratorio.domain.contracts import Outcome, RunStatus
    from laboratorio.domain.session import Bet, SessionResult

    bet = Bet("2025-01-01 05:10", (7,), 1, 1, (7, 8, 9, 10, 11), 80, 179)
    result = SessionResult(Outcome.GOAL, 1, 1, 80, 179, (bet,))
    with pytest.raises(QuotaExceeded):
        repo.complete_run(
            identifier,
            0,
            result,
            quota_bytes=generous,
            quota_explicit=False,
            disk_usage=lambda _: disk(generous),
        )
    assert repo.get_experiment(identifier).runs[0].status is RunStatus.RUNNING
    repo.complete_run(
        identifier, 0, result, quota_bytes=generous, disk_usage=lambda _: disk(generous)
    )
    assert repo.get_experiment(identifier).runs[0].status is RunStatus.COMPLETED


def test_concurrent_preference_cannot_undercut_in_flight_write(repo):
    inside_write = Event()
    release_write = Event()

    def paused_disk_usage(_):
        inside_write.set()
        assert release_write.wait(5)
        return disk(2 * 1024**3)

    def insert():
        return repo.create_experiment(
            request("First"),
            history_id="history",
            history_sha256="a" * 64,
            rankings_id="rankings",
            rankings_sha256="b" * 64,
            code_version="v1",
            disk_usage=paused_disk_usage,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(insert)
        try:
            assert inside_write.wait(5)
            setter = pool.submit(repo.set_quota_preference, 1)
        finally:
            release_write.set()
        identifier = future.result(timeout=10)
        with pytest.raises(QuotaBelowUsage):
            setter.result(timeout=10)
    assert repo.get_experiment(identifier) is not None
    assert repo.get_quota_preference() is None


def test_logical_usage_excludes_original_inputs_and_physical_overhead(repo, tmp_path):
    (tmp_path / "source.json").write_bytes(b"x" * 4096)
    (tmp_path / "rank.npz").write_bytes(b"x" * 4096)
    empty = repo.quota_status(5 * 1024**3, disk_usage=lambda _: disk(2 * 1024**3))
    assert empty.logical_used_bytes == 0
    identifier = repo.create_experiment(
        request("First"),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    status = repo.quota_status(5 * 1024**3, disk_usage=lambda _: disk(2 * 1024**3))
    assert status.logical_used_bytes > 0
    assert status.logical_used_bytes < 4096
    assert status.sqlite_bytes >= repo.path.stat().st_size
    assert status.free_disk_bytes == 2 * 1024**3
    assert status.limit_bytes == 5 * 1024**3
    assert repo.get_experiment(identifier) is not None


def test_sqlite_wal_and_temporary_sidecars_reported_separately(repo, monkeypatch):
    # A real SQLite open can clean up stale sidecars; isolate measurement itself.
    monkeypatch.setattr(repo, "logical_experiment_bytes", lambda: 0)
    for suffix, size in (("-wal", 47), ("-shm", 31), ("-journal", 13)):
        (repo.path.parent / (repo.path.name + suffix)).write_bytes(b"a" * size)
    status = repo.quota_status(5 * 1024**3, disk_usage=lambda _: disk(2 * 1024**3))
    assert status.wal_bytes == 47
    assert status.temp_bytes == 13
    assert status.sqlite_bytes == repo.path.stat().st_size + 47 + 31 + 13
    assert status.disk_margin_bytes > 0
    assert status.logical_margin_bytes > 0


def test_below_at_and_above_threshold_and_free_disk_independent(repo, monkeypatch):
    limit = 5 * 1024**3
    base = repo.quota_status(limit, disk_usage=lambda _: disk(2 * 1024**3))
    threshold = limit - base.logical_margin_bytes
    monkeypatch.setattr(repo, "logical_experiment_bytes", lambda: threshold - 1)
    repo.require_capacity(limit, disk_usage=lambda _: disk(2 * 1024**3))
    monkeypatch.setattr(repo, "logical_experiment_bytes", lambda: threshold)
    with pytest.raises(QuotaExceeded, match="quota"):
        repo.require_capacity(limit, disk_usage=lambda _: disk(2 * 1024**3))
    monkeypatch.setattr(repo, "logical_experiment_bytes", lambda: threshold + 1)
    with pytest.raises(QuotaExceeded, match="quota"):
        repo.require_capacity(limit, disk_usage=lambda _: disk(2 * 1024**3))
    monkeypatch.setattr(repo, "logical_experiment_bytes", lambda: 0)
    with pytest.raises(QuotaExceeded, match="disk"):
        repo.require_capacity(limit, disk_usage=lambda _: disk(base.disk_margin_bytes))
    repo.require_capacity(limit, disk_usage=lambda _: disk(base.disk_margin_bytes + 1))


def test_result_write_checks_exact_utf8_bytes_before_commit(repo):
    from laboratorio.domain.contracts import ExperimentStatus, Outcome
    from laboratorio.domain.session import Bet, SessionResult

    identifier = repo.create_experiment(
        request("First"),
        history_id="history",
        history_sha256="a" * 64,
        rankings_id="rankings",
        rankings_sha256="b" * 64,
        code_version="v1",
    )
    repo.start_run(identifier, 0)
    bet = Bet("2025-01-01 05:10", (7,), 1, 1, (7, 8, 9, 10, 11), 80, 179)
    result = SessionResult(Outcome.GOAL, 1, 1, 80, 179, (bet,))
    used = repo.logical_experiment_bytes()
    limit = used + 100
    with pytest.raises(QuotaExceeded):
        repo.complete_run(
            identifier, 0, result, quota_bytes=limit, disk_usage=lambda _: disk(2 * 1024**3)
        )
    saved = repo.get_experiment(identifier)
    assert saved.status is ExperimentStatus.RUNNING
    assert saved.runs[0].result is None
