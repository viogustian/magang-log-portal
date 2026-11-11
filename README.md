# MagangLog Portal (v2.0)

Aplikasi desktop Windows (*standalone installer*) dan otomasi CLI untuk membantu menyusun, meninjau, dan mengisi laporan harian logbook di portal **MagangHub Monev** secara rapi, aman, dan terverifikasi.

MagangLog Portal menggabungkan **pengumpul bukti aktivitas kerja lokal** (Git commit, catatan harian, aktivitas aplikasi, dan riwayat browser yang disaring), **AI Drafter (Google Gemini)** dengan sanitasi privasi ketat, **Dashboard Desktop (.NET 8 WinForms)**, serta **otomasi browser Playwright** untuk pengisian form portal tanpa pernah memalsukan lokasi atau mengirim laporan tanpa persetujuan.

---

## Fitur Utama

- **Dashboard Lokal Desktop:** Tampilan kalender bulanan, feed bukti aktivitas harian, editor draf *inline* (validasi minimal 100 & maksimal 5.000 karakter), catatan refleksi cepat, dan pengaturan lengkap.
- **Pengumpul Bukti & Sanitasi Privasi:** Mengumpulkan bukti dari Git commit, catatan manual, aplikasi aktif, dan domain browser yang diizinkan — seluruh path sensitif, username, dan rahasia/token disaring secara deterministik sebelum dikirim ke LLM.
- **Portal Automation Anti-Tamper:** Login manual sekali untuk OTP/CAPTCHA, verifikasi status hari di kalender (hari libur nasional, terkunci, atau sudah terkirim tidak disentuh), cek lokasi perangkat, serta verifikasi ulang dari server setelah submit.
- **Otomasi Terjadwal & CLI Lengkap:** Mendukung Windows Task Scheduler (`scripts/install_task.ps1`), audit riwayat (`status`, `report`), dan ekspor ke Markdown (`export`).

---

## Cara 1: Instalasi Pengguna Umum (via Installer `.exe`)

