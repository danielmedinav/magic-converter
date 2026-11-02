"""Video conversion and audio extraction with ffmpeg."""

from __future__ import annotations

import collections
import os
import threading
from pathlib import Path
from typing import Callable

from . import ffmpeg
from .errors import ConversionCancelled, ConversionError
from .models import VideoOptions

ProgressFn = Callable[[float], None]  # 0..1, or -1 for "indeterminate"

# Quality presets. CRF = constant quality (lower is better).
X264_CRF = {"Low": 28, "Medium": 23, "High": 19, "Original": 17}
VP9_CRF = {"Low": 40, "Medium": 33, "High": 28, "Original": 24}
MPEG4_Q = {"Low": 9, "Medium": 5, "High": 3, "Original": 2}
AUDIO_BITRATE = {"Low": "96k", "Medium": "128k", "High": "192k", "Original": "256k"}
MP3_BITRATE = {"Low": "128k", "Medium": "192k", "High": "256k", "Original": "320k"}
GIF_FPS = {"Low": 10, "Medium": 12, "High": 15, "Original": 20}
GIF_MAX_WIDTH = {"Low": 360, "Medium": 480, "High": 640, "Original": 960}

MUXER = {"MP4": "mp4", "MKV": "matroska", "MOV": "mov", "AVI": "avi",
         "WEBM": "webm", "GIF": "gif", "MP3": "mp3"}

# Codecs each container can hold without re-encoding (used by the "Original" preset).
COPY_COMPAT = {
    "MP4": ({"h264", "hevc", "av1", "mpeg4"}, {"aac", "mp3", "ac3", "eac3", "opus", "alac", "flac"}),
    "MOV": ({"h264", "hevc", "mpeg4", "prores", "mjpeg"}, {"aac", "mp3", "ac3", "alac", "pcm_s16le"}),
    "MKV": ({"h264", "hevc", "vp8", "vp9", "av1", "mpeg4", "mpeg2video"},
            {"aac", "mp3", "ac3", "eac3", "opus", "vorbis", "flac", "dts", "truehd", "pcm_s16le"}),
    "WEBM": ({"vp8", "vp9", "av1"}, {"opus", "vorbis"}),
    "AVI": ({"mpeg4", "msmpeg4v3", "mjpeg"}, {"mp3", "ac3", "pcm_s16le"}),
}


def convert_video(
    src: Path,
    dst: Path,
    opts: VideoOptions,
    cancel: threading.Event,
    progress: ProgressFn,
) -> None:
    exe = ffmpeg.require(ffmpeg.ffmpeg_path(), "FFmpeg")
    info = ffmpeg.probe(src)
    fmt = opts.format.upper()

    if fmt == "MP3":
        if not info.has_audio:
            raise ConversionError("This video has no audio track to extract.")
    elif not info.has_video:
        raise ConversionError("No video stream found in this file.")

    tmp = dst.with_name(f".{dst.stem}.mcpart{dst.suffix}")
    args = [str(exe), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
            "-i", str(src), *build_args(fmt, opts, info),
            "-progress", "pipe:1", "-nostats", "-f", MUXER[fmt], str(tmp)]

    # GIF palette generation buffers the whole clip, so progress can't be tracked.
    indeterminate = fmt == "GIF" or not info.duration
    progress(-1 if indeterminate else 0.0)

    try:
        _run(args, info.duration if not indeterminate else None, cancel, progress)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)
    progress(1.0)


# --- Command building --------------------------------------------------------

