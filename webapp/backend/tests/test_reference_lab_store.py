import hashlib
import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
import pytest

from laboratorio.storage.database import SCHEMA_VERSION, connection, initialize_database
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.reference_lab_store import ReferenceLabStoreError

_SESSION_KEYS = (
    "outcome",
    "start_index",
    "end_index",
    "draws",
    "final_balance",
    "wagered",
    "paid",
)
_INT_FIELDS = _SESSION_KEYS[1:]


def _digest(sessions):
    rows = [[session[key] for key in _SESSION_KEYS] for session in sessions]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _session(outcome, start, draws, wagered, paid, capital=2000):
    return {
        "outcome": outcome,
        "start_index": start,
        "end_index": start + draws - 1,
        "draws": draws,
        "final_balance": capital + paid - wagered,
        "wagered": wagered,
        "paid": paid,
    }


def _build(lab_id, sessions, capital=2000):
    closed = [s["final_balance"] - capital for s in sessions if s["outcome"] != "incomplete"]
    wagered = sum(s["wagered"] for s in sessions)
    paid = sum(s["paid"] for s in sessions)
    return {
        "config": {
            "lab_id": lab_id,
            "name": "Prueba ñ",
            "capital": capital,
            "window": {"start": "a", "end": "b"},
        },
        "provenance": {
            "history_sha256": "a" * 64,
            "history_origin": "frozen",
            "rankings_sha256": "b" * 64,
        },
        "result": {
            "lab_id": lab_id,
            "sessions": sessions,
            "totals": {
                "completed": len(closed),
                "incomplete": sum(s["outcome"] == "incomplete" for s in sessions),
                "goals": sum(s["outcome"] == "goal" for s in sessions),
                "ruins": sum(s["outcome"] == "ruin" for s in sessions),
                "sessions_total": len(sessions),
                "total_wagered": wagered,
                "total_paid": paid,
                "total_net": paid - wagered,
                "total_steps": sum(s["draws"] for s in sessions),
                "mean_net_closed": sum(closed) / len(closed) if closed else None,
            },
            "eligible_draws": sum(s["draws"] for s in sessions),
            "gaps": 0,
            "first": "á",
            "last": "ó",
            "session_sha256": _digest(sessions),
        },
    }


def _record(lab_id="lab-a", *, sessions=1):
    return _build(lab_id, [_session("goal", index, 1, 1, 0) for index in range(sessions)])


def _create(repo, run_id=None, **kwargs):
    record = _record(**kwargs)
    return repo.create_reference_lab_run(
        run_id or str(uuid.uuid4()),
        record["config"]["lab_id"],
        record["config"],
        record["provenance"],
        record["result"],
        quota_bytes=10**9,
        quota_explicit=None,
    )


def test_current_schema_fresh_and_v15_upgrade_preserve_old_saved_run_and_history(tmp_path):
    from laboratorio.storage.database import _run_migrations

    fresh = tmp_path / "fresh.db"
    initialize_database(fresh)
    with connection(fresh) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        for table in ("reference_lab_runs", "reference_lab_sessions"):
            assert db.execute("SELECT name FROM sqlite_master WHERE name=?", (table,)).fetchone()

    old = tmp_path / "v15.db"
    with sqlite3.connect(old) as db:
        _run_migrations(db, 0, list(range(1, 16)))
        db.execute("INSERT INTO saved_runs VALUES ('old','Old',1,'{}','{}','2025-01-01T00:00:00Z')")
        db.execute("INSERT INTO history_sources VALUES ('sha','created',1,1,'a','a',x'01')")
        db.execute("INSERT INTO history_active VALUES (1,'sha')")
    with connection(old) as db:
        db.execute("PRAGMA user_version=15")
    initialize_database(old)
    with connection(old) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT id FROM saved_runs").fetchall() == [("old",)]
        assert db.execute("SELECT sha256 FROM history_sources").fetchall() == [("sha",)]
        assert db.execute("SELECT sha256 FROM history_active").fetchall() == [("sha",)]


