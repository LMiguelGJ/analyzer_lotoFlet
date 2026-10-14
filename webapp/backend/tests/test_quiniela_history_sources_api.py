"""Public API behavior for immutable, profile-bound v2 history sources."""

import hashlib
import json
from dataclasses import replace

from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"
HEADERS = {"Origin": BASE_URL, "Content-Type": "application/json"}
ROOT = "/api/v2/history-sources"
PROFILE_ROOT = "/api/v2/game-profiles"


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


def make_app(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def source_json(*, draws=None, timezone="UTC"):
    draws = draws or [
        {
            "schema_version": 2,
            "draw_id": "sample-1",
            "timestamp": "2026-01-01T12:00:00Z",
            "results": [1, 2],
        }
    ]
    return json.dumps(
        {"schema_version": 2, "timezone": timezone, "draws": draws},
        separators=(",", ":"),
    )


def create_profile(client):
    response = client.post(
        PROFILE_ROOT,
        json={"name": "Target", "rules": rules()},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    return response.json()


def public_state(client):
    return {
        "sources": client.get(ROOT).json(),
        "profiles": client.get(PROFILE_ROOT).json(),
        "legacy_history": client.get("/api/v1/history").json(),
        "laboratories": client.get("/api/v1/laboratories").json(),
        "storage": {
            key: client.get("/api/v1/settings").json()["storage"][key]
            for key in (
                "history_artifact_bytes_exact",
                "admission_logical_bytes_exact",
                "logical_used_bytes_exact",
            )
        },
    }


def test_preview_confirm_reopen_is_idempotent_and_never_activates_v1_history(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        profile = create_profile(client)
        before = public_state(client)
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Imported source",
            "raw_json": source_json(),
        }
        preview = client.post(ROOT + "/preview", json=body, headers=HEADERS)
        assert preview.status_code == 200, preview.text
        result = preview.json()
        assert result["draw_count"] == 1
        assert result["timezone"] == "UTC"
        assert result["raw_sha256"] == hashlib.sha256(body["raw_json"].encode()).hexdigest()
        assert len(result["sample"]) == 1
        assert "draws" not in result
        confirm_body = body | {"expected_preview_sha256": result["preview_sha256"]}
        confirmed = client.post(ROOT, json=confirm_body, headers=HEADERS)
        assert confirmed.status_code == 200, confirmed.text
        record = confirmed.json()
        assert record["created"] is True
        assert record["source_reference"]["origin"] == "imported"
        assert record["source_reference"]["rankings_sha256"] is None
        assert record["source_reference"]["profile_sha256"] == profile["sha256"]
        assert client.get(f"{ROOT}/{record['source']['id']}").json()["source"] == record["source"]
        page = client.get(ROOT, params={"offset": 0, "limit": 1}).json()
        assert page["total"] == 1 and page["items"][0]["source"] == record["source"]
        repeated = client.post(ROOT, json=confirm_body, headers=HEADERS)
        assert repeated.status_code == 200
        assert repeated.json()["created"] is False
        after = public_state(client)
        assert after["legacy_history"] == before["legacy_history"]
        assert after["laboratories"] == before["laboratories"]
        assert int(after["storage"]["history_artifact_bytes_exact"]) > int(
            before["storage"]["history_artifact_bytes_exact"]
        )
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as reopened:
        assert reopened.get(ROOT).json()["total"] == 1
        assert reopened.get("/api/v1/history").json()["active"]["origin"] == "frozen"


def test_preview_and_confirm_rejections_leave_public_sources_profiles_counters_and_v1_unchanged(
    tmp_path, lab_data
):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        profile = create_profile(client)
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Rejected",
            "raw_json": source_json(),
        }
        before = public_state(client)
        malformed = client.post(
            ROOT + "/preview", json=body | {"unexpected": True}, headers=HEADERS
        )
        assert malformed.status_code == 422
        preview = client.post(ROOT + "/preview", json=body, headers=HEADERS).json()
        wrong = client.post(
            ROOT,
            json=body | {"expected_preview_sha256": "0" * 64},
            headers=HEADERS,
        )
        assert wrong.status_code == 409
        changed = client.post(
            ROOT,
            json=body
            | {
                "raw_json": source_json(
                    draws=[
                        {
                            "schema_version": 2,
                            "draw_id": "changed",
                            "timestamp": "2026-01-01T12:00:00Z",
                            "results": [2, 1],
                        }
                    ]
                ),
                "expected_preview_sha256": preview["preview_sha256"],
            },
            headers=HEADERS,
        )
        assert changed.status_code == 409
        conflicting = source_json(
            draws=[
                {
                    "schema_version": 2,
                    "draw_id": "same-id",
                    "timestamp": "2026-01-01T12:00:00Z",
                    "results": [1, 2],
                },
                {
                    "schema_version": 2,
                    "draw_id": "same-id",
                    "timestamp": "2026-01-01T12:00:00Z",
                    "results": [2, 1],
                },
            ]
        )
        conflict = client.post(
            ROOT + "/preview",
            json=body | {"raw_json": conflicting},
            headers=HEADERS,
        )
        assert conflict.status_code == 422
        incompatible = client.post(
            ROOT + "/preview",
            json=body | {"profile_id": "00000000-0000-0000-0000-000000000000"},
            headers=HEADERS,
        )
        assert incompatible.status_code == 404
        assert public_state(client) == before


def test_naive_timezone_requires_confirmation_and_invalid_paging_is_nonmutating(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        profile = create_profile(client)
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Naive",
            "timezone": "UTC",
            "raw_json": source_json(
                draws=[
                    {
                        "schema_version": 2,
                        "draw_id": "naive",
                        "timestamp": "2026-01-01T12:00:00",
                        "results": [1, 2],
                    }
                ]
            ),
        }
        before = public_state(client)
        rejected = client.post(ROOT + "/preview", json=body, headers=HEADERS)
        assert rejected.status_code == 422
        accepted = client.post(
            ROOT + "/preview", json=body | {"timezone_confirmed": True}, headers=HEADERS
        )
        assert accepted.status_code == 200
        assert accepted.json()["sample"][0]["timestamp"] == "2026-01-01T12:00:00Z"
        for params in ({"offset": -1}, {"offset": 2**53}, {"limit": 101}, {"limit": 0}):
            assert client.get(ROOT, params=params).status_code == 422
        assert public_state(client) == before


def test_history_source_posts_preserve_local_guards_and_body_limits(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        profile = create_profile(client)
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Guarded",
            "raw_json": source_json(),
        }
        before = public_state(client)
        missing_origin = client.post(
            ROOT + "/preview",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        assert missing_origin.status_code == 403
        too_large = client.post(
            ROOT + "/preview",
            content=b"{}",
            headers=HEADERS | {"Content-Length": str(64 * 1024 * 1024 + 64 * 1024 + 1)},
        )
        assert too_large.status_code == 413
        duplicate = (
            '{"profile_id":"'
            + profile["profile"]["id"]
            + '","profile_id":"'
            + profile["profile"]["id"]
            + '","name":"bad","raw_json":"{}"}'
        )
        duplicate_response = client.post(ROOT + "/preview", content=duplicate, headers=HEADERS)
        assert duplicate_response.status_code == 422
        assert public_state(client) == before


def test_included_routes_use_only_configured_frozen_input_and_preserve_exact_raw_hash(
    tmp_path, lab_data, monkeypatch
):
    import laboratorio.api.history_sources as history_sources_api
    import laboratorio.storage.quiniela_history_store as history_store

    included = {
        "metadata": {"zona_horaria": "America/Santo_Domingo"},
        "sorteos_por_fecha": {
            "2026-06-10": [{"hora": "12:00", "numeros": ["07", "03", "09", "01", "00"]}]
        },
    }
    raw = json.dumps(included, separators=(",", ":")).encode("utf-8")
    configured_file = tmp_path / "configured-included.json"
    configured_file.write_bytes(raw)
    settings = replace(
        Settings.from_environment(),
        data_dir=tmp_path,
        port=8765,
        history_path=configured_file,
    )
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    frozen_sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(history_sources_api, "HISTORY_SHA256", frozen_sha)
    monkeypatch.setattr(history_store, "HISTORY_SHA256", frozen_sha)
    include_rules = rules() | {
        "universe": list(range(100)),
        "display_width": 2,
        "positions": 5,
        "played_positions": [0, 1, 2, 3, 4],
        "multipliers": [{"numerator": 1, "denominator": 1}] * 5,
        "max_coverage": 50,
        "max_exposure": 1_000_000,
    }
    with TestClient(app, base_url=BASE_URL) as client:
        profile = client.post(
            PROFILE_ROOT,
            json={"name": "Included-compatible", "rules": include_rules},
            headers=HEADERS,
        ).json()
        body = {"profile_id": profile["profile"]["id"]}
        before = public_state(client)
        rejected_extra = client.post(
            ROOT + "/included/preview", json=body | {"path": "elsewhere"}, headers=HEADERS
        )
        assert rejected_extra.status_code == 422
        preview = client.post(ROOT + "/included/preview", json=body, headers=HEADERS)
        assert preview.status_code == 200, preview.text
        assert preview.json()["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        confirmed = client.post(
            ROOT + "/included/confirm",
            json=body | {"expected_preview_sha256": preview.json()["preview_sha256"]},
            headers=HEADERS,
        )
        assert confirmed.status_code == 200, confirmed.text
        reference = confirmed.json()["source_reference"]
        assert reference["origin"] == "included"
        assert reference["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert reference["rankings_sha256"] is None
        assert client.get("/api/v1/history").json() == before["legacy_history"]


def test_corrupt_persisted_history_is_rejected_without_repair(tmp_path, lab_data):
    from laboratorio.storage.database import connection

    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        profile = create_profile(client)
        body = {
            "profile_id": profile["profile"]["id"],
            "name": "Corruptible",
            "raw_json": source_json(),
        }
        preview = client.post(ROOT + "/preview", json=body, headers=HEADERS).json()
        stored = client.post(
            ROOT,
            json=body | {"expected_preview_sha256": preview["preview_sha256"]},
            headers=HEADERS,
        )
        assert stored.status_code == 200
        identifier = stored.json()["source"]["id"]
        with connection(app.state.repo.path) as db:
            db.execute(
                "UPDATE quiniela_history_sources SET canonical_sha256=? WHERE id=?",
                ("0" * 64, identifier),
            )
            db.commit()
        before = client.get("/api/v1/settings").json()["storage"]
        for path in (ROOT, f"{ROOT}/{identifier}"):
            response = client.get(path)
            assert response.status_code == 409
        after = client.get("/api/v1/settings").json()["storage"]
        assert after["history_artifact_bytes_exact"] == before["history_artifact_bytes_exact"]
