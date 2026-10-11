"""All fourteen reference laboratories through the public HTTP surface against the frozen golden.

The oracle is ``fixtures/reference_labs_golden.json`` plus independent arithmetic and a local
digest routine; nothing here hashes sessions with production helpers.
"""

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.domain.reference_labs import REFERENCE_LABS
from laboratorio.settings import Settings

BASE_URL = "http://localhost:8765"
ORIGIN = {"Origin": BASE_URL, "Content-Type": "application/json"}
ROOT = "/api/v1/reference-labs"
GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "reference_labs_golden.json").read_text(encoding="utf-8")
)
GOLDEN_BY_ID = {row["lab_id"]: row for row in GOLDEN["laboratories"]}
SESSION_FIELDS = (
    "outcome",
    "start_index",
    "end_index",
    "draws",
    "final_balance",
    "wagered",
    "paid",
)


@pytest.fixture(scope="module")
def client(tmp_path_factory, lab_data):
    settings = replace(
        Settings.from_environment(), data_dir=tmp_path_factory.mktemp("golden-http"), port=8765
    )
    app = create_app(settings, catalog_loader=lambda _settings: lab_data)
    with TestClient(app, base_url=BASE_URL) as test_client:
        yield test_client


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _boundaries(rows):
    picked = {}
    for index, row in enumerate(rows):
        if row[0] in ("goal", "ruin") and row[0] not in picked:
            picked[row[0]] = {"index": index, "session": list(row)}
    for index in range(len(rows) - 1, -1, -1):
        if rows[index][0] == "incomplete":
            picked["incomplete"] = {"index": index, "session": list(rows[index])}
            break
    if rows:
        picked["first"] = {"index": 0, "session": list(rows[0])}
        picked["last"] = {"index": len(rows) - 1, "session": list(rows[-1])}
    return picked


def _page_all(client, lab_id, run_id):
    rows, offset, total = [], 0, None
    while total is None or offset < total:
        response = client.get(
            f"{ROOT}/{lab_id}/runs/{run_id}/sessions", params={"limit": 100, "offset": offset}
        )
        assert response.status_code == 200, response.text
        page = response.json()
        total = page["total"]
        assert page["offset"] == offset and page["limit"] == 100
        assert len(page["items"]) <= 100
        for item in page["items"]:
            assert item["ordinal"] == len(rows)
            assert set(item["summary"]) == set(SESSION_FIELDS)
            rows.append(tuple(item["summary"][name] for name in SESSION_FIELDS))
        offset += 100
    assert total == len(rows)
    return rows


def test_golden_fixture_pins_the_loaded_frozen_sources(lab_data):
    assert GOLDEN["provenance"]["history"]["sha256"] == lab_data.history.sha256
    assert tuple(GOLDEN_BY_ID) == tuple(lab.lab_id for lab in REFERENCE_LABS)
    assert len(GOLDEN_BY_ID) == 14


@pytest.mark.parametrize("lab_id", [lab.lab_id for lab in REFERENCE_LABS])
def test_http_run_matches_golden_summary_provenance_and_every_session(client, lab_id):
    expected = GOLDEN_BY_ID[lab_id]
    started = time.perf_counter()
    created = client.post(
        f"{ROOT}/{lab_id}/runs",
        json={"required_history_sha256": GOLDEN["provenance"]["history"]["sha256"]},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["lab_id"] == lab_id
    assert body["provenance"] == {
        "history_sha256": GOLDEN["provenance"]["history"]["sha256"],
        "history_origin": "frozen",
        "rankings_sha256": GOLDEN["provenance"]["rankings"]["sha256"],
    }
    assert body["summary"] == {
        "eligible_draws": expected["eligible_draws"],
        "gaps": expected["gaps"],
        "first": expected["first"],
        "last": expected["last"],
        "session_sha256": expected["session_sha256"],
        "session_count": expected["session_count"],
        "totals": expected["totals"],
    }
    assert body["summary"]["totals"]["mean_net_closed"] == expected["totals"]["mean_net_closed"]
    assert body["config"]["capital"] == expected["capital"] == 2000
    assert body["config"]["prizes"] == expected["prizes"]

    assert client.get(f"{ROOT}/{lab_id}/runs/{body['id']}").json() == body
    listed = client.get(f"{ROOT}/{lab_id}/runs", params={"limit": 100}).json()
    thin = next(item for item in listed["items"] if item["id"] == body["id"])
    assert thin["summary"] == {
        "eligible_draws": expected["eligible_draws"],
        "gaps": expected["gaps"],
        "totals": expected["totals"],
    }

    rows = _page_all(client, lab_id, body["id"])
    assert len(rows) == expected["session_count"]
    assert _digest(rows) == expected["session_sha256"]
    assert _boundaries([list(row) for row in rows]) == expected["boundary_sessions"]
    totals = expected["totals"]
    assert sum(row[5] for row in rows) == totals["total_wagered"]
    assert sum(row[6] for row in rows) == totals["total_paid"]
    assert sum(row[3] for row in rows) == totals["total_steps"]
    closed = [row[4] - 2000 for row in rows if row[0] != "incomplete"]
    assert len(closed) == totals["completed"]
    assert (sum(closed) / len(closed) if closed else None) == totals["mean_net_closed"]
    print(f"{lab_id}: {len(rows)} sessions in {time.perf_counter() - started:.1f}s")