def test_reference_run_round_trip_filter_paging_stable_order_and_cascade(repo):
    ids = [str(uuid.UUID(int=value)) for value in (1, 2, 3)]
    for value, lab in zip(ids, ("lab-a", "lab-b", "lab-a"), strict=True):
        _create(repo, value, lab_id=lab, sessions=3)
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET created_at='2025-01-01T00:00:00.000000Z'")
        db.commit()
    listed = repo.list_reference_lab_runs(limit=2)
    assert listed["total"] == 3
    assert [item["id"] for item in listed["items"]] == sorted(ids, reverse=True)[:2]
    assert repo.list_reference_lab_runs(lab_id="lab-a")["total"] == 2
    run = repo.get_reference_lab_run(ids[0])
    assert run["result"]["totals"]["total_net"] == -3
    page = repo.list_reference_lab_sessions(ids[0], offset=1, limit=2)
    assert (page["total"], len(page["items"])) == (3, 2)
    assert repo.delete_reference_lab_run(ids[0]) is True
    with connection(repo.path) as db:
        count = db.execute(
            "SELECT count(*) FROM reference_lab_sessions WHERE run_id=?", (ids[0],)
        ).fetchone()[0]
        assert count == 0


def test_utf8_payload_is_counted_by_shared_run_quota_and_denials_are_atomic(repo):
    before = repo.admission_logical_bytes()
    _create(repo)
    measured = repo.admission_logical_bytes()
    with connection(repo.path) as db:
        stored = db.execute(
            "SELECT sum(length(CAST(id AS BLOB)) + length(CAST(lab_id AS BLOB)) + 8 + "
            "length(CAST(metadata_json AS BLOB)) + length(CAST(result_json AS BLOB)) + "
            "length(CAST(created_at AS BLOB))) "
            "FROM reference_lab_runs"
        ).fetchone()[0]
        stored += db.execute(
            "SELECT sum(length(CAST(run_id AS BLOB)) + 8 + "
            "length(CAST(session_json AS BLOB))) FROM reference_lab_sessions"
        ).fetchone()[0]
    assert measured - before == stored
    repo.set_quota_preference(measured)
    assert repo.get_quota_preference() == measured
    from laboratorio.storage.repository import QuotaBelowUsage

    with pytest.raises(QuotaBelowUsage):
        repo.set_quota_preference(measured - 1)
    record = _record("other")
    with pytest.raises(QuotaExceeded):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "other",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=1,
            quota_explicit=None,
        )
    with connection(repo.path) as db:
        assert db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0] == 1


def test_limits_paging_validation_and_corruption_fail_closed(repo):
    with pytest.raises(ValueError):
        repo.list_reference_lab_runs(limit=True)
    with pytest.raises(ValueError):
        repo.list_reference_lab_sessions("missing", offset=-1)
    run_id = _create(repo)
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET metadata_json='NaN' WHERE id=?", (run_id,))
        db.commit()
    with pytest.raises(ReferenceLabStoreError):
        repo.get_reference_lab_run(run_id)
    record = _record("x")
    with pytest.raises(ReferenceLabStoreError):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "x",
            {},
            {},
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )


def test_asdict_reference_result_with_tuple_sessions_round_trips(repo):
    record = _record()
    record["result"]["sessions"] = tuple(record["result"]["sessions"])
    run_id = repo.create_reference_lab_run(
        str(uuid.uuid4()),
        "lab-a",
        record["config"],
        record["provenance"],
        record["result"],
        quota_bytes=10**9,
        quota_explicit=None,
    )
    assert len(repo.get_reference_lab_run(run_id)["sessions"]) == 1


def test_empty_session_run_is_valid(repo):
    record = _record(sessions=0)
    run_id = repo.create_reference_lab_run(
        str(uuid.uuid4()),
        "lab-a",
        record["config"],
        record["provenance"],
        record["result"],
        quota_bytes=10**9,
        quota_explicit=None,
    )
    assert repo.get_reference_lab_run(run_id)["sessions"] == []


def test_shared_result_validator_keeps_reference_session_default(repo):
    from laboratorio.storage.reference_lab_store import MAX_SESSIONS, _validate_result

    record = _record(sessions=1)
    assert _validate_result(
        record["config"]["lab_id"], record["config"]["capital"], record["result"]
    )[0]
    assert MAX_SESSIONS == 50_000


def test_payload_and_session_caps_and_numeric_types(repo):
    from laboratorio.storage.reference_lab_store import MAX_PAYLOAD_BYTES, MAX_SESSIONS

    record = _record(sessions=MAX_SESSIONS + 1)
    with pytest.raises(ReferenceLabStoreError):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "lab-a",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )
    record = _record()
    record["config"]["large"] = "x" * MAX_PAYLOAD_BYTES
    with pytest.raises(ReferenceLabStoreError):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "lab-a",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )
    record = _record()
    record["result"]["totals"]["goals"] = True
    with pytest.raises(ReferenceLabStoreError):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "lab-a",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )
    record = _record()
    record["result"]["totals"]["mean_net_closed"] = float("inf")
    with pytest.raises(ReferenceLabStoreError):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "lab-a",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )


