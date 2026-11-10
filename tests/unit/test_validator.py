"""Unit tests untuk mesin validasi deterministik multi-tahap (MultiStageValidator)."""

from __future__ import annotations

from dataclasses import is_dataclass
from datetime import date, datetime, timezone

import pytest

from magang_log.collectors.base import Evidence
from magang_log.drafter.models import LogEntryDraft
from magang_log.validator import (
    CANNED_FILLER_PHRASES,
    MultiStageValidator,
    ValidationReport,
    strip_markdown,
    validate,
)


def _make_valid_draft(
    aktivitas: str | None = None,
    pembelajaran: str | None = None,
    kendala: str | None = None,
    evidence_refs: dict[str, list[str]] | None = None,
) -> LogEntryDraft:
    default_text = (
        "Mengembangkan implementasi modul autentikasi portal magang dengan pengujian unit "
        "komprehensif untuk memastikan kepatuhan standar keamanan instansi pemerintah terkait [ev1]."
    )
    return LogEntryDraft(
        work_date=date(2026, 10, 27),
        kehadiran="Hadir",
        aktivitas=aktivitas or default_text,
        pembelajaran=pembelajaran
        or (
            "Memahami arsitektur penanganan sesi login portal berbasis token serta penerapan "
            "isolasi hak akses yang aman pada lingkungan produksi instansi pemerintah [ev1]."
        ),
        kendala=kendala
        or (
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "menyelesaikannya melalui konfigurasi mekanisme exponential backoff retry [ev1]."
        ),
        evidence_refs=evidence_refs or {"aktivitas": ["ev1"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )


def _make_evidence(id_: str, title: str = "Tugas") -> Evidence:
    return Evidence(
        id=id_,
        source="git",  # type: ignore[arg-type]
        kind="commit",
        ts=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        title=title,
        detail="Commit detail",
        strength="strong",  # type: ignore[arg-type]
    )


def test_validation_report_dataclass_fields() -> None:
    """ValidationReport harus berupa dataclass dengan atribut lengkap."""
    assert is_dataclass(ValidationReport)
    report = ValidationReport(
        is_valid=True,
        errors=[],
        warnings=[],
        grounding_score=0.95,
        detected_filler=[],
    )
    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []
    assert report.grounding_score == 0.95
    assert report.detected_filler == []


@pytest.mark.parametrize(
    ("length", "expected_valid"),
    [
        (99, False),
        (100, True),
        (5000, True),
        (5001, False),
    ],
)
def test_portal_character_boundaries_exact_limits(length: int, expected_valid: bool) -> None:
    """Menguji batas karakter portal: 99 (gagal), 100 (lulus), 5000 (lulus), 5001 (gagal)."""
    # Gunakan teks bervariasi agar tidak gagal pada filter keragaman leksikal
    base_sentence = "Melakukan implementasi komponen pengujian autentikasi portal resmi magang kemnaker secara terstruktur [ev1]. "
    multiplier = (length // len(base_sentence)) + 1
    repeated_words = (base_sentence * multiplier)[:length]
    # Pastikan tepat 'length' karakter
    assert len(repeated_words) == length

    draft = _make_valid_draft(aktivitas=repeated_words)
    evidence = [_make_evidence("ev1")]

    report = validate(draft, evidence)

    if expected_valid:
        # Tidak boleh ada error panjang karakter pada aktivitas
        length_errors = [e for e in report.errors if "aktivitas" in e and "karakter" in e]
        assert len(length_errors) == 0, f"Harusnya lolos tapi ada error: {length_errors}"
    else:
        # Wajib ada error panjang karakter pada aktivitas
        length_errors = [e for e in report.errors if "aktivitas" in e and "karakter" in e]
        assert len(length_errors) > 0, "Harusnya gagal pada batas panjang karakter"
        assert report.is_valid is False


def test_portal_character_boundaries_all_fields() -> None:
    """Ketiga field (aktivitas, pembelajaran, kendala) wajib memenuhi batas 100-5000 karakter."""
    draft = _make_valid_draft(
        aktivitas="Terlalu pendek",
        pembelajaran="Juga terlalu pendek",
        kendala="Pendek",
    )
    report = validate(draft)
    assert report.is_valid is False
    assert any("aktivitas" in e and "kurang dari batas minimum" in e for e in report.errors)
    assert any("pembelajaran" in e and "kurang dari batas minimum" in e for e in report.errors)
    assert any("kendala" in e and "kurang dari batas minimum" in e for e in report.errors)


def test_text_format_sanitization_markdown_and_links() -> None:
    """Validator wajib menolak markdown (code block, backticks, bullets), URL, email, dan HTML."""
    evidence = [_make_evidence("ev1")]

    # 1. Code blocks
    d1 = _make_valid_draft(aktivitas="```python\nprint('hello')\n```\n" + "A" * 120 + " [ev1]")
    r1 = validate(d1, evidence)
    assert r1.is_valid is False
    assert any("markdown code block" in e for e in r1.errors)

    # 2. Backticks
    d2 = _make_valid_draft(
        aktivitas="Melakukan pengujian fitur `auth_login` pada portal " + "B" * 100 + " [ev1]"
    )
    r2 = validate(d2, evidence)
    assert r2.is_valid is False
    assert any("markdown backtick" in e for e in r2.errors)

    # 3. Bullet points
    d3 = _make_valid_draft(
        aktivitas="- Mengerjakan tugas autentikasi portal magang dengan cermat "
        + "C" * 100
        + " [ev1]"
    )
    r3 = validate(d3, evidence)
    assert r3.is_valid is False
    assert any("bullet point" in e for e in r3.errors)

    # 4. Raw URLs
    d4 = _make_valid_draft(
        aktivitas="Mengakses dokumentasi resmi pada https://kemnaker.go.id/portal "
        + "D" * 100
        + " [ev1]"
    )
    r4 = validate(d4, evidence)
    assert r4.is_valid is False
    assert any("URL mentah" in e for e in r4.errors)

    # 5. Emails
    d5 = _make_valid_draft(
        aktivitas="Menghubungi pembimbing magang melalui mentor@kemnaker.go.id "
        + "E" * 100
        + " [ev1]"
    )
    r5 = validate(d5, evidence)
    assert r5.is_valid is False
    assert any("alamat email" in e for e in r5.errors)

    # 6. HTML tags
    d6 = _make_valid_draft(
        aktivitas="Menyelesaikan implementasi <b>modul autentikasi</b> portal "
        + "F" * 100
        + " [ev1]"
    )
    r6 = validate(d6, evidence)
    assert r6.is_valid is False
    assert any("tag HTML" in e for e in r6.errors)


def test_strip_markdown_utility() -> None:
    """strip_markdown harus membersihkan formatting ke teks polos."""
    raw = (
        "```python\ncode\n```\n"
        "- Melakukan pengujian `login_session` pada sistem\n"
        "• Menyusun laporan <b>resmi</b> magang."
    )
    cleaned = strip_markdown(raw)
    assert "```" not in cleaned
    assert "`" not in cleaned
    assert "- " not in cleaned
    assert "• " not in cleaned
    assert "<b>" not in cleaned
    assert "</b>" not in cleaned
    assert "Melakukan pengujian login_session pada sistem" in cleaned
    assert "Menyusun laporan resmi magang." in cleaned


@pytest.mark.parametrize("filler", CANNED_FILLER_PHRASES)
def test_anti_filler_phrase_detector_legacy_templates(filler: str) -> None:
    """Validator wajib menolak seluruh frasa template pengisi canned warisan lama."""
    text_with_filler = (
        f"Aktivitas magang hari ini {filler} dan seluruh target kerja terselesaikan "
        "dengan dedikasi tinggi serta pencatatan terstruktur [ev1]."
    )
    draft = _make_valid_draft(aktivitas=text_with_filler)
    evidence = [_make_evidence("ev1")]

    report = validate(draft, evidence)

    assert report.is_valid is False
    assert filler in report.detected_filler
    assert any(f"frasa filler terlarang: '{filler}'" in e for e in report.errors)


def test_anti_filler_phrase_detector_case_insensitive() -> None:
    """Anti-filler harus bekerja secara case-insensitive dan tahan variasi tanda baca."""
    text = (
        "Pekerjaan hari ini, BERJALAN DENGAN LANCAR TANPA ADA KENDALA sama sekali, "
        "sehingga modul dapat langsung diuji ke server staging instansi [ev1]."
    )
    draft = _make_valid_draft(aktivitas=text)
    report = validate(draft, [_make_evidence("ev1")])

    assert report.is_valid is False
    assert "berjalan dengan lancar tanpa ada kendala" in report.detected_filler


def test_lexical_diversity_check_flags_warning() -> None:
    """Teks dengan keragaman leksikal rendah (< 0.4) harus memicu peringatan (warning)."""
    # Mengulang kata-kata yang sama secara berlebihan
    words = ["tugas", "kerja", "portal"] * 25
    low_diversity_text = " ".join(words) + " selesai [ev1]."
    draft = _make_valid_draft(pembelajaran=low_diversity_text)

    report = validate(draft, [_make_evidence("ev1")])

    assert any("keragaman leksikal rendah" in w for w in report.warnings)


def test_repetition_ratio_detects_repeated_sentences() -> None:
    """Teks dengan kalimat berulang (rasio > 0.3) harus ditolak dengan error."""
    repeated_sentence = "Mengembangkan fitur autentikasi portal magang secara komprehensif [ev1]. "
    text = repeated_sentence * 5  # Kalimat yang persis sama diulang 5 kali
    draft = _make_valid_draft(aktivitas=text)

    report = validate(draft, [_make_evidence("ev1")])

    assert report.is_valid is False
    assert any("pengulangan kalimat/n-gram berlebihan" in e for e in report.errors)


def test_grounding_score_calculation_all_grounded() -> None:
    """Ketika semua kalimat merujuk pada bukti yang valid, grounding score adalah 1.0 tanpa warning."""
    aktivitas = (
        "Mengembangkan implementasi modul autentikasi sesi login portal [ev1]. "
        "Menambahkan pengujian unit komprehensif untuk pengujian alur kerja [ev2]."
    )
    evidence = [_make_evidence("ev1"), _make_evidence("ev2")]
    draft = _make_valid_draft(
        aktivitas=aktivitas,
        evidence_refs={"aktivitas": ["ev1", "ev2"]},
    )

    report = validate(draft, evidence)

    assert report.grounding_score == 1.0
    assert not any("Grounding score" in w for w in report.warnings)


def test_grounding_score_calculation_low_grounding_attaches_warning() -> None:
    """Ketika skor grounding < 0.8, validator harus melampirkan pesan peringatan."""
    # 1 dari 3 kalimat terhubung ke bukti valid -> skor 1/3 = 0.3333 (< 0.8)
    aktivitas = (
        "Mengembangkan implementasi modul autentikasi sesi login portal [ev1]. "
        "Membantu rekan tim merapikan dokumentasi arsitektur internal tanpa tiket. "
        "Mengikuti diskusi perencanaan sprint mingguan tanpa ada komit."
    )
    evidence = [_make_evidence("ev1")]
    draft = _make_valid_draft(
        aktivitas=aktivitas,
        evidence_refs={"aktivitas": ["ev1"]},
    )

    report = validate(draft, evidence)

    assert report.grounding_score < 0.8
    assert any(
        "Grounding score" in w and "di bawah batas minimum 0.8" in w for w in report.warnings
    )


def test_grounding_score_with_indexed_sentence_refs() -> None:
    """Validator mendukung pemetaan referensi bukti berbasis indeks kalimat."""
    aktivitas = (
        "Mengembangkan handler otorisasi pengguna berbasis role portal. "
        "Melakukan migrasi skema basis data SQLite ke versi terbaru."
    )
    evidence = [_make_evidence("c1"), _make_evidence("c2")]
    draft = _make_valid_draft(
        aktivitas=aktivitas,
        evidence_refs={"0": ["c1"], "1": ["c2"]},
    )

    report = validate(draft, evidence)

    assert report.grounding_score == 1.0
    assert not any("Grounding score" in w for w in report.warnings)


def test_grounding_score_rejects_unverified_evidence_ids() -> None:
    """ID bukti yang tidak ada dalam daftar bukti terverifikasi tidak dihitung sebagai grounded."""
    aktivitas = "Mengembangkan fitur berdasarkan komit palsu [fake_commit_999]."
    evidence = [_make_evidence("real_commit_1")]
    draft = _make_valid_draft(
        aktivitas=aktivitas,
        evidence_refs={"aktivitas": ["fake_commit_999"]},
    )

    report = validate(draft, evidence)

    # fake_commit_999 tidak valid, sehingga 0 kalimat grounded -> skor 0.0
    assert report.grounding_score == 0.0
    assert any("Grounding score" in w for w in report.warnings)


def test_clean_valid_draft_passes_completely() -> None:
    """Draf bersih yang mematuhi seluruh aturan portal harus lulus tanpa error dan tanpa warning."""
    evidence = [_make_evidence("ev1")]
    draft = _make_valid_draft(
        aktivitas=(
            "Mengembangkan implementasi modul autentikasi sesi portal industri Kemnaker "
            "dengan menerapkan validasi token JWT serta penanganan exception yang aman [ev1]."
        ),
        pembelajaran=(
            "Mempelajari konfigurasi siklus hidup sesi pengguna pada aplikasi web serta "
            "mekanisme regenerasi token untuk mencegah serangan session fixation [ev1]."
        ),
        kendala=(
            "Mengidentifikasi latensi tinggi pada respons server autentikasi lokal dan "
            "mengatasinya dengan optimasi pool koneksi HTTP client [ev1]."
        ),
        evidence_refs={"aktivitas": ["ev1"], "pembelajaran": ["ev1"], "kendala": ["ev1"]},
    )

    report = validate(draft, evidence)

    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []
    assert report.grounding_score == 1.0
    assert report.detected_filler == []


def test_multistage_validator_class_interface() -> None:
    """MultiStageValidator instance harus mengembalikan ValidationReport yang konsisten dengan validate()."""
    validator_obj = MultiStageValidator()
    draft = _make_valid_draft()
    evidence = [_make_evidence("ev1")]

    report = validator_obj.validate(draft, evidence)

    assert report.is_valid is True
    assert report.grounding_score == 1.0
