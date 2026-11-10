"""Unit tests untuk Application Session Log Parser dengan opt-in pattern matching."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from magang_log.collectors.session_log import (
    ApplicationSessionLogParser,
    parse_log_content,
    resolve_log_files,
    sanitize_log_detail,
)
from magang_log.workprofile import ApplicationConfig, WorkProfile


def test_sanitize_log_detail() -> None:
    raw = r"Saved report to C:\Users\vio.gustian\Documents\Report.pbix with token=secret123"
    sanitized = sanitize_log_detail(raw)
    assert r"C:\Users\vio.gustian" not in sanitized
    assert "~/Documents/Report.pbix" in sanitized
    assert "secret123" not in sanitized
    assert "[REDACTED]" in sanitized


def test_resolve_log_files_with_env_and_relative(tmp_path: Path) -> None:
    local_dir = tmp_path / "AppData" / "Local"
    roaming_dir = tmp_path / "AppData" / "Roaming"
    local_dir.mkdir(parents=True)
    roaming_dir.mkdir(parents=True)

    log1 = local_dir / "Microsoft" / "Power BI Desktop" / "User.log"
    log1.parent.mkdir(parents=True)
    log1.write_text("dummy log 1", encoding="utf-8")

    log2 = roaming_dir / "CustomApp" / "session.json"
    log2.parent.mkdir(parents=True)
    log2.write_text("{}", encoding="utf-8")

    env_overrides = {
        "LOCALAPPDATA": local_dir,
        "APPDATA": roaming_dir,
    }

    # Relative pattern without env var -> should resolve in LOCALAPPDATA / APPDATA
    res1 = resolve_log_files(
        patterns=["Microsoft/Power BI Desktop/User.log"],
        env_overrides=env_overrides,
    )
    assert log1 in res1

    # Pattern with %APPDATA%
    res2 = resolve_log_files(
        patterns=["%APPDATA%/CustomApp/session.json"],
        env_overrides=env_overrides,
    )
    assert log2 in res2

    # Pattern with glob
    res3 = resolve_log_files(
        patterns=["Microsoft/Power BI Desktop/*.log"],
        env_overrides=env_overrides,
    )
    assert log1 in res3


def test_parse_log_content_text_lines() -> None:
    target_date = date(2026, 10, 27)
    sample_text = """
2026-10-27T08:30:00.000Z [INFO] Application started
2026-10-27T09:15:22.000Z [INFO] SaveReport: Saved project C:\\Users\\intern\\Sales_Q3.pbix successfully
2026-10-27T11:45:00.000Z [INFO] Active editing session duration: 45m on Sales_Q3.pbix
2026-10-28T09:00:00.000Z [INFO] SaveReport: Saved project C:\\Users\\intern\\Sales_Q4.pbix
"""
    evidence = parse_log_content(
        content=sample_text,
        app_name="Power BI Desktop",
        target_date=target_date,
    )

    assert len(evidence) == 2
    # Only events from 2026-10-27 matching operations
    assert all(ev.source == "app" for ev in evidence)
    assert all(ev.kind == "app:session_log" for ev in evidence)
    assert all(ev.strength == "strong" for ev in evidence)
    assert all(ev.work_date == target_date for ev in evidence)

    titles = [ev.title for ev in evidence]
    assert any("Sales_Q3.pbix" in t for t in titles)
    assert not any("Sales_Q4.pbix" in t for t in titles)


def test_parse_log_content_json_records() -> None:
    target_date = date(2026, 10, 27)
    records = [
        {
            "timestamp": "2026-10-27T10:00:00Z",
            "action": "export",
            "project": "Dashboard.pbix",
            "detail": "Exported report to PDF",
        },
        {
            "timestamp": "2026-10-27T14:20:00Z",
            "action": "save",
            "project": r"C:\Users\intern\Dashboard.pbix",
            "duration_minutes": 60,
        },
        {
            "timestamp": "2026-10-28T10:00:00Z",
            "action": "save",
            "project": "Tomorrow.pbix",
        },
    ]
    json_text = "\n".join(json.dumps(r) for r in records)

    evidence = parse_log_content(
        content=json_text,
        app_name="Power BI Desktop",
        target_date=target_date,
    )

    assert len(evidence) == 2
    assert evidence[0].strength == "strong"
    assert evidence[0].kind == "app:session_log"
    assert "Dashboard.pbix" in evidence[0].title
    assert evidence[0].work_date == target_date


def test_scanner_end_to_end_with_workprofile(tmp_path: Path) -> None:
    local_dir = tmp_path / "Local"
    local_dir.mkdir()
    pbi_log = local_dir / "Microsoft" / "Power BI Desktop" / "User.log"
    pbi_log.parent.mkdir(parents=True)
    pbi_log.write_text(
        """
