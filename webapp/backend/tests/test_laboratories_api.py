import asyncio
import json
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from laboratorio.api import laboratories as laboratories_api
from laboratorio.app import create_app
from laboratorio.settings import Settings
from laboratorio.storage.database import connection

BASE_URL = "http://localhost:8765"
HEADERS = {"Origin": BASE_URL, "Content-Type": "application/json"}
ROOT = "/api/v1/laboratories"
CONFIG = {
    "schema_version": 1,
    "system": "transition",
    "coverage": 1,
    "stake_style": "bold",
    "capital": 2000,
    "goal": 2800,
    "prizes": [80, 8, 4, 2, 1],
    "window_start": "2025-09-02 05:10",
    "window_end": "2026-09-25 18:20",
}


def make_app(tmp_path, lab_data, *, quota_bytes=None):
    settings = replace(Settings.from_environment(), data_dir=tmp_path, port=8765)
    if quota_bytes is not None:
        settings = replace(settings, quota_bytes=quota_bytes, quota_explicit=True)
    return create_app(settings, catalog_loader=lambda _settings: lab_data)


def post(client, name="Manual test", config=CONFIG, **extra):
    return client.post(ROOT, json={"name": name, "config": config, **extra}, headers=HEADERS)


def test_create_manual_laboratory_returns_canonical_definition(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        response = post(client)

    assert response.status_code == 201, response.text
    definition = response.json()
    assert set(definition) == {"schema_version", "id", "name", "reference_id", "config"}
    assert str(uuid.UUID(definition["id"])) == definition["id"]
    assert definition["name"] == "Manual test"
    assert definition["reference_id"] is None
    assert definition["config"] == CONFIG


def test_list_detail_delete_and_recreate_use_canonical_snapshots(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        first = post(client, "Café").json()
        listing = client.get(ROOT)
        assert listing.status_code == 200
        page = listing.json()
        assert (page["total"], page["offset"], page["limit"]) == (15, 0, 20)
        assert page["items"][0] == first
        tail = client.get(ROOT, params={"offset": 14, "limit": 1}).json()["items"]
        assert tail == page["items"][14:15]
        assert tail[0]["reference_id"] is not None
        assert client.get(ROOT, params={"offset": 2**63 - 1}).json()["items"] == []
        detail = client.get(f"{ROOT}/{first['id']}")
        assert detail.json() == {
            "definition": first,
            "owned_run_count": 0,
            "owned_session_count": 0,
        }
        deleted = client.request(
            "DELETE", f"{ROOT}/{first['id']}", json={"confirmed_run_count": 0}, headers=HEADERS
        )
        assert deleted.status_code == 200
        assert set(deleted.json()) == {
            "id",
            "name",
            "definition_bytes",
            "owned_run_count",
            "owned_session_count",
        }
        assert deleted.json()["id"] == first["id"]
        assert client.get(f"{ROOT}/{first['id']}").status_code == 404
        assert (
            client.request(
                "DELETE",
                f"{ROOT}/{first['id']}",
                json={"confirmed_run_count": 0},
                headers=HEADERS,
            ).status_code
            == 404
        )
        replacement = post(client, "CAFÉ").json()
        assert replacement["id"] != first["id"]


@pytest.mark.parametrize(
    "query",
    [
        {"offset": -1},
        {"offset": 2**63},
        {"offset": "1.5"},
        {"limit": 0},
        {"limit": 101},
        {"limit": "x"},
    ],
)
def test_list_query_paging_is_bounded_and_integer_only(tmp_path, lab_data, query):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get(ROOT, params=query).status_code == 422


def test_root_and_nested_extra_fields_are_rejected_without_writes(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        for body in (
            {"name": "Manual", "config": CONFIG, "id": str(uuid.uuid4())},
            {"name": "Manual", "config": CONFIG, "reference_id": "seed"},
            {"name": "Manual", "config": CONFIG | {"unexpected": True}},
            {"name": "Manual", "config": CONFIG | {"schema_version": True}},
        ):
            assert client.post(ROOT, json=body, headers=HEADERS).status_code == 422
        assert client.get(ROOT).json()["total"] == 14


@pytest.mark.parametrize(
    "name,config",
    [
        (" trimmed ", CONFIG),
        ("", CONFIG),
        ("x\ny", CONFIG),
        ("x" * 121, CONFIG),
        ("é" * 61, CONFIG),
        ("Manual", CONFIG | {"system": "unsupported"}),
        ("Manual", CONFIG | {"coverage": True}),
        ("Manual", CONFIG | {"capital": 2000.0}),
        ("Manual", CONFIG | {"prizes": [80, 8, 4, 2]}),
        ("Manual", CONFIG | {"window_start": "2025-02-30 05:10"}),
    ],
)
def test_invalid_name_or_domain_config_is_422(tmp_path, lab_data, name, config):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert post(client, name, config).status_code == 422
        assert client.get(ROOT).json()["total"] == 14


def test_duplicate_casefold_and_quota_fail_with_conflict_without_mutation(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert post(client, "Duplica").status_code == 201
        assert post(client, "DUPLICA").status_code == 409
        assert client.get(ROOT).json()["total"] == 15

    quota_app = make_app(tmp_path / "quota", lab_data, quota_bytes=1)
    with TestClient(quota_app, base_url=BASE_URL) as client:
        assert post(client, "Quota").status_code == 409
        assert client.get(ROOT).json()["total"] == 14


def test_unknown_definition_get_and_delete_are_404(tmp_path, lab_data):
    identifier = str(uuid.uuid4())
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        assert client.get(f"{ROOT}/{identifier}").status_code == 404
        deleted = client.request(
            "DELETE",
            f"{ROOT}/{identifier}",
            json={"confirmed_run_count": 0},
            headers=HEADERS,
        )
        assert deleted.status_code == 404
        assert client.get(ROOT).json()["total"] == 14


def test_delete_confirmation_is_required_strict_and_extra_free(tmp_path, lab_data):
    with TestClient(make_app(tmp_path, lab_data), base_url=BASE_URL) as client:
        definition = post(client).json()
        path = f"{ROOT}/{definition['id']}"
        for body in (
            {},
            {"confirmed_run_count": True},
            {"confirmed_run_count": 0.0},
            {"confirmed_run_count": "0"},
            {"confirmed_run_count": None},
            {"confirmed_run_count": 0, "extra": 1},
            {"confirmed_run_count": 2**63},
        ):
            response = client.request("DELETE", path, json=body, headers=HEADERS)
            assert response.status_code == 422
        assert client.get(path).status_code == 200


def test_delete_stale_count_is_conflict_and_preserves_owned_rows(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        definition = post(client).json()
        run_id = str(uuid.uuid4())
        with connection(app.state.repo.path) as db:
            db.execute(
                "INSERT INTO reference_lab_runs "
                "(id,lab_id,contract_version,created_at,metadata_json,result_json,"
                "owner_laboratory_id) VALUES (?, ?, 1, '2025-01-01T00:00:00.000000Z', "
                "'{}', '{}', ?)",
                (run_id, definition["id"], definition["id"]),
            )
            db.execute("INSERT INTO reference_lab_sessions VALUES (?, 0, '{}')", (run_id,))
            db.commit()
        path = f"{ROOT}/{definition['id']}"
        assert client.get(path).json()["owned_run_count"] == 1
        stale = client.request("DELETE", path, json={"confirmed_run_count": 0}, headers=HEADERS)
        assert stale.status_code == 409
        assert client.get(path).json()["owned_session_count"] == 1
        with connection(app.state.repo.path) as db:
            run_count = db.execute(
                "SELECT count(*) FROM reference_lab_runs WHERE id=?", (run_id,)
            ).fetchone()[0]
            assert run_count == 1


def test_confirmed_delete_cascades_only_owned_run_and_sessions(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        definition = post(client).json()
        owned_id, legacy_id = str(uuid.uuid4()), str(uuid.uuid4())
        with connection(app.state.repo.path) as db:
            for run_id, owner in ((owned_id, definition["id"]), (legacy_id, None)):
                db.execute(
                    "INSERT INTO reference_lab_runs "
                    "(id,lab_id,contract_version,created_at,metadata_json,result_json,"
                    "owner_laboratory_id) VALUES (?, ?, 1, '2025-01-01T00:00:00.000000Z', "
                    "'{}', '{}', ?)",
                    (run_id, definition["id"], owner),
                )
                db.execute("INSERT INTO reference_lab_sessions VALUES (?, 0, '{}')", (run_id,))
            db.commit()
        result = client.request(
            "DELETE",
            f"{ROOT}/{definition['id']}",
            json={"confirmed_run_count": 1},
            headers=HEADERS,
        )
        assert result.status_code == 200
        assert result.json()["owned_run_count"] == 1
        assert result.json()["owned_session_count"] == 1
        with connection(app.state.repo.path) as db:
            assert db.execute(
                "SELECT id,owner_laboratory_id FROM reference_lab_runs"
            ).fetchall() == [(legacy_id, None)]
            assert db.execute("SELECT run_id FROM reference_lab_sessions").fetchall() == [
                (legacy_id,)
            ]


def test_corrupt_definition_reads_and_delete_fail_closed(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL) as client:
        definition = post(client).json()
        with connection(app.state.repo.path) as db:
            db.execute(
                "UPDATE laboratory_definitions SET name_key='corrupt' WHERE id=?",
                (definition["id"],),
            )
            db.commit()
        path = f"{ROOT}/{definition['id']}"
        assert client.get(path).status_code == 409
        deleted = client.request("DELETE", path, json={"confirmed_run_count": 0}, headers=HEADERS)
        assert deleted.status_code == 409
        with connection(app.state.repo.path) as db:
            count = db.execute(
                "SELECT count(*) FROM laboratory_definitions WHERE id=?", (definition["id"],)
            ).fetchone()[0]
            assert count == 1


def test_declared_content_length_with_thousands_of_digits_is_bounded(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    huge = "9" * 4301
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        for path in (
            ROOT,
            f"{ROOT}/",
            "/api/v1/runs",
            "/api/v1/reference-labs/seed/runs",
        ):
            response = client.post(path, content=b"{}", headers={**HEADERS, "Content-Length": huge})
            assert response.status_code == 413, response.text
        history = client.post(
            "/api/v1/history", content=b"{}", headers={**HEADERS, "Content-Length": huge}
        )
        assert history.status_code == 413, history.text
        assert client.get(ROOT).json()["total"] == 14
        assert client.get("/api/v1/runs").json()["total"] == 0


def test_collection_body_cap_handles_zero_padding_and_exact_actual_bytes(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    valid = json.dumps({"name": "Manual test", "config": CONFIG}, separators=(",", ":")).encode()

    def padded(size):
        return valid + b" " * (size - len(valid))

    with TestClient(app, base_url=BASE_URL) as client:
        under_limit = json.dumps(
            {"name": "Manual short", "config": CONFIG}, separators=(",", ":")
        ).encode()
        leading_zero_under_limit = client.post(
            ROOT,
            content=under_limit,
            headers={**HEADERS, "Content-Length": "0" * 4300 + str(len(under_limit))},
        )
        assert leading_zero_under_limit.status_code == 201, leading_zero_under_limit.text
        accepted = client.post(
            ROOT,
            content=padded(65536),
            headers={**HEADERS, "Content-Length": "0" * 4300 + "65536"},
        )
        assert accepted.status_code == 201, accepted.text
        rejected = client.post(
            ROOT,
            content=b"{}",
            headers={**HEADERS, "Content-Length": "0" * 4300 + "65537"},
        )
        assert rejected.status_code == 413
        zero_only = client.post(
            ROOT, content=b"{}", headers={**HEADERS, "Content-Length": "0" * 4301}
        )
        assert zero_only.status_code == 422
        oversized_domain_value = client.post(
            ROOT,
            json={"name": "x" * 121, "config": CONFIG},
            headers=HEADERS,
        )
        assert oversized_domain_value.status_code == 422
        assert client.get(ROOT).json()["total"] == 16


def test_collection_content_length_rejects_non_ascii_and_malformed_headers(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    invalid_headers = (
        [(b"content-length", b"-1")],
        [(b"content-length", b"not-a-number")],
        [(b"content-length", b"\xd9\xa1")],
        [(b"content-length", b"1"), (b"content-length", b"2")],
    )

    async def request_with(headers):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "path": ROOT,
            "raw_path": ROOT.encode(),
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "headers": [
                (b"host", b"localhost:8765"),
                (b"origin", BASE_URL.encode()),
                (b"content-type", b"application/json"),
                *headers,
            ],
            "server": ("localhost", 8765),
            "client": ("127.0.0.1", 50000),
            "state": {},
        }
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)
        return sent[0]["status"]

    for headers in invalid_headers:
        assert asyncio.run(request_with(headers)) == 413


def test_collection_body_cap_covers_exact_route_slashes_and_streamed_bytes(tmp_path, lab_data):
    app = make_app(tmp_path, lab_data)
    body = b'{"name":"' + b"x" * 100 + b'","config":{}}'

    def padded(size):
        return body + b" " * (size - len(body))

    with TestClient(app, base_url=BASE_URL) as client:
        exact = client.post(ROOT, content=padded(65536), headers=HEADERS)
        assert exact.status_code == 422
        assert client.post(ROOT, content=padded(65537), headers=HEADERS).status_code == 413
        declared = {**HEADERS, "Content-Length": "65537"}
        assert client.post(f"{ROOT}/", content=b"{}", headers=declared).status_code == 413
        small_header = {**HEADERS, "Content-Length": "2"}
        streamed = (piece for piece in (b"{" + b" " * 40000, b" " * 30000, b"}"))
        assert client.post(ROOT, content=streamed, headers=small_header).status_code == 413
        assert client.get(ROOT).json()["total"] == 14

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": ROOT,
        "raw_path": ROOT.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [
            (b"host", b"localhost:8765"),
            (b"origin", BASE_URL.encode()),
            (b"content-type", b"application/json"),
        ],
        "server": ("localhost", 8765),
        "client": ("127.0.0.1", 50000),
        "state": {},
    }
    sent = []

    async def drive():
        chunks = [b" " * 30000, b" " * 30000, b" " * 30000]

        async def receive():
            chunk = chunks.pop(0) if chunks else b""
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)

    asyncio.run(drive())
    assert sent[0]["status"] == 413


def test_unexpected_storage_failure_uses_safe_server_error(tmp_path, lab_data, monkeypatch):
    app = make_app(tmp_path, lab_data)
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:

        def fail(*_args, **_kwargs):
            raise RuntimeError("C:/private/database-secret.db")

        monkeypatch.setattr(laboratories_api, "list_laboratory_definitions", fail)
        response = client.get(ROOT)
        assert response.status_code == 500
        assert "database-secret" not in response.text
