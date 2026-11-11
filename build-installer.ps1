# =====================================================================
# Build & Package Script untuk MagangLog Portal Installer (100% Standalone)
# Menghasilkan installer .exe siap distribusi ke klien via Inno Setup
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " [1/4] Memulai Publish Mandiri .NET 8 (Self-Contained) ... " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$publishDir = "publish\desktop-bundle"
if (Test-Path $publishDir) {
    Remove-Item -Recurse -Force $publishDir -ErrorAction SilentlyContinue
}

dotnet publish desktop/MagangLog.Desktop/MagangLog.Desktop.csproj `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -o $publishDir

if ($LASTEXITCODE -ne 0) {
    Write-Error "Gagal melakukan publish aplikasi .NET Desktop."
    exit 1
}

Write-Host "`n[OK] Publish .NET selesai! Binary tersimpan di: $publishDir" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " [2/4] Membundle Backend Python (PyInstaller) ...         " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$pythonExe = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$backendDistDir = "publish\backend-dist"
$pyiBuildDir = "build\pyinstaller"

if (Test-Path $backendDistDir) {
    Remove-Item -Recurse -Force $backendDistDir -ErrorAction SilentlyContinue
}
if (Test-Path $pyiBuildDir) {
    Remove-Item -Recurse -Force $pyiBuildDir -ErrorAction SilentlyContinue
}

& $pythonExe -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller belum terpasang di environment Python ($pythonExe). Jalankan: pip install -e '.[build]'"
    exit 1
}

& $pythonExe -m PyInstaller `
    --onedir `
    --console `
    --noconfirm `
    --clean `
    --name magang-log `
    --distpath $backendDistDir `
    --workpath $pyiBuildDir `
    --specpath $pyiBuildDir `
    --collect-all playwright `
    --collect-submodules magang_log `
    --collect-submodules uvicorn `
    --collect-submodules fastapi `
    --collect-submodules starlette `
    --collect-submodules anyio `
    --copy-metadata playwright `
    --copy-metadata magang-log `
    --copy-metadata fastapi `
    --copy-metadata uvicorn `
    --copy-metadata pydantic `
    src\magang_log\_entry.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Gagal melakukan bundling backend Python dengan PyInstaller."
    exit 1
}

Write-Host "`n[OK] Backend Python berhasil dibundle di: $backendDistDir\magang-log" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " [3/4] Memeriksa Instalasi Inno Setup Compiler ...        " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$isccCandidates = @(
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Get-Command iscc -ErrorAction SilentlyContinue).Source
)

$isccPath = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $isccPath) {
    Write-Error "ISCC.exe tidak ditemukan. Pastikan Inno Setup 6 atau 7 terpasang di komputer Anda."
    exit 1
}

Write-Host "[OK] Inno Setup ditemukan di: $isccPath" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " [4/4] Mengompilasi Installer via Inno Setup (ISCC) ...  " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$installerDir = "dist\installer"
if (-not (Test-Path $installerDir)) {
    New-Item -ItemType Directory -Force -Path $installerDir | Out-Null
}

& $isccPath "installer.iss"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Kompilasi Inno Setup gagal."
    exit 1
}

$outputFile = Get-ChildItem -Path $installerDir -Filter "MagangLogPortal_Setup_*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " SELAMAT! Installer Standalone Berhasil Dibuat!           " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
if ($outputFile) {
    $sizeMb = [math]::Round($outputFile.Length / 1MB, 2)
    Write-Host " Lokasi File : $($outputFile.FullName)" -ForegroundColor White
    Write-Host " Ukuran File : $sizeMb MB" -ForegroundColor White
    Write-Host "`nFile ini 100% standalone - langsung instal & pakai tanpa Python/SDK!" -ForegroundColor Cyan
}
