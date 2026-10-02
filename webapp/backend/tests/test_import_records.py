"""Pure importer: bounded admission, deterministic identity and all-or-nothing preview."""

import builtins
import json
from dataclasses import FrozenInstanceError
from hashlib import sha256
from typing import cast

import pytest

from laboratorio.domain.contracts import GameProfile
from laboratorio.importing.records import (
    MAX_COLUMNS,
    MAX_ERRORS,
    MAX_INPUT_BYTES,
    MAX_ROWS,
    ClockDeclaration,
    ColumnMapping,
    SourceMetadata,
    parse_records,
)


def profile(positions=3, *, repeats=True, universe=100, revision=1):
    return GameProfile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "test-draw",
            "revision": revision,
            "universe_size": universe,
            "positions": positions,
            "allows_repeats": repeats,
            "multipliers": [{"numerator": 2, "denominator": 1}] * positions,
            "currency": "DOP",
            "scale": 0,
            "stake_increment": 1,
            "minimum_stake": 1,
            "maximum_stake": 10,
            "max_coverage": universe,
            "max_exposure": universe * 10,
            "best_rule": "maximum-payout/v1",
        }
    )


def options(positions=3, **changes):
    kwargs = {
        "format": "json",
        "mapping": ColumnMapping("day", "hour", tuple(f"p{i}" for i in range(positions))),
        "profile": profile(positions),
        "source": SourceMetadata("local-1", "historical", "v1", "manual upload"),
        "clock": ClockDeclaration("naive_legacy"),
    }
    kwargs.update(changes)
    return kwargs


def row(numbers=(0, 1, 2), day="2025-09-02", hour="05:10"):
    return {"day": day, "hour": hour, **{f"p{i}": value for i, value in enumerate(numbers)}}


def parse(rows, **kwargs):
    return parse_records(json.dumps(rows).encode(), **options(**kwargs))


def codes(result):
    return {error.code for error in result.errors}


@pytest.mark.parametrize("positions", [1, 3, 5])
@pytest.mark.parametrize("format", ["json", "csv"])
def test_valid_position_counts_and_zero_padded_values(positions, format):
    opts = options(positions, format=format)
    values = ["00", *range(1, positions)]
    raw = (
        json.dumps([row(values)]).encode()
        if format == "json"
        else (
            "day,hour,"
            + ",".join(opts["mapping"].positions)
            + "\n"
            + "2025-09-02,05:10,"
            + ",".join(map(str, values))
            + "\n"
        ).encode()
    )
    result = parse_records(raw, **opts)
    assert result.promotable and result.error_count == 0
    assert result.records[0].numbers == tuple(range(positions))
    assert result.source_sha256 == sha256(raw).hexdigest()
    assert result.dataset_sha256 is not None and len(result.dataset_sha256) == 64
    with pytest.raises(FrozenInstanceError):
        field = "date"
        setattr(result.records[0], field, "other")
    assert isinstance(result.records, tuple)


@pytest.mark.parametrize(
    "raw,format,expected",
    [
        (b"{}", "json", "shape"),
        (b"[[1,2]]", "json", "shape"),
        (b'{"day":"2025-09-02"}', "json", "shape"),
        (b'[{"day":"x","day":"y"}]', "json", "json"),
        (b"[NaN]", "json", "json"),
        (b"day,hour,p0,p1,p1\n2025-09-02,05:10,1,2,3\n", "csv", "header"),
        (b"day,hour,p0,p1,p2\n2025-09-02,05:10,1,2\n", "csv", "shape"),
        (b"day,hour,p0,p1,p2\n2025-09-02,05:10,1,2,3,4\n", "csv", "shape"),
        (b"\xff", "csv", "encoding"),
    ],
)
def test_malformed_shape_header_and_encoding(raw, format, expected):
    result = parse_records(raw, **options(format=format))
    assert expected in codes(result)
    assert not result.promotable and result.records == () and result.dataset_sha256 is None


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("day", "2025-02-29", "date"),
        ("day", "2025-2-09", "date"),
        ("day", "2025-13-01", "date"),
        ("hour", "24:00", "time"),
        ("hour", "5:10", "time"),
        ("hour", "05:60", "time"),
        ("p0", True, "number"),
        ("p0", 1.0, "number"),
        ("p0", -1, "number"),
        ("p0", 100, "number"),
        ("p0", "2.0", "number"),
        ("p0", "9" * 5000, "number"),
    ],
)
def test_invalid_row_fields(field, value, expected):
    result = parse([row(), dict(row(hour="05:11"), **{field: value})])
    assert codes(result) == {expected} and result.rows_seen == 2
    assert result.records == () and not result.promotable


