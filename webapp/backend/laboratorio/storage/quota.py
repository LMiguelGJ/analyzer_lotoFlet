"""Measured experiment budget and conservative disk admission, without cleanup."""

import shutil
from dataclasses import dataclass
from pathlib import Path

LOGICAL_MARGIN_BYTES = 1024**2  # reserve for the next run's unknown serialized result
DISK_MARGIN_BYTES = 64 * 1024**2  # WAL, journal, temporary writes and metadata headroom


class QuotaExceeded(RuntimeError):
    """A new write or calculation cannot be admitted with the measured headroom."""


@dataclass(frozen=True)
class QuotaStatus:
    limit_bytes: int
    logical_used_bytes: int
    logical_margin_bytes: int
    free_disk_bytes: int
    disk_margin_bytes: int
    database_bytes: int
    wal_bytes: int
    shm_bytes: int
    temp_bytes: int

    @property
    def sqlite_bytes(self) -> int:
        return self.database_bytes + self.wal_bytes + self.shm_bytes + self.temp_bytes

    @property
    def warning(self) -> bool:
        return (
            self.limit_bytes - self.logical_used_bytes <= 2 * self.logical_margin_bytes
            or self.free_disk_bytes <= 2 * self.disk_margin_bytes
        )

    def require_capacity(self, write_bytes: int = 0) -> None:
        if self.logical_used_bytes + write_bytes + self.logical_margin_bytes >= self.limit_bytes:
            raise QuotaExceeded("experiment quota has insufficient remaining headroom")
        if self.free_disk_bytes <= self.disk_margin_bytes + write_bytes:
            raise QuotaExceeded("free disk has insufficient write headroom")


def validate_quota_bytes(value: int) -> int:
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise ValueError("quota_bytes must be a positive SQLite-safe integer number of bytes")
    return value


def measure(path: Path, limit_bytes: int, logical_used_bytes: int, *, disk_usage=shutil.disk_usage):
    """Snapshot only known local files; SQLite may allocate other OS-managed temp files."""
    limit_bytes = validate_quota_bytes(limit_bytes)
    path = Path(path)

    def size(suffix):
        try:
            return path.with_name(path.name + suffix).stat().st_size
        except FileNotFoundError:
            return 0

    return QuotaStatus(
        limit_bytes=limit_bytes,
        logical_used_bytes=logical_used_bytes,
        logical_margin_bytes=min(LOGICAL_MARGIN_BYTES, max(1, limit_bytes // 20)),
        free_disk_bytes=disk_usage(path.parent).free,
        disk_margin_bytes=DISK_MARGIN_BYTES,
        database_bytes=size(""),
        wal_bytes=size("-wal"),
        shm_bytes=size("-shm"),
        temp_bytes=size("-journal") + size("-stmtjrnl"),
    )
