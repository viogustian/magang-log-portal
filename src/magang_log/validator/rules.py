"""Aturan validasi deterministik, pola regex sanitasi, dan algoritma scoring."""

from __future__ import annotations

import re
from typing import Sequence

MIN_FIELD_LENGTH = 100
MAX_FIELD_LENGTH = 5000
TARGET_TEXT_FIELDS: tuple[str, ...] = ("aktivitas", "pembelajaran", "kendala")

CANNED_FILLER_PHRASES: tuple[str, ...] = (
    "berjalan dengan lancar tanpa ada kendala",
    "tidak menemui kendala yang berarti",
    "semua tugas diselesaikan sesuai rencana",
    "bekerja dengan baik dan efektif",
    "tanpa kendala teknis maupun non teknis",
)

# Regex sanitasi teks format
RE_CODE_BLOCK = re.compile(r"```")
RE_BACKTICK = re.compile(r"`")
RE_BULLET_POINT = re.compile(r"(?:^|\n)\s*[-*+•]\s+|[•\u2022\u25cf]")
RE_RAW_URL = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_HTML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")


def strip_markdown(text: str) -> str:
    """Membersihkan format markdown, tag HTML, dan simbol bullet menjadi teks polos."""
    # Hapus blok kode
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", text)
    cleaned = re.sub(r"```", "", cleaned)
    # Hapus inline backtick
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"`", "", cleaned)
    # Hapus tag HTML
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Hapus bullet point di awal baris
    cleaned = re.sub(r"(?m)^\s*[-*+•]\s+", "", cleaned)
    # Hapus simbol bullet sisa
    cleaned = re.sub(r"[•\u2022\u25cf]", "", cleaned)
    # Normalisasi spasi dan baris baru
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def detect_format_violations(text: str, field_name: str) -> list[str]:
    """Mendeteksi pelanggaran format teks markdown, URL mentah, email, dan HTML."""
    violations: list[str] = []
    if RE_CODE_BLOCK.search(text):
        violations.append(
            f"Field '{field_name}' mengandung sintaks markdown code block (```) yang tidak diizinkan."
        )
    elif RE_BACKTICK.search(text):
        violations.append(
            f"Field '{field_name}' mengandung format markdown backtick (`) yang tidak diizinkan."
        )

    if RE_BULLET_POINT.search(text):
        violations.append(
            f"Field '{field_name}' mengandung simbol bullet point (*, -, +, •) yang tidak diizinkan."
        )

    if RE_RAW_URL.search(text):
        violations.append(f"Field '{field_name}' mengandung URL mentah yang tidak diizinkan.")

    if RE_EMAIL.search(text):
        violations.append(f"Field '{field_name}' mengandung alamat email yang tidak diizinkan.")

    if RE_HTML_TAG.search(text):
        violations.append(f"Field '{field_name}' mengandung tag HTML yang tidak diizinkan.")

    return violations


def detect_canned_fillers(text: str, field_name: str) -> tuple[list[str], list[str]]:
    """Mendeteksi frasa template pengisi (canned filler) warisan lama.

    Returns:
        tuple (daftar frasa filler yang ditemukan, daftar pesan error).
    """
    detected: list[str] = []
    errors: list[str] = []

    # Normalisasi teks: lowercase, hilangkan tanda baca tertentu, normalisasi spasi
    norm_text = re.sub(r"[.,;:!?]", " ", text.lower())
    norm_text = " ".join(norm_text.split())

    for phrase in CANNED_FILLER_PHRASES:
        norm_phrase = " ".join(phrase.lower().split())
        if norm_phrase in norm_text:
            if phrase not in detected:
                detected.append(phrase)
            errors.append(f"Field '{field_name}' mengandung frasa filler terlarang: '{phrase}'.")

    return detected, errors


def split_sentences(text: str) -> list[str]:
    """Membagi teks ke dalam kalimat berdasarkan tanda baca akhir kalimat atau baris baru."""
    raw = [s.strip() for s in re.split(r"(?<=[.!?])(?:\s+|\n+)|(?:\n+)", text) if s.strip()]
    if not raw and text.strip():
        return [text.strip()]
    return raw


def compute_lexical_diversity(text: str) -> float:
    """Menghitung keragaman leksikal (unique words / total words)."""
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 1.0
    return len(set(words)) / len(words)


def compute_repetition_ratio(text: str) -> float:
    """Menghitung rasio pengulangan kalimat dan n-gram (trigram)."""
    words = re.findall(r"\b\w+\b", text.lower())
    sentences = split_sentences(text)

    sent_rep = 0.0
    if len(sentences) >= 2:
        norm_sents = [s.lower() for s in sentences]
        sent_rep = 1.0 - (len(set(norm_sents)) / len(norm_sents))

    ngram_rep = 0.0
    if len(words) >= 6:
        trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
        if trigrams:
            ngram_rep = 1.0 - (len(set(trigrams)) / len(trigrams))

    return max(sent_rep, ngram_rep)


def compute_grounding_score(
    aktivitas: str,
    evidence_refs: dict[str, list[str]],
    valid_evidence_ids: set[str],
) -> tuple[float, list[str]]:
    """Menghitung skor keterhubungan bukti (Grounding Score) pada field aktivitas.

    Rumus:
        Grounding Score = (Jumlah kalimat dengan minimal 1 ID bukti valid) / (Total kalimat pada aktivitas)

    Returns:
        tuple (skor 0.0-1.0, daftar peringatan bila skor < 0.8).
    """
    sentences = split_sentences(aktivitas)
    if not sentences:
        return 1.0, []

    # Kumpulkan semua ID yang dicantumkan dalam evidence_refs
    all_cited_ids: set[str] = set()
    for ids in evidence_refs.values():
        if isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)):
            for item in ids:
                if str(item).strip():
                    all_cited_ids.add(str(item).strip())

    # Filter hanya ID yang terverifikasi dalam koleksi bukti
    if valid_evidence_ids:
        verified_cited_ids = {cid for cid in all_cited_ids if cid in valid_evidence_ids}
    else:
        verified_cited_ids = all_cited_ids

    grounded_count = 0
    for idx, sentence in enumerate(sentences):
        is_grounded = False

        # 1. Cek pemetaan langsung indeks kalimat pada evidence_refs
        candidate_keys = (
            str(idx),
            f"sentence_{idx}",
            f"aktivitas_{idx}",
            f"aktivitas[{idx}]",
            f"s{idx}",
            sentence,
        )
        for key in candidate_keys:
            if key in evidence_refs:
                key_ids = evidence_refs[key]
                if isinstance(key_ids, Sequence) and not isinstance(key_ids, (str, bytes)):
                    if any(
                        str(i).strip() in (valid_evidence_ids or verified_cited_ids)
                        for i in key_ids
                    ):
                        is_grounded = True
                        break
        if is_grounded:
            grounded_count += 1
            continue

        # 2. Cek apakah teks kalimat merujuk pada salah satu ID bukti yang valid
        for cid in verified_cited_ids:
            pattern = rf"(?:\b{re.escape(cid)}\b|\[{re.escape(cid)}\]|\({re.escape(cid)}\))"
            if re.search(pattern, sentence, re.IGNORECASE):
                is_grounded = True
                break

        if is_grounded:
            grounded_count += 1

    score = round(grounded_count / len(sentences), 4)
    warnings: list[str] = []
    if score < 0.8:
        warnings.append(
            f"Grounding score ({score:.2f}) di bawah batas minimum 0.8. "
            f"Hanya {grounded_count} dari {len(sentences)} kalimat aktivitas yang terhubung ke bukti terverifikasi."
        )

    return score, warnings
