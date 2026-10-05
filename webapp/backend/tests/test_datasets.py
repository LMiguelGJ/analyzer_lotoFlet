"""Dataset promotion is an immutable, quota-admitted server reparse."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from types import SimpleNamespace

import pytest
from test_import_records import options, profile, row

from laboratorio.domain.contracts import SettlementMode
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector, ProfileStaking
from laboratorio.importing.records import parse_records
from laboratorio.storage.database import initialize_database
from laboratorio.storage.quota import LOGICAL_MARGIN_BYTES, QuotaExceeded
from laboratorio.storage.repository import QuotaBelowUsage, Repository


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "datasets.db"
    initialize_database(path)
    return Repository(path)


def raw():
    return json.dumps([row()], ensure_ascii=False).encode()


def promote(repo, data=None, **kwargs):
    return repo.promote_dataset(raw() if data is None else data, **{**options(), **kwargs})


def disk(_):
    return SimpleNamespace(free=2 * 1024**3)


def equality_limit(projected):
    return next(
        limit
        for limit in range(projected, 2 * projected + 20)
        if limit - min(LOGICAL_MARGIN_BYTES, max(1, limit // 20)) == projected
    )


# B-STO-065: invalid input and external previews never create persisted datasets.
def test_invalid_source_and_forged_preview_never_insert(repo):
    preview = parse_records(raw(), **options())
    assert preview.promotable
    with pytest.raises(TypeError):
        repo.promote_dataset(b"invalid", preview=preview, **options())
    with pytest.raises(ValueError, match="not promotable"):
        promote(repo, b"invalid")
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM datasets").fetchone()[0] == 0


# B-STO-066: canonical/raw hashes, source context, and duplicate identity are stable.
def test_canonical_utf8_raw_retention_context_identity_and_duplicate(repo):
    data = json.dumps([row()], indent=2).encode()
    first = promote(repo, data)
    canonical = first.dataset.canonical_json
    assert first.created and first.dataset.raw_bytes == data
    assert sha256(canonical).hexdigest() == first.dataset.dataset_sha256
    assert first.dataset.source_sha256 == sha256(data).hexdigest()
    expected = len(canonical) + len(data) + 128 + len(first.dataset.created_at.encode())
    assert repo.dataset_artifact_bytes() == expected
    other_raw = raw()
    duplicate = promote(
        repo, other_raw, quota_bytes=1, disk_usage=lambda _: SimpleNamespace(free=0)
    )
    assert not duplicate.created and duplicate.duplicate_source_differs
    assert duplicate.submitted_source_sha256 == sha256(other_raw).hexdigest()
    assert duplicate.dataset == first.dataset
    same = promote(repo, data, quota_bytes=1)
    assert not same.created and not same.duplicate_source_differs
    assert Repository(repo.path).get_dataset(first.dataset.dataset_sha256) == first.dataset
    assert repo.get_dataset("missing") is None
    assert repo.dataset_artifact_bytes() == expected
    changed = promote(
        repo,
        data,
        source=options()["source"].__class__("new-id", "historical", "v1", "manual upload"),
    )
    assert changed.created and changed.dataset.dataset_sha256 != first.dataset.dataset_sha256
    assert changed.dataset.raw_bytes == data


# B-STO-067: datasets contribute exact artifact bytes to shared quota accounting.
def test_quota_exact_delta_and_other_writes_include_datasets(repo):
    baseline = repo.admission_logical_bytes()
    data = raw()
    first = promote(repo, data)
    delta = repo.dataset_artifact_bytes()
    assert delta == len(data) + len(first.dataset.canonical_json) + 128 + len(
        first.dataset.created_at.encode()
    )
    assert repo.admission_logical_bytes() == baseline + delta
    assert repo.quota_status(disk_usage=disk).dataset_artifact_bytes == delta
    with pytest.raises(QuotaBelowUsage):
        repo.set_quota_preference(baseline + delta - 1)
    repo.set_quota_preference(baseline + delta)
    with pytest.raises(QuotaExceeded):
        promote(
            repo,
            data,
            source=options()["source"].__class__("new", "historical", "v1", "manual upload"),
            quota_explicit=False,
            disk_usage=disk,
        )
    assert repo.dataset_artifact_bytes() == delta
    assert repo.get_dataset(first.dataset.dataset_sha256) is not None


# B-STO-068: dataset equality boundary and failed insert leave accounting atomic.
def test_quota_boundary_failed_insert_and_rollback(repo):
    baseline = repo.admission_logical_bytes()
    data = raw()
    first = promote(repo, data)
    delta = repo.dataset_artifact_bytes()
    # Recreate the same boundary on another fresh database.
    path = repo.path.parent / "boundary.db"
    initialize_database(path)
    other = Repository(path)
    assert other.admission_logical_bytes() == baseline
    limit = equality_limit(baseline + delta)
    with pytest.raises(QuotaExceeded):
        promote(other, data, quota_bytes=limit, disk_usage=disk)
    assert other.dataset_artifact_bytes() == 0
    accepted_limit = next(
        candidate
        for candidate in range(limit + 1, limit + 20)
        if candidate - min(LOGICAL_MARGIN_BYTES, max(1, candidate // 20)) > baseline + delta
    )
    admitted = promote(other, data, quota_bytes=accepted_limit, disk_usage=disk).dataset
    assert admitted.canonical_json == first.dataset.canonical_json
    assert admitted.raw_bytes == first.dataset.raw_bytes
    assert other.dataset_artifact_bytes() == delta
    with sqlite3.connect(other.path) as db:
        db.execute(
            "CREATE TRIGGER reject_dataset BEFORE INSERT ON datasets "
            "BEGIN SELECT RAISE(ABORT, 'reject'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="reject"):
        promote(
            other,
            data,
            source=options()["source"].__class__("different", "historical", "v1", "manual upload"),
        )
    assert other.dataset_artifact_bytes() == delta


# B-STO-069: datasets are immutable and altered raw/context/canonical bytes fail closed.
def test_immutability_and_corrupt_bytes_context_rejected(repo):
    saved = promote(repo).dataset
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE datasets SET raw_bytes = X'00'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM datasets")
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute("UPDATE datasets SET raw_bytes = X'00'")
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.get_dataset(saved.dataset_sha256)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE datasets SET raw_bytes = ?", (raw(),))
        db.execute("UPDATE datasets SET source_sha256 = ?", ("0" * 64,))
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.get_dataset(saved.dataset_sha256)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE datasets SET source_sha256 = ?", (saved.source_sha256,))
        db.execute("UPDATE datasets SET canonical_json = '{}' ")
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.get_dataset(saved.dataset_sha256)


# B-STO-070: dataset pages slice before integrity checks and order ties deterministically.
def test_page_datasets_slices_before_integrity_work_and_orders_ties(repo, monkeypatch):
    import laboratorio.storage.repository as storage

    for source_id in ("a", "b", "c"):
        promote(repo, source=options()["source"].__class__(source_id, "historical", "v1", "manual"))
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute("UPDATE datasets SET created_at = ?", ("2025-01-01T00:00:00Z",))
        ordered = [
            row[0]
            for row in db.execute(
                "SELECT dataset_sha256 FROM datasets ORDER BY created_at, dataset_sha256"
            )
        ]
        db.execute("UPDATE datasets SET raw_bytes = X'00' WHERE dataset_sha256 = ?", (ordered[0],))
    checked = storage.checked_dataset
    seen = []

    def selected_only(row):
        seen.append(row[0])
        return checked(row)

    monkeypatch.setattr(storage, "checked_dataset", selected_only)
    total, page = repo.page_datasets(1, 2)
    assert total == 3 and [item.dataset_sha256 for item in page] == ordered[1:]
    assert seen == ordered[1:]
    assert repo.page_datasets(3, 2) == (3, [])
    assert seen == ordered[1:]
    with pytest.raises(ValueError, match="corrupt stored dataset"):
        repo.page_datasets(0, 1)
    for offset, limit in ((-1, 1), (0, 0), (0, 101), (True, 1), (0, True)):
        with pytest.raises(ValueError, match="out of range"):
            repo.page_datasets(offset, limit)


# B-STO-071: dataset preflight checks exact profile, selectors, start draw, and affordability.
def test_preflight_requires_exact_registered_embedded_profile_and_static_configs(repo):
    saved = promote(repo).dataset
    selected = profile()
    conditions = ProfileConditions(1, "2025-09-02 05:10", 100, 200, SettlementMode.ALL)
    selector = ProfileSelector(1, "static-numbers/v1", 1, (0,))
    random = ProfileSelector(
        1, "seeded-random/hash-sha256-v1", 1, seed=42, algorithm_version="hash-sha256-v1"
    )
    staking = ProfileStaking(1, "flat-per-number/v1", 1)
    with pytest.raises(ValueError, match="must be persisted"):
        repo.preflight_profile_dataset(
            saved.dataset_sha256, selected, conditions, selector, staking
        )
    repo.create_game_profile(selected)
    assert (
        repo.preflight_profile_dataset(
            saved.dataset_sha256, selected, conditions, selector, staking
        )
        == saved
    )
    assert (
        repo.preflight_profile_dataset(saved.dataset_sha256, selected, conditions, random, staking)
        == saved
    )
    different = selected.model_copy(update={"maximum_stake": 9})
    with pytest.raises(ValueError, match="differs"):
        repo.preflight_profile_dataset(
            saved.dataset_sha256, different, conditions, selector, staking
        )
    with pytest.raises(ValueError, match="start draw"):
        repo.preflight_profile_dataset(
            saved.dataset_sha256,
            selected,
            ProfileConditions(1, "2025-09-03 05:10", 100, 200, SettlementMode.ALL),
            selector,
            staking,
        )
    with pytest.raises(ValueError, match="static number"):
        repo.preflight_profile_dataset(
            saved.dataset_sha256,
            selected,
            conditions,
            ProfileSelector(1, "static-numbers/v1", 1, (100,)),
            staking,
        )
    with pytest.raises(ValueError, match="cannot afford"):
        repo.preflight_profile_dataset(
            saved.dataset_sha256,
            selected,
            conditions,
            ProfileSelector(1, "static-numbers/v1", 11, tuple(range(11))),
            ProfileStaking(1, "flat-per-number/v1", 10),
        )


# B-STO-072: concurrent promotion of one dataset charges exactly one artifact.
def test_concurrent_promotions_charge_once(repo):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: promote(repo), range(8)))
    assert sum(result.created for result in results) == 1
    assert len({result.dataset.dataset_sha256 for result in results}) == 1
    assert repo.dataset_artifact_bytes() == (
        len(results[0].dataset.canonical_json)
        + len(results[0].dataset.raw_bytes)
        + 128
        + len(results[0].dataset.created_at.encode())
    )
