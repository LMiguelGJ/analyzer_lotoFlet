"""Local-only API factory; no database is created at import time."""

import json
import re
import socket
import sys
import threading
import unicodedata
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from laboratorio.api import settings as settings_api
from laboratorio.api.game_profiles import router as game_profiles_router
from laboratorio.api.history import router as history_router
from laboratorio.api.history_sources import router as history_sources_router
from laboratorio.api.laboratories import router as laboratories_router
from laboratorio.api.laboratory_runs import router as laboratory_runs_router
from laboratorio.api.reference_labs import router as reference_labs_router
from laboratorio.api.runs import router as runs_router
from laboratorio.engine.active_history import HistoryCatalog
from laboratorio.engine.adapter import open_lab_data
from laboratorio.settings import Settings
from laboratorio.storage.database import initialize_database
from laboratorio.storage.repository import Repository

_REFERENCE_RUNS_PATH = re.compile(r"/api/v1/reference-labs/[^/]+/runs")
_OWNED_RUNS_PATH = re.compile(r"/api/v1/laboratories/[^/]+/runs")
_LABORATORIES_COLLECTION_PATH = re.compile(r"/api/v1/laboratories/?")
_V2_PROFILES_COLLECTION_PATH = re.compile(r"/api/v2/game-profiles/?")
_V2_HISTORY_SOURCES_POST_PATH = re.compile(
    r"/api/v2/history-sources(?:/(?:preview|included/(?:preview|confirm)))?/?"
)
_HOST = re.compile(r"(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?\Z")


def _valid_host(value: str, port: int) -> bool:
    match = _HOST.fullmatch(value)
    return bool(match and (match[2] is None or int(match[2]) == port))


def _valid_origin(value: str, host: str) -> bool:
    return value == f"http://{host}"


def _decimal_exceeds(value: str, limit: int) -> bool:
    normalized = "".join(str(unicodedata.decimal(char)) for char in value).lstrip("0") or "0"
    bound = str(limit)
    return len(normalized) > len(bound) or (len(normalized) == len(bound) and normalized > bound)


class _DuplicateJSONKey(ValueError):
    """A bounded v2 request has ambiguous duplicate object keys."""


def _unique_json_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise _DuplicateJSONKey
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise ValueError("nonfinite JSON number")


def create_app(
    settings: Settings,
    *,
    catalog_loader=open_lab_data,
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
        initialize_database(settings.database_path)
        repo = Repository(settings.database_path)
        data = catalog_loader(settings)  # fail startup rather than fabricate catalog data
        app.state.repo = repo
        app.state.data = data
        app.state.history = HistoryCatalog(repo, data, settings)
        app.state.settings = settings
        app.state.rankings_cache = {}
        app.state.rankings_lock = threading.Lock()
        app.state.reference_lab_lock = threading.RLock()
        yield

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
        run_post = (
            request.url.path == "/api/v1/runs"
            or _REFERENCE_RUNS_PATH.fullmatch(request.url.path)
            or _OWNED_RUNS_PATH.fullmatch(request.url.path)
        )
        profile_post = bool(_V2_PROFILES_COLLECTION_PATH.fullmatch(request.url.path))
        history_source_post = bool(_V2_HISTORY_SOURCES_POST_PATH.fullmatch(request.url.path))
        strict_json_post = profile_post or history_source_post
        bounded_post = (
            run_post
            or _LABORATORIES_COLLECTION_PATH.fullmatch(request.url.path)
            or profile_post
            or history_source_post
        )
        if request.method == "POST" and bounded_post:
            byte_limit = 64 * 1024 * 1024 + 64 * 1024 if history_source_post else 64 * 1024
            lengths = request.headers.getlist("content-length")
            invalid_length = len(lengths) > 1 or (
                lengths
                and (
                    not lengths[0].isascii()
                    or not lengths[0].isdecimal()
                    or _decimal_exceeds(lengths[0], byte_limit)
                )
            )
            if invalid_length:
                return JSONResponse(
                    {"detail": "La solicitud supera el límite de 64 KiB."}, status_code=413
                )
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > byte_limit:
                    return JSONResponse(
                        {"detail": "La solicitud supera el límite de 64 KiB."}, status_code=413
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
            if strict_json_post:
                try:
                    json.loads(
                        request._body,
                        object_pairs_hook=_unique_json_pairs,
                        parse_constant=_reject_json_constant,
                    )
                except _DuplicateJSONKey:
                    return JSONResponse(
                        {"detail": "La solicitud contiene claves JSON duplicadas."}, status_code=422
                    )
                except (ValueError, RecursionError):
                    return JSONResponse(
                        {"detail": "La solicitud JSON no es válida."}, status_code=422
                    )
        if request.method == "POST" and request.url.path == "/api/v1/history":
            byte_limit = 32 * 1024 * 1024
            lengths = request.headers.getlist("content-length")
            if any(value.isdecimal() and _decimal_exceeds(value, byte_limit) for value in lengths):
                return JSONResponse(
                    {"detail": "El archivo supera el límite de 32 MiB."}, status_code=413
                )
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > byte_limit:
                    return JSONResponse(
                        {"detail": "El archivo supera el límite de 32 MiB."}, status_code=413
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    app.include_router(settings_api.router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(reference_labs_router, prefix="/api/v1")
    app.include_router(laboratories_router, prefix="/api/v1")
    app.include_router(laboratory_runs_router, prefix="/api/v1")
    app.include_router(game_profiles_router, prefix="/api/v2")
    app.include_router(history_sources_router, prefix="/api/v2")

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
            if not path.startswith("assets/"):
                # History fallback: the router owns every page path, including retired
                # ones that redirect. Anything that looks like a file is a real 404.
                if "." in path.rsplit("/", 1)[-1]:
                    return JSONResponse({"detail": "not found"}, status_code=404)
                return FileResponse(index)
            if path.endswith("/"):
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
