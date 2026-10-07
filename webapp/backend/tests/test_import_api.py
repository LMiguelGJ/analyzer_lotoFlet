"""Local import HTTP admission, bounded projection, and promotion authority."""

# Contract traceability:
# B-API-065: test_preview_no_writes_bounded_sample_truthful_counts_and_errors
# B-API-066: test_promote_hash_gate_idempotence_and_distinct_raw_retained
# B-API-067/068: test_invalid_envelope_metadata_and_parser_errors
# B-API-069: test_quota_failure_rolls_back_and_integrity_failure_is_opaque
# B-API-070/072: test_cap_declared_and_streamed_with_missing_or_false_length_and_local_guard
# B-API-071: test_decoded_limit_and_other_route_unchanged
# B-API-111..114: native history imports remain covered by tests in
#   test_history_import.py (preview/hash/promotion, metadata/profile validation,
#   quota revalidation, and strict legacy import format).

import base64
import json
import sqlite3
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_import_records import options, row

from laboratorio.app import _IMPORT_ENVELOPE_BYTES, create_app
from laboratorio.settings import Settings

PATH = "/api/v1/imports"
ORIGIN = {"Origin": "http://127.0.0.1:8765"}


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "local"
    settings = Settings(root, root / "history", root / "rankings", root / "frontend")
    app = create_app(settings, catalog_loader=lambda _: SimpleNamespace())
    with TestClient(app, base_url="http://127.0.0.1:8765") as api:
        yield api, settings


def payload(raw=None, **changes):
    opts = options()
    data = json.dumps([row()]).encode() if raw is None else raw
    body = {
        "raw_base64": base64.b64encode(data).decode("ascii"),
        "format": opts["format"],
        "mapping": {
            "date": opts["mapping"].date,
            "time": opts["mapping"].time,
            "positions": list(opts["mapping"].positions),
        },
        "source": vars(opts["source"]),
        "clock": vars(opts["clock"]),
        "profile": opts["profile"].model_dump(mode="json"),
    }
    body.update(changes)
    return body


def post(api, action, body, headers=None):
    return api.post(f"{PATH}/{action}", json=body, headers=ORIGIN if headers is None else headers)


def count(settings):
    with sqlite3.connect(settings.database_path) as db:
        return db.execute("SELECT count(*) FROM datasets").fetchone()[0]


def test_preview_no_writes_bounded_sample_truthful_counts_and_errors(client):
    api, settings = client
    data = json.dumps([row(hour=f"{n // 60:02d}:{n % 60:02d}") for n in range(25)]).encode()
    result = post(api, "preview", payload(data))
    assert result.status_code == 200
    view = result.json()
    assert view["promotable"] and view["execution_supported"] is False
    assert view["rows_seen"] == view["records_total"] == 25
    assert len(view["sample"]) == 20
    assert len(view["dataset_sha256"]) == 64
    assert view["source_sha256"] == sha256(data).hexdigest()
    assert count(settings) == 0
    errors = post(api, "preview", payload(json.dumps([row(hour="bad")] * 105).encode()))
    assert errors.status_code == 200
    invalid = errors.json()
    assert not invalid["promotable"] and invalid["dataset_sha256"] is None
    assert invalid["records_total"] == 0 and invalid["rows_seen"] == 105
    assert invalid["error_count"] == 105 and invalid["errors_truncated"]
    assert len(invalid["errors"]) == 100 and invalid["sample"] == []
    assert count(settings) == 0


def test_promote_hash_gate_idempotence_and_distinct_raw_retained(client):
    api, settings = client
    body = payload()
    preview = post(api, "preview", body).json()
    rejected = post(api, "promote", {**body, "expected_dataset_sha256": "0" * 64})
    assert rejected.status_code == 409 and count(settings) == 0
    approved = {**body, "expected_dataset_sha256": preview["dataset_sha256"]}
    first = post(api, "promote", approved)
    assert first.status_code == 200
    saved = first.json()
    assert saved["created"] and saved["dataset_sha256"] == preview["dataset_sha256"]
    assert saved["retained_source_sha256"] == saved["submitted_source_sha256"]
    assert saved["execution_supported"] is False
    assert "raw_bytes" not in saved and "canonical_json" not in saved
    again = post(api, "promote", approved).json()
    assert not again["created"] and not again["duplicate_source_differs"]
    alternate = payload(json.dumps([row()], indent=2).encode())
    alternate["expected_dataset_sha256"] = preview["dataset_sha256"]
    duplicate = post(api, "promote", alternate).json()
    assert not duplicate["created"] and duplicate["duplicate_source_differs"]
    assert duplicate["retained_source_sha256"] == saved["retained_source_sha256"]
    assert duplicate["submitted_source_sha256"] != saved["retained_source_sha256"]
    assert count(settings) == 1


