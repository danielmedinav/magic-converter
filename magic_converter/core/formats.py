"""Supported formats and the mapping between them."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


IMAGE_INPUT_EXTS = {
    ".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".tif", ".tiff",
    ".gif", ".ico", ".heic", ".heif", ".avif",
}

VIDEO_INPUT_EXTS = {
    ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".flv",
    ".mpg", ".mpeg", ".3gp", ".ts", ".mts", ".m2ts", ".ogv",
}

IMAGE_OUTPUT_FORMATS = ["PNG", "JPG", "WEBP", "AVIF", "BMP", "TIFF", "GIF", "ICO"]
VIDEO_OUTPUT_FORMATS = ["MP4", "MKV", "MOV", "AVI", "WEBM", "GIF", "MP3"]

# Formats where the quality slider has no effect (lossless / palette based).
LOSSLESS_IMAGE_FORMATS = {"PNG", "BMP", "TIFF", "GIF", "ICO"}

OUTPUT_EXTENSIONS = {
    "PNG": ".png", "JPG": ".jpg", "WEBP": ".webp", "AVIF": ".avif",
    "BMP": ".bmp", "TIFF": ".tiff", "GIF": ".gif", "ICO": ".ico",
    "MP4": ".mp4", "MKV": ".mkv", "MOV": ".mov", "AVI": ".avi",
    "WEBM": ".webm", "MP3": ".mp3",
}

VIDEO_RESOLUTIONS = ["Original", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
VIDEO_PRESETS = ["Low", "Medium", "High", "Original"]


def kind_of(path: Path) -> MediaKind | None:
    ext = path.suffix.lower()
    if ext in IMAGE_INPUT_EXTS:
        return MediaKind.IMAGE
    if ext in VIDEO_INPUT_EXTS:
        return MediaKind.VIDEO
    return None


def extension_for(fmt: str) -> str:
    return OUTPUT_EXTENSIONS[fmt.upper()]


def dialog_filter() -> str:
    """Filter string for QFileDialog."""
    images = " ".join(f"*{e}" for e in sorted(IMAGE_INPUT_EXTS))
    videos = " ".join(f"*{e}" for e in sorted(VIDEO_INPUT_EXTS))
    return (
        f"Media files ({images} {videos});;"
        f"Images ({images});;"
        f"Videos ({videos});;"
        "All files (*)"
    )
