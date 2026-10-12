import hashlib
import json
import uuid

from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.database import connection


def _legacy_record(lab_id):
    session = {
        "outcome": "goal",
        "start_index": 0,
        "end_index": 0,
        "draws": 1,
        "final_balance": 10,
        "wagered": 1,
        "paid": 1,
    }
    totals = {
        "completed": 1,
        "incomplete": 0,
        "goals": 1,
        "ruins": 0,
        "sessions_total": 1,
        "total_wagered": 1,
        "total_paid": 1,
        "total_net": 0,
        "total_steps": 1,
        "mean_net_closed": 0.0,
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
    return (
        {"lab_id": lab_id, "capital": 10},
        {
            "history_sha256": "a" * 64,
            "history_origin": "frozen",
            "rankings_sha256": "b" * 64,
        },
        {
            "lab_id": lab_id,
            "sessions": [session],
            "totals": totals,
            "eligible_draws": 1,
            "gaps": 0,
            "first": "first",
            "last": "last",
            "session_sha256": hashlib.sha256(
                json.dumps(digest_rows, separators=(",", ":")).encode()
            ).hexdigest(),
        },
    )


def _create_legacy(repo, run_id, lab_id):
    config, provenance, result = _legacy_record(lab_id)
    return repo.create_reference_lab_run(
        run_id,
        lab_id,
        config,
        provenance,
        result,
        quota_bytes=10**9,
        quota_explicit=None,
    )


def _insert_owned(repo, run_id, laboratory_id, metadata, result, *, created_at):
    with connection(repo.path) as db:
        db.execute(
            "INSERT INTO reference_lab_runs "
            "(id,lab_id,contract_version,created_at,metadata_json,result_json,"
            "owner_laboratory_id) VALUES (?,?,1,?,?,?,?)",
            (run_id, laboratory_id, created_at, metadata, result, laboratory_id),
        )
        db.execute(
            "INSERT INTO reference_lab_sessions VALUES (?,?,?)",
            (run_id, 0, '{"owned":true}'),
        )
        db.commit()


def test_legacy_run_methods_exclude_owned_rows_and_preserve_legacy_uuid_collision(repo):
    definition = initial_laboratory_definitions()[0]
    legacy_collision = _create_legacy(repo, definition.id, definition.id)
    legacy_alias = _create_legacy(repo, str(uuid.UUID(int=500)), "legacy-alias")
    own_ids = [str(uuid.UUID(int=value)) for value in (501, 502, 503)]
    owned_metadata = json.dumps(
        OwnedLaboratoryRunSnapshot(definition, "a" * 64, "b" * 64).to_mapping()
    )
    config, provenance, result = _legacy_record(definition.id)
    legacy_metadata = json.dumps({"schema_version": 1, "config": config, "provenance": provenance})
    legacy_result = json.dumps({"schema_version": 1, "result": result})
    _insert_owned(
        repo,
        own_ids[0],
        definition.id,
        owned_metadata,
        "{",
        created_at="2025-01-01T00:00:00.000000Z",
    )
    _insert_owned(
        repo,
        own_ids[1],
        definition.id,
        legacy_metadata,
        legacy_result,
        created_at="2025-01-03T00:00:00.000000Z",
    )
    _insert_owned(
        repo,
        own_ids[2],
        definition.id,
        "not-json",
        "not-json",
        created_at="2025-01-02T00:00:00.000000Z",
    )
    with connection(repo.path) as db:
        db.execute(
            "UPDATE reference_lab_runs SET created_at='2025-01-01T00:00:00.000000Z' WHERE id=?",
            (legacy_collision,),
        )
        db.execute(
            "UPDATE reference_lab_runs SET created_at='2025-01-02T00:00:00.000000Z' WHERE id=?",
            (legacy_alias,),
        )
        db.commit()

    assert repo.get_reference_lab_run(own_ids[0]) is None
    assert repo.list_reference_lab_sessions(own_ids[0]) is None
    assert repo.delete_reference_lab_run(own_ids[0]) is False
    for run_id in own_ids:
        assert repo.get_reference_lab_run(run_id) is None
        assert repo.list_reference_lab_sessions(run_id) is None
        assert repo.delete_reference_lab_run(run_id) is False

    all_runs = repo.list_reference_lab_runs(limit=1)
    assert all_runs["total"] == 2
    assert [item["id"] for item in all_runs["items"]] == [legacy_alias]
    second_page = repo.list_reference_lab_runs(offset=1, limit=1)
    assert second_page["total"] == 2
    assert [item["id"] for item in second_page["items"]] == [legacy_collision]
    filtered = repo.list_reference_lab_runs(lab_id=definition.id)
    assert filtered["total"] == 1
    assert [item["id"] for item in filtered["items"]] == [legacy_collision]

    assert repo.get_reference_lab_run(legacy_collision)["id"] == definition.id
    assert repo.list_reference_lab_sessions(legacy_collision)["total"] == 1
    assert repo.delete_reference_lab_run(legacy_collision) is True
    with connection(repo.path) as db:
        assert db.execute(
            "SELECT owner_laboratory_id FROM reference_lab_runs WHERE id=?", (own_ids[0],)
        ).fetchone() == (definition.id,)
        assert db.execute(
            "SELECT count(*) FROM reference_lab_sessions WHERE run_id=?", (own_ids[0],)
        ).fetchone() == (1,)
        assert db.execute(
            "SELECT count(*) FROM laboratory_definitions WHERE id=?", (definition.id,)
        ).fetchone() == (1,)
    assert repo.get_reference_lab_run(legacy_alias)["id"] == legacy_alias
    assert repo.delete_reference_lab_run(legacy_alias) is True


def test_legacy_list_filters_owned_corrupt_json_before_projection(repo):
    definition = initial_laboratory_definitions()[0]
    legacy_id = _create_legacy(repo, str(uuid.UUID(int=600)), definition.id)
    owned_id = str(uuid.UUID(int=601))
    _insert_owned(
        repo,
        owned_id,
        definition.id,
        "{",
        "{",
        created_at="2025-02-01T00:00:00.000000Z",
    )

    listed = repo.list_reference_lab_runs(lab_id=definition.id)

    assert listed["total"] == 1
    assert [item["id"] for item in listed["items"]] == [legacy_id]
