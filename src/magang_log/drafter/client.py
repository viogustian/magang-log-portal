"""Protokol antarmuka klien model AI (ModelClient) dan FakeModelClient untuk pengujian."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel

from .models import LogEntryDraft


@runtime_checkable
class ModelClient(Protocol):
    """Protokol klien model AI vendor-agnostik tanpa akses ke tool eksekusi."""

    def generate(
        self,
        system_prompt: str,
        user_payload: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Menghasilkan instance skema Pydantic dari system_prompt dan user_payload."""
        ...


class FakeModelClient:
    """Implementasi klien tiruan ModelClient untuk pengujian 100% offline."""

    def __init__(
        self,
        response: BaseModel | None = None,
        response_factory: Callable[[str, str, type[BaseModel]], BaseModel] | None = None,
    ) -> None:
        self.response = response
        self.response_factory = response_factory
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        system_prompt: str,
        user_payload: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_payload": user_payload,
                "schema": schema,
                "tools": None,  # Explicitly forbidden
            }
        )
        if self.response is not None:
            return self.response
        if self.response_factory is not None:
            return self.response_factory(system_prompt, user_payload, schema)

        # Respon bawaan jika schema adalah LogEntryDraft
        if issubclass(schema, LogEntryDraft):
            return LogEntryDraft(
                work_date=date.today(),
                kehadiran="Hadir",
                aktivitas="Melaksanakan pengujian otomatis dan perancangan arsitektur sistem.",
                pembelajaran="Memahami konsep pemisahan seam dan pembuatan protokol vendor-agnostik.",
                kendala="",
                evidence_refs={},
                needs_input=["kendala"],
                prompt_version="v1",
                model="fake-model",
            )

        return schema()  # type: ignore[call-arg]


class GeminiModelClient:
    """Implementasi ModelClient resmi menggunakan Google Gemini API via REST HTTP (tanpa tool eksekusi)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.5-flash",
        temperature: float = 0.2,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        system_prompt: str,
        user_payload: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        import json
        import urllib.error
        import urllib.request

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY tidak ditemukan. Pastikan variabel lingkungan sudah disetel."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_payload}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "response_mime_type": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Panggilan Gemini API gagal (HTTP {exc.code}): {err_body}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Gagal menghubungi endpoint Gemini API: {exc}") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini API tidak mengembalikan kandidat respons: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError(f"Bagian teks jawaban Gemini kosong: {candidates[0]}")

        raw_text = parts[0].get("text", "")
        return schema.model_validate_json(raw_text)