def test_invalid_envelope_metadata_and_parser_errors(client):
    api, settings = client
    body = payload()
    for field, value in (
        ("raw_base64", "ab==!"),
        ("raw_base64", "%%%"),
        ("raw_base64", body["raw_base64"] + "="),
        ("format", "xml"),
        ("source", {**body["source"], "source_id": True}),
        ("mapping", {**body["mapping"], "positions": [True, "p1", "p2"]}),
        ("clock", {**body["clock"], "mode": True}),
        ("profile", {**body["profile"], "positions": True}),
    ):
        assert post(api, "preview", {**body, field: value}).status_code == 422
    assert post(api, "preview", {**body, "unexpected": 1}).status_code == 422
    assert post(api, "promote", body).status_code == 422  # hash is mandatory
    for raw in (b"{", b"[" * 1100, json.dumps([row(hour="25:00")]).encode()):
        invalid = payload(raw)
        view = post(api, "preview", invalid)
        assert view.status_code == 200 and not view.json()["promotable"]
        rejected = post(api, "promote", {**invalid, "expected_dataset_sha256": "0" * 64})
        assert rejected.status_code == 422
    for text in ('{"raw_base64":', '{"raw_base64":"a","raw_base64":"b"}', "[" * 1100):
        response = api.post(f"{PATH}/preview", content=text, headers=ORIGIN)
        assert response.status_code == 422
    assert count(settings) == 0


def test_quota_failure_rolls_back_and_integrity_failure_is_opaque(client):
    api, settings = client
    body = payload()
    body["expected_dataset_sha256"] = post(api, "preview", body).json()["dataset_sha256"]
    api.app.state.settings = replace(settings, quota_bytes=1, quota_explicit=True)
    response = post(api, "promote", body)
    assert response.status_code == 409 and count(settings) == 0
    api.app.state.settings = settings
    assert post(api, "promote", body).status_code == 200
    with sqlite3.connect(settings.database_path) as db:
        db.execute("DROP TRIGGER datasets_no_update")
        db.execute("UPDATE datasets SET raw_bytes = X'00'")
    corrupt = post(api, "promote", body)
    assert corrupt.status_code == 409
    assert "corrupt stored dataset" not in corrupt.text and "canonical" not in corrupt.text
    assert count(settings) == 1


def test_cap_declared_and_streamed_with_missing_or_false_length_and_local_guard(client):
    api, settings = client
    limit = _IMPORT_ENVELOPE_BYTES
    path = f"{PATH}/preview"
    declared = api.post(path, content=b"{}", headers={**ORIGIN, "Content-Length": str(limit + 1)})
    assert declared.status_code == 413

    def chunks():
        yield b" " * limit
        yield b"x"

    for action in ("preview", "promote"):
        for headers in (ORIGIN, {**ORIGIN, "Content-Length": "2"}):
            response = api.post(f"{PATH}/{action}", content=chunks(), headers=headers)
            assert response.status_code == 413
    assert post(api, "preview", payload(), headers={"Host": "evil", **ORIGIN}).status_code == 403
    assert post(api, "preview", payload(), headers={"Origin": "http://evil"}).status_code == 403
    assert post(api, "preview", payload(), headers={}).status_code == 403
    assert count(settings) == 0


def test_decoded_limit_and_other_route_unchanged(client):
    api, _ = client
    body = payload(b"x" * (2 * 1024 * 1024 + 1))
    assert post(api, "preview", body).status_code == 413
    assert post(api, "promote", {**body, "expected_dataset_sha256": "0" * 64}).status_code == 413
    other = api.post(
        "/api/v1/does-not-exist", content=b"x" * (_IMPORT_ENVELOPE_BYTES + 1), headers=ORIGIN
    )
    assert other.status_code == 404


@pytest.mark.parametrize("action", ["preview", "promote"])
def test_common_entry_strict_mode_and_records_budget(client, action):
    api, settings = client
    body = payload()
    if action == "promote":
        body["expected_dataset_sha256"] = post(api, "preview", body).json()["dataset_sha256"]
    # Explicit records uses exactly the old envelope/parser, including decoded limit.
    headers = {**ORIGIN, "X-Import-Mode": "records"}
    assert post(api, action, body, headers=headers).status_code == 200
    oversized = payload(b"x" * (2 * 1024 * 1024 + 1))
    if action == "promote":
        oversized["expected_dataset_sha256"] = "0" * 64
    assert post(api, action, oversized, headers=headers).status_code == 413
    assert (
        api.post(
            f"{PATH}/{action}",
            content=b"{}",
            headers={**headers, "Content-Length": str(_IMPORT_ENVELOPE_BYTES + 1)},
        ).status_code
        == 413
    )

    def chunks():
        yield b" " * _IMPORT_ENVELOPE_BYTES
        yield b"x"

    for length in ({}, {"Content-Length": "2"}):
        assert (
            api.post(
                f"{PATH}/{action}", content=chunks(), headers={**headers, **length}
            ).status_code
            == 413
        )
    for values in (
        ["unknown"],
        ["History"],
        ["history,records"],
        [""],
        ["history", "records"],
        ["history", "history"],
    ):
        response = api.post(
            f"{PATH}/{action}",
            content=b"{}",
            headers=[
                *ORIGIN.items(),
                *(("X-Import-Mode", value) for value in values),
                ("Content-Length", str(_IMPORT_ENVELOPE_BYTES + 1)),
            ],
        )
        assert response.status_code == 422  # invalid mode never selects a larger budget
    assert count(settings) == (1 if action == "promote" else 0)
