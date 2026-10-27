"""Protokol antarmuka klien model AI (ModelClient) dan FakeModelClient untuk pengujian."""

from __future__ import annotations

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
