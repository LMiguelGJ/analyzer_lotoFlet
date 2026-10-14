"""Atomic admission and defensive reads for profile-bound history storage."""

import json
from dataclasses import replace

from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings

HEADERS = {"Origin": "http://localhost:8765", "Content-Type": "application/json"}
PROFILE_ROOT = "/api/v2/game-profiles"
ROOT = "/api/v2/history-sources"


def make_app(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def rules():
    return {
        "schema_version": 2,
        "universe": list(range(10)),
        "display_width": 1,
        "positions": 2,
        "played_positions": [0, 1],
        "order_matters": True,
        "allows_repeats": True,
        "multipliers": [{"numerator": 1, "denominator": 1}] * 2,
        "payout_mode": "all",
        "currency": "DOP",
        "scale": 0,
        "minimum_stake": 1,
        "stake_increment": 1,
        "maximum_stake": 100,
        "max_coverage": 10,
        "max_exposure": 1_000,
    }


def source_json(draws=None):
    draws = draws or [
        {
            "schema_version": 2,
            "draw_id": "sample-1",
            "timestamp": "2026-01-01T12:00:00Z",
            "results": [1, 2],
        }
    ]
    return json.dumps(
        {"schema_version": 2, "timezone": "UTC", "draws": draws},
        separators=(",", ":"),
    )


def test_confirmed_source_is_charged_once_and_quota_rejection_is_atomic(tmp_path, lab_data):
    from laboratorio.storage.database import connection

    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url="http://localhost:8765") as client:
        profile = client.post(
            PROFILE_ROOT,
            json={"name": "Quota target", "rules": rules()},
            headers=HEADERS,
        ).json()
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Quota history",
            "raw_json": source_json(),
        }
        preview = client.post(ROOT + "/preview", json=body, headers=HEADERS).json()
        storage = client.get("/api/v1/settings").json()["storage"]
        before_bytes = int(storage["history_artifact_bytes_exact"])
        with connection(app.state.repo.path) as db:
            db.execute("INSERT INTO settings_quota(id,quota_bytes) VALUES(1,1)")
            db.commit()
        response = client.post(
            ROOT,
            json=body | {"expected_preview_sha256": preview["preview_sha256"]},
            headers=HEADERS,
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "La cuota no permite guardar esta fuente."}
        assert client.get(ROOT).json()["total"] == 0
        after = client.get("/api/v1/settings").json()["storage"]
        assert int(after["history_artifact_bytes_exact"]) == before_bytes
        assert client.get("/api/v1/history").json()["active"]["origin"] == "frozen"


def test_source_pagination_never_returns_all_draw_rows(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url="http://localhost:8765") as client:
        profile = client.post(
            PROFILE_ROOT,
            json={"name": "Page target", "rules": rules()},
            headers=HEADERS,
        ).json()
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Page source",
            "raw_json": source_json(
                draws=[
                    {
                        "schema_version": 2,
                        "draw_id": f"d-{index}",
                        "timestamp": f"2026-01-01T12:00:{index:02d}Z",
                        "results": [1, 2],
                    }
                    for index in range(5)
                ]
            ),
        }
        preview = client.post(ROOT + "/preview", json=body, headers=HEADERS).json()
        confirmed = client.post(
            ROOT,
            json=body | {"expected_preview_sha256": preview["preview_sha256"]},
            headers=HEADERS,
        )
        assert confirmed.status_code == 200
        page = client.get(ROOT, params={"limit": 1}).json()
        assert page["total"] == 1
        assert len(page["items"]) == 1
        assert len(page["items"][0]["sample"]) == 3
        assert "draws" not in page["items"][0]
