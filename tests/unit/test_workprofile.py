"""Unit test untuk domain model WorkProfile, ApplicationConfig, dan pemuatan preset."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from magang_log.workprofile import (
    ApplicationConfig,
    PresetError,
    WorkProfile,
    get_preset,
    load_preset_map,
    load_presets,
)


def test_application_config_creation_and_field_validation() -> None:
    app = ApplicationConfig(
        name="Figma",
        process_names=["  Figma.exe  "],
        file_extensions=[".fig", ".sketch"],
        log_patterns=["Figma/logs/*.log"],
    )

    assert app.name == "Figma"
    assert app.process_names == ["Figma.exe"]
    assert app.file_extensions == [".fig", ".sketch"]
    assert app.log_patterns == ["Figma/logs/*.log"]

    # Ekstensi tanpa titik di depan harus ditolak
    with pytest.raises(ValidationError):
        ApplicationConfig(name="Figma", file_extensions=["fig"])


def test_application_config_defaults_and_forbid_extra() -> None:
    app = ApplicationConfig(name="VS Code")
    assert app.name == "VS Code"
    assert app.process_names == []
    assert app.file_extensions == []
    assert app.log_patterns == []

    # extra='forbid' harus menolak field yang tidak didefinisikan
    with pytest.raises(ValidationError):
        ApplicationConfig(name="VS Code", unknown_field="invalid")  # type: ignore[call-arg]


def test_work_profile_creation_and_helpers() -> None:
    app_figma = ApplicationConfig(
        name="Figma",
        process_names=["Figma.exe"],
        file_extensions=[".fig"],
    )
    app_xd = ApplicationConfig(
        name="Adobe XD",
        process_names=["XD.exe"],
        file_extensions=[".xd"],
    )

    profile = WorkProfile(
        profile_name="UI/UX Designer",
        natural_description="Perancangan antarmuka dan pengalaman pengguna.",
        applications=[app_figma, app_xd],
        browser_domains=["figma.com", "dribbble.com"],
        watch_folders=["C:/Projects/Designs"],
    )

    assert profile.profile_name == "UI/UX Designer"
    assert profile.natural_description == "Perancangan antarmuka dan pengalaman pengguna."
    assert len(profile.applications) == 2
    assert profile.browser_domains == ["figma.com", "dribbble.com"]
    assert profile.watch_folders == ["C:/Projects/Designs"]

    # Helper all_file_extensions
    assert profile.all_file_extensions() == {".fig", ".xd"}

    # Helper all_process_names
    assert profile.all_process_names() == {"figma.exe", "xd.exe"}

    # Rejection of extra fields
    with pytest.raises(ValidationError):
        WorkProfile(profile_name="Test", unapproved_key="error")  # type: ignore[call-arg]


def test_load_presets_from_bundled_yaml() -> None:
    presets = load_presets()
    assert len(presets) >= 5

    names = {p.profile_name for p in presets}
    expected_profiles = {
        "Software Engineer",
        "UI/UX Designer",
        "Data Analyst",
        "Motion Designer",
        "Office / Admin",
    }
    assert expected_profiles.issubset(names)

    # Verifikasi masing-masing preset terurai valid
    preset_map = load_preset_map()
    assert len(preset_map) >= 5

    # 1. Software Engineer
    profile_se = preset_map["Software Engineer"]
    assert any("Code.exe" in app.process_names for app in profile_se.applications)
    assert any("git.exe" in app.process_names for app in profile_se.applications)
    assert any("github.com" in domain for domain in profile_se.browser_domains)

    # 2. UI/UX Designer
    profile_ui = preset_map["UI/UX Designer"]
    assert any("Figma.exe" in app.process_names for app in profile_ui.applications)
    assert ".fig" in profile_ui.all_file_extensions()
    assert any("figma.com" in domain for domain in profile_ui.browser_domains)

    # 3. Data Analyst
    profile_da = preset_map["Data Analyst"]
    assert any("PBIDesktop.exe" in app.process_names for app in profile_da.applications)
    assert ".pbix" in profile_da.all_file_extensions()
    assert ".xlsx" in profile_da.all_file_extensions()
    assert any("powerbi.com" in domain for domain in profile_da.browser_domains)

    # 4. Motion Designer
    profile_md = preset_map["Motion Designer"]
    assert any("AfterFX.exe" in app.process_names for app in profile_md.applications)
    assert ".aep" in profile_md.all_file_extensions()
    assert ".blend" in profile_md.all_file_extensions()

    # 5. Office / Admin
    profile_admin = preset_map["Office / Admin"]
    assert any("WINWORD.EXE" in app.process_names for app in profile_admin.applications)
    assert ".docx" in profile_admin.all_file_extensions()
    assert ".pptx" in profile_admin.all_file_extensions()


def test_get_preset_by_name() -> None:
    preset = get_preset("Software Engineer")
    assert preset.profile_name == "Software Engineer"
    assert len(preset.applications) > 0

    # Pencarian tidak sensitif huruf besar/kecil atau spasi
    preset_lower = get_preset("ui/ux designer")
    assert preset_lower.profile_name == "UI/UX Designer"

    with pytest.raises(PresetError, match="not found"):
        get_preset("Profil Kerja Tak Dikenal 12345")


def test_load_presets_missing_file_raises_preset_error(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent_presets.yaml"
    with pytest.raises(PresetError, match="not found|does not exist"):
        load_presets(missing)


def test_load_presets_invalid_yaml_raises_preset_error(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid: [yaml: broken", encoding="utf-8")
    with pytest.raises(PresetError, match="Failed to parse|Invalid"):
        load_presets(bad_yaml)


def test_load_presets_missing_presets_key_raises_preset_error(tmp_path: Path) -> None:
    bad_schema = tmp_path / "no_presets_key.yaml"
    bad_schema.write_text("version: 1\nroles: []\n", encoding="utf-8")
    with pytest.raises(PresetError, match="missing 'presets' key"):
        load_presets(bad_schema)


def test_load_presets_invalid_schema_raises_preset_error(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "invalid_schema.yaml"
    invalid_schema.write_text(
        """
presets:
  - profile_name: ""
    applications: "not a list"
""",
        encoding="utf-8",
    )
    with pytest.raises(PresetError, match="Validation error|Failed to validate"):
        load_presets(invalid_schema)

