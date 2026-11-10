"""Integration tests untuk AppActivityCollector, pipeline runner, factory, dan CLI preview."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from magang_log.cli import CliRunner, main
from magang_log.collectors.app import AppActivityCollector
from magang_log.collectors.base import CollectorRunner
from magang_log.collectors.factory import collect_and_sanitize_evidence, create_collectors
from magang_log.collectors.recent import create_synthetic_lnk
from magang_log.settings import AppConfig, AppSourceSettings, SourcesSettings
from magang_log.store import LedgerStore
from magang_log.workprofile import ApplicationConfig, WorkProfile


def _make_profile() -> WorkProfile:
    return WorkProfile(
        profile_name="Data Analyst",
        natural_description="Analisis data bisnis",
        applications=[
            ApplicationConfig(
                name="Power BI Desktop",
                process_names=["PBIDesktop.exe"],
                file_extensions=[".pbix"],
                log_patterns=["Microsoft/Power BI Desktop/User.log"],
            ),
            ApplicationConfig(
                name="Figma",
                process_names=["Figma.exe"],
                file_extensions=[".fig"],
                log_patterns=[],
            ),
        ],
        browser_domains=["app.powerbi.com", "figma.com"],
    )


def test_app_activity_collector_with_collector_runner(tmp_path: Path) -> None:
    profile = _make_profile()
    target_date = date(2026, 10, 27)

    recent_dir = tmp_path / "Recent"
    recent_dir.mkdir()
    (recent_dir / "Dashboard.pbix.lnk").write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Dashboard.pbix",
            write_time=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        )
    )

    collector = AppActivityCollector(
        work_profile=profile,
        recent_dir=recent_dir,
    )

    runner = CollectorRunner(collectors=[collector])
    results = runner.run(target_date)

    assert len(results) == 1
    assert results[0].source == "app"
    assert results[0].kind == "app:recent_file"
    assert results[0].strength == "weak"
    assert runner.failures == []


def test_factory_creates_app_activity_collector_when_configured(tmp_path: Path) -> None:
    profile = _make_profile()
    db_file = tmp_path / "state.db"
    store = LedgerStore(db_path=db_file)

    config = AppConfig(
        sources=SourcesSettings(
            app=AppSourceSettings(
                enabled=True,
                work_profile=profile,
            )
        )
    )

    collectors = create_collectors(config, store)
    app_collectors = [c for c in collectors if getattr(c, "name", "") == "app"]
    assert len(app_collectors) == 1
    assert isinstance(app_collectors[0], AppActivityCollector)


def test_pipeline_collect_and_sanitize_evidence_integration(tmp_path: Path) -> None:
    profile = _make_profile()
    db_file = tmp_path / "state.db"
    store = LedgerStore(db_path=db_file)

    recent_dir = tmp_path / "Recent"
    recent_dir.mkdir()
    (recent_dir / "Report.pbix.lnk").write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Report.pbix",
            write_time=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        )
    )

    config = AppConfig(
        sources=SourcesSettings(
            app=AppSourceSettings(
                enabled=True,
                work_profile=profile,
                recent_dir=recent_dir,
            )
        )
    )

    target_date = date(2026, 10, 27)
    evidence = collect_and_sanitize_evidence(target_date, config, store)

    app_evidence = [e for e in evidence if e.source == "app"]
    assert len(app_evidence) == 1
    assert app_evidence[0].title == "Power BI Desktop - Report.pbix"
    assert app_evidence[0].strength == "weak"
    assert "~/Report.pbix" in app_evidence[0].detail


def test_cli_profile_list_command(capsys: pytest.CaptureFixture[str]) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["profile", "list"])
    assert result.exit_code == 0
    assert "PUSTAKA PRESET PROFIL KERJA" in result.stdout
    assert "Software Engineer" in result.stdout
    assert "Data Analyst" in result.stdout

    # Test JSON mode
    result_json = runner.invoke(main, ["profile", "list", "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert isinstance(data, list)
    assert any(p["profile_name"] == "Data Analyst" for p in data)


def test_cli_profile_show_command(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
timezone: Asia/Jakarta
sources:
  app:
    enabled: true
    work_profile:
      profile_name: "UI/UX Designer"
      natural_description: "Perancangan desain UI"
      applications:
        - name: "Figma"
          file_extensions: [".fig"]
      browser_domains: ["figma.com"]
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["profile", "show", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "PROFIL KERJA AKTIF: UI/UX DESIGNER" in result.stdout
    assert "Figma" in result.stdout
    assert "figma.com" in result.stdout

    # Test JSON mode
    result_json = runner.invoke(main, ["profile", "show", "--config", str(config_file), "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert data["profile_name"] == "UI/UX Designer"


def test_cli_preview_evidence_command(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    recent_dir = tmp_path / "Recent"
    recent_dir.mkdir()
    (recent_dir / "Design.fig.lnk").write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Design.fig",
            write_time=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        )
    )

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
timezone: Asia/Jakarta
sources:
  app:
    enabled: true
    recent_dir: "{str(recent_dir).replace("\\", "/")}"
    work_profile:
      profile_name: "UI/UX Designer"
      applications:
        - name: "Figma"
          file_extensions: [".fig"]
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "preview-evidence",
            "--source",
            "app",
            "--date",
            "2026-10-27",
            "--config",
            str(config_file),
            "--db",
            str(db_file),
        ],
    )
    assert result.exit_code == 0
    assert "PREVIEW BUKTI AKTIVITAS TANGGAL: 2026-10-27" in result.stdout
    assert "Figma - Design.fig" in result.stdout

    # Test JSON mode
    result_json = runner.invoke(
        main,
        [
            "preview-evidence",
            "--source",
            "app",
            "--date",
            "2026-10-27",
            "--config",
            str(config_file),
            "--db",
            str(db_file),
            "--json",
        ],
    )
    assert result_json.exit_code == 0
    items = json.loads(result_json.stdout)
    assert len(items) == 1
    assert items[0]["source"] == "app"
    assert items[0]["strength"] == "weak"
    assert items[0]["title"] == "Figma - Design.fig"
