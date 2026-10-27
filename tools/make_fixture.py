#!/usr/bin/env python3
"""Buat halaman tiruan untuk test dari snapshot HTML portal yang asli.

Pemakaian:
    python -I tools/make_fixture.py SNAPSHOT.html tests/fixtures/portal_mock/riwayat.html

Yang dipertahankan: markup asli <section class="history-page"> (kalender, form, label,
aria-label), supaya selector diuji terhadap struktur nyata. Yang ditambahkan: tools/mock.js.
Yang dibuang: semua <script>/<style>/<link> dan seluruh bagian halaman di luar section itu.
Jalankan ulang setiap kali portal berubah dan Anda menyimpan snapshot baru.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def main(snapshot: Path, out: Path) -> None:
    soup = BeautifulSoup(snapshot.read_text(encoding="utf-8"), "lxml")
    section = soup.select_one("section.history-page")
    if section is None:
        sys.exit("section.history-page tidak ditemukan: struktur halaman portal berubah?")
    for tag in section.find_all(["script", "style", "link"]):
        tag.decompose()

    markup = str(section)
    if re.search(r"@|\b\d{16}\b", markup):
        sys.exit("Ditemukan pola email/NIK di markup; periksa manual sebelum dijadikan fixture.")

    mock_js = (Path(__file__).parent / "mock.js").read_text(encoding="utf-8")
    html = (
        '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8">\n'
        "<title>Riwayat | MagangHub Monev (FIXTURE UJI)</title>\n</head>\n<body>\n"
        "<!-- FIXTURE UJI: markup diturunkan dari snapshot asli; perilaku = tools/mock.js. "
        "BUKAN portal. -->\n"
        f'<main id="main-content">\n{markup}\n</main>\n<script>\n{mock_js}\n</script>\n'
        "</body>\n</html>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out} ({len(html)} karakter)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
