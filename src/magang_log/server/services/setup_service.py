"""SetupWizard service layer for Gemini connectivity testing and role prediction."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel

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
