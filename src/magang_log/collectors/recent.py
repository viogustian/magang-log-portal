"""Kolektor bukti aktivitas Windows Recent Items (.lnk) dengan filtrasi allowlist ketat."""

from __future__ import annotations

import logging
import os
import re
import struct
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Evidence, SourceConfig

if TYPE_CHECKING:
    from ..workprofile import WorkProfile

logger = logging.getLogger(__name__)

# Selisih antara Windows FILETIME Epoch (1601-01-01) dan Unix Epoch (1970-01-01) dalam unit 100-ns
WINDOWS_FILETIME_EPOCH_OFFSET = 116_444_736_000_000_000
MS_SHLLINK_CLSID = b"\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46"


@dataclass(frozen=True)
class LnkInfo:
    """Informasi hasil ekstraksi dari berkas pintasan .lnk Windows."""

    target_path: str
    modified_time: datetime


def sanitize_path(path: str | Path) -> str:
    """Membersihkan path file lokal Windows dengan mengganti direktori pengguna menjadi ~ dan menormalkan slash."""
    p_str = str(path).replace("\\", "/")
    # Ganti drive:\Users\<user> atau /Users/<user> dengan ~
    sanitized = re.sub(r"^[A-Za-z]:/[Uu]sers/[^/]+", "~", p_str)
    sanitized = re.sub(r"^/[Uu]sers/[^/]+", "~", sanitized)
    sanitized = re.sub(r"^~/{2,}", "~/", sanitized)
    return sanitized


def create_synthetic_lnk(
    target_path: str,
    write_time: datetime | None = None,
) -> bytes:
    """Membuat byte payload berkas .lnk sintetis (MS-SHLLINK) untuk keperluan pengujian."""
    header_size = 76
    flags = 0x02  # HasLinkInfo
    file_attrs = 0
    creation_time = 0
    access_time = 0

    if write_time is not None:
        if write_time.tzinfo is None:
            wt = write_time.replace(tzinfo=timezone.utc)
        else:
            wt = write_time.astimezone(timezone.utc)
        filetime = int((wt.timestamp() * 10_000_000) + WINDOWS_FILETIME_EPOCH_OFFSET)
    else:
        filetime = 0

    header = (
        struct.pack("<I", header_size)
        + MS_SHLLINK_CLSID
        + struct.pack("<I", flags)
        + struct.pack("<I", file_attrs)
        + struct.pack("<Q", creation_time)
        + struct.pack("<Q", access_time)
        + struct.pack("<Q", filetime)
        + struct.pack("<I", 0)  # FileSize
        + struct.pack("<I", 0)  # IconIndex
        + struct.pack("<I", 1)  # ShowCommand
        + struct.pack("<H", 0)  # HotKey
        + struct.pack("<H", 0)  # Reserved1
        + struct.pack("<I", 0)  # Reserved2
        + struct.pack("<I", 0)  # Reserved3
    )

    path_bytes = target_path.encode("utf-8") + b"\x00"
    link_info_header_size = 28  # 0x1C
    local_base_path_offset = link_info_header_size
    link_info_size = link_info_header_size + len(path_bytes)
    link_info_flags = 1  # VolumeIDAndLocalBasePath

    link_info = (
        struct.pack(
            "<IIIIIII",
            link_info_size,
            link_info_header_size,
            link_info_flags,
            0,  # VolumeIDOffset
            local_base_path_offset,
            0,  # CommonNetworkRelativeLinkOffset
            0,  # CommonPathSuffixOffset
        )
        + path_bytes
    )

    return header + link_info


def parse_lnk(data_or_path: bytes | Path | str) -> LnkInfo | None:
    """Mem-parse berkas pintasan .lnk Windows secara lightweight tanpa pustaka biner eksternal."""
    data: bytes
    file_mtime: datetime | None = None

    if isinstance(data_or_path, (str, Path)):
        p = Path(data_or_path)
        if not p.is_file():
            return None
        try:
            data = p.read_bytes()
            st = p.stat()
            file_mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        except OSError as exc:
            logger.debug("Gagal membaca berkas .lnk %s: %s", p, exc)
            return None
    elif isinstance(data_or_path, (bytes, bytearray)):
        data = bytes(data_or_path)
    else:
        return None

    if len(data) < 76:
        return None

    try:
        header_size = struct.unpack("<I", data[:4])[0]
        if header_size != 76:
            return None

        clsid = data[4:20]
        if clsid != MS_SHLLINK_CLSID:
            return None

        flags = struct.unpack("<I", data[20:24])[0]
        raw_write_time = struct.unpack("<Q", data[44:52])[0]

        mod_dt: datetime | None = None
        if raw_write_time != 0:
            try:
                ts = (raw_write_time - WINDOWS_FILETIME_EPOCH_OFFSET) / 10_000_000
                if ts > 0:
                    mod_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                mod_dt = None

        if mod_dt is None:
            mod_dt = file_mtime or datetime.now(timezone.utc)

        target_path: str = ""
        offset = 76

        has_id_list = bool(flags & 0x01)
        if has_id_list:
            if len(data) < offset + 2:
                return None
            id_list_size = struct.unpack("<H", data[offset : offset + 2])[0]
            offset += 2 + id_list_size

        has_link_info = bool(flags & 0x02)
        if has_link_info and len(data) >= offset + 28:
            link_info_header_size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
            local_base_path_offset = struct.unpack("<I", data[offset + 16 : offset + 20])[0]

            if local_base_path_offset > 0:
                p_start = offset + local_base_path_offset
                if p_start < len(data):
                    path_slice = data[p_start:].split(b"\x00", 1)[0]
                    target_path = path_slice.decode("utf-8", errors="replace")

            # Fallback ke Unicode path jika ada LinkInfoHeaderSize >= 0x24
            if not target_path and link_info_header_size >= 36 and len(data) >= offset + 32:
                local_base_path_unicode_offset = struct.unpack(
                    "<I", data[offset + 28 : offset + 32]
                )[0]
                if local_base_path_unicode_offset > 0:
                    p_uni_start = offset + local_base_path_unicode_offset
                    if p_uni_start < len(data):
                        uni_slice = data[p_uni_start:].split(b"\x00\x00", 1)[0]
                        target_path = uni_slice.decode("utf-16le", errors="replace")

        # Fallback binary regex search jika target_path masih kosong
        if not target_path:
            match = re.search(rb"[A-Za-z]:\\[^\x00\r\n\t]+", data)
            if match:
                target_path = match.group(0).decode("utf-8", errors="replace")

        if not target_path:
            return None

        return LnkInfo(target_path=target_path, modified_time=mod_dt)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Gagal mem-parse payload .lnk: %s", exc)
        return None


