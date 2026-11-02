"""Work out output filenames before converting, so the UI can preview them."""

from __future__ import annotations

import os
from pathlib import Path

from .formats import extension_for


def _key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def free_path(folder: Path, stem: str, ext: str, taken: set[str] | None = None) -> Path:
    """First of ``stem.ext``, ``stem (1).ext``, ... that isn't on disk or in ``taken``."""
    taken = taken if taken is not None else set()
    n = 0
    while True:
        candidate = folder / (f"{stem}{ext}" if n == 0 else f"{stem} ({n}){ext}")
        if _key(candidate) not in taken and not candidate.exists():
            return candidate
        n += 1


def plan_outputs(items: list[tuple[int, Path, str]], output_dir: Path | None) -> dict[int, Path]:
    """Plan an output path per (job id, source, format), in queue order.

    Never collides with existing files or with another planned output in the queue.
    """
    taken: set[str] = set()
    plan: dict[int, Path] = {}
    for job_id, source, fmt in items:
        path = free_path(output_dir or source.parent, source.stem, extension_for(fmt), taken)
        taken.add(_key(path))
        plan[job_id] = path
    return plan
