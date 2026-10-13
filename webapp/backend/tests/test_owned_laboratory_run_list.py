import hashlib
import json

import pytest

from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage import owned_laboratory_run_store
from laboratorio.storage.database import connection
from laboratorio.storage.owned_laboratory_run_store import (
    OwnedLaboratoryRunStoreError,
    list_runs,
)

_CREATED_AT = "2025-01-02T03:04:05.000000Z"


def _run_id(number):
    return f"00000000-0000-4000-8000-{number:012d}"


def _result(definition):
    values = ["goal", 0, 0, 1, definition.config.capital + 10, 1, 11]
    session = dict(
        zip(
            ("outcome", "start_index", "end_index", "draws", "final_balance", "wagered", "paid"),
            values,
            strict=True,
        )
    )
    return {
        "lab_id": definition.id,
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
        "session_sha256": hashlib.sha256(
            json.dumps([values], separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _summary(run):
    return {
        **{
            key: run[key]
            for key in ("id", "owner_laboratory_id", "lab_id", "contract_version", "created_at")
        },
        "summary": {key: run["result"][key] for key in ("totals", "eligible_draws", "gaps")},
    }


@pytest.fixture
def owned_page(repo):
    config = initial_laboratory_definitions()[0].config
    definitions = [
        repo.create_laboratory_definition(name, config, quota_bytes=10**9, quota_explicit=True)
        for name in ("List owner", "Other list owner")
    ]
    owner, other = definitions
    snapshot = OwnedLaboratoryRunSnapshot(owner, "a" * 64, "b" * 64)
    for number in (1, 2, 3):
        repo.create_owned_laboratory_run(
            _run_id(number),
            owner.id,
            snapshot,
            _result(owner),
            quota_bytes=10**9,
            quota_explicit=True,
        )
    repo.create_owned_laboratory_run(
        _run_id(4),
        other.id,
        OwnedLaboratoryRunSnapshot(other, "a" * 64, "b" * 64),
        _result(other),
        quota_bytes=10**9,
        quota_explicit=True,
    )
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET created_at=?", (_CREATED_AT,))
        db.execute("UPDATE reference_lab_runs SET result_json='broken' WHERE id=?", (_run_id(4),))
        db.execute(
            "INSERT INTO reference_lab_runs "
            "(id,lab_id,contract_version,created_at,metadata_json,result_json,owner_laboratory_id) "
            "SELECT ?,lab_id,contract_version,created_at,metadata_json,'broken',NULL "
            "FROM reference_lab_runs WHERE id=?",
            (_run_id(9), _run_id(1)),
        )
        db.commit()
    runs = [repo.get_owned_laboratory_run(owner.id, _run_id(n)) for n in (3, 2, 1)]
    return owner, runs


def test_owned_listing_is_ordered_paginated_and_explicitly_owner_scoped(repo, owned_page, capsys):
    owner, runs = owned_page
    counts = repo.get_laboratory_owned_counts(owner.id)
    expected = [_summary(run) for run in runs]
    assert repo.list_owned_laboratory_runs(owner.id) == {
        "total": 3,
        "offset": 0,
        "limit": 20,
        "items": expected,
    }
    assert list_runs(repo, owner.id, offset=1, limit=1) == {
        "total": 3,
        "offset": 1,
        "limit": 1,
        "items": [expected[1]],
    }
    assert repo.list_owned_laboratory_runs(owner.id, offset=2**63 - 1, limit=100) == {
        "total": 3,
        "offset": 2**63 - 1,
        "limit": 100,
        "items": [],
    }
    assert repo.list_owned_laboratory_runs(_run_id(8), offset=7, limit=10) == {
        "total": 0,
        "offset": 7,
        "limit": 10,
        "items": [],
    }
    page = repo.list_owned_laboratory_runs(owner.id)
    page["items"][0]["summary"]["totals"]["total_net"] = -99
    assert repo.get_owned_laboratory_run(owner.id, runs[0]["id"]) == runs[0]
    assert repo.get_laboratory_owned_counts(owner.id) == counts
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("owner_override", "paging"),
    [
        ("", {}),
        (False, {}),
        (42, {}),
        ("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", {}),
        (None, {"offset": True}),
        (None, {"offset": -1}),
        (None, {"offset": 0.0}),
        (None, {"offset": 2**63}),
        (None, {"limit": 0}),
        (None, {"limit": 101}),
        (None, {"limit": True}),
        (None, {"limit": "1"}),
    ],
)
def test_invalid_listing_inputs_do_not_change_records_or_counts(
    repo, owned_page, owner_override, paging, capsys
):
    owner, runs = owned_page
    counts = repo.get_laboratory_owned_counts(owner.id)
    identifier = owner.id if owner_override is None else owner_override
    with pytest.raises(OwnedLaboratoryRunStoreError):
        repo.list_owned_laboratory_runs(identifier, **paging)
    assert repo.get_laboratory_owned_counts(owner.id) == counts
    assert [repo.get_owned_laboratory_run(owner.id, run["id"]) for run in runs] == runs
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("column", ["metadata_json", "result_json"])
def test_listing_fails_closed_on_visible_corruption_but_ignores_off_page_rows(
    repo, owned_page, column, capsys
):
    owner, runs = owned_page
    counts = repo.get_laboratory_owned_counts(owner.id)
    with connection(repo.path) as db:
        db.execute(f"UPDATE reference_lab_runs SET {column}='broken' WHERE id=?", (_run_id(1),))
        db.commit()
    assert repo.list_owned_laboratory_runs(owner.id, limit=1) == {
        "total": 3,
        "offset": 0,
        "limit": 1,
        "items": [_summary(runs[0])],
    }
    with pytest.raises(OwnedLaboratoryRunStoreError, match="corrupt owned-laboratory run"):
        repo.list_owned_laboratory_runs(owner.id, offset=2, limit=1)
    assert repo.get_laboratory_owned_counts(owner.id) == counts
    assert repo.get_owned_laboratory_run(owner.id, runs[0]["id"]) == runs[0]
    assert capsys.readouterr() == ("", "")


def test_listing_uses_historical_snapshot_without_current_definition(repo, owned_page):
    owner, runs = owned_page
    with connection(repo.path) as db:
        db.execute(
            "UPDATE laboratory_definitions SET definition_json='broken' WHERE id=?", (owner.id,)
        )
        db.commit()
    assert repo.list_owned_laboratory_runs(owner.id) == {
        "total": 3,
        "offset": 0,
        "limit": 20,
        "items": [_summary(run) for run in runs],
    }
    assert repo.get_owned_laboratory_run(owner.id, runs[0]["id"]) == runs[0]


def test_listing_keeps_one_read_snapshot_during_interleaved_confirmed_delete(
    repo, owned_page, monkeypatch
):
    owner, runs = owned_page
    with connection(repo.path) as db:
        db.execute("PRAGMA journal_mode=WAL")
    original = owned_laboratory_run_store.get_run
    deleted = False

    def delete_between_page_selection_and_decode(db, owner_id, run_id):
        nonlocal deleted
        if not deleted:
            deleted = True
            repo.delete_laboratory_definition(owner.id, confirmed_run_count=3)
        return original(db, owner_id, run_id)

    monkeypatch.setattr(
        owned_laboratory_run_store, "get_run", delete_between_page_selection_and_decode
    )
    assert repo.list_owned_laboratory_runs(owner.id) == {
        "total": 3,
        "offset": 0,
        "limit": 20,
        "items": [_summary(run) for run in runs],
    }
    assert deleted
    assert repo.get_laboratory_definition(owner.id) is None
    assert all(repo.get_owned_laboratory_run(owner.id, run["id"]) is None for run in runs)
    assert repo.list_owned_laboratory_runs(owner.id) == {
        "total": 0,
        "offset": 0,
        "limit": 20,
        "items": [],
    }
