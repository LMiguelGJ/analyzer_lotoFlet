"""Bounded native backtest snapshots. No source access or replay on reads.

Capture a prefix of whole sessions; ordinals are zero-based original positions.
The digest detects accidental stored-payload changes (not a trust signature).
Money remains the engine's integer RD$ units, never profile cents.
"""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from laboratorio.domain.backtest import BacktestConfig, _ladder, _stake
from laboratorio.domain.contracts import StakingStyle

MAX_TRACE_BYTES = 2 * 1024 * 1024
MAX_TRACE_BETS = 10_000
MAX_TRACE_SESSIONS = 1_000
MAX_LABEL_LENGTH = 256
VERSION = 1
_ENCODER = json.JSONEncoder(
    sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
)


def _size(value, ceiling):
    size = 0
    for chunk in _ENCODER.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > ceiling:
            return size
    return size


def _digest(core, config, aggregate):
    digest = hashlib.sha256()
    for value in (core, config, aggregate):
        for chunk in _ENCODER.iterencode(value):
            digest.update(chunk.encode("utf-8"))
    return digest.hexdigest()


def _identity(row, index):
    return {"label": row.label, "minute": row.minute, "source_index": index}


def _source_lookup(result, rows):
    """Bound the index to labels eligible for capture; ambiguous labels get no ID."""
    eligible = {}
    bets = 0
    for ordinal, session in enumerate(result.sessions):
        if ordinal >= MAX_TRACE_SESSIONS or bets + len(session.bets) > MAX_TRACE_BETS:
            break
        for bet in session.bets:
            if len(bet.label) <= MAX_LABEL_LENGTH:
                eligible[bet.label] = []
        bets += len(session.bets)
    for index, row in enumerate(rows):
        if row.label in eligible:
            matches = eligible[row.label]
            # At most two entries: enough to mark an ambiguous identity.
            if len(matches) < 2:
                matches.append((index, row))
    return eligible


def build_trace(result, config, aggregate, rows=None):
    """Use only the just-executed immutable ledger and optional original rows.

    Rows are already resident in the producer. Index only capture-eligible labels,
    never infer an identity from ambiguous labels. A rejected session leaves no
    partial bets stored.
    """
    source_window = None
    if rows:
        source_window = {
            "count": len(rows),
            "first": _identity(rows[0], 0),
            "last": _identity(rows[-1], len(rows) - 1),
        }
    core = {
        "version": VERSION,
        "status": "empty" if not result.sessions else "complete",
        "reason": None,
        "unit": "native-RD$-integer",
        "total_sessions": len(result.sessions),
        "stored_sessions": 0,
        "total_bets": result.window.bets,
        "stored_bets": 0,
        "source_window": source_window,
        "limits": {
            "bytes": MAX_TRACE_BYTES,
            "bets": MAX_TRACE_BETS,
            "sessions": MAX_TRACE_SESSIONS,
        },
        "sessions": [],
    }
    # Reserve ample space for status, counts and digest; charge commas explicitly.
    remaining = MAX_TRACE_BYTES - _size(core, MAX_TRACE_BYTES) - 256
    lookup = _source_lookup(result, rows) if rows is not None else {}
    for ordinal, session in enumerate(result.sessions):
        if ordinal >= MAX_TRACE_SESSIONS or len(session.bets) > (
            MAX_TRACE_BETS - core["stored_bets"]
        ):
            break
        item = {
            "ordinal": ordinal,
            "outcome": session.outcome,
            "final_balance": session.final_balance,
            "bets": [],
        }
        used = _size(item, remaining) + 1
        fits = used <= remaining
        for bet_index, bet in enumerate(session.bets):
            if not fits or len(bet.label) > MAX_LABEL_LENGTH:
                fits = False
                break
            identity = {"source_index": None, "minute": None}
            if rows is not None:
                matches = lookup.get(bet.label, [])
                if not matches:
                    raise ValueError("native bet has no original source identity")
                if len(matches) == 1:
                    source_index, row = matches[0]
                    if (
                        tuple(row.results) != bet.results
                        or row.order is None
                        or (tuple(row.order[: config["strategy"]["coverage"]]) != bet.numbers)
                    ):
                        raise ValueError("native bet differs from original row")
                    identity = {"source_index": source_index, "minute": row.minute}
            recorded = {
                "bet_index": bet_index,
                "label": bet.label,
                **identity,
                "numbers": list(bet.numbers),
                "per_number": bet.per_number,
                "wagered": bet.wagered,
                "results": list(bet.results),
                "paid": bet.paid,
                "balance": bet.balance,
            }
            used += _size(recorded, remaining - used) + 1
            if used > remaining:
                fits = False
                break
            item["bets"].append(recorded)
        if not fits:
            break
        core["sessions"].append(item)
        core["stored_sessions"] += 1
        core["stored_bets"] += len(session.bets)
        remaining -= used
    if core["stored_sessions"] < core["total_sessions"]:
        core.update(status="truncated", reason="limit_exceeded")
    saved = {**core, "sha256": _digest(core, config, aggregate)}
    validate_trace(saved, config, aggregate)
    return saved


