"""Canonical nested history parsing and bounded API promotion."""

import json
import sqlite3
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_import_records import profile

from laboratorio.app import _IMPORT_ENVELOPE_BYTES, create_app
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.importing.history import MAX_HISTORY_BYTES, parse_history
from laboratorio.settings import Settings


def document(draws=None):
    draws = draws or {
        "2025-01-01": [
            {"hora": "05:05", "numeros": ["01", "02", "03"]},
            {"hora": "05:10", "numeros": ["04", "05", "06"]},
        ]
    }
    return {
        "metadata": {
            "schema_version": 1,
            "juego": "Example",
            "origen": "https://example.test/history",
            "endpoint": "https://example.test/api",
            "zona_horaria": "UTC",
            "cantidad_sorteos": sum(len(items) for items in draws.values()),
            "rango_seleccionado": {"desde": "2025-01-01", "hasta": "2025-01-01"},
        },
        "sorteos_por_fecha": draws,
    }


# B-STO-073: nested history preview counts actual draws and hashes exact source bytes.
def test_nested_history_counts_actual_rows_and_hashes_raw_bytes():
    raw = json.dumps(document(), separators=(",", ":")).encode()
    result = parse_history(raw, profile())
    assert result.promotable
    assert result.rows_seen == len(result.records) == 2
    assert result.source_sha256 == sha256(raw).hexdigest()
    assert result.dataset_sha256 and len(result.dataset_sha256) == 64
    assert result.records[0].numbers == (1, 2, 3)


# B-STO-074: history accepts 10,002 draws and merges exact duplicate labels.
def test_history_accepts_more_than_legacy_row_limit_and_merges_exact_duplicates():
    items = [{"hora": "05:05", "numeros": ["01", "02", "03"]}] * 10_002
    raw = json.dumps(document({"2025-01-01": items})).encode()
    result = parse_history(raw, profile())
    assert result.promotable
    assert result.rows_seen == 10_002
    assert len(result.records) == 1
    assert result.duplicates_merged == 10_001


@pytest.mark.parametrize(
    "raw,code",
    [
        (b'{"metadata":{},"metadata":{},"sorteos_por_fecha":{}}', "json"),
        (
            json.dumps(
                document({"2025-01-01": [{"hora": "05:05", "numeros": [1, 1, 1]}]})
            ).encode(),
            "repeats",
        ),
        (
            json.dumps(
                document({"2025-01-01": [{"hora": "25:00", "numeros": [1, 2, 3]}]})
            ).encode(),
            "time",
        ),
    ],
)
# B-STO-075: malformed nested history rows/duplicate keys return parser error codes.
def test_history_rejects_malformed_nested_rows_and_duplicate_keys(raw, code):
    result = parse_history(raw, profile(repeats=False))
    assert not result.promotable and result.dataset_sha256 is None
    assert code in {error.code for error in result.errors}


@pytest.fixture
def api(tmp_path):
    root = tmp_path / "app"
    settings = Settings(root, root / "history", root / "rankings", root / "frontend")
    app = create_app(settings, catalog_loader=lambda _: SimpleNamespace())
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        game = profile()
        app.state.repo.create_game_profile(game)
        yield client, settings, game, app


def history_headers(profile_value, *, expected=None, source="https://example.test/history"):
    headers = {
        "Origin": "http://127.0.0.1:8765",
        "X-Profile-Id": profile_value.profile_id,
        "X-Profile-Revision": str(profile_value.revision),
        "X-Profile-Sha256": profile_sha256(profile_value),
        "X-Confirm-Source": source,
        "X-Confirm-Timezone": "UTC",
    }
    if expected is not None:
        headers["X-Expected-Dataset-Sha256"] = expected
    return headers


