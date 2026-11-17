"""Versioned HTTP resources and presentation helpers."""

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def repo(request: Request):
    return request.app.state.repo


def history(request: Request):
    return request.app.state.history


def require_chance_express(request: Request) -> None:
    """Dependency for endpoints that only know Loteka (history import, reference labs)."""
    catalog = request.app.state.lists
    active = catalog.active()
    if active.id != "chance_express":
        raise HTTPException(
            409,
            f"La lista activa es «{active.name}» y esta función todavía solo funciona con "
            "«Loteka Chance Express». Cámbiala en Ajustes.",
        )
