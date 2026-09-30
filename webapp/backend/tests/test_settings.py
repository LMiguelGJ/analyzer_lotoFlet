"""Quota provenance from environment and manually constructed settings."""

from dataclasses import replace

import pytest

from laboratorio.settings import DEFAULT_QUOTA_BYTES, Settings


def test_explicit_default_environment_quota_is_still_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LABORATORIO_QUOTA_BYTES", str(DEFAULT_QUOTA_BYTES))
    settings = Settings.from_environment()
    assert settings.quota_bytes == DEFAULT_QUOTA_BYTES
    assert settings.is_quota_explicit is True
    assert replace(settings, data_dir=tmp_path).is_quota_explicit is True


def test_manual_settings_preserve_legacy_override_and_can_opt_into_default(tmp_path):
    settings = Settings(tmp_path, tmp_path / "history", tmp_path / "ranks", tmp_path)
    assert settings.is_quota_explicit is False
    assert replace(settings, quota_bytes=123).is_quota_explicit is True
    assert replace(settings, quota_explicit=False, quota_bytes=123).is_quota_explicit is False
    with pytest.raises(ValueError, match="quota_explicit"):
        replace(settings, quota_explicit=1)
