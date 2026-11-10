# =====================================================================
# Build & Package Script untuk MagangLog Portal Installer
# Menghasilkan installer .exe siap distribusi ke klien via Inno Setup
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " [1/3] Memulai Publish Mandiri .NET 8 (Self-Contained) ... " -ForegroundColor Yellow
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

Write-Host "`n[OK] Publish berhasil! Binary tersimpan di: $publishDir" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " [2/3] Memeriksa Instalasi Inno Setup Compiler ...        " -ForegroundColor Yellow
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
Write-Host " [3/3] Mengompilasi Installer via Inno Setup (ISCC) ...  " -ForegroundColor Yellow
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
Write-Host " SELAMAT! Installer Klien Berhasil Dibuat!               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
if ($outputFile) {
    $sizeMb = [math]::Round($outputFile.Length / 1MB, 2)
    Write-Host " Lokasi File : $($outputFile.FullName)" -ForegroundColor White
    Write-Host " Ukuran File : $sizeMb MB" -ForegroundColor White
    Write-Host "`nFile ini dapat langsung dibagikan dan di-instal di laptop/PC klien." -ForegroundColor Cyan
}

