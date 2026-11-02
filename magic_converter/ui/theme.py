"""Light/dark palettes, the global stylesheet and a manager that follows the OS."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from . import icons


@dataclass(frozen=True)
class Palette:
    dark: bool
    bg: str
    surface: str
    surface_alt: str
    raised: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_border: str
    on_accent: str
    success: str
    error: str
    warning: str


LIGHT = Palette(
    dark=False,
    bg="#F6F6F9", surface="#FFFFFF", surface_alt="#F1F1F6", raised="#FFFFFF",
    border="#E5E5EE", border_strong="#CFCFDB",
    text="#17171F", text_muted="#6B6B7D", text_faint="#A8A8B8",
    accent="#7C5CFF", accent_hover="#8E72FF", accent_pressed="#6847F0",
    accent_soft="#EEE9FF", accent_border="#D8CCFF", on_accent="#FFFFFF",
    success="#16A34A", error="#DC2626", warning="#D97706",
)

DARK = Palette(
    dark=True,
    bg="#0F0F14", surface="#17171E", surface_alt="#1F1F28", raised="#2B2B37",
    border="#2A2A35", border_strong="#3A3A48",
    text="#EDEDF3", text_muted="#9090A2", text_faint="#5C5C6E",
    accent="#7C5CFF", accent_hover="#9177FF", accent_pressed="#6A4AF0",
    accent_soft="#262040", accent_border="#3A2F6B", on_accent="#FFFFFF",
    success="#34D399", error="#F87171", warning="#FBBF24",
)

_QSS = Template("""
QWidget { color: $text; }
QMainWindow, QDialog, #Root { background: $bg; }
QLabel { background: transparent; }
QToolTip {
    background: $surface; color: $text; border: 1px solid $border;
    border-radius: 6px; padding: 6px 8px;
}
#Title { font-size: 15pt; font-weight: 600; }
#SectionTitle { font-size: 11pt; font-weight: 600; }
#Muted { color: $text_muted; }
#Small { color: $text_muted; font-size: 9pt; }
#FieldLabel { color: $text_muted; }
#Card { background: $surface; border: 1px solid $border; border-radius: 14px; }
#Separator { background: $border; max-height: 1px; min-height: 1px; border: none; }
#Badge { color: $accent; font-weight: 600; }
#CustomBadge { color: $accent; font-size: 8pt; }
#StatusDone { color: $success; }
#StatusError { color: $error; }
#SmallError { color: $error; font-size: 9pt; }
#StatusMuted { color: $text_muted; }
#EmptyState { color: $text_faint; font-size: 10.5pt; }
#UpdateBanner { background: $accent_soft; border: 1px solid $accent_border; border-radius: 12px; }
#BannerTitle { font-weight: 600; }

#QueueRow { background: transparent; border-radius: 10px; }
#QueueRow:hover { background: $surface_alt; }

QComboBox {
    background: $surface_alt; border: 1px solid $border; border-radius: 8px;
    padding: 6px 10px; min-height: 20px; min-width: 90px;
}
QComboBox:hover { border-color: $border_strong; }
QComboBox:focus, QComboBox:on { border-color: $accent; }
QComboBox:disabled { color: $text_faint; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url($chevron); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 4px; outline: 0; selection-background-color: $accent_soft;
    selection-color: $text;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 0 8px; border-radius: 6px; }

QSpinBox, QLineEdit {
    background: $surface_alt; border: 1px solid $border; border-radius: 8px;
    padding: 5px 8px; selection-background-color: $accent; selection-color: $on_accent;
}
QSpinBox:hover, QLineEdit:hover { border-color: $border_strong; }
QSpinBox:focus, QLineEdit:focus { border-color: $accent; }
QSpinBox:disabled, QLineEdit:disabled { color: $text_faint; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }

QSlider { min-height: 22px; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $surface; border: 2px solid $accent;
    width: 12px; height: 12px; margin: -6px 0; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: $accent; }
