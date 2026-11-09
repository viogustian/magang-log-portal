"""SetupWizard service layer for Gemini connectivity testing and role prediction."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from ...settings import AppConfig, find_repo_root, sync_work_profile_browser_domains
from ...workprofile import WorkProfile, load_presets

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


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


def verify_gemini_connection(
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Test connectivity to Google AI Studio Gemini API with provided API key."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise ValueError("API key must not be empty.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
    body = {
        "contents": [{"parts": [{"text": "ping"}]}],
        "generationConfig": {
            "maxOutputTokens": 5,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
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
        headers={"Content-Type": "application/json"},
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

    saved_time = datetime.now(timezone.utc).isoformat()
    logger.info("Configuration successfully saved to %s at %s", target, saved_time)
    return {"success": True, "saved_at": saved_time}


def register_task_scheduler(
    trigger_time: str,
    task_prefix: str = "MagangLog",
    root_path: Path | None = None,
) -> dict[str, Any]:
    """Register daily execution task via Windows Task Scheduler."""
    clean_time = trigger_time.strip()
    if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", clean_time):
        raise ValueError("Invalid trigger_time format. Expected HH:MM (e.g. '17:00').")

    root = root_path or find_repo_root()
    script_candidates = [
        root / "scripts" / "register_scheduler.ps1",
        root / "scripts" / "install_task.ps1",
    ]
    script_path = next((p for p in script_candidates if p.exists()), script_candidates[-1])

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
        clean_time,
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
    logger.info("Task Scheduler registered successfully: %s at %s", task_name, clean_time)
    return {"success": True, "task_name": task_name}
