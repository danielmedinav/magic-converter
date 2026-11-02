"""Path helpers that work both from source and inside a PyInstaller bundle."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_ID


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """Root folder that contains the ``resources`` directory."""
    if is_frozen():
        # PyInstaller >= 6 puts data files in ``_internal`` (exposed as _MEIPASS).
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def resource(*parts: str) -> Path:
    return base_dir().joinpath("resources", *parts)


def user_data_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(root) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path
