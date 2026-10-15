from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from importlib import import_module
from typing import cast

import pytest

_cache_module = import_module("laboratorio.storage.owned_laboratory_read_cache")
MAX_CACHE_ENTRIES = _cache_module.MAX_CACHE_ENTRIES
MAX_CACHE_PAYLOAD_BYTES = _cache_module.MAX_CACHE_PAYLOAD_BYTES
OwnedLaboratoryReadCache = _cache_module.OwnedLaboratoryReadCache
OwnedLaboratoryReadCertificate = _cache_module.OwnedLaboratoryReadCertificate


def certificate(metadata=b"{}", digests=b"\x00" * 32):
    return OwnedLaboratoryReadCertificate(metadata=metadata, session_digests=digests)


def test_get_put_hits_and_key_dimensions_are_isolated():
    cache = OwnedLaboratoryReadCache()
    value = certificate(b'{"summary":1}', b"a" * 32)
    cache.put("db-a", 1, "owner-a", "run-a", value)

    assert cache.get("db-a", 1, "owner-a", "run-a") == value
    assert cache.get("db-b", 1, "owner-a", "run-a") is None
    assert cache.get("db-a", 1, "owner-b", "run-a") is None
    assert cache.get("db-a", 1, "owner-a", "run-b") is None
    assert cache.get("db-a", 2, "owner-a", "run-a") is None


def test_lru_evicts_oldest_entry_after_capacity_and_get_updates_recency():
    cache = OwnedLaboratoryReadCache()
    for index in range(MAX_CACHE_ENTRIES):
        cache.put("db", 1, "owner", f"run-{index}", certificate(str(index).encode()))

    assert cache.get("db", 1, "owner", "run-0") is not None
    cache.put("db", 1, "owner", "run-new", certificate(b"new"))

    assert cache.get("db", 1, "owner", "run-0") is not None
    assert cache.get("db", 1, "owner", "run-1") is None
    assert cache.get("db", 1, "owner", "run-2") is not None
    assert cache.info.entries == MAX_CACHE_ENTRIES


def test_payload_accounting_evicts_by_compact_bytes_and_reports_exact_size():
    cache = OwnedLaboratoryReadCache()
    half = MAX_CACHE_PAYLOAD_BYTES // 2
    first = certificate(b"a" * half, b"b" * 32)
    second = certificate(b"c" * (MAX_CACHE_PAYLOAD_BYTES - half - 32), b"d" * 32)
    cache.put("db", 1, "owner", "one", first)
    cache.put("db", 1, "owner", "two", second)

    assert cache.info.payload_bytes == len(second.metadata) + len(second.session_digests)
    assert cache.info.entries == 1
    assert cache.get("db", 1, "owner", "one") is None
    assert cache.get("db", 1, "owner", "two") == second


def test_oversize_certificate_is_not_cached_and_does_not_raise():
    cache = OwnedLaboratoryReadCache()
    too_large = certificate(b"x" * (MAX_CACHE_PAYLOAD_BYTES + 1), b"")

    cache.put("db", 1, "owner", "large", too_large)

    assert cache.get("db", 1, "owner", "large") is None
    assert cache.info.entries == 0
    assert cache.info.payload_bytes == 0


def test_new_epoch_invalidates_old_entries_and_rejects_late_old_snapshot_put():
    cache = OwnedLaboratoryReadCache()
    old = certificate(b"old")
    current = certificate(b"current")
    cache.put("db", 4, "owner", "run", old)

    assert cache.get("db", 5, "owner", "run") is None
    cache.put("db", 5, "owner", "run", current)
    cache.put("db", 4, "owner", "late-old", old)

    assert cache.get("db", 4, "owner", "run") is None
    assert cache.get("db", 4, "owner", "late-old") is None
    assert cache.get("db", 5, "owner", "run") == current
    assert cache.info.entries == 1


def test_epoch_tracking_is_separate_for_each_database_identity():
    cache = OwnedLaboratoryReadCache()
    cache.put("db-a", 8, "owner", "run", certificate(b"a"))
    cache.put("db-b", 2, "owner", "run", certificate(b"b"))
    cache.put("db-a", 9, "owner", "new", certificate(b"new"))

    assert cache.get("db-a", 8, "owner", "run") is None
    assert cache.get("db-b", 2, "owner", "run") == certificate(b"b")


def test_certificate_is_frozen_compact_bytes_and_digest_block_is_ordinal_aligned():
    value = certificate(b'{"totals":{}}', b"z" * (32 * 3))

    assert type(value.metadata) is bytes
    assert type(value.session_digests) is bytes
    assert len(value.session_digests) == 32 * 3
    assert value.payload_bytes == len(value.metadata) + len(value.session_digests)
    with pytest.raises(FrozenInstanceError):
        field_name = "metadata"
        setattr(value, field_name, b"changed")
    with pytest.raises(ValueError):
        OwnedLaboratoryReadCertificate(metadata=cast(bytes, bytearray(b"{}")), session_digests=b"")
    with pytest.raises(ValueError):
        OwnedLaboratoryReadCertificate(metadata=b"{}", session_digests=b"short")


def test_cache_clear_resets_entries_and_epoch_state():
    cache = OwnedLaboratoryReadCache()
    cache.put("db", 10, "owner", "run", certificate())

    cache.clear()

    assert cache.info.entries == 0
    assert cache.info.payload_bytes == 0
    cache.put("db", 1, "owner", "run", certificate(b"after-clear"))
    assert cache.get("db", 1, "owner", "run") == certificate(b"after-clear")


def test_concurrent_get_put_and_clear_preserve_bounds_and_certificate_integrity():
    cache = OwnedLaboratoryReadCache()

    def operate(worker):
        for index in range(150):
            epoch = index % 7
            run_id = f"run-{worker}-{index}"
            value = certificate(f"{worker}:{index}".encode(), bytes([worker]) * 32)
            cache.put("shared-db", epoch, "owner", run_id, value)
            observed = cache.get("shared-db", epoch, "owner", run_id)
            assert observed is None or observed == value
            if index % 31 == 0:
                cache.clear()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(operate, range(8)))

    info = cache.info
    assert 0 <= info.entries <= MAX_CACHE_ENTRIES
    assert 0 <= info.payload_bytes <= MAX_CACHE_PAYLOAD_BYTES
