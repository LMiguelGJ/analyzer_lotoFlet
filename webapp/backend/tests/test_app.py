"""Production entrypoint and static delivery contracts with bounded local sockets."""

import asyncio
import socket
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from urllib.request import urlopen

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from laboratorio.app import create_app
from laboratorio.settings import Settings


@pytest.fixture
def local_settings(tmp_path):
    root = tmp_path / "folder with spaces"
    dist = root / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/main.js"></script>', encoding="utf-8")
    (dist / "assets" / "main.js").write_text("console.log('ready')", encoding="utf-8")
    return Settings(root / "data", root / "history", root / "rankings", dist)


def _client(settings):
    def catalog(_):
        return SimpleNamespace(
            history=SimpleNamespace(labels=("2025-01-01 05:10",), sha256="a" * 64),
            rankings=SimpleNamespace(row_ids=(0,), path="rankings.npz"),
        )

    return TestClient(
        create_app(settings, catalog_loader=catalog, serve_frontend=True),
        base_url="http://127.0.0.1:8765",
    )


# B-SET-011
# B-SET-012 is covered by the route-specific direct-navigation tests below.
def test_production_static_spa_and_api_isolation(local_settings):
    with _client(local_settings) as client:
        for route in (
            "/",
            "/experimentos",
            "/experimentos/nuevo",
            "/experimentos/test-id",
            "/experimentos/test-id/comparacion",
            "/configuraciones",
            "/ajustes",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert response.headers["content-type"].startswith("text/html")
            assert "main.js" in response.text
        asset = client.get("/assets/main.js")
        assert asset.status_code == 200
        assert asset.headers["content-type"].startswith("text/javascript")
        assert asset.text == "console.log('ready')"
        assert client.head("/assets/main.js").status_code == 200
        assert client.get("/assets/absent.js").status_code == 404
        assert client.get("/unknown.js").status_code == 404
        assert client.get("/api/v1/does-not-exist").status_code == 404
        assert (
            client.get("/api/v1/does-not-exist")
            .headers["content-type"]
            .startswith("application/json")
        )
        assert client.get("/api/v1/queue").status_code == 200
        assert client.get("/api/v1/catalog").status_code == 200


# B-SET-012
def test_profile_creation_direct_navigation_serves_only_the_spa_route(local_settings):
    expected = (local_settings.frontend_dist / "index.html").read_text(encoding="utf-8")
    with _client(local_settings) as client:
        for method in (client.get, client.head):
            response = method("/experimentos/nuevo/perfil")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            if method == client.get:
                assert response.text == expected
        for path in (
            "/experimentos/nuevo/perfiles",
            "/experimentos/nuevo/perfil/child",
            "/experimentos/nuevo/other",
            "/experimentos/other/perfil",
        ):
            for method in (client.get, client.head):
                assert method(path).status_code == 404, path


# B-SET-012
def test_batch_session_direct_navigation_serves_only_the_spa_route(local_settings):
    expected = (local_settings.frontend_dist / "index.html").read_text(encoding="utf-8")
    with _client(local_settings) as client:
        for path in (
            "/experimentos/nuevo/sesion",
            "/experimentos/nuevo/sesion?draft=session",
        ):
            for method in (client.get, client.head):
                response = method(path)
                assert response.status_code == 200, path
                assert response.headers["content-type"].startswith("text/html")
                if method == client.get:
                    assert response.text == expected
        for path in (
            "/experimentos/nuevo/sesiones",
            "/experimentos/nuevo/sesion/child",
            "/experimentos/nuevo/sesion-extra",
            "/experimentos/other/sesion",
            "/api/v1/does-not-exist",
            "/assets/absent.js",
        ):
            for method in (client.get, client.head):
                assert method(path).status_code == 404, path


# B-SET-012
def test_datos_direct_navigation_serves_only_the_spa_route(local_settings):
    expected = (local_settings.frontend_dist / "index.html").read_text(encoding="utf-8")
    with _client(local_settings) as client:
        response = client.get("/datos")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.text == expected
        for path in ("/datos/child", "/datos-extra"):
            assert client.get(path).status_code == 404


# B-SET-013
def test_static_never_leaks_outside_build(local_settings, tmp_path):
    secret = tmp_path / "private.txt"
    secret.write_text("not public", encoding="utf-8")
    dist = local_settings.frontend_dist
    (dist / "assets" / "escape.txt").symlink_to(secret)
    with _client(local_settings) as client:
        for route in (
            "/assets/escape.txt",
            "/assets/../private.txt",
            "/assets/%2e%2e/private.txt",
            "/assets/%5cprivate.txt",
            "/assets/%252e%252e/private.txt",
            "/data/laboratorio.db",
            "/private.txt",
        ):
            response = client.get(route)
            assert response.status_code in (400, 404), route
            assert "not public" not in response.text
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
        assert client.get("/", headers={"Origin": "http://evil.example"}).status_code == 403
        assert client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


# B-SET-014
def test_missing_build_fails_production_startup_but_api_factory_remains_usable(local_settings):
    local_settings.frontend_dist.joinpath("index.html").unlink()
    with pytest.raises(RuntimeError, match="npm run build"):
        with _client(local_settings):
            pass
    with TestClient(
        create_app(local_settings, catalog_loader=lambda _: object()),
        base_url="http://127.0.0.1:8765",
    ) as client:
        assert client.get("/api/v1/queue").status_code == 200


# B-SET-015
def test_settings_paths_are_absolute_and_cwd_independent(local_settings, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LABORATORIO_HISTORY", raising=False)
    monkeypatch.delenv("LABORATORIO_RANKINGS", raising=False)
    settings = Settings.from_environment()
    assert settings.frontend_dist.is_absolute()
    assert settings.history_path.is_absolute()
    assert settings.rankings_path.is_absolute()
    assert settings.frontend_dist == Path(__file__).resolve().parents[2] / "frontend" / "dist"


# B-SET-016
def test_browser_only_after_own_server_started_and_once(local_settings, monkeypatch):
    from laboratorio.app import BrowserServer

    opened = []
    state = {"ready": False}

    async def startup(self, sockets=None):
        self.started = state["ready"]

    monkeypatch.setattr(uvicorn.Server, "startup", startup)
    server = BrowserServer(
        uvicorn.Config(create_app(local_settings), port=8765), browser_open=opened.append
    )
    asyncio.run(server.startup())
    assert opened == []
    state["ready"] = True
    asyncio.run(server.startup())
    asyncio.run(server.startup())
    assert opened == ["http://127.0.0.1:8765/"]


# B-SET-017
def test_port_busy_never_creates_or_opens_server(local_settings):
    from laboratorio.app import run_production

    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        settings = replace(local_settings, port=occupied.getsockname()[1])
        with pytest.raises(RuntimeError, match="occupied"):
            run_production(settings, browser_open=lambda _: pytest.fail("opened other instance"))


# B-SET-018
def test_frozen_inputs_fail_before_browser_opens(local_settings):
    with pytest.raises(ValueError, match="file not found"):
        with TestClient(create_app(local_settings, serve_frontend=True)):
            pass


# B-SET-018
def test_corrupt_frozen_input_refuses_startup(local_settings):
    local_settings.history_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        with TestClient(create_app(local_settings, serve_frontend=True)):
            pass


# B-SET-019
def test_real_uvicorn_opens_once_after_owned_listener_is_ready():
    from laboratorio.app import BrowserServer

    app = FastAPI()

    @app.get("/")
    def home():
        return {"ready": True}

    opened = []
    ready = Event()

    def open_browser(url):
        opened.append(url)
        ready.set()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = BrowserServer(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"),
            browser_open=open_browser,
        )
        thread = Thread(target=server.run, kwargs={"sockets": [listener]})
        try:
            thread.start()
            assert ready.wait(5)
            assert opened == [f"http://127.0.0.1:{port}/"]
            with urlopen(opened[0], timeout=5) as response:
                assert response.status == 200
                assert response.read() == b'{"ready":true}'
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()


# B-SET-020
def test_windows_launcher_has_foreground_and_failure_guards():
    launcher = Path(__file__).resolve().parents[3] / "iniciar-laboratorio.bat"
    text = launcher.read_text(encoding="utf-8").lower()
    assert 'pushd "%~dp0' in text
    assert "popd" in text
    assert "frontend\\dist\\index.html" in text
    assert "npm run build" in text
    assert 'set "python=py"' in text
    assert 'set "python_args=-3"' in text
    assert '"%python%" %python_args% -b -m laboratorio.app' in text
    assert 'set "exit_code=%errorlevel%"' in text
    assert "pause" in text
    assert "start " not in text and "pip install" not in text
