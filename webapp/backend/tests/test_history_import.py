"""Canonical nested history parsing and bounded API promotion."""

import json
import sqlite3
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_import_records import profile

from laboratorio.app import create_app
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.importing.history import parse_history
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


def test_nested_history_counts_actual_rows_and_hashes_raw_bytes():
    raw = json.dumps(document(), separators=(",", ":")).encode()
    result = parse_history(raw, profile())
    assert result.promotable
    assert result.rows_seen == len(result.records) == 2
    assert result.source_sha256 == sha256(raw).hexdigest()
    assert result.dataset_sha256 and len(result.dataset_sha256) == 64
    assert result.records[0].numbers == (1, 2, 3)


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
