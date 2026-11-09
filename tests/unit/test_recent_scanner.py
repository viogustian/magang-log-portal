"""Unit tests untuk Windows Recent Items scanner, LNK parser, dan strict allowlist gating."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from magang_log.collectors.recent import (
    RecentItemsScanner,
    create_synthetic_lnk,
    parse_lnk,
    sanitize_path,
)
from magang_log.workprofile import ApplicationConfig, WorkProfile


def _make_test_profile() -> WorkProfile:
    return WorkProfile(
        profile_name="Data Analyst",
        natural_description="Analisis data dan pelaporan BI",
        applications=[
            ApplicationConfig(
                name="Power BI Desktop",
                process_names=["PBIDesktop.exe"],
                file_extensions=[".pbix", ".pbit"],
            ),
            ApplicationConfig(
                name="Figma",
                process_names=["Figma.exe"],
                file_extensions=[".fig"],
            ),
        ],
        browser_domains=["app.powerbi.com", "figma.com"],
    )


def test_sanitize_path() -> None:
    assert (
        sanitize_path(r"C:\Users\vio.gustian\Documents\Projek\Report.pbix")
        == "~/Documents/Projek/Report.pbix"
    )
    assert sanitize_path("C:/Users/intern/Designs/UI.fig") == "~/Designs/UI.fig"
    assert sanitize_path(r"D:\Shared\Work\Sheet.xlsx") == "D:/Shared/Work/Sheet.xlsx"
    assert sanitize_path("~/Projects/App.py") == "~/Projects/App.py"


def test_parse_synthetic_lnk() -> None:
    target = r"C:\Users\testuser\Documents\Sales.pbix"
    target_dt = datetime(2026, 10, 27, 11, 45, 0, tzinfo=timezone.utc)
    raw_lnk = create_synthetic_lnk(target, write_time=target_dt)

    info = parse_lnk(raw_lnk)
    assert info is not None
    assert info.target_path == target
    assert info.modified_time == target_dt


def test_parse_corrupt_lnk_returns_none() -> None:
    assert parse_lnk(b"") is None
    assert parse_lnk(b"short") is None
    assert parse_lnk(b"\x00" * 80) is None
    assert parse_lnk(Path("non_existent_file.lnk")) is None


def test_scanner_filtering_by_target_date(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)
    other_date = date(2026, 10, 28)

    # File on target date
    lnk1 = tmp_path / "Sales_Q3.pbix.lnk"
    lnk1.write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Sales_Q3.pbix",
            write_time=datetime(2026, 10, 27, 14, 0, 0, tzinfo=timezone.utc),
        )
    )

    # File on other date
    lnk2 = tmp_path / "Sales_Q4.pbix.lnk"
    lnk2.write_bytes(
        create_synthetic_lnk(
            r"C:\Users\intern\Sales_Q4.pbix",
            write_time=datetime(2026, 10, 28, 9, 30, 0, tzinfo=timezone.utc),
        )
    )

    scanner = RecentItemsScanner(recent_dir=tmp_path, work_profile=profile)
    evidence = scanner.scan(target_date)

    assert len(evidence) == 1
    assert evidence[0].title == "Power BI Desktop - Sales_Q3.pbix"
    assert evidence[0].work_date == target_date

    # Scan for other date
    evidence_other = scanner.scan(other_date)
    assert len(evidence_other) == 1
    assert evidence_other[0].title == "Power BI Desktop - Sales_Q4.pbix"
    assert evidence_other[0].work_date == other_date


def test_scanner_strict_opt_in_allowlist(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)
    dt = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

    # Monitored files (.pbix, .fig)
    (tmp_path / "Dashboard.pbix.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Dashboard.pbix", write_time=dt)
    )
    (tmp_path / "Mockup.fig.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Mockup.fig", write_time=dt)
    )

    # Unmonitored files (MUST be discarded before parsing/inspecting)
    (tmp_path / "Resume.pdf.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Resume.pdf", write_time=dt)
    )
    (tmp_path / "Tutorial.mp4.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Tutorial.mp4", write_time=dt)
    )
    (tmp_path / "Temp.tmp.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Temp.tmp", write_time=dt)
    )
    # Even garbage binary file named with unmonitored extension must be ignored cleanly
    (tmp_path / "secret.docx.lnk").write_bytes(b"NOT_A_VALID_LNK_PAYLOAD")

    scanner = RecentItemsScanner(recent_dir=tmp_path, work_profile=profile)
    evidence = scanner.scan(target_date)

    assert len(evidence) == 2
    titles = {ev.title for ev in evidence}
    assert titles == {
        "Power BI Desktop - Dashboard.pbix",
        "Figma - Mockup.fig",
    }


def test_scanner_evidence_contract_mapping(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)
    dt = datetime(2026, 10, 27, 15, 30, 0, tzinfo=timezone.utc)

    (tmp_path / "Financial_Report.pbix.lnk").write_bytes(
        create_synthetic_lnk(
            r"C:\Users\vio.gustian\Documents\Financial_Report.pbix",
            write_time=dt,
        )
    )

    scanner = RecentItemsScanner(recent_dir=tmp_path, work_profile=profile)
    evidence = scanner.scan(target_date)

    assert len(evidence) == 1
    ev = evidence[0]

    assert ev.source == "app"
    assert ev.kind == "app:recent_file"
    assert ev.strength == "weak"
    assert ev.title == "Power BI Desktop - Financial_Report.pbix"
    assert ev.detail == "Project file opened from ~/Documents/Financial_Report.pbix"
    assert ev.ts == dt
    assert ev.work_date == target_date
    assert len(ev.id) == 10


def test_scanner_graceful_missing_or_inaccessible_dir(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)

    # Missing directory
    scanner_missing = RecentItemsScanner(
        recent_dir=tmp_path / "does_not_exist",
        work_profile=profile,
    )
    assert scanner_missing.scan(target_date) == []

    # Path is a file, not a directory
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello", encoding="utf-8")
    scanner_file = RecentItemsScanner(recent_dir=dummy_file, work_profile=profile)
    assert scanner_file.scan(target_date) == []

    # Empty directory
    scanner_empty = RecentItemsScanner(recent_dir=tmp_path, work_profile=profile)
    assert scanner_empty.scan(target_date) == []


def test_scanner_zero_surveillance_boundary(tmp_path: Path) -> None:
    target_date = date(2026, 10, 27)
    dt = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

    (tmp_path / "Project.pbix.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Project.pbix", write_time=dt)
    )

    # Profile is None
    scanner_no_profile = RecentItemsScanner(recent_dir=tmp_path, work_profile=None)
    assert scanner_no_profile.scan(target_date) == []

    # Profile with no applications
    empty_profile = WorkProfile(
        profile_name="Blank Profile",
        natural_description="Tidak memantau aplikasi desktop apapun",
        applications=[],
    )
    scanner_blank = RecentItemsScanner(recent_dir=tmp_path, work_profile=empty_profile)
    assert scanner_blank.scan(target_date) == []


def test_scanner_deduplication(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)
    dt = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

    # Two different lnk files pointing to the same sanitized path
    (tmp_path / "Project.pbix.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Project.pbix", write_time=dt)
    )
    (tmp_path / "Project (1).pbix.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Project.pbix", write_time=dt)
    )

    scanner = RecentItemsScanner(recent_dir=tmp_path, work_profile=profile)
    evidence = scanner.scan(target_date)

    assert len(evidence) == 1
    assert evidence[0].title == "Power BI Desktop - Project.pbix"


def test_scanner_collect_protocol(tmp_path: Path) -> None:
    profile = _make_test_profile()
    target_date = date(2026, 10, 27)
    dt = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

    (tmp_path / "Dashboard.pbix.lnk").write_bytes(
        create_synthetic_lnk(r"C:\Users\intern\Dashboard.pbix", write_time=dt)
    )

    scanner = RecentItemsScanner(recent_dir=tmp_path)
    # Pass profile via collect(target_date, config=profile)
    evidence = scanner.collect(target_date, config=profile)

    assert len(evidence) == 1
    assert evidence[0].title == "Power BI Desktop - Dashboard.pbix"
