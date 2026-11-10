"""Unit tests untuk AppActivityCollector dan penggabungan bukti (recent vs session log)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from magang_log.collectors.app import (
    AppActivityCollector,
    merge_app_evidence,
)
from magang_log.collectors.base import Evidence
from magang_log.workprofile import ApplicationConfig, WorkProfile


def _make_sample_profile() -> WorkProfile:
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


def test_merge_app_evidence_prioritizes_strong_session_over_weak_touch() -> None:
    target_date = date(2026, 10, 27)

    # Project Sales.pbix has both weak touch and strong session log
    weak_sales = Evidence(
        source="app",
        kind="app:recent_file",
        strength="weak",
        title="Power BI Desktop - Sales.pbix",
        detail="Project file opened from ~/Documents/Sales.pbix",
        ts=datetime(2026, 10, 27, 9, 0, 0, tzinfo=timezone.utc),
        work_date=target_date,
    )
    strong_sales = Evidence(
        source="app",
        kind="app:session_log",
        strength="strong",
        title="Power BI Desktop - Sales.pbix",
        detail="Saved project ~/Documents/Sales.pbix (duration: 60 min)",
        ts=datetime(2026, 10, 27, 10, 30, 0, tzinfo=timezone.utc),
        work_date=target_date,
    )

    # Project Mockup.fig only has weak touch
    weak_mockup = Evidence(
        source="app",
        kind="app:recent_file",
        strength="weak",
        title="Figma - Mockup.fig",
        detail="Project file opened from ~/Designs/Mockup.fig",
        ts=datetime(2026, 10, 27, 14, 0, 0, tzinfo=timezone.utc),
        work_date=target_date,
    )

    merged = merge_app_evidence(
        recent_evidence=[weak_sales, weak_mockup],
        session_evidence=[strong_sales],
    )

    # weak_sales should be superseded by strong_sales, but weak_mockup is retained
    assert len(merged) == 2
    titles = [ev.title for ev in merged]
    assert titles.count("Power BI Desktop - Sales.pbix") == 1
    assert "Figma - Mockup.fig" in titles

    sales_ev = next(ev for ev in merged if ev.title == "Power BI Desktop - Sales.pbix")
    assert sales_ev.strength == "strong"
    assert sales_ev.kind == "app:session_log"


def test_app_activity_collector_zero_surveillance(tmp_path: Path) -> None:
    target_date = date(2026, 10, 27)

    # Collector without WorkProfile returns []
    collector = AppActivityCollector(work_profile=None)
    assert collector.collect(target_date) == []


def test_app_activity_collector_orchestration(tmp_path: Path) -> None:
    profile = _make_sample_profile()
    target_date = date(2026, 10, 27)

    # Create dummy Recent directory with a .lnk
    from magang_log.collectors.recent import create_synthetic_lnk

    recent_dir = tmp_path / "Recent"
    recent_dir.mkdir()
    (recent_dir / "Design.fig.lnk").write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Design.fig",
            write_time=datetime(2026, 10, 27, 11, 0, 0, tzinfo=timezone.utc),
        )
    )

    # Create dummy Local AppData with User.log
    local_dir = tmp_path / "Local"
    local_dir.mkdir()
    log_file = local_dir / "Microsoft" / "Power BI Desktop" / "User.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(
        "2026-10-27T10:00:00Z [INFO] SaveReport: Saved C:\\Users\\intern\\Finance.pbix\n",
        encoding="utf-8",
    )

    collector = AppActivityCollector(
        work_profile=profile,
        recent_dir=recent_dir,
        log_base_dirs=[local_dir],
    )

    evidence = collector.collect(target_date)
    assert len(evidence) == 2

    figma_ev = next(ev for ev in evidence if "Figma" in ev.title)
    assert figma_ev.strength == "weak"
    assert figma_ev.kind == "app:recent_file"

    pbi_ev = next(ev for ev in evidence if "Power BI" in ev.title)
    assert pbi_ev.strength == "strong"
    assert pbi_ev.kind == "app:session_log"
