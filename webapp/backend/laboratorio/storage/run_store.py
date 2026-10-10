"""Persistence and fail-closed validation for run reports."""

import json

from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes


def _json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _valid_report(row):
    identifier, name, schema, config_json, summary_json, created_at = row
    try:
        config, summary = json.loads(config_json), json.loads(summary_json)
        if (
            type(identifier) is not str
            or not identifier
            or type(name) is not str
            or not name
            or type(schema) is not int
            or schema != 1
            or type(created_at) is not str
            or not created_at
            or type(config) is not dict
            or type(summary) is not dict
        ):
            raise ValueError
        if config.get("name") != name:
            raise ValueError
        if any(
            type(config.get(key)) is not dict
            for key in ("rules", "strategy", "conditions", "window", "history")
        ):
            raise ValueError
        conditions = config["conditions"]
        capital, goal = conditions.get("capital"), conditions.get("goal")
        coverage = config["strategy"].get("coverage")
        rules = config["rules"]
        stake = rules.get("minimum_stake")
        positions, prizes = rules.get("positions"), rules.get("prizes")
        max_draws = conditions.get("max_draws")
        if (
            type(capital) is not int
            or capital < coverage * stake
            or type(goal) is not int
            or goal <= capital
            or type(coverage) is not int
            or not 1 <= coverage <= 50
            or type(stake) is not int
            or stake < 1
            or type(positions) is not int
            or not 1 <= positions <= 5
            or type(prizes) is not list
            or len(prizes) != positions
            or any(type(prize) is not int or prize < 1 for prize in prizes)
            or (max_draws is not None and (type(max_draws) is not int or max_draws < 1))
        ):
            raise ValueError
        totals = summary["totals"]
        count_keys = ("sessions", "goal", "ruin", "limit", "incomplete", "bets", "wagered", "paid")
        if any(type(totals[key]) is not int or totals[key] < 0 for key in count_keys):
            raise ValueError
        outcomes = sum(totals[key] for key in ("goal", "ruin", "limit", "incomplete"))
        if totals["sessions"] != outcomes or totals["net"] != totals["paid"] - totals["wagered"]:
            raise ValueError
        net = totals["net"]
        if type(net) is not int or type(totals["paid"]) is not int:
            raise ValueError
        detail = summary["detail"]
        if type(detail) is not dict or detail.get("status") not in (
            "complete",
            "partial",
            "sessions_truncated",
        ):
            raise ValueError
        detail_keys = ("total_sessions", "stored_sessions", "total_bets", "stored_bets")
        if any(type(detail.get(key)) is not int or detail[key] < 0 for key in detail_keys):
            raise ValueError
        if detail["total_sessions"] != totals["sessions"] or detail["total_bets"] != totals["bets"]:
            raise ValueError
        if (
            detail["stored_sessions"] > detail["total_sessions"]
            or detail["stored_bets"] > detail["total_bets"]
        ):
            raise ValueError
        return {
            "id": identifier,
            "name": name,
            "created_at": created_at,
            "schema_version": schema,
            "config": config,
            "summary": summary,
        }
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise ValueError("stored run is corrupt") from exc


