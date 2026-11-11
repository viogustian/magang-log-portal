"""SetupWizard service layer for Gemini connectivity testing and role prediction."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import packaging.specifiers
import packaging.version
import yaml
from pydantic import BaseModel, Field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from ...settings import AppConfig, find_repo_root, sync_work_profile_browser_domains
from ...workprofile import WorkProfile, load_presets

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash"


class InstallationGuidance(BaseModel):
    """Windows-specific installation and troubleshooting steps for requirements."""

    download_url: str
    install_steps: list[str]
    verification_command: str
    expected_output: str
    troubleshooting: list[str]


class RequirementItem(BaseModel):
    """System requirement state, minimum required version, and installation guidance."""

    name: str
    min_version: str
    installed_version: str | None = None
    status: Literal["ok", "version_mismatch", "missing"]
    guidance: InstallationGuidance


class FolderValidationResult(BaseModel):
    """Validation report for a single workspace folder path."""

    path: str
    exists: bool
    readable: bool
    is_git: bool
    error: str | None = None


class WizardProgressState(BaseModel):
    """Persistent state representation of SetupWizard progression."""

    current_step: int = 0
    completed_steps: list[int] = Field(default_factory=list)
    step_data: dict[str, Any] = Field(default_factory=dict)


WINDOWS_REQUIREMENTS_GUIDANCE: dict[str, dict[str, Any]] = {
    "Python": {
        "download_url": "https://www.python.org/downloads/windows/",
        "install_steps": [
            "Unduh installer Python 64-bit untuk Windows dari tautan resmi.",
            "Jalankan installer dan pastikan opsi 'Add python.exe to PATH' dicentang sebelum klik Install Now.",
            "Selesaikan proses instalasi dan klik 'Disable path length limit' jika diminta.",
        ],
        "verification_command": "python --version",
        "expected_output": "Python >= 3.12",
        "troubleshooting": [
            "Jika perintah 'python' tidak dikenali di terminal, tutup dan buka ulang terminal/PowerShell.",
            "Periksa System Environment Variables dan pastikan path Python dan Scripts ada di PATH pengguna.",
        ],
    },
    "Playwright": {
        "download_url": "https://playwright.dev/python/docs/intro",
        "install_steps": [
            "Pastikan virtual environment aktif: .\\.venv\\Scripts\\Activate.ps1",
            "Instal paket Playwright: pip install playwright",
            "Unduh binary browser Chromium: playwright install chromium",
        ],
        "verification_command": "playwright --version",
        "expected_output": "Version 1.40+",
        "troubleshooting": [
            "Pastikan binary browser terinstal dengan menjalankan 'playwright install chromium'.",
            "Jika terjadi error PowerShell script execution policy, jalankan 'Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser'.",
        ],
    },
    ".NET SDK": {
        "download_url": "https://dotnet.microsoft.com/download/dotnet/8.0",
        "install_steps": [
            "Unduh .NET SDK 8.0+ Windows x64 Installer.",
            "Jalankan installer hingga selesai.",
        ],
        "verification_command": "dotnet --version",
        "expected_output": "8.0.x",
        "troubleshooting": [
            "Pastikan dotnet ada di System PATH atau restart terminal Anda.",
        ],
    },
    "Git": {
        "download_url": "https://git-scm.com/download/win",
        "install_steps": [
            "Unduh Git for Windows 64-bit installer.",
            "Jalankan installer dengan konfigurasi default (pilih 'Git from the command line and also from 3rd-party software').",
        ],
        "verification_command": "git --version",
        "expected_output": "git version 2.x",
        "troubleshooting": [
            "Tutup dan buka kembali terminal agar PATH Git terbarui.",
        ],
    },
}


def get_guidance_for(name: str) -> InstallationGuidance:
    """Retrieve Windows installation guidance for requirement with fallback."""
    if name in WINDOWS_REQUIREMENTS_GUIDANCE:
        return InstallationGuidance(**WINDOWS_REQUIREMENTS_GUIDANCE[name])

    clean = name.lower()
    for k, v in WINDOWS_REQUIREMENTS_GUIDANCE.items():
        if k.lower() == clean:
            return InstallationGuidance(**v)

    return InstallationGuidance(
        download_url=f"https://pypi.org/project/{name.lower()}/",
        install_steps=[f"Pastikan virtual environment aktif, lalu jalankan: pip install {name}"],
        verification_command=f"python -m pip show {name}",
        expected_output=f"Name: {name}",
        troubleshooting=[
            "Pastikan pip dan setuptools terinstal ke versi terbaru.",
            "Periksa koneksi internet jika instalasi gagal mengunduh wheel.",
        ],
    )


def get_installed_version(name: str) -> str | None:
    """Retrieve installed version of a tool/runtime or package on the host system."""
    clean_name = name.strip()
    norm = clean_name.lower()

    if norm in ("python", "python3"):
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    if norm in ("git",):
        git_bin = shutil.which("git")
        if not git_bin:
            return None
        try:
            res = subprocess.run(
                [git_bin, "--version"], capture_output=True, text=True, check=False, timeout=5
            )
            if res.returncode == 0:
                m = re.search(r"(\d+(\.\d+)+)", res.stdout)
                if m:
                    return m.group(1)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("Failed checking git version: %s", exc)
            return None
        return None

    if norm in (".net sdk", "dotnet", ".net"):
        dotnet_bin = shutil.which("dotnet")
        if not dotnet_bin:
            return None
        try:
            res = subprocess.run(
                [dotnet_bin, "--version"], capture_output=True, text=True, check=False, timeout=5
            )
            if res.returncode == 0:
                m = re.search(r"(\d+(\.\d+)+)", res.stdout)
                if m:
                    return m.group(1)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("Failed checking dotnet version: %s", exc)
            return None
        return None

    if "playwright" in norm:
        try:
            return importlib.metadata.version("playwright")
        except (importlib.metadata.PackageNotFoundError, ValueError):
            pass
        try:
            from playwright._repo_version import version as pw_version

            if pw_version:
                return str(pw_version)
        except ImportError:
            pass
        playwright_bin = shutil.which("playwright")
        if playwright_bin:
            try:
                res = subprocess.run(
                    [playwright_bin, "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if res.returncode == 0:
                    m = re.search(r"(\d+(\.\d+)+)", res.stdout)
                    if m:
                        return m.group(1)
            except (OSError, subprocess.SubprocessError) as exc:
                logger.debug("Failed running playwright CLI: %s", exc)
        return None

    # Python package metadata lookup
    try:
        return importlib.metadata.version(norm)
    except (importlib.metadata.PackageNotFoundError, ValueError):
        pass

    bin_path = shutil.which(norm)
    if bin_path:
        try:
            res = subprocess.run(
                [bin_path, "--version"], capture_output=True, text=True, check=False, timeout=5
            )
            if res.returncode == 0:
                m = re.search(r"(\d+(\.\d+)+)", res.stdout or res.stderr)
                if m:
                    return m.group(1)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("Failed running %s --version: %s", norm, exc)

    return None


def check_requirement_status(
    min_version_spec: str,
    installed_version_str: str | None,
) -> Literal["ok", "version_mismatch", "missing"]:
    """Compare installed version against required version specifier."""
    if not installed_version_str:
        return "missing"

    try:
        v_match = re.search(r"\d+(\.\d+)+", installed_version_str)
        if not v_match:
            return "version_mismatch"
        parsed_installed = packaging.version.parse(v_match.group(0))
    except (packaging.version.InvalidVersion, ValueError, TypeError):
        return "version_mismatch"

    clean_spec = min_version_spec.strip()
    if clean_spec.startswith((">=", "<=", "==", ">", "<", "!=")):
        spec_str = clean_spec
    elif clean_spec:
        spec_str = f">={clean_spec}"
    else:
        return "ok"

    try:
        spec = packaging.specifiers.SpecifierSet(spec_str)
        if parsed_installed in spec:
            return "ok"
        return "version_mismatch"
    except (packaging.specifiers.InvalidSpecifier, ValueError):
        try:
            target_v = packaging.version.parse(clean_spec.lstrip(">=< "))
            if parsed_installed >= target_v:
                return "ok"
            return "version_mismatch"
        except (packaging.version.InvalidVersion, ValueError):
            return "ok"


def scan_system_requirements(root_path: Path | str | None = None) -> list[RequirementItem]:
    """Dynamically parse repository files and inspect host system runtime requirements."""
    root = Path(root_path).resolve() if root_path else find_repo_root()
    pyproject_file = root / "pyproject.toml"

    requirements_to_check: list[tuple[str, str]] = []

    if pyproject_file.exists():
        try:
            data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
            project_section = data.get("project", {})

            # 1. Python version requirement
            req_python = project_section.get("requires-python")
            if req_python:
                requirements_to_check.append(("Python", req_python))

            # 2. Dependencies
            deps = project_section.get("dependencies", [])
            for dep in deps:
                m = re.match(r"^([a-zA-Z0-9_\-]+)(.*)$", dep.strip())
                if m:
                    dep_name, dep_spec = m.group(1), m.group(2).strip()
                    if dep_name.lower() == "playwright":
                        requirements_to_check.append(("Playwright", dep_spec or ">=1.40"))
        except (OSError, ValueError) as exc:
            logger.warning("Failed parsing pyproject.toml for requirements: %s", exc)

    # Check for .python-version
    python_version_file = root / ".python-version"
    if python_version_file.exists():
        try:
            v_str = python_version_file.read_text(encoding="utf-8").strip()
            if v_str and not any(r[0] == "Python" for r in requirements_to_check):
                requirements_to_check.append(("Python", f">={v_str}"))
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("Failed reading .python-version: %s", exc)

    # Fallback requirement definitions if not found
    if not any(r[0] == "Python" for r in requirements_to_check):
        requirements_to_check.append(("Python", ">=3.12"))

    if not any(r[0] == "Playwright" for r in requirements_to_check):
        requirements_to_check.append(("Playwright", ">=1.40"))

    has_dotnet = (
        (root / "desktop").exists()
        or (root / "global.json").exists()
        or any(root.glob("*.csproj"))
        or any(root.glob("*.sln"))
    )
    if has_dotnet:
        requirements_to_check.append((".NET SDK", ">=8.0"))

    results: list[RequirementItem] = []
    for req_name, min_v in requirements_to_check:
        installed_v = get_installed_version(req_name)
        status = check_requirement_status(min_v, installed_v)
        guidance = get_guidance_for(req_name)
        results.append(
            RequirementItem(
                name=req_name,
                min_version=min_v,
                installed_version=installed_v,
                status=status,
                guidance=guidance,
            )
        )

    return results


def recheck_system_requirement(name: str, root_path: Path | str | None = None) -> RequirementItem:
    """Isolate and re-evaluate a single system requirement by name."""
    clean_name = name.strip()
    all_reqs = scan_system_requirements(root_path=root_path)
    for item in all_reqs:
        if item.name.lower() == clean_name.lower():
            return item

    for known_name, guidance_data in WINDOWS_REQUIREMENTS_GUIDANCE.items():
        if known_name.lower() == clean_name.lower():
            installed_v = get_installed_version(known_name)
            status = check_requirement_status("", installed_v)
            return RequirementItem(
                name=known_name,
                min_version=">=1.0",
                installed_version=installed_v,
                status=status,
                guidance=InstallationGuidance(**guidance_data),
            )

    raise ValueError(f"Requirement '{name}' not found in project specification.")


def validate_folder_paths(paths: list[str]) -> list[FolderValidationResult]:
    """Validate directory paths for existence, readability, and Git marker."""
    results: list[FolderValidationResult] = []
    for raw_path in paths:
        clean = (raw_path or "").strip()
        p = Path(clean).expanduser().resolve()
        if not p.exists():
            results.append(
                FolderValidationResult(
                    path=str(p),
                    exists=False,
                    readable=False,
                    is_git=False,
                    error="Folder tidak ditemukan",
                )
            )
            continue

        if not p.is_dir():
            results.append(
                FolderValidationResult(
                    path=str(p),
                    exists=False,
                    readable=False,
                    is_git=False,
                    error="Path bukan direktori",
                )
            )
            continue

        readable = True
        try:
            list(p.iterdir())
        except (PermissionError, OSError):
            readable = False

        if not readable:
            results.append(
                FolderValidationResult(
                    path=str(p),
                    exists=True,
                    readable=False,
                    is_git=False,
                    error="Tidak ada izin baca",
                )
            )
            continue

        git_marker = p / ".git"
        is_git = git_marker.exists()
        results.append(
            FolderValidationResult(
                path=str(p),
                exists=True,
                readable=True,
                is_git=is_git,
                error=None,
            )
        )

    return results


def get_wizard_progress_path(root_path: Path | None = None) -> Path:
    """Return the canonical path to config/wizard-progress.yaml."""
    root = root_path or find_repo_root()
    return (root / "config" / "wizard-progress.yaml").resolve()


def load_wizard_progress(target_path: Path | str | None = None) -> WizardProgressState:
    """Load partial wizard progress state from disk or return default initial state."""
    path = Path(target_path).resolve() if target_path else get_wizard_progress_path()
    if not path.exists():
        return WizardProgressState(current_step=0, completed_steps=[], step_data={})

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        if isinstance(data, dict):
            return WizardProgressState.model_validate(data)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        logger.warning("Could not read wizard progress from %s: %s", path, exc)

    return WizardProgressState(current_step=0, completed_steps=[], step_data={})


def save_wizard_progress(
    state: WizardProgressState | dict[str, Any],
    target_path: Path | str | None = None,
) -> dict[str, Any]:
    """Atomically persist partial wizard progress state to disk."""
    path = Path(target_path).resolve() if target_path else get_wizard_progress_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(state, dict):
        validated = WizardProgressState.model_validate(state)
    else:
        validated = state

    data_dict = validated.model_dump(mode="python")
    cleaned_dict = _clean_paths_for_yaml(data_dict)
    yaml_text = yaml.safe_dump(cleaned_dict, sort_keys=False, allow_unicode=True)

    temp_target = path.with_suffix(".tmp")
    temp_target.write_text(yaml_text, encoding="utf-8")
    os.replace(temp_target, path)

    saved_time = datetime.now(timezone.utc).isoformat()
    logger.info("Wizard progress saved to %s at %s", path, saved_time)
    return {"success": True, "saved_at": saved_time}



class PredictProfileResponse(BaseModel):
    """Response payload for work profile prediction."""

    source: Literal["gemini", "preset_fallback"]
    profile: WorkProfile


def find_closest_preset(
    description: str,
    presets: list[WorkProfile] | None = None,
) -> WorkProfile:
    """Find the best-matching offline preset WorkProfile for a given job description."""
    if presets is None:
        presets = load_presets()

    if not presets:
        raise ValueError("No presets available in configuration.")

    desc_words = set(re.findall(r"\w+", description.lower()))
    if not desc_words:
        return presets[0]

    best_preset = presets[0]
    best_score = -1

    for preset in presets:
        score = 0
        name_words = set(re.findall(r"\w+", preset.profile_name.lower()))
        desc_target_words = set(re.findall(r"\w+", preset.natural_description.lower()))
        app_words = {
            w
            for app in preset.applications
            for w in re.findall(r"\w+", app.name.lower())
        }
        domain_words = {
            w
            for d in preset.browser_domains
            for w in re.findall(r"\w+", d.lower())
        }

        score += len(desc_words & name_words) * 3
        score += len(desc_words & desc_target_words) * 2
        score += len(desc_words & app_words) * 2
        score += len(desc_words & domain_words) * 1

        if score > best_score:
            best_score = score
            best_preset = preset

    return best_preset


FALLBACK_FLASH_MODELS: list[dict[str, Any]] = [
    {"id": "gemini-3.5-flash", "display_name": "Gemini 3.5 Flash", "is_recommended": True},
    {"id": "gemini-3.8-flash", "display_name": "Gemini 3.8 Flash", "is_recommended": False},
    {"id": "gemini-flash-latest", "display_name": "Gemini Flash Latest", "is_recommended": False},
    {"id": "gemini-3.7-flash", "display_name": "Gemini 3.7 Flash", "is_recommended": False},
]

DEPRECATED_MODELS: set[str] = {
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}


def fetch_available_gemini_models(
    api_key: str | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Fetch live list of generateContent-compatible Flash models from Google AI Studio.

    Filters for active text/json generative flash models and flags the recommended model.
    Falls back gracefully to FALLBACK_FLASH_MODELS if key is missing or offline.
    """
    clean_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not clean_key:
        return {
            "models": FALLBACK_FLASH_MODELS,
            "source": "fallback_offline",
            "active_model": DEFAULT_MODEL,
        }

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    req = urllib.request.Request(
        url,
        headers={"x-goog-api-key": clean_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("models", [])
            items: list[dict[str, Any]] = []
            for m in raw_models:
                m_name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                if m_name in DEPRECATED_MODELS:
                    continue

                low_name = m_name.lower()
                # Prioritize general text/json flash models, ignore specialized tts/image/robotics
                if "flash" in low_name and not any(
                    k in low_name for k in ("tts", "image", "transcribe", "robotics")
                ):
                    display_name = m.get("displayName", m_name)
                    is_rec = (m_name == DEFAULT_MODEL)
                    items.append({
                        "id": m_name,
                        "display_name": display_name,
                        "is_recommended": is_rec,
                    })

            if not items:
                items = list(FALLBACK_FLASH_MODELS)
            else:
                has_rec = any(it["is_recommended"] for it in items)
                if not has_rec and items:
                    items[0]["is_recommended"] = True

            return {
                "models": items,
                "source": "google_api",
                "active_model": DEFAULT_MODEL,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch live Gemini models from Google AI Studio: %s", exc)
        return {
            "models": FALLBACK_FLASH_MODELS,
            "source": "fallback_error",
            "active_model": DEFAULT_MODEL,
        }


def verify_gemini_connection(
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Test connectivity to Google AI Studio Gemini API with provided API key."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise ValueError("API key must not be empty.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": "ping"}]}],
        "generationConfig": {
            "maxOutputTokens": 5,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clean_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data or "candidates" not in data:
                raise RuntimeError(f"Unexpected response format from Gemini: {data}")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", err_body)
        except Exception:  # noqa: BLE001
            msg = err_body
        raise RuntimeError(f"Gemini API error (HTTP {exc.code}): {msg}") from exc
    except OSError as exc:
        raise RuntimeError(f"Network error connecting to Gemini API: {exc}") from exc

    return {"valid": True, "model": model}


def call_gemini_for_profile(
    description: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 30,
) -> WorkProfile:
    """Invoke Gemini structured prompt to generate a WorkProfile from job description."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise ValueError("API key must not be empty.")

    system_prompt = (
        "You are an assistant that analyzes an internship role description and outputs a "
        "tailored WorkProfile in JSON format. Provide:\n"
        "- profile_name (string): canonical title (e.g. 'Software Engineer', 'UI/UX Designer', etc.)\n"
        "- natural_description (string): concise summary of work duties\n"
        "- applications (list): desktop apps used, each with:\n"
        "    - name (string): canonical application name\n"
        "    - process_names (list of string): executable names (e.g. ['Code.exe'])\n"
        "    - file_extensions (list of string): file extensions starting with a dot (e.g. ['.py'])\n"
        "    - log_patterns (list of string): internal log path globs (default: [])\n"
        "- browser_domains (list of string): websites visited for work (e.g. ['github.com'])\n"
        "- watch_folders (list of string): directories to scan (default: [])\n"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": description}]}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clean_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini did not return any candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini returned empty parts.")

    raw_text = parts[0].get("text", "")
    profile_dict = json.loads(raw_text)

    # Clean dict to match WorkProfile fields strictly
    allowed_fields = {"profile_name", "natural_description", "applications", "browser_domains", "watch_folders"}
    cleaned_dict = {k: v for k, v in profile_dict.items() if k in allowed_fields}

    return WorkProfile.model_validate(cleaned_dict)


def predict_work_profile(
    description: str,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> PredictProfileResponse:
    """Predict WorkProfile using Gemini, falling back to offline preset if needed."""
    if api_key and api_key.strip():
        try:
            profile = call_gemini_for_profile(description, api_key=api_key, model=model)
            return PredictProfileResponse(source="gemini", profile=profile)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini prediction failed (%s); using preset fallback.", exc)

    fallback_profile = find_closest_preset(description)
    return PredictProfileResponse(source="preset_fallback", profile=fallback_profile)


def scan_workspace_repos(root_path: str | Path, only_git: bool = True) -> list[dict[str, Any]]:
    """Scan child directories in root_path for Git repositories."""
    p = Path(root_path).resolve()
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"Root path '{root_path}' does not exist or is not a directory.")

    results: list[dict[str, Any]] = []
    try:
        children = sorted(p.iterdir(), key=lambda c: c.name.lower())
    except OSError as exc:
        raise PermissionError(f"Cannot access directory '{root_path}': {exc}") from exc

    for child in children:
        if child.is_dir():
            git_marker = child / ".git"
            is_git = git_marker.exists()
            if only_git and not is_git:
                continue
            results.append({
                "name": child.name,
                "path": str(child.resolve()),
                "is_git": is_git,
            })

    return results


def _clean_paths_for_yaml(val: Any) -> Any:
    """Recursively convert Path objects to strings for YAML serialization."""
    if isinstance(val, dict):
        return {k: _clean_paths_for_yaml(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_clean_paths_for_yaml(v) for v in val]
    if isinstance(val, Path):
        return str(val)
    return val


def save_app_configuration(
    config: AppConfig | dict[str, Any],
    target_path: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically save validated configuration to config.yaml."""
    if target_path is None:
        root = find_repo_root()
        target = (root / "config" / "config.yaml").resolve()
    else:
        target = Path(target_path).resolve()

    target.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(config, dict):
        validated = AppConfig.model_validate(config)
    else:
        validated = config

    # Synchronize browser domains if a work profile is present
    sync_work_profile_browser_domains(validated)

    data_dict = validated.model_dump(mode="python")
    cleaned_dict = _clean_paths_for_yaml(data_dict)

    yaml_text = yaml.safe_dump(cleaned_dict, sort_keys=False, allow_unicode=True)

    # Atomic write via temporary file
    temp_target = target.with_suffix(".tmp")
    temp_target.write_text(yaml_text, encoding="utf-8")
    os.replace(temp_target, target)

    # Clean up wizard progress file if present after final save
    try:
        progress_path = get_wizard_progress_path()
        if progress_path.exists():
            progress_path.unlink()
            logger.info("Cleaned up wizard progress file at %s", progress_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to clean up wizard progress file: %s", exc)

    saved_time = datetime.now(timezone.utc).isoformat()
    logger.info("Configuration successfully saved to %s at %s", target, saved_time)
    return {"success": True, "saved_at": saved_time}


def register_task_scheduler(
    trigger_time: str | None = None,
    review_time: str = "16:30",
    resume_time: str = "20:00",
    active_days: list[str] | None = None,
    task_prefix: str = "MagangLog",
    root_path: Path | None = None,
) -> dict[str, Any]:
    """Register daily execution tasks via Windows Task Scheduler.

    Supports dual execution times: afternoon review and evening resume.
    """
    target_review = (trigger_time.strip() if trigger_time else review_time).strip()
    target_resume = resume_time.strip()

    for t_name, val in [("review_time", target_review), ("resume_time", target_resume)]:
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", val):
            raise ValueError(f"Invalid {t_name} format. Expected HH:MM (e.g. '16:30'): {val!r}")

    root = root_path or find_repo_root()
    script_candidates = [
        root / "scripts" / "install_task.ps1",
        root / "scripts" / "register_scheduler.ps1",
    ]
    script_path = next((p for p in script_candidates if p.exists()), script_candidates[0])

    ps_bin = shutil.which("powershell") or shutil.which("pwsh") or "powershell"

    cmd = [
        ps_bin,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Install",
        "-ReviewTime",
        target_review,
        "-ResumeTime",
        target_resume,
        "-TaskPrefix",
        task_prefix,
    ]

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip() or f"Process exited with code {res.returncode}"
        raise RuntimeError(f"Task Scheduler registration failed: {err}")

    task_name = f"{task_prefix}-Review"
    logger.info(
        "Task Scheduler registered successfully: %s (Review: %s, Resume: %s)",
        task_name,
        target_review,
        target_resume,
    )
    return {
        "success": True,
        "task_name": task_name,
        "review_time": target_review,
        "resume_time": target_resume,
    }


def inspect_scheduler_status(
    task_prefix: str = "MagangLog",
    root_path: Path | None = None,
) -> dict[str, Any]:
    """Inspect registration status of MagangLog tasks in Windows Task Scheduler."""
    review_task = f"{task_prefix}-Review"
    resume_task = f"{task_prefix}-Resume"

    def _query_task(task_name: str) -> dict[str, Any]:
        schtasks_bin = shutil.which("schtasks") or "schtasks"
        try:
            res = subprocess.run(
                [schtasks_bin, "/query", "/tn", task_name, "/v", "/fo", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if res.returncode != 0:
                return {"exists": False}

            info: dict[str, str] = {}
            for line in res.stdout.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    info[parts[0].strip().lower()] = parts[1].strip()

            start_time = info.get("start time")
            time_str = None
            if start_time:
                m = re.match(r"^(\d{1,2}:\d{2})", start_time)
                if m:
                    time_str = m.group(1).zfill(5)

            state = info.get("scheduled task state", "").lower()
            is_enabled = "enabled" in state or "ready" in info.get("status", "").lower()

            return {
                "exists": True,
                "enabled": is_enabled,
                "time": time_str,
                "raw": info,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to query task %s: %s", task_name, exc)
            return {"exists": False, "error": str(exc)}

    review_info = _query_task(review_task)
    resume_info = _query_task(resume_task)

    has_review = review_info.get("exists", False)
    has_resume = resume_info.get("exists", False)

    if has_review and has_resume:
        status_val = "registered"
        is_reg = True
        review_time = review_info.get("time") or "16:30"
        resume_time = resume_info.get("time") or "20:00"
        msg = f"Seluruh tugas terjadwal aktif terdaftar di Windows Task Scheduler (Review: {review_time}, Resume: {resume_time})."
    elif has_review or has_resume:
        status_val = "needs_update"
        is_reg = False
        review_time = review_info.get("time")
        resume_time = resume_info.get("time")
        msg = "Salah satu tugas terjadwal tidak ditemukan atau belum aktif. Disarankan mendaftarkan ulang."
    else:
        status_val = "unregistered"
        is_reg = False
        review_time = None
        resume_time = None
        msg = "Tugas terjadwal belum terdaftar di Windows Task Scheduler."

    return {
        "status": status_val,
        "is_registered": is_reg,
        "review_task_name": review_task,
        "resume_task_name": resume_task,
        "review_time": review_time,
        "resume_time": resume_time,
        "diagnostic_message": msg,
    }


def unregister_task_scheduler(
    task_prefix: str = "MagangLog",
    root_path: Path | None = None,
) -> dict[str, Any]:
    """Unregister scheduled tasks from Windows Task Scheduler."""
    root = root_path or find_repo_root()
    script_candidates = [
        root / "scripts" / "install_task.ps1",
    ]
    script_path = next((p for p in script_candidates if p.exists()), None)

    # 1. Try running install_task.ps1 -Uninstall
    if script_path and script_path.exists():
        ps_bin = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
        cmd = [
            ps_bin,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-Uninstall",
            "-TaskPrefix",
            task_prefix,
        ]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if res.returncode == 0:
            logger.info("Task Scheduler uninstalled via install_task.ps1 for prefix %s", task_prefix)
            return {
                "success": True,
                "message": f"Tugas terjadwal dengan prefix '{task_prefix}' berhasil dihapus dari Windows Task Scheduler.",
            }

    # 2. Fallback directly via schtasks /delete
    schtasks_bin = shutil.which("schtasks") or "schtasks"
    for name in [f"{task_prefix}-Review", f"{task_prefix}-Resume"]:
        subprocess.run(
            [schtasks_bin, "/delete", "/tn", name, "/f"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    logger.info("Task Scheduler uninstalled via schtasks for prefix %s", task_prefix)
    return {
        "success": True,
        "message": f"Tugas terjadwal dengan prefix '{task_prefix}' berhasil dihapus dari Windows Task Scheduler.",
    }
