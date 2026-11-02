"""Background queue runner. Lives in a QThread and talks to the UI via signals."""

from __future__ import annotations

import logging
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .errors import ConversionCancelled, ConversionError
from .formats import MediaKind, extension_for
from .image_converter import convert_image
from .models import ConversionTask
from .video_converter import convert_video

log = logging.getLogger(__name__)


def unique_output_path(task: ConversionTask) -> Path:
    folder = task.output_dir or task.source.parent
    ext = extension_for(task.options.format)
    candidate = folder / f"{task.source.stem}{ext}"
    n = 1
    while candidate.exists():
        candidate = folder / f"{task.source.stem} ({n}){ext}"
        n += 1
    return candidate


class ConversionWorker(QObject):
    job_started = Signal(int)
    job_progress = Signal(int, float)          # job id, 0..1 or -1 (indeterminate)
    job_done = Signal(int, str)                # job id, output path
    job_failed = Signal(int, str, str)         # job id, message, detail
    job_cancelled = Signal(int)
    overall_progress = Signal(float, int, int)  # fraction, finished count, total
    finished = Signal()

    def __init__(self, tasks: list[ConversionTask]) -> None:
        super().__init__()
        self._tasks = tasks
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Thread-safe: may be called from the UI thread."""
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        total = len(self._tasks)
        for index, task in enumerate(self._tasks):
            if self._cancel.is_set():
                for rest in self._tasks[index:]:
                    self.job_cancelled.emit(rest.job_id)
                break
            self._run_one(task, index, total)
            self.overall_progress.emit((index + 1) / total, index + 1, total)
        self.finished.emit()

    def _run_one(self, task: ConversionTask, index: int, total: int) -> None:
        self.job_started.emit(task.job_id)

        def on_progress(p: float) -> None:
            self.job_progress.emit(task.job_id, p)
            if p >= 0:
                self.overall_progress.emit((index + p) / total, index, total)

        try:
            folder = task.output_dir or task.source.parent
            if not task.source.is_file():
                raise ConversionError("The file no longer exists.")
            folder.mkdir(parents=True, exist_ok=True)
            dst = unique_output_path(task)
            if task.kind is MediaKind.IMAGE:
                convert_image(task.source, dst, task.options, self._cancel, on_progress)
            else:
                convert_video(task.source, dst, task.options, self._cancel, on_progress)
        except ConversionCancelled:
            self.job_cancelled.emit(task.job_id)
        except ConversionError as exc:
            self.job_failed.emit(task.job_id, exc.message, exc.detail)
        except PermissionError as exc:
            self.job_failed.emit(task.job_id, "Can't write to the output folder.", str(exc))
        except Exception as exc:  # never let one file kill the batch
            log.exception("Unexpected error converting %s", task.source)
            self.job_failed.emit(task.job_id, f"Unexpected error: {exc}", traceback.format_exc())
        else:
            self.job_done.emit(task.job_id, str(dst))
