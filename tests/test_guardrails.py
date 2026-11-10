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
    # Memastikan tidak ada spoofing koordinat buatan; hanya bridging sensor fisik OS di device_location yang sah
    offenders = [
        o for o in _offenders(r"set_geolocation|geolocation\s*=|\"geolocation\"\s*:")
        if not o.startswith("playwright_portal.py")
    ]
    assert offenders == []


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


# ── Guardrails AST (Abstract Syntax Tree) ───────────────────────────────────


def test_ast_guardrail_zero_llm_imports_in_portal_package() -> None:
    """AST guardrail: memastikan paket portal TIDAK PERNAH mengimpor SDK LLM apa pun."""
    import ast

    forbidden = (
        "anthropic",
        "openai",
        "google.genai",
        "google.generativeai",
        "litellm",
        "langchain",
        "transformers",
    )
    violations: list[str] = []

    for path, text in SOURCES.items():
        if "portal" not in path.parts:
            continue
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(f) for f in forbidden):
                        violations.append(f"{path.name}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if any(node.module.startswith(f) for f in forbidden):
                    violations.append(f"{path.name}:{node.lineno} from {node.module}")

    assert violations == []


def test_ast_guardrail_zero_set_geolocation_overrides_in_production_code() -> None:
    """AST guardrail: memastikan pemanggilan set_geolocation tidak ada di kode produksi."""
    import ast

    violations: list[str] = []

    for path, text in SOURCES.items():
        if path.name == "playwright_portal.py":
            continue  # Bridging resmi sensor fisik OS Windows (device_location.py)
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "set_geolocation":
                    violations.append(f"{path.name}:{node.lineno} .set_geolocation()")
                elif isinstance(node.func, ast.Name) and node.func.id == "set_geolocation":
                    violations.append(f"{path.name}:{node.lineno} set_geolocation()")

    assert violations == []


def test_ast_guardrail_zero_hardcoded_password_or_otp_selectors() -> None:
    """AST guardrail: memastikan tidak ada pengetikan atau selector password/OTP pada form."""
    import ast

    forbidden_terms = {"password", "kata sandi", "otp", "passcode", "pin"}
    violations: list[str] = []

    for path, text in SOURCES.items():
        if path.name == "playwright_portal.py":
            continue  # Bridging resmi sensor fisik OS Windows (device_location.py)
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {
                    "get_by_label",
                    "get_by_text",
                    "get_by_placeholder",
                    "fill",
                    "type",
                }:
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            val = arg.value.lower()
                            if any(term in val for term in forbidden_terms):
                                violations.append(
                                    f"{path.name}:{node.lineno} {node.func.attr}({arg.value!r})"
                                )

    assert violations == []
