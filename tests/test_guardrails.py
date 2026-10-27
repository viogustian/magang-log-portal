"""Penjaga statis: pelanggaran prinsip keamanan akan gagal di CI, bukan baru ketahuan di produksi."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "magang_log"
SOURCES = {p: p.read_text(encoding="utf-8") for p in SRC.rglob("*.py")}


def _offenders(pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return [f"{p.name}:{i}" for p, t in SOURCES.items() for i, line in enumerate(t.splitlines(), 1)
            if rx.search(line) and not line.lstrip().startswith("#")]  # fmt: skip


def test_location_is_never_overridden_in_production_code() -> None:
    assert _offenders(r"set_geolocation|geolocation\s*=|\"geolocation\"\s*:") == []


def test_geolocation_permission_is_granted_only_per_origin() -> None:
    text = (SRC / "portal" / "playwright_portal.py").read_text(encoding="utf-8")
    assert 'grant_permissions(["geolocation"], origin=' in text
    assert 'permissions=["geolocation"]' not in text  # akan berlaku untuk semua origin


def test_no_credential_typing_and_no_arbitrary_js() -> None:
    assert _offenders(r"(?i)get_by_label\([^)]*(password|kata sandi|otp)") == []
    assert _offenders(r"\.evaluate\(|\.add_init_script\(|\.eval_on_selector") == []


def test_no_llm_client_in_portal_package() -> None:
    portal_text = "\n".join(t for p, t in SOURCES.items() if "portal" in p.parts)
    assert not re.search(
        r"(?i)^\s*(import|from)\s+(anthropic|openai|google\.genai|litellm)", portal_text, re.M
    )


def test_all_portal_selectors_live_in_selectors_module() -> None:
    # Selain selectors.py, tidak boleh ada pemanggilan locator/get_by_* langsung.
    offenders = [
        f"{p.name}:{i}"
        for p, t in SOURCES.items()
        if p.name != "selectors.py"
        for i, line in enumerate(t.splitlines(), 1)
        if re.search(r"\.(get_by_\w+|locator)\(", line)
    ]
    assert offenders == []