def test_wrong_stored_contract_version_and_bad_session_json_fail_closed(repo):
    run_id = _create(repo)
    with connection(repo.path) as db:
        db.execute(
            "UPDATE reference_lab_runs SET metadata_json=? WHERE id=?",
            ('{"schema_version":2}', run_id),
        )
        db.commit()
    with pytest.raises(ReferenceLabStoreError):
        repo.get_reference_lab_run(run_id)
    repo.delete_reference_lab_run(run_id)
    run_id = _create(repo)
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_sessions SET session_json='{' WHERE run_id=?", (run_id,))
        db.commit()
    with pytest.raises(ReferenceLabStoreError):
        repo.list_reference_lab_sessions(run_id)


def test_old_run_admission_includes_reference_artifacts(repo):
    _create(repo)
    with pytest.raises(QuotaExceeded):
        repo.create_run("old-admission", "Old", {}, {}, [], quota_bytes=1, quota_explicit=None)
    with connection(repo.path) as db:
        assert db.execute("SELECT count(*) FROM saved_runs").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0] == 1


def test_disk_margin_rejection_leaves_no_partial_reference_rows(repo, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "disk_usage", lambda _path: SimpleNamespace(free=1))
    record = _record()
    with pytest.raises(QuotaExceeded):
        repo.create_reference_lab_run(
            str(uuid.uuid4()),
            "lab-a",
            record["config"],
            record["provenance"],
            record["result"],
            quota_bytes=10**9,
            quota_explicit=None,
        )
    with connection(repo.path) as db:
        assert db.execute("SELECT count(*) FROM reference_lab_runs").fetchone()[0] == 0


def test_concurrent_admission_is_serialized_without_partial_rows(repo):
    from laboratorio.storage.reference_lab_store import _validate_input

    records = [_record("parallel"), _record("parallel")]
    identifiers = [str(uuid.uuid4()), str(uuid.uuid4())]
    payload, result, sessions = _validate_input(
        identifiers[0],
        "parallel",
        records[0]["config"],
        records[0]["provenance"],
        records[0]["result"],
    )
    projected = (
        len(identifiers[0].encode())
        + len("parallel")
        + 8
        + 27
        + len(payload.encode())
        + len(result.encode())
        + sum(len(identifiers[0].encode()) + 8 + len(item.encode()) for item in sessions)
    )
    base = repo.admission_logical_bytes()
    quota = ((base + projected + 1) * 20 + 18) // 19

    def create(index):
        record = records[index]
        try:
            repo.create_reference_lab_run(
                identifiers[index],
                "parallel",
                record["config"],
                record["provenance"],
                record["result"],
                quota_bytes=quota,
                quota_explicit=None,
            )
            return True
        except QuotaExceeded:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create, range(2)))
    assert sorted(outcomes) == [False, True]
    with connection(repo.path) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM reference_lab_runs WHERE lab_id='parallel'"
            ).fetchone()[0]
            == 1
        )


def _store(repo, record, run_id=None):
    return repo.create_reference_lab_run(
        run_id or str(uuid.uuid4()),
        record["config"]["lab_id"],
        record["config"],
        record["provenance"],
        record["result"],
        quota_bytes=10**9,
        quota_explicit=None,
    )


def _count(repo, table="reference_lab_runs"):
    with connection(repo.path) as db:
        return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _edit(repo, run_id, mutate):
    """Rewrite the stored copies; ``mutate(metadata, envelope, rows)`` edits them in place."""
    with connection(repo.path) as db:
        metadata_json, result_json = db.execute(
            "SELECT metadata_json,result_json FROM reference_lab_runs WHERE id=?", (run_id,)
        ).fetchone()
        metadata, envelope = json.loads(metadata_json), json.loads(result_json)
        rows = [
            json.loads(text)
            for (text,) in db.execute(
                "SELECT session_json FROM reference_lab_sessions WHERE run_id=? ORDER BY ordinal",
                (run_id,),
            )
        ]
        mutate(metadata, envelope, rows)
        db.execute(
            "UPDATE reference_lab_runs SET metadata_json=?,result_json=? WHERE id=?",
            (_dump(metadata), _dump(envelope), run_id),
        )
        for ordinal, row in enumerate(rows):
            db.execute(
                "UPDATE reference_lab_sessions SET session_json=? WHERE run_id=? AND ordinal=?",
                (_dump(row), run_id, ordinal),
            )
        db.commit()


