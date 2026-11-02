"""Slim banner that announces, downloads and installs app updates."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import __version__, updater
from ..paths import is_frozen
from . import icons, theme
from .widgets import AnimatedButton, ElidedLabel, SmoothProgressBar, fade_in


class _Bridge(QObject):
    """Carries results from worker threads back to the UI thread."""

    found = Signal(object, bool)      # UpdateInfo | None, manual
    check_failed = Signal(str, bool)  # message, manual
    progress = Signal(float)
    downloaded = Signal(str)
    download_failed = Signal(str)
    download_cancelled = Signal()


class UpdateBanner(QFrame):
    message = Signal(str)            # short status text for the main window footer
    update_requested = Signal()      # main window decides whether it's safe to proceed
    install_ready = Signal(str)      # path to the downloaded installer

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        self._info: updater.UpdateInfo | None = None
        self._action = "Update"  # primary button label: "Update" or "Install"
        self._checking = False
        self._downloading = False
        self._cancel = threading.Event()
        self._bridge = _Bridge(self)
        self._bridge.found.connect(self._on_found)
        self._bridge.check_failed.connect(self._on_check_failed)
        self._bridge.progress.connect(self._on_progress)
        self._bridge.downloaded.connect(self._on_downloaded)
        self._bridge.download_failed.connect(self._on_download_failed)
        self._bridge.download_cancelled.connect(self._on_download_cancelled)

        self._icon = QLabel()
        self._icon.setFixedSize(20, 20)
        self.title = QLabel()
        self.title.setObjectName("BannerTitle")
        self.subtitle = ElidedLabel("")
        self.subtitle.setObjectName("Small")
        self.progress = SmoothProgressBar(height=4)
        self.progress.hide()
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(self.title)
        text_col.addWidget(self.subtitle)
        text_col.addWidget(self.progress)

        self.secondary_btn = AnimatedButton("Later", "ghost")
        self.primary_btn = AnimatedButton("Update", "primary")
        self.secondary_btn.clicked.connect(self._on_secondary)
        self.primary_btn.clicked.connect(self._on_primary)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 10, 10)
        layout.setSpacing(12)
        layout.addWidget(self._icon)
        layout.addLayout(text_col, 1)
        layout.addWidget(self.secondary_btn)
        layout.addWidget(self.primary_btn)

        theme.manager().changed.connect(lambda _: self._refresh_icon())
        self._refresh_icon()
        self.hide()

    def _refresh_icon(self) -> None:
        self._icon.setPixmap(icons.pixmap("sparkles", theme.current().accent, 20))

    # --- Checking -----------------------------------------------------------

    def check(self, manual: bool = False) -> None:
        if self._checking or self._downloading:
            return
        if not updater.enabled():
            if manual:
                self.message.emit(f"Magic Converter {__version__} · update checks are not configured.")
            return
        if manual:
            self.message.emit("Checking for updates…")
        self._checking = True

        def work() -> None:
            try:
                self._bridge.found.emit(updater.check_for_update(), manual)
            except updater.UpdateError as exc:
                self._bridge.check_failed.emit(str(exc), manual)
            except Exception as exc:  # never crash the app because of an update check
                self._bridge.check_failed.emit(f"Update check failed: {exc}", manual)

        threading.Thread(target=work, daemon=True).start()

    def _on_found(self, info, manual: bool) -> None:
        self._checking = False
        if info is None:
            if manual:
                self.message.emit(f"You're up to date — version {__version__}.")
            return
        self._info = info
        self._action = "Update"
        self.title.setText(f"Version {info.version} is available")
        first_line = next((line.strip("-*# ").strip() for line in info.notes.splitlines()
                           if line.strip("-*# ").strip()), "")
        self.subtitle.setText(f"You have {__version__}." + (f"  What's new: {first_line}" if first_line else ""))
        self.setToolTip(info.notes[:1500] if info.notes else "")
        self._set_buttons("Later", "Update" if is_frozen() else "Open download page")
        self.progress.hide()
        self._reveal()

    def install_version(self, info: updater.UpdateInfo) -> None:
        """Download and install a version picked by the user, newer or older."""
        if self._checking or self._downloading:
            return
        self._info = info
        self._action = "Install"
        self.title.setText(f"Installing version {info.version}")
        self.subtitle.setText(f"You have {__version__}.")
        self.setToolTip("")
        self._set_buttons("Later", "Install")
        self.progress.hide()
        self._reveal()
        self.update_requested.emit()

    def _reveal(self) -> None:
        if not self.isVisible():
            self.show()
            fade_in(self)

    def _on_check_failed(self, message: str, manual: bool) -> None:
        self._checking = False
        if manual:
            self.message.emit(message)

    # --- Downloading & installing -------------------------------------------

    def _set_buttons(self, secondary: str, primary: str | None) -> None:
        self.secondary_btn.setText(secondary)
        self.secondary_btn.updateGeometry()
        self.primary_btn.setVisible(primary is not None)
        if primary:
            self.primary_btn.setText(primary)
            self.primary_btn.updateGeometry()

    def _on_primary(self) -> None:
        if not self._info:
            return
        if not is_frozen():
            # Running from source: there is no installed app to upgrade.
            QDesktopServices.openUrl(QUrl(self._info.page_url))
            return
        self.update_requested.emit()

    def start_download(self) -> None:
        info = self._info
        if not info or self._downloading:
            return
        self._downloading = True
        self._cancel.clear()
        self.subtitle.setText("Downloading…")
        self.progress.set_state("normal")
        self.progress.set_value(0, animate=False)
        self.progress.show()
        self._set_buttons("Cancel", None)

        def work() -> None:
            try:
                path = updater.download(info, self._bridge.progress.emit, self._cancel)
                self._bridge.downloaded.emit(str(path))
            except updater.UpdateCancelled:
                self._bridge.download_cancelled.emit()
            except updater.UpdateError as exc:
                self._bridge.download_failed.emit(str(exc))
            except Exception as exc:
                self._bridge.download_failed.emit(f"Download failed: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_secondary(self) -> None:
        if self._downloading:
            self._cancel.set()
        else:
            self.hide()

    def _on_progress(self, value: float) -> None:
        if value < 0:
            self.progress.set_indeterminate(True)
            return
        self.progress.set_value(value)
        size_mb = (self._info.size / 1_048_576) if self._info and self._info.size else 0
        self.subtitle.setText(f"Downloading… {round(value * 100)}%"
                              + (f" of {size_mb:.0f} MB" if size_mb else ""))

    def _on_downloaded(self, path: str) -> None:
        self._downloading = False
        self.progress.set_value(1.0)
        self.subtitle.setText("Installing… Magic Converter will restart in a moment.")
        self._set_buttons("", None)
        self.secondary_btn.hide()
        self.install_ready.emit(path)

    def _on_download_failed(self, message: str) -> None:
        self._downloading = False
        self.progress.set_state("error")
        self.subtitle.setText(message)
        self._set_buttons("Later", "Retry")

    def _on_download_cancelled(self) -> None:
        self._downloading = False
        self.progress.hide()
        self.subtitle.setText("Download cancelled.")
        self._set_buttons("Later", self._action)

    def is_downloading(self) -> bool:
        return self._downloading

    def cancel(self) -> None:
        self._cancel.set()
