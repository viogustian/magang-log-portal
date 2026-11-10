; =====================================================================
; Inno Setup 7 Script — MagangLog Portal
; Pengembang Utama: Vio Gustian Nur Alamsyah
; Deskripsi: Installer klien terpadu untuk MagangLog Portal Desktop
; =====================================================================

#define MyAppName "MagangLog Portal"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Vio Gustian Nur Alamsyah"
#define MyAppURL "https://github.com/viogustian"
#define MyAppExeName "MagangLog.Desktop.exe"

[Setup]
; Identifikasi Unik Aplikasi (GUID)
AppId={{E72F198C-D8A3-4C10-859A-1F5BC68E0F21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Direktori & Izin Instalasi
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist\installer
OutputBaseFilename=MagangLogPortal_Setup_v{#MyAppVersion}

; Arsitektur Sistem 64-bit
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Mode Hak Akses (Mendukung instalasi per-user tanpa hak administrator)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Kompresi Maksimal
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone
Name: "startupicon"; Description: "Jalankan otomatis saat Windows startup (Opsional)"; GroupDescription: "Otomasi:"; Flags: unchecked

[Files]
; 1. Biner Aplikasi Desktop .NET 8 (Self-Contained WinForms)
Source: "publish\desktop-bundle\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2. Modul Backend Python & Konfigurasi Bawaan
Source: "src\*"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Direktori data lokal & log audit (Diberikan izin write untuk pengguna saat ini)
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\auth"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
; Shortcut di Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Shortcut di Desktop
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

; Shortcut di Startup Windows
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
; Opsi menjalankan aplikasi setelah instalasi selesai
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Pembersihan berkas temporer saat uninstall
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\data\*.log"

