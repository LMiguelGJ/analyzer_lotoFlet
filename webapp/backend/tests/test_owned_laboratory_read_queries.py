import hashlib
import json

import pytest

from laboratorio.domain.laboratories import initial_laboratory_definitions
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage import owned_laboratory_run_store
from laboratorio.storage.owned_laboratory_run_store import OwnedLaboratoryRunStoreError

RUN_ID = "00000000-0000-4000-8000-000000000001"


def _valid_result(definition):
    session = {
        "outcome": "goal",
        "start_index": 0,
        "end_index": 0,
        "draws": 1,
        "final_balance": definition.config.capital + 10,
        "wagered": 1,
        "paid": 11,
    }
    values = [
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


@pytest.fixture
def saved_owned_run(repo):
    definition = repo.create_laboratory_definition(
        "Certified read",
        initial_laboratory_definitions()[0].config,
        quota_bytes=10**9,
        quota_explicit=True,
    )
    repo.create_owned_laboratory_run(
        RUN_ID,
        definition.id,
        OwnedLaboratoryRunSnapshot(definition, "a" * 64, "b" * 64),
        _valid_result(definition),
        quota_bytes=10**9,
        quota_explicit=True,
    )
    return definition


def test_cold_certificate_validates_all_rows_and_warm_reads_only_requested_page(
    repo, saved_owned_run, monkeypatch
):
    definition = saved_owned_run
    calls = []
    decode = owned_laboratory_run_store._decode_run

    def track_decode(row, session_rows):
        calls.append((row[0], len(session_rows)))
        return decode(row, session_rows)

    monkeypatch.setattr(owned_laboratory_run_store, "_decode_run", track_decode)
    cold = repo.list_owned_laboratory_run_summaries(definition.id, limit=1)
    warm = repo.list_owned_laboratory_run_summaries(definition.id, limit=1)
    detail = repo.get_owned_laboratory_run_summary(definition.id, RUN_ID)
    page = repo.list_owned_laboratory_run_sessions(definition.id, RUN_ID, offset=0, limit=1)

    assert cold == warm
    assert cold["total"] == 1
    assert set(cold["items"][0]["summary"]) == {"totals", "eligible_draws", "gaps"}
    assert detail["summary"]["session_count"] == 1
    assert detail["summary"]["wallet"] == {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": definition.config.capital,
        "final_wealth": definition.config.capital + 10,
    }
    assert repo._owned_laboratory_read_cache.info.payload_bytes > 32
    assert page == {
        "run_id": RUN_ID,
        "total": 1,
        "offset": 0,
        "limit": 1,
        "items": [{"ordinal": 0, "summary": _valid_result(definition)["sessions"][0]}],
    }
    assert calls == [(RUN_ID, 1)]


def test_wallet_derivation_runs_once_on_cold_certificate_and_not_when_warm(
    repo, saved_owned_run, monkeypatch
):
    definition = saved_owned_run
    calls = []
    derive = owned_laboratory_run_store.derive_wallet

    def track_wallet(*args):
        calls.append(len(args[0]))
        return derive(*args)

    monkeypatch.setattr(owned_laboratory_run_store, "derive_wallet", track_wallet)
    cold = repo.get_owned_laboratory_run_summary(definition.id, RUN_ID)
    assert calls == [1]
    warm = repo.get_owned_laboratory_run_summary(definition.id, RUN_ID)

    assert warm == cold
    assert calls == [1]


def test_cached_certificate_invalidates_after_out_of_page_owner_mutation(repo, saved_owned_run):
    definition = saved_owned_run
    repo.list_owned_laboratory_run_summaries(definition.id, limit=1)
    # A visible owner's row outside the selected page must invalidate the epoch.
    from laboratorio.storage.database import connection

    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET metadata_json='broken' WHERE id=?", (RUN_ID,))
        db.commit()
    with pytest.raises(OwnedLaboratoryRunStoreError):
        repo.list_owned_laboratory_run_summaries(definition.id, limit=1)
