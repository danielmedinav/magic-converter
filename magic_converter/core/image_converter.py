"""Image conversion with Pillow (+ HEIC and AVIF plugins)."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from .errors import ConversionCancelled, ConversionError
from .models import ImageOptions, ResizeOptions

# --- Optional format plugins -------------------------------------------------

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:  # pragma: no cover
    HEIF_AVAILABLE = False

Image.init()
if ".avif" not in Image.registered_extensions():
    # Pillow < 11.3 has no native AVIF support; fall back to the plugin.
    try:
        import pillow_avif  # noqa: F401
    except ImportError:  # pragma: no cover
        pass
Image.init()
AVIF_AVAILABLE = ".avif" in Image.registered_extensions()

# Guard against decompression-bomb false positives on huge (but legit) photos.
Image.MAX_IMAGE_PIXELS = 400_000_000

PIL_FORMAT = {
    "PNG": "PNG", "JPG": "JPEG", "WEBP": "WEBP", "AVIF": "AVIF",
    "BMP": "BMP", "TIFF": "TIFF", "GIF": "GIF", "ICO": "ICO",
}
ANIMATED_OUTPUTS = {"GIF", "WEBP"}
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

ProgressFn = Callable[[float], None]


def convert_image(
    src: Path,
    dst: Path,
    opts: ImageOptions,
    cancel: threading.Event,
    progress: ProgressFn,
) -> None:
    fmt = opts.format.upper()
    if fmt == "AVIF" and not AVIF_AVAILABLE:
        raise ConversionError("AVIF output is not available in this build.")

    tmp = dst.with_name(f".{dst.stem}.mcpart{dst.suffix}")
    try:
        with _open(src) as im:
            frames = getattr(im, "n_frames", 1)
            if frames > 1 and fmt in ANIMATED_OUTPUTS:
                _save_animated(im, tmp, fmt, opts, cancel, progress)
            else:
                progress(0.2)
                frame = _prepare(im, opts.resize)
                progress(0.6)
                _check(cancel)
                _save_still(frame, im.info, tmp, fmt, opts)
        _check(cancel)
        os.replace(tmp, dst)
        progress(1.0)
    except (ConversionError, ConversionCancelled):
        raise
    except MemoryError:
        raise ConversionError("The image is too large to convert.")
    except PermissionError as exc:
        raise ConversionError("Can't write to the output folder (permission denied).", str(exc))
    except (OSError, ValueError, SyntaxError) as exc:
        # Pillow raises OSError for truncated/broken files and encoder issues.
        raise ConversionError("The image could not be converted. It may be corrupted.", str(exc))
    finally:
        tmp.unlink(missing_ok=True)


# --- Helpers -----------------------------------------------------------------

def _check(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise ConversionCancelled()


def _open(src: Path) -> Image.Image:
    try:
        im = Image.open(src)
        im.load()
        return im
    except UnidentifiedImageError as exc:
        hint = "" if HEIF_AVAILABLE or src.suffix.lower() not in (".heic", ".heif") else " (HEIC support missing)"
        raise ConversionError(f"Not a valid image, or the format is unsupported{hint}.", str(exc))
    except Image.DecompressionBombError as exc:
        raise ConversionError("The image is too large to open safely.", str(exc))
    except FileNotFoundError as exc:
        raise ConversionError("The file no longer exists.", str(exc))
    except OSError as exc:
        raise ConversionError("The image file is corrupted or incomplete.", str(exc))


def _target_size(w: int, h: int, r: ResizeOptions) -> tuple[int, int]:
    if r.mode == "percent":
        f = r.percent / 100
        return max(1, round(w * f)), max(1, round(h * f))
    if r.mode == "size":
        tw, th = r.width, r.height
        if tw <= 0 and th <= 0:
            return w, h
        if r.keep_aspect:
            if tw <= 0:
                tw = round(w * th / h)
            elif th <= 0:
                th = round(h * tw / w)
            else:  # fit inside the box
                scale = min(tw / w, th / h)
                tw, th = round(w * scale), round(h * scale)
        else:
            tw = tw if tw > 0 else w
            th = th if th > 0 else h
        return max(1, tw), max(1, th)
    return w, h


def _normalize_mode(im: Image.Image) -> Image.Image:
    """Bring exotic modes (CMYK, I;16, P, ...) to RGB/RGBA."""
    if im.mode in ("RGB", "RGBA"):
        return im
    has_alpha = im.mode in ("LA", "PA", "RGBa", "La") or (
        im.mode == "P" and "transparency" in im.info
    )
    if im.mode.startswith("I;16") or im.mode == "I":
        im = im.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    elif im.mode == "F":
        im = im.convert("L")
    return im.convert("RGBA" if has_alpha else "RGB")


def _prepare(im: Image.Image, resize: ResizeOptions) -> Image.Image:
    frame = ImageOps.exif_transpose(im) or im
    frame = _normalize_mode(frame)
    size = _target_size(frame.width, frame.height, resize)
    if size != frame.size:
        frame = frame.resize(size, Image.Resampling.LANCZOS)
    return frame


def _flatten(im: Image.Image, color=(255, 255, 255)) -> Image.Image:
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, color)
        bg.paste(im, mask=im.getchannel("A"))
        return bg
    return im.convert("RGB")


def _square(im: Image.Image) -> Image.Image:
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im.convert("RGBA"), ((side - im.width) // 2, (side - im.height) // 2))
    return canvas


def _save_still(im: Image.Image, info: dict, out: Path, fmt: str, opts: ImageOptions) -> None:
    icc = info.get("icc_profile")
    q = opts.quality
    kw: dict = {}

    if fmt == "JPG":
        im = _flatten(im)
        kw = dict(quality=q, optimize=True, progressive=True)
    elif fmt == "PNG":
        kw = dict(compress_level=6)
    elif fmt == "WEBP":
        kw = dict(quality=q, method=4, lossless=q >= 100)
    elif fmt == "AVIF":
        kw = dict(quality=q)
    elif fmt == "BMP":
        im = _flatten(im)
    elif fmt == "TIFF":
        kw = dict(compression="tiff_lzw")
    elif fmt == "GIF":
        kw = dict(optimize=True)
    elif fmt == "ICO":
        im = _square(im)
        sizes = [s for s in ICO_SIZES if s <= im.width] or [im.width]
        kw = dict(sizes=[(s, s) for s in sizes])

    if icc and fmt in ("JPG", "PNG", "WEBP", "TIFF", "AVIF"):
        kw["icc_profile"] = icc
    im.save(out, format=PIL_FORMAT[fmt], **kw)


def _save_animated(
    im: Image.Image,
    out: Path,
    fmt: str,
    opts: ImageOptions,
    cancel: threading.Event,
    progress: ProgressFn,
) -> None:
    total = im.n_frames
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i, frame in enumerate(ImageSequence.Iterator(im)):
        _check(cancel)
        durations.append(int(frame.info.get("duration", 100)) or 100)
        f = frame.convert("RGBA")
        size = _target_size(f.width, f.height, opts.resize)
        if size != f.size:
            f = f.resize(size, Image.Resampling.LANCZOS)
        frames.append(f)
        progress(0.8 * (i + 1) / total)

    kw: dict = dict(save_all=True, append_images=frames[1:], duration=durations,
                    loop=im.info.get("loop", 0))
    if fmt == "GIF":
        kw.update(disposal=2, optimize=False)
    else:
        kw.update(quality=opts.quality, method=4, lossless=opts.quality >= 100)
    frames[0].save(out, format=PIL_FORMAT[fmt], **kw)
