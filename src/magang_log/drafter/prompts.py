"""Pemuat template prompt AI berversi untuk penyusunan logbook."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Mencari direktori root repositori berdasarkan file penanda pyproject.toml."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").exists() or (parent / "prompts").exists():
            return parent
    return cur


def load_prompt_template(version: str = "v1", prompts_dir: Path | None = None) -> str:
    """Memuat template prompt dari file markdown berversi (mis. prompts/draft_logbook.v1.md)."""
    p_dir = prompts_dir or (find_project_root() / "prompts")
    template_file = p_dir / f"draft_logbook.{version}.md"
    if not template_file.exists():
        raise FileNotFoundError(f"Template prompt '{version}' tidak ditemukan pada {template_file}")
    return template_file.read_text(encoding="utf-8")
