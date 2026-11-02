# Downloads a static FFmpeg build (gyan.dev "release essentials", GPLv3) and copies
# ffmpeg.exe, ffprobe.exe and the licence into resources\ffmpeg.
#
#   powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes Invoke-WebRequest much faster

$Root = Split-Path $PSScriptRoot -Parent
$Dest = Join-Path $Root "resources\ffmpeg"
$Url  = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$Tmp  = Join-Path ([IO.Path]::GetTempPath()) ("mc-ffmpeg-" + [guid]::NewGuid())

New-Item -ItemType Directory -Force $Dest, $Tmp | Out-Null
try {
    $zip = Join-Path $Tmp "ffmpeg.zip"
    Write-Host "Downloading $Url ..."
    Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing

    Write-Host "Extracting ..."
    Expand-Archive -Path $zip -DestinationPath $Tmp -Force
    $bin = Get-ChildItem -Path $Tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $bin) { throw "ffmpeg.exe not found in the archive." }
    $buildDir = $bin.Directory.Parent.FullName

    Copy-Item (Join-Path $bin.DirectoryName "ffmpeg.exe")  $Dest -Force
    Copy-Item (Join-Path $bin.DirectoryName "ffprobe.exe") $Dest -Force
    $license = Get-ChildItem -Path $buildDir -Filter "LICENSE*" | Select-Object -First 1
    if ($license) { Copy-Item $license.FullName (Join-Path $Dest "LICENSE.txt") -Force }

    & (Join-Path $Dest "ffmpeg.exe") -hide_banner -version | Select-Object -First 1
    Write-Host "FFmpeg is ready in $Dest"
}
finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
