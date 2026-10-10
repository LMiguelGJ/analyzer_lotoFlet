"""HTTP contract for active history listing and raw JSON imports."""

import json
from dataclasses import replace

from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}


def make_app(tmp_path, lab_data, *, quota_bytes=None):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    if quota_bytes is not None:
        settings = replace(settings, quota_bytes=quota_bytes, quota_explicit=True)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def history_bytes(entries):
    by_date = {}
    for date, hour, numbers in entries:
        by_date.setdefault(date, []).append(
            {"hora": hour, "numeros": [f"{number:02d}" for number in numbers]}
        )
    return json.dumps({"sorteos_por_fecha": by_date}).encode()


NEW_DRAWS = [
    ("2026-09-26", "10:00", [1, 2, 3, 4, 5]),
    ("2026-09-26", "15:00", [6, 7, 8, 9, 10]),
]


def test_get_fresh_history_reports_frozen_catalog(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.get("/api/v1/history")

    assert response.status_code == 200
    body = response.json()
    assert body["active"] == {
        "sha256": lab_data.history.sha256,
        "origin": "frozen",
        "draws": 105426,
        "ranked_draws": 65235,
        "first_label": "2025-03-05 05:05",
        "last_label": "2026-09-25 18:20",
        "added_draws": 0,
        "created_at": None,
        "active": True,
    }
    assert body["sources"] == [body["active"]]


def test_import_is_active_idempotent_persistent_and_updates_settings(tmp_path, lab_data):
    raw = history_bytes(NEW_DRAWS)
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        before = client.get("/api/v1/settings").json()["storage"]
        response = client.post("/api/v1/history", content=raw, headers=ORIGIN)
        assert response.status_code == 201
        result = response.json()
        assert result["created"] is True
        assert result["added"] == len(NEW_DRAWS)
        assert result["active"]["draws"] == 105426 + len(NEW_DRAWS)
        assert result["active"]["added_draws"] == len(NEW_DRAWS)
        assert result["active"]["active"] is True

        listing = client.get("/api/v1/history").json()
        assert listing["active"] == result["active"]
        assert [item["origin"] for item in listing["sources"]] == ["frozen", "import"]
        assert listing["sources"][1]["active"] is True

        repeated = client.post("/api/v1/history", content=raw, headers=ORIGIN)
        assert repeated.status_code == 200
        assert repeated.json()["created"] is False
        assert repeated.json()["added"] == 0

        after = client.get("/api/v1/settings").json()["storage"]
        assert "history_artifact_bytes" in before
        assert "history_artifact_bytes_exact" in before
        assert int(after["history_artifact_bytes_exact"]) > int(
            before["history_artifact_bytes_exact"]
        )

    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as second_client:
        persisted = second_client.get("/api/v1/history").json()
    assert persisted["active"]["origin"] == "import"
    assert persisted["active"]["draws"] == 105426 + len(NEW_DRAWS)


def test_history_import_errors_and_origin_policy(tmp_path, lab_data):
    conflict = history_bytes([("2025-03-05", "05:05", [99, 98, 97, 96, 95])])
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.post("/api/v1/history", content=b"{", headers=ORIGIN).status_code == 422
        assert (
            client.post("/api/v1/history", content=b'{"wrong": []}', headers=ORIGIN).status_code
            == 422
        )
        assert client.post("/api/v1/history", content=b"", headers=ORIGIN).status_code == 422
        response = client.post("/api/v1/history", content=conflict, headers=ORIGIN)
        assert response.status_code == 409
        assert "sorteos" in response.json()["detail"]
        assert client.post("/api/v1/history", content=b"{} ").status_code == 403


def test_history_import_rejects_oversized_content_length(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.post(
            "/api/v1/history",
            content=b"{}",
            headers={**ORIGIN, "Content-Length": str(32 * 1024 * 1024 + 1)},
        )
    assert response.status_code == 413
    assert response.json() == {"detail": "El archivo supera el límite de 32 MiB."}


def test_history_import_rejects_oversized_stream_without_content_length(tmp_path, lab_data):
    payload = b"x" * (32 * 1024 * 1024 + 1)
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.post(
            "/api/v1/history",
            content=iter((payload,)),
            headers=ORIGIN,
        )
    assert response.status_code == 413
    assert response.json() == {"detail": "El archivo supera el límite de 32 MiB."}


def test_history_import_quota_exceeded(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data, quota_bytes=1), base_url=BASE_URL) as client:
        response = client.post("/api/v1/history", content=history_bytes(NEW_DRAWS), headers=ORIGIN)
    assert response.status_code == 409
    assert "cuota" in response.json()["detail"]
