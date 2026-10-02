"""Persistent local-agent bearer credential; deliberately contains no application data."""

import os
import re
import secrets
import tempfile
from pathlib import Path

_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_MAX_CREDENTIAL_BYTES = 128


def _read_token(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(_MAX_CREDENTIAL_BYTES + 1)
    if len(raw) > _MAX_CREDENTIAL_BYTES:
        raise ValueError("persisted agent credential is corrupt")
    try:
        token = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("persisted agent credential is corrupt") from exc
    if _TOKEN.fullmatch(token) is None:
        raise ValueError("persisted agent credential is corrupt")
    return token


def load_or_create_token(path: Path) -> str:
    """Read a valid persisted token or atomically publish a new winner; fail closed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _read_token(path)
    except FileNotFoundError:
        pass

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="") as stream:
            token = secrets.token_urlsafe(32)
            if _TOKEN.fullmatch(token) is None:
                raise ValueError("generated agent credential is invalid")
            stream.write(token)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Same-directory hard-link creation is atomic and exclusive; it never
            # replaces another creator's final credential.
            os.link(temporary_path, path)
        except FileExistsError:
            pass
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass

    # A racing creator may have won publication. Always return and validate the
    # stable final file rather than returning our candidate token.
    return _read_token(path)
