<p align="center">
  <img src="icon.png" alt="MagangLog Portal Logo" width="180" />
</p>

<h1 align="center">MagangLog Portal (v2.0)</h1>

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

## Arsitektur Privasi Data, Etika AI (Gemini) & Guardrails Keamanan

Aplikasi ini dibangun dengan prinsip **Privacy by Design**, **Zero Surveillance Boundary**, dan **Human-in-the-Loop**. Seluruh pembatasan berikut ditegakkan langsung di level kode Python (bukan sekadar aturan prompt):

### 1. Sanitasi Privasi Deterministik Pra-LLM ([`collectors/privacy.py`](src/magang_log/collectors/privacy.py))
Sebelum bukti aktivitas apa pun dikirim ke Gemini API, fungsi `collect_and_sanitize_evidence()` ([`collectors/factory.py`](src/magang_log/collectors/factory.py)) menjalankan `DeterministicPrivacyEngine` dengan urutan 8 tahap deterministik:
1. **Penyaringan Password (`redact_passwords=True`):** Assignment seperti `password=...` atau `password:...` otomatis diganti menjadi `[REDACTED_PASSWORD]`.
2. **Penyaringan Token & API Key (`redact_tokens=True`):** Regex khusus mendeteksi dan menyensor Bearer token, GitHub PAT (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Slack token (`xox[baprs]-`), GitLab PAT (`glpat-`), AWS Access Key (`AKIA...`), prefix key `sk-...`, serta parameter `api_key`, `access_token`, `auth_token`, `secret_key`, dan `token` menjadi `[REDACTED_TOKEN]`.
3. **Penyaringan Email (`redact_emails=True`):** Alamat email disensor menjadi `[REDACTED_EMAIL]`.
4. **Penyaringan IPv4 Privat (`redact_ips=True`):** Alamat jaringan internal (`10.x.x.x`, `172.16.x.x`–`172.31.x.x`, `192.168.x.x`) disensor menjadi `[REDACTED_IP]`.
5. **Relativisasi Path Lokal (`redact_paths=True`):** Path absolut Windows (`C:\...`, `Program Files`) dan Unix (`/home/...`, `/Users/...`) diubah menjadi path relatif terhadap `repo_roots`, atau diganti `[REDACTED_PATH]` bila berada di luar direktori proyek kerja.
6. **Penyaringan Username OS (`redact_usernames=True`):** Mendeteksi nama pengguna sistem dari variabel lingkungan (`USERNAME`, `USER`, `LOGNAME`), `getpass.getuser()`, `os.getlogin()`, maupun `custom_usernames` lalu menyensornya menjadi `[USER]`.
7. **Aturan Kustom (`custom_rules`):** Mendukung pola regex penyensoran tambahan sesuai kebijakan instansi/perusahaan Anda.
8. **Pembatasan Panjang Teks:** Membatasi `max_title_length` maksimal `300` karakter dan `max_detail_length` maksimal `1000` karakter serta menghitung ulang ID bukti setelah disanitasi.

> Anda dapat memeriksa payload JSON final yang telah disanitasi sebelum dikirim ke Gemini dengan menjalankan `magang-log preview-payload`.

### 2. Minimasi Data & *Zero Surveillance Boundary* pada Kolektor
- **Git Lokal ([`collectors/git.py`](src/magang_log/collectors/git.py), [`settings.py`](src/magang_log/settings.py)):** Secara bawaan `include_diff: False` dan `send_to_llm: ["commit_message", "file_paths_relative"]`. Kolektor hanya mengambil metadata commit (`git show --no-patch`) dan statistik berkas relatif (`--numstat`) — **isi *source code* maupun *diff patch* proyek perusahaan tidak dikirim ke AI**.
- **Riwayat Browser ([`collectors/browser.py`](src/magang_log/collectors/browser.py)):** Dinonaktifkan secara default (`enabled: False`). Bila diaktifkan:
  - Hanya domain pada daftar izin (*allowlist*) yang diambil melalui `is_domain_allowed()` — seluruh riwayat domain lain diabaikan.
  - Database `History` disalin ke berkas snapshot sementara dan dibuka dalam mode read-only `sqlite3` (`?immutable=1`) lalu langsung dihapus (`unlink`).
  - Fungsi `sanitize_url()` menghapus seluruh *query string* (`?...`) dan *hash fragment* (`#...`) agar token sesi atau parameter privat di URL tidak pernah terbawa.
- **Aktivitas Aplikasi Desktop ([`collectors/app.py`](src/magang_log/collectors/app.py), [`recent.py`](src/magang_log/collectors/recent.py), [`session_log.py`](src/magang_log/collectors/session_log.py)):** Menerapkan *strict opt-in allowlist* berdasarkan ekstensi file dan proses di `WorkProfile`. Tanpa `WorkProfile` aktif, kolektor mengembalikan hasil kosong (*zero surveillance boundary*). Path direktori pengguna (`C:\Users\<user>`) disingkat menjadi `~` lewat `sanitize_path()`, dan detail log sesi disaring melalui `sanitize_log_detail()` (`SENSITIVE_PARAM_REGEX` → `[REDACTED]`).
- **Evidence Strength Gate ([`collectors/strength.py`](src/magang_log/collectors/strength.py)):** Fungsi `evaluate_evidence_strength()` memblokir pemanggilan Gemini (`PERLU_INPUT`, exit code `10`) jika tidak ada minimal 1 bukti kategori `strong` (commit Git atau catatan manual), dan `filter_evidence_for_llm()` menghormati saklar `send_to_llm` per sumber.

### 3. Etika AI (Google Gemini) & Guardrails Generasi Draf
- **Klien REST Tanpa Akses Eksekusi Tool ([`drafter/client.py`](src/magang_log/drafter/client.py)):** `GeminiModelClient` menghubungi endpoint resmi Gemini `generateContent` dengan keluaran JSON terstruktur (`response_mime_type: "application/json"`) **tanpa kemampuan *tool calling* / eksekusi sistem** (`tools: None`). Model tidak bisa membaca file di luar payload, menjalankan perintah shell, atau mengirim form sendiri. API Key dikirim lewat header `x-goog-api-key` (bukan query URL), dengan batas default `max_input_tokens: 6000` dan `daily_token_budget: 20000` ([`settings.py`](src/magang_log/settings.py)).
- **Anti-Halusinasi & Anti-Filler ([`prompts/draft_logbook.v1.md`](prompts/draft_logbook.v1.md), [`drafter/engine.py`](src/magang_log/drafter/engine.py)):**
  - *Hard constraint* melarang AI mengarang kegiatan di luar bukti atau memakai kalimat klise (*boilerplate* seperti *"berjalan lancar tanpa kendala"*).
  - Bila bukti tidak memuat kendala atau pembelajaran nyata, `EvidenceDrafter` otomatis menambahkan kolom terkait ke daftar `needs_input` agar dilengkapi manusia (bukan dikarang oleh AI).
- **Pertahanan terhadap *Prompt Injection* ([`drafter/engine.py`](src/magang_log/drafter/engine.py)):** Seluruh bukti dibungkus dalam blok `<bukti>...</bukti>` sebagai *untrusted passive data*, dengan instruksi tegas kepada model untuk mengabaikan perintah atau instruksi manipulasi peran yang mungkin terselip di dalam pesan commit maupun catatan.
- **Validator Deterministik & *Self-Correction Loop* ([`validator/engine.py`](src/magang_log/validator/engine.py), [`validator/rules.py`](src/magang_log/validator/rules.py), [`drafter/stage.py`](src/magang_log/drafter/stage.py)):** Setiap keluaran Gemini diperiksa oleh `MultiStageValidator` (maksimal `max_retries=2` di `DraftingStage`):
  - Memastikan panjang teks tiap kolom `100`–`5000` karakter.
  - Menolak format terlarang: kode Markdown (`` ``` ``, `` ` ``), bullet point (`*`, `-`, `+`, `•`), tag HTML, URL mentah, dan email.
  - Mendeteksi *canned filler* (`CANNED_FILLER_PHRASES`), keragaman leksikal rendah (`compute_lexical_diversity` `< 0.4`), serta pengulangan kalimat/trigram berlebih (`compute_repetition_ratio` `> 0.3`).
  - Menghitung **Grounding Score** (`compute_grounding_score()`) guna mengecek keterhubungan kalimat `aktivitas` terhadap ID bukti terverifikasi.
- **Kendali Manusia (*Human-in-the-Loop*) ([`reviewer/auto_approval.py`](src/magang_log/reviewer/auto_approval.py), [`settings.py`](src/magang_log/settings.py)):** Secara default `review.mode` bernilai `"review"` dan `auto_if_confident` bernilai `False`. Bahkan jika diaktifkan, `ConditionalAutoApprovalEngine` hanya meloloskan draf apabila `validation.is_valid == True`, `len(warnings) == 0`, `grounding_score >= 0.8`, sudah ada minimal `10` riwayat entri yang disetujui manusia, serta median rasio suntingan manusia historis `<= 0.15`.

### 4. Keamanan Server Lokal, Audit Log & Anti-Tamper Portal
- **Server Loopback Ketat ([`server/config.py`](src/magang_log/server/config.py)):** `ServerConfig` mewajibkan `is_loopback(host)` saat startup (`127.0.0.1`, `localhost`, atau IP loopback valid lain) dan melempar `ValueError` bila ada upaya binding ke antarmuka jaringan eksternal.
- **Privacy Guard pada Logging ([`logger.py`](src/magang_log/logger.py)):** `check_privacy_guard()` melarang penulisan field privat (`PROHIBITED_INFO_FIELDS`: `aktivitas`, `pembelajaran`, `kendala`, `draft`, `evidence`, `secret`, `password`, `token`, `api_key`, dll.) pada log level `INFO` (`data/logs/magang-log.jsonl`) dan memicu `PrivacyViolationError` bila dilanggar.
- **Proteksi Sesi & Anti-Tamper Portal ([`portal/session.py`](src/magang_log/portal/session.py), [`portal/anti_tamper.py`](src/magang_log/portal/anti_tamper.py), [`portal/device_location.py`](src/magang_log/portal/device_location.py), [`portal/playwright_portal.py`](src/magang_log/portal/playwright_portal.py)):**
  - **Tanpa Penyimpanan Password/OTP:** Login ke portal MagangHub dilakukan interaktif langsung oleh pengguna; sesi tersimpan lokal di `data/auth/state.json` (dengan `os.chmod(..., 0o600)` di POSIX).
  - **Fail-Closed Anti-Tamper Gate:** `AntiTamperGate.inspect()` mengevaluasi `aria-label` dan atribut `disabled` tombol hari di kalender sebelum menyentuh form — hari berstatus `LIBUR`, `TERKUNCI`, `SUDAH_TERKIRIM`, `PERLU_TINDAKAN`, atau `TIDAK_DIKENAL` langsung menghentikan proses.
  - **Lokasi Asli Perangkat (Tanpa Spoofing):** `get_windows_device_location()` membaca koordinat fisik perangkat melalui sensor OS Windows (`System.Device.Location.GeoCoordinateWatcher`), dan izin geolocation hanya diberikan ke origin portal. Jika lokasi gagal terbaca, pengiriman dihentikan dengan status `LOKASI_TIDAK_TERSEDIA`.
  - **Gerbang Persetujuan & Verifikasi Server:** `assert_approved_for_submission()` memblokir pengiriman apabila `approved_at` kosong (perlu persetujuan eksplisit di UI atau ketik `Y`/`YES`/`SETUJU` di CLI). Setelah submit, `_verify_after_submit()` memuat ulang halaman dari server untuk memverifikasi perubahan status secara nyata.
- **Isolasi Penyimpanan Lokal ([`.gitignore`](.gitignore)):** Direktori `data/`, database `*.db`/`state.db`, `state.json`, `.env`, `config.yaml`, `wizard-progress.yaml`, kunci/sertifikat (`*.pem`, `*.key`), dan log dikecualikan dari Git agar tidak pernah bocor ke repositori.

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
