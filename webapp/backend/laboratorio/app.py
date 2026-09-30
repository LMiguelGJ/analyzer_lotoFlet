"""Local-only API factory; no database or worker is created at import time."""

import re
import socket
import sys
import threading
import webbrowser
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from laboratorio.api import catalog, configurations, experiments, queue
from laboratorio.api import settings as settings_api
from laboratorio.engine.adapter import open_lab_data
from laboratorio.jobs.queue import JobQueue
from laboratorio.settings import Settings
from laboratorio.storage.database import initialize_database
from laboratorio.storage.repository import Repository

_HOST = re.compile(r"(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?\Z")
_OWNERS_LOCK = threading.Lock()
_SPA_PATH = re.compile(
    r"/(?:|experimentos(?:/nuevo|/[^/]+(?:/comparacion)?)?|configuraciones|ajustes)\Z"
)


class QueueLifecycle(Protocol):
    def start(self) -> None: ...

    def shutdown(self) -> None: ...

    @property
    def is_stopped(self) -> bool: ...


# None reserves the database while startup constructs its queue.
_OWNED_DATABASES: dict[str, QueueLifecycle | None] = {}


def _valid_host(value: str, port: int) -> bool:
    match = _HOST.fullmatch(value)
    return bool(match and (match[2] is None or int(match[2]) == port))


def _valid_origin(value: str, host: str) -> bool:
    return value == f"http://{host}"


def create_app(
    settings: Settings,
    *,
    catalog_loader=open_lab_data,
    queue_factory: Callable[[Path, Settings], QueueLifecycle] = JobQueue,
    serve_frontend: bool = False,
) -> FastAPI:
    if settings.host != "127.0.0.1":
        raise ValueError("the local API must bind to 127.0.0.1")

    dist = settings.frontend_dist.resolve()
    index = (dist / "index.html").resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if serve_frontend and (not index.is_relative_to(dist) or not index.is_file()):
            raise RuntimeError(
                "Frontend build missing or unsafe: run npm ci and npm run build "
                "in webapp/frontend before starting the launcher."
            )
        key = str(settings.database_path.resolve())
        with _OWNERS_LOCK:
            if key in _OWNED_DATABASES:
                previous = _OWNED_DATABASES[key]
                if previous is None or not previous.is_stopped:
                    raise RuntimeError("a queue already owns this database in this process")
            _OWNED_DATABASES[key] = None
        jobs = None
        try:
            initialize_database(settings.database_path)
            repo = Repository(settings.database_path)
            data = catalog_loader(settings)  # fail startup rather than fabricate catalog data
            jobs = queue_factory(settings.database_path, settings)
            with _OWNERS_LOCK:
                _OWNED_DATABASES[key] = jobs
            jobs.start()  # recover interrupted and held jobs before serving requests
            app.state.repo = repo
            app.state.jobs = jobs
            app.state.data = data
            app.state.settings = settings
            yield
        finally:
            stopped = jobs is None
            try:
                if jobs is not None:
                    jobs.shutdown()  # a failure must retain ownership until the thread exits
                    stopped = True
            finally:
                if stopped:
                    with _OWNERS_LOCK:
                        if key in _OWNED_DATABASES and _OWNED_DATABASES[key] is jobs:
                            del _OWNED_DATABASES[key]

    app = FastAPI(title="Laboratorio Quiniela 80", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        hosts = request.headers.getlist("host")
        origins = request.headers.getlist("origin")
        host = hosts[0] if len(hosts) == 1 else ""
        if not _valid_host(host, settings.port):
            return JSONResponse({"detail": "local Host required"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "cross-site requests denied"}, status_code=403)
        if origins and (len(origins) != 1 or not _valid_origin(origins[0], host)):
            return JSONResponse({"detail": "same-origin required"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and not origins:
            return JSONResponse({"detail": "Origin required for mutation"}, status_code=403)
        return await call_next(request)

    for router in (
        catalog.router,
        experiments.router,
        configurations.router,
        queue.router,
        settings_api.router,
    ):
        app.include_router(router, prefix="/api/v1")

    if serve_frontend:

        @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def frontend(request: Request, path: str):
            # Reject encodings rather than guessing how a proxy/browser normalizes a path.
            raw_path = request.scope.get("raw_path", b"")
            if (
                b"%" in raw_path
                or b"\\" in raw_path
                or "\\" in path
                or "." in path.split("/")
                or ".." in path.split("/")
            ):
                return JSONResponse({"detail": "not found"}, status_code=404)
            url_path = "/" + path
            if url_path.startswith("/api"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            if _SPA_PATH.fullmatch(url_path):
                return FileResponse(index)
            if not path.startswith("assets/") or path.endswith("/"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            asset = (dist / path).resolve()
            if not asset.is_relative_to(dist) or not asset.is_file():
                return JSONResponse({"detail": "not found"}, status_code=404)
            return FileResponse(asset)

    return app


class BrowserServer(uvicorn.Server):
    """Open the browser only after this server's lifespan and listening socket are ready."""

    def __init__(self, config: uvicorn.Config, *, browser_open=webbrowser.open):
        super().__init__(config)
        self._browser_open = browser_open
        self._browser_opened = False

    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started and not self.should_exit and not self._browser_opened:
            self._browser_opened = True
            try:
                self._browser_open(f"http://127.0.0.1:{self.config.port}/")
            except Exception as exc:
                print(
                    f"Browser could not open ({type(exc).__name__}); visit the URL manually.",
                    file=sys.stderr,
                )


def run_production(
    settings: Settings, *, browser_open=webbrowser.open, server_factory=BrowserServer
) -> None:
    """Reserve the loopback port atomically; own one foreground server until Ctrl+C."""
    if settings.host != "127.0.0.1":
        raise ValueError("the local API must bind to 127.0.0.1")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((settings.host, settings.port))
            listener.listen(128)
        except OSError as exc:
            raise RuntimeError(
                f"Port {settings.port} is occupied on 127.0.0.1. Close the other instance "
                "or change LABORATORIO_PORT; nothing was opened."
            ) from exc
        app = create_app(settings, serve_frontend=True)
        config = uvicorn.Config(app, host=settings.host, port=settings.port)
        server = server_factory(config, browser_open=browser_open)
        server.run(sockets=[listener])
        if not server.started:
            raise RuntimeError(
                "Server did not start; check the build and frozen input errors above."
            )


def main():
    try:
        run_production(Settings.from_environment())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Laboratorio could not start: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
