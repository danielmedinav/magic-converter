# ✦ Magic Converter

A modern, minimalist desktop app for converting images and videos on Windows.
Drop in files or whole folders, pick a format, and hit **Convert**.

- **Images:** JPG, PNG, WEBP, AVIF, BMP, TIFF, GIF, ICO (input also HEIC/HEIF)
- **Videos:** MP4, MKV, MOV, AVI, WEBM, animated GIF, and MP3 audio extraction
- Batch queue with per-file and overall progress, cancel at any time
- Quality slider and resize for images. Resolution and Low/Medium/High/Original presets for video
- Per-file settings override (the sliders button on each queue row)
- Dark and light themes that follow Windows, with a manual toggle
- Remembers your last settings
- FFmpeg is bundled, so users don't need to install anything

Built with **Python 3.11+**, **PySide6 (Qt 6)**, **Pillow** (+ pillow-heif) and **FFmpeg**.

---

## Run in development

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Get FFmpeg (downloads ffmpeg.exe + ffprobe.exe into resources\ffmpeg)
powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1

# 4. Generate the app icon
python scripts\make_icon.py

# 5. Run
python main.py
```

> If `resources\ffmpeg` is empty, the app falls back to an `ffmpeg` on your `PATH`.

## Build the Windows installer

Prerequisites: the dev setup above, plus **[Inno Setup 6.3+](https://jrsoftware.org/isdl.php)**
(`winget install JRSoftware.InnoSetup`).

**Easiest: one command does everything**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

**Or step by step**

```powershell
# 1. Build the app folder -> dist\MagicConverter\MagicConverter.exe
python -m PyInstaller --noconfirm --clean MagicConverter.spec

# 2. Build the installer -> dist\installer\MagicConverter-Setup-1.0.0.exe
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.0.0 installer\MagicConverter.iss
```

(If Inno Setup was installed with winget, ISCC is in `%LOCALAPPDATA%\Programs\Inno Setup 6\`.)

The installer:
- installs per-user, with no admin prompt (all-users is optional)
- adds a Start Menu shortcut, an optional desktop shortcut and an uninstaller in *Settings → Apps*

## Versions, releases and updates

Versions follow **MAJOR.MINOR.PATCH**:

| Change | Example |
|---|---|
| Bug fix only | 1.0.0 → 1.0.1 |
| New feature | 1.0.1 → 1.1.0 |
| Big or breaking change | 1.4.2 → 2.0.0 |

The version lives in one place: `__version__` in `magic_converter/__init__.py`.

### One-time setup for updates

1. Create a GitHub repository, for example `yourname/magic-converter`. Releases must be
   public for the app to see them, so a public repo is simplest.
2. Set `UPDATE_REPO = "yourname/magic-converter"` in `magic_converter/__init__.py` and commit.
3. Connect the local repo and push:
   ```powershell
   git remote add origin https://github.com/yourname/magic-converter.git
   git push -u origin main --tags
   ```
4. Optional, for one-command publishing: `winget install GitHub.cli`, then `gh auth login`.

### Making a release

```powershell
# 1. Work on the code, test with: python main.py
# 2. Describe the changes under "## [Unreleased]" in CHANGELOG.md
# 3. Commit your work
git add -A
git commit -m "Add batch rename"

# 4. Release: bumps the version, builds the installer, commits and tags
powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -Version 1.1.0 -Publish
```

Without `-Publish`, the script prints the steps for uploading the installer to GitHub by hand.

### How users get the update

- On start-up, the app quietly checks the latest GitHub Release. Users can also click the
  version label in the header to check manually.
- If a newer version exists, a banner offers **Update**. The app downloads the installer,
  checks its size and SHA-256, closes, upgrades silently and reopens. Settings are kept.
- Users without the app just download the latest `Setup.exe` from the Releases page.
  Installing over an older version upgrades it in place.

> Never change the `AppId` in `installer\MagicConverter.iss`. Windows uses it to recognise
> new versions as upgrades of the same app.

### Going back to an older version

Each release is a Git tag. `git checkout v1.0.0` shows the exact code of 1.0.0, and
`git checkout main` returns to the latest. To fix a bad release, ship a new version with
the fix, such as 1.1.1, rather than reusing a number.

## Project structure

```
main.py                         entry point
magic_converter/
  app.py                        QApplication bootstrap, fonts, theme
  paths.py                      resource paths (dev + frozen), %APPDATA% dir
  settings.py                   persistent settings (JSON)
  updater.py                    GitHub Releases update check, download, install
  core/                         conversion logic, no UI code
    formats.py                  supported formats
    models.py                   Job / options dataclasses
    image_converter.py          Pillow pipeline
    ffmpeg.py                   ffmpeg/ffprobe discovery + probing
    video_converter.py          ffmpeg command builder + progress
    worker.py                   background QThread queue runner
    errors.py                   user-facing exceptions
  ui/                           PySide6 widgets
    theme.py                    palettes, stylesheet, system theme tracking
    icons.py                    inline SVG icon set
    widgets.py                  animated button, progress bar, segmented control
    drop_zone.py, queue_list.py, settings_panel.py, update_banner.py, main_window.py
resources/                      icon + bundled ffmpeg
scripts/                        make_icon.py, fetch_ffmpeg.ps1, build.ps1, release.ps1
CHANGELOG.md                    release notes, one section per version
installer/MagicConverter.iss    Inno Setup script
MagicConverter.spec             PyInstaller spec
```

## How conversions work

| Output | Encoder | Notes |
|---|---|---|
| MP4 / MOV / MKV | H.264 + AAC | CRF 28 / 23 / 19 / 17 for Low / Medium / High / Original |
| WEBM | VP9 + Opus | constant-quality mode |
| AVI | MPEG-4 Part 2 + MP3 | |
| GIF | FFmpeg two-pass palette | 10–20 fps, width capped by preset |
| MP3 | LAME | 128 / 192 / 256 / 320 kbps |

- **Original preset:** if the source codecs fit the target container, the streams are copied without re-encoding, which is near-instant and lossless.
- **Resolution presets:** these only ever downscale. They apply to the short side, so portrait videos work too.
- **Safe output files:** each file is written to a temporary `.mcpart` file and renamed when complete. A cancel or error never leaves half-written output.
- **No overwriting:** if the output name already exists, the new file becomes `name (1).ext`.

## Settings and logs

`%APPDATA%\MagicConverter\settings.json` and `app.log`. Delete the folder to reset.

## Licensing note

The bundled FFmpeg build (gyan.dev "essentials") is licensed under the **GPLv3**,
and its licence is shipped in `resources\ffmpeg\LICENSE.txt`. If you distribute the
installer publicly, comply with the GPL. That means offering the FFmpeg source,
for example by linking to https://www.gyan.dev/ffmpeg/builds/ and https://ffmpeg.org.
Alternatively, swap in an LGPL build.