def test_missing_fields_and_repeats_rejected_without_partial_promotion():
    missing = row()
    del missing["p1"]
    result = parse([row(), missing, row((1, 1, 2), hour="05:11")], profile=profile(repeats=False))
    assert codes(result) == {"missing_field", "repeats"}
    assert result.records == () and result.dataset_sha256 is None


def test_mapping_and_source_clock_validation():
    duplicate = ColumnMapping("day", "day", ("p0", "p1", "p2"))
    assert "mapping_duplicate" in codes(parse([row()], mapping=duplicate))
    assert "positions" in codes(parse([row()], mapping=ColumnMapping("day", "hour", ("p0",))))
    assert "clock" in codes(parse([row()], clock=ClockDeclaration("naive_legacy", "UTC")))
    invalid_zone = ClockDeclaration("iana", "Invalid/NoSuchZone")
    assert "clock_zone" in codes(parse([row()], clock=invalid_zone))
    missing_source = SourceMetadata("", "historical", "v1", "manual")
    assert "source" in codes(parse([row()], source=missing_source))
    assert "format" in codes(parse([row()], format="xml"))
    result = parse([row()], clock=ClockDeclaration("iana", "UTC"))
    # UTC is stdlib zoneinfo data on supported systems; unavailable installations
    # must disclose the limitation instead of accepting an unchecked zone.
    assert result.promotable or codes(result) == {"clock_zone"}


def test_conflicts_block_promotion_identical_duplicates_merge_and_sort():
    later = row((3, 4, 5), day="2025-09-03")
    first = row((0, 1, 2))
    result = parse([later, first, first])
    assert result.promotable and result.rows_seen == 3
    assert result.duplicates_merged == 1
    assert [record.date for record in result.records] == ["2025-09-02", "2025-09-03"]
    conflict = parse([first, row((3, 4, 5))])
    assert "conflict" in codes(conflict) and not conflict.promotable
    assert conflict.records == () and conflict.dataset_sha256 is None


def test_normalized_hash_order_provenance_mapping_profile_and_clock():
    first, second = row(), row((3, 4, 5), hour="05:11")
    a, b = parse([first, second]), parse([second, first])
    assert a.dataset_sha256 == b.dataset_sha256
    assert a.source_sha256 != b.source_sha256
    assert parse([first, first, second]).dataset_sha256 == a.dataset_sha256
    alternate_source = SourceMetadata("other", "historical", "v1", "manual upload")
    assert parse([first, second], source=alternate_source).dataset_sha256 != a.dataset_sha256
    assert parse([first, second], profile=profile(revision=2)).dataset_sha256 != a.dataset_sha256
    alternate_mapping = ColumnMapping("day", "hour", ("p1", "p0", "p2"))
    assert parse([first, second], mapping=alternate_mapping).dataset_sha256 != a.dataset_sha256
    zone = parse([first, second], clock=ClockDeclaration("iana", "UTC"))
    if zone.promotable:
        assert zone.dataset_sha256 != a.dataset_sha256


def test_input_limit_precedes_decode_and_import_column_ceiling():
    raw = b"\xff" * (MAX_INPUT_BYTES + 1)
    result = parse_records(raw, **options())
    assert codes(result) == {"input_limit"} and result.source_sha256 == sha256(raw).hexdigest()
    # A malformed oversized mapping is rejected before an invalid UTF-8 payload.
    oversized = ColumnMapping("day", "hour", tuple(f"p{i}" for i in range(31)))
    result = parse_records(b"\xff", **options(mapping=oversized))
    assert {"column_limit", "positions"} == codes(result)
    header = "day,hour,p0,p1,p2," + ",".join(f"extra{i}" for i in range(MAX_COLUMNS - 4))
    result = parse_records((header + "\n").encode(), **options(format="csv"))
    assert "column_limit" in codes(result)


