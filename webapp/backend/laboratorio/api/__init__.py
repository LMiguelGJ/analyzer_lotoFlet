"""Versioned HTTP resources and presentation helpers."""

from fastapi import Request
from pydantic import BaseModel, ConfigDict


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def repo(request: Request):
    return request.app.state.repo


def history(request: Request):
    return request.app.state.history