def _assert_unreadable(repo, run_id):
    with pytest.raises(ReferenceLabStoreError):
        repo.get_reference_lab_run(run_id)
    with pytest.raises(ReferenceLabStoreError):
        repo.list_reference_lab_sessions(run_id)


def _engine_record(lab_id, labels, rows):
    from laboratorio.domain.reference_labs import get_reference_lab
    from laboratorio.engine.reference_labs import run_reference_lab

    count = len(labels)
    history = SimpleNamespace(labels=tuple(labels), nums=np.asarray(rows, dtype=np.uint8))
    rankings = SimpleNamespace(
        row_ids=np.arange(count, dtype=np.int64),
        family=lambda _system: np.tile(np.arange(100, dtype=np.uint8), (count, 1)),
    )
    lab = get_reference_lab(lab_id)
    result = run_reference_lab(lab, history, rankings)
    record = {
        "config": asdict(lab),
        "provenance": {
            "history_sha256": "a" * 64,
            "history_origin": "frozen",
            "rankings_sha256": "b" * 64,
        },
        "result": asdict(result),
    }
    return result, record


_MISS, _HIT = [1, 2, 3, 4, 5], [0, 1, 2, 3, 4]
_IN_WINDOW = [f"2025-09-03 {hour:02d}:00" for hour in range(5)]


@pytest.mark.parametrize(
    ("labels", "rows"),
    [
        (_IN_WINDOW, [_MISS, _MISS, _HIT, _MISS, _MISS]),
        (_IN_WINDOW[:3], [_MISS, _MISS, _MISS]),
        (["2024-01-01 00:00"], [_MISS]),
    ],
    ids=["goal-then-incomplete", "negative-net-only", "empty-run"],
)
def test_actual_engine_result_round_trips_with_its_own_digest(repo, labels, rows):
    result, record = _engine_record("transicion_1_audaz", labels, rows)
    assert record["result"]["session_sha256"] == result.session_sha256
    run_id = _store(repo, record)
    stored = repo.get_reference_lab_run(run_id)["result"]
    assert stored["session_sha256"] == result.session_sha256
    assert stored["totals"] == asdict(result.totals)
    assert stored["sessions"] == [asdict(session) for session in result.sessions]
    assert repo.list_reference_lab_sessions(run_id)["total"] == len(result.sessions)
    if labels == _IN_WINDOW[:3]:
        assert stored["totals"]["total_net"] < 0 and stored["totals"]["mean_net_closed"] is None
    if len(rows) == 5:
        assert [s["outcome"] for s in stored["sessions"]] == ["goal", "incomplete"]
    bad = _dump({**record["result"], "session_sha256": "d" * 64})
    record["result"] = json.loads(bad)
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)


def test_digest_mismatch_is_rejected_before_any_write_and_on_every_read(repo):
    record = _record(sessions=2)
    record["result"]["session_sha256"] = "c" * 64
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)
    assert _count(repo) == 0 and _count(repo, "reference_lab_sessions") == 0

    run_id = _store(repo, _record(sessions=2))

    def swap(_metadata, envelope, _rows):
        envelope["result"]["session_sha256"] = "e" * 64

    _edit(repo, run_id, swap)
    _assert_unreadable(repo, run_id)


def test_empty_session_digest_is_the_canonical_empty_list_digest(repo):
    record = _record(sessions=0)
    assert record["result"]["session_sha256"] == hashlib.sha256(b"[]").hexdigest()
    assert repo.get_reference_lab_run(_store(repo, record))["sessions"] == []
    record["result"]["session_sha256"] = "c" * 64
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)


def test_mixed_goal_ruin_incomplete_run_keeps_exact_float_mean(repo):
    sessions = [
        _session("goal", 0, 2, 10, 811),
        _session("ruin", 2, 5, 2000, 0),
        _session("incomplete", 7, 1, 5, 0),
    ]
    record = _build("lab-a", sessions)
    assert record["result"]["totals"]["mean_net_closed"] == -599.5
    stored = repo.get_reference_lab_run(_store(repo, record))
    assert stored["result"]["totals"]["mean_net_closed"] == -599.5
    assert stored["result"]["totals"]["total_net"] == 811 - 2015


