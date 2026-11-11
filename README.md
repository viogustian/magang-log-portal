# MagangLog Portal (v2.0)

Aplikasi desktop Windows dan otomasi CLI untuk membantu menyusun, meninjau, dan mengisi laporan harian logbook di portal **MagangHub Monev** secara rapi, aman, dan terverifikasi.

MagangLog Portal menggabungkan **pengumpul bukti aktivitas kerja lokal** (Git commit, catatan harian, aktivitas aplikasi, dan riwayat browser yang disaring), **AI Drafter (Google Gemini)** dengan sanitasi privasi ketat, **Dashboard Desktop (.NET 8 WinForms)**, serta **otomasi browser Playwright** untuk pengisian form portal tanpa pernah memalsukan lokasi atau mengirim laporan tanpa persetujuan.

---

## Fitur Utama

- **Setup Wizard 6 Langkah:** Panduan instalasi awal terpadu untuk cek prasyarat sistem, tes koneksi Gemini API Key, pilih folder proyek Git, atur profil kerja, privasi, hingga penjadwalan otomatis.
- **Dashboard Lokal Desktop:** Tampilan kalender bulanan, feed bukti aktivitas harian, editor draf *inline* (validasi minimal 100 & maksimal 5.000 karakter), catatan refleksi cepat, dan pengaturan lengkap.
- **Pengumpul Bukti & Sanitasi Privasi:** Mengumpulkan bukti dari Git commit, catatan manual, aplikasi aktif, dan domain browser yang diizinkan — seluruh path sensitif, username, dan rahasia/token disaring secara deterministik sebelum dikirim ke LLM.
- **Portal Automation Anti-Tamper:** Login manual sekali untuk OTP/CAPTCHA, verifikasi status hari di kalender (hari libur nasional, terkunci, atau sudah terkirim tidak disentuh), cek lokasi perangkat, serta verifikasi ulang dari server setelah submit.
- **Otomasi Terjadwal & CLI Lengkap:** Mendukung Windows Task Scheduler (`scripts/install_task.ps1`), audit riwayat (`status`, `report`), dan ekspor ke Markdown (`export`).

---

## Prasyarat Sistem

Sebelum memulai, pastikan komputer Windows Anda sudah memenuhi kebutuhan berikut:

