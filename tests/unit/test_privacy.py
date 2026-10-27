"""Unit tests untuk mesin sanitasi privasi deterministik (PrivacyFilter & DeterministicPrivacyEngine)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from magang_log.collectors.base import Evidence, compute_evidence_id
from magang_log.collectors.privacy import (
    DeterministicPrivacyEngine,
    PrivacyConfig,
    PrivacyFilter,
    sanitize_evidence,
)


def _make_evidence(
    title: str = "Test evidence",
    detail: str = "Detail info",
    source: str = "git",
    kind: str = "commit",
) -> Evidence:
    return Evidence(
        source=source,  # type: ignore[arg-type]
        kind=kind,
        ts=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        title=title,
        detail=detail,
    )


def test_privacy_filter_protocol_conformance() -> None:
    """Memastikan DeterministicPrivacyEngine memenuhi protokol PrivacyFilter."""
    engine = DeterministicPrivacyEngine()
    assert isinstance(engine, PrivacyFilter)


def test_path_redaction_windows_repo_relative() -> None:
    """Path Windows absolut di dalam repositori dikonversi menjadi relative path POSIX."""
    repo = "C:\\Users\\intern\\workspace\\magang-log-portal"
    config = PrivacyConfig(repo_roots=[repo])
    engine = DeterministicPrivacyEngine(default_config=config)

    raw = [
        _make_evidence(
            title="Modified C:\\Users\\intern\\workspace\\magang-log-portal\\src\\app.py",
            detail="See file at C:\\Users\\intern\\workspace\\magang-log-portal\\tests\\test_app.py for info.",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert len(sanitized) == 1
    assert sanitized[0].title == "Modified src/app.py"
    assert sanitized[0].detail == "See file at tests/test_app.py for info."


def test_path_redaction_windows_outside_repo() -> None:
    """Path Windows absolut di luar repositori disensor menjadi [REDACTED_PATH]."""
    repo = "C:\\Users\\intern\\workspace\\magang-log-portal"
    config = PrivacyConfig(repo_roots=[repo])
    engine = DeterministicPrivacyEngine(default_config=config)

    raw = [
        _make_evidence(
            title="Access C:\\Windows\\System32\\cmd.exe",
            detail="Config at C:\\Users\\secret\\keys.txt and C:\\Program Files\\App\\app.exe",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert sanitized[0].title == "Access [REDACTED_PATH]"
    assert sanitized[0].detail == "Config at [REDACTED_PATH] and [REDACTED_PATH]"


def test_path_redaction_unix_home_directories() -> None:
    """Path Unix home /home/... atau /Users/... dikonversi ke relative atau [REDACTED_PATH]."""
    repo = "/home/developer/magang-log-portal"
    config = PrivacyConfig(repo_roots=[repo])
    engine = DeterministicPrivacyEngine(default_config=config)

    raw = [
        _make_evidence(
            title="Checked /home/developer/magang-log-portal/src/main.py",
            detail="Leaked /home/developer/.ssh/id_rsa and /Users/admin/.aws/credentials",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert sanitized[0].title == "Checked src/main.py"
    assert "[REDACTED_PATH]" in sanitized[0].detail
    assert "/home/developer/.ssh" not in sanitized[0].detail
    assert "/Users/admin" not in sanitized[0].detail


def test_os_username_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Username sistem operasi dan custom username disensor menjadi [USER]."""
    monkeypatch.setenv("USERNAME", "secret_agent_47")
    monkeypatch.setenv("USER", "secret_agent_47")

    config = PrivacyConfig(custom_usernames=["special_intern"])
    engine = DeterministicPrivacyEngine(default_config=config)

    raw = [
        _make_evidence(
            title="Commit by secret_agent_47: initial push",
            detail="Reviewed by special_intern and secret_agent_47.",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert sanitized[0].title == "Commit by [USER]: initial push"
    assert sanitized[0].detail == "Reviewed by [USER] and [USER]."


def test_secrets_and_bearer_tokens_redaction() -> None:
    """Bearer tokens, API keys, dan token token berentropi tinggi disensor menjadi [REDACTED_TOKEN]."""
    engine = DeterministicPrivacyEngine()
    raw = [
        _make_evidence(
            title="Fix auth with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tokenpayload123",
            detail=(
                "api_key = 'sk-1234567890abcdef1234567890abcdef' and "
                "ghp_1234567890abcdefghijklmnopqrstuvwxyz and "
                "AKIAIOSFODNN7EXAMPLE"
            ),
        )
    ]
    sanitized = engine.sanitize(raw)

    assert "Bearer" not in sanitized[0].title or "[REDACTED_TOKEN]" in sanitized[0].title
    assert "eyJhbGci" not in sanitized[0].title
    assert "[REDACTED_TOKEN]" in sanitized[0].title

    assert "sk-1234567890" not in sanitized[0].detail
    assert "ghp_1234567890" not in sanitized[0].detail
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized[0].detail
    assert "[REDACTED_TOKEN]" in sanitized[0].detail


def test_password_parameters_redaction() -> None:
    """Parameter password disensor menjadi [REDACTED_PASSWORD]."""
    engine = DeterministicPrivacyEngine()
    raw = [
        _make_evidence(
            title="Set password=SuperSecretPassword123!",
            detail="Connecting with password: 'SecretKey@2026' and PASSWORD=topsecret",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert "SuperSecretPassword123!" not in sanitized[0].title
    assert "[REDACTED_PASSWORD]" in sanitized[0].title

    assert "SecretKey@2026" not in sanitized[0].detail
    assert "topsecret" not in sanitized[0].detail
    assert sanitized[0].detail.count("[REDACTED_PASSWORD]") >= 2


def test_private_ipv4_redaction() -> None:
    """Alamat IPv4 privat (10.x, 172.16-31.x, 192.168.x) disensor menjadi [REDACTED_IP], publik dipertahankan."""
    engine = DeterministicPrivacyEngine()
    raw = [
        _make_evidence(
            title="Deploy to 192.168.1.100 and 10.0.0.15",
            detail="Cluster nodes: 172.20.1.5, 172.16.0.1, but DNS is 8.8.8.8 and 1.1.1.1.",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert "192.168.1.100" not in sanitized[0].title
    assert "10.0.0.15" not in sanitized[0].title
    assert sanitized[0].title == "Deploy to [REDACTED_IP] and [REDACTED_IP]"

    assert "172.20.1.5" not in sanitized[0].detail
    assert "172.16.0.1" not in sanitized[0].detail
    assert "8.8.8.8" in sanitized[0].detail
    assert "1.1.1.1" in sanitized[0].detail
    assert "[REDACTED_IP]" in sanitized[0].detail


def test_email_redaction() -> None:
    """Alamat email disensor menjadi [REDACTED_EMAIL]."""
    engine = DeterministicPrivacyEngine()
    raw = [
        _make_evidence(
            title="Author: intern.name@company.co.id",
            detail="CC to team-lead+alerts@sub.domain.org and user123@gmail.com",
        )
    ]
    sanitized = engine.sanitize(raw)

    assert "intern.name@company.co.id" not in sanitized[0].title
    assert sanitized[0].title == "Author: [REDACTED_EMAIL]"

    assert "team-lead+alerts@sub.domain.org" not in sanitized[0].detail
    assert "user123@gmail.com" not in sanitized[0].detail
    assert sanitized[0].detail.count("[REDACTED_EMAIL]") == 2


def test_character_length_bounds() -> None:
    """Batas panjang karakter: title maksimal 300 karakter, detail maksimal 1000 karakter."""
    engine = DeterministicPrivacyEngine()
    long_title = "A" * 500
    long_detail = "B" * 1500

    raw = [_make_evidence(title=long_title, detail=long_detail)]
    sanitized = engine.sanitize(raw)

    assert len(sanitized[0].title) == 300
    assert sanitized[0].title == "A" * 300
    assert len(sanitized[0].detail) == 1000
    assert sanitized[0].detail == "B" * 1000


def test_input_immutability_and_evidence_id_recalculation() -> None:
    """Sanitasi mengembalikan list baru berisi objek Evidence baru tanpa memutasi objek input."""
    engine = DeterministicPrivacyEngine()
    original_title = "Secret password=my_secret_token"
    original_detail = "Contact secret@example.com"
    raw_item = _make_evidence(title=original_title, detail=original_detail)
    original_id = raw_item.id

    raw_list = [raw_item]
    sanitized_list = engine.sanitize(raw_list)

    # List tidak termutasi
    assert sanitized_list is not raw_list
    assert len(sanitized_list) == 1

    # Objek asli tidak termutasi
    assert raw_item.title == original_title
    assert raw_item.detail == original_detail
    assert raw_item.id == original_id

    # Objek tersanitasi adalah instance baru dengan ID yang dihitung ulang
    sanitized_item = sanitized_list[0]
    assert sanitized_item is not raw_item
    assert sanitized_item.title == "Secret [REDACTED_PASSWORD]"
    assert sanitized_item.detail == "Contact [REDACTED_EMAIL]"

    expected_id = compute_evidence_id(
        source=sanitized_item.source,
        kind=sanitized_item.kind,
        ts=sanitized_item.ts,
        title=sanitized_item.title,
    )
    assert sanitized_item.id == expected_id
    assert sanitized_item.id != original_id


def test_redteam_complex_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uji red-team gabungan berbagai input sensitif dalam satu payload kompleks."""
    monkeypatch.setenv("USERNAME", "target_user")
    repo = "C:\\Users\\target_user\\projects\\secret-portal"
    config = PrivacyConfig(repo_roots=[repo], custom_usernames=["target_user"])
    engine = DeterministicPrivacyEngine(default_config=config)

    malicious_title = (
        "target_user committed to C:\\Users\\target_user\\projects\\secret-portal\\src\\api.py: "
        "Bearer eyJhbGciOiJIUzI1NiJ9.supertoken12345678"
    )
    malicious_detail = (
        "Server at 192.168.1.10 crashed. Connect with password=rootPass123! "
        "Log dump at C:\\Windows\\temp\\crash.log and /home/target_user/.bash_history. "
        "Contact target_user@corp.internal or admin@yahoo.com. "
        "AWS key: AKIAIOSFODNN7EXAMPLE. " + ("X" * 1200)
    )

    raw = [_make_evidence(title=malicious_title, detail=malicious_detail)]
    sanitized = engine.sanitize(raw)
    result = sanitized[0]

    # Pastikan batasan panjang dihormati
    assert len(result.title) <= 300
    assert len(result.detail) <= 1000

    # Pastikan tidak ada kebocoran
    assert "target_user" not in result.title
    assert "target_user" not in result.detail
    assert "rootPass123!" not in result.detail
    assert "192.168.1.10" not in result.detail
    assert "target_user@corp.internal" not in result.detail
    assert "admin@yahoo.com" not in result.detail
    assert "AKIAIOSFODNN7EXAMPLE" not in result.detail
    assert "C:\\Windows\\temp" not in result.detail
    assert "/home/target_user" not in result.detail
    assert "supertoken12345678" not in result.title

    # Relative path repo berhasil dipertahankan
    assert "src/api.py" in result.title
    assert "[USER]" in result.title
    assert "[REDACTED_PASSWORD]" in result.detail
    assert "[REDACTED_IP]" in result.detail
    assert "[REDACTED_EMAIL]" in result.detail
    assert "[REDACTED_PATH]" in result.detail


def test_sanitize_evidence_helper() -> None:
    """Helper sanitize_evidence berfungsi sesuai default config."""
    raw = [_make_evidence(title="Fix password=12345")]
    sanitized = sanitize_evidence(raw)
    assert sanitized[0].title == "Fix [REDACTED_PASSWORD]"
