"""Strict parser contracts for immutable v2 quiniela histories."""

import hashlib
import json

import pytest

from laboratorio.domain.quiniela_profiles import create_profile
from laboratorio.engine.quiniela_import import (
    HistoryImportError,
    preview_history,
    preview_included_history,
)


def rules(numbers=10, positions=2):
    return {
        "schema_version": 2,
        "universe": list(range(numbers)),
        "display_width": len(str(numbers - 1)),
        "positions": positions,
        "played_positions": list(range(positions)),
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [{"numerator": 1, "denominator": 1} for _ in range(positions)],
        "payout_mode": "all",
        "currency": "DOP",
        "scale": 0,
        "minimum_stake": 1,
        "stake_increment": 1,
        "maximum_stake": 100,
        "max_coverage": numbers,
        "max_exposure": 1_000,
    }


def profile():
    return create_profile("Import target", rules())


def canonical(draws, timezone="UTC"):
    return json.dumps(
        {"schema_version": 2, "timezone": timezone, "draws": draws},
        separators=(",", ":"),
    ).encode()


def draw(draw_id="a", timestamp="2026-01-01T12:00:00Z", results=(1, 2)):
    return {
        "schema_version": 2,
        "draw_id": draw_id,
        "timestamp": timestamp,
        "results": list(results),
    }


def test_preview_binds_exact_raw_and_canonical_hash_and_is_immutable():
    raw = canonical([draw("later", "2026-01-02T12:00:00Z"), draw()])
    preview = preview_history(raw, profile(), name="My source", origin="imported")
    assert preview.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert preview.draw_count == 2
    assert preview.draws[0].draw_id == "a"
    assert preview.to_mapping()["sample"][0] == draw()
    with pytest.raises((AttributeError, TypeError)):
        preview.__setattr__("draw_count", 4)


def test_identical_repeats_are_reported_and_deduplicated_but_conflicts_reject_all():
    repeated = canonical([draw(), draw()])
    preview = preview_history(repeated, profile(), name="Repeats", origin="imported")
    assert preview.draw_count == 1
    assert preview.duplicate_count == 1
    conflict = canonical([draw(), draw(results=(2, 1))])
    with pytest.raises(HistoryImportError, match="conflict"):
        preview_history(conflict, profile(), name="Conflict", origin="imported")


@pytest.mark.parametrize(
    "payload,confirmed,timezone",
    [
        (canonical([draw(timestamp="2026-01-01T12:00:00")]), False, "UTC"),
        (canonical([draw(timestamp="2026-01-01T12:00:00")]), True, "Invalid/Zone"),
        (canonical([draw(timestamp="2026-03-08T02:30:00")], "America/New_York"), True, None),
        (b'{"schema_version":2,"schema_version":2,"timezone":"UTC","draws":[]}', True, "UTC"),
        (canonical([draw(results=(1, True))]), True, "UTC"),
    ],
)
def test_invalid_time_zone_or_json_is_rejected(payload, confirmed, timezone):
    with pytest.raises((HistoryImportError, ValueError)):
        preview_history(
            payload,
            profile(),
            name="Invalid",
            origin="imported",
            timezone=timezone,
            timezone_confirmed=confirmed,
        )


def test_naive_time_requires_explicit_confirmation_and_dedicated_dst_resolution():
    naive = canonical([draw(timestamp="2026-01-01T12:00:00")])
    with pytest.raises(HistoryImportError, match="confirmation"):
        preview_history(naive, profile(), name="Naive", origin="imported", timezone="UTC")
    accepted = preview_history(
        naive,
        profile(),
        name="Naive",
        origin="imported",
        timezone="UTC",
        timezone_confirmed=True,
    )
    assert accepted.draws[0].timestamp == "2026-01-01T12:00:00Z"


@pytest.mark.parametrize(
    "schema_version,results,extra_key",
    [
        (True, [1, 2], None),
        (2, [1.0, 2], None),
        (2, [1, 2], "rankings_sha256"),
        (2, [1, float("nan")], None),
    ],
)
def test_noncanonical_schema_coercion_unknown_keys_and_nonfinite_values_reject(
    schema_version, results, extra_key
):
    row = draw(results=results) | {"schema_version": schema_version}
    if extra_key is not None:
        row[extra_key] = "0" * 64
    raw = canonical([row])
    with pytest.raises(HistoryImportError):
        preview_history(raw, profile(), name="Invalid")


def test_ambiguous_local_dst_time_and_conflicting_declared_timezone_reject():
    ambiguous = canonical([draw(timestamp="2026-11-01T01:30:00")], "America/New_York")
    with pytest.raises(HistoryImportError, match="ambiguous"):
        preview_history(
            ambiguous,
            profile(),
            name="DST",
            timezone_confirmed=True,
        )
    conflict = canonical([draw()], "UTC")
    with pytest.raises(HistoryImportError, match="conflicts"):
        preview_history(conflict, profile(), name="Conflict", timezone="Etc/UTC")


def _included_raw(*, source_url=None, include_url=False, extra=None):
    entry = {"hora": "12:00", "numeros": ["07", "03", "09", "01", "00"]}
    if include_url:
        entry["source_url"] = source_url
    if extra:
        entry.update(extra)
    return json.dumps(
        {
            "metadata": {"zona_horaria": "America/Santo_Domingo"},
            "sorteos_por_fecha": {"2026-06-10": [entry]},
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_included_source_url_is_ignored_but_exact_raw_bytes_remain_bound():
    included_profile = create_profile("Included target", rules(numbers=100, positions=5))
    legacy_raw = _included_raw()
    url_raw = _included_raw(source_url="https://ignored.invalid/source", include_url=True)

    legacy = preview_included_history(legacy_raw, included_profile)
    with_url = preview_included_history(url_raw, included_profile)

    assert legacy.draws[0].draw_id == with_url.draws[0].draw_id == "2026-06-10 12:00"
    assert legacy.draws[0].timestamp == with_url.draws[0].timestamp == "2026-06-10T16:00:00Z"
    assert legacy.draws[0].results == with_url.draws[0].results == (7, 3, 9, 1, 0)
    assert legacy.raw_sha256 == hashlib.sha256(legacy_raw).hexdigest()
    assert with_url.raw_sha256 == hashlib.sha256(url_raw).hexdigest()
    assert legacy.raw_sha256 != with_url.raw_sha256
    assert legacy.canonical_sha256 == with_url.canonical_sha256


def test_included_adapter_rejects_unknown_keys_and_nonstring_source_url():
    included_profile = create_profile("Included target", rules(numbers=100, positions=5))
    with pytest.raises(HistoryImportError, match="schema"):
        preview_included_history(_included_raw(extra={"unexpected": "value"}), included_profile)
    with pytest.raises(HistoryImportError, match="source_url"):
        preview_included_history(_included_raw(source_url=7, include_url=True), included_profile)


def test_result_order_is_preserved_and_profile_incompatibility_rejects():
    raw = canonical([draw(results=(2, 1))])
    ordered = preview_history(raw, profile(), name="Ordered", origin="imported")
    assert ordered.draws[0].results == (2, 1)
    incompatible = create_profile("Incompatible", rules(positions=1))
    with pytest.raises(HistoryImportError, match="positions"):
        preview_history(raw, incompatible, name="Bad", origin="imported")
