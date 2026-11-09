"""Kolektor bukti aktivitas dari log dan cache sesi aplikasi desktop (app:session_log)."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from .base import Evidence, SourceConfig
from .recent import sanitize_path

if TYPE_CHECKING:
    from ..workprofile import WorkProfile

logger = logging.getLogger(__name__)

# Pola regex timestamp ISO dan variasi standar
TIMESTAMP_REGEX = re.compile(
    r"\b(\d{4}[-/]\d{2}[-/]\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?)\b"
)

# Pola regex untuk mendeteksi token/kunci rahasia dalam detail log
SENSITIVE_PARAM_REGEX = re.compile(
    r"(?i)\b(token|password|passwd|secret|api_key|apikey|key|auth|bearer)\s*([:=])\s*([^\s,;\"']+)"
)

# Kata kunci operasi aktif aplikasi desktop yang relevan untuk bukti
OPERATION_KEYWORDS = {
    "save",
    "saved",
    "saving",
    "export",
    "exported",
    "exporting",
    "session",
    "opened",
    "closed",
    "edit",
    "editing",
    "duration",
    "render",
    "rendered",
    "build",
    "compile",
    "publish",
    "published",
    "commit",
}

# Ekstensi file proyek umum untuk ekstraksi nama proyek dari teks log
PROJECT_EXTENSIONS_REGEX = re.compile(
    r"\b([A-Za-z0-9_.\-]+?\.(?:pbix|pbit|fig|xd|sketch|xlsx|xls|csv|blend|aep|prproj|py|ts|js|json|sql|md|docx|pptx))\b",
    re.IGNORECASE,
)


def sanitize_log_detail(detail: str) -> str:
    """Membersihkan teks detail log dari direktori pengguna lokal dan mereduksi parameter sensitif."""
    # Normalkan slash terlebih dahulu
    p_str = detail.replace("\\", "/")
    # Ganti path direktori user Windows yang tertanam di dalam kalimat
    sanitized = re.sub(r"\b[A-Za-z]:/[Uu]sers/[^/\s,\";']+", "~", p_str)
    sanitized = re.sub(r"\b/[Uu]sers/[^/\s,\";']+", "~", sanitized)
    sanitized = re.sub(r"~/{2,}", "~/", sanitized)
    # Reduksi parameter kredensial atau token sensitif
    sanitized = SENSITIVE_PARAM_REGEX.sub(r"\1\2[REDACTED]", sanitized)
    return sanitized.strip()


def _parse_iso_string(s: str) -> datetime | None:
    """Mengurai string berformat ISO ke UTC datetime."""
    cleaned = s.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_timestamp(raw_val: Any) -> datetime | None:
    """Mengurai berbagai representasi timestamp string/numerik menjadi UTC datetime."""
    if isinstance(raw_val, (int, float)):
        try:
            return datetime.fromtimestamp(raw_val, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    if not isinstance(raw_val, str) or not raw_val.strip():
        return None

    # Coba ISO format standar langsung
    dt = _parse_iso_string(raw_val)
    if dt is not None:
        return dt

    # Coba ekstrak pola regex timestamp
    match = TIMESTAMP_REGEX.search(raw_val.strip())
    if match:
        matched_str = match.group(1).replace("/", "-").replace(" ", "T")
        return _parse_iso_string(matched_str)

    return None


def _match_path_or_glob(target_path: Path, seen: set[str], resolved: list[Path]) -> None:
    """Menambahkan berkas tunggal atau hasil ekspansi glob ke list resolved tanpa duplikasi."""
    path_str = str(target_path)
    if "*" in path_str or "?" in path_str:
        parent = target_path.parent
        file_pat = target_path.name
        if parent.exists() and parent.is_dir():
            for match in parent.glob(file_pat):
                if match.is_file() and str(match) not in seen:
                    seen.add(str(match))
                    resolved.append(match)
    elif target_path.is_file() and path_str not in seen:
        seen.add(path_str)
        resolved.append(target_path)


def resolve_log_files(
    patterns: Sequence[str],
    env_overrides: dict[str, Path | str] | None = None,
    base_dirs: Sequence[Path | str] | None = None,
) -> list[Path]:
    """Menyelesaikan pola berkas log (termasuk variabel lingkungan dan glob) ke path berkas aktual."""
    overrides = env_overrides or {}
    localappdata_val = overrides.get("LOCALAPPDATA") or os.environ.get("LOCALAPPDATA")
    appdata_val = overrides.get("APPDATA") or os.environ.get("APPDATA")

    local_path = Path(localappdata_val) if localappdata_val else (Path.home() / "AppData" / "Local")
    roaming_path = Path(appdata_val) if appdata_val else (Path.home() / "AppData" / "Roaming")

    candidate_bases: list[Path] = [local_path, roaming_path]
    if base_dirs:
        for b in base_dirs:
            candidate_bases.append(Path(b))

    resolved_files: list[Path] = []
    seen: set[str] = set()

    for pattern in patterns:
        clean_pat = pattern.strip()
        if not clean_pat:
            continue

        # Kasus 1: Pola memuat variabel %LOCALAPPDATA% atau %APPDATA%
        if "%" in clean_pat:
            expanded = clean_pat
            expanded = re.sub(
                r"%LOCALAPPDATA%",
                str(local_path).replace("\\", "/"),
                expanded,
                flags=re.IGNORECASE,
            )
            expanded = re.sub(
                r"%APPDATA%",
                str(roaming_path).replace("\\", "/"),
                expanded,
                flags=re.IGNORECASE,
            )
            _match_path_or_glob(Path(expanded), seen, resolved_files)
            continue

        # Kasus 2: Pola absolut
        p_obj = Path(clean_pat)
        if p_obj.is_absolute():
            _match_path_or_glob(p_obj, seen, resolved_files)
            continue

        # Kasus 3: Pola relatif terhadap kandidat direktori basis
        for base in candidate_bases:
            if not base.exists() or not base.is_dir():
                continue

            if "*" in clean_pat or "?" in clean_pat:
                for match in base.glob(clean_pat):
                    if match.is_file() and str(match) not in seen:
                        seen.add(str(match))
                        resolved_files.append(match)
            else:
                target = base / clean_pat
                if target.is_file() and str(target) not in seen:
                    seen.add(str(target))
                    resolved_files.append(target)

    return resolved_files


def _extract_project_name(text: str) -> str:
    """Mengekstrak nama berkas proyek dari baris teks log."""
    match = PROJECT_EXTENSIONS_REGEX.search(text)
    if match:
        return match.group(1)
    # Jika tidak ada ekstensi spesifik, cari kata di dalam tanda kutip
    quoted = re.search(r"['\"]([^'\"]+\.[a-zA-Z0-9]+)['\"]", text)
    if quoted:
        return Path(quoted.group(1)).name
    return ""


def parse_log_content(
    content: str,
    app_name: str,
    target_date: date,
) -> list[Evidence]:
    """Mem-parse konten teks atau JSON log aplikasi menjadi list Evidence."""
    evidence_items: list[Evidence] = []
    seen_dedup: set[tuple[str, str, datetime]] = set()

    lines = content.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Coba periksa apakah baris berformat JSON
        is_json = stripped.startswith("{") and stripped.endswith("}")
        if is_json:
            try:
                record = json.loads(stripped)
                if isinstance(record, dict):
                    # Ekstrak timestamp
                    ts_val = (
                        record.get("timestamp")
                        or record.get("ts")
                        or record.get("time")
                        or record.get("datetime")
                        or record.get("date")
                    )
                    dt = _parse_timestamp(ts_val)
                    if dt is None or dt.date() != target_date:
                        continue

                    # Ekstrak project & action
                    project = str(
                        record.get("project")
                        or record.get("file")
                        or record.get("document")
                        or record.get("name")
                        or record.get("model")
                        or ""
                    )
                    action = str(
                        record.get("action")
                        or record.get("event")
                        or record.get("operation")
                        or record.get("type")
                        or record.get("message")
                        or ""
                    )
                    duration = record.get("duration") or record.get("duration_minutes")

                    clean_project = Path(project).name if project else "Session"
                    title = f"{app_name} - {clean_project}"

                    detail_parts: list[str] = []
                    if action:
                        detail_parts.append(action.capitalize())
                    if project:
                        detail_parts.append(f"project {sanitize_path(project)}")
                    if duration:
                        detail_parts.append(f"(duration: {duration} min)")
                    if not detail_parts:
                        detail_parts.append(f"Session activity for {app_name}")

                    raw_detail = " ".join(detail_parts)
                    sanitized_detail = sanitize_log_detail(raw_detail)

                    dedup_key = (title, sanitized_detail, dt)
                    if dedup_key in seen_dedup:
                        continue
                    seen_dedup.add(dedup_key)

                    ev = Evidence(
                        source="app",
                        kind="app:session_log",
                        strength="strong",
                        title=title,
                        detail=sanitized_detail,
                        ts=dt,
                        work_date=target_date,
                    )
                    evidence_items.append(ev)
                    continue
            except json.JSONDecodeError:
                pass

        # Baris teks standar
        ts_match = TIMESTAMP_REGEX.search(stripped)
        if not ts_match:
            continue

        raw_ts = ts_match.group(1)
        dt = _parse_timestamp(raw_ts)
        if dt is None or dt.date() != target_date:
            continue

        # Periksa apakah baris memuat operasi kerja relevan
        line_lower = stripped.lower()
        if not any(k in line_lower for k in OPERATION_KEYWORDS):
            continue

        # Ekstrak nama proyek jika tersedia
        project_name = _extract_project_name(stripped)
        title = f"{app_name} - {project_name}" if project_name else f"{app_name} - Session Activity"

        # Buang prefix timestamp dari detail agar ringkas dan bersih
        op_text = stripped[ts_match.end() :].strip()
        # Bersihkan prefix umum seperti [INFO], [DEBUG], dll.
        op_text = re.sub(r"^\[[A-Za-z]+\]\s*", "", op_text)
        if not op_text:
            op_text = stripped

        sanitized_detail = sanitize_log_detail(op_text)
        dedup_key = (title, sanitized_detail, dt)
        if dedup_key in seen_dedup:
            continue
        seen_dedup.add(dedup_key)

        ev = Evidence(
            source="app",
            kind="app:session_log",
            strength="strong",
            title=title,
            detail=sanitized_detail,
            ts=dt,
            work_date=target_date,
        )
        evidence_items.append(ev)

    return evidence_items


class ApplicationSessionLogParser:
    """Kolektor bukti kuat (strong) dari berkas log dan cache sesi aplikasi desktop aktif."""

    name: str = "app_session_log"

    def __init__(
        self,
        base_dirs: Sequence[Path | str] | None = None,
        env_overrides: dict[str, Path | str] | None = None,
        work_profile: WorkProfile | None = None,
    ) -> None:
        self.base_dirs = list(base_dirs) if base_dirs else []
        self.env_overrides = dict(env_overrides) if env_overrides else {}
        self.work_profile = work_profile

    def scan(
        self,
        target_date: date,
        profile: WorkProfile | None = None,
    ) -> list[Evidence]:
        """Memindai berkas log sesi untuk aplikasi yang aktif pada profil kerja."""
        active_profile = profile if profile is not None else self.work_profile
        if active_profile is None:
            logger.debug(
                "Tidak ada WorkProfile aktif, pemindaian log sesi dibatalkan (zero surveillance)."
            )
            return []

        if not active_profile.applications:
            logger.debug("WorkProfile tidak memiliki aplikasi desktop yang terdaftar.")
            return []

        all_evidence: list[Evidence] = []

        # Hanya pindai aplikasi yang explicitly terdaftar di WorkProfile
        for app in active_profile.applications:
            if not app.log_patterns:
                continue

            # Selesaikan pola log ke berkas aktual
            log_files = resolve_log_files(
                patterns=app.log_patterns,
                env_overrides=self.env_overrides,
                base_dirs=self.base_dirs,
            )

            for log_file in log_files:
                try:
                    content = log_file.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.debug("Gagal membaca berkas log %s: %s", log_file, exc)
                    continue

                items = parse_log_content(
                    content=content,
                    app_name=app.name,
                    target_date=target_date,
                )
                all_evidence.extend(items)

        return all_evidence

    def collect(
        self,
        target_date: date,
        config: SourceConfig = None,
    ) -> list[Evidence]:
        """Mengumpulkan bukti log sesi untuk target_date (protokol Collector)."""
        profile = self.work_profile
        from ..workprofile import WorkProfile

        if isinstance(config, WorkProfile):
            profile = config
        elif isinstance(config, dict) and "profile" in config:
            profile = config["profile"]
        elif hasattr(config, "profile") and isinstance(config.profile, WorkProfile):
            profile = config.profile

        return self.scan(target_date, profile=profile)


# Alias untuk kemudahan penggunaan
SessionLogParser = ApplicationSessionLogParser
SessionLogCollector = ApplicationSessionLogParser
