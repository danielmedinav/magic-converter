"""Dialog for picking any published version to install (newer, older or the same)."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from .. import __version__, updater
from .widgets import AnimatedButton


class _Bridge(QObject):
    """Carries the release list from the worker thread back to the UI thread."""

    loaded = Signal(list)   # list[UpdateInfo]
    failed = Signal(str)


class VersionDialog(QDialog):
    """``selected`` holds the chosen release once the dialog is accepted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Install another version")
        self.setModal(True)
        self.setMinimumSize(520, 420)
        self.selected: updater.UpdateInfo | None = None
        self._releases: list[updater.UpdateInfo] = []
        self._bridge = _Bridge(self)
        self._bridge.loaded.connect(self._on_loaded)
        self._bridge.failed.connect(self._on_failed)

        title = QLabel("Choose a version")
        title.setObjectName("SectionTitle")
        sub = QLabel(f"You have version {__version__}. Your settings are kept whichever you pick.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)

        self.combo = QComboBox()
        self.combo.setEnabled(False)
        self.combo.currentIndexChanged.connect(self._on_selected)

        self.notes = QLabel("Loading versions…")
        self.notes.setObjectName("Muted")
        self.notes.setWordWrap(True)
        self.notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.notes.setOpenExternalLinks(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.notes)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 12, 16)
        cl.addWidget(scroll)

        self.warning = QLabel()
        self.warning.setObjectName("Small")
        self.warning.setWordWrap(True)
        self.warning.hide()

        self.retry_btn = AnimatedButton("Retry", "ghost")
        self.retry_btn.hide()
        self.retry_btn.clicked.connect(self._load)
        cancel = AnimatedButton("Cancel", "secondary")
        cancel.clicked.connect(self.reject)
        self.install_btn = AnimatedButton("Install", "primary")
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._install)

        buttons = QHBoxLayout()
        buttons.addWidget(self.retry_btn)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.install_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(4)
        layout.addWidget(self.combo)
        layout.addWidget(card, 1)
        layout.addWidget(self.warning)
        layout.addSpacing(6)
        layout.addLayout(buttons)

        self._load()

    # --- Loading ------------------------------------------------------------

    def _load(self) -> None:
        self.retry_btn.hide()
        self.notes.setTextFormat(Qt.TextFormat.PlainText)
        self.notes.setText("Loading versions…")

        def work() -> None:
            try:
                self._bridge.loaded.emit(updater.list_releases())
            except updater.UpdateError as exc:
                self._bridge.failed.emit(str(exc))
            except Exception as exc:  # never crash the app because of the version list
                self._bridge.failed.emit(f"Couldn't load the versions: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, releases: list) -> None:
        self._releases = releases
        if not releases:
            self.notes.setText("No versions are available to install right now.")
            return
        self.combo.blockSignals(True)
        self.combo.clear()
        for r in releases:
            label = r.version
            if r.version == __version__:
                label += "  (installed)"
            elif r is releases[0]:
                label += "  (latest)"
            if r.published:
                label += f"  ·  {r.published}"
            self.combo.addItem(label)
        self.combo.blockSignals(False)
        self.combo.setEnabled(True)
        # Start on the newest version that isn't the one already installed.
        start = next((i for i, r in enumerate(releases) if r.version != __version__), 0)
        self.combo.setCurrentIndex(start)
        self._on_selected(start)

    def _on_failed(self, message: str) -> None:
        self.notes.setText(message)
        self.retry_btn.show()

    # --- Selection ----------------------------------------------------------

    def _on_selected(self, index: int) -> None:
        if not 0 <= index < len(self._releases):
            return
        r = self._releases[index]
        self.notes.setTextFormat(Qt.TextFormat.MarkdownText)
        self.notes.setText(r.notes or "_No release notes for this version._")

        if updater.is_newer(__version__, r.version):
            self.warning.setText(
                f"{r.version} is older than the version you have. Older versions may not "
                "have this version list, so to come back later, download a newer installer "
                "from the Releases page.")
            self.warning.show()
        else:
            self.warning.hide()
        self.install_btn.setText("Reinstall" if r.version == __version__ else "Install")
        self.install_btn.updateGeometry()
        self.install_btn.setEnabled(True)

    def _install(self) -> None:
        index = self.combo.currentIndex()
        if 0 <= index < len(self._releases):
            self.selected = self._releases[index]
            self.accept()
