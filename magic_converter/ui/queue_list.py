"""The file queue: one card per file, each with its own output format."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..core.formats import OUTPUT_LABELS, MediaKind, output_choices
from ..core.models import Job
from . import icons, theme
from .widgets import AnimatedButton, ElidedLabel, SmoothProgressBar, fade_in

KIND_LABEL = {MediaKind.IMAGE: "Image", MediaKind.VIDEO: "Video"}
# File extensions that are just other names for a detected format.
EXT_ALIASES = {"JPG": "JPEG", "JFIF": "JPEG", "TIF": "TIFF", "HEIF": "HEIC", "M4V": "MP4",
               "MPG": "MPEG", "TS": "MPEG-TS", "MTS": "M2TS"}


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


class QueueRow(QFrame):
    remove_requested = Signal(int)
    format_changed = Signal(int, str)   # job id, output format
    open_requested = Signal(int)

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job.id
        self.kind = job.kind
        self._done = False
        self.setObjectName("QueueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(58)

        self._kind_icon = QLabel()
        self._kind_icon.setFixedSize(20, 20)

        # Left column: file name + (details | error)
        self.name = ElidedLabel(job.source.name)
        self.name.setToolTip(str(job.source))

        ext = job.source.suffix.lstrip(".").upper()
        detected = job.detected or ext
        self.meta = QLabel(f"{human_size(job.size)} · {detected}")
        self.meta.setObjectName("Small")
        if ext and EXT_ALIASES.get(ext, ext) != detected:
            self.meta.setToolTip(f"Detected as {detected} from the file contents "
                                 f"(the name says .{ext.lower()})")
        self.output_name = ElidedLabel("", mode=Qt.TextElideMode.ElideMiddle)
        self.output_name.setObjectName("OutputName")
        details = QWidget()
        dl = QHBoxLayout(details)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addWidget(self.meta)
        dl.addWidget(self.output_name, 1)
        self.error = ElidedLabel("", mode=Qt.TextElideMode.ElideRight)
        self.error.setObjectName("SmallError")
        self.line2 = QStackedWidget()
        self.line2.addWidget(details)
        self.line2.addWidget(self.error)
        self.line2.setFixedHeight(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(self.name)
        text_col.addWidget(self.line2)

        # Type label + per-file format picker
        self.type_pill = QLabel(KIND_LABEL[job.kind])
        self.type_pill.setObjectName("TypePill")
        self.type_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_pill.setFixedSize(54, 20)

        self.format = QComboBox()
        self.format.setObjectName("RowCombo")
        self.format.setToolTip("Output format for this file")
        # A fixed-width holder keeps every card's dropdown aligned (stylesheet
        # min-width rules would otherwise override a width set on the combo itself).
        format_box = QWidget()
        format_box.setFixedWidth(124)
        fb = QHBoxLayout(format_box)
        fb.setContentsMargins(0, 0, 0, 0)
        fb.addWidget(self.format)
        for fmt in output_choices(job.kind):
            self.format.addItem(OUTPUT_LABELS.get(fmt, fmt), fmt)
        self.set_format(job.format)
        self.format.currentIndexChanged.connect(
            lambda _: self.format_changed.emit(self.job_id, self.current_format()))

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
        self.status_stack.setFixedWidth(140)
        self.status_stack.addWidget(self.status)
        self.status_stack.addWidget(prog_page)

        self.remove_btn = AnimatedButton("", "ghost", "x")
        self.remove_btn.setToolTip("Remove from queue")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.job_id))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        layout.setSpacing(12)
        layout.addWidget(self._kind_icon)
        layout.addLayout(text_col, 1)
        layout.addWidget(self.type_pill)
        layout.addWidget(format_box)
        layout.addWidget(self.status_stack)
        layout.addWidget(self.remove_btn)

        theme.manager().changed.connect(lambda _: self._refresh_icon())
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        name = "image" if self.kind is MediaKind.IMAGE else "film"
        self._kind_icon.setPixmap(icons.pixmap(name, theme.current().text_muted, 20, 1.7))

    # --- format & output preview --------------------------------------------

    def current_format(self) -> str:
        return self.format.currentData()

    def set_format(self, fmt: str) -> None:
        """Change the selection without emitting format_changed."""
        idx = self.format.findData(fmt)
        if idx >= 0 and idx != self.format.currentIndex():
            self.format.blockSignals(True)
            self.format.setCurrentIndex(idx)
            self.format.blockSignals(False)

    def set_output_name(self, name: str, full_path: str = "") -> None:
        self.output_name.setText(f"→  {name}" if name else "")
        self.output_name.setToolTip(full_path or name)

    def set_locked(self, locked: bool) -> None:
        self.format.setEnabled(not locked)
        self.remove_btn.setEnabled(not locked)

    # --- status ----------------------------------------------------------------

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

    def set_waiting(self) -> None:
        self._done = False
        self.setToolTip("")
        self.line2.setCurrentIndex(0)
        self._show_status("Waiting", "StatusMuted")

    def set_running(self) -> None:
        self.line2.setCurrentIndex(0)
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
        self.error.setText(message)
        self.error.setToolTip(tip)
        self.line2.setCurrentIndex(1)
        self._show_status("⚠  Failed", "StatusError", tip)

    def set_cancelled(self) -> None:
        self._show_status("Cancelled", "StatusMuted")

    def mouseDoubleClickEvent(self, e):
        if self._done:
            self.open_requested.emit(self.job_id)
        super().mouseDoubleClickEvent(e)


class QueueList(QWidget):
    remove_requested = Signal(int)
    format_changed = Signal(int, str)
    open_requested = Signal(int)
    clear_requested = Signal()
    apply_all_requested = Signal(object, str)  # MediaKind, output format

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[int, QueueRow] = {}

        title = QLabel("Queue")
        title.setObjectName("SectionTitle")
        self.count = QLabel("")
        self.count.setObjectName("Muted")
        self.apply_images_btn = self._apply_button(MediaKind.IMAGE)
        self.apply_videos_btn = self._apply_button(MediaKind.VIDEO)
        self.clear_btn = AnimatedButton("Clear all", "ghost")
        self.clear_btn.clicked.connect(self.clear_requested)
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 0, 0)
        header.setSpacing(4)
        header.addWidget(title)
        header.addSpacing(4)
        header.addWidget(self.count)
        header.addStretch()
        header.addWidget(self.apply_images_btn)
        header.addWidget(self.apply_videos_btn)
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

    # --- "Apply to all" menus ---------------------------------------------------

    def _apply_button(self, kind: MediaKind) -> AnimatedButton:
        noun = "images" if kind is MediaKind.IMAGE else "videos"
        btn = AnimatedButton(f"Apply to all {noun}  ▾", "ghost")
        btn.setToolTip(f"Set the same output format for every {noun[:-1]} in the queue")
        btn.clicked.connect(lambda: self._show_apply_menu(btn, kind))
        return btn

    def _show_apply_menu(self, btn: AnimatedButton, kind: MediaKind) -> None:
        menu = QMenu(self)
        noun = "image" if kind is MediaKind.IMAGE else "video"
        menu.addSection(f"Convert every {noun} to…")
        for fmt in output_choices(kind):
            action = menu.addAction(OUTPUT_LABELS.get(fmt, fmt))
            action.triggered.connect(lambda _=False, f=fmt: self.apply_all_requested.emit(kind, f))
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height() + 4)))

    # --- rows ---------------------------------------------------------------------

    def row(self, job_id: int) -> QueueRow | None:
        return self._rows.get(job_id)

    def rows(self):
        return self._rows.values()

    def add_job(self, job: Job) -> QueueRow:
        row = QueueRow(job)
        row.remove_requested.connect(self.remove_requested)
        row.format_changed.connect(self.format_changed)
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

    def set_locked(self, locked: bool) -> None:
        for w in (self.clear_btn, self.apply_images_btn, self.apply_videos_btn):
            w.setEnabled(not locked)
        for row in self._rows.values():
            row.set_locked(locked)

    def _update_header(self) -> None:
        n = len(self._rows)
        images = sum(1 for r in self._rows.values() if r.kind is MediaKind.IMAGE)
        self.count.setText(f"· {n} file{'s' if n != 1 else ''}" if n else "")
        self.clear_btn.setVisible(n > 0)
        # Batch actions only make sense with two or more files of that type.
        self.apply_images_btn.setVisible(images >= 2)
        self.apply_videos_btn.setVisible(n - images >= 2)
        self._stack.setCurrentIndex(1 if n else 0)
