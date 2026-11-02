"""Application bootstrap."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, __version__
from .paths import resource, user_data_dir
from .settings import load_settings


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(user_data_dir() / "app.log", encoding="utf-8", mode="w")],
    )


def run() -> int:
    _setup_logging()
    if sys.platform == "win32":
        # Own taskbar identity so Windows shows our icon instead of python.exe's.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.App")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setStyle("Fusion")

    families = set(QFontDatabase.families())
    family = next((f for f in ("Segoe UI Variable Text", "Segoe UI", "Inter") if f in families),
                  app.font().family())
    app.setFont(QFont(family, 10))

    icon = resource("icon.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    # Imported after QApplication exists (widgets need it).
    from .ui import theme
    from .ui.main_window import MainWindow

    settings = load_settings()
    theme.init(app, settings.theme)
    window = MainWindow(settings)
    window.show()

    # Files passed on the command line (e.g. "Open with" or dropped on the .exe).
    args = [Path(a) for a in sys.argv[1:] if Path(a).exists()]
    if args:
        window.add_paths(args)

    return app.exec()