@pytest.mark.parametrize("field", ["final_balance", "wagered", "paid"])
@pytest.mark.parametrize("delta", [1, -1])
def test_session_accounting_is_enforced_on_admission(repo, field, delta):
    record = _record()
    record["result"]["sessions"][0][field] += delta
    if field != "final_balance":
        record["result"]["totals"]["total_" + field] += delta
        record["result"]["totals"]["total_net"] = (
            record["result"]["totals"]["total_paid"] - record["result"]["totals"]["total_wagered"]
        )
    record["result"]["session_sha256"] = _digest(record["result"]["sessions"])
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)
    assert _count(repo) == 0


def test_coherent_tampering_in_both_copies_with_fresh_digest_fails_accounting(repo):
    run_id = _store(repo, _record(sessions=2))

    def tamper(_metadata, envelope, rows):
        for row in (envelope["result"]["sessions"][0], rows[0]):
            row["final_balance"] += 50
        envelope["result"]["session_sha256"] = _digest(envelope["result"]["sessions"])

    _edit(repo, run_id, tamper)
    _assert_unreadable(repo, run_id)


def test_stored_capital_tampering_or_bad_capital_is_rejected(repo):
    run_id = _store(repo, _record())
    _edit(repo, run_id, lambda metadata, _envelope, _rows: metadata["config"].update(capital=2001))
    _assert_unreadable(repo, run_id)
    for bad in (None, 0, -5, True, 2000.0, 2**63):
        record = _record()
        record["config"]["capital"] = bad
        with pytest.raises(ReferenceLabStoreError):
            _store(repo, record)
    record = _record()
    del record["config"]["capital"]
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)


@pytest.mark.parametrize("mean", [None, 0.0, -1.5, 1.0])
def test_mean_net_closed_must_match_completed_session_mean(repo, mean):
    record = _record(sessions=1)
    record["result"]["totals"]["mean_net_closed"] = mean
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)
    empty = _record(sessions=0)
    empty["result"]["totals"]["mean_net_closed"] = 0.0
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, empty)


def test_mean_tampering_with_fresh_digest_fails_on_read(repo):
    run_id = _store(repo, _record())
    _edit(
        repo,
        run_id,
        lambda _m, envelope, _r: envelope["result"]["totals"].update(mean_net_closed=-2.0),
    )
    _assert_unreadable(repo, run_id)


def _bad_values(value):
    values = [float(value), -1, 2**63, "1", None, [value]]
    if value in (0, 1):
        values.append(bool(value))
    return values


_ROW = _session("goal", 0, 1, 1, 0)
_ROW_CASES = [(f, bad) for f in _INT_FIELDS for bad in _bad_values(_ROW[f])]


@pytest.mark.parametrize(("field", "bad"), _ROW_CASES)
def test_corrupt_numeric_row_copy_fails_even_when_python_equal(repo, field, bad):
    run_id = _store(repo, _record())
    _edit(repo, run_id, lambda _m, _e, rows: rows[0].update({field: bad}))
    _assert_unreadable(repo, run_id)


@pytest.mark.parametrize(("field", "bad"), _ROW_CASES)
def test_numeric_session_substitutions_are_rejected_on_admission(repo, field, bad):
    record = _record()
    record["result"]["sessions"][0][field] = bad
    record["result"]["session_sha256"] = _digest(record["result"]["sessions"])
    with pytest.raises(ReferenceLabStoreError):
        _store(repo, record)
    assert _count(repo) == 0


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda row: row.update(extra=1),
        lambda row: row.pop("paid"),
        lambda row: row.update(outcome="won"),
        lambda row: row.update(outcome=1),
    ],
    ids=["extra-key", "missing-key", "unknown-outcome", "non-text-outcome"],
)
def test_unknown_row_schema_fails_closed(repo, corrupt):
    run_id = _store(repo, _record())
    _edit(repo, run_id, lambda _m, _e, rows: corrupt(rows[0]))
    _assert_unreadable(repo, run_id)


def test_non_object_row_json_fails_closed(repo):
    run_id = _store(repo, _record())
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_sessions SET session_json='[1]' WHERE run_id=?", (run_id,))
        db.commit()
    _assert_unreadable(repo, run_id)


def test_legitimate_zero_and_signed_net_fields_survive(repo):
    sessions = [_session("incomplete", 0, 1, 40, 0), _session("goal", 1, 1, 0, 0)]
    stored = repo.get_reference_lab_run(_store(repo, _build("lab-a", sessions)))
    assert stored["result"]["totals"]["total_net"] == -40
    assert stored["sessions"][1]["wagered"] == 0 and stored["sessions"][1]["paid"] == 0