def build_args(fmt: str, opts: VideoOptions, info: ffmpeg.ProbeInfo) -> list[str]:
    preset = opts.preset if opts.preset in X264_CRF else "Medium"

    if fmt == "MP3":
        return ["-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-b:a", MP3_BITRATE[preset]]

    maps = ["-map", "0:v:0", "-map", "0:a?", "-sn", "-dn"]

    if fmt == "GIF":
        return ["-map", "0:v:0", "-an", "-sn", "-dn", "-vf", _gif_filter(opts, info), "-loop", "0"]

    if preset == "Original" and opts.resolution == "Original" and _can_copy(fmt, info):
        return [*maps, "-c", "copy", *(_faststart(fmt))]

    vf = _scale_filter(opts.resolution, info, even=True)
    vf_args = ["-vf", vf] if vf else []
    abr = AUDIO_BITRATE[preset]

    if fmt in ("MP4", "MOV", "MKV"):
        return [*maps, *vf_args, "-c:v", "libx264", "-preset", "medium",
                "-crf", str(X264_CRF[preset]), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", abr, *(_faststart(fmt))]
    if fmt == "WEBM":
        return [*maps, *vf_args, "-c:v", "libvpx-vp9", "-crf", str(VP9_CRF[preset]),
                "-b:v", "0", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
                "-pix_fmt", "yuv420p", "-c:a", "libopus", "-b:a", abr]
    if fmt == "AVI":
        return [*maps, *vf_args, "-c:v", "mpeg4", "-q:v", str(MPEG4_Q[preset]),
                "-pix_fmt", "yuv420p", "-c:a", "libmp3lame", "-b:a", abr]
    raise ConversionError(f"Unsupported output format: {fmt}")


def _faststart(fmt: str) -> list[str]:
    return ["-movflags", "+faststart"] if fmt in ("MP4", "MOV") else []


def _can_copy(fmt: str, info: ffmpeg.ProbeInfo) -> bool:
    compat = COPY_COMPAT.get(fmt)
    if not compat:
        return False
    vcodecs, acodecs = compat
    return info.video_codec in vcodecs and all(a in acodecs for a in info.audio_codecs)


def _target_short_side(resolution: str) -> int | None:
    if resolution.endswith("p") and resolution[:-1].isdigit():
        return int(resolution[:-1])
    return None


def _scale_filter(resolution: str, info: ffmpeg.ProbeInfo, even: bool) -> str:
    """Downscale so the short side matches the preset; never upscale."""
    w, h = info.width, info.height
    target = _target_short_side(resolution)
    if target and w and h and target < min(w, h):
        return f"scale=-2:{target}" if w >= h else f"scale={target}:-2"
    if even and (w % 2 or h % 2):
        # H.264 / VP9 with yuv420p require even dimensions.
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    return ""


def _gif_filter(opts: VideoOptions, info: ffmpeg.ProbeInfo) -> str:
    preset = opts.preset if opts.preset in GIF_FPS else "Medium"
    target = _target_short_side(opts.resolution)
    if target:
        scale = f"scale=-2:'min({target},ih)'" if info.width >= info.height \
            else f"scale='min({target},iw)':-2"
    else:
        scale = f"scale='min({GIF_MAX_WIDTH[preset]},iw)':-2"
    return (f"fps={GIF_FPS[preset]},{scale}:flags=lanczos,split[a][b];"
            f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5")


# --- Process handling --------------------------------------------------------

def _run(args: list[str], duration: float | None,
         cancel: threading.Event, progress: ProgressFn) -> None:
    try:
        proc = ffmpeg.popen(args)
    except OSError as exc:
        raise ConversionError("Could not start FFmpeg.", str(exc))

    stderr_tail: collections.deque[str] = collections.deque(maxlen=30)

    def drain_stderr() -> None:
        for line in proc.stderr:
            stderr_tail.append(line.rstrip())

    def watch_cancel() -> None:
        while proc.poll() is None:
            if cancel.wait(0.15):
                proc.kill()
                return

    threading.Thread(target=drain_stderr, daemon=True).start()
    threading.Thread(target=watch_cancel, daemon=True).start()

    for line in proc.stdout:
        key, _, value = line.strip().partition("=")
        if duration and key in ("out_time_us", "out_time_ms") and value.isdigit():
            # Both keys are in microseconds (out_time_ms is misnamed in ffmpeg).
            progress(min(0.99, int(value) / 1_000_000 / duration))

    proc.wait()
    if cancel.is_set():
        raise ConversionCancelled()
    if proc.returncode != 0:
        detail = "\n".join(stderr_tail)
        raise ConversionError(_friendly(detail), detail)


def _friendly(stderr: str) -> str:
    s = stderr.lower()
    if "permission denied" in s:
        return "Can't write to the output folder (permission denied)."
    if "no space left" in s:
        return "Not enough disk space."
    if "moov atom not found" in s or "invalid data found" in s:
        return "The video is corrupted or incomplete."
    if "unknown encoder" in s or "encoder not found" in s:
        return "This FFmpeg build is missing a required encoder."
    if "no such file" in s:
        return "The file could not be found."
    return "FFmpeg could not convert this file."
