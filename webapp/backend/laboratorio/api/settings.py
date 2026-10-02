"""Effective quota preference and read-only local storage measurements."""

import re
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import field_validator

from laboratorio.api import StrictBody, repo
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256
from laboratorio.storage.repository import QuotaBelowUsage, QuotaReadOnly

router = APIRouter()
_QUOTA_DECIMAL = re.compile(r"[1-9][0-9]{0,18}\Z")


class QuotaPreference(StrictBody):
    quota_bytes: str

    @field_validator("quota_bytes", mode="before")
    @classmethod
    def exact_decimal_bytes(cls, value):
        if not isinstance(value, str) or _QUOTA_DECIMAL.fullmatch(value) is None:
            raise ValueError("quota_bytes must be a canonical ASCII decimal string of bytes")
        if int(value) > 2**63 - 1:
            raise ValueError("quota_bytes exceeds the SQLite signed 64-bit maximum")
        return value


@router.get("/settings")
def read_settings(request: Request):
    settings = request.app.state.settings
    repository = repo(request)
    effective = repository.effective_quota(
        settings.quota_bytes, quota_explicit=settings.is_quota_explicit
    )
    status = repository.quota_status(
        settings.quota_bytes, quota_explicit=settings.is_quota_explicit
    )
    return {
        "storage": {
            **asdict(status),
            "sqlite_bytes": status.sqlite_bytes,
            "warning": status.warning,
            "logical_used_bytes_exact": str(status.logical_used_bytes),
            "profile_artifact_bytes_exact": str(status.profile_artifact_bytes),
            "dataset_artifact_bytes_exact": str(status.dataset_artifact_bytes),
            "admission_logical_bytes_exact": str(status.admission_logical_bytes),
        },
        "quota": {
            "effective_bytes": str(effective.effective_bytes),
            "persisted_bytes": (
                str(effective.persisted_bytes) if effective.persisted_bytes is not None else None
            ),
            "source": effective.source,
            "writable": effective.writable,
        },
        "sources": {
            "history_id": settings.history_path.name,
            "history_sha256": HISTORY_SHA256,
            "rankings_id": settings.rankings_path.name,
            "rankings_sha256": RANKINGS_SHA256,
            "code_version": request.app.version,
        },
        "connection": {
            "host": settings.host,
            "port": settings.port,
            "version": request.app.version,
        },
    }


@router.put("/settings")
def update_settings(body: QuotaPreference, request: Request):
    settings = request.app.state.settings
    try:
        repo(request).set_quota_preference(
            int(body.quota_bytes), quota_explicit=settings.is_quota_explicit
        )
    except QuotaReadOnly as exc:
        raise HTTPException(409, "environment quota is read-only") from exc
    except QuotaBelowUsage as exc:
        raise HTTPException(409, "quota cannot be below current logical usage") from exc
    return read_settings(request)
