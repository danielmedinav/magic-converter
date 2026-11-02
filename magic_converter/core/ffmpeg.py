"""Locating and invoking the bundled ffmpeg / ffprobe binaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..paths import resource
from .errors import ConversionError

# Prevent a console window from flashing up for every subprocess on Windows.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _find(name: str) -> Path | None:
    exe = f"{name}.exe" if sys.platform == "win32" else name
    bundled = resource("ffmpeg", exe)
    if bundled.is_file():
        return bundled
    found = shutil.which(name)
    return Path(found) if found else None


@lru_cache(maxsize=None)
def ffmpeg_path() -> Path | None:
    return _find("ffmpeg")


@lru_cache(maxsize=None)
def ffprobe_path() -> Path | None:
    return _find("ffprobe")


def require(path: Path | None, name: str) -> Path:
    if path is None:
        raise ConversionError(
            f"{name} was not found. Reinstall Magic Converter to restore it.",
        )
    return path


def popen(args: list[str], **kw) -> subprocess.Popen:
    return subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
        **kw,
    )


@dataclass
class ProbeInfo:
    duration: float | None
    has_video: bool
    has_audio: bool
    video_codec: str = ""
    audio_codecs: tuple[str, ...] = ()
    width: int = 0
    height: int = 0  # display size (rotation already applied)


def probe(path: Path) -> ProbeInfo:
    exe = require(ffprobe_path(), "ffprobe")
    try:
        proc = popen([
            str(exe), "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ])
        out, err = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise ConversionError("Timed out while reading the video.")
    if proc.returncode != 0:
        raise ConversionError(
            "Could not read this video. It may be corrupted or in an unsupported format.",
            err.strip(),
        )
    try:
        data = json.loads(out or "{}")
    except ValueError as exc:
        raise ConversionError("Could not read this video's information.", str(exc))

    streams = data.get("streams", [])
    # Ignore cover-art "video" streams (attached pictures).
    videos = [s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in streams if s.get("codec_type") == "audio"]

    duration = _float(data.get("format", {}).get("duration"))
    if duration is None and videos:
        duration = _float(videos[0].get("duration"))

    info = ProbeInfo(duration=duration, has_video=bool(videos), has_audio=bool(audios),
                     audio_codecs=tuple(a.get("codec_name", "") for a in audios))
    if videos:
        v = videos[0]
        info.video_codec = v.get("codec_name", "")
        w, h = int(v.get("width") or 0), int(v.get("height") or 0)
        if abs(_rotation(v)) in (90, 270):
            w, h = h, w
        info.width, info.height = w, h
    return info


def _float(value) -> float | None:
    try:
        f = float(value)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _rotation(stream: dict) -> int:
    rot = stream.get("tags", {}).get("rotate")
    if rot is None:
        for sd in stream.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = sd["rotation"]
                break
    try:
        return int(float(rot or 0)) % 360
    except (TypeError, ValueError):
        return 0
