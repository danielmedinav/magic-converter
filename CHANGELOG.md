# Changelog

All notable changes to Magic Converter. Versions follow MAJOR.MINOR.PATCH:
bug fixes bump PATCH, new features bump MINOR, big or breaking changes bump MAJOR.

Write notes for the next release under **Unreleased**; `scripts\release.ps1`
moves them under the new version number automatically.

## [Unreleased]

- Install any published version: click the version label in the header →
  **Install another version…**, choose from the list (with each version's notes) and
  install it, newer or older. Settings are kept.
- The version label now opens a small menu: **Check for updates** / **Install another version…**.
- The installer clears the previous app files first, so nothing from another version is left behind.

## [1.1.0] - 2026-11-01

- Each file in the queue now has its own output-format dropdown, so different files
  can be converted to different formats in one batch.
- The dropdown only offers formats that fit the file's real type (images or
  video/audio), detected from the file contents rather than the extension.
- Sensible default output per type, e.g. HEIC → JPG, MOV → MP4, PNG → WEBP.
- Each card shows an "Image" or "Video" label and a live preview of the output filename.
- New "Apply to all images" / "Apply to all videos" actions above the queue.
- Quality and resize stay global (Image / Video tabs in the bottom panel). The
  per-file settings dialog was removed, because format is now chosen on the card.
- README: new Installation section for end users and developers.

## [1.0.0] - 2026-11-01

- First release.
- Convert images: JPG, PNG, WEBP, AVIF, BMP, TIFF, GIF, ICO (HEIC/HEIF input).
- Convert videos: MP4, MKV, MOV, AVI, WEBM, animated GIF, and MP3 audio extraction.
- Drag and drop files or folders, batch queue, per-file settings, cancel at any time.
- Light and dark themes that follow Windows.
- Automatic update checks via GitHub Releases.
