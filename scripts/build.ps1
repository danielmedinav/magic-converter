# One-shot build: icon + FFmpeg (if missing) -> PyInstaller -> Inno Setup installer.
#
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1            # full build
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipInstaller

param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

# Prefer the project's virtual environment if there is one.
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

if (-not (Test-Path "resources\icon.ico")) {
    & $Python scripts\make_icon.py
    if ($LASTEXITCODE) { throw "Icon generation failed." }
}
if (-not (Test-Path "resources\ffmpeg\ffmpeg.exe")) {
    & (Join-Path $PSScriptRoot "fetch_ffmpeg.ps1")
}

Write-Host "`n== PyInstaller ==" -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean MagicConverter.spec
if ($LASTEXITCODE) { throw "PyInstaller failed." }
Write-Host "App folder: $Root\dist\MagicConverter"

if ($SkipInstaller) { return }

Write-Host "`n== Inno Setup ==" -ForegroundColor Cyan
$Version = (& $Python -c "import magic_converter; print(magic_converter.__version__)").Trim()
$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { $Iscc = $cmd.Source }
}
if (-not $Iscc) { throw "ISCC.exe not found. Install Inno Setup 6.3+ (winget install JRSoftware.InnoSetup)." }

& $Iscc "/DMyAppVersion=$Version" "installer\MagicConverter.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed." }
Write-Host "`nInstaller: $Root\dist\installer\MagicConverter-Setup-$Version.exe" -ForegroundColor Green
