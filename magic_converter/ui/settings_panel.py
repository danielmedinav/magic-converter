"""Global quality/size settings and the output folder.

Output *format* is chosen per file on each queue card; everything here applies to
all images (Image tab) or all videos (Video tab).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QRadioButton, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.formats import VIDEO_PRESETS, VIDEO_RESOLUTIONS
from ..core.models import ImageOptions, ResizeOptions, VideoOptions
from ..settings import AppSettings
from .widgets import AnimatedButton, SegmentedControl, Separator


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("FieldLabel")
    lbl.setMinimumWidth(78)
    return lbl


def _spin(minimum: int, maximum: int, suffix: str = "", special: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(minimum, maximum)
    s.setSuffix(suffix)
    s.setAlignment(Qt.AlignmentFlag.AlignCenter)
    s.setFixedWidth(84)
    s.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    if special:
        s.setSpecialValueText(special)
    return s


class ImageSettingsForm(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(1, 100)
        self.quality.setToolTip("Used by JPG, WEBP and AVIF. Lossless formats "
                                "(PNG, BMP, TIFF, GIF, ICO) ignore it.")
        self.quality_value = QLabel("90")
        self.quality_value.setFixedWidth(30)
        self.quality_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.resize_off = QRadioButton("Off")
        self.resize_percent = QRadioButton("Percentage")
        self.resize_size = QRadioButton("Width × Height")
        self._resize_group = QButtonGroup(self)
        for i, b in enumerate((self.resize_off, self.resize_percent, self.resize_size)):
            self._resize_group.addButton(b, i)

        self.percent = _spin(1, 1000, " %")
        self.width = _spin(0, 20000, " px", "auto")
        self.height = _spin(0, 20000, " px", "auto")
        self.keep_aspect = QCheckBox("Keep aspect ratio")

        percent_page = QWidget()
        pl = QHBoxLayout(percent_page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(self.percent)
        pl.addStretch()

        size_page = QWidget()
        sl = QHBoxLayout(size_page)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        times = QLabel("×")
        times.setObjectName("Muted")
        sl.addWidget(self.width)
        sl.addWidget(times)
        sl.addWidget(self.height)
        sl.addSpacing(8)
        sl.addWidget(self.keep_aspect)
        sl.addStretch()

        self.resize_stack = QStackedWidget()
        self.resize_stack.addWidget(QWidget())
        self.resize_stack.addWidget(percent_page)
        self.resize_stack.addWidget(size_page)
        self.resize_stack.setFixedHeight(34)

        q_row = QHBoxLayout()
        q_row.setSpacing(10)
        q_row.addWidget(self.quality, 1)
        q_row.addWidget(self.quality_value)
        radios = QHBoxLayout()
        radios.setSpacing(18)
        for b in (self.resize_off, self.resize_percent, self.resize_size):
            radios.addWidget(b)
        radios.addSpacing(6)
        radios.addWidget(self.resize_stack, 1)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.addWidget(_field_label("Quality"), 0, 0)
        grid.addLayout(q_row, 0, 1)
        grid.addWidget(_field_label("Resize"), 1, 0)
        grid.addLayout(radios, 1, 1)
        grid.setColumnStretch(1, 1)

        self.quality.valueChanged.connect(self._on_change)
        self._resize_group.idClicked.connect(self._on_change)
        for w in (self.percent, self.width, self.height):
            w.valueChanged.connect(self._on_change)
        self.keep_aspect.toggled.connect(self._on_change)

        self.set_options(ImageOptions())

    def _on_change(self, *_):
        self._sync()
        self.changed.emit()

    def _sync(self) -> None:
        self.quality_value.setText(str(self.quality.value()))
        self.resize_stack.setCurrentIndex(max(0, self._resize_group.checkedId()))

    def get_options(self) -> ImageOptions:
        mode = ("none", "percent", "size")[max(0, self._resize_group.checkedId())]
        return ImageOptions(
            quality=self.quality.value(),
            resize=ResizeOptions(mode=mode, percent=self.percent.value(),
                                 width=self.width.value(), height=self.height.value(),
                                 keep_aspect=self.keep_aspect.isChecked()),
        )

    def set_options(self, o: ImageOptions) -> None:
        widgets = (self.quality, self.percent, self.width, self.height,
                   self.keep_aspect, self._resize_group)
        for w in widgets:
            w.blockSignals(True)
        self.quality.setValue(o.quality)
        {"none": self.resize_off, "percent": self.resize_percent,
         "size": self.resize_size}.get(o.resize.mode, self.resize_off).setChecked(True)
        self.percent.setValue(o.resize.percent)
        self.width.setValue(o.resize.width)
        self.height.setValue(o.resize.height)
        self.keep_aspect.setChecked(o.resize.keep_aspect)
        for w in widgets:
            w.blockSignals(False)
        self._sync()


PRESET_HINTS = {
    "Low": "Smallest files, noticeably lower quality. MP3: 128 kbps.",
    "Medium": "Balanced size and quality — good for most uses. MP3: 192 kbps.",
    "High": "Visually near-lossless, larger files. MP3: 256 kbps.",
    "Original": "Keeps the source quality; copies streams without re-encoding when possible. MP3: 320 kbps.",
}


class VideoSettingsForm(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resolution = QComboBox()
        self.resolution.addItems(VIDEO_RESOLUTIONS)
        self.resolution.setToolTip("Only ever scales down. Ignored for MP3.")
        self.preset = SegmentedControl(VIDEO_PRESETS)
        self.hint = QLabel()
        self.hint.setObjectName("Small")
        self.hint.setWordWrap(True)

        res_row = QHBoxLayout()
        res_row.addWidget(self.resolution)
        res_row.addStretch()
        preset_row = QHBoxLayout()
        preset_row.addWidget(self.preset)
        preset_row.addSpacing(12)
        preset_row.addWidget(self.hint, 1)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.addWidget(_field_label("Resolution"), 0, 0)
        grid.addLayout(res_row, 0, 1)
        grid.addWidget(_field_label("Quality"), 1, 0)
        grid.addLayout(preset_row, 1, 1)
        grid.setColumnStretch(1, 1)

        self.resolution.currentTextChanged.connect(self._on_change)
        self.preset.currentChanged.connect(self._on_change)
        self.set_options(VideoOptions())

    def _on_change(self, *_):
        self._sync()
        self.changed.emit()

    def _sync(self) -> None:
        self.hint.setText(PRESET_HINTS[self.preset.current_text()])

    def get_options(self) -> VideoOptions:
        return VideoOptions(resolution=self.resolution.currentText(),
                            preset=self.preset.current_text())

    def set_options(self, o: VideoOptions) -> None:
        for w in (self.resolution, self.preset):
            w.blockSignals(True)
        self.resolution.setCurrentText(o.resolution)
        self.preset.set_current_text(o.preset, animate=False)
        for w in (self.resolution, self.preset):
            w.blockSignals(False)
        self._sync()


class OutputSelector(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.same = QRadioButton("Same folder as source")
        self.custom = QRadioButton("")
        self.custom.setToolTip("Save to a custom folder")
        group = QButtonGroup(self)
        group.addButton(self.same)
        group.addButton(self.custom)
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setPlaceholderText("Choose a folder…")
        self.path.setMinimumWidth(220)
        self.browse = AnimatedButton("", "secondary", "folder-open")
        self.browse.setToolTip("Choose output folder")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_field_label("Output"))
        layout.addSpacing(6)
        layout.addWidget(self.same)
        layout.addSpacing(14)
        layout.addWidget(self.custom)
        layout.addWidget(self.path, 1)
        layout.addWidget(self.browse)

        self.same.toggled.connect(self._on_change)
        self.browse.clicked.connect(self.choose)
        self.custom.clicked.connect(self._custom_clicked)

    def _custom_clicked(self) -> None:
        if not self.path.text():
            self.choose()

    def choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.path.text())
        if folder:
            self.path.setText(folder)
            self.custom.setChecked(True)
        elif not self.path.text():
            self.same.setChecked(True)
        self._on_change()

    def _on_change(self, *_):
        self.path.setEnabled(self.custom.isChecked())
        self.changed.emit()

    def mode(self) -> str:
        return "custom" if self.custom.isChecked() and self.path.text() else "source"

    def set_values(self, mode: str, folder: str) -> None:
        self.blockSignals(True)
        self.path.setText(folder)
        (self.custom if mode == "custom" and folder else self.same).setChecked(True)
        self.path.setEnabled(self.custom.isChecked())
        self.blockSignals(False)


class SettingsPanel(QFrame):
    """Card at the bottom of the window: quality/size for all images or all videos."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.tabs = SegmentedControl(["Image", "Video"])
        self.image_form = ImageSettingsForm()
        self.video_form = VideoSettingsForm()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.image_form)
        self.stack.addWidget(self.video_form)
        self.output = OutputSelector()

        top = QHBoxLayout()
        top.addWidget(self.tabs)
        top.addStretch()
        self.tab_hint = QLabel()
        self.tab_hint.setObjectName("Small")
        top.addWidget(self.tab_hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        layout.addLayout(top)
        layout.addWidget(self.stack)
        layout.addWidget(Separator())
        layout.addWidget(self.output)

        self.tabs.currentChanged.connect(self._on_tab)
        for sig in (self.image_form.changed, self.video_form.changed, self.output.changed):
            sig.connect(self.changed)
        self._on_tab(0)

    def _on_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.tab_hint.setText(
            "Quality and size for all images · pick formats on each file above" if index == 0
            else "Quality and size for all videos · pick formats on each file above")
        self.changed.emit()

    def load(self, s: AppSettings) -> None:
        self.image_form.set_options(s.image)
        self.video_form.set_options(s.video)
        self.output.set_values(s.output_mode, s.output_dir)
        self.tabs.set_current_index(1 if s.active_tab == "video" else 0, animate=False)
        self.stack.setCurrentIndex(self.tabs.current_index())

    def store(self, s: AppSettings) -> None:
        s.image = self.image_form.get_options()
        s.video = self.video_form.get_options()
        s.output_mode = self.output.mode()
        s.output_dir = self.output.path.text()
        s.active_tab = "video" if self.tabs.current_index() == 1 else "image"

    def set_locked(self, locked: bool) -> None:
        for w in (self.image_form, self.video_form, self.output, self.tabs):
            w.setEnabled(not locked)