@pytest.fixture
def heavy_repo(repo):
    """Three runs with 1000 sessions and ~4 MB of caller metadata each."""
    for index in range(3):
        record = _build("lab-heavy", [_session("goal", n, 1, 1, 0) for n in range(1000)])
        record["config"]["blob"] = "x" * 3_000_000
        record["provenance"]["notes"] = ["y" * 1_000_000]
        _store(repo, record, str(uuid.UUID(int=index + 1)))
    return repo


def test_listing_uses_thin_projection_without_decoding_or_fetching_full_records(
    heavy_repo, monkeypatch
):
    import tracemalloc

    from laboratorio.storage import database, reference_lab_store

    statements, decoded = [], []
    real_connection = database.connection

    def traced(path):
        context = real_connection(path)

        class Traced:
            def __enter__(self):
                db = context.__enter__()
                db.set_trace_callback(statements.append)
                return db

            def __exit__(self, *args):
                return context.__exit__(*args)

        return Traced()

    real_loads = reference_lab_store._loads
    monkeypatch.setattr(
        reference_lab_store, "_loads", lambda text: decoded.append(len(text)) or real_loads(text)
    )
    for name in ("_read_run", "_decode_run"):
        monkeypatch.setattr(
            reference_lab_store, name, lambda *_: pytest.fail("listing must not read full runs")
        )
    monkeypatch.setattr(database, "connection", traced)
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        listed = heavy_repo.list_reference_lab_runs(limit=100)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert listed["total"] == 3 and len(listed["items"]) == 3
    assert peak < 1_000_000
    assert max(decoded, default=0) < 4096
    assert not any("session_json" in s or "metadata_json" in s for s in statements)
    assert not any("SELECT id,lab_id,contract_version,created_at,metadata" in s for s in statements)
    assert len(json.dumps(listed)) < 3 * 1500
    item = listed["items"][0]
    assert set(item) == {"id", "lab_id", "contract_version", "created_at", "summary"}
    assert item["contract_version"] == 1 and item["lab_id"] == "lab-heavy"
    summary = item["summary"]
    assert set(summary) == {"eligible_draws", "gaps", "totals"}
    assert summary["eligible_draws"] == 1000 and summary["gaps"] == 0
    assert summary["totals"]["sessions_total"] == 1000
    assert summary["totals"]["total_net"] == -1000
    assert summary["totals"]["mean_net_closed"] == -1.0


def test_listing_keeps_filter_order_offset_and_limit_cap(repo):
    ids = [str(uuid.UUID(int=value)) for value in (1, 2, 3, 4)]
    for value, lab in zip(ids, ("lab-a", "lab-b", "lab-a", "lab-a"), strict=True):
        _store(repo, _record(lab), value)
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET created_at='2025-01-01T00:00:00.000000Z'")
        db.execute(
            "UPDATE reference_lab_runs SET created_at='2025-02-01T00:00:00.000000Z' WHERE id=?",
            (ids[0],),
        )
        db.commit()
    listed = repo.list_reference_lab_runs(lab_id="lab-a", offset=1, limit=1)
    assert listed["total"] == 3 and listed["offset"] == 1 and listed["limit"] == 1
    assert [item["id"] for item in listed["items"]] == [ids[3]]
    full = repo.list_reference_lab_runs(lab_id="lab-a")["items"]
    assert [item["id"] for item in full] == [ids[0], ids[3], ids[2]]
    assert repo.list_reference_lab_runs(lab_id="x' OR '1'='1")["total"] == 0
    with pytest.raises(ValueError):
        repo.list_reference_lab_runs(limit=101)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda env: env["result"]["totals"].update(completed=True),
        lambda env: env["result"]["totals"].update(pad="x" * 100_000),
        lambda env: env["result"]["totals"].update(total_net=5),
        lambda env: env["result"].update(totals=[1]),
        lambda env: env.update(result=None),
    ],
    ids=["bool-total", "oversized-totals", "inconsistent", "non-object-totals", "no-result"],
)
def test_listing_fails_closed_on_malformed_projection(repo, corrupt):
    run_id = _store(repo, _record())
    _edit(repo, run_id, lambda _m, envelope, _r: corrupt(envelope))
    with pytest.raises(ReferenceLabStoreError):
        repo.list_reference_lab_runs()
    with connection(repo.path) as db:
        db.execute("UPDATE reference_lab_runs SET result_json='{' WHERE id=?", (run_id,))
        db.commit()
    with pytest.raises(ReferenceLabStoreError):
        repo.list_reference_lab_runs()
