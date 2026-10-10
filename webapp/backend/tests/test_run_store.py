import json
import sqlite3

import pytest

from laboratorio.storage.database import connection
from laboratorio.storage.quota import QuotaExceeded


def _valid_run_data():
    config = {
        "name": "Demo",
        "rules": {"minimum_stake": 1, "positions": 1, "prizes": [3]},
        "strategy": {"coverage": 2},
        "conditions": {"capital": 10, "goal": 11},
        "window": {},
        "history": {},
    }
    summary = {
        "totals": {
            "sessions": 2,
            "goal": 2,
            "ruin": 0,
            "limit": 0,
            "incomplete": 0,
            "bets": 2,
            "wagered": 4,
            "paid": 6,
            "net": 2,
        },
        "detail": {
            "status": "complete",
            "total_sessions": 2,
            "stored_sessions": 2,
            "total_bets": 2,
            "stored_bets": 2,
        },
    }
    bet_data = json.dumps([["2025-01-01 00:00", [1, 2], [2], 3, 11]])
    sessions = [
        (1, "goal", 0, 0, "2025-01-01 00:00", "2025-01-01 00:00", 1, 1, 2, 3, 11, bet_data),
        (2, "goal", 1, 1, "2025-01-02 00:00", "2025-01-02 00:00", 1, 1, 2, 3, 11, bet_data),
    ]
    return config, summary, sessions


def _create_valid_run(repo, run_id="integrity"):
    config, summary, sessions = _valid_run_data()
    repo.create_run(
        run_id,
        "Demo",
        config,
        summary,
        sessions,
        quota_bytes=None,
        quota_explicit=None,
    )


def test_run_migration_fresh_and_v14_upgrade_preserves_legacy_runs(tmp_path):
    from laboratorio.storage.database import _run_migrations, initialize_database

    fresh = tmp_path / "fresh.db"
    initialize_database(fresh)
    with connection(fresh) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='saved_run_sessions'"
        ).fetchone()
        assert db.execute("SELECT name FROM sqlite_master WHERE name='saved_runs'").fetchone()

    old = tmp_path / "old.db"
    with sqlite3.connect(old) as db:
        _run_migrations(db, 0, list(range(1, 15)))
        db.execute(
            "INSERT INTO experiments (id,status,request_json,history_id,history_sha256,"
            "rankings_id,rankings_sha256,code_version) "
            "VALUES ('legacy','pending','{}','h','h','r','r','v')"
        )
        db.execute("INSERT INTO runs (experiment_id,ordinal,status) VALUES ('legacy',0,'pending')")
    with connection(old) as db:
        db.execute("PRAGMA user_version=14")
    initialize_database(old)
    with connection(old) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 15
        assert db.execute("SELECT experiment_id,ordinal,status FROM runs").fetchall() == [
            ("legacy", 0, "pending")
        ]
        assert db.execute("SELECT count(*) FROM saved_runs").fetchone()[0] == 0


def test_run_round_trip_paging_corruption_and_quota(repo):
    config = {
        "name": "Demo",
        "rules": {"minimum_stake": 1, "positions": 1, "prizes": [3]},
        "strategy": {"coverage": 2},
        "conditions": {"capital": 10, "goal": 11},
        "window": {},
        "history": {},
    }
    summary = {
        "totals": {
            "sessions": 1,
            "goal": 1,
            "ruin": 0,
            "limit": 0,
            "incomplete": 0,
            "bets": 1,
            "wagered": 2,
            "paid": 3,
            "net": 1,
        },
        "detail": {
            "status": "complete",
            "total_sessions": 1,
            "stored_sessions": 1,
            "total_bets": 1,
            "stored_bets": 1,
        },
    }
    bet_data = json.dumps([["2025-01-01 00:00", [1, 2], [2], 3, 11]], separators=(",", ":"))
    session = (
        1,
        "goal",
        0,
        0,
        "2025-01-01 00:00",
        "2025-01-01 00:00",
        1,
        1,
        2,
        3,
        11,
        bet_data,
    )
    before = repo.quota_status()
    assert before.run_artifact_bytes == 0
    legacy_bytes = repo.logical_experiment_bytes()
    created = repo.create_run(
        "r1", "Demo", config, summary, [session], quota_bytes=None, quota_explicit=None
    )
    assert repo.get_run("r1")["created_at"] == created
    assert repo.search_runs(0, 10)[0] == 1
    count, items = repo.page_run_sessions("r1", 0, 10, outcome="goal")
    assert count == 1 and items[0]["net"] == 1
    bets = repo.page_run_bets("r1", 1, 0, 10)
    assert bets["items"][0]["wagered"] == 2
    after = repo.quota_status()
    assert after.run_artifact_bytes > 0
    assert after.admission_logical_bytes > before.admission_logical_bytes
    assert repo.logical_experiment_bytes() == legacy_bytes
    with pytest.raises(QuotaExceeded):
        repo.create_run(
            "over-quota",
            "Demo",
            config,
            summary,
            [session],
            quota_bytes=1,
            quota_explicit=True,
        )
    with connection(repo.path) as db:
        db.execute("UPDATE saved_runs SET summary_json='{}' WHERE id='r1'")
        db.commit()
    with pytest.raises(ValueError, match="stored run is corrupt"):
        repo.get_run("r1")
    assert repo.delete_run("r1")
    with connection(repo.path) as db:
        assert db.execute("SELECT count(*) FROM saved_run_sessions").fetchone()[0] == 0


