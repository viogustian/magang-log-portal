"""Modul konfigurasi magang-log: pemuatan YAML dengan validasi skema ketat (Pydantic extra='forbid')."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigurationError(Exception):
    """Kesalahan pemuatan atau validasi konfigurasi aplikasi."""


DAY_NAME_MAP: dict[str, int] = {
    "mon": 0,
    "monday": 0,
    "senin": 0,
    "tue": 1,
    "tuesday": 1,
    "selasa": 1,
    "wed": 2,
    "wednesday": 2,
    "rabu": 2,
    "thu": 3,
    "thursday": 3,
    "kamis": 3,
    "fri": 4,
    "friday": 4,
    "jumat": 4,
    "sat": 5,
    "saturday": 5,
    "sabtu": 5,
    "sun": 6,
    "sunday": 6,
    "minggu": 6,
}


def normalize_workdays(days: list[str]) -> set[int]:
    """Mengonversi nama hari kerja menjadi himpunan indeks hari (0=Senin, ..., 6=Minggu)."""
    normalized: set[int] = set()
    for day in days:
        key = str(day).strip().lower()
        if key not in DAY_NAME_MAP:
            raise ValueError(
                f"Invalid workday name: {day!r}. Supported values: {list(DAY_NAME_MAP.keys())}"
            )
        normalized.add(DAY_NAME_MAP[key])
    return normalized


def resolve_path(p: str | Path, root_dir: Path) -> Path:
    """Mengevaluasi path relatif terhadap root repo atau direktori home pengguna (~)."""
    s = str(p)
    if s.startswith("~"):
        return Path(s).expanduser()
    path = Path(s)
    if path.is_absolute():
        return path
    return (root_dir / path).resolve()


class StrictBaseModel(BaseModel):
    """Model dasar Pydantic yang menolak atribut tak dikenal."""

    model_config = ConfigDict(extra="forbid")


class PortalSettings(StrictBaseModel):
    base_url: str = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat"
    auth_state: Path = Path("data/auth/state.json")
    headless: bool = True
    artifacts_dir: Path = Path("data/runs")
    channel: str | None = "chrome"
    timeout_ms: int = 30_000
    location_timeout_ms: int = 15_000
    allow_location: bool = True


class RulesSettings(StrictBaseModel):
    min_chars: int = 100
    max_chars: int = 5000


class ReviewSettings(StrictBaseModel):
    mode: str = "review"


class LLMSettings(StrictBaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_input_tokens: int = 6000
    daily_token_budget: int = 20000


class GitSourceSettings(StrictBaseModel):
    enabled: bool = True
    repos: list[str] = Field(default_factory=list)
    include_diff: bool = False
    send_to_llm: list[str] = Field(
        default_factory=lambda: ["commit_message", "file_paths_relative"]
    )


class NotesSourceSettings(StrictBaseModel):
    enabled: bool = True


class BrowserSourceSettings(StrictBaseModel):
    enabled: bool = False
    allow_domains: list[str] = Field(
        default_factory=lambda: ["github.com", "stackoverflow.com", "learn.microsoft.com"]
    )
    send_to_llm: list[str] = Field(default_factory=lambda: ["title", "domain"])


class SourcesSettings(StrictBaseModel):
    git: GitSourceSettings = Field(default_factory=GitSourceSettings)
    notes: NotesSourceSettings = Field(default_factory=NotesSourceSettings)
    browser: BrowserSourceSettings = Field(default_factory=BrowserSourceSettings)


class NotifySettings(StrictBaseModel):
    channels: list[str] = Field(default_factory=lambda: ["toast"])


class RetentionDaysSettings(StrictBaseModel):
    evidence: int = 14
    artifacts: int = 30


class AppConfig(StrictBaseModel):
    timezone: str = "Asia/Jakarta"
    workdays: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])
    holidays_file: Path = Path("config/holidays.yaml")
    personal_holidays: dict[str, str] = Field(default_factory=dict)
    portal: PortalSettings = Field(default_factory=PortalSettings)
    rules: RulesSettings = Field(default_factory=RulesSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    sources: SourcesSettings = Field(default_factory=SourcesSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    retention_days: RetentionDaysSettings = Field(default_factory=RetentionDaysSettings)

    def active_workdays(self) -> set[int]:
        """Mengembalikan himpunan hari kerja yang dinormalisasi (0=Senin .. 6=Minggu)."""
        return normalize_workdays(self.workdays)


def find_repo_root(start: Path | None = None) -> Path:
    """Mencari direktori root repositori berdasarkan penanda pyproject.toml atau .git."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return cur


def load_config(
    path: str | Path | None = None,
    root_dir: Path | None = None,
) -> AppConfig:
    """Memuat dan memvalidasi konfigurasi YAML dengan skema ketat."""
    root = (root_dir or find_repo_root()).resolve()

    if path is None:
        default_yaml = root / "config" / "config.yaml"
        example_yaml = root / "config" / "config.example.yaml"
        if default_yaml.exists():
            target_file = default_yaml
        elif example_yaml.exists():
            target_file = example_yaml
        else:
            return AppConfig()
    else:
        target_file = resolve_path(path, root)

    if not target_file.exists():
        raise ConfigurationError(f"File konfigurasi tidak ditemukan: {target_file}")

    try:
        raw_text = target_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Sintaks YAML tidak valid di {target_file}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ConfigurationError(
            f"Isi file konfigurasi harus berupa mapping/dictionary: {target_file}"
        )

    try:
        config = AppConfig.model_validate(parsed)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            errors.append(f"- {loc}: {msg}")
        joined_errors = "\n".join(errors)
        raise ConfigurationError(
            f"Validasi konfigurasi gagal di {target_file}:\n{joined_errors}"
        ) from exc

    # Evaluasi path relatif terhadap root repo atau home user
    config.portal.auth_state = resolve_path(config.portal.auth_state, root)
    config.portal.artifacts_dir = resolve_path(config.portal.artifacts_dir, root)
    config.holidays_file = resolve_path(config.holidays_file, root)
    config.sources.git.repos = [str(resolve_path(r, root)) for r in config.sources.git.repos]

    return config
