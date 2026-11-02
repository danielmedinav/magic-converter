# Cut a new release in one command.
#
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -Version 1.1.0
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -Version 1.1.0 -Publish
#
# Steps: checks -> bump __version__ -> move CHANGELOG "Unreleased" notes under the
# new version -> build app + installer -> git commit + tag. With -Publish it also
# pushes to GitHub and creates the GitHub Release (needs the GitHub CLI "gh").

param(
    [Parameter(Mandatory = $true)][string]$Version,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Fail($msg) { Write-Host "`n$msg" -ForegroundColor Red; exit 1 }

# --- Checks ------------------------------------------------------------------
if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "Version must look like 1.2.0 (MAJOR.MINOR.PATCH)." }
if (-not (Test-Path ".git")) { Fail "This folder is not a Git repository." }
if (git status --porcelain) { Fail "You have uncommitted changes. Commit them first (git add -A; git commit -m '...')." }
if (git tag --list "v$Version") { Fail "Tag v$Version already exists." }

$InitFile = "magic_converter\__init__.py"
$init = [IO.File]::ReadAllText("$Root\$InitFile")
$current = [regex]::Match($init, '__version__\s*=\s*"([^"]+)"').Groups[1].Value
if ([version]$Version -le [version]$current) { Fail "New version $Version must be higher than the current $current." }

$ChangelogFile = "CHANGELOG.md"
$changelog = [IO.File]::ReadAllText("$Root\$ChangelogFile")
$m = [regex]::Match($changelog, '(?s)## \[Unreleased\][^\n]*\n(.*?)(?=\r?\n## \[|\z)')
if (-not $m.Success) { Fail "CHANGELOG.md has no '## [Unreleased]' section." }
$notes = $m.Groups[1].Value.Trim()
if (-not $notes) { Fail "Write what changed under '## [Unreleased]' in CHANGELOG.md, commit it, then run again." }

if ($Publish -and -not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Fail "-Publish needs the GitHub CLI: winget install GitHub.cli, then gh auth login."
}

Write-Host "Releasing $current -> $Version" -ForegroundColor Cyan

# --- Bump version + changelog --------------------------------------------------
$date = Get-Date -Format "yyyy-MM-dd"
$section = "## [Unreleased]`n`n## [$Version] - $date`n`n$notes`n"
$changelog = $changelog.Substring(0, $m.Index) + $section + $changelog.Substring($m.Index + $m.Length)
[IO.File]::WriteAllText("$Root\$ChangelogFile", $changelog, $Utf8)
$init = [regex]::Replace($init, '__version__\s*=\s*"[^"]+"', "__version__ = `"$Version`"")
[IO.File]::WriteAllText("$Root\$InitFile", $init, $Utf8)

# --- Build ---------------------------------------------------------------------
try {
    & (Join-Path $PSScriptRoot "build.ps1")
} catch {
    git checkout -- $InitFile $ChangelogFile
    Fail "Build failed, version bump undone: $_"
}
$Installer = "dist\installer\MagicConverter-Setup-$Version.exe"
if (-not (Test-Path $Installer)) {
    git checkout -- $InitFile $ChangelogFile
    Fail "Installer not found at $Installer, version bump undone."
}
New-Item -ItemType Directory -Force "dist" | Out-Null
$NotesFile = "dist\release-notes-$Version.md"
[IO.File]::WriteAllText("$Root\$NotesFile", $notes + "`n", $Utf8)

# --- Commit + tag ----------------------------------------------------------------
git add -A
git commit -m "Release $Version"
git tag -a "v$Version" -m "Magic Converter $Version"
Write-Host "`nCommitted and tagged v$Version." -ForegroundColor Green

# --- Publish -------------------------------------------------------------------
if ($Publish) {
    git push
    git push origin "v$Version"
    gh release create "v$Version" $Installer --title "Magic Converter $Version" --notes-file $NotesFile
    Write-Host "`nPublished. Installed copies will offer the update on their next start." -ForegroundColor Green
} else {
    Write-Host @"

Next steps to publish:
  1. git push; git push origin v$Version
  2. On GitHub: Releases -> Draft a new release -> choose tag v$Version
  3. Title: Magic Converter $Version   Notes: paste $NotesFile
  4. Attach $Installer and click Publish.
(Or re-run next time with -Publish to do all of this automatically.)
"@
}
