"""Persistent user settings stored as JSON in %APPDATA%\\MagicConverter."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, get_type_hints

from .core.formats import (
    IMAGE_OUTPUT_FORMATS,
    VIDEO_OUTPUT_FORMATS,
    VIDEO_PRESETS,
    VIDEO_RESOLUTIONS,
)
from .core.models import ImageOptions, ResizeOptions, VideoOptions
from .paths import user_data_dir

log = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"


@dataclass
class AppSettings:
    image: ImageOptions = field(default_factory=ImageOptions)
    video: VideoOptions = field(default_factory=VideoOptions)
    output_mode: str = "source"     # "source" | "custom"
    output_dir: str = ""
    theme: str = "system"           # "system" | "light" | "dark"
    active_tab: str = "image"       # "image" | "video"
    last_browse_dir: str = ""
    window_geometry: str = ""       # base64 QByteArray from saveGeometry()


def _from_dict(cls: type, data: Any) -> Any:
    """Build a dataclass from a dict, ignoring unknown or mistyped keys."""
    obj = cls()
    if not isinstance(data, dict):
        return obj
    hints = get_type_hints(cls)
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        current = getattr(obj, f.name)
        if is_dataclass(current):
            setattr(obj, f.name, _from_dict(hints[f.name], value))
        elif type(value) is type(current):
            setattr(obj, f.name, value)
    return obj


def _sanitize(s: AppSettings) -> AppSettings:
    if s.image.format not in IMAGE_OUTPUT_FORMATS:
        s.image.format = ImageOptions.format
    s.image.quality = max(1, min(100, s.image.quality))
    r = s.image.resize
    if r.mode not in ("none", "percent", "size"):
        r.mode = ResizeOptions.mode
    r.percent = max(1, min(1000, r.percent))
    r.width = max(0, min(20000, r.width))
    r.height = max(0, min(20000, r.height))
    if s.video.format not in VIDEO_OUTPUT_FORMATS:
        s.video.format = VideoOptions.format
    if s.video.resolution not in VIDEO_RESOLUTIONS:
        s.video.resolution = VideoOptions.resolution
    if s.video.preset not in VIDEO_PRESETS:
        s.video.preset = VideoOptions.preset
    if s.output_mode not in ("source", "custom"):
        s.output_mode = "source"
    if s.theme not in ("system", "light", "dark"):
        s.theme = "system"
    if s.active_tab not in ("image", "video"):
        s.active_tab = "image"
    return s


def load_settings() -> AppSettings:
    path = user_data_dir() / SETTINGS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppSettings()
    except (OSError, ValueError) as exc:
        log.warning("Could not read settings (%s); using defaults.", exc)
        return AppSettings()
    return _sanitize(_from_dict(AppSettings, data))


def save_settings(settings: AppSettings) -> None:
    path = user_data_dir() / SETTINGS_FILE
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("Could not save settings: %s", exc)