def test_run_bet_detail_can_be_unavailable(repo):
    config = {
        "name": "Partial",
        "rules": {"minimum_stake": 1, "positions": 1, "prizes": [1]},
        "strategy": {"coverage": 1},
        "conditions": {"capital": 10, "goal": 11},
        "window": {},
        "history": {},
    }
    summary = {
        "totals": {
            "sessions": 1,
            "goal": 0,
            "ruin": 0,
            "limit": 0,
            "incomplete": 1,
            "bets": 1,
            "wagered": 1,
            "paid": 1,
            "net": 0,
        },
        "detail": {
            "status": "partial",
            "total_sessions": 1,
            "stored_sessions": 1,
            "total_bets": 1,
            "stored_bets": 0,
        },
    }
    session = (1, "incomplete", 0, 0, "start", "end", 1, 1, 1, 1, 10, None)
    repo.create_run(
        "partial",
        "Partial",
        config,
        summary,
        [session],
        quota_bytes=None,
        quota_explicit=None,
    )
    page = repo.page_run_bets("partial", 1, 0, 10)
    assert page["detail_available"] is False
    assert page["items"] == []
    assert page["session"]["detail_available"] is False


@pytest.mark.parametrize(
    ("column", "value"),
    [("wagered", 999), ("paid", 999), ("final_balance", 999)],
)
def test_run_session_accounting_tampering_is_rejected(repo, column, value):
    _create_valid_run(repo)
    with connection(repo.path) as db:
        db.execute(
            f"UPDATE saved_run_sessions SET {column}=? WHERE run_id='integrity' AND ordinal=1",
            (value,),
        )
        db.commit()
    with pytest.raises(ValueError, match="stored run is corrupt"):
        repo.get_run("integrity")


@pytest.mark.parametrize(
    "payload",
    [
        '[["label",[1,1],[2],3,11]]',
        '[["label",[1,2],[100],3,11]]',
        '[["label",[1,2],[2],true,11]]',
        '[["label",[1,2],[2],3,12]]',
    ],
)
def test_requested_run_bet_payload_is_validated(repo, payload):
    _create_valid_run(repo)
    with connection(repo.path) as db:
        db.execute(
            "UPDATE saved_run_sessions SET bets_json=? WHERE run_id='integrity' AND ordinal=1",
            (payload,),
        )
        db.commit()
    with pytest.raises(ValueError, match="stored run is corrupt"):
        repo.page_run_bets("integrity", 1, 0, 10)


def test_run_summary_and_session_pages_do_not_decode_bet_payloads(repo, monkeypatch):
    import laboratorio.storage.run_store as run_store

    _create_valid_run(repo)
    with connection(repo.path) as db:
        db.execute(
            "UPDATE saved_run_sessions SET bets_json='not-json' "
            "WHERE run_id='integrity' AND ordinal=2"
        )
        db.commit()

    original_loads = run_store.json.loads
    decoded_poison = []

    def track_poison(value, *args, **kwargs):
        if value == "not-json":
            decoded_poison.append(value)
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(run_store.json, "loads", track_poison)
    assert repo.get_run("integrity") is not None
    assert repo.search_runs(0, 10)[0] == 1
    assert repo.page_run_sessions("integrity", 0, 10)[0] == 2
    assert decoded_poison == []
    good = repo.page_run_bets("integrity", 1, 0, 10)
    assert len(good["items"]) == 1
    with pytest.raises(ValueError, match="stored run is corrupt"):
        repo.page_run_bets("integrity", 2, 0, 10)
    assert decoded_poison == ["not-json"]


def test_truncated_run_summary_reconciles_only_stored_session_counts(repo):
    config, summary, sessions = _valid_run_data()
    summary["totals"].update(sessions=3, goal=3, bets=3, wagered=6, paid=9, net=3)
    summary["detail"].update(status="sessions_truncated", total_sessions=3, total_bets=3)
    repo.create_run(
        "truncated",
        "Demo",
        config,
        summary,
        sessions,
        quota_bytes=None,
        quota_explicit=None,
    )
    assert repo.get_run("truncated")["summary"]["detail"]["stored_sessions"] == 2
    assert repo.search_runs(0, 10)[0] == 1
    assert repo.page_run_sessions("truncated", 0, 10)[0] == 2


def test_concurrent_run_admission_is_atomic_at_quota(repo):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    config, summary, sessions = _valid_run_data()
    serialized_config = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    serialized_summary = json.dumps(
        summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    projected = (
        2
        + len("Demo")
        + 8
        + len(serialized_config.encode())
        + len(serialized_summary.encode())
        + 27
    )
    for row in sessions:
        projected += (
            2
            + 8
            + len(row[1].encode())
            + 8 * 8
            + len(row[4].encode())
            + len(row[5].encode())
            + len(row[11].encode())
        )
    quota = projected * 2
    barrier = Barrier(2)

    def create(run_id):
        barrier.wait()
        return repo.create_run(
            run_id,
            "Demo",
            config,
            summary,
            sessions,
            quota_bytes=quota,
            quota_explicit=None,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result() if not future.exception() else future.exception()
            for future in [pool.submit(create, "r1"), pool.submit(create, "r2")]
        ]
    assert sum(not isinstance(result, QuotaExceeded) for result in results) == 1
    assert sum(isinstance(result, QuotaExceeded) for result in results) == 1
    with connection(repo.path) as db:
        assert db.execute("SELECT count(*) FROM saved_runs").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM saved_run_sessions").fetchone()[0] == 2
