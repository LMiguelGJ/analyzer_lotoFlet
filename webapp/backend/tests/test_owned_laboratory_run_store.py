import hashlib
import json
import uuid

import pytest

from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.database import connection
from laboratorio.storage.owned_laboratory_run_store import (
    OwnedLaboratoryRunStoreError,
    get_run,
)

_HISTORY_SHA256 = "a" * 64
_RANKINGS_SHA256 = "b" * 64
_CREATED_AT = "2025-01-02T03:04:05.000000Z"
_UNSET = object()


def _snapshot(definition):
    return OwnedLaboratoryRunSnapshot(definition, _HISTORY_SHA256, _RANKINGS_SHA256).to_mapping()


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


def _insert_run(
    repo,
    definition,
    run_id,
    *,
    owner_id=_UNSET,
    lab_id=None,
    metadata=None,
    result=None,
    sessions=None,
    created_at=_CREATED_AT,
    contract_version=1,
):
    owner_id = definition.id if owner_id is _UNSET else owner_id
    lab_id = definition.id if lab_id is None else lab_id
    metadata = _snapshot(definition) if metadata is None else metadata
    result = _result(lab_id, definition.config.capital) if result is None else result
    if isinstance(result, dict):
        default_session = result["sessions"][0]
    else:
        default_session = _result(lab_id, definition.config.capital)["sessions"][0]
    if sessions is None:
        sessions = [(0, _canonical(default_session))]
    if not isinstance(metadata, str):
        metadata = _canonical(metadata)
    if not isinstance(result, str):
        result = _canonical({"schema_version": 1, "result": result})
    with connection(repo.path) as db:
        db.execute(
            "INSERT INTO reference_lab_runs "
            "(id,lab_id,contract_version,created_at,metadata_json,result_json,owner_laboratory_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (run_id, lab_id, contract_version, created_at, metadata, result, owner_id),
        )
        for ordinal, session_json in sessions:
            db.execute(
                "INSERT INTO reference_lab_sessions VALUES (?,?,?)",
                (run_id, ordinal, session_json),
            )
        db.commit()


