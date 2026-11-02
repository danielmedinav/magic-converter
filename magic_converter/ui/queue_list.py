"""The file queue: one animated row per file."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.formats import MediaKind
from ..core.models import Job
from . import icons, theme
from .widgets import AnimatedButton, ElidedLabel, SmoothProgressBar, fade_in


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


class QueueRow(QFrame):
    remove_requested = Signal(int)
    settings_requested = Signal(int)
    open_requested = Signal(int)

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job.id
        self.kind = job.kind
        self._done = False
        self.setObjectName("QueueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(56)

        self._kind_icon = QLabel()
        self._kind_icon.setFixedSize(20, 20)

        self.name = ElidedLabel(job.source.name)
        self.name.setToolTip(str(job.source))
        self._meta_text = f"{human_size(job.size)} · {job.source.suffix.lstrip('.').upper()}"
        self.meta = ElidedLabel(self._meta_text, mode=Qt.TextElideMode.ElideRight)
        self.meta.setObjectName("Small")
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.addWidget(self.name)
        text_col.addWidget(self.meta)

        self.badge = QLabel()
        self.badge.setObjectName("Badge")
        self.badge.setMinimumWidth(64)
        self.custom_badge = QLabel("custom")
        self.custom_badge.setObjectName("CustomBadge")
        self.custom_badge.setToolTip("This file uses its own settings")
        badge_col = QVBoxLayout()
        badge_col.setSpacing(0)
        badge_col.addStretch()
        badge_col.addWidget(self.badge)
        badge_col.addWidget(self.custom_badge)
        badge_col.addStretch()

        # Status area: label <-> progress bar
        self.status = ElidedLabel("Waiting", mode=Qt.TextElideMode.ElideRight)
        self.status.setObjectName("StatusMuted")
        self.progress = SmoothProgressBar()
        self.percent = QLabel("")
        self.percent.setObjectName("Small")
        self.percent.setFixedWidth(36)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_page = QWidget()
        prog_layout = QHBoxLayout(prog_page)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(8)
        prog_layout.addWidget(self.progress, 1)
        prog_layout.addWidget(self.percent)
        self.status_stack = QStackedWidget()
        self.status_stack.setFixedWidth(180)
        self.status_stack.addWidget(self.status)
        self.status_stack.addWidget(prog_page)

        self.settings_btn = AnimatedButton("", "ghost", "sliders")
        self.settings_btn.setToolTip("Settings for this file")
        self.settings_btn.clicked.connect(lambda: self.settings_requested.emit(self.job_id))
        self.remove_btn = AnimatedButton("", "ghost", "x")
        self.remove_btn.setToolTip("Remove from queue")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.job_id))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        layout.setSpacing(12)
        layout.addWidget(self._kind_icon)
        layout.addLayout(text_col, 1)
        layout.addLayout(badge_col)
        layout.addWidget(self.status_stack)
        layout.addWidget(self.settings_btn)
        layout.addWidget(self.remove_btn)

        theme.manager().changed.connect(lambda _: self._refresh_icon())
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        name = "image" if self.kind is MediaKind.IMAGE else "film"
        self._kind_icon.setPixmap(icons.pixmap(name, theme.current().text_muted, 20, 1.7))

    # --- state ---------------------------------------------------------------

    def set_target(self, fmt: str, custom: bool) -> None:
        self.badge.setText(f"→ {fmt}")
        self.custom_badge.setVisible(custom)

    def set_locked(self, locked: bool) -> None:
        self.settings_btn.setEnabled(not locked)
        self.remove_btn.setEnabled(not locked)

    @staticmethod
    def _restyle(label: QLabel, style: str) -> None:
        label.setObjectName(style)
        label.style().unpolish(label)
        label.style().polish(label)

    def _show_status(self, text: str, style: str, tooltip: str = "") -> None:
        self.status.setText(text)
        self._restyle(self.status, style)
        self.status.setToolTip(tooltip)
        self.status_stack.setCurrentIndex(0)

    def _set_meta(self, text: str, style: str = "Small", tooltip: str = "") -> None:
        self.meta.setText(text)
        self._restyle(self.meta, style)
        self.meta.setToolTip(tooltip)

    def set_waiting(self) -> None:
        self._done = False
        self.setToolTip("")
        self._set_meta(self._meta_text)
        self._show_status("Waiting", "StatusMuted")

    def set_running(self) -> None:
        self.progress.set_state("normal")
        self.progress.set_value(0, animate=False)
        self.percent.setText("")
        self.status_stack.setCurrentIndex(1)

    def set_progress(self, value: float) -> None:
        if value < 0:
            self.progress.set_indeterminate(True)
            self.percent.setText("")
        else:
            self.progress.set_value(value)
            self.percent.setText(f"{round(value * 100)}%")

    def set_done(self, output: str) -> None:
        self._done = True
        self.setToolTip(f"Saved to {output}\nDouble-click to show in folder")
        self._show_status("✓  Done", "StatusDone", output)

    def set_failed(self, message: str, detail: str) -> None:
        tip = message if not detail else f"{message}\n\nDetails:\n{detail[-800:]}"
        self._set_meta(message, "SmallError", tip)
        self._show_status("⚠  Failed", "StatusError", tip)

    def set_cancelled(self) -> None:
        self._show_status("Cancelled", "StatusMuted")

    def mouseDoubleClickEvent(self, e):
        if self._done:
            self.open_requested.emit(self.job_id)
        super().mouseDoubleClickEvent(e)


class QueueList(QWidget):
    remove_requested = Signal(int)
    settings_requested = Signal(int)
    open_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[int, QueueRow] = {}

        title = QLabel("Queue")
        title.setObjectName("SectionTitle")
        self.count = QLabel("")
        self.count.setObjectName("Muted")
        self.clear_btn = AnimatedButton("Clear all", "ghost")
        self.clear_btn.clicked.connect(self.clear_requested)
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(title)
        header.addWidget(self.count)
        header.addStretch()
        header.addWidget(self.clear_btn)

        self._container = QWidget()
        self._container.setObjectName("QueueContainer")
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(0, 0, 4, 0)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._container)
        scroll.viewport().setAutoFillBackground(False)
        self._scroll = scroll

        empty = QLabel("Your queue is empty — add some files to get started.")
        empty.setObjectName("EmptyState")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._stack = QStackedWidget()
        self._stack.addWidget(empty)
        self._stack.addWidget(scroll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self._stack, 1)
        self._update_header()

    def row(self, job_id: int) -> QueueRow | None:
        return self._rows.get(job_id)

    def rows(self):
        return self._rows.values()

    def add_job(self, job: Job, target: str, custom: bool) -> QueueRow:
        row = QueueRow(job)
        row.set_target(target, custom)
        row.remove_requested.connect(self.remove_requested)
        row.settings_requested.connect(self.settings_requested)
        row.open_requested.connect(self.open_requested)
        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        self._rows[job.id] = row
        if len(self._rows) <= 60:  # skip the animation for huge batches
            fade_in(row)
        self._update_header()
        return row

    def remove(self, job_id: int) -> None:
        row = self._rows.pop(job_id, None)
        if row:
            row.setParent(None)
            row.deleteLater()
        self._update_header()

    def clear(self) -> None:
        for job_id in list(self._rows):
            self.remove(job_id)

    def scroll_to(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row:
            self._scroll.ensureWidgetVisible(row, 0, 8)

    def _update_header(self) -> None:
        n = len(self._rows)
        self.count.setText(f"· {n} file{'s' if n != 1 else ''}" if n else "")
        self.clear_btn.setVisible(n > 0)
        self._stack.setCurrentIndex(1 if n else 0)
