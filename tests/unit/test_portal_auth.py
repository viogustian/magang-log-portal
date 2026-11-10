"""Unit tests for portal authentication state checker and login guard."""

import json
import time
from pathlib import Path

import pytest

from magang_log.server.services.portal_service import (
    PortalAuthService,
    get_portal_auth_status,
)


def test_auth_status_missing_file(tmp_path: Path) -> None:
    non_existent = tmp_path / "state.json"
    status = get_portal_auth_status(auth_state_path=non_existent)
    assert status.authenticated is False
    assert status.session_status == "missing"
    assert status.expires_at is None
    assert status.username is None


def test_auth_status_invalid_json(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "state.json"
    corrupt_file.write_text("not-a-valid-json", encoding="utf-8")
    status = get_portal_auth_status(auth_state_path=corrupt_file)
    assert status.authenticated is False
    assert status.session_status == "invalid"


def test_auth_status_expired_cookies(tmp_path: Path) -> None:
    expired_file = tmp_path / "state.json"
    past_timestamp = time.time() - 3600
    data = {
        "cookies": [
            {"name": "session_id", "value": "123", "expires": past_timestamp},
        ],
        "origins": [],
    }
    expired_file.write_text(json.dumps(data), encoding="utf-8")

    status = get_portal_auth_status(auth_state_path=expired_file)
    assert status.authenticated is False
    assert status.session_status == "expired"


def test_auth_status_valid_session(tmp_path: Path) -> None:
    valid_file = tmp_path / "state.json"
    future_timestamp = time.time() + 86400
    data = {
        "cookies": [
            {
                "name": "auth_token",
                "value": "xyz",
                "expires": future_timestamp,
            },
            {
                "name": "username",
                "value": "intern@example.com",
                "expires": future_timestamp,
            },
        ],
        "origins": [],
    }
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    status = get_portal_auth_status(auth_state_path=valid_file)
    assert status.authenticated is True
    assert status.session_status == "active"
    assert status.expires_at is not None
    assert status.username == "intern@example.com"


def test_concurrent_login_guard() -> None:
    service = PortalAuthService()
    assert service.is_login_active is False

    with service.acquire_login():
        assert service.is_login_active is True
        # Attempting to acquire again while active must raise RuntimeError
        with pytest.raises(RuntimeError, match="already in progress"):
            with service.acquire_login():
                pass

    assert service.is_login_active is False
