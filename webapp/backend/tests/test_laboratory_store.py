import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from laboratorio.domain.laboratories import (
    create_laboratory_definition,
    initial_laboratory_definitions,
)
from laboratorio.storage.database import connection, initialize_database
from laboratorio.storage.laboratory_store import (
    LaboratoryDefinitionConflict,
    LaboratoryStoreError,
)
from laboratorio.storage.quota import QuotaExceeded

_CONFIG = initial_laboratory_definitions()[0].config


def _create(repo, name="Manual ñ", **kwargs):
    return repo.create_laboratory_definition(name, _CONFIG, **kwargs)


def test_manual_definition_create_and_read_round_trip(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)

    assert definition.name == "Manual ñ"
    assert definition.config == _CONFIG
    assert repo.get_laboratory_definition(definition.id) == definition


def test_creation_charges_exact_canonical_utf8_snapshot_once(repo):
    before = repo.admission_logical_bytes()
    before_definitions = repo.quota_status().laboratory_definition_bytes
    run_bytes = repo.quota_status().run_artifact_bytes
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    snapshot = json.dumps(
        definition.to_mapping(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    expected = len(snapshot.encode("utf-8"))

    with connection(repo.path) as db:
        stored, byte_count = db.execute(
            "SELECT definition_json,definition_bytes FROM laboratory_definitions WHERE id=?",
            (definition.id,),
        ).fetchone()
    assert stored == snapshot
    assert byte_count == expected
    assert repo.admission_logical_bytes() - before == expected
    assert repo.quota_status().laboratory_definition_bytes - before_definitions == expected
    assert repo.quota_status().run_artifact_bytes == run_bytes == 0


def test_creation_rejects_overquota_without_changing_rows_or_metrics(repo):
    before = repo.admission_logical_bytes()
    definitions = repo.list_laboratory_definitions(limit=100)["total"]

    with pytest.raises(QuotaExceeded):
        _create(repo, quota_bytes=1, quota_explicit=True)

    assert repo.admission_logical_bytes() == before
    assert repo.list_laboratory_definitions(limit=100)["total"] == definitions
    assert repo.quota_status().run_artifact_bytes == 0
    assert repo.quota_status().history_artifact_bytes == 0


def test_casefold_duplicate_conflicts_even_under_concurrent_creation(repo):
    barrier = Barrier(2)

    def create(name):
        barrier.wait()
        try:
            return _create(repo, name, quota_bytes=10**9, quota_explicit=True)
        except LaboratoryDefinitionConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("Café", "CAFÉ")))

    assert sum(item is not None for item in results) == 1
    assert repo.list_laboratory_definitions(limit=100)["total"] == 15


def test_concurrent_quota_admission_accepts_only_one_definition(repo):
    barrier = Barrier(2)
    before = repo.admission_logical_bytes()
    sample = create_laboratory_definition("Quota A", _CONFIG)
    payload_bytes = len(
        json.dumps(
            sample.to_mapping(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )
    limit = before + payload_bytes + 1
    while True:
        adjusted = before + payload_bytes + min(1024**2, max(1, limit // 20)) + 1
        if adjusted == limit:
            break
        limit = adjusted

    def create(name):
        barrier.wait()
        try:
            _create(repo, name, quota_bytes=limit, quota_explicit=True)
            return True
        except QuotaExceeded:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create, ("Quota A", "Quota B")))

    assert sorted(outcomes) == [False, True]
    assert repo.admission_logical_bytes() - before == payload_bytes
    assert repo.list_laboratory_definitions(limit=100)["total"] == 15


def test_seed_definitions_are_strictly_readable_and_paged_stably(repo):
    seeds = initial_laboratory_definitions()
    for seed in seeds:
        assert repo.get_laboratory_definition(seed.id) == seed
    manual = [
        _create(repo, f"Manual {i}", quota_bytes=10**9, quota_explicit=True) for i in range(2)
    ]
    with connection(repo.path) as db:
        db.execute("UPDATE laboratory_definitions SET created_at='2025-01-01T00:00:00.000000Z'")
        db.commit()

    first = repo.list_laboratory_definitions(limit=5)
    second = repo.list_laboratory_definitions(offset=5, limit=5)
    ordered = sorted([*seeds, *manual], key=lambda item: item.id, reverse=True)
    assert (first["total"], first["offset"], first["limit"]) == (16, 0, 5)
    assert first["items"] == ordered[:5]
    assert second["items"] == ordered[5:10]
    assert repo.list_laboratory_definitions(offset=16)["items"] == []
    assert repo.get_laboratory_definition(str(uuid.uuid4())) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"offset": True},
        {"offset": -1},
        {"offset": 2**63},
        {"limit": True},
        {"limit": 0},
        {"limit": 101},
    ],
)
def test_paging_rejects_bool_negative_and_unsafe_values(repo, kwargs):
    with pytest.raises(ValueError):
        repo.list_laboratory_definitions(**kwargs)


