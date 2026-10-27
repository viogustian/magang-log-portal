"""Unit test untuk kontrak data Evidence dan komputasi ID deterministik."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from magang_log.collectors.base import Evidence, compute_evidence_id


def test_deterministic_id_generation() -> None:
    ts = datetime(2026, 10, 27, 10, 30, 0, tzinfo=timezone.utc)
    ev_id = compute_evidence_id(
        source="note",
        kind="note:aktivitas",
        ts=ts,
        title="Menulis unit test",
    )

    # Panjang hash tepat 10 karakter
    assert len(ev_id) == 10
    # Berisi karakter hexadecimal valid
    assert all(c in "0123456789abcdef" for c in ev_id)

    # Deterministik: input yang identik menghasilkan hash yang identik
    ev_id2 = compute_evidence_id(
        source="note",
        kind="note:aktivitas",
        ts=ts,
        title="  Menulis unit test  ",  # spasi ekstra harus di-strip
    )
    assert ev_id == ev_id2

    # Perubahan atribut menghasilkan hash yang berbeda
    ev_id_diff = compute_evidence_id(
        source="note",
        kind="note:kendala",
        ts=ts,
        title="Menulis unit test",
    )
    assert ev_id != ev_id_diff


def test_evidence_creation_and_fields() -> None:
    ts = datetime(2026, 10, 27, 8, 15, 0, tzinfo=timezone.utc)
    ev = Evidence(
        source="git",
        kind="commit",
        ts=ts,
        title="feat: add evidence data contract",
        detail="src/magang_log/collectors/base.py (+50/-0)",
        strength="strong",
    )

    assert ev.source == "git"
    assert ev.kind == "commit"
    assert ev.ts == ts
    assert ev.title == "feat: add evidence data contract"
    assert ev.detail == "src/magang_log/collectors/base.py (+50/-0)"
    assert ev.strength == "strong"
    # ID otomatis dihitung secara deterministik
    assert len(ev.id) == 10
    assert ev.work_date == ts.date()


def test_evidence_immutability() -> None:
    ts = datetime(2026, 10, 27, 9, 0, 0, tzinfo=timezone.utc)
    ev = Evidence(
        source="note",
        kind="note:kendala",
        ts=ts,
        title="Kendala konfigurasi",
        detail="Error parsing YAML",
        strength="strong",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.title = "Ubah judul"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.detail = "Ubah detail"  # type: ignore[misc]


def test_evidence_validation_source_and_strength() -> None:
    ts = datetime(2026, 10, 27, 9, 0, 0, tzinfo=timezone.utc)

    # Sumber tidak valid harus melempar ValueError
    with pytest.raises(ValueError, match="Invalid source"):
        Evidence(
            source="invalid_source",  # type: ignore[arg-type]
            kind="commit",
            ts=ts,
            title="Judul",
            strength="strong",
        )

    # Strength tidak valid harus melempar ValueError
    with pytest.raises(ValueError, match="Invalid strength"):
        Evidence(
            source="git",
            kind="commit",
            ts=ts,
            title="Judul",
            strength="medium",  # type: ignore[arg-type]
        )
