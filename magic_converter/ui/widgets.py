"""Custom-painted widgets with subtle animations."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QLabel, QPushButton, QSizePolicy, QWidget,
)

from . import icons, theme
from .theme import mix


def _animation(parent, duration: int, on_value) -> QVariantAnimation:
    anim = QVariantAnimation(parent)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(on_value)
    return anim


def _animate_to(anim: QVariantAnimation, current: float, target: float) -> None:
    anim.stop()
    anim.setStartValue(float(current))
    anim.setEndValue(float(target))
    anim.start()


class AnimatedButton(QPushButton):
    """Rounded button with a smooth hover/press colour transition.

    variant: "primary" (accent filled), "secondary" (outlined) or "ghost" (flat).
    """

    def __init__(self, text: str = "", variant: str = "secondary",
                 icon_name: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.variant = variant
        self.icon_name = icon_name
        self._hover = 0.0
        self._anim = _animation(self, 160, self._set_hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        theme.manager().changed.connect(lambda _: self.update())

    def set_icon_name(self, name: str | None) -> None:
        self.icon_name = name
        self.updateGeometry()
        self.update()

    def _set_hover(self, v) -> None:
        self._hover = float(v)
        self.update()

    def enterEvent(self, e):
        _animate_to(self._anim, self._hover, 1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        _animate_to(self._anim, self._hover, 0.0)
        super().leaveEvent(e)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self._font())
        text_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        icon_w = 16 if self.icon_name else 0
        gap = 8 if (text_w and icon_w) else 0
        h = 40 if self.variant == "primary" else 34
        pad = 22 if self.text() else (h - icon_w) // 2
        return QSize(text_w + icon_w + gap + pad * 2, h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _font(self):
        f = self.font()
        f.setWeight(f.Weight.DemiBold if self.variant == "primary" else f.Weight.Medium)
        return f

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 10 if self.variant == "primary" else 8
        enabled = self.isEnabled()
        pressed = self.isDown()

        border = None
        if self.variant == "primary":
            bg = mix(p.accent, p.accent_hover, self._hover)
            if pressed:
                bg = QColor(p.accent_pressed)
            fg = QColor(p.on_accent)
            if not enabled:
                bg, fg = QColor(p.border), QColor(p.text_faint)
        elif self.variant == "secondary":
            bg = mix(p.surface, p.surface_alt, self._hover)
            border = mix(p.border, p.border_strong, self._hover)
            if pressed:
                bg = QColor(p.border)
            fg = QColor(p.text if enabled else p.text_faint)
        else:  # ghost
            transparent = QColor(p.surface_alt)
            transparent.setAlpha(0)
            bg = mix(transparent, p.surface_alt if not p.dark else p.raised, self._hover)
            if pressed:
                bg = QColor(p.border)
            fg = QColor(p.text_muted if enabled else p.text_faint)
            if self._hover > 0.5 and enabled:
                fg = QColor(p.text)

        painter.setPen(QPen(border, 1) if border else Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(r, radius, radius)

        font = self._font()
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        icon_w = 16 if self.icon_name else 0
        gap = 8 if (text_w and icon_w) else 0
        x = (self.width() - (text_w + icon_w + gap)) / 2
        if self.icon_name:
            px = icons.pixmap(self.icon_name, fg.name(), 16)
            painter.drawPixmap(round(x), round((self.height() - 16) / 2), px)
            x += icon_w + gap
        if self.text():
            painter.setPen(fg)
            painter.drawText(QRectF(x, 0, text_w + 1, self.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        painter.end()


class SmoothProgressBar(QWidget):
    """Thin rounded progress bar with animated value and an indeterminate mode."""

    def __init__(self, parent: QWidget | None = None, height: int = 6) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._display = 0.0
        self._state = "normal"
        self._indeterminate = False
        self._phase = 0.0
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = _animation(self, 280, self._set_display)
        self._loop = QVariantAnimation(self)
        self._loop.setStartValue(0.0)
        self._loop.setEndValue(1.0)
        self._loop.setDuration(1300)
        self._loop.setLoopCount(-1)
        self._loop.valueChanged.connect(self._set_phase)
        theme.manager().changed.connect(lambda _: self.update())

    def _set_display(self, v) -> None:
        self._display = float(v)
        self.update()

    def _set_phase(self, v) -> None:
        self._phase = float(v)
        self.update()

    def value(self) -> float:
        return self._value

    def set_value(self, value: float, animate: bool = True) -> None:
        value = max(0.0, min(1.0, value))
        self.set_indeterminate(False)
        self._value = value
        if animate and self.isVisible():
            _animate_to(self._anim, self._display, value)
        else:
            self._anim.stop()
            self._set_display(value)

    def set_indeterminate(self, on: bool) -> None:
        if on == self._indeterminate:
            return
        self._indeterminate = on
        if on:
            self._loop.start()
        else:
            self._loop.stop()
        self.update()

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        radius = r.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.border))
        painter.drawRoundedRect(r, radius, radius)

        color = {"success": p.success, "error": p.error}.get(self._state, p.accent)
        painter.setBrush(QColor(color))
        if self._indeterminate:
            clip = QPainterPath()
            clip.addRoundedRect(r, radius, radius)
            painter.setClipPath(clip)
            seg = r.width() * 0.3
            x = -seg + (r.width() + seg) * QEasingCurve(QEasingCurve.Type.InOutQuad).valueForProgress(self._phase)
            painter.drawRoundedRect(QRectF(x, 0, seg, r.height()), radius, radius)
        elif self._display > 0:
            w = max(r.height(), r.width() * self._display)
            painter.drawRoundedRect(QRectF(0, 0, w, r.height()), radius, radius)
        painter.end()


class SegmentedControl(QWidget):
    """Pill-shaped segmented selector with a sliding indicator."""

    currentChanged = Signal(int)

    def __init__(self, options: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options
        self._index = 0
        self._pos = 0.0
        self._hover_index = -1
        self._anim = _animation(self, 220, self._set_pos)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        theme.manager().changed.connect(lambda _: self.update())

    def _set_pos(self, v) -> None:
        self._pos = float(v)
        self.update()

    def options(self) -> list[str]:
        return list(self._options)

    def current_index(self) -> int:
        return self._index

    def current_text(self) -> str:
        return self._options[self._index]

    def set_current_index(self, index: int, animate: bool = True) -> None:
        index = max(0, min(len(self._options) - 1, index))
        if index == self._index:
            return
        self._index = index
        if animate and self.isVisible():
            _animate_to(self._anim, self._pos, index)
        else:
            self._set_pos(index)
        self.currentChanged.emit(index)

    def set_current_text(self, text: str, animate: bool = True) -> None:
        if text in self._options:
            self.set_current_index(self._options.index(text), animate)

    def _segment_width(self) -> float:
        return (self.width() - 6) / len(self._options)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        widest = max(fm.horizontalAdvance(o) for o in self._options)
        return QSize(int((widest + 32) * len(self._options) + 6), 34)

    def mouseMoveEvent(self, e):
        idx = int((e.position().x() - 3) // self._segment_width())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()

    def leaveEvent(self, e):
        self._hover_index = -1
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            idx = int((e.position().x() - 3) // self._segment_width())
            self.set_current_index(idx)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Left:
            self.set_current_index(self._index - 1)
        elif e.key() == Qt.Key.Key_Right:
            self.set_current_index(self._index + 1)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(p.border), 1))
        painter.setBrush(QColor(p.surface_alt))
        painter.drawRoundedRect(r, 9, 9)

        seg_w = self._segment_width()
        ind = QRectF(3 + self._pos * seg_w, 3, seg_w, self.height() - 6)
        painter.setPen(QPen(QColor(p.border), 1) if not p.dark else Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.raised))
        painter.drawRoundedRect(ind, 7, 7)

        for i, text in enumerate(self._options):
            rect = QRectF(3 + i * seg_w, 0, seg_w, self.height())
            if not self.isEnabled():
                color = p.text_faint
            elif i == self._index or i == self._hover_index:
                color = p.text
            else:
                color = p.text_muted
            font = self.font()
            font.setWeight(font.Weight.DemiBold if i == self._index else font.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


class ElidedLabel(QLabel):
    """Single-line label that elides long text (in the middle by default)."""

    def __init__(self, text: str = "", parent: QWidget | None = None,
                 mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle) -> None:
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        self._refresh()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full = text
        self._refresh()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.FontChange:
            self._refresh()

    def _refresh(self) -> None:
        elided = QFontMetrics(self.font()).elidedText(
            self._full, self._mode, max(10, self.width()))
        super().setText(elided)


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Separator")


def icon_label(name: str, color: str, size: int = 18) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(icons.pixmap(name, color, size))
    lbl.setFixedSize(size, size)
    return lbl


def fade_in(widget: QWidget, duration: int = 220) -> None:
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    # Drop the effect afterwards: it would otherwise slow down repaints.
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
