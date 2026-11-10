"""Modul konfigurasi magang-log: pemuatan YAML dengan validasi skema ketat (Pydantic extra='forbid')."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .workprofile import WorkProfile

logger = logging.getLogger(__name__)


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
    auto_if_confident: bool = False


class LLMSettings(StrictBaseModel):
    provider: str = "gemini"
    model: str = "gemini-3.5-flash"
    temperature: float = 0.2
    max_input_tokens: int = 6000
    daily_token_budget: int = 20000


class GitSourceSettings(StrictBaseModel):
    enabled: bool = True
    repos: list[str] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
    author_email: str | None = None
    include_diff: bool = False
    send_to_llm: bool | list[str] = Field(
        default_factory=lambda: ["commit_message", "file_paths_relative"]
    )

    def get_repositories(self) -> list[str]:
        """Mengambil daftar repositori yang dikonfigurasi (repositories atau repos)."""
        return self.repositories if self.repositories else self.repos


class NotesSourceSettings(StrictBaseModel):
    enabled: bool = True
    send_to_llm: bool | list[str] = True


class BrowserSourceSettings(StrictBaseModel):
    enabled: bool = False
    allow_domains: list[str] = Field(
        default_factory=lambda: ["github.com", "stackoverflow.com", "learn.microsoft.com"]
    )
    allowlist: list[str] = Field(default_factory=list)
    history_files: list[str] = Field(default_factory=list)
    send_to_llm: bool | list[str] = Field(default_factory=lambda: ["title", "domain"])

    def get_allowlist(self) -> list[str]:
        """Mengambil daftar domain yang diizinkan (allowlist atau allow_domains)."""
        return self.allowlist if self.allowlist else self.allow_domains


class AppSourceSettings(StrictBaseModel):
    """Konfigurasi sumber pengumpulan aktivitas aplikasi desktop (AppActivity)."""

    enabled: bool = True
    work_profile: WorkProfile | None = None
    recent_dir: Path | None = None

    def get_recent_dir(self) -> Path:
        """Mengembalikan direktori Windows Recent aktif, atau fallback default OS."""
        if self.recent_dir is not None:
            return self.recent_dir
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Microsoft" / "Windows" / "Recent"
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Recent"


class SourcesSettings(StrictBaseModel):
    git: GitSourceSettings = Field(default_factory=GitSourceSettings)
    notes: NotesSourceSettings = Field(default_factory=NotesSourceSettings)
    browser: BrowserSourceSettings = Field(default_factory=BrowserSourceSettings)
    browser_history: BrowserSourceSettings | None = None
    app: AppSourceSettings = Field(default_factory=AppSourceSettings)

    def get_browser(self) -> BrowserSourceSettings:
        """Mengambil konfigurasi browser yang aktif (browser_history atau browser)."""
        return self.browser_history if self.browser_history is not None else self.browser


class NotifySettings(StrictBaseModel):
    channels: list[str] = Field(default_factory=lambda: ["toast"])
    notify_on_success: bool = False


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


def load_dotenv(env_path: Path | None = None) -> None:
    """Memuat variabel dari file .env lokal jika ada dan belum disetel di lingkungan sistem."""
    target = env_path or (find_repo_root() / ".env")
    if not target.exists():
        return
    try:
        content = target.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def load_config(
    path: str | Path | None = None,
    root_dir: Path | None = None,
) -> AppConfig:
    """Memuat dan memvalidasi konfigurasi YAML dengan skema ketat."""
    root = (root_dir or find_repo_root()).resolve()
    load_dotenv(root / ".env")

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
    if config.sources.git.repositories:
        config.sources.git.repositories = [
            str(resolve_path(r, root)) for r in config.sources.git.repositories
        ]
    if config.sources.app.recent_dir is not None:
        config.sources.app.recent_dir = resolve_path(config.sources.app.recent_dir, root)

    return config


def clean_domain(domain: str) -> str:
    """Membersihkan string domain: membuang protokol, port, path, trailing slash, dan spasi.

    Contoh:
    - 'https://figma.com/' -> 'figma.com'
    - 'http://dribbble.com/shots' -> 'dribbble.com'
    - '  APP.POWERBI.COM:443/report  ' -> 'app.powerbi.com'
    """
    s = str(domain).strip()
    if not s:
        return ""
    # Hapus protokol
    if s.lower().startswith("https://"):
        s = s[8:]
    elif s.lower().startswith("http://"):
        s = s[7:]
    # Buang trailing slashes dan whitespace
    s = s.rstrip("/").strip()
    # Ambil bagian hostname sebelum slash pertama atau port
    if "/" in s:
        s = s.split("/")[0].strip()
    if ":" in s:
        s = s.split(":")[0].strip()
    return s.lower()


def merge_browser_domains(
    existing_domains: Sequence[str],
    profile_domains: Sequence[str],
) -> list[str]:
    """Menggabungkan domain peramban dari profil kerja ke daftar domain yang sudah ada.

    Menjaga urutan domain kustom pengguna yang telah ada sebelumnya, dan menambahkan domain
    profil kerja baru tanpa duplikasi (case-insensitive). Operasi bersifat idempoten.
    """
    seen: set[str] = set()
    result: list[str] = []

    for d in [*existing_domains, *profile_domains]:
        cleaned = clean_domain(d)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    return result


def sync_work_profile_browser_domains(
    config: AppConfig,
    profile: WorkProfile | None = None,
) -> list[str]:
    """Menyinkronkan browser_domains dari WorkProfile aktif ke sources.browser.allow_domains pada AppConfig."""
    browser_cfg = config.sources.get_browser()
    if profile is None:
        if not config.sources.app.enabled:
            return browser_cfg.get_allowlist()
        target_profile = config.sources.app.work_profile
    else:
        target_profile = profile

    if target_profile is None or not target_profile.browser_domains:
        return browser_cfg.get_allowlist()

    merged = merge_browser_domains(
        browser_cfg.get_allowlist(),
        target_profile.browser_domains,
    )
    browser_cfg.allow_domains = merged
    if browser_cfg.allowlist:
        browser_cfg.allowlist = merged
    return merged


def update_config_browser_domains(
    config_path: Path | str,
    profile_or_domains: WorkProfile | Sequence[str],
) -> Path:
    """Menyimpan pembaruan browser allowlist hasil sinkronisasi WorkProfile ke file YAML config.

    Mempertahankan komentar dan struktur file jika memungkinkan, serta memastikan
    file hasil pembaruan tetap valid menurut skema AppConfig.

    Raises:
        ConfigurationError: Jika file konfigurasi tidak ditemukan atau tidak valid.
    """
    target = Path(config_path).resolve()
    if not target.exists():
        raise ConfigurationError(f"File konfigurasi tidak ditemukan: {target}")

    try:
        raw_text = target.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Sintaks YAML tidak valid di {target}: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"Gagal membaca file konfigurasi {target}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ConfigurationError(f"Isi file konfigurasi harus berupa dictionary: {target}")

    if isinstance(profile_or_domains, WorkProfile):
        profile_domains = profile_or_domains.browser_domains
    else:
        profile_domains = list(profile_or_domains)

    sources_dict = parsed.setdefault("sources", {})
    if not isinstance(sources_dict, dict):
        sources_dict = {}
        parsed["sources"] = sources_dict

    browser_dict = sources_dict.setdefault("browser", {})
    if not isinstance(browser_dict, dict):
        browser_dict = {}
        sources_dict["browser"] = browser_dict

    allow_key = "allowlist" if "allowlist" in browser_dict else "allow_domains"
    existing_domains = browser_dict.get(allow_key, [])
    if not isinstance(existing_domains, list):
        existing_domains = []

    merged = merge_browser_domains(existing_domains, profile_domains)
    browser_dict[allow_key] = merged

    # Coba ganti langsung blok/flow allow_domains/allowlist pada teks asli untuk mempertahankan komentar
    formatted_json = json.dumps(merged)
    pattern = re.compile(
        rf"(^[ \t]*{allow_key}[ \t]*:[ \t]*)(?:\[[^\]]*\]|(?:\r?\n[ \t]*-[ \t]*[^\r\n]+)+)",
        re.MULTILINE,
    )

    if pattern.search(raw_text):
        new_text = pattern.sub(rf"\g<1>{formatted_json}", raw_text, count=1)
    else:
        new_text = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)

    # Validasi bahwa hasil pembaruan valid menurut skema AppConfig
    try:
        re_parsed = yaml.safe_load(new_text)
        AppConfig.model_validate(re_parsed)
    except (yaml.YAMLError, ValidationError) as exc:
        logger.debug(
            "Regex update allow_domains tidak valid, fallback ke safe_dump: %s",
            exc,
        )
        new_text = yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True)
        re_parsed = yaml.safe_load(new_text)
        try:
            AppConfig.model_validate(re_parsed)
        except ValidationError as val_exc:
            raise ConfigurationError(
                f"Hasil persistensi konfigurasi tidak valid: {val_exc}"
            ) from val_exc

    target.write_text(new_text, encoding="utf-8")
    return target

