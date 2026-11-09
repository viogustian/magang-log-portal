"""Unit tests for SetupWizard service helpers: preset matching and Gemini testing."""

from unittest.mock import MagicMock, patch

import pytest

from magang_log.server.services.setup_service import (
    find_closest_preset,
    predict_work_profile,
    verify_gemini_connection,
)
from magang_log.workprofile import ApplicationConfig, WorkProfile


def test_find_closest_preset_matches_designer() -> None:
    presets = [
        WorkProfile(
            profile_name="Software Engineer",
            natural_description="Coding in Python and Git.",
            applications=[ApplicationConfig(name="VS Code", process_names=["Code.exe"])],
            browser_domains=["github.com"],
        ),
        WorkProfile(
            profile_name="UI/UX Designer",
            natural_description="Perancangan wireframe dan visual mockup di Figma.",
            applications=[ApplicationConfig(name="Figma", process_names=["Figma.exe"])],
            browser_domains=["figma.com"],
        ),
    ]

    match = find_closest_preset("Saya mendesain mockup aplikasi dan wireframe di figma", presets)
    assert match.profile_name == "UI/UX Designer"


def test_find_closest_preset_fallback_to_default_when_empty() -> None:
    presets = [
        WorkProfile(
            profile_name="Software Engineer",
            natural_description="Coding in Python.",
        ),
        WorkProfile(
            profile_name="UI/UX Designer",
            natural_description="Designing mockups.",
        ),
    ]
    match = find_closest_preset("", presets)
    assert match.profile_name == "Software Engineer"


def test_verify_gemini_connection_empty_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        verify_gemini_connection("")


def test_verify_gemini_connection_success() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = verify_gemini_connection("valid-key-123", model="gemini-2.5-flash")
        assert result["valid"] is True
        assert result["model"] == "gemini-2.5-flash"


def test_predict_work_profile_gemini_success() -> None:
    mock_profile = WorkProfile(
        profile_name="AI Engineer",
        natural_description="Model fine-tuning and evaluation.",
        applications=[ApplicationConfig(name="VS Code", process_names=["Code.exe"])],
    )

    with patch(
        "magang_log.server.services.setup_service.call_gemini_for_profile",
        return_value=mock_profile,
    ):
        result = predict_work_profile("Developing neural networks", api_key="test-key")
        assert result.source == "gemini"
        assert result.profile.profile_name == "AI Engineer"


def test_predict_work_profile_fallback_when_gemini_fails() -> None:
    with patch(
        "magang_log.server.services.setup_service.call_gemini_for_profile",
        side_effect=RuntimeError("API quota exceeded"),
    ):
        result = predict_work_profile("Coding and debugging in python", api_key="test-key")
        assert result.source == "preset_fallback"
        assert result.profile.profile_name == "Software Engineer"