def _validate_with_sessions(db, row):
    report = _valid_report(row)
    detail = report["summary"]["detail"]
    totals = report["summary"]["totals"]
    config = report["config"]
    capital = config["conditions"]["capital"]
    goal = config["conditions"]["goal"]
    coverage = config["strategy"]["coverage"]
    cost = coverage * config["rules"]["minimum_stake"]
    max_draws = config["conditions"].get("max_draws")
    # Session validation is entirely SQL-side: report/listing paths do not select or
    # decode bets_json, including when an unrelated stored detail blob is corrupt.
    aggregate = db.execute(
        "SELECT count(*), min(ordinal), max(ordinal), coalesce(sum(bets),0), "
        "coalesce(sum(wagered),0), coalesce(sum(paid),0), "
        "coalesce(sum(outcome='goal'),0), coalesce(sum(outcome='ruin'),0), "
        "coalesce(sum(outcome='limit'),0), coalesce(sum(outcome='incomplete'),0), "
        "sum(CASE WHEN typeof(ordinal)!='integer' OR ordinal<1 "
        "OR typeof(outcome)!='text' OR outcome NOT IN ('goal','ruin','limit','incomplete') "
        "OR typeof(start_index)!='integer' OR start_index<0 "
        "OR typeof(end_index)!='integer' OR end_index<start_index "
        "OR typeof(draws)!='integer' OR draws<1 OR draws!=end_index-start_index+1 "
        "OR typeof(start_label)!='text' OR length(start_label)=0 "
        "OR typeof(end_label)!='text' OR length(end_label)=0 "
        "OR typeof(bets)!='integer' OR bets<0 "
        "OR typeof(wagered)!='integer' OR wagered<0 OR wagered!=bets*? "
        "OR typeof(paid)!='integer' OR paid<0 "
        "OR typeof(final_balance)!='integer' OR final_balance<0 "
        "OR final_balance!=?+paid-wagered "
        "OR (outcome='goal' AND final_balance<?) "
        "OR (outcome='ruin' AND final_balance>=?) "
        "OR (outcome='limit' AND (final_balance<? OR final_balance>=? OR ? IS NULL OR draws<?)) "
        "OR (outcome='incomplete' AND (final_balance>=? OR final_balance<? "
        "OR (? IS NOT NULL AND draws>=?))) THEN 1 ELSE 0 END) "
        "FROM saved_run_sessions WHERE run_id=?",
        (
            cost,
            capital,
            goal,
            cost,
            cost,
            goal,
            max_draws,
            max_draws,
            goal,
            cost,
            max_draws,
            max_draws,
            row[0],
        ),
    ).fetchone()
    (
        count,
        first,
        last,
        bets,
        wagered,
        paid,
        goal_count,
        ruin_count,
        limit_count,
        incomplete_count,
        invalid,
    ) = aggregate
    if (
        count != detail["stored_sessions"]
        or invalid
        or (count and (first != 1 or last != count))
        or bets < 0
        or wagered < 0
        or paid < 0
        or goal_count + ruin_count + limit_count + incomplete_count != count
    ):
        raise ValueError("stored run is corrupt")
    if detail["status"] != "sessions_truncated" and count != detail["total_sessions"]:
        raise ValueError("stored run is corrupt")
    if detail["status"] == "sessions_truncated" and count >= detail["total_sessions"]:
        raise ValueError("stored run is corrupt")
    stored_bets = db.execute(
        "SELECT coalesce(sum(CASE WHEN bets_json IS NOT NULL THEN bets ELSE 0 END),0) "
        "FROM saved_run_sessions WHERE run_id=?",
        (row[0],),
    ).fetchone()[0]
    if stored_bets != detail["stored_bets"] or (
        detail["status"] == "complete" and stored_bets != totals["bets"]
    ):
        raise ValueError("stored run is corrupt")
    if detail["status"] != "sessions_truncated":
        exact = (bets, wagered, paid, goal_count, ruin_count, limit_count, incomplete_count)
        expected = (
            totals["bets"],
            totals["wagered"],
            totals["paid"],
            totals["goal"],
            totals["ruin"],
            totals["limit"],
            totals["incomplete"],
        )
        if exact != expected:
            raise ValueError("stored run is corrupt")
    elif (
        bets > totals["bets"]
        or wagered > totals["wagered"]
        or paid > totals["paid"]
        or goal_count > totals["goal"]
        or ruin_count > totals["ruin"]
        or limit_count > totals["limit"]
        or incomplete_count > totals["incomplete"]
    ):
        raise ValueError("stored run is corrupt")
    return report


