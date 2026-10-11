from dataclasses import replace

from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.reference_labs import REFERENCE_LABS
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"


def make_app(tmp_path, lab_data):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def test_reference_catalog_returns_ordered_immutable_contracts_and_provenance(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = client.get("/api/v1/reference-labs")

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == 1
    assert body["reference_history"] == {
        "sha256": lab_data.history.sha256,
        "origin": "frozen_reference",
        "draws": 105426,
        "ranked_draws": 65235,
        "first_label": "2025-03-05 05:05",
        "last_label": "2026-09-25 18:20",
    }
    assert body["capabilities"] == {"session_summary": True, "per_bet_trace": False}
    assert [item["lab_id"] for item in body["items"]] == [lab.lab_id for lab in REFERENCE_LABS]
    assert body["items"] == [
        {
            "lab_id": lab.lab_id,
            "system": lab.system,
            "coverage": lab.coverage,
            "stake_style": lab.stake_style,
            "selection_kind": lab.selection_kind,
            "capital": 2000,
            "goal": 2800,
            "prizes": [80, 8, 4, 2, 1],
            "window": {"start": "2025-09-02 05:10", "end": "2026-09-25 18:20"},
            "duration_cap": None,
            "editable": False,
        }
        for lab in REFERENCE_LABS
    ]


def test_reference_lab_detail_matches_catalog_item_and_unknown_is_404(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        catalog = client.get("/api/v1/reference-labs").json()
        detail = client.get("/api/v1/reference-labs/paridad_50_escalera")
        unknown = client.get("/api/v1/reference-labs/not-a-lab")

    assert detail.status_code == 200
    assert detail.json() == {
        "contract_version": catalog["contract_version"],
        "reference_history": catalog["reference_history"],
        "capabilities": catalog["capabilities"],
        "lab": catalog["items"][12],
    }
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "El laboratorio de referencia no existe."}