2026-10-27T10:00:00Z [INFO] SaveReport: Saved C:\\Users\\intern\\Finance.pbix
2026-10-27T12:00:00Z [INFO] Session ended for Finance.pbix (duration: 120m)
2026-10-28T10:00:00Z [INFO] SaveReport: Saved C:\\Users\\intern\\Other.pbix
""",
        encoding="utf-8",
    )

    profile = WorkProfile(
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
    )

    scanner = ApplicationSessionLogParser(
        base_dirs=[local_dir],
        work_profile=profile,
    )
    target_date = date(2026, 10, 27)
    evidence = scanner.scan(target_date)

    assert len(evidence) == 2
    for ev in evidence:
        assert ev.source == "app"
        assert ev.kind == "app:session_log"
        assert ev.strength == "strong"
        assert ev.work_date == target_date
        assert ev.title == "Power BI Desktop - Finance.pbix"
        assert "C:/Users/intern" not in ev.detail
        assert "C:\\Users\\intern" not in ev.detail

    assert "~/Finance.pbix" in evidence[0].detail
    assert "Finance.pbix" in evidence[1].detail


def test_scanner_zero_surveillance_and_opt_in(tmp_path: Path) -> None:
    local_dir = tmp_path / "Local"
    local_dir.mkdir()
    # Log for an unmonitored application
    unmonitored_log = local_dir / "UnmonitoredApp" / "activity.log"
    unmonitored_log.parent.mkdir(parents=True)
    unmonitored_log.write_text(
        "2026-10-27T10:00:00Z [INFO] Save file secret.doc",
        encoding="utf-8",
    )

    # 1. Profile is None -> returns []
    scanner_none = ApplicationSessionLogParser(
        base_dirs=[local_dir],
        work_profile=None,
    )
    assert scanner_none.scan(date(2026, 10, 27)) == []

    # 2. Profile has no log patterns -> returns []
    profile_no_logs = WorkProfile(
        profile_name="Designer",
        natural_description="Desain grafis",
        applications=[
            ApplicationConfig(
                name="Figma",
                file_extensions=[".fig"],
                log_patterns=[],
            )
        ],
    )
    scanner_no_logs = ApplicationSessionLogParser(
        base_dirs=[local_dir],
        work_profile=profile_no_logs,
    )
    assert scanner_no_logs.scan(date(2026, 10, 27)) == []


def test_scanner_resilience_corrupted_and_missing(tmp_path: Path) -> None:
    local_dir = tmp_path / "Local"
    local_dir.mkdir()

    # File exists but corrupted binary garbage
    corrupt_log = local_dir / "App" / "corrupted.log"
    corrupt_log.parent.mkdir(parents=True)
    corrupt_log.write_bytes(b"\x00\xff\xfe\xca\xfe\xba\xbe\x00\x01\x02\x03")

    profile = WorkProfile(
        profile_name="Tester",
        natural_description="Testing",
        applications=[
            ApplicationConfig(
                name="CorruptedApp",
                log_patterns=["App/corrupted.log", "App/non_existent.log"],
            )
        ],
    )

    scanner = ApplicationSessionLogParser(
        base_dirs=[local_dir],
        work_profile=profile,
    )
    # Does not throw, handles gracefully
    evidence = scanner.scan(date(2026, 10, 27))
    assert evidence == []


def test_scanner_collector_protocol(tmp_path: Path) -> None:
    local_dir = tmp_path / "Local"
    local_dir.mkdir()
    log = local_dir / "app.log"
    log.write_text("2026-10-27T10:00:00Z Save project Test.pbix", encoding="utf-8")

    profile = WorkProfile(
        profile_name="Analyst",
        natural_description="Analyst",
        applications=[
            ApplicationConfig(
                name="Power BI Desktop",
                log_patterns=["app.log"],
            )
        ],
    )

    scanner = ApplicationSessionLogParser(base_dirs=[local_dir])
    # Pass profile via config in collect()
    evidence = scanner.collect(date(2026, 10, 27), config=profile)
    assert len(evidence) == 1
    assert evidence[0].kind == "app:session_log"
    assert evidence[0].strength == "strong"
