"""The large drop target at the top of the window."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import icons, theme
from .theme import mix
from .widgets import AnimatedButton, _animate_to, _animation


class DropZone(QWidget):
    FULL_HEIGHT = 176
    COMPACT_HEIGHT = 104

    browse_files = Signal()
    browse_folder = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._highlight = 0.0   # drag-over intensity
        self._hover = 0.0       # mouse-hover intensity
        self._hl_anim = _animation(self, 200, self._set_highlight)
        self._hover_anim = _animation(self, 180, self._set_hover)
        self._height_anim = _animation(self, 260, lambda v: self.setFixedHeight(round(v)))
        self._compact = False
        self.setFixedHeight(self.FULL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._icon = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._icon.setFixedHeight(40)
        self._title = QLabel("Drop images, videos or folders here",
                             alignment=Qt.AlignmentFlag.AlignCenter)
        self._title.setObjectName("SectionTitle")
        self._hint = QLabel("JPG · PNG · WEBP · HEIC · AVIF · MP4 · MKV · MOV · and more",
                            alignment=Qt.AlignmentFlag.AlignCenter)
        self._hint.setObjectName("Small")

        self.browse_btn = AnimatedButton("Browse files", "secondary", "upload")
        self.folder_btn = AnimatedButton("Add folder", "ghost", "folder")
        self.browse_btn.clicked.connect(self.browse_files)
        self.folder_btn.clicked.connect(self.browse_folder)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        buttons.addWidget(self.browse_btn)
        buttons.addWidget(self.folder_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(6)
        layout.addStretch()
        layout.addWidget(self._icon)
        layout.addSpacing(4)
        layout.addWidget(self._title)
        layout.addWidget(self._hint)
        layout.addSpacing(10)
        layout.addLayout(buttons)
        layout.addStretch()

        theme.manager().changed.connect(lambda _: self._refresh_icon())
        self._refresh_icon()

    # --- animation state ---------------------------------------------------

    def set_compact(self, compact: bool) -> None:
        """Shrink to a slim strip once the queue has files, giving it more room."""
        if compact == self._compact:
            return
        self._compact = compact
        self._icon.setVisible(not compact)
        self._hint.setVisible(not compact)
        target = self.COMPACT_HEIGHT if compact else self.FULL_HEIGHT
        if self.isVisible():
            _animate_to(self._height_anim, self.height(), target)
        else:
            self.setFixedHeight(target)

    def set_highlight(self, on: bool) -> None:
        _animate_to(self._hl_anim, self._highlight, 1.0 if on else 0.0)

    def _set_highlight(self, v) -> None:
        was_on = self._highlight >= 0.5
        self._highlight = float(v)
        if was_on != (self._highlight >= 0.5):
            self._refresh_icon()
        self.update()

    def _set_hover(self, v) -> None:
        self._hover = float(v)
        self.update()

    def _refresh_icon(self) -> None:
        p = theme.current()
        color = p.accent if self._highlight >= 0.5 else p.text_muted
        self._icon.setPixmap(icons.pixmap("upload", color, 34, 1.6))
        self._title.setText("Release to add files" if self._highlight >= 0.5
                            else "Drop images, videos or folders here")

    # --- events -------------------------------------------------------------

    def enterEvent(self, e):
        _animate_to(self._hover_anim, self._hover, 1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        _animate_to(self._hover_anim, self._hover, 0.0)
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.browse_files.emit()
        super().mouseReleaseEvent(e)

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        fill = mix(p.surface, p.accent_soft, max(self._highlight, self._hover * 0.35))
        border = mix(p.border_strong, p.accent, max(self._highlight, self._hover * 0.45))
        pen = QPen(border, 1.6, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(r, 16, 16)

        if self._highlight > 0:  # soft inner glow while dragging
            glow = QColor(p.accent)
            glow.setAlphaF(0.10 * self._highlight)
            painter.setPen(QPen(glow, 6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(4, 4, -4, -4), 12, 12)
        painter.end()
