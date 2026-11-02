# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Magic Converter (one-folder build, no console window).
#   python -m PyInstaller --noconfirm --clean MagicConverter.spec

from pathlib import Path

ROOT = Path(SPECPATH)
RES = ROOT / "resources"

for required in (RES / "icon.ico", RES / "ffmpeg" / "ffmpeg.exe", RES / "ffmpeg" / "ffprobe.exe"):
    if not required.exists():
        raise SystemExit(f"Missing {required}. Run scripts\\make_icon.py / scripts\\fetch_ffmpeg.ps1 first.")

datas = [
    (str(RES / "icon.ico"), "resources"),
    (str(RES / "icon.png"), "resources"),
    (str(RES / "ffmpeg" / "ffmpeg.exe"), "resources/ffmpeg"),
    (str(RES / "ffmpeg" / "ffprobe.exe"), "resources/ffmpeg"),
]
if (RES / "ffmpeg" / "LICENSE.txt").exists():
    datas.append((str(RES / "ffmpeg" / "LICENSE.txt"), "resources/ffmpeg"))

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["pillow_heif", "pillow_avif", "PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "pydoc", "test",
        "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia", "PySide6.Qt3DCore",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf",
        "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtOpenGL", "PySide6.QtBluetooth",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MagicConverter",
    icon=str(RES / "icon.ico"),
    console=False,
    debug=False,
    strip=False,
    upx=False,  # UPX-packed exes trigger antivirus false positives
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MagicConverter",
)
