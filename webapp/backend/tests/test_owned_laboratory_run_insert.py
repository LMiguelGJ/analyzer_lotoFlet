import hashlib
import json
import sqlite3
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest

import laboratorio.storage.owned_laboratory_run_store as owned_run_store
from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.database import connection
from laboratorio.storage.owned_laboratory_run_store import (
    OwnedLaboratoryRunStoreError,
    create_run,
)
from laboratorio.storage.quota import QuotaExceeded

_HISTORY_SHA256 = "a" * 64
_RANKINGS_SHA256 = "b" * 64


def _definition(repo, name="Owned insert"):
    config = replace(
        initial_laboratory_definitions()[0].config,
        capital=2001,
        goal=2801,
    )
    return repo.create_laboratory_definition(name, config, quota_bytes=10**9, quota_explicit=True)


def _snapshot(definition):
    return OwnedLaboratoryRunSnapshot(definition, _HISTORY_SHA256, _RANKINGS_SHA256)


def _result(lab_id, capital):
    session = {
        "outcome": "goal",
        "start_index": 0,
        "end_index": 0,
        "draws": 1,
        "final_balance": capital + 10,
        "wagered": 1,
        "paid": 11,
    }
    digest_rows = [
        [
            session[key]
            for key in (
                "outcome",
                "start_index",
                "end_index",
                "draws",
                "final_balance",
                "wagered",
                "paid",
            )
        ]
    ]
    digest = hashlib.sha256(json.dumps(digest_rows, separators=(",", ":")).encode()).hexdigest()
    return {
        "lab_id": lab_id,
        "sessions": [session],
        "totals": {
            "completed": 1,
            "incomplete": 0,
            "goals": 1,
            "ruins": 0,
            "sessions_total": 1,
            "total_wagered": 1,
            "total_paid": 11,
            "total_net": 10,
            "total_steps": 1,
            "mean_net_closed": 10.0,
        },
        "eligible_draws": 1,
        "gaps": 0,
        "first": "draw-1",
        "last": "draw-1",
        "session_sha256": digest,
    }


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _save(repo, definition, run_id=None, *, snapshot=None, result=None, quota_bytes=10**9):
    snapshot = _snapshot(definition) if snapshot is None else snapshot
    result = _result(definition.id, definition.config.capital) if result is None else result
    return repo.create_owned_laboratory_run(
        run_id or str(uuid.uuid4()),
        definition.id,
        snapshot,
        result,
        quota_bytes=quota_bytes,
        quota_explicit=True,
    )


def _counts(repo):
    with connection(repo.path) as db:
        return (
            db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0],
            db.execute("SELECT count(*) FROM reference_lab_sessions").fetchone()[0],
        )


def test_repository_owned_insert_round_trips_canonical_owned_run_without_mutation(repo):
    definition = _definition(repo)
    snapshot = _snapshot(definition)
    result = _result(definition.id, definition.config.capital)
    snapshot_before = snapshot.to_mapping()
    result_before = json.loads(json.dumps(result))
    run_id = str(uuid.uuid4())

    assert _save(repo, definition, run_id, snapshot=snapshot, result=result) == run_id

    with connection(repo.path) as db:
        row = db.execute(
            "SELECT id,lab_id,contract_version,created_at,metadata_json,result_json,"
            "owner_laboratory_id FROM reference_lab_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        session_rows = db.execute(
            "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=?",
            (run_id,),
        ).fetchall()
        version = db.execute("PRAGMA user_version").fetchone()[0]
    stored_snapshot = snapshot.to_mapping()
    expected_sessions = result["sessions"]
    assert row[0:3] == (run_id, definition.id, 1)
    assert row[3]
    assert row[4] == _canonical(stored_snapshot)
    assert row[5] == _canonical({"schema_version": 1, "result": result})
    assert row[6] == definition.id
    assert session_rows == [(0, _canonical(expected_sessions[0]))]
    assert version == 17
    assert repo.get_owned_laboratory_run(definition.id, run_id) == {
        "id": run_id,
        "owner_laboratory_id": definition.id,
        "lab_id": definition.id,
        "contract_version": 1,
        "created_at": row[3],
        "snapshot": stored_snapshot,
        "result": result,
        "sessions": expected_sessions,
    }
    assert repo.list_reference_lab_runs(lab_id=definition.id)["total"] == 0
    assert snapshot.to_mapping() == snapshot_before
    assert result == result_before