def test_row_limit_and_bounded_error_count_truthful():
    result = parse([row((1, 2, 3), hour="99:99")] * (MAX_ERRORS + 5))
    assert result.error_count == MAX_ERRORS + 5 and len(result.errors) == MAX_ERRORS
    assert result.errors_truncated and not result.promotable
    assert result.errors[0].row == 1 and result.errors[-1].row == MAX_ERRORS
    raw = b"day,hour,p0,p1,p2\n" + b"2025-09-02,05:10,0,1,2\n" * (MAX_ROWS + 1)
    result = parse_records(raw, **options(format="csv"))
    assert "row_limit" in codes(result) and not result.promotable
    assert result.rows_seen == MAX_ROWS + 1 and result.records == ()
    result = parse([row()] * (MAX_ROWS + 1))
    assert "row_limit" in codes(result) and not result.promotable


def test_empty_and_oversized_csv_numeric_cell():
    assert "empty" in codes(parse([]))
    result = parse_records(
        b"day,hour,p0,p1,p2\n2025-09-02,05:10," + b"9" * 5000 + b",1,2\n", **options(format="csv")
    )
    assert codes(result) == {"number"}


def test_malformed_mapping_and_json_row_width_are_validation_errors():
    malformed = ColumnMapping("day", "hour", (cast(str, []), "p1", "p2"))
    assert "mapping" in codes(parse([row()], mapping=malformed))
    wide_row = {**row(), **{f"extra{i}": i for i in range(MAX_COLUMNS)}}
    assert "column_limit" in codes(parse([wide_row]))
    assert "shape" in codes(parse([{**row(), "nested": {"value": 1}}]))


def test_deeply_nested_valid_json_is_bounded_invalid_preview():
    raw = b"[" * 100_000 + b"0" + b"]" * 100_000
    result = parse_records(raw, **options())
    assert result.source_sha256 == sha256(raw).hexdigest()
    assert codes(result) == {"json"} and result.error_count == 1
    assert result.records == () and result.dataset_sha256 is None
    assert not result.promotable and not result.errors_truncated


@pytest.mark.parametrize("field", ["source_id", "revision", "provenance"])
def test_lone_surrogate_source_metadata_is_invalid_preview(field):
    raw = json.dumps([row()]).encode()
    values = {"source_id": "local-1", "revision": "v1", "provenance": "manual"}
    values[field] = "prefix\ud800suffix"
    source = SourceMetadata(
        values["source_id"], "historical", values["revision"], values["provenance"]
    )
    result = parse_records(raw, **options(source=source))
    assert result.source_sha256 == sha256(raw).hexdigest()
    assert codes(result) == {"source"} and result.error_count == 1
    assert result.records == () and result.dataset_sha256 is None and not result.promotable


def test_lone_surrogate_mapping_and_clock_are_invalid_previews():
    raw = json.dumps([row()]).encode()
    mapping = ColumnMapping("day", "hour", ("p0", "p1", "p\ud800"))
    mapped = parse_records(raw, **options(mapping=mapping))
    clocked = parse_records(raw, **options(clock=ClockDeclaration("iana", "Etc/\ud800")))
    assert codes(mapped) == {"mapping"} and codes(clocked) == {"clock_zone"}
    for result in (mapped, clocked):
        assert result.source_sha256 == sha256(raw).hexdigest()
        assert result.records == () and result.dataset_sha256 is None and not result.promotable


def test_bypassed_profile_text_validation_cannot_poison_hash():
    raw = json.dumps([row()]).encode()
    valid = profile()
    # model_construct is explicitly outside GameProfile validation, but the
    # importer still must not crash or promote an invalid textual identity.
    forged = GameProfile.model_construct(**{**valid.model_dump(), "profile_id": "bad\ud800"})
    result = parse_records(raw, **options(profile=forged))
    assert codes(result) == {"profile"} and result.source_sha256 == sha256(raw).hexdigest()
    assert result.records == () and result.dataset_sha256 is None and not result.promotable


def test_naive_preview_does_not_open_application_files(monkeypatch):
    def deny_open(*args, **kwargs):
        raise AssertionError("parser must not open files")

    monkeypatch.setattr(builtins, "open", deny_open)
    assert parse([row()]).promotable
