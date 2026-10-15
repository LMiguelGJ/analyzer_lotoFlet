"""Small bounded LRU for immutable owned-run read certificates.

This primitive owns no database connection and performs no persistence. T5 callers
must supply the database/repository identity and epoch read in the same SQLite
snapshot as the data they certify.
"""

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

MAX_CACHE_ENTRIES = 64
MAX_CACHE_PAYLOAD_BYTES = 16 * 1024 * 1024
_SHA256_BYTES = 32


@dataclass(frozen=True, slots=True)
class OwnedLaboratoryReadCertificate:
    """Validated compact metadata and ordinal-ordered SHA-256 digest bytes.

    ``metadata`` is the canonical compact snapshot/summary encoding only; it
    must not contain result_json or session collections. ``session_digests`` is
    a packed block of exactly one 32-byte digest per session ordinal.
    """

    metadata: bytes
    session_digests: bytes

    def __post_init__(self):
        if type(self.metadata) is not bytes or type(self.session_digests) is not bytes:
            raise ValueError("certificate payloads must be immutable bytes")
        if len(self.session_digests) % _SHA256_BYTES:
            raise ValueError("session digest block must contain 32-byte SHA-256 values")

    @property
    def payload_bytes(self):
        """Exact budgeted payload size (metadata bytes plus packed digests)."""
        return len(self.metadata) + len(self.session_digests)


@dataclass(frozen=True, slots=True)
class CacheInfo:
    """Observable payload accounting for this cache instance."""

    entries: int
    payload_bytes: int


class OwnedLaboratoryReadCache:
    """Thread-safe per-repository LRU certificate cache with fixed hard limits.

    ``get`` and ``put`` use the complete key ``(database_id, epoch, owner_id,
    run_id)``. A newly observed epoch invalidates prior entries for that database.
    Delayed old-snapshot puts are rejected after a newer epoch has been observed.
    ``clear`` resets both certificates and observed epochs. Payload accounting
    includes only certificate metadata and digest bytes, never Python object
    overhead. An entry too large for the entire payload budget is silently
    skipped so cache capacity never rejects a run.
    """

    def __init__(self):
        self._lock = Lock()
        self._entries = OrderedDict()
        self._latest_epochs = {}
        self._payload_bytes = 0

    @staticmethod
    def _validate_key(database_id, epoch, owner_id, run_id):
        if type(database_id) is not str or not database_id:
            raise ValueError("database_id must be a non-empty string")
        if type(epoch) is not int or epoch < 0:
            raise ValueError("epoch must be a non-negative integer")
        if type(owner_id) is not str or not owner_id:
            raise ValueError("owner_id must be a non-empty string")
        if type(run_id) is not str or not run_id:
            raise ValueError("run_id must be a non-empty string")

    def _observe_epoch(self, database_id, epoch):
        latest = self._latest_epochs.get(database_id)
        if latest is not None and epoch < latest:
            return False
        if latest is None or epoch > latest:
            self._latest_epochs[database_id] = epoch
            stale = [key for key in self._entries if key[0] == database_id]
            for key in stale:
                self._remove(key)
        return True

    def _remove(self, key):
        certificate = self._entries.pop(key)
        self._payload_bytes -= certificate.payload_bytes

    @property
    def info(self):
        """Return a lock-consistent count and exact cached payload byte total."""
        with self._lock:
            return CacheInfo(len(self._entries), self._payload_bytes)

    def get(self, database_id, epoch, owner_id, run_id):
        """Return a cached certificate, or None when absent/stale."""
        self._validate_key(database_id, epoch, owner_id, run_id)
        key = (database_id, epoch, owner_id, run_id)
        with self._lock:
            if not self._observe_epoch(database_id, epoch):
                return None
            certificate = self._entries.get(key)
            if certificate is not None:
                self._entries.move_to_end(key)
            return certificate

    def put(self, database_id, epoch, owner_id, run_id, certificate):
        """Cache a validated immutable certificate unless stale or oversized."""
        self._validate_key(database_id, epoch, owner_id, run_id)
        if type(certificate) is not OwnedLaboratoryReadCertificate:
            raise TypeError("certificate must be an OwnedLaboratoryReadCertificate")
        key = (database_id, epoch, owner_id, run_id)
        with self._lock:
            if not self._observe_epoch(database_id, epoch):
                return
            if certificate.payload_bytes > MAX_CACHE_PAYLOAD_BYTES:
                return
            if key in self._entries:
                self._remove(key)
            self._entries[key] = certificate
            self._payload_bytes += certificate.payload_bytes
            while (
                len(self._entries) > MAX_CACHE_ENTRIES
                or self._payload_bytes > MAX_CACHE_PAYLOAD_BYTES
            ):
                self._remove(next(iter(self._entries)))

    def clear(self):
        """Drop all entries and epoch observations atomically."""
        with self._lock:
            self._entries.clear()
            self._latest_epochs.clear()
            self._payload_bytes = 0