def test_listing_validates_only_the_requested_page(repo):
    with connection(repo.path) as db:
        identifier = db.execute(
            "SELECT id FROM laboratory_definitions ORDER BY id LIMIT 1"
        ).fetchone()[0]
        db.execute("UPDATE laboratory_definitions SET name_key='corrupt' WHERE id=?", (identifier,))
        db.commit()

    assert len(repo.list_laboratory_definitions(limit=1)["items"]) == 1
    with pytest.raises(LaboratoryStoreError, match="stored laboratory definition is corrupt"):
        repo.get_laboratory_definition(identifier)


@pytest.mark.parametrize(
    "column,value",
    [
        ("name", "Other"),
        ("name_key", "wrong-key"),
        ("definition_bytes", 1),
        ("definition_json", '{ "schema_version": 1 }'),
    ],
)
def test_reads_fail_closed_on_row_snapshot_namekey_and_byte_corruption(repo, column, value):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    with connection(repo.path) as db:
        db.execute(
            f"UPDATE laboratory_definitions SET {column}=? WHERE id=?", (value, definition.id)
        )
        db.commit()

    with pytest.raises(LaboratoryStoreError, match="stored laboratory definition is corrupt"):
        repo.get_laboratory_definition(definition.id)


def test_failed_sql_insert_rolls_back_without_charging_or_leaving_a_row(repo, monkeypatch):
    seed = initial_laboratory_definitions()[0]
    import laboratorio.domain.laboratories as domain

    monkeypatch.setattr(domain.uuid, "uuid4", lambda: uuid.UUID(seed.id))
    before = repo.admission_logical_bytes()
    count = repo.list_laboratory_definitions(limit=100)["total"]

    with pytest.raises(LaboratoryStoreError, match="could not store laboratory definition"):
        _create(repo, "Unique manual", quota_bytes=10**9, quota_explicit=True)

    assert repo.admission_logical_bytes() == before
    assert repo.list_laboratory_definitions(limit=100)["total"] == count
    assert repo.quota_status().run_artifact_bytes == 0


def test_invalid_definition_input_and_identifier_are_rejected(repo):
    with pytest.raises(ValueError):
        repo.create_laboratory_definition(" trimmed ", _CONFIG, quota_bytes=10**9)
    with pytest.raises(ValueError, match="canonical UUID"):
        repo.get_laboratory_definition("NOT-A-UUID")


def test_definition_can_be_deleted_after_confirming_owned_run_count(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)

    deleted = repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)

    assert deleted["id"] == definition.id
    assert deleted["definition_bytes"] > 0
    assert deleted["owned_run_count"] == deleted["owned_session_count"] == 0
    assert repo.get_laboratory_definition(definition.id) is None


def _insert_reference_run(db, run_id, lab_id, owner_id=None, sessions=1):
    db.execute(
        "INSERT INTO reference_lab_runs "
        "(id,lab_id,contract_version,created_at,metadata_json,result_json,"
        "owner_laboratory_id) VALUES (?, ?, 1, '2025-01-01T00:00:00.000000Z', '{}', '{}', ?)",
        (run_id, lab_id, owner_id),
    )
    for ordinal in range(sessions):
        db.execute("INSERT INTO reference_lab_sessions VALUES (?, ?, '{}')", (run_id, ordinal))


def test_owned_counts_and_delete_cascade_preserve_unowned_and_other_owner_data(repo):
    definition = _create(repo, "Owner", quota_bytes=10**9, quota_explicit=True)
    other = _create(repo, "Other", quota_bytes=10**9, quota_explicit=True)
    owned_id, other_id, legacy_same, legacy_alias, trial_id = (str(uuid.uuid4()) for _ in range(5))
    with connection(repo.path) as db:
        _insert_reference_run(db, owned_id, definition.id, definition.id, sessions=2)
        _insert_reference_run(db, other_id, other.id, other.id, sessions=1)
        _insert_reference_run(db, legacy_same, definition.id)
        _insert_reference_run(db, legacy_alias, "legacy-static-id")
        _insert_reference_run(db, trial_id, "custom-trial-id")
        db.execute(
            "UPDATE reference_lab_runs SET metadata_json='not-json',result_json='not-json' "
            "WHERE id=?",
            (owned_id,),
        )
        db.commit()

    assert repo.get_laboratory_owned_counts(definition.id) == {
        "owned_run_count": 1,
        "owned_session_count": 2,
    }
    before = repo.admission_logical_bytes()
    before_definition_bytes = repo.quota_status().laboratory_definition_bytes
    before_run_bytes = repo.quota_status().run_artifact_bytes
    deleted = repo.delete_laboratory_definition(definition.id, confirmed_run_count=1)

    assert deleted["owned_run_count"] == 1
    assert deleted["owned_session_count"] == 2
    assert repo.admission_logical_bytes() == before - deleted["definition_bytes"] - (
        before_run_bytes - repo.quota_status().run_artifact_bytes
    )
    assert (
        before_definition_bytes - repo.quota_status().laboratory_definition_bytes
        == deleted["definition_bytes"]
    )
    with connection(repo.path) as db:
        survivors = db.execute(
            "SELECT id,owner_laboratory_id FROM reference_lab_runs ORDER BY id"
        ).fetchall()
        session_runs = db.execute(
            "SELECT run_id FROM reference_lab_sessions ORDER BY run_id"
        ).fetchall()
        assert session_runs == sorted([(legacy_alias,), (legacy_same,), (other_id,), (trial_id,)])
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert survivors == sorted(
        [(legacy_alias, None), (legacy_same, None), (other_id, other.id), (trial_id, None)]
    )
    replacement = _create(repo, "OWNER", quota_bytes=10**9, quota_explicit=True)
    assert replacement.id != definition.id
    assert repo.get_laboratory_owned_counts(replacement.id) == {
        "owned_run_count": 0,
        "owned_session_count": 0,
    }
    with connection(repo.path) as db:
        assert db.execute(
            "SELECT id FROM reference_lab_runs WHERE id IN (?, ?) ORDER BY id",
            (legacy_same, legacy_alias),
        ).fetchall() == sorted([(legacy_alias,), (legacy_same,)])