QSlider::sub-page:horizontal:disabled { background: $border_strong; }
QSlider::handle:horizontal:disabled { border-color: $border_strong; background: $surface_alt; }

QRadioButton, QCheckBox { spacing: 8px; background: transparent; }
QRadioButton:disabled, QCheckBox:disabled { color: $text_faint; }
QRadioButton::indicator {
    width: 14px; height: 14px; border-radius: 9px;
    border: 2px solid $border_strong; background: $surface_alt;
}
QRadioButton::indicator:hover, QCheckBox::indicator:hover { border-color: $accent; }
QRadioButton::indicator:checked { border: 5px solid $accent; background: $on_accent; width: 8px; height: 8px; }
QCheckBox::indicator {
    width: 14px; height: 14px; border-radius: 5px;
    border: 2px solid $border_strong; background: $surface_alt;
}
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($check); }

QScrollArea, #QueueContainer { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 3px; min-height: 30px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: $text_faint; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: $surface; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft; }

QMessageBox { background: $bg; }
""")


def _qpalette(p: Palette) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: p.bg,
        QPalette.ColorRole.WindowText: p.text,
        QPalette.ColorRole.Base: p.surface_alt,
        QPalette.ColorRole.AlternateBase: p.surface,
        QPalette.ColorRole.Text: p.text,
        QPalette.ColorRole.Button: p.surface_alt,
        QPalette.ColorRole.ButtonText: p.text,
        QPalette.ColorRole.Highlight: p.accent,
        QPalette.ColorRole.HighlightedText: p.on_accent,
        QPalette.ColorRole.ToolTipBase: p.surface,
        QPalette.ColorRole.ToolTipText: p.text,
        QPalette.ColorRole.PlaceholderText: p.text_faint,
        QPalette.ColorRole.Link: p.accent,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(p.text_faint))
    return pal


def mix(a: str | QColor, b: str | QColor, t: float) -> QColor:
    """Linear blend between two colours (t=0 -> a, t=1 -> b)."""
    ca, cb = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
        round(ca.alpha() + (cb.alpha() - ca.alpha()) * t),
    )


class ThemeManager(QObject):
    """Applies the palette app-wide and re-applies it when the OS theme changes."""

    changed = Signal(object)  # Palette

    def __init__(self, app: QApplication, mode: str = "system") -> None:
        super().__init__(app)
        self._app = app
        self._mode = mode
        self._applying = False
        self.palette: Palette = LIGHT
        app.styleHints().colorSchemeChanged.connect(self._on_scheme_changed)
        self.apply()

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.apply()

    def _on_scheme_changed(self, *_):
        if self._mode == "system" and not self._applying:
            self.apply()

    def apply(self) -> None:
        self._applying = True
        try:
            hints = self._app.styleHints()
            # Qt >= 6.8 can force the scheme (this also themes native title bars).
            if hasattr(hints, "setColorScheme"):
                hints.setColorScheme({
                    "light": Qt.ColorScheme.Light,
                    "dark": Qt.ColorScheme.Dark,
                }.get(self._mode, Qt.ColorScheme.Unknown))
            if self._mode == "system":
                dark = hints.colorScheme() == Qt.ColorScheme.Dark
            else:
                dark = self._mode == "dark"
            self.palette = DARK if dark else LIGHT
            p = self.palette
            self._app.setPalette(_qpalette(p))
            self._app.setStyleSheet(_QSS.substitute(
                asdict(p),
                chevron=icons.svg_file("chevron-down", p.text_muted),
                check=icons.svg_file("check", p.on_accent, 3),
            ))
        finally:
            self._applying = False
        self.changed.emit(self.palette)


_manager: ThemeManager | None = None


def init(app: QApplication, mode: str) -> ThemeManager:
    global _manager
    _manager = ThemeManager(app, mode)
    return _manager


def manager() -> ThemeManager:
    assert _manager is not None, "theme.init() must be called first"
    return _manager


def current() -> Palette:
    return _manager.palette if _manager else LIGHT
