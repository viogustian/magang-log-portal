"""Unit tests for SetupWizard service helpers: preset matching and Gemini testing."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magang_log.server.services.setup_service import (
    WizardProgressState,
    check_requirement_status,
    find_closest_preset,
    load_wizard_progress,
    predict_work_profile,
    save_wizard_progress,
    scan_system_requirements,
    validate_folder_paths,
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


def test_check_requirement_status_specifiers() -> None:
    assert check_requirement_status(">=3.12", "3.14.8") == "ok"
    assert check_requirement_status(">=3.12", "3.11.0") == "version_mismatch"
    assert check_requirement_status(">=3.12", None) == "missing"
    assert check_requirement_status(">=1.40", "1.42.0") == "ok"
    assert check_requirement_status(">=1.40", "1.39.0") == "version_mismatch"
    assert check_requirement_status("", "1.0.0") == "ok"


def test_scan_system_requirements_custom_root(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "dummy-app"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "playwright>=1.40",
]
""",
        encoding="utf-8",
    )

    items = scan_system_requirements(root_path=tmp_path)
    assert len(items) >= 2
    names = {i.name for i in items}
    assert "Python" in names
    assert "Playwright" in names

    py_item = next(i for i in items if i.name == "Python")
    assert py_item.min_version == ">=3.12"
    assert py_item.guidance.download_url.startswith("http")


def test_validate_folder_paths_unit(tmp_path: Path) -> None:
    folder_ok = tmp_path / "project_a"
    folder_ok.mkdir()
    (folder_ok / ".git").mkdir()

    results = validate_folder_paths([str(folder_ok), str(tmp_path / "absent")])
    assert len(results) == 2
    assert results[0].exists is True
    assert results[0].is_git is True
    assert results[1].exists is False
    assert results[1].error == "Folder tidak ditemukan"


def test_wizard_progress_persistence_unit(tmp_path: Path) -> None:
    target_yaml = tmp_path / "wizard-progress.yaml"

    # Default when not exists
    initial = load_wizard_progress(target_yaml)
    assert initial.current_step == 0
    assert initial.completed_steps == []

    # Save
    state = WizardProgressState(
        current_step=3,
        completed_steps=[0, 1, 2],
        step_data={"role": "UI/UX Designer", "git_intensity": "jarang"},
    )
    res = save_wizard_progress(state, target_path=target_yaml)
    assert res["success"] is True

    # Load again
    loaded = load_wizard_progress(target_yaml)
    assert loaded.current_step == 3
    assert loaded.completed_steps == [0, 1, 2]
    assert loaded.step_data["role"] == "UI/UX Designer"