def test_deleting_seed_does_not_reseed_when_database_is_reopened(repo):
    from laboratorio.domain.laboratories import initial_laboratory_definitions

    seed = initial_laboratory_definitions()[0]
    assert repo.delete_laboratory_definition(seed.id, confirmed_run_count=0)["id"] == seed.id
    initialize_database(repo.path)
    assert repo.get_laboratory_definition(seed.id) is None


def test_owned_count_stale_confirmation_and_missing_definition_are_safe(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    run_id = str(uuid.uuid4())
    with connection(repo.path) as db:
        _insert_reference_run(db, run_id, definition.id, definition.id)
        db.commit()

    with pytest.raises(LaboratoryDefinitionConflict, match="count changed"):
        repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)
    assert repo.get_laboratory_definition(definition.id) == definition
    missing_id = str(uuid.uuid4())
    assert repo.get_laboratory_owned_counts(missing_id) is None
    assert repo.delete_laboratory_definition(missing_id, confirmed_run_count=0) is None
    with pytest.raises(ValueError, match="canonical UUID"):
        repo.get_laboratory_owned_counts("NOT-A-UUID")


@pytest.mark.parametrize("value", [True, False, -1, 1.0, 2**63, None])
def test_delete_confirmation_requires_safe_nonnegative_integer_before_mutation(repo, value):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    with pytest.raises(TypeError):
        repo.delete_laboratory_definition(definition.id)
    with pytest.raises(ValueError, match="safe integer"):
        repo.delete_laboratory_definition(definition.id, confirmed_run_count=value)
    assert repo.get_laboratory_definition(definition.id) == definition


def test_corrupt_definition_cannot_be_counted_or_deleted(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    with connection(repo.path) as db:
        db.execute("UPDATE laboratory_definitions SET name_key='bad' WHERE id=?", (definition.id,))
        db.commit()
    with pytest.raises(LaboratoryStoreError, match="stored laboratory definition is corrupt"):
        repo.get_laboratory_owned_counts(definition.id)
    with pytest.raises(LaboratoryStoreError, match="stored laboratory definition is corrupt"):
        repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)
    with connection(repo.path) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM laboratory_definitions WHERE id=?", (definition.id,)
            ).fetchone()[0]
            == 1
        )


def test_sql_delete_failure_rolls_back_definition_and_owned_artifacts(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    run_id = str(uuid.uuid4())
    with connection(repo.path) as db:
        _insert_reference_run(db, run_id, definition.id, definition.id, sessions=2)
        db.execute(
            "CREATE TRIGGER fail_definition_delete BEFORE DELETE ON laboratory_definitions "
            "BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
        db.commit()
    before = repo.admission_logical_bytes()
    with pytest.raises(LaboratoryStoreError, match="could not delete"):
        repo.delete_laboratory_definition(definition.id, confirmed_run_count=1)
    assert repo.get_laboratory_definition(definition.id) == definition
    assert repo.get_laboratory_owned_counts(definition.id) == {
        "owned_run_count": 1,
        "owned_session_count": 2,
    }
    assert repo.admission_logical_bytes() == before


def test_owned_run_insert_races_confirmed_delete_without_orphans(repo):
    definition = _create(repo, quota_bytes=10**9, quota_explicit=True)
    barrier = Barrier(2)
    run_id = str(uuid.uuid4())

    def insert_owned():
        barrier.wait()
        try:
            with connection(repo.path) as db:
                db.execute("BEGIN IMMEDIATE")
                _insert_reference_run(db, run_id, definition.id, definition.id)
                db.commit()
            return "inserted"
        except sqlite3.IntegrityError:
            return "rejected"

    def delete_confirmed():
        barrier.wait()
        try:
            repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)
            return "deleted"
        except LaboratoryDefinitionConflict:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        inserted, deleted = list(
            pool.map(lambda action: action(), (insert_owned, delete_confirmed))
        )
    assert (inserted, deleted) in (("rejected", "deleted"), ("inserted", "stale"))
    with connection(repo.path) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        run_count = db.execute(
            "SELECT count(*) FROM reference_lab_runs WHERE id=?", (run_id,)
        ).fetchone()[0]
        assert run_count == (inserted == "inserted")
