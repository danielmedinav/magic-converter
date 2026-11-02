"""Supported formats and the mapping between them."""

from __future__ import annotations

from enum import Enum


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

OUTPUT_LABELS = {"MP3": "MP3 (audio)", "GIF": "GIF"}

# Sensible default output per detected input format.
DEFAULT_IMAGE_TARGET = {
    "HEIC": "JPG", "AVIF": "JPG", "TIFF": "JPG",
    "JPEG": "PNG", "BMP": "PNG", "ICO": "PNG",
    "PNG": "WEBP", "GIF": "WEBP",
    "WEBP": "PNG",
}
DEFAULT_VIDEO_TARGET = {"MP4": "WEBM"}  # everything else -> MP4
FALLBACK_TARGET = {MediaKind.IMAGE: "PNG", MediaKind.VIDEO: "MP4"}

VIDEO_RESOLUTIONS =["Original", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
VIDEO_PRESETS = ["Low", "Medium", "High", "Original"]


def extension_for(fmt: str) -> str:
    return OUTPUT_EXTENSIONS[fmt.upper()]


def output_choices(kind: MediaKind) -> list[str]:
    """Output formats valid for a given input type."""
    if kind is MediaKind.IMAGE:
        from .image_converter import AVIF_AVAILABLE
        return [f for f in IMAGE_OUTPUT_FORMATS if f != "AVIF" or AVIF_AVAILABLE]
    return list(VIDEO_OUTPUT_FORMATS)


def default_target(kind: MediaKind, detected_format: str) -> str:
    table = DEFAULT_IMAGE_TARGET if kind is MediaKind.IMAGE else DEFAULT_VIDEO_TARGET
    target = table.get(detected_format.upper(), FALLBACK_TARGET[kind])
    return target if target in output_choices(kind) else FALLBACK_TARGET[kind]


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