def test_get_run_returns_owned_snapshot_and_validated_result(repo):
    definition = repo.create_laboratory_definition(
        "Owned reader",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    result = _result(definition.id, definition.config.capital)
    session_rows = [(0, _canonical(result["sessions"][0]))]
    _insert_run(repo, definition, run_id, result=result, sessions=session_rows)

    with connection(repo.path) as db:
        run = get_run(db, definition.id, run_id)

    assert run is not None
    assert set(run) == {
        "id",
        "owner_laboratory_id",
        "lab_id",
        "contract_version",
        "created_at",
        "snapshot",
        "result",
        "sessions",
    }
    assert run == {
        "id": run_id,
        "owner_laboratory_id": definition.id,
        "lab_id": definition.id,
        "contract_version": 1,
        "created_at": _CREATED_AT,
        "snapshot": _snapshot(definition),
        "result": result,
        "sessions": result["sessions"],
    }


def test_repository_owned_reader_delegates_and_returns_fresh_defensive_values(repo):
    definition = repo.create_laboratory_definition(
        "Owned delegation",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    _insert_run(
        repo,
        definition,
        run_id,
        sessions=[
            (0, _canonical(_result(definition.id, definition.config.capital)["sessions"][0]))
        ],
    )

    first = repo.get_owned_laboratory_run(definition.id, run_id)
    first["snapshot"]["definition"]["config"]["capital"] += 1
    first["result"]["sessions"][0]["wagered"] += 1
    second = repo.get_owned_laboratory_run(definition.id, run_id)

    assert second["snapshot"] == _snapshot(definition)
    assert second["result"] == _result(definition.id, definition.config.capital)


@pytest.mark.parametrize("owner_id", [str(uuid.uuid4()), None])
def test_get_run_hides_missing_wrong_owner_and_legacy_rows(repo, owner_id):
    definition = repo.create_laboratory_definition(
        "Owned visibility",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    if owner_id is not None:
        other = repo.create_laboratory_definition(
            "Other owner",
            initial_laboratory_definitions()[0].config,
            quota_bytes=10**9,
            quota_explicit=True,
        )
        owner_id = other.id
    # The schema requires owner_laboratory_id to equal lab_id for owned rows.
    _insert_run(
        repo,
        definition,
        run_id,
        owner_id=owner_id,
        lab_id=owner_id or definition.id,
        metadata="{",
        result="{",
    )

    with connection(repo.path) as db:
        assert get_run(db, definition.id, str(uuid.uuid4())) is None
        assert get_run(db, definition.id, run_id) is None


@pytest.mark.parametrize(
    "value",
    [None, "", "not-a-uuid", "00000000-0000-0000-0000-00000000000A", 1, True],
)
def test_get_run_rejects_noncanonical_or_nontext_identifiers(repo, value):
    error = "invalid owned-laboratory run identifiers"
    with connection(repo.path) as db:
        with pytest.raises(OwnedLaboratoryRunStoreError, match=error):
            get_run(db, value, str(uuid.uuid4()))
        with pytest.raises(OwnedLaboratoryRunStoreError, match=error):
            get_run(db, str(uuid.uuid4()), value)


@pytest.mark.parametrize(
    ("metadata", "result", "lab_id", "contract_version", "created_at"),
    [
        ("{", None, None, 1, _CREATED_AT),
        (
            '{"kind":"owned_laboratory_run","kind":"owned_laboratory_run"}',
            None,
            None,
            1,
            _CREATED_AT,
        ),
        ({"schema_version": 1, "kind": "reference_lab_run"}, None, None, 1, _CREATED_AT),
        (
            {"schema_version": 1, "kind": "owned_laboratory_run", "extra": 1},
            None,
            None,
            1,
            _CREATED_AT,
        ),
        (
            {
                "schema_version": 1,
                "kind": "owned_laboratory_run",
                "definition": {},
                "provenance": {},
            },
            None,
            None,
            1,
            _CREATED_AT,
        ),
        (None, "{", None, 1, _CREATED_AT),
        (None, '{"schema_version":1,"result":{},"result":{}}', None, 1, _CREATED_AT),
        (None, '{"schema_version":true,"result":{}}', None, 1, _CREATED_AT),
        (None, '{"schema_version":2,"result":{}}', None, 1, _CREATED_AT),
        (None, '{"schema_version":1,"result":{},"extra":1}', None, 1, _CREATED_AT),
        (None, '{"schema_version":1,"result":[]}', None, 1, _CREATED_AT),
        (None, None, None, 1, "2025-01-02 03:04:05"),
    ],
    ids=[
        "bad-snapshot-json",
        "duplicate-snapshot-key",
        "wrong-snapshot-kind",
        "extra-owned-root-key",
        "malformed-owned-snapshot",
        "bad-result-json",
        "duplicate-result-key",
        "boolean-envelope-version",
        "unsupported-envelope-version",
        "extra-envelope-key",
        "non-dict-result",
        "bad-timestamp",
    ],
)
def test_get_run_converts_corrupt_matched_rows_to_store_error(
    repo, metadata, result, lab_id, contract_version, created_at
):
    definition = repo.create_laboratory_definition(
        "Corrupt owned row",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    _insert_run(
        repo,
        definition,
        run_id,
        metadata=metadata,
        result=result,
        lab_id=lab_id,
        contract_version=contract_version,
        created_at=created_at,
    )

    with connection(repo.path) as db:
        with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
            get_run(db, definition.id, run_id)


@pytest.mark.parametrize(
    "build_rows",
    [
        lambda lab_id, capital: [],
        lambda lab_id, capital: [(1, _canonical(_result(lab_id, capital)["sessions"][0]))],
        lambda lab_id, capital: [
            (0, _canonical(_result(lab_id, capital)["sessions"][0])),
            (1, _canonical(_result(lab_id, capital)["sessions"][0])),
        ],
        lambda lab_id, capital: [
            (
                0,
                _canonical(
                    {
                        **_result(lab_id, capital)["sessions"][0],
                        "paid": 12,
                        "final_balance": capital + 11,
                    }
                ),
            )
        ],
    ],
    ids=["missing-row", "wrong-ordinal", "excess-row", "canonical-copy-disagreement"],
)
def test_get_run_rejects_session_row_count_and_copy_mismatches(repo, build_rows):
    definition = repo.create_laboratory_definition(
        "Session row validation",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    session_rows = build_rows(definition.id, definition.config.capital)
    _insert_run(repo, definition, run_id, sessions=session_rows)

    with connection(repo.path) as db:
        with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
            get_run(db, definition.id, run_id)


def test_get_run_returns_sessions_that_do_not_alias_the_result(repo):
    definition = repo.create_laboratory_definition(
        "Session aliasing",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    run_id = str(uuid.uuid4())
    _insert_run(repo, definition, run_id)

    with connection(repo.path) as db:
        run = get_run(db, definition.id, run_id)

    assert run is not None
    expected = _result(definition.id, definition.config.capital)["sessions"][0]["wagered"]
    run["sessions"][0]["wagered"] += 1
    assert run["result"]["sessions"][0]["wagered"] == expected


def test_get_run_validates_against_the_snapshot_capital(repo):
    definition = repo.create_laboratory_definition(
        "Snapshot capital",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    metadata = _snapshot(definition)
    metadata["definition"]["config"]["capital"] += 1
    # The altered snapshot must stay a valid owned snapshot, so only the capital disagrees.
    OwnedLaboratoryRunSnapshot.from_mapping(metadata)
    run_id = str(uuid.uuid4())
    _insert_run(repo, definition, run_id, metadata=metadata)

    with connection(repo.path) as db:
        with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
            get_run(db, definition.id, run_id)


def test_get_run_rejects_sessions_exceeding_persisted_eligible_draws(repo):
    definition = repo.create_laboratory_definition(
        "Eligible read bound",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    result = _result(definition.id, definition.config.capital)
    result["eligible_draws"] = 0
    run_id = str(uuid.uuid4())
    _insert_run(repo, definition, run_id, result=result)

    with connection(repo.path) as db:
        with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
            get_run(db, definition.id, run_id)


def test_get_run_rejects_snapshot_result_and_owner_identity_disagreement(repo):
    definition = repo.create_laboratory_definition(
        "Identity consistency",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    other = repo.create_laboratory_definition(
        "Different snapshot",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    cases = [
        (_snapshot(other), None),
        (None, _result(str(uuid.uuid4()), definition.config.capital)),
    ]
    for metadata, result in cases:
        run_id = str(uuid.uuid4())
        _insert_run(repo, definition, run_id, metadata=metadata, result=result)
        with connection(repo.path) as db:
            with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
                get_run(db, definition.id, run_id)
