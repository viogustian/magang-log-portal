"""Unit tests untuk domain cleaning, allowlist merging, dan persistensi konfigurasi browser domains."""

from __future__ import annotations

from pathlib import Path

import pytest

from magang_log.settings import (
    AppConfig,
    ConfigurationError,
    clean_domain,
    load_config,
    merge_browser_domains,
    sync_work_profile_browser_domains,
    update_config_browser_domains,
)
from magang_log.workprofile import WorkProfile


def test_clean_domain_variations() -> None:
    assert clean_domain("https://figma.com/") == "figma.com"
    assert clean_domain("http://dribbble.com/shots/popular") == "dribbble.com"
    assert clean_domain("  APP.POWERBI.COM:443/report/1  ") == "app.powerbi.com"
    assert clean_domain("github.com") == "github.com"
    assert clean_domain("  ") == ""
    assert clean_domain("http://") == ""


def test_merge_browser_domains_preserves_custom_and_appends() -> None:
    existing = ["custom-internal.corp", "github.com", "stackoverflow.com"]
    profile_domains = [
        "https://figma.com/",
        "dribbble.com",
        "GITHUB.COM",  # duplikat case-insensitive
        "https://custom-internal.corp/",  # duplikat dengan protocol
    ]

    merged = merge_browser_domains(existing, profile_domains)

    assert merged == [
        "custom-internal.corp",
        "github.com",
        "stackoverflow.com",
        "figma.com",
        "dribbble.com",
    ]


def test_merge_browser_domains_idempotency() -> None:
    existing = ["codewars.com", "github.com"]
    profile_domains = ["figma.com", "behance.net"]

    once = merge_browser_domains(existing, profile_domains)
    twice = merge_browser_domains(once, profile_domains)
    thrice = merge_browser_domains(twice, profile_domains)

    assert once == ["codewars.com", "github.com", "figma.com", "behance.net"]
    assert once == twice
    assert twice == thrice


def test_sync_work_profile_browser_domains_in_memory() -> None:
    cfg = AppConfig()
    cfg.sources.browser.allow_domains = ["google.com", "github.com"]

    profile = WorkProfile(
        profile_name="UI/UX Designer",
        browser_domains=["figma.com", "dribbble.com"],
    )

    synced = sync_work_profile_browser_domains(cfg, profile)

    assert synced == ["google.com", "github.com", "figma.com", "dribbble.com"]
    assert cfg.sources.browser.allow_domains == synced


def test_sync_work_profile_browser_domains_disabled_app_skipped() -> None:
    cfg = AppConfig()
    cfg.sources.browser.allow_domains = ["google.com"]
    cfg.sources.app.enabled = False
    cfg.sources.app.work_profile = WorkProfile(
        profile_name="Data Analyst",
        browser_domains=["app.powerbi.com"],
    )

    # Ketika profile tidak dilempar secara eksplisit dan sources.app nonaktif, jangan sinkronkan
    synced = sync_work_profile_browser_domains(cfg)
    assert synced == ["google.com"]
    assert cfg.sources.browser.allow_domains == ["google.com"]


def test_update_config_browser_domains_persistence(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
timezone: Asia/Jakarta
sources:
  browser:
    enabled: true
    allow_domains: ["my-site.org", "github.com"]
""",
        encoding="utf-8",
    )

    profile = WorkProfile(
        profile_name="Data Analyst",
        browser_domains=["app.powerbi.com", "tableau.com"],
    )

    # Jalankan sinkronisasi dan update ke file YAML
    res_path = update_config_browser_domains(config_file, profile)
    assert res_path == config_file

    # Muat ulang konfigurasi menggunakan load_config
    loaded = load_config(config_file, root_dir=tmp_path)
    expected_domains = ["my-site.org", "github.com", "app.powerbi.com", "tableau.com"]
    assert loaded.sources.browser.allow_domains == expected_domains

    # Pastikan operasi bersifat idempotent saat dijalankan ulang
    content_after_first = config_file.read_text(encoding="utf-8")
    update_config_browser_domains(config_file, profile)
    content_after_second = config_file.read_text(encoding="utf-8")

    loaded_again = load_config(config_file, root_dir=tmp_path)
    assert loaded_again.sources.browser.allow_domains == expected_domains
    assert content_after_first == content_after_second


def test_update_config_browser_domains_missing_file_raises_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing_config.yaml"
    profile = WorkProfile(profile_name="Test", browser_domains=["test.com"])

    with pytest.raises(ConfigurationError, match="tidak ditemukan"):
        update_config_browser_domains(missing, profile)

