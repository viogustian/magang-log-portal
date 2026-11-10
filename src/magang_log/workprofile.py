"""Domain model untuk profil kerja intern (WorkProfile), konfigurasi aplikasi, dan pustaka preset."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class PresetError(Exception):
    """Kesalahan pemuatan, pembacaan, atau validasi pustaka preset profil kerja."""


class StrictBaseModel(BaseModel):
    """Model dasar Pydantic yang menolak atribut tak dikenal."""

    model_config = ConfigDict(extra="forbid")


class ApplicationConfig(StrictBaseModel):
    """Konfigurasi satu aplikasi desktop dalam WorkProfile.

    Fields:
    - name: Nama kanonikal aplikasi (mis. "Figma", "Power BI Desktop")
    - process_names: Nama executable proses (mis. ["Figma.exe"], ["PBIDesktop.exe"])
    - file_extensions: Ekstensi file proyek dengan titik awal (mis. [".fig"], [".pbix", ".pbit"])
    - log_patterns: Pola glob/relatif lokasi berkas log internal sesi aplikasi
    """

    name: str
    process_names: list[str] = Field(default_factory=list)
    file_extensions: list[str] = Field(default_factory=list)
    log_patterns: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Application name must not be empty.")
        return s

    @field_validator("process_names")
    @classmethod
    def normalize_process_names(cls, v: Sequence[str]) -> list[str]:
        return [proc.strip() for proc in v if proc.strip()]

    @field_validator("file_extensions")
    @classmethod
    def validate_file_extensions(cls, v: Sequence[str]) -> list[str]:
        validated: list[str] = []
        for ext in v:
            clean = ext.strip()
            if not clean:
                continue
            if not clean.startswith("."):
                raise ValueError(
                    f"File extension must start with a leading dot ('.'): {ext!r}"
                )
            if len(clean) == 1:
                raise ValueError(f"File extension cannot be only a dot: {ext!r}")
            validated.append(clean.lower())
        return validated


class WorkProfile(StrictBaseModel):
    """Model domain profil kerja intern yang memetakan software stack dan domain relevan.

    Fields:
    - profile_name: Judul profil kerja kanonikal (mis. "Software Engineer", "UI/UX Designer")
    - natural_description: Deskripsi kegiatan magang dalam bahasa manusia
    - applications: Daftar konfigurasi aplikasi desktop yang dipantau
    - browser_domains: Daftar domain peramban yang relevan dengan profil kerja
    - watch_folders: Daftar direktori pemantauan berkas proyek
    """

    profile_name: str
    natural_description: str = ""
    applications: list[ApplicationConfig] = Field(default_factory=list)
    browser_domains: list[str] = Field(default_factory=list)
    watch_folders: list[str] = Field(default_factory=list)

    @field_validator("profile_name")
    @classmethod
    def validate_profile_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Profile name must not be empty.")
        return s

    def all_file_extensions(self) -> set[str]:
        """Mengembalikan himpunan seluruh ekstensi berkas yang dipantau (lowercase dengan titik)."""
        return {
            ext.lower()
            for app in self.applications
            for ext in app.file_extensions
        }

    def all_process_names(self) -> set[str]:
        """Mengembalikan himpunan seluruh nama proses yang dipantau (lowercase)."""
        return {
            proc.lower()
            for app in self.applications
            for proc in app.process_names
        }


def _resolve_presets_path(path: Path | str | None) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if path is not None:
        p = Path(path)
        if not p.is_absolute():
            if p.exists():
                return p.resolve()
            candidate = repo_root / p
            if candidate.exists():
                return candidate.resolve()
        return p

    # Default path
    cwd_candidate = Path("config/presets.yaml")
    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    return (repo_root / "config" / "presets.yaml").resolve()


def load_presets(path: Path | str | None = None) -> list[WorkProfile]:
    """Membaca dan memvalidasi pustaka preset dari file YAML ke dalam list WorkProfile.

    Raises:
        PresetError: Jika file tidak ditemukan, sintaks YAML cacat, atau skema tidak valid.
    """
    resolved_path = _resolve_presets_path(path)
    if not resolved_path.exists():
        raise PresetError(f"Preset file not found: {resolved_path}")

    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise PresetError(f"Failed to parse preset YAML file {resolved_path}: {exc}") from exc
    except OSError as exc:
        raise PresetError(f"Failed to read preset file {resolved_path}: {exc}") from exc

    if not isinstance(data, (dict, list)):
        raise PresetError(
            f"Invalid preset format in {resolved_path}. Expected a YAML mapping or list, got {type(data).__name__}."
        )

    raw_list: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if "presets" not in data:
            raise PresetError(
                f"Failed to validate preset file {resolved_path}: missing 'presets' key."
            )
        presets_val = data["presets"]
        if not isinstance(presets_val, list):
            raise PresetError(
                f"Failed to validate preset file {resolved_path}: 'presets' key must be a list."
            )
        raw_list = presets_val
    elif isinstance(data, list):
        raw_list = data

    if not raw_list:
        raise PresetError(f"Preset file {resolved_path} contains no presets.")

    profiles: list[WorkProfile] = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise PresetError(
                f"Failed to validate preset item at index {idx} in {resolved_path}: item must be a dictionary."
            )
        try:
            profile = WorkProfile.model_validate(item)
            profiles.append(profile)
        except Exception as exc:
            raise PresetError(
                f"Failed to validate preset profile at index {idx} in {resolved_path}: {exc}"
            ) from exc

    return profiles


def load_preset_map(path: Path | str | None = None) -> dict[str, WorkProfile]:
    """Membaca pustaka preset dan mengembalikannya sebagai kamus yang dipetakan berdasarkan nama profil."""
    presets = load_presets(path)
    return {p.profile_name: p for p in presets}


def get_preset(name: str, path: Path | str | None = None) -> WorkProfile:
    """Mengambil satu preset WorkProfile berdasarkan nama kanonikal profil kerja (case-insensitive)."""
    preset_map = load_preset_map(path)
    lookup_clean = name.strip().lower()

    for preset_name, profile in preset_map.items():
        if preset_name.strip().lower() == lookup_clean:
            return profile

    raise PresetError(
        f"Preset with name {name!r} not found. Available presets: {list(preset_map.keys())}"
    )

