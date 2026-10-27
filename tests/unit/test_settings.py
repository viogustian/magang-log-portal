from pathlib import Path

import pytest

from magang_log.settings import (
    AppConfig,
    ConfigurationError,
    load_config,
    normalize_workdays,
)


def test_default_config() -> None:
    cfg = AppConfig()
    assert cfg.timezone == "Asia/Jakarta"
    assert cfg.workdays == ["mon", "tue", "wed", "thu", "fri"]
    assert cfg.portal.headless is True
    assert cfg.rules.min_chars == 100
    assert cfg.rules.max_chars == 5000
    assert cfg.review.mode == "review"
    assert cfg.llm.provider == "gemini"
    assert cfg.sources.git.enabled is True
    assert cfg.sources.notes.enabled is True
    assert cfg.sources.browser.enabled is False


def test_load_valid_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
portal:
  base_url: "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat"
  auth_state: "data/auth/state.json"
  headless: false
rules:
  min_chars: 120
  max_chars: 4000
review:
  mode: review
llm:
  provider: gemini
  model: "gemini-2.5-flash"
  temperature: 0.3
  max_input_tokens: 5000
  daily_token_budget: 15000
sources:
  git:
    enabled: true
    repos: ["~/Projek/my-repo", "relative/repo"]
    include_diff: true
    send_to_llm: [commit_message]
  notes:
    enabled: true
  browser:
    enabled: false
    allow_domains: ["github.com"]
    send_to_llm: [title]
notify:
  channels: [toast]
retention_days:
  evidence: 7
  artifacts: 14
""",
        encoding="utf-8",
    )

    cfg = load_config(config_file, root_dir=tmp_path)
    assert cfg.portal.headless is False
    assert cfg.rules.min_chars == 120
    assert cfg.sources.git.include_diff is True
    assert cfg.retention_days.evidence == 7
    # Path evaluation checks
    assert cfg.portal.auth_state == tmp_path / "data/auth/state.json"
    assert cfg.sources.git.repos[0] == str(Path("~/Projek/my-repo").expanduser())
    assert cfg.sources.git.repos[1] == str((tmp_path / "relative/repo").resolve())


def test_reject_unknown_root_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
auto_update_logbook: true
workdays: [mon, tue, wed, thu, fri]
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(config_file, root_dir=tmp_path)
    assert "auto_update_logbook" in str(exc_info.value)


def test_reject_unknown_nested_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
sources:
  browser:
    enabled: false
    browsers: ["chrome"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(config_file, root_dir=tmp_path)
    assert "browsers" in str(exc_info.value)


def test_normalize_workdays() -> None:
    assert normalize_workdays(["Mon", "tue", "WED", "thu", "fri"]) == {0, 1, 2, 3, 4}
    assert normalize_workdays(["Senin", "selasa", "Rabu", "Kamis", "Jumat"]) == {0, 1, 2, 3, 4}
    assert normalize_workdays(["mon", "sat"]) == {0, 5}

    with pytest.raises(ValueError, match="Invalid workday name"):
        normalize_workdays(["funday"])
