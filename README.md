# magang-log — modul portal MagangHub

Pengisi form **Riwayat Kehadiran → Tambah laporan** di portal MagangHub Monev memakai Playwright,
**tanpa LLM**. Ini bagian M3 dari PRD *magang-log v2*; bagian lain (pengumpul bukti, penulis
draf, validator, ledger) belum ada di sini.

Dibangun dari snapshot halaman asli (2026-10-27). Seluruh selector ada di satu file:
`src/magang_log/portal/selectors.py`.

## Apa yang dilakukan

| Langkah | Perilaku |
| :-- | :-- |
| Baca status hari | dari `aria-label` tombol hari di kalender, mis. `Selasa, 27 Oktober 2026, Belum Diisi` |
| Berhenti bila tidak boleh | `Menunggu Persetujuan`/disetujui → `SUDAH_TERKIRIM`; libur → `LIBUR`; tombol hari nonaktif → `TERKUNCI`; label tak dikenal → `PERLU_TINDAKAN`. Form **tidak disentuh** |
| Cek lokasi | form meminta lokasi. Tidak ada lokasi → `LOKASI_TIDAK_TERSEDIA`. **Lokasi tidak pernah dipalsukan** |
| Isi 3 kolom | Uraian aktivitas, Pembelajaran yang diperoleh, Kendala yang dialami (**min 100, maks 5000 karakter**) |
| Pernyataan | dicentang **hanya** bila entri sudah Anda setujui (`approved_at`) |
| Kirim + verifikasi | klik *Simpan dan Kirim*, lalu muat ulang dari server dan baca status hari. Bukan percaya pada klik |

## Pakai

Prasyarat: Python 3.12+, Google Chrome terpasang.

```powershell
pip install -e .
magang-portal login                          # login MANUAL sekali (OTP/captcha oleh Anda); sesi disimpan di data/auth/state.json
magang-portal check                          # diagnosis read-only: login, status hari, lokasi, selector
magang-portal fill   --entry mine.json       # DRY-RUN: mengisi kolom, tidak mencentang, tidak mengirim
magang-portal submit --entry mine.json       # menampilkan isi, minta ketik SETUJU, lalu kirim + verifikasi
```

Format `mine.json`: lihat `examples/entry.example.json` (salin, lalu **ganti semua isinya**).
Pilihan umum: `--channel chrome|msedge|chromium`, `--headless`.

Kode keluar: `0` selesai/dilewati dengan benar, `10` butuh tindakan Anda, `20` login diperlukan,
`40` gagal/terkunci/lokasi tidak tersedia.

> `data/` (sesi login, screenshot) ada di `.gitignore`. File sesi setara kunci akun: jangan
> di-commit atau dibagikan. Screenshot berisi isi logbook Anda.

## Jalankan test

```powershell
pip install -e ".[dev]"
playwright install chromium     # untuk test (memakai Chromium bawaan Playwright)
pytest
```

32 test berjalan terhadap **halaman tiruan** (`tests/fixtures/portal_mock/riwayat.html`):
markup-nya asli dari snapshot, perilakunya tiruan (`tools/mock.js`). Test memeriksa antara lain
status tiap hari, selector unik, dry-run tidak mengirim, kirim terverifikasi muat-ulang, "sukses
palsu" tertangkap, login/lokasi, dan penjaga statis (tidak ada override lokasi, tidak ada
pengetikan kredensial, tidak ada klien LLM di paket portal).

Bila portal berubah: simpan snapshot HTML baru, lalu
`python -I tools/make_fixture.py snapshot.html tests/fixtures/portal_mock/riwayat.html`
dan perbarui `selectors.py` sampai test lulus.

## Yang BELUM terverifikasi (perlu Anda uji di laptop)

1. **Lokasi:** apakah Chrome yang dikendalikan Playwright mendapat lokasi (berjendela vs `--headless`).
   Jalankan `magang-portal check`; lihat `"location"`. Bila `false`, tool berhenti, tidak memalsukan.
2. **Perilaku form asli** yang tidak ada di snapshot: aturan aktif/nonaktif tombol kirim, teks galat
   lokasi, ada/tidaknya dialog konfirmasi setelah *Simpan dan Kirim*. Adapter mengandalkan
   verifikasi status kalender, yang sudah ditulis sesuai label asli.
3. **Mencentang pernyataan:** checkbox Vuetify kadang tersembunyi; ada cadangan klik label, belum
   teruji di portal asli.
4. **Baca-balik isi teks** setelah kirim: butuh snapshot halaman detail hari yang sudah terkirim
   (mis. klik tanggal 26 Okt, simpan halamannya). Sekarang verifikasi hanya lewat status hari.
5. **Label status lain** (`Hadir disetujui`, `Menunggu Tindakan Mentor`, dll.) hanya terlihat di
   legenda; bentuk `aria-label`-nya belum dikonfirmasi. Yang belum dikenal diperlakukan aman (berhenti).
6. **Pindah periode** (21 Okt–20 Nov = "Periode 2") belum didukung; tanggal di luar periode yang
   tampil → `GAGAL` dengan pesan jelas.
7. **Tanggal terkunci:** pada 27 Okt, tanggal 23 Okt berstatus *Belum Diisi* tetapi tombolnya nonaktif.
   Jadi ada batas waktu pengisian; mengisi ulang hari lampau (backfill) mungkin tidak bisa.
