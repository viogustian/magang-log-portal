<#
.SYNOPSIS
    Manajemen otomasi penjadwalan Windows Task Scheduler untuk magang-log.

.DESCRIPTION
    Mengonfigurasi dua jadwal eksekusi harian otomatis via Windows Task Scheduler:
    1. Afternoon Review (16:30): magang-log run --mode review
    2. Evening Resume (20:00): magang-log run --resume

.PARAMETER Install
    Mendaftarkan kedua tugas terjadwal ke Windows Task Scheduler.

.PARAMETER Uninstall
    Menghapus kedua tugas terjadwal dari Windows Task Scheduler.

.PARAMETER Status
    Menampilkan status registrasi, jadwal berikutnya, dan kode keluar terakhir.

.PARAMETER ReviewTime
    Jam eksekusi review sore (default: "16:30").

.PARAMETER ResumeTime
    Jam eksekusi resume malam (default: "20:00").

.PARAMETER ProjectPath
    Direktori kerja root proyek (default: root direktori magang-log-portal).

.PARAMETER TaskPrefix
    Prefix nama tugas di Windows Task Scheduler (default: "MagangLog").
#>

[CmdletBinding(DefaultParameterSetName = "Default")]
param(
    [Parameter(ParameterSetName = "Install")]
    [switch]$Install,

    [Parameter(ParameterSetName = "Uninstall")]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = "Status")]
    [switch]$Status,

    [Parameter()]
    [string]$ReviewTime = "16:30",

    [Parameter()]
    [string]$ResumeTime = "20:00",

    [Parameter()]
    [string]$ProjectPath = "",

    [Parameter()]
    [string]$TaskPrefix = "MagangLog"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Tentukan root proyek jika tidak dispesifikasikan
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectPath = (Resolve-Path $ProjectPath).Path
}

$taskReviewName = "$TaskPrefix-Review"
$taskResumeName = "$TaskPrefix-Resume"

if (-not $Install -and -not $Uninstall -and -not $Status) {
    $Status = $true
}

# --- 1. INSTALASI TUGAS TERJADWAL ---
if ($Install) {
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host " MENDAFTARKAN JADWAL TUGAS WINDOWS TASK SCHEDULER ($TaskPrefix)" -ForegroundColor Cyan
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host "Akun Pengguna: $env:USERNAME"
    Write-Host "Direktori    : $ProjectPath"
    Write-Host "Tugas 1      : $taskReviewName (Pukul $ReviewTime, magang-log run --mode review)"
    Write-Host "Tugas 2      : $taskResumeName (Pukul $ResumeTime, magang-log run --resume)"
    Write-Host "--------------------------------------------------------------------------"

    # Pastikan direktori logs tersedia
    $logsDir = Join-Path $ProjectPath "data\logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    }

    $psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

    # Perintah eksekusi terisolasi, non-interaktif, tanpa pop-up window
    $reviewCmd = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& { Set-Location '$ProjectPath'; New-Item -ItemType Directory -Force -Path 'data/logs' | Out-Null; `$env:PYTHONUNBUFFERED='1'; `$exe = if (Test-Path '.venv\Scripts\magang-log.exe') { '.venv\Scripts\magang-log.exe' } else { 'magang-log' }; & `$exe run --mode review *>> 'data/logs/task_review.log'; exit `$LASTEXITCODE }`""
    $resumeCmd = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& { Set-Location '$ProjectPath'; New-Item -ItemType Directory -Force -Path 'data/logs' | Out-Null; `$env:PYTHONUNBUFFERED='1'; `$exe = if (Test-Path '.venv\Scripts\magang-log.exe') { '.venv\Scripts\magang-log.exe' } else { 'magang-log' }; & `$exe run --resume *>> 'data/logs/task_resume.log'; exit `$LASTEXITCODE }`""

    $actionReview = New-ScheduledTaskAction -Execute $psExe -Argument $reviewCmd -WorkingDirectory $ProjectPath
    $actionResume = New-ScheduledTaskAction -Execute $psExe -Argument $resumeCmd -WorkingDirectory $ProjectPath

    # Trigger harian
    $triggerReview = New-ScheduledTaskTrigger -Daily -At $ReviewTime
    $triggerResume = New-ScheduledTaskTrigger -Daily -At $ResumeTime

    # Pengaturan eksekusi tangguh (StartWhenAvailable, baterai laptop, batas waktu 10 menit)
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    # Jalankan di bawah akun pengguna saat ini tanpa meminta kata sandi
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

    try {
        Register-ScheduledTask `
            -TaskName $taskReviewName `
            -Action $actionReview `
            -Trigger $triggerReview `
            -Settings $settings `
            -Principal $principal `
            -Description "MagangLog Otomasi Sore: mengumpulkan bukti, membuat draf logbook, dan mengirim notifikasi review." `
            -Force | Out-Null
        Write-Host "[OK] Tugas '$taskReviewName' berhasil didaftarkan (Pukul $ReviewTime)." -ForegroundColor Green
    } catch {
        Write-Error "Gagal mendaftarkan tugas '$taskReviewName': $_"
    }

    try {
        Register-ScheduledTask `
            -TaskName $taskResumeName `
            -Action $actionResume `
            -Trigger $triggerResume `
            -Settings $settings `
            -Principal $principal `
            -Description "MagangLog Otomasi Malam: memulihkan alur pengiriman logbook jika telah disetujui atau mengirim pengingat." `
            -Force | Out-Null
        Write-Host "[OK] Tugas '$taskResumeName' berhasil didaftarkan (Pukul $ResumeTime)." -ForegroundColor Green
    } catch {
        Write-Error "Gagal mendaftarkan tugas '$taskResumeName': $_"
    }

    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host "Instalasi selesai. Jalankan '.\scripts\install_task.ps1 -Status' untuk melihat jadwal." -ForegroundColor Cyan
    exit 0
}