def test_history_api_raw_preview_hash_promote_and_paginated_library(api):
    client, settings, game, _app = api
    raw = json.dumps(document(), separators=(",", ":")).encode()
    headers = history_headers(game)
    preview = client.post("/api/v1/imports/history/preview", content=raw, headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["promotable"] and body["records_total"] == 2
    assert body["source_sha256"] == sha256(raw).hexdigest()
    assert body["profile_compatibility"]["registered"]
    assert body["profile_compatibility"]["execution_supported"] is False
    rejected = client.post(
        "/api/v1/imports/history/promote",
        content=raw,
        headers=history_headers(game, expected="0" * 64),
    )
    assert rejected.status_code == 409
    promoted = client.post(
        "/api/v1/imports/history/promote",
        content=raw,
        headers=history_headers(game, expected=body["dataset_sha256"]),
    )
    assert promoted.status_code == 200 and promoted.json()["created"]
    assert promoted.json()["retained_source_sha256"] == sha256(raw).hexdigest()
    listing = client.get("/api/v1/datasets?offset=0&limit=1")
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert listing.json()["items"][0]["records_total"] == 2
    assert listing.json()["items"][0]["first_draw"] == "2025-01-01 05:05"
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT raw_bytes FROM datasets").fetchone()[0] == raw


def test_history_api_requires_explicit_metadata_and_registered_profile(api):
    client, _, game, _app = api
    raw = json.dumps(document()).encode()
    assert (
        client.post(
            "/api/v1/imports/history/preview",
            content=raw,
            headers={"Origin": "http://127.0.0.1:8765"},
        ).status_code
        == 422
    )
    mismatch = history_headers(game, source="https://wrong.example")
    mismatch_response = client.post(
        "/api/v1/imports/history/preview", content=raw, headers=mismatch
    )
    assert mismatch_response.status_code == 409
    unknown = {**history_headers(game), "X-Profile-Id": "not-registered"}
    unknown_response = client.post("/api/v1/imports/history/preview", content=raw, headers=unknown)
    assert unknown_response.status_code == 422
    stale_hash = {**history_headers(game), "X-Profile-Sha256": "0" * 64}
    assert (
        client.post("/api/v1/imports/history/preview", content=raw, headers=stale_hash).status_code
        == 409
    )


def test_history_promote_revalidates_quota_and_old_import_format_stays_strict(api):
    client, _, game, app = api
    raw = json.dumps(document()).encode()
    headers = history_headers(game)
    preview = client.post("/api/v1/imports/history/preview", content=raw, headers=headers).json()
    app.state.settings = replace(app.state.settings, quota_bytes=1, quota_explicit=True)
    denied = client.post(
        "/api/v1/imports/history/promote",
        content=raw,
        headers=history_headers(game, expected=preview["dataset_sha256"]),
    )
    assert denied.status_code == 409
    legacy = client.post(
        "/api/v1/imports/preview",
        json={"raw_base64": "e30=", "format": "history_json"},
        headers={"Origin": "http://127.0.0.1:8765"},
    )
    assert legacy.status_code == 422


@pytest.mark.parametrize("action", ["preview", "promote"])
def test_common_history_entry_is_lossless_and_retains_native_admission(api, action):
    client, _, game, app = api
    # Valid history over the generic wire cap must arrive unchanged at the native parser.
    raw = json.dumps(document()).encode() + b" " * _IMPORT_ENVELOPE_BYTES
    legacy_headers = history_headers(game)
    baseline = client.post(
        "/api/v1/imports/history/preview", content=raw, headers=legacy_headers
    ).json()
    headers = {
        **history_headers(game, expected=baseline["dataset_sha256"]),
        "X-Import-Mode": "history",
    }
    path = f"/api/v1/imports/{action}"
    response = client.post(path, content=raw, headers=headers)
    assert response.status_code == 200
    if action == "preview":
        assert response.json() == baseline
    else:
        assert response.json()["retained_source_sha256"] == sha256(raw).hexdigest()
        alias = client.post("/api/v1/imports/history/promote", content=raw, headers=headers)
        assert alias.status_code == 200 and not alias.json()["created"]
    assert client.post(path, content=raw, headers=legacy_headers).status_code == 413
    assert (
        client.post(
            path,
            content=raw,
            headers={"Origin": "http://127.0.0.1:8765", "X-Import-Mode": "history"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, content=raw, headers={**headers, "Origin": "http://evil.example"}
        ).status_code
        == 403
    )
    for change, status in (
        ({"X-Profile-Sha256": "0" * 64}, 409),
        ({"X-Profile-Id": "missing"}, 422),
        ({"X-Confirm-Source": "wrong"}, 409),
        ({"X-Confirm-Timezone": "wrong"}, 409),
    ):
        assert client.post(path, content=raw, headers={**headers, **change}).status_code == status
    assert (
        client.post(path, content=b'{"metadata":{},"metadata":{}}', headers=headers).status_code
        == 422
    )
    if action == "promote":
        assert (
            client.post(
                path, content=raw, headers={**headers, "X-Expected-Dataset-Sha256": "0" * 64}
            ).status_code
            == 409
        )
        app.state.settings = replace(app.state.settings, quota_bytes=1, quota_explicit=True)
        # A distinct source/dataset still revalidates quota through the native promotion path.
        changed = json.dumps(
            document({"2025-01-01": [{"hora": "06:00", "numeros": [1, 2, 3]}]})
        ).encode()
        digest = client.post("/api/v1/imports/preview", content=changed, headers=headers).json()[
            "dataset_sha256"
        ]
        assert (
            client.post(
                path, content=changed, headers={**headers, "X-Expected-Dataset-Sha256": digest}
            ).status_code
            == 409
        )
    assert (
        client.post(
            path, content=b"{}", headers={**headers, "Content-Length": str(MAX_HISTORY_BYTES + 1)}
        ).status_code
        == 413
    )

    def chunks():
        for _ in range(32):
            yield b" " * (1024 * 1024)
        yield b"x"

    for length in ({}, {"Content-Length": "2"}):
        assert client.post(path, content=chunks(), headers={**headers, **length}).status_code == 413
    for alias in ("preview", "promote"):
        assert (
            client.post(
                f"/api/v1/imports/history/{alias}",
                content=raw,
                headers={**legacy_headers, "X-Import-Mode": "records"},
            ).status_code
            == 422
        )