def _resolve_app_name(profile: WorkProfile | None, ext: str) -> str:
    """Mencari nama kanonikal aplikasi berdasarkan ekstensi file dalam WorkProfile."""
    if profile is not None:
        for app in profile.applications:
            if ext in (e.lower() for e in app.file_extensions):
                return app.name
    clean_ext = ext.lstrip(".").upper()
    return f"{clean_ext} Application" if clean_ext else "Desktop Application"


class RecentItemsScanner:
    """Kolektor bukti aktivitas Windows Recent Items (.lnk) dengan filtrasi allowlist ketat."""

    name: str = "recent"

    def __init__(
        self,
        recent_dir: Path | str | None = None,
        work_profile: WorkProfile | None = None,
    ) -> None:
        if recent_dir is not None:
            self.recent_dir = Path(recent_dir)
        else:
            appdata = os.environ.get("APPDATA")
            if appdata:
                self.recent_dir = Path(appdata) / "Microsoft" / "Windows" / "Recent"
            else:
                self.recent_dir = (
                    Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Recent"
                )
        self.work_profile = work_profile

    def scan(
        self,
        target_date: date,
        profile: WorkProfile | None = None,
    ) -> list[Evidence]:
        """Memindai direktori Recent Items untuk target_date dengan strict opt-in allowlist."""
        active_profile = profile if profile is not None else self.work_profile
        if active_profile is None:
            logger.debug("Tidak ada WorkProfile aktif, pemindaian Recent Items dibatalkan.")
            return []

        allowed_extensions = active_profile.all_file_extensions()
        if not allowed_extensions:
            logger.debug(
                "WorkProfile tidak memiliki ekstensi berkas yang dipantau (zero surveillance boundary)."
            )
            return []

        if not self.recent_dir.exists() or not self.recent_dir.is_dir():
            logger.debug(
                "Direktori Recent Items tidak ditemukan atau tidak dapat diakses: %s",
                self.recent_dir,
            )
            return []

        try:
            entries = list(self.recent_dir.iterdir())
        except OSError as exc:
            logger.debug(
                "Gagal membaca isi direktori Recent Items %s: %s",
                self.recent_dir,
                exc,
            )
            return []

        evidence_items: list[Evidence] = []
        seen_targets: set[str] = set()

        for entry in sorted(entries):
            if not entry.is_file():
                continue
            if entry.suffix.lower() != ".lnk":
                continue

            # Strict opt-in allowlist gating sebelum membuka atau membaca isi berkas
            # Pintasan Windows Recent umumnya bernama <nama_berkas>.<ext>.lnk
            stem = entry.stem
            pre_ext = Path(stem).suffix.lower()
            if pre_ext not in allowed_extensions:
                continue

            info = parse_lnk(entry)
            if info is None or not info.target_path:
                continue

            target_ext = Path(info.target_path).suffix.lower()
            if target_ext not in allowed_extensions:
                continue

            mod_dt = info.modified_time
            if mod_dt.tzinfo is None:
                mod_dt = mod_dt.replace(tzinfo=timezone.utc)
            else:
                mod_dt = mod_dt.astimezone(timezone.utc)

            if mod_dt.date() != target_date:
                continue

            sanitized = sanitize_path(info.target_path)
            if sanitized in seen_targets:
                continue
            seen_targets.add(sanitized)

            filename = Path(info.target_path).name
            app_name = _resolve_app_name(active_profile, target_ext)

            ev = Evidence(
                source="app",
                kind="app:recent_file",
                strength="weak",
                title=f"{app_name} - {filename}",
                detail=f"Project file opened from {sanitized}",
                ts=mod_dt,
                work_date=target_date,
            )
            evidence_items.append(ev)

        return evidence_items

    def collect(
        self,
        target_date: date,
        config: SourceConfig = None,
    ) -> list[Evidence]:
        """Mengumpulkan bukti Recent Items untuk target_date (mengimplementasikan protokol Collector)."""
        profile = self.work_profile
        from ..workprofile import WorkProfile

        if isinstance(config, WorkProfile):
            profile = config
        elif isinstance(config, dict) and "profile" in config:
            profile = config["profile"]
        elif hasattr(config, "profile") and isinstance(config.profile, WorkProfile):
            profile = config.profile

        return self.scan(target_date, profile=profile)
