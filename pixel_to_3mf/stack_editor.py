"""PySide6 editor for authoring stack-based relief manifests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import math
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .config import ConversionConfig
from .image_processor import PixelData
from .relief_workflow import filter_pixel_data_to_regions, prepare_relief_image
from .stack_manifest import (
    StackDefinition,
    apply_stack_manifest_settings,
    build_stack_manifest_data,
    connected_color_component,
    load_stack_manifest,
    validate_stack_manifest,
    write_stack_manifest,
)


def _parse_rgb(text: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 3:
        raise ValueError("RGB must contain three comma-separated values")
    result = tuple(int(part) for part in parts)
    if not all(0 <= channel <= 255 for channel in result):
        raise ValueError("RGB values must be between 0 and 255")
    return result[0], result[1], result[2]


def pixel_data_to_qimage(pixel_data: PixelData) -> QImage:
    """Convert bottom-left-origin processed pixels to a top-left QImage."""

    image = QImage(pixel_data.width, pixel_data.height, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    for (x, model_y), rgba in pixel_data.pixels.items():
        image.setPixelColor(
            x,
            pixel_data.height - 1 - model_y,
            QColor(rgba[0], rgba[1], rgba[2], rgba[3]),
        )
    return image


class ImageCanvas(QGraphicsView):
    """Nearest-neighbor image view with cursor-anchored zoom and middle pan."""

    pixel_clicked = Signal(int, int, object)

    def __init__(self, pixel_data: PixelData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pixel_data = pixel_data
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._image_item = QGraphicsPixmapItem(QPixmap.fromImage(pixel_data_to_qimage(pixel_data)))
        self._image_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self._overlay_item = QGraphicsPixmapItem()
        self._overlay_item.setZValue(1)
        self._scene.addItem(self._image_item)
        self._scene.addItem(self._overlay_item)
        self._scene.setSceneRect(0, 0, pixel_data.width, pixel_data.height)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor(32, 32, 32))
        self._panning = False
        self._pan_origin = QPoint()

    def set_selection(self, pixels: set[tuple[int, int]] | frozenset[tuple[int, int]]) -> None:
        overlay = QImage(
            self.pixel_data.width,
            self.pixel_data.height,
            QImage.Format.Format_RGBA8888,
        )
        overlay.fill(Qt.GlobalColor.transparent)
        selected = QColor(0, 190, 255, 125)
        for x, model_y in pixels:
            overlay.setPixelColor(x, self.pixel_data.height - 1 - model_y, selected)
        self._overlay_item.setPixmap(QPixmap.fromImage(overlay))

    def fit_image(self) -> None:
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        current = self.transform().m11()
        target = current * factor
        if 0.05 <= target <= 128:
            self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            scene_point = self.mapToScene(event.position().toPoint())
            x = math.floor(scene_point.x())
            top_y = math.floor(scene_point.y())
            if 0 <= x < self.pixel_data.width and 0 <= top_y < self.pixel_data.height:
                model_y = self.pixel_data.height - 1 - top_y
                self.pixel_clicked.emit(x, model_y, event.modifiers())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._panning:
            position = event.position().toPoint()
            delta = position - self._pan_origin
            self._pan_origin = position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class StackEditorWindow(QMainWindow):
    """Author named stack selections without embedding geometry logic in Qt."""

    def __init__(
        self,
        source_path: Path,
        manifest_path: Path,
        pixel_data: PixelData,
        config: ConversionConfig,
        stacks: list[StackDefinition] | None = None,
    ) -> None:
        super().__init__()
        self.source_path = source_path
        self.manifest_path = manifest_path
        self.pixel_data = pixel_data
        self.config = config
        self.stacks = list(stacks or [])
        self.selection: set[tuple[int, int]] = set()
        self.editing_stack_id: str | None = None
        self.dirty = False

        self.setWindowTitle(f"Stack Manifest Editor — {source_path.name}")
        self.resize(1180, 760)
        self.canvas = ImageCanvas(pixel_data)
        self.canvas.pixel_clicked.connect(self._fill_clicked)

        self.stack_list = QListWidget()
        self.stack_list.currentItemChanged.connect(self._stack_selected)
        self.name_edit = QLineEdit()
        self.stack_height = self._height_spinbox(3.0)
        self.color_height = self._height_spinbox(1.0)
        self.background_edit = QLineEdit(",".join(map(str, config.relief_background_color)))
        self.backing_edit = QLineEdit(",".join(map(str, config.backing_color)))
        self.backing_height = self._height_spinbox(config.base_height_mm)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Stack name", self.name_edit)
        form.addRow("Stack height (mm)", self.stack_height)
        form.addRow("Color height (mm)", self.color_height)
        form.addRow("Background RGB", self.background_edit)
        form.addRow("Backing RGB", self.backing_edit)
        form.addRow("Backing height (mm)", self.backing_height)

        new_button = QPushButton("New Stack")
        save_stack_button = QPushButton("Add / Update Stack")
        delete_button = QPushButton("Delete Stack")
        clear_button = QPushButton("Clear Selection")
        save_button = QPushButton("Save Manifest")
        close_button = QPushButton("Close")
        new_button.clicked.connect(self._new_stack)
        save_stack_button.clicked.connect(self._save_stack)
        delete_button.clicked.connect(self._delete_stack)
        clear_button.clicked.connect(self._clear_selection)
        save_button.clicked.connect(self.save_manifest)
        close_button.clicked.connect(self.close)
        self.background_edit.editingFinished.connect(self._global_settings_changed)
        self.backing_edit.editingFinished.connect(self._global_settings_changed)
        self.backing_height.valueChanged.connect(self._mark_dirty)

        stack_buttons = QHBoxLayout()
        stack_buttons.addWidget(new_button)
        stack_buttons.addWidget(delete_button)
        right = QVBoxLayout()
        right.addWidget(QLabel("Stacks"))
        right.addWidget(self.stack_list, 1)
        right.addLayout(stack_buttons)
        right.addLayout(form)
        right.addWidget(save_stack_button)
        right.addWidget(clear_button)
        right.addWidget(self.status_label)
        right.addStretch()
        bottom = QHBoxLayout()
        bottom.addWidget(save_button)
        bottom.addWidget(close_button)
        right.addLayout(bottom)
        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setMinimumWidth(330)
        right_widget.setMaximumWidth(440)

        splitter = QSplitter()
        splitter.addWidget(self.canvas)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(
            "Click: replace selection   Shift-click: add fill   Alt-click: remove fill   "
            "Mouse wheel: zoom   Middle-drag: pan"
        )
        self._refresh_stack_list()
        if self.stacks:
            self.stack_list.setCurrentRow(0)
        else:
            self._new_stack()
            self.dirty = False
        self._update_status()

    @staticmethod
    def _height_spinbox(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setDecimals(3)
        control.setRange(0.001, 1000.0)
        control.setSingleStep(0.25)
        control.setValue(max(0.001, value))
        return control

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if not getattr(self, "_did_fit", False):
            self.canvas.fit_image()
            self._did_fit = True

    def _fill_clicked(self, x: int, model_y: int, modifiers: object) -> None:
        component = set(connected_color_component(self.pixel_data, (x, model_y)))
        if not component:
            return
        if not isinstance(modifiers, Qt.KeyboardModifier):
            return
        keyboard_modifiers = modifiers
        if keyboard_modifiers & Qt.KeyboardModifier.AltModifier:
            self.selection.difference_update(component)
        elif keyboard_modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.selection.update(component)
        else:
            self.selection = component
        self.canvas.set_selection(self.selection)
        self._update_status()

    def _stack_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        stack_id = current.data(Qt.ItemDataRole.UserRole)
        stack = next((item for item in self.stacks if item.stack_id == stack_id), None)
        if stack is None:
            return
        self.editing_stack_id = stack.stack_id
        self.selection = set(stack.pixels)
        self.name_edit.setText(stack.name)
        self.stack_height.setValue(stack.stack_height_mm)
        self.color_height.setValue(stack.color_height_mm)
        self.canvas.set_selection(self.selection)
        self._update_status()

    def _new_stack(self) -> None:
        self.stack_list.clearSelection()
        self.stack_list.setCurrentRow(-1)
        self.editing_stack_id = None
        self.selection.clear()
        self.name_edit.setText(f"Stack {self._next_stack_number():02d}")
        self.stack_height.setValue(1.0)
        self.color_height.setValue(1.0)
        self.canvas.set_selection(self.selection)
        self._update_status()

    def _next_stack_number(self) -> int:
        used = {
            int(stack.stack_id.removeprefix("stack_"))
            for stack in self.stacks
            if stack.stack_id.removeprefix("stack_").isdigit()
        }
        number = 1
        while number in used:
            number += 1
        return number

    def _save_stack(self) -> None:
        if not self.selection:
            QMessageBox.warning(self, "No selection", "Select at least one image area first.")
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter a name for this stack.")
            return
        total = self.stack_height.value()
        color = self.color_height.value()
        if color > total:
            QMessageBox.warning(
                self,
                "Invalid heights",
                "Color height must not exceed the total stack height.",
            )
            return
        stack_id = self.editing_stack_id
        if stack_id is None:
            stack_id = f"stack_{self._next_stack_number():02d}"

        selected = frozenset(self.selection)
        updated: list[StackDefinition] = []
        for stack in self.stacks:
            if stack.stack_id == stack_id:
                continue
            remaining = stack.pixels - selected
            if remaining:
                updated.append(replace(stack, pixels=remaining))
        updated.append(StackDefinition(stack_id, name, selected, total, color))
        self.stacks = updated
        self.editing_stack_id = stack_id
        self.dirty = True
        self._refresh_stack_list(select_id=stack_id)
        self._update_status()

    def _delete_stack(self) -> None:
        if self.editing_stack_id is None:
            return
        self.stacks = [
            stack for stack in self.stacks if stack.stack_id != self.editing_stack_id
        ]
        self.editing_stack_id = None
        self.selection.clear()
        self.canvas.set_selection(self.selection)
        self.dirty = True
        self._refresh_stack_list()
        self._update_status()

    def _clear_selection(self) -> None:
        self.selection.clear()
        self.canvas.set_selection(self.selection)
        self._update_status()

    def _refresh_stack_list(self, select_id: str | None = None) -> None:
        self.stack_list.blockSignals(True)
        self.stack_list.clear()
        selected_item: QListWidgetItem | None = None
        for stack in self.stacks:
            item = QListWidgetItem(
                f"{stack.name}  —  {stack.stack_height_mm:g}mm / "
                f"{stack.color_height_mm:g}mm color  —  {len(stack.pixels)} px"
            )
            item.setData(Qt.ItemDataRole.UserRole, stack.stack_id)
            self.stack_list.addItem(item)
            if stack.stack_id == select_id:
                selected_item = item
        self.stack_list.blockSignals(False)
        if selected_item is not None:
            self.stack_list.setCurrentItem(selected_item)

    def _current_background(self) -> tuple[int, int, int]:
        try:
            return _parse_rgb(self.background_edit.text())
        except ValueError:
            return self.config.relief_background_color

    def _update_status(self) -> None:
        owned = set().union(*(stack.pixels for stack in self.stacks)) if self.stacks else set()
        background = self._current_background()
        required = {
            coordinate
            for coordinate, rgba in self.pixel_data.pixels.items()
            if rgba[:3] != background
        }
        unassigned = required - owned
        self.status_label.setText(
            f"Current selection: {len(self.selection)} pixel(s)\n"
            f"Saved stacks: {len(self.stacks)}\n"
            f"Unassigned non-background pixels: {len(unassigned)}"
        )

    def _global_settings_changed(self) -> None:
        try:
            _parse_rgb(self.background_edit.text())
            _parse_rgb(self.backing_edit.text())
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 5000)
            return
        self._mark_dirty()
        self._update_status()

    def _mark_dirty(self, *_args) -> None:
        self.dirty = True

    def _sync_global_settings(self) -> None:
        self.config.relief_background_color = _parse_rgb(self.background_edit.text())
        self.config.backing_color = _parse_rgb(self.backing_edit.text())
        self.config.base_height_mm = self.backing_height.value()

    def save_manifest(self) -> bool:
        try:
            self._sync_global_settings()
            data = build_stack_manifest_data(
                self.source_path, self.pixel_data, self.config, self.stacks
            )
            _, errors, warnings = validate_stack_manifest(
                data, self.pixel_data, require_complete=False
            )
            if errors:
                raise ValueError("; ".join(errors))
            write_stack_manifest(self.manifest_path, data)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not save manifest", str(exc))
            return False
        self.dirty = False
        message = f"Saved {self.manifest_path}"
        if warnings:
            message += f" — {warnings[0]}"
        self.statusBar().showMessage(message, 8000)
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if not self.dirty:
            event.accept()
            return
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            if self.save_manifest():
                event.accept()
            else:
                event.ignore()
        elif answer == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()


def load_stack_editor_state(
    source_path: Path,
    manifest_path: Path,
    config: ConversionConfig,
) -> tuple[PixelData, list[StackDefinition]]:
    """Replay an existing draft or initialize an empty editor project."""

    data = None
    if manifest_path.exists():
        data = load_stack_manifest(manifest_path)
        source = data.get("source")
        expected = source.get("sha256") if isinstance(source, dict) else None
        if expected and sha256(source_path.read_bytes()).hexdigest() != expected:
            raise ValueError("Manifest source SHA-256 does not match the selected image")
        apply_stack_manifest_settings(data, config)
    pixels, regions = prepare_relief_image(source_path, config)
    pixels = filter_pixel_data_to_regions(pixels, regions)
    if data is None:
        return pixels, []
    manifest, errors, _ = validate_stack_manifest(data, pixels, require_complete=False)
    if errors or manifest is None:
        raise ValueError("Invalid stack manifest: " + "; ".join(errors))
    return pixels, list(manifest.stacks)


def launch_stack_editor(
    source_path: str | Path,
    manifest_path: str | Path,
    config: ConversionConfig,
) -> int:
    """Launch the editor and return the Qt application exit code."""

    source = Path(source_path)
    output = Path(manifest_path)
    pixels, stacks = load_stack_editor_state(source, output, config)
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])
    window = StackEditorWindow(source, output, pixels, config, stacks)
    window.show()
    if owns_app:
        return app.exec()
    return 0