1. **Sistem Operasi:** Windows 10 atau Windows 11 (64-bit).
2. **Python 3.12 atau lebih baru:** Unduh dari [python.org](https://www.python.org/downloads/windows/).
   > **Penting:** Saat menginstal Python, pastikan Anda mencentang opsi **"Add python.exe to PATH"**.
3. **Google Chrome:** Terpasang di Windows (digunakan oleh Playwright untuk login & isi portal MagangHub).
4. **Git for Windows:** Unduh dari [git-scm.com](https://git-scm.com/download/win) *(disarankan jika ingin mengambil bukti aktivitas dari commit Git)*.
5. **Gemini API Key:** Kunci API gratis dari [Google AI Studio](https://aistudio.google.com/apikey).
6. **.NET 8 SDK *(Khusus Developer)*:** Hanya dibutuhkan jika Anda menjalankan atau mem-build aplikasi dari source code. Pengguna installer `.exe` **tidak perlu** menginstal .NET 8 secara terpisah.

---

## Cara 1: Instalasi Mudah (Untuk Pengguna Umum via Installer `.exe`)

### Langkah 1 — Unduh & Instal Aplikasi
1. Buka halaman **[Releases di GitHub](https://github.com/viogustian/magang-log-portal/releases)**.
2. Unduh file **`MagangLogPortal_Setup_v2.0.0.exe`** pada rilis terbaru.
3. Jalankan installer tersebut dan ikuti petunjuk hingga selesai *(tidak memerlukan hak Administrator)*.
   - Lokasi instalasi default: `%LOCALAPPDATA%\Programs\MagangLog Portal`

### Langkah 2 — Siapkan Environment Python (Cukup Sekali)
Agar aplikasi desktop dapat menjalankan mesin backend & Playwright di latar belakang, buka **PowerShell** lalu jalankan perintah berikut:

```powershell
# 1. Masuk ke folder instalasi MagangLog Portal
cd "$env:LOCALAPPDATA\Programs\MagangLog Portal"

# 2. Buat virtual environment (.venv) dan aktifkan
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Pasang paket backend Python & browser Playwright
pip install -e .
playwright install chromium
```

> **Catatan PowerShell:** Jika muncul pesan error *"execution of scripts is disabled on this system"* saat menjalankan `Activate.ps1`, jalankan perintah berikut sekali saja lalu ulangi langkah aktivasi:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Langkah 3 — Jalankan Aplikasi & Setup Wizard
1. Buka **MagangLog Portal** dari Start Menu atau ikon Desktop.
2. Saat pertama kali dibuka, **Setup Wizard (6 Langkah)** akan muncul otomatis:
   - **Langkah 1 (Kebutuhan Sistem & Gemini API):** Pastikan status kebutuhan sistem berwarna hijau/OK, lalu masukkan **Gemini API Key** Anda dan tekan tombol tes koneksi.
   - **Langkah 2 (Folder Proyek):** Tambahkan folder proyek/repositori Git tempat Anda bekerja.
   - **Langkah 3 (Profil Kerja & Kata Kunci):** Pilih peran magang Anda (atau gunakan preset bawaan) agar draf laporan sesuai bidang kerja.
   - **Langkah 4 (Sumber Bukti & Privasi):** Pilih sumber bukti yang diizinkan (Git, Catatan, Aplikasi, Browser) dan setujui ketentuan privasi.
   - **Langkah 5 (Mode Pengiriman):** Pilih apakah laporan selalu ditinjau manual sebelum dikirim (*Review*) atau mode lain sesuai kebutuhan.
   - **Langkah 6 (Ringkasan & Simpan):** Periksa ulang pengaturan lalu klik simpan untuk membuat file `config/config.yaml`.

### Langkah 4 — Login ke Portal MagangHub (Sekali Saja)
1. Pada Dashboard utama, klik tombol **Login Portal** *(atau melalui terminal dengan `magang-portal login`)*.
2. Jendela Google Chrome akan terbuka ke halaman MagangHub Monev.
3. Silakan login seperti biasa termasuk mengisi **OTP / CAPTCHA secara manual**.
4. Setelah berhasil masuk ke halaman Riwayat Kehadiran, sesi Anda otomatis disimpan secara lokal di `data/auth/state.json` sehingga tidak perlu login berulang kali.

---

## Cara 2: Setup Developer (Dari Source Code)

Jika Anda ingin memodifikasi kode, menjalankan pengujian, atau mem-build installer sendiri:

### 1. Clone Repositori & Siapkan Virtual Environment
```powershell
git clone https://github.com/viogustian/magang-log-portal.git
cd magang-log-portal

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
playwright install chromium
```

### 2. Menjalankan Aplikasi Desktop saat Development
```powershell
# Menjalankan GUI Desktop (.NET 8 WinForms) — otomatis menyalakan backend FastAPI di 127.0.0.1:8765
dotnet run --project desktop/MagangLog.Desktop/MagangLog.Desktop.csproj
```

Atau jalankan hanya server backend secara terpisah:
```powershell
magang-log ui --port 8765 --server-only
```

### 3. Menjalankan Pengujian & Linter
```powershell
# Pengujian Backend Python & Portal Playwright (Mock)
pytest

# Linter kode Python
ruff check src tests

# Pengujian Aplikasi Desktop (.NET 8 xUnit)
dotnet test desktop/MagangLog.slnx
```

### 4. Mem-build Installer Windows (`.exe`) Sendiri
Pastikan [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) dan [Inno Setup 6 atau 7](https://jrsoftware.org/isdl.php) sudah terpasang di Windows, lalu jalankan:

```powershell
.\build-installer.ps1
```
Hasil installer siap distribusi akan dibuat di: `dist\installer\MagangLogPortal_Setup_v2.0.0.exe`.

---

## Panduan Singkat CLI (`magang-log` / `magang-portal`)

Selain menggunakan tampilan Desktop GUI, seluruh fitur juga dapat dijalankan langsung lewat terminal (pastikan `.venv` aktif):

| Perintah | Fungsi |
| :--- | :--- |
| `magang-log login` | Membuka browser untuk login manual ke portal MagangHub dan menyimpan sesi |
| `magang-log check` | Diagnosis *read-only*: cek status login, tanggal hari ini, akses lokasi, dan selector portal |
| `magang-log doctor` | Memeriksa kesehatan konfigurasi lokal, database, dan jadwal (`--portal` untuk cek selector) |
| `magang-log note "Isi catatan" --type aktivitas` | Menambah catatan manual (`--type`: `aktivitas`, `pembelajaran`, atau `kendala`) |
| `magang-log preview-evidence` | Melihat bukti aktivitas yang terkumpul hari ini tanpa menyentuh LLM/portal |
| `magang-log preview-payload` | Melihat payload JSON yang akan dikirim ke Gemini (sudah disanitasi privasinya) |
| `magang-log run --dry-run` | Menjalankan simulasi pipeline penuh tanpa mengirim ke portal |
| `magang-log run` | Menjalankan pipeline harian lengkap (kumpul bukti → buat draf → validasi → review → submit) |
| `magang-log review` | Meninjau dan menyetujui draf logbook secara interaktif di terminal |
| `magang-log submit` | Mengisi form portal, meminta konfirmasi `SETUJU`, mengirim, dan memverifikasi ulang |
| `magang-log status` | Menampilkan tabel status logbook 14 hari terakhir |
| `magang-log export -o logbook.md` | Mengekspor seluruh logbook yang sudah disetujui ke file Markdown |

> **Kode Keluar (Exit Codes):** `0` = sukses/dilewati dengan aman, `10` = perlu tindakan pengguna, `20` = perlu login ulang, `40` = gagal/terkunci/lokasi tidak tersedia.

---

## Keamanan & Privasi Data

- **Penyimpanan Lokal:** Kunci API Gemini (`.env`), konfigurasi pribadi (`config/config.yaml`), sesi login (`data/auth/state.json`), database ledger (`data/state.db`), dan log (`data/logs/`) disimpan **sepenuhnya di komputer Anda** dan sudah dikecualikan dari Git melalui `.gitignore`.
- **Server Loopback Ketat:** Backend FastAPI hanya mengikat alamat lokal (`127.0.0.1`) dan tidak terbuka ke jaringan luar.
- **Anti-Pemalsuan:** Aplikasi tidak pernah memalsukan lokasi perangkat maupun mencentang pernyataan kirim otomatis tanpa persetujuan eksplisit Anda (`approved_at`).

---

## Pemecahan Masalah Umum (Troubleshooting)

- **Aplikasi Desktop menampilkan status server *Offline*:**
  Pastikan Python >= 3.12 sudah terpasang di `PATH` dan langkah `pip install -e .` sudah dijalankan di dalam `.venv` pada folder aplikasi. Cek apakah port `8765` tidak sedang dipakai aplikasi lain.
- **Playwright gagal membuka browser:**
  Jalankan ulang `playwright install chromium` di dalam `.venv` dan pastikan Google Chrome sudah terinstal di Windows.
- **Gagal mengisi laporan karena lokasi (`LOKASI_TIDAK_TERSEDIA`):**
  Pastikan izin lokasi (*Location Services*) di Windows aktif dan izinkan akses lokasi saat jendela Chrome portal terbuka.

---

**Pengembang Utama:** Vio Gustian Nur Alamsyah ([@viogustian](https://github.com/viogustian))
