"""Mesin sanitasi privasi deterministik untuk path, rahasia, username, dan pembatasan panjang data."""

from __future__ import annotations

import getpass
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

from .base import Evidence, compute_evidence_id

logger = logging.getLogger(__name__)

# Pola regex rahasia dan parameter sensitif
_PASSWORD_PARAM_RE = re.compile(r"""(?i)\bpassword\s*[:=]\s*(?:'[^']*'|"[^"]*"|\S+)""")

_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Bearer tokens
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=+/]{16,}\b"),
    # GitHub personal access tokens
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    # Slack tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    # GitLab personal access tokens
    re.compile(r"\bglpat-[A-Za-z0-9\-]{20,}\b"),
    # AWS access keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Prefix api keys / secret keys
    re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),
    # Assignment key / token
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|\S+)"
    ),
    re.compile(r"(?i)\btoken\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|\S{16,})"),
)

# Pola regex alamat IPv4 privat: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
_PRIVATE_IPV4_RE = re.compile(
    r"\b(?:10(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}|"
    r"192\.168(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){2}|"
    r"172\.(?:1[6-9]|2[0-9]|3[0-1])(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){2})\b"
)

# Pola regex alamat email
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Pola regex path absolut Windows dan direktori home Unix (termasuk quoted path dan Program Files)
_WINDOWS_PATH_RE = re.compile(
    r"""(?:"[A-Za-z]:\\[^"\r\n]+"|'[A-Za-z]:\\[^'\r\n]+'|"""
    r"""[A-Za-z]:\\(?:Program Files(?: \(x86\))?)\\[^ \t\r\n'"`<>|]+|"""
    r"""[A-Za-z]:\\[^ \t\r\n'"`<>|]+)"""
)
_UNIX_HOME_PATH_RE = re.compile(
    r"""(?:"/(?:home|Users)/[^"\r\n]+"|'/(?:home|Users)/[^'\r\n]+'|"""
    r"""(?:/home|/Users)/[^ \t\r\n'"`<>|]+)"""
)


@dataclass(frozen=True)
class PrivacyConfig:
    """Konfigurasi aturan penyaringan privasi deterministik.

    Fields:
    - repo_roots: daftar direktori root repositori untuk mengubah path absolut menjadi relatif
    - custom_usernames: daftar username tambahan yang harus disensor
    - custom_rules: aturan regex kustom tambahan berupa pasangan (pattern, replacement)
    - max_title_length: panjang maksimum string judul/pesan komit (default: 300)
    - max_detail_length: panjang maksimum string detail (default: 1000)
    - redact_paths: aktifkan sensor path absolut (default: True)
    - redact_usernames: aktifkan sensor username lokal OS (default: True)
    - redact_tokens: aktifkan sensor token rahasia & bearer (default: True)
    - redact_passwords: aktifkan sensor parameter password (default: True)
    - redact_ips: aktifkan sensor IPv4 privat (default: True)
    - redact_emails: aktifkan sensor alamat email (default: True)
    """

    repo_roots: Sequence[Path | str] = ()
    custom_usernames: Sequence[str] = ()
    custom_rules: Sequence[tuple[re.Pattern[str] | str, str]] = ()
    max_title_length: int = 300
    max_detail_length: int = 1000
    redact_paths: bool = True
    redact_usernames: bool = True
    redact_tokens: bool = True
    redact_passwords: bool = True
    redact_ips: bool = True
    redact_emails: bool = True


@runtime_checkable
class PrivacyFilter(Protocol):
    """Protokol antarmuka filter privasi untuk menyaring daftar bukti mentah."""

    def sanitize(
        self,
        raw_evidence: list[Evidence],
        rules: PrivacyConfig | None = None,
    ) -> list[Evidence]:
        """Mentransformasikan raw_evidence menjadi list[Evidence] baru yang telah disanitasi."""
        ...


def get_detected_usernames() -> set[str]:
    """Mendeteksi username sistem operasi lokal dari lingkungan eksekusi secara aman."""
    usernames: set[str] = set()
    for env_var in ("USERNAME", "USER", "LOGNAME"):
        val = os.environ.get(env_var)
        if val and len(val.strip()) > 1:
            usernames.add(val.strip())

    try:
        user = getpass.getuser()
        if user and len(user.strip()) > 1:
            usernames.add(user.strip())
    except (KeyError, OSError):
        pass

    try:
        login = os.getlogin()
        if login and len(login.strip()) > 1:
            usernames.add(login.strip())
    except (AttributeError, OSError):
        pass

    return usernames