# --- 2. PENGHAPUSAN TUGAS TERJADWAL ---
if ($Uninstall) {
    Write-Host "==========================================================================" -ForegroundColor Yellow
    Write-Host " MENGHAPUS JADWAL TUGAS WINDOWS TASK SCHEDULER ($TaskPrefix)" -ForegroundColor Yellow
    Write-Host "==========================================================================" -ForegroundColor Yellow

    $tasks = @($taskReviewName, $taskResumeName)
    $removedCount = 0

    foreach ($name in $tasks) {
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -ne $existing) {
            try {
                Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
                Write-Host "[OK] Tugas '$name' berhasil dihapus dari Windows Task Scheduler." -ForegroundColor Green
                $removedCount++
            } catch {
                Write-Error "Gagal menghapus tugas '$name': $_"
            }
        } else {
            Write-Host "[INFO] Tugas '$name' tidak ditemukan di Windows Task Scheduler." -ForegroundColor DarkGray
        }
    }

    Write-Host "==========================================================================" -ForegroundColor Yellow
    Write-Host "Penghapusan selesai ($removedCount tugas dihapus)." -ForegroundColor Yellow
    exit 0
}

# --- 3. STATUS TUGAS TERJADWAL ---
if ($Status) {
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host " STATUS PENJADWALAN OTOMASI MAGANG-LOG (WINDOWS TASK SCHEDULER)" -ForegroundColor Cyan
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host "Akun Pengguna: $env:USERNAME"
    Write-Host "Direktori    : $ProjectPath"
    Write-Host "--------------------------------------------------------------------------"

    $tasks = @(
        @{ Name = $taskReviewName; Label = "Review Sore"; Time = $ReviewTime; Mode = "--mode review" },
        @{ Name = $taskResumeName; Label = "Resume Malam"; Time = $ResumeTime; Mode = "--resume" }
    )

    $allRegistered = $true

    foreach ($t in $tasks) {
        $taskObj = Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue
        if ($null -ne $taskObj) {
            $info = Get-ScheduledTaskInfo -TaskName $t.Name -ErrorAction SilentlyContinue
            $lastResult = if ($null -ne $info) { $info.LastTaskResult } else { "N/A" }
            $lastRun = if ($null -ne $info -and $info.LastRunTime -ne [datetime]::MinValue) { $info.LastRunTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "Belum pernah dijalankan" }
            $nextRun = if ($null -ne $info -and $info.NextRunTime -ne [datetime]::MinValue) { $info.NextRunTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "N/A" }

            $resultDesc = switch ($lastResult) {
                0 { "0 (BERHASIL)" }
                10 { "10 (PERLU_TINDAKAN / REVIEW)" }
                20 { "20 (LOGIN_DIPERLUKAN)" }
                30 { "30 (VALIDASI_GAGAL)" }
                40 { "40 (GAGAL / TERKUNCI)" }
                1 { "1 (CRASH / FATAL)" }
                267009 { "267009 (Belum dijalankan)" }
                default { "$lastResult" }
            }

            Write-Host "Tugas        : $($t.Name) ($($t.Label))" -ForegroundColor Green
            Write-Host "Status State : $($taskObj.State)"
            Write-Host "Jadwal Harian: Setiap hari pukul $($t.Time) (magang-log run $($t.Mode))"
            Write-Host "Next Run     : $nextRun"
            Write-Host "Last Run     : $lastRun"
            Write-Host "Last ExitCode: $resultDesc"
            Write-Host "Missed Runs  : $(if ($null -ne $info) { $info.NumberOfMissedRuns } else { 0 })"
        } else {
            $allRegistered = $false
            Write-Host "Tugas        : $($t.Name) ($($t.Label))" -ForegroundColor Yellow
            Write-Host "Status State : [BELUM TERDAFTAR]" -ForegroundColor Red
            Write-Host "Jadwal Target: Setiap hari pukul $($t.Time) (magang-log run $($t.Mode))"
            Write-Host "Panduan      : Jalankan '.\scripts\install_task.ps1 -Install' untuk mendaftarkan."
        }
        Write-Host "--------------------------------------------------------------------------"
    }

    Write-Host "==========================================================================" -ForegroundColor Cyan
    if ($allRegistered) {
        Write-Host "Status: Seluruh tugas otomasi terdaftar aktif di Windows Task Scheduler." -ForegroundColor Green
    } else {
        Write-Host "Status: Satu atau lebih tugas belum terdaftar di Windows Task Scheduler." -ForegroundColor Yellow
    }
    Write-Host "==========================================================================" -ForegroundColor Cyan
    exit 0
}