def _validate_bet_payload(raw, session, report):
    try:
        if raw is not None and type(raw) is not str:
            raise ValueError
        payload = json.loads(raw) if raw is not None else []
        coverage = report["config"]["strategy"]["coverage"]
        stake = report["config"]["rules"]["minimum_stake"]
        positions = report["config"]["rules"]["positions"]
        prizes = report["config"]["rules"]["prizes"]
        capital = report["config"]["conditions"]["capital"]
        if type(payload) is not list or len(payload) != session["bets"]:
            raise ValueError
        balance = capital
        paid_total = 0
        for bet in payload:
            if (
                type(bet) is not list
                or len(bet) != 5
                or type(bet[0]) is not str
                or not bet[0]
                or type(bet[1]) is not list
                or len(bet[1]) != coverage
                or any(type(number) is not int or not 0 <= number <= 99 for number in bet[1])
                or len(set(bet[1])) != coverage
                or type(bet[2]) is not list
                or len(bet[2]) != positions
                or any(type(number) is not int or not 0 <= number <= 99 for number in bet[2])
                or type(bet[3]) is not int
                or bet[3] < 0
                or type(bet[4]) is not int
                or bet[4] < 0
            ):
                raise ValueError
            selected = set(bet[1])
            expected_paid = sum(
                prizes[index] * stake for index, result in enumerate(bet[2]) if result in selected
            )
            balance += expected_paid - coverage * stake
            if bet[3] != expected_paid or bet[4] != balance:
                raise ValueError
            paid_total += expected_paid
        if (
            len(payload) != session["bets"]
            or len(payload) * coverage * stake != session["wagered"]
            or paid_total != session["paid"]
            or balance != session["final_balance"]
        ):
            raise ValueError
        return payload
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise ValueError("stored run is corrupt") from exc


def _quota(db, path, quota_bytes, quota_explicit, disk_usage):
    from dataclasses import fields

    from laboratorio.storage.repository import (
        RepositoryQuotaStatus,
        _dataset_artifact_bytes,
        _history_artifact_bytes,
        _logical_experiment_bytes,
        _profile_artifact_bytes,
        _run_artifact_bytes,
        _strategy_artifact_bytes,
    )

    validate_quota_bytes(quota_bytes)
    status = measure(
        path,
        quota_bytes,
        _logical_experiment_bytes(db),
        profile_artifact_bytes=_profile_artifact_bytes(db),
        dataset_artifact_bytes=_dataset_artifact_bytes(db),
        strategy_artifact_bytes=_strategy_artifact_bytes(db),
        disk_usage=disk_usage,
    )
    return RepositoryQuotaStatus(
        **{item.name: getattr(status, item.name) for item in fields(QuotaStatus)},
        history_artifact_bytes=_history_artifact_bytes(db),
        run_artifact_bytes=_run_artifact_bytes(db),
    )


def create_run(repo, run_id, name, config, summary, session_rows, *, quota_bytes, quota_explicit):
    from laboratorio.storage.repository import _now_iso, _transaction

    config_json, summary_json = _json(config), _json(summary)
    created_at = _now_iso()
    effective = repo.effective_quota(quota_bytes, quota_explicit=quota_explicit)
    projected = (
        len(run_id.encode())
        + len(name.encode())
        + 8
        + len(config_json.encode())
        + len(summary_json.encode())
        + len(created_at.encode())
    )
    for row in session_rows:
        projected += (
            len(run_id.encode())
            + 8
            + len(row[1].encode())
            + 8 * 8
            + len(row[4].encode())
            + len(row[5].encode())
            + (len(row[11].encode()) if row[11] is not None else 0)
        )
    with _transaction(repo.path) as db:
        _quota(
            db,
            repo.path,
            effective.effective_bytes,
            effective.source == "environment",
            __import__("shutil").disk_usage,
        ).require_capacity(projected)
        db.execute(
            "INSERT INTO saved_runs VALUES (?, ?, 1, ?, ?, ?)",
            (run_id, name, config_json, summary_json, created_at),
        )
        db.executemany(
            "INSERT INTO saved_run_sessions (run_id, ordinal, outcome, start_index, end_index, "
            "start_label, end_label, draws, bets, wagered, paid, final_balance, bets_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(run_id, *row) for row in session_rows],
        )
    return created_at