def test_direct_create_run_returns_id_and_persists_validated_result(repo):
    definition = _definition(repo, "Direct owned insert")
    run_id = str(uuid.uuid4())

    assert (
        create_run(
            repo,
            run_id,
            definition.id,
            _snapshot(definition),
            _result(definition.id, definition.config.capital),
            quota_bytes=10**9,
            quota_explicit=True,
        )
        == run_id
    )
    assert repo.get_owned_laboratory_run(definition.id, run_id)["id"] == run_id


@pytest.mark.parametrize(
    ("run_id", "owner_id"),
    [
        (True, "valid-owner"),
        (1, "valid-owner"),
        (None, "valid-owner"),
        ("not-a-uuid", "valid-owner"),
        ("00000000-0000-0000-0000-00000000000A", "valid-owner"),
        ("valid-run", True),
        ("valid-run", 1),
        ("valid-run", None),
        ("valid-run", "not-a-uuid"),
        ("valid-run", "00000000-0000-0000-0000-00000000000A"),
    ],
    ids=[
        "run-bool",
        "run-int",
        "run-none",
        "run-malformed",
        "run-noncanonical",
        "owner-bool",
        "owner-int",
        "owner-none",
        "owner-malformed",
        "owner-noncanonical",
    ],
)
def test_invalid_identifiers_fail_before_either_insert(repo, run_id, owner_id):
    definition = _definition(repo)
    if owner_id == "valid-owner":
        owner_id = definition.id
    if run_id == "valid-run":
        run_id = str(uuid.uuid4())
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        create_run(
            repo,
            run_id,
            owner_id,
            _snapshot(definition),
            _result(definition.id, definition.config.capital),
            quota_bytes=10**9,
            quota_explicit=True,
        )

    assert _counts(repo) == before


class _SnapshotSubclass(OwnedLaboratoryRunSnapshot):
    pass


@pytest.mark.parametrize("snapshot_kind", ["mapping", "fake", "subclass"])
def test_snapshot_requires_exact_validated_snapshot_type(repo, snapshot_kind):
    definition = _definition(repo)
    snapshot = _snapshot(definition)
    if snapshot_kind == "mapping":
        snapshot = snapshot.to_mapping()
    elif snapshot_kind == "fake":
        snapshot = SimpleNamespace(to_mapping=snapshot.to_mapping)
    else:
        snapshot = _SnapshotSubclass(definition, _HISTORY_SHA256, _RANKINGS_SHA256)
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition, snapshot=snapshot)

    assert _counts(repo) == before


@pytest.mark.parametrize(
    "mismatch", ["snapshot-owner", "result-owner", "invalid-numeric", "session-total"]
)
def test_invalid_identity_or_shared_result_contract_writes_no_rows(repo, mismatch):
    definition = _definition(repo)
    other = _definition(repo, "Other valid definition")
    snapshot = _snapshot(definition)
    result = _result(definition.id, definition.config.capital)
    if mismatch == "snapshot-owner":
        snapshot = _snapshot(other)
    elif mismatch == "result-owner":
        result = _result(other.id, other.config.capital)
    elif mismatch == "invalid-numeric":
        result["totals"]["completed"] = True
    else:
        result["totals"]["sessions_total"] = 2
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition, snapshot=snapshot, result=result)

    assert _counts(repo) == before


def test_missing_definition_rejects_snapshot_before_any_rows_are_written(repo):
    definition = _definition(repo)
    snapshot = _snapshot(definition)
    repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition, snapshot=snapshot)

    assert _counts(repo) == before


def test_changed_valid_current_definition_rejects_old_snapshot(repo):
    definition = _definition(repo)
    edited = replace(
        definition,
        config=replace(definition.config, capital=definition.config.capital + 1),
    )
    encoded = _canonical(edited.to_mapping())
    with connection(repo.path) as db:
        db.execute(
            "UPDATE laboratory_definitions SET name=?,name_key=?,definition_json=?,"
            "definition_bytes=? WHERE id=?",
            (
                edited.name,
                edited.name.casefold(),
                encoded,
                len(encoded.encode("utf-8")),
                definition.id,
            ),
        )
        db.commit()
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition)

    assert _counts(repo) == before


