"""Plain data objects shared by the UI, the worker and the converters."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Union

from .formats import MediaKind


@dataclass
class ResizeOptions:
    mode: str = "none"          # "none" | "percent" | "size"
    percent: int = 50
    width: int = 1920
    height: int = 1080
    keep_aspect: bool = True


@dataclass
class ImageOptions:
    format: str = "PNG"
    quality: int = 90
    resize: ResizeOptions = field(default_factory=ResizeOptions)

    def summary(self) -> str:
        return self.format


@dataclass
class VideoOptions:
    format: str = "MP4"
    resolution: str = "Original"
    preset: str = "Medium"

    def summary(self) -> str:
        return self.format


Options = Union[ImageOptions, VideoOptions]


class JobStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


_job_ids = itertools.count(1)


@dataclass
class Job:
    """A queued file. Owned and mutated by the UI thread only."""

    source: Path
    kind: MediaKind
    size: int = 0
    override: Options | None = None
    status: JobStatus = JobStatus.WAITING
    output: Path | None = None
    id: int = field(default_factory=lambda: next(_job_ids))


@dataclass(frozen=True)
class ConversionTask:
    """Immutable snapshot handed to the background worker."""

    job_id: int
    source: Path
    kind: MediaKind
    options: Options
    output_dir: Path | None  # None = next to the source file