def _sanitize_path_match(match: re.Match[str], repo_roots: Sequence[Path | str]) -> str:
    """Mengonversi path yang cocok menjadi repo-relative atau [REDACTED_PATH]."""
    raw_match = match.group(0)
    has_leading_quote = False
    if raw_match.startswith(('"', "'")):
        has_leading_quote = True
        raw_match = raw_match[1:]

    trailing_punct = ""
    # Pisahkan tanda baca dan penutup quote di akhir path
    while raw_match and raw_match[-1] in ".,;:!?)]}>\"'":
        char = raw_match[-1]
        raw_match = raw_match[:-1]
        if char in ('"', "'") and has_leading_quote:
            has_leading_quote = False
            continue
        trailing_punct = char + trailing_punct

    if not raw_match:
        return trailing_punct

    # Normalisasi slash untuk string prefix check yang cross-platform
    norm_p = raw_match.replace("\\", "/").rstrip("/")

    for root in repo_roots:
        norm_r = str(root).replace("\\", "/").rstrip("/")
        if norm_p == norm_r:
            return "." + trailing_punct
        if norm_p.startswith(norm_r + "/"):
            rel_str = norm_p[len(norm_r) + 1 :]
            return rel_str + trailing_punct

        # Coba juga perbandingan via Path jika kompatibel
        try:
            p_obj = Path(raw_match).resolve()
            r_obj = Path(root).resolve()
            if p_obj == r_obj or p_obj.is_relative_to(r_obj):
                rel = p_obj.relative_to(r_obj).as_posix()
                return rel + trailing_punct
        except (ValueError, TypeError, OSError):
            continue

    return "[REDACTED_PATH]" + trailing_punct


class DeterministicPrivacyEngine:
    """Implementasi mesin sanitasi privasi deterministik."""

    def __init__(self, default_config: PrivacyConfig | None = None) -> None:
        self.default_config = default_config or PrivacyConfig()

    def sanitize_text(
        self,
        text: str,
        config: PrivacyConfig,
        detected_users: set[str],
        max_length: int | None = None,
    ) -> str:
        """Menyaring konten teks tunggal sesuai urutan aturan deterministik."""
        if not text:
            return ""

        result = text

        # 1. Password parameter
        if config.redact_passwords:
            result = _PASSWORD_PARAM_RE.sub("[REDACTED_PASSWORD]", result)

        # 2. Token berentropi tinggi, API key, & Bearer token
        if config.redact_tokens:
            for pattern in _TOKEN_PATTERNS:
                result = pattern.sub("[REDACTED_TOKEN]", result)

        # 3. Alamat email
        if config.redact_emails:
            result = _EMAIL_RE.sub("[REDACTED_EMAIL]", result)

        # 4. Alamat IPv4 privat
        if config.redact_ips:
            result = _PRIVATE_IPV4_RE.sub("[REDACTED_IP]", result)

        # 5. Path file absolut (Windows drive & Unix home)
        if config.redact_paths:
            result = _WINDOWS_PATH_RE.sub(
                lambda m: _sanitize_path_match(m, config.repo_roots),
                result,
            )
            result = _UNIX_HOME_PATH_RE.sub(
                lambda m: _sanitize_path_match(m, config.repo_roots),
                result,
            )

        # 6. Username sistem operasi & custom usernames
        if config.redact_usernames:
            all_users = set(detected_users)
            for u in config.custom_usernames:
                if u and len(u.strip()) > 1:
                    all_users.add(u.strip())

            for username in sorted(all_users, key=len, reverse=True):
                user_pattern = re.compile(rf"(?i)\b{re.escape(username)}\b")
                result = user_pattern.sub("[USER]", result)

        # 7. Aturan kustom pengguna
        for pattern, replacement in config.custom_rules:
            if isinstance(pattern, str):
                result = re.sub(pattern, replacement, result)
            else:
                result = pattern.sub(replacement, result)

        # 8. Batas panjang karakter
        if max_length is not None and len(result) > max_length:
            result = result[:max_length]

        return result

    def sanitize(
        self,
        raw_evidence: list[Evidence],
        rules: PrivacyConfig | None = None,
    ) -> list[Evidence]:
        """Mentransformasikan bukti mentah menjadi bukti baru yang telah disanitasi."""
        config = rules if rules is not None else self.default_config
        detected_users = get_detected_usernames() if config.redact_usernames else set()

        sanitized_items: list[Evidence] = []
        for item in raw_evidence:
            new_title = self.sanitize_text(
                item.title,
                config=config,
                detected_users=detected_users,
                max_length=config.max_title_length,
            )
            new_detail = self.sanitize_text(
                item.detail,
                config=config,
                detected_users=detected_users,
                max_length=config.max_detail_length,
            )

            # Hitung ulang ID jika title berubah
            new_id = (
                compute_evidence_id(
                    source=item.source,
                    kind=item.kind,
                    ts=item.ts,
                    title=new_title,
                )
                if new_title != item.title
                else item.id
            )

            sanitized_item = Evidence(
                source=item.source,
                kind=item.kind,
                ts=item.ts,
                title=new_title,
                detail=new_detail,
                strength=item.strength,
                id=new_id,
                work_date=item.work_date,
            )
            sanitized_items.append(sanitized_item)

        return sanitized_items


def sanitize_evidence(
    raw_evidence: list[Evidence],
    rules: PrivacyConfig | None = None,
) -> list[Evidence]:
    """Helper fungsi cepat untuk menyaring daftar bukti aktivitas dengan konfigurasi standar."""
    engine = DeterministicPrivacyEngine(default_config=rules)
    return engine.sanitize(raw_evidence, rules=rules)