def test_corrupt_current_definition_fails_closed_without_owned_rows(repo):
    definition = _definition(repo)
    with connection(repo.path) as db:
        db.execute(
            "UPDATE laboratory_definitions SET definition_json='{' WHERE id=?",
            (definition.id,),
        )
        db.commit()
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition)

    assert _counts(repo) == before


def test_recreated_same_name_with_new_uuid_does_not_accept_old_snapshot(repo):
    definition = _definition(repo, "Recreated laboratory")
    old_snapshot = _snapshot(definition)
    repo.delete_laboratory_definition(definition.id, confirmed_run_count=0)
    recreated = _definition(repo, "Recreated laboratory")
    assert recreated.id != definition.id
    before = _counts(repo)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, recreated, snapshot=old_snapshot)

    assert _counts(repo) == before


def test_duplicate_run_preserves_original_rows_and_shared_quota(repo):
    definition = _definition(repo, "Duplicate owner")
    run_id = _save(repo, definition)
    before_rows = _counts(repo)
    before_quota = repo.admission_logical_bytes()
    before_run_bytes = repo.quota_status().run_artifact_bytes

    with pytest.raises(sqlite3.IntegrityError):
        _save(repo, definition, run_id)

    assert _counts(repo) == before_rows
    assert repo.admission_logical_bytes() == before_quota
    assert repo.quota_status().run_artifact_bytes == before_run_bytes
    assert repo.get_owned_laboratory_run(definition.id, run_id) is not None


def test_shared_quota_charges_exact_persisted_utf8_run_and_session_bytes(repo):
    definition = _definition(repo, "UTF-8 laboratory ñ")
    before_admission = repo.admission_logical_bytes()
    before_run_bytes = repo.quota_status().run_artifact_bytes
    run_id = _save(repo, definition)
    with connection(repo.path) as db:
        row = db.execute(
            "SELECT id,lab_id,created_at,metadata_json,result_json "
            "FROM reference_lab_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        session_bytes = db.execute(
            "SELECT sum(length(CAST(run_id AS BLOB)) + 8 + "
            "length(CAST(session_json AS BLOB))) FROM reference_lab_sessions "
            "WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
    persisted_run_bytes = (
        len(row[0].encode())
        + len(row[1].encode())
        + 8
        + len(row[2].encode())
        + len(row[3].encode("utf-8"))
        + len(row[4].encode("utf-8"))
        + session_bytes
    )

    assert repo.quota_status().run_artifact_bytes - before_run_bytes == persisted_run_bytes
    assert repo.admission_logical_bytes() - before_admission == persisted_run_bytes


def test_quota_denial_leaves_run_session_counts_and_logical_usage_unchanged(repo):
    definition = _definition(repo, "Denied owned run")
    before_rows = _counts(repo)
    before_admission = repo.admission_logical_bytes()

    with pytest.raises(QuotaExceeded):
        _save(repo, definition, quota_bytes=1)

    assert _counts(repo) == before_rows
    assert repo.admission_logical_bytes() == before_admission


def test_session_insert_failure_rolls_back_run_and_preserves_existing_run(repo):
    definition = _definition(repo, "Atomic owned runs")
    existing_id = _save(repo, definition)
    before_rows = _counts(repo)
    before_admission = repo.admission_logical_bytes()
    with connection(repo.path) as db:
        db.execute(
            "CREATE TRIGGER reject_owned_session BEFORE INSERT ON reference_lab_sessions "
            "BEGIN SELECT RAISE(ABORT, 'owned-session-insert-fault'); END"
        )
        db.commit()

    failed_id = str(uuid.uuid4())
    with pytest.raises(sqlite3.IntegrityError, match="owned-session-insert-fault"):
        _save(repo, definition, failed_id)

    assert _counts(repo) == before_rows
    assert repo.admission_logical_bytes() == before_admission
    assert repo.get_owned_laboratory_run(definition.id, existing_id) is not None
    assert repo.get_owned_laboratory_run(definition.id, failed_id) is None


def test_payload_limit_rejection_uses_small_test_limit_without_partial_rows(repo, monkeypatch):
    definition = _definition(repo, "Small payload limit")
    before = _counts(repo)
    monkeypatch.setattr(owned_run_store, "MAX_PAYLOAD_BYTES", 1)

    with pytest.raises(OwnedLaboratoryRunStoreError):
        _save(repo, definition)

    assert _counts(repo) == before
