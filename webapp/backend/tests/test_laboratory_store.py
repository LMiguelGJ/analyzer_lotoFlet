import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from laboratorio.domain.laboratories import (
    create_laboratory_definition,
    initial_laboratory_definitions,
)
from laboratorio.storage.database import connection
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