def get_run(repo, run_id):
    from laboratorio.storage.database import connection

    with connection(repo.path) as db:
        row = db.execute(
            "SELECT id,name,schema_version,config_json,summary_json,created_at "
            "FROM saved_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        return None if row is None else _validate_with_sessions(db, row)


def search_runs(repo, offset, limit):
    from laboratorio.storage.database import connection

    _paging(offset, limit)
    with connection(repo.path) as db:
        db.execute("BEGIN")
        total = db.execute("SELECT count(*) FROM saved_runs").fetchone()[0]
        rows = db.execute(
            "SELECT id,name,schema_version,config_json,summary_json,created_at "
            "FROM saved_runs ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return total, [_validate_with_sessions(db, row) for row in rows]


def _paging(offset, limit):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("offset and limit out of range")


def page_run_sessions(repo, run_id, offset, limit, outcome=None):
    from laboratorio.storage.database import connection

    _paging(offset, limit)
    if outcome is not None and outcome not in ("goal", "ruin", "limit", "incomplete"):
        raise ValueError("invalid outcome")
    with connection(repo.path) as db:
        head = db.execute(
            "SELECT id,name,schema_version,config_json,summary_json,created_at "
            "FROM saved_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if head is None:
            return None
        report = _validate_with_sessions(db, head)
        if outcome is None:
            total = db.execute(
                "SELECT count(*) FROM saved_run_sessions WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            saved = db.execute(
                "SELECT ordinal,outcome,start_index,end_index,start_label,end_label,draws,bets,"
                "wagered,paid,final_balance,bets_json IS NOT NULL FROM saved_run_sessions "
                "WHERE run_id=? "
                "ORDER BY ordinal LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
        else:
            total = db.execute(
                "SELECT count(*) FROM saved_run_sessions WHERE run_id=? AND outcome=?",
                (run_id, outcome),
            ).fetchone()[0]
            saved = db.execute(
                "SELECT ordinal,outcome,start_index,end_index,start_label,end_label,draws,bets,"
                "wagered,paid,final_balance,bets_json IS NOT NULL FROM saved_run_sessions "
                "WHERE run_id=? AND outcome=? ORDER BY ordinal LIMIT ? OFFSET ?",
                (run_id, outcome, limit, offset),
            ).fetchall()
        capital = report["config"]["conditions"]["capital"]
        items = [
            {
                "ordinal": r[0],
                "outcome": r[1],
                "start_index": r[2],
                "end_index": r[3],
                "start_label": r[4],
                "end_label": r[5],
                "draws": r[6],
                "bets": r[7],
                "wagered": r[8],
                "paid": r[9],
                "final_balance": r[10],
                "net": r[10] - capital,
                "detail_available": bool(r[11]),
            }
            for r in saved
        ]
        return total, items


def page_run_bets(repo, run_id, ordinal, offset, limit):
    from laboratorio.storage.database import connection

    _paging(offset, limit)
    if type(ordinal) is not int or ordinal < 1:
        raise ValueError("session ordinal out of range")
    with connection(repo.path) as db:
        head = db.execute(
            "SELECT id,name,schema_version,config_json,summary_json,created_at "
            "FROM saved_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if head is None:
            return None
        report = _validate_with_sessions(db, head)
        r = db.execute(
            "SELECT ordinal,outcome,start_index,end_index,start_label,end_label,draws,"
            "bets,wagered,paid,final_balance,bets_json FROM saved_run_sessions "
            "WHERE run_id=? AND ordinal=?",
            (run_id, ordinal),
        ).fetchone()
        if r is None:
            return None
        capital = report["config"]["conditions"]["capital"]
        session = {
            "ordinal": r[0],
            "outcome": r[1],
            "start_index": r[2],
            "end_index": r[3],
            "start_label": r[4],
            "end_label": r[5],
            "draws": r[6],
            "bets": r[7],
            "wagered": r[8],
            "paid": r[9],
            "final_balance": r[10],
            "net": r[10] - capital,
            "detail_available": r[11] is not None,
        }
        payload = _validate_bet_payload(r[11], session, report) if r[11] is not None else []
        coverage = report["config"]["strategy"]["coverage"]
        stake = report["config"]["rules"]["minimum_stake"]
        items = [
            {
                "index": i + 1,
                "label": bet[0],
                "numbers": bet[1],
                "results": bet[2],
                "wagered": coverage * stake,
                "paid": bet[3],
                "balance": bet[4],
            }
            for i, bet in enumerate(payload[offset : offset + limit], offset)
        ]
        return {
            "session": session,
            "total": r[7],
            "offset": offset,
            "limit": limit,
            "detail_available": r[11] is not None,
            "items": items,
        }


def delete_run(repo, run_id):
    from laboratorio.storage.repository import _transaction

    with _transaction(repo.path) as db:
        cursor = db.execute("DELETE FROM saved_runs WHERE id=?", (run_id,))
        return cursor.rowcount > 0
