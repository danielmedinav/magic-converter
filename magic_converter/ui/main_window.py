"""Main application window."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QThread, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__, updater
from ..core.formats import MediaKind, dialog_filter, kind_of
from ..core.models import ConversionTask, Job, JobStatus, Options
from ..core.worker import ConversionWorker
from ..settings import AppSettings, save_settings
from . import icons, theme
from .drop_zone import DropZone
from .queue_list import QueueList
from .settings_panel import OverrideDialog, SettingsPanel
from .update_banner import UpdateBanner
from .widgets import AnimatedButton, SmoothProgressBar

THEME_CYCLE = {"system": "light", "light": "dark", "dark": "system"}
THEME_ICON = {"system": "monitor", "light": "sun", "dark": "moon"}
THEME_TIP = {"system": "Theme: follow system", "light": "Theme: light", "dark": "Theme: dark"}


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.jobs: dict[int, Job] = {}
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None
        self._batch: list[int] = []
        self._last_output: Path | None = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(780, 620)
        avail = self.screen().availableGeometry()
        self.resize(min(940, avail.width() - 40), min(820, avail.height() - 40))
        self.setAcceptDrops(True)

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self._save_settings)
        self._msg_timer = QTimer(self, singleShot=True, interval=7000)
        self._msg_timer.timeout.connect(lambda: self.message.setText(""))

        self._build_ui()
        self.panel.load(settings)
        self._update_theme_button()
        self._update_buttons()
        if settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(settings.window_geometry.encode()))
        # Quiet background update check shortly after start-up.
        QTimer.singleShot(2500, self.update_banner.check)

    # --- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget(objectName="Root")
        self.setCentralWidget(root)

        self.logo = QLabel()
        self.logo.setFixedSize(24, 24)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        self.theme_btn = AnimatedButton("", "ghost", "monitor")
        self.theme_btn.clicked.connect(self._cycle_theme)
        self.version_btn = AnimatedButton(f"v{__version__}", "ghost")
        self.version_btn.setToolTip("Check for updates")
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(self.logo)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.version_btn)
        header.addWidget(self.theme_btn)

        self.update_banner = UpdateBanner()
        self.version_btn.clicked.connect(lambda: self.update_banner.check(manual=True))
        self.update_banner.message.connect(self._show_message)
        self.update_banner.update_requested.connect(self._on_update_requested)
        self.update_banner.install_ready.connect(self._install_update)

        self.drop_zone = DropZone()
        self.drop_zone.browse_files.connect(self._browse_files)
        self.drop_zone.browse_folder.connect(self._browse_folder)

        self.queue = QueueList()
        self.queue.remove_requested.connect(self._remove_job)
        self.queue.settings_requested.connect(self._edit_job)
        self.queue.open_requested.connect(self._reveal_job)
        self.queue.clear_requested.connect(self._clear_queue)

        self.panel = SettingsPanel()
        self.panel.changed.connect(self._on_settings_changed)

        # Footer: overall progress + actions
        self.overall_label = QLabel("Overall")
        self.overall_label.setObjectName("Muted")
        self.overall_count = QLabel("")
        self.overall_count.setObjectName("Muted")
        self.overall = SmoothProgressBar(height=6)
        self.message = QLabel("")
        self.message.setObjectName("Muted")
        self.open_btn = AnimatedButton("Open folder", "ghost", "folder-open")
        self.open_btn.clicked.connect(self._open_last_folder)
        self.open_btn.hide()
        self.cancel_btn = AnimatedButton("Cancel", "secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        self.convert_btn = AnimatedButton("Convert", "primary")
        self.convert_btn.setMinimumWidth(140)
        self.convert_btn.clicked.connect(self._start)

        prog_row = QHBoxLayout()
        prog_row.addWidget(self.overall_label)
        prog_row.addStretch()
        prog_row.addWidget(self.overall_count)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.message, 1)
        action_row.addWidget(self.open_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.convert_btn)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 20, 28, 22)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self.update_banner)
        layout.addWidget(self.drop_zone)
        layout.addWidget(self.queue, 1)
        layout.addWidget(self.panel)
        footer = QVBoxLayout()
        footer.setSpacing(8)
        footer.addLayout(prog_row)
        footer.addWidget(self.overall)
        footer.addSpacing(6)
        footer.addLayout(action_row)
        layout.addLayout(footer)

        theme.manager().changed.connect(lambda _: self._refresh_logo())
        self._refresh_logo()

    def _refresh_logo(self) -> None:
        self.logo.setPixmap(icons.pixmap("sparkles", theme.current().accent, 24))

    # --- Theme --------------------------------------------------------------

    def _cycle_theme(self) -> None:
        self.settings.theme = THEME_CYCLE[self.settings.theme]
        theme.manager().set_mode(self.settings.theme)
        self._update_theme_button()
        self._save_timer.start()

    def _update_theme_button(self) -> None:
        self.theme_btn.set_icon_name(THEME_ICON[self.settings.theme])
        self.theme_btn.setToolTip(THEME_TIP[self.settings.theme] + "  (click to change)")

    # --- Adding files -------------------------------------------------------

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add files", self.settings.last_browse_dir, dialog_filter())
        if files:
            self.settings.last_browse_dir = str(Path(files[0]).parent)
            self.add_paths([Path(f) for f in files])

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add folder", self.settings.last_browse_dir)
        if folder:
            self.settings.last_browse_dir = folder
            self.add_paths([Path(folder)])

    def add_paths(self, paths: list[Path]) -> None:
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                for root, dirs, names in os.walk(p):
                    dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                    files.extend(Path(root) / n for n in sorted(names))
            elif p.is_file():
                files.append(p)

        known = {self._key(j.source) for j in self.jobs.values()}
        added = skipped = 0
        for f in files:
            kind = kind_of(f)
            if kind is None or ".mcpart." in f.name:
                skipped += 1
                continue
            key = self._key(f)
            if key in known:
                continue
            known.add(key)
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            job = Job(source=f, kind=kind, size=size)
            self.jobs[job.id] = job
            opts = self._effective(job)
            row = self.queue.add_job(job, opts.format, custom=False)
            row.set_locked(self._busy())
            added += 1

        parts = []
        if added:
            parts.append(f"Added {added} file{'s' if added != 1 else ''}.")
        if skipped:
            parts.append(f"Skipped {skipped} unsupported file{'s' if skipped != 1 else ''}.")
        if not added and not skipped and files:
            parts.append("Those files are already in the queue.")
        if not files and paths:
            parts.append("No files found.")
        self._show_message(" ".join(parts))
        self._update_buttons()

    @staticmethod
    def _key(path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    # --- Drag & drop (anywhere on the window) -------------------------------

    def _has_local_urls(self, event) -> bool:
        md = event.mimeData()
        return md.hasUrls() and any(u.isLocalFile() for u in md.urls())

    def dragEnterEvent(self, event):
        if self._has_local_urls(event):
            event.acceptProposedAction()
            self.drop_zone.set_highlight(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._has_local_urls(event):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_zone.set_highlight(False)

    def dropEvent(self, event):
        self.drop_zone.set_highlight(False)
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        event.acceptProposedAction()
        # Defer so the OS drag operation finishes before we walk folders.
        QTimer.singleShot(0, lambda: self.add_paths(paths))

    # --- Queue management ---------------------------------------------------

    def _effective(self, job: Job) -> Options:
        if job.override is not None:
            return job.override
        return self.settings.image if job.kind is MediaKind.IMAGE else self.settings.video

    def _refresh_targets(self) -> None:
        for job in self.jobs.values():
            row = self.queue.row(job.id)
            if row:
                row.set_target(self._effective(job).format, job.override is not None)

    def _remove_job(self, job_id: int) -> None:
        if self._busy():
            return
        self.jobs.pop(job_id, None)
        self.queue.remove(job_id)
        self._update_buttons()

    def _clear_queue(self) -> None:
        if self._busy():
            return
        self.jobs.clear()
        self.queue.clear()
        self.overall.set_value(0, animate=False)
        self.overall_count.setText("")
        self.open_btn.hide()
        self._update_buttons()

    def _edit_job(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if not job or self._busy():
            return
        dlg = OverrideDialog(job.source.name, job.kind, self._effective(job),
                             job.override is not None, self)
        if dlg.exec():
            job.override = dlg.result_options
            if job.status is JobStatus.DONE:  # allow re-converting with new settings
                job.status = JobStatus.WAITING
                self.queue.row(job_id).set_waiting()
            self._refresh_targets()
            self._update_buttons()

    def _reveal_job(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if job and job.output and job.output.exists():
            self._reveal(job.output)

    @staticmethod
    def _reveal(path: Path) -> None:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _open_last_folder(self) -> None:
        if self._last_output and self._last_output.exists():
            self._reveal(self._last_output)

    # --- Settings -----------------------------------------------------------

    def _on_settings_changed(self) -> None:
        self.panel.store(self.settings)
        self._refresh_targets()
        self._save_timer.start()

    def _save_settings(self) -> None:
        self.panel.store(self.settings)
        self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        save_settings(self.settings)

    # --- Conversion ---------------------------------------------------------

    def _busy(self) -> bool:
        return self._thread is not None

    def _pending(self) -> list[Job]:
        return [j for j in self.jobs.values()
                if j.status in (JobStatus.WAITING, JobStatus.FAILED, JobStatus.CANCELLED)]

    def _update_buttons(self) -> None:
        busy = self._busy()
        pending = len(self._pending())
        self.convert_btn.setEnabled(not busy and pending > 0)
        self.convert_btn.setText("Converting…" if busy else
                                 f"Convert {pending} file{'s' if pending != 1 else ''}" if pending
                                 else "Convert")
        self.cancel_btn.setVisible(busy)
        self.cancel_btn.setEnabled(busy)
        self.cancel_btn.setText("Cancel")
        self.queue.clear_btn.setEnabled(not busy)
        self.drop_zone.set_compact(bool(self.jobs))
        self.panel.set_locked(busy)
        for row in self.queue.rows():
            row.set_locked(busy)

    def _start(self) -> None:
        if self._busy():
            return
        pending = self._pending()
        if not pending:
            self._show_message("Add some files first.")
            return
        self.panel.store(self.settings)
        output_dir = None
        if self.settings.output_mode == "custom":
            output_dir = Path(self.settings.output_dir)

        tasks = []
        for job in pending:
            job.status = JobStatus.WAITING
            self.queue.row(job.id).set_waiting()
            tasks.append(ConversionTask(job.id, job.source, job.kind,
                                        copy.deepcopy(self._effective(job)), output_dir))
        self._batch = [t.job_id for t in tasks]

        self._thread = QThread(self)
        self._worker = ConversionWorker(tasks)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.job_started.connect(self._on_job_started)
        self._worker.job_progress.connect(self._on_job_progress)
        self._worker.job_done.connect(self._on_job_done)
        self._worker.job_failed.connect(self._on_job_failed)
        self._worker.job_cancelled.connect(self._on_job_cancelled)
        self._worker.overall_progress.connect(self._on_overall)
        self._worker.finished.connect(self._on_finished)

        self.overall.set_state("normal")
        self.overall.set_value(0, animate=False)
        self.overall_count.setText(f"0 / {len(tasks)}")
        self.open_btn.hide()
        self._show_message("")
        self._thread.start()
        self._update_buttons()

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("Cancelling…")

    @Slot(int)
    def _on_job_started(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.RUNNING
            self.queue.row(job_id).set_running()
            self.queue.scroll_to(job_id)

    @Slot(int, float)
    def _on_job_progress(self, job_id: int, value: float) -> None:
        row = self.queue.row(job_id)
        if row:
            row.set_progress(value)

    @Slot(int, str)
    def _on_job_done(self, job_id: int, output: str) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.DONE
            job.output = Path(output)
            self._last_output = job.output
            self.queue.row(job_id).set_done(output)

    @Slot(int, str, str)
    def _on_job_failed(self, job_id: int, message: str, detail: str) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            self.queue.row(job_id).set_failed(message, detail)

    @Slot(int)
    def _on_job_cancelled(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.CANCELLED
            self.queue.row(job_id).set_cancelled()

    @Slot(float, int, int)
    def _on_overall(self, fraction: float, done: int, total: int) -> None:
        self.overall.set_value(fraction)
        self.overall_count.setText(f"{done} / {total}")

    @Slot()
    def _on_finished(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._worker:
            self._worker.deleteLater()
        self._thread = self._worker = None

        statuses = [self.jobs[i].status for i in self._batch if i in self.jobs]
        done = statuses.count(JobStatus.DONE)
        failed = statuses.count(JobStatus.FAILED)
        cancelled = statuses.count(JobStatus.CANCELLED)
        parts = [f"{done} converted"]
        if failed:
            parts.append(f"{failed} failed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")
        self._show_message(("Done — " if not cancelled else "Stopped — ") + ", ".join(parts) + ".")
        self.overall.set_state("error" if failed and not done else "success" if done else "normal")
        if done:
            self.open_btn.show()
        self._update_buttons()
        if not self.isActiveWindow():
            QApplication.alert(self)  # flash the taskbar button

    def _show_message(self, text: str) -> None:
        self.message.setText(text)
        if text:
            self._msg_timer.start()

    # --- Updates ------------------------------------------------------------

    def _on_update_requested(self) -> None:
        if self._busy():
            self._show_message("Finish or cancel the current conversion before updating.")
            return
        self.update_banner.start_download()

    def _install_update(self, installer: str) -> None:
        if self._busy():
            self._show_message("Finish or cancel the current conversion before updating.")
            return
        try:
            updater.launch_installer(Path(installer))
        except OSError as exc:
            self._show_message(f"Couldn't start the installer: {exc}")
            return
        self.close()  # the installer replaces the files and relaunches the app

    # --- Lifecycle ----------------------------------------------------------

    def closeEvent(self, event):
        if self.update_banner.is_downloading():
            self.update_banner.cancel()
        if self._busy():
            answer = QMessageBox.question(
                self, APP_NAME, "A conversion is still running. Cancel it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._thread.quit()
            self._thread.wait(10000)
        self._save_timer.stop()
        self._save_settings()
        super().closeEvent(event)