def _require(condition, message):
    if not condition:
        raise ValueError(f"invalid backtest trace: {message}")


def _keys(value, keys):
    _require(type(value) is dict and value.keys() == set(keys.split()), "keys")


def _integer(value, minimum=0):
    _require(type(value) is int and value >= minimum, "native integer")


def _label(value):
    _require(type(value) is str and 0 < len(value) <= MAX_LABEL_LENGTH, "label")


def _check_identity(value):
    _keys(value, "label minute source_index")
    _label(value["label"])
    _integer(value["source_index"])
    _require(type(value["minute"]) is int, "minute")


def validate_trace(saved, config, aggregate):
    """Fail closed before exposing even metadata. Absence is handled by caller."""
    _keys(
        saved,
        "version status reason unit total_sessions stored_sessions total_bets "
        "stored_bets source_window limits sessions sha256",
    )
    _require(type(saved["version"]) is int and saved["version"] == VERSION, "version")
    _require(saved["unit"] == "native-RD$-integer", "unit")
    limits = saved["limits"]
    _keys(limits, "bytes bets sessions")
    for key in limits:
        _integer(limits[key])
    _require(
        0 < limits["bytes"] <= MAX_TRACE_BYTES
        and limits["bets"] <= MAX_TRACE_BETS
        and limits["sessions"] <= MAX_TRACE_SESSIONS,
        "limits",
    )
    _require(_size(saved, limits["bytes"]) <= limits["bytes"], "byte cap")
    for key in ("total_sessions", "stored_sessions", "total_bets", "stored_bets"):
        _integer(saved[key])
    _require(
        saved["total_sessions"] == aggregate["window"]["sessions"]
        and saved["total_bets"] == aggregate["window"]["bets"],
        "aggregate counts",
    )
    _require(type(saved["sessions"]) is list, "sessions")
    _require(
        saved["stored_sessions"]
        == len(saved["sessions"])
        <= min(limits["sessions"], saved["total_sessions"]),
        "session count",
    )
    _require(saved["stored_bets"] <= min(limits["bets"], saved["total_bets"]), "bet count")
    status = (
        "empty"
        if saved["total_sessions"] == 0
        else ("complete" if saved["stored_sessions"] == saved["total_sessions"] else "truncated")
    )
    _require(
        saved["status"] == status
        and saved["reason"] == ("limit_exceeded" if status == "truncated" else None),
        "availability",
    )
    window = saved["source_window"]
    if window is not None:
        _keys(window, "count first last")
        _integer(window["count"], 1)
        for edge in ("first", "last"):
            _check_identity(window[edge])
        _require(
            window["first"]["source_index"] == 0
            and window["last"]["source_index"] == window["count"] - 1,
            "window bounds",
        )
        _require(
            (window["count"] == 1 and window["first"] == window["last"])
            or (window["count"] > 1 and window["first"]["minute"] < window["last"]["minute"]),
            "window clock",
        )
    game, conditions, strategy = config["game"], config["conditions"], config["strategy"]
    native = BacktestConfig(
        conditions["capital"],
        conditions["goal"],
        game["numbers"],
        game["positions"],
        tuple(game["prizes"]),
        game["min_stake"],
        strategy["coverage"],
        StakingStyle(strategy["staking"]),
    )
    ladder = _ladder(native) if native.staking is StakingStyle.LADDER else ()
    counts = {"reached_goal": 0, "quiebre": 0, "incomplete": 0}
    bets = wagered = paid = net = 0
    previous_index = previous_minute = None
    for ordinal, session in enumerate(saved["sessions"]):
        _keys(session, "ordinal outcome final_balance bets")
        _integer(session["ordinal"])
        _require(session["ordinal"] == ordinal, "original ordinal")
        _require(type(session["outcome"]) is str and session["outcome"] in counts, "outcome")
        _integer(session["final_balance"])
        _require(type(session["bets"]) is list, "bets")
        balance = conditions["capital"]
        round_index = 0
        for index, bet in enumerate(session["bets"]):
            _keys(
                bet,
                "bet_index label source_index minute numbers per_number wagered "
                "results paid balance",
            )
            _integer(bet["bet_index"])
            _require(bet["bet_index"] == index, "bet ordinal")
            _label(bet["label"])
            if window is None or bet["source_index"] is None:
                _require(
                    bet["source_index"] is None and bet["minute"] is None,
                    "unavailable source identity",
                )
            else:
                _check_identity({key: bet[key] for key in ("label", "minute", "source_index")})
                source_index, minute = bet["source_index"], bet["minute"]
                _require(
                    0 <= source_index < window["count"]
                    and window["first"]["minute"] <= minute <= window["last"]["minute"],
                    "source bounds",
                )
                _require(
                    previous_index is None or source_index > previous_index, "source chronology"
                )
                _require(previous_minute is None or minute > previous_minute, "clock chronology")
                for edge in ("first", "last"):
                    if source_index == window[edge]["source_index"]:
                        _require(
                            bet["label"] == window[edge]["label"]
                            and minute == window[edge]["minute"],
                            "boundary identity",
                        )
                previous_index, previous_minute = source_index, minute
            for key, length in (("numbers", strategy["coverage"]), ("results", game["positions"])):
                values = bet[key]
                _require(type(values) is list and len(values) == length, "number count")
                for number in values:
                    _integer(number)
                    _require(number < game["numbers"], "number range")
            _require(len(set(bet["numbers"])) == len(bet["numbers"]), "distinct selection")
            for key in ("per_number", "wagered", "paid", "balance"):
                _integer(bet[key])
            _require(
                bet["per_number"] >= game["min_stake"]
                and bet["wagered"] == bet["per_number"] * strategy["coverage"]
                and bet["wagered"] <= balance < conditions["goal"],
                "native wager",
            )
            _require(
                bet["per_number"] == _stake(native, balance, round_index, ladder), "native staking"
            )
            payment = bet["per_number"] * sum(
                prize
                for number, prize in zip(bet["results"], game["prizes"], strict=True)
                if number in bet["numbers"]
            )
            balance += payment - bet["wagered"]
            _require(bet["paid"] == payment and bet["balance"] == balance, "native accounting")
            bets += 1
            wagered += bet["wagered"]
            paid += payment
            if native.staking is StakingStyle.LADDER:
                round_index = (
                    0 if bet["results"][0] in bet["numbers"] else ((round_index + 1) % len(ladder))
                )
        _require(session["final_balance"] == balance, "final balance")
        _require(
            (balance >= conditions["goal"]) == (session["outcome"] == "reached_goal"),
            "goal outcome",
        )
        if session["outcome"] != "reached_goal":
            next_stake = _stake(native, balance, round_index, ladder)
            can_continue = next_stake >= native.minimum_stake and (
                next_stake * native.coverage <= balance
            )
            _require(can_continue == (session["outcome"] == "incomplete"), "native close")
        if session["outcome"] == "incomplete":
            _require(ordinal == saved["total_sessions"] - 1, "censored tail")
        else:
            net += balance - conditions["capital"]
        counts[session["outcome"]] += 1
    _require(bets == saved["stored_bets"], "stored bet total")
    for key, value in (("bets", bets), ("wagered", wagered), ("paid", paid)):
        _require(value <= aggregate["window"][key], "prefix window totals")
        if status != "truncated":
            _require(value == aggregate["window"][key], "complete window totals")
    for key, aggregate_key in (
        ("reached_goal", "reached_goal"),
        ("quiebre", "quiebres"),
        ("incomplete", "incomplete"),
    ):
        _require(counts[key] <= aggregate[aggregate_key], "prefix outcomes")
        if status != "truncated":
            _require(counts[key] == aggregate[aggregate_key], "complete outcomes")
    if status != "truncated":
        completed = counts["reached_goal"] + counts["quiebre"]
        mean = (
            float(Decimal(str(net / completed)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            if completed
            else 0.0
        )
        _require(mean == aggregate["neto_medio"], "native mean")
    core = {key: value for key, value in saved.items() if key != "sha256"}
    _require(
        type(saved["sha256"]) is str and saved["sha256"] == _digest(core, config, aggregate),
        "payload digest",
    )


def trace_metadata(saved):
    if saved is None:
        return {"status": "not_stored", "reason": "legacy"}
    return {key: value for key, value in saved.items() if key not in ("sessions", "sha256")}


def _wire_money(value):
    # Preserve native integer precision through JavaScript JSON.parse as well.
    return value if value <= 2**53 - 1 else str(value)


def bet_projection(bet):
    return {
        **bet,
        **{key: _wire_money(bet[key]) for key in ("per_number", "wagered", "paid", "balance")},
    }


def session_summary(session):
    bets = session["bets"]

    def identity(bet):
        return {key: bet[key] for key in ("label", "source_index", "minute")}

    return {
        "ordinal": session["ordinal"],
        "outcome": session["outcome"],
        "final_balance": _wire_money(session["final_balance"]),
        "bets_count": len(bets),
        "first_bet": identity(bets[0]) if bets else None,
        "last_bet": identity(bets[-1]) if bets else None,
    }