### Kebutuhan Minimum di Laptop Pengguna
1. **Windows 10 / Windows 11 (64-bit).**
2. **Google Chrome** sudah terpasang (digunakan untuk membuka & mengisi portal MagangHub).
3. **Gemini API Key** gratis dari [Google AI Studio](https://aistudio.google.com/apikey).
4. **Git for Windows** *(opsional — hanya diperlukan jika Anda ingin mengambil bukti aktivitas otomatis dari riwayat commit Git proyek Anda)*.

> **Catatan:** Anda **tidak perlu** menginstal Python, **tidak perlu** menginstal .NET SDK, dan **tidak perlu** mengetik perintah terminal apa pun.

### Langkah Pemasangan & Pemakaian
1. Buka halaman **[Releases Terbaru di GitHub](https://github.com/viogustian/magang-log-portal/releases/latest)** dan unduh file **[`MagangLogPortal_Setup_v2.0.0.exe`](https://github.com/viogustian/magang-log-portal/releases/latest/download/MagangLogPortal_Setup_v2.0.0.exe)**.
2. Jalankan file installer `.exe` tersebut:
   - Jika muncul peringatan **Windows Defender SmartScreen** (*"Windows protected your PC"*), klik **More info** → **Run anyway** *(wajar untuk aplikasi open-source tanpa sertifikat tanda tangan berbayar)*.
   - Klik **Next → Install → Finish** *(bisa diinstal per-user tanpa hak Administrator)*.
3. Buka aplikasi **MagangLog Portal** dari Start Menu atau ikon Desktop.
4. Jalankan **Setup Wizard** lalu lakukan:
   - **Langkah 1 (Sistem & Gemini API):** Pastikan status requirement siap, lalu masukkan **Gemini API Key** Anda dan klik tes koneksi.
   - **Langkah 2 (Folder Proyek):** Pilih folder proyek/repositori Git tempat Anda bekerja.
   - **Langkah 3 (Profil Kerja & Kata Kunci):** Pilih bidang/peran magang Anda (atau gunakan preset bawaan seperti *Software Engineer*, dll.).
   - **Langkah 4 (Sumber Bukti & Privasi):** Pilih sumber bukti yang diizinkan (Git, Catatan, Aplikasi, Browser) dan setujui ketentuan privasi.
   - **Langkah 5 (Mode Pengiriman):** Pilih apakah laporan ditinjau manual sebelum dikirim (*Review*) atau mode lain sesuai kebutuhan.
   - **Langkah 6 (Ringkasan & Simpan):** Periksa ringkasan lalu simpan konfigurasi.
5. **Login ke Portal MagangHub (Sekali Saja):**
   - Klik tombol **Login Portal** di Dashboard utama.
   - Jendela Google Chrome akan terbuka ke MagangHub Monev — silakan login serta isi **OTP / CAPTCHA** seperti biasa.
   - Setelah berhasil masuk ke halaman Riwayat Kehadiran, sesi Anda tersimpan aman secara lokal di folder `data\auth\state.json`.

---

## Cara 2: Setup Developer (Dari Source Code)

Jika Anda ingin memodifikasi kode, menjalankan pengujian, atau mem-build installer sendiri:

### Prasyarat Developer
- Python **3.12+** (centang *Add python.exe to PATH*)
- **.NET 8 SDK** ([dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet/8.0))
- Git for Windows & Google Chrome
- [Inno Setup 6 atau 7](https://jrsoftware.org/isdl.php) *(jika ingin mem-build `.exe` installer)*

### 1. Clone & Siapkan Environment
```powershell
git clone https://github.com/viogustian/magang-log-portal.git
cd magang-log-portal

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev,build]"
playwright install chromium
```

### 2. Menjalankan Aplikasi Desktop saat Development
```powershell
# Menjalankan GUI Desktop (.NET 8 WinForms) — otomatis menyalakan backend lokal di 127.0.0.1:8765
dotnet run --project desktop/MagangLog.Desktop/MagangLog.Desktop.csproj
```

Atau jalankan server backend secara terpisah:
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

### 4. Mem-build Installer Standalone (`.exe`)
Skrip berikut otomatis mengompilasi `.NET 8 Desktop`, membundle `Backend Python` via PyInstaller, lalu mem-package semuanya ke Inno Setup:

```powershell
.\build-installer.ps1
```
Hasil installer siap distribusi akan tersimpan di: `dist\installer\MagangLogPortal_Setup_v2.0.0.exe`.

---

## Panduan Singkat CLI (`magang-log` / `magang-portal`)

Seluruh perintah CLI juga tersedia untuk pengguna tingkat lanjut (baik lewat `backend\magang-log.exe` di folder instalasi maupun `magang-log` di `.venv` developer):

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

- **Penyimpanan Lokal:** Kunci API Gemini (`.env`), konfigurasi pribadi (`config/config.yaml`), sesi login (`data/auth/state.json`), database ledger (`data/state.db`), dan log (`data/logs/`) disimpan **sepenuhnya di komputer Anda** dan dikecualikan dari Git melalui `.gitignore`.
- **Server Loopback Ketat:** Backend FastAPI hanya mengikat alamat lokal (`127.0.0.1`) dan tidak terbuka ke jaringan luar.
- **Anti-Pemalsuan:** Aplikasi tidak pernah memalsukan lokasi perangkat maupun mencentang pernyataan kirim otomatis tanpa persetujuan eksplisit Anda (`approved_at`).

---

## Pemecahan Masalah Umum (Troubleshooting)

- **Windows memblokir installer saat dibuka (SmartScreen *"Windows protected your PC"*):**
  Klik **More info** lalu pilih **Run anyway**. Installer open-source ini dikompilasi bersih dari repositori ini tanpa sertifikat *code-signing* komersial.
- **Aplikasi Desktop menampilkan status server *Offline*:**
  Tunggu beberapa detik saat peluncuran awal, atau pastikan port `8765` tidak sedang dipakai aplikasi lain lalu buka ulang aplikasi.
- **Gagal membuka browser saat klik Login Portal:**
  Pastikan **Google Chrome** terinstal di Windows.
- **Gagal mengisi laporan karena lokasi (`LOKASI_TIDAK_TERSEDIA`):**
  Aktifkan *Location Services* di pengaturan Windows dan izinkan akses lokasi saat jendela Chrome portal terbuka.

---

**Pengembang Utama:** Vio Gustian Nur Alamsyah ([@viogustian](https://github.com/viogustian))
