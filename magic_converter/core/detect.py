"""Detect a file's real media type from its contents (magic bytes), not its extension."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .formats import VIDEO_INPUT_EXTS, MediaKind

HEAD_SIZE = 512

HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1", b"mif2"}
AVIF_BRANDS = {b"avif", b"avis"}
QUICKTIME_ATOMS = {b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"}
BMP_DIB_SIZES = {12, 40, 52, 56, 64, 108, 124}

# Pillow format names -> our display names
PIL_NAMES = {"JPEG": "JPEG", "MPO": "JPEG", "TIFF": "TIFF", "ICO": "ICO", "HEIF": "HEIC"}


@dataclass(frozen=True)
class Detected:
    kind: MediaKind
    format: str  # display name of the real format, e.g. "HEIC", "MOV"


def sniff(head: bytes) -> Detected | None:
    """Identify a format from the first bytes of a file. Pure function."""
    img = lambda f: Detected(MediaKind.IMAGE, f)  # noqa: E731
    vid = lambda f: Detected(MediaKind.VIDEO, f)  # noqa: E731

    if head.startswith(b"\xff\xd8\xff"):
        return img("JPEG")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return img("PNG")
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return img("GIF")
    if head[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        return img("TIFF")
    if head[:2] == b"BM" and len(head) >= 18 and struct.unpack("<I", head[14:18])[0] in BMP_DIB_SIZES:
        return img("BMP")
    if head[:4] == b"\x00\x00\x01\x00" and len(head) >= 6 and struct.unpack("<H", head[4:6])[0] > 0:
        return img("ICO")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return img("WEBP")
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return vid("AVI")

    if head[4:8] == b"ftyp":  # ISO base media: MP4, MOV, 3GP, HEIC, AVIF
        size = struct.unpack(">I", head[:4])[0]
        major = head[8:12]
        brands = {major} | {head[i:i + 4] for i in range(16, min(max(size, 16), len(head)) - 3, 4)}
        if brands & AVIF_BRANDS:
            return img("AVIF")
        if major in HEIF_BRANDS or (brands & HEIF_BRANDS and not brands & {b"isom", b"mp41", b"mp42"}):
            return img("HEIC")
        if major == b"qt  ":
            return vid("MOV")
        if major.startswith((b"3gp", b"3g2")):
            return vid("3GP")
        return vid("MP4")
    if head[4:8] in QUICKTIME_ATOMS:  # old QuickTime files without an ftyp box
        return vid("MOV")

    if head.startswith(b"\x1a\x45\xdf\xa3"):  # EBML: Matroska / WebM
        return vid("WEBM" if b"webm" in head[:64] else "MKV")
    if head.startswith(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11"):
        return vid("WMV")
    if head.startswith(b"FLV\x01"):
        return vid("FLV")
    if head.startswith(b"OggS") and b"theora" in head:
        return vid("OGV")
    if head[:4] in (b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"):
        return vid("MPEG")
    if len(head) >= 377 and head[0] == 0x47 and head[188] == 0x47 and head[376] == 0x47:
        return vid("MPEG-TS")
    if len(head) >= 389 and head[4] == 0x47 and head[196] == 0x47 and head[388] == 0x47:
        return vid("M2TS")
    return None


def detect(path: Path) -> Detected | None:
    """Return the media type of ``path``, or None if it isn't a supported image/video."""
    try:
        with open(path, "rb") as f:
            head = f.read(HEAD_SIZE)
    except OSError:
        return None
    if not head:
        return None

    found = sniff(head)
    if found:
        return found

    # Unknown signature: let Pillow try (it knows many more image formats).
    try:
        from PIL import Image
        from . import image_converter  # noqa: F401  (registers HEIC/AVIF openers)

        with Image.open(path) as im:
            return Detected(MediaKind.IMAGE, PIL_NAMES.get(im.format or "", im.format or "Image"))
    except Exception:
        pass

    # Last resort for video containers without a clear signature. Only for files that
    # look like video by name, so scanning a big folder doesn't probe every document.
    if path.suffix.lower() in VIDEO_INPUT_EXTS:
        from . import ffmpeg
        from .errors import ConversionError
        try:
            info = ffmpeg.probe(path)
        except ConversionError:
            return None
        if info.has_video:
            return Detected(MediaKind.VIDEO, path.suffix.lstrip(".").upper())
    return None
