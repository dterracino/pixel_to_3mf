"""PySide6 editor for authoring stack-based relief manifests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import colorsys
import math
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QPointF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QCloseEvent,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
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
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import ConversionConfig
from .image_processor import PixelData
from .relief_workflow import filter_pixel_data_to_regions, prepare_relief_image
from .selection_outline import (
    MaskEdge,
    SelectionOutlineAnimator,
    pixel_selection_edges,
)
from .stack_manifest import (
    StackDefinition,
    apply_stack_manifest_settings,
    build_stack_manifest_data,
    load_stack_manifest,
    matching_color_pixels,
    validate_stack_manifest,
    write_stack_manifest,
)


class SelectionTool(Enum):
    FILL = "fill"
    MAGIC_WAND = "magic_wand"


class SelectionMode(Enum):
    REPLACE = "replace"
    ADD = "add"
    SUBTRACT = "subtract"


@dataclass(frozen=True)
class ImageViewSettings:
    """Non-destructive display controls for saved assignment masks."""

    show_assigned: bool = True
    show_unassigned: bool = True
    assigned_opacity: float = 1.0
    assigned_saturation: float = 1.0
    invert_assigned: bool = False


def _tool_icon(tool: SelectionTool) -> QIcon:
    """Create crisp dependency-free icons for the editor tools."""

    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(0, 135, 195), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if tool is SelectionTool.FILL:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(7, 13),
                    QPointF(16, 7),
                    QPointF(24, 15),
                    QPointF(15, 23),
                ]
            )
        )
        painter.drawLine(QPointF(10, 10), QPointF(20, 20))
        painter.drawLine(QPointF(6, 26), QPointF(25, 26))
        painter.setBrush(QColor(0, 190, 255))
        painter.drawEllipse(QPointF(25, 22), 2.5, 3.5)
    else:
        painter.drawLine(QPointF(8, 25), QPointF(22, 11))
        painter.drawLine(QPointF(7, 24), QPointF(10, 27))
        for start, end in (
            ((22, 4), (22, 9)),
            ((22, 15), (22, 20)),
            ((14, 12), (19, 12)),
            ((25, 12), (30, 12)),
            ((16, 6), (19, 9)),
            ((25, 15), (28, 18)),
            ((16, 18), (19, 15)),
            ((25, 9), (28, 6)),
        ):
            painter.drawLine(QPointF(*start), QPointF(*end))
    painter.end()
    return QIcon(pixmap)


def _parse_rgb(text: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 3:
        raise ValueError("RGB must contain three comma-separated values")
    result = tuple(int(part) for part in parts)
    if not all(0 <= channel <= 255 for channel in result):
        raise ValueError("RGB values must be between 0 and 255")
    return result[0], result[1], result[2]


def pixel_data_to_qimage(
    pixel_data: PixelData,
    assigned_pixels: set[tuple[int, int]] | frozenset[tuple[int, int]] = frozenset(),
    settings: ImageViewSettings = ImageViewSettings(),
) -> QImage:
    """Convert processed pixels to a filtered, top-left-origin display image."""

    image = QImage(pixel_data.width, pixel_data.height, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    for (x, model_y), rgba in pixel_data.pixels.items():
        assigned = (x, model_y) in assigned_pixels
        if (assigned and not settings.show_assigned) or (
            not assigned and not settings.show_unassigned
        ):
            continue
        red, green, blue = rgba[:3]
        alpha = rgba[3]
        if assigned:
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0, green / 255.0, blue / 255.0
            )
            red_f, green_f, blue_f = colorsys.hsv_to_rgb(
                hue,
                saturation * settings.assigned_saturation,
                value,
            )
            red, green, blue = (
                round(red_f * 255),
                round(green_f * 255),
                round(blue_f * 255),
            )
            if settings.invert_assigned:
                red, green, blue = 255 - red, 255 - green, 255 - blue
            alpha = round(alpha * settings.assigned_opacity)
        image.setPixelColor(
            x,
            pixel_data.height - 1 - model_y,
            QColor(red, green, blue, alpha),
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
        self._selection_edges: list[MaskEdge] = []
        self._selection_outline = SelectionOutlineAnimator(self)
        self._selection_outline.frame_changed.connect(self.viewport().update)

    def set_image_view(
        self,
        assigned_pixels: set[tuple[int, int]] | frozenset[tuple[int, int]],
        settings: ImageViewSettings,
    ) -> None:
        image = pixel_data_to_qimage(self.pixel_data, assigned_pixels, settings)
        self._image_item.setPixmap(QPixmap.fromImage(image))

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
        self._selection_edges = pixel_selection_edges(pixels, self.pixel_data.height)
        self._selection_outline.set_active(bool(self._selection_edges))
        self.viewport().update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        if not self._selection_edges:
            return
        origin = self.mapFromScene(QPointF(0.0, 0.0))
        painter = QPainter(self.viewport())
        self._selection_outline.draw(
            painter,
            self._selection_edges,
            origin_x=float(origin.x()),
            origin_y=float(origin.y()),
            zoom=self.transform().m11(),
        )
        painter.end()

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
        self.active_tool = SelectionTool.FILL
        self.selection_mode = SelectionMode.REPLACE
        self.view_settings = ImageViewSettings()
        self.dirty = False

        self.setWindowTitle(f"Stack Manifest Editor — {source_path.name}")
        self.resize(1180, 760)
        self.canvas = ImageCanvas(pixel_data)
        self.canvas.pixel_clicked.connect(self._select_at)

        self.fill_button = self._tool_button(SelectionTool.FILL, "Fill")
        self.magic_wand_button = self._tool_button(
            SelectionTool.MAGIC_WAND, "Magic Wand"
        )
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_group.addButton(self.fill_button)
        self.tool_group.addButton(self.magic_wand_button)
        self.fill_button.setChecked(True)
        self.fill_button.clicked.connect(
            lambda: self._set_tool(SelectionTool.FILL)
        )
        self.magic_wand_button.clicked.connect(
            lambda: self._set_tool(SelectionTool.MAGIC_WAND)
        )
        tool_row = QHBoxLayout()
        tool_row.addWidget(self.fill_button)
        tool_row.addWidget(self.magic_wand_button)
        tool_row.addStretch()

        fill_options = QLabel("Selects one exact-color, 4-connected area.")
        fill_options.setWordWrap(True)
        self.magic_wand_contiguous = QCheckBox("Contiguous")
        self.magic_wand_contiguous.setChecked(True)
        wand_options = QWidget()
        wand_options_layout = QVBoxLayout(wand_options)
        wand_options_layout.setContentsMargins(0, 0, 0, 0)
        wand_options_layout.addWidget(self.magic_wand_contiguous)
        wand_options_layout.addWidget(
            QLabel("Uncheck to select every matching RGB in the image.")
        )
        self.tool_options = QStackedWidget()
        self.tool_options.addWidget(fill_options)
        self.tool_options.addWidget(wand_options)
        options_group = QGroupBox("Tool options")
        options_layout = QVBoxLayout(options_group)
        options_layout.addWidget(self.tool_options)

        self.replace_mode_button = self._selection_mode_button("Replace")
        self.add_mode_button = self._selection_mode_button("Add")
        self.subtract_mode_button = self._selection_mode_button("Subtract")
        self.selection_mode_group = QButtonGroup(self)
        self.selection_mode_group.setExclusive(True)
        for button in (
            self.replace_mode_button,
            self.add_mode_button,
            self.subtract_mode_button,
        ):
            self.selection_mode_group.addButton(button)
        self.replace_mode_button.setChecked(True)
        self.replace_mode_button.clicked.connect(
            lambda: self._set_selection_mode(SelectionMode.REPLACE)
        )
        self.add_mode_button.clicked.connect(
            lambda: self._set_selection_mode(SelectionMode.ADD)
        )
        self.subtract_mode_button.clicked.connect(
            lambda: self._set_selection_mode(SelectionMode.SUBTRACT)
        )
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.replace_mode_button)
        mode_row.addWidget(self.add_mode_button)
        mode_row.addWidget(self.subtract_mode_button)
        mode_group = QGroupBox("Selection mode")
        mode_group.setLayout(mode_row)

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
        preview_button = QPushButton("Render Preview")
        save_button = QPushButton("Save Manifest")
        close_button = QPushButton("Close")
        new_button.clicked.connect(self._new_stack)
        save_stack_button.clicked.connect(self._save_stack)
        delete_button.clicked.connect(self._delete_stack)
        clear_button.clicked.connect(self._clear_selection)
        preview_button.clicked.connect(self.show_render_preview)
        save_button.clicked.connect(self.save_manifest)
        close_button.clicked.connect(self.close)
        self.background_edit.editingFinished.connect(self._global_settings_changed)
        self.backing_edit.editingFinished.connect(self._global_settings_changed)
        self.backing_height.valueChanged.connect(self._mark_dirty)

        stack_buttons = QHBoxLayout()
        stack_buttons.addWidget(new_button)
        stack_buttons.addWidget(delete_button)
        right = QVBoxLayout()
        right.addWidget(QLabel("Selection tool"))
        right.addLayout(tool_row)
        right.addWidget(options_group)
        right.addWidget(mode_group)
        right.addWidget(QLabel("Stacks"))
        right.addWidget(self.stack_list, 1)
        right.addLayout(stack_buttons)
        right.addLayout(form)
        right.addWidget(save_stack_button)
        right.addWidget(clear_button)
        right.addWidget(self.status_label)
        right.addWidget(preview_button)
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
        self._create_menus()
        self.statusBar().showMessage(
            "Click: replace selection   Shift-click: add selection   "
            "Alt-click: remove selection   "
            "Mouse wheel: zoom   Middle-drag: pan"
        )
        self._refresh_stack_list()
        if self.stacks:
            self.stack_list.setCurrentRow(0)
        else:
            self._new_stack()
            self.dirty = False
        self._update_status()
        self._refresh_image_view()

    @staticmethod
    def _height_spinbox(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setDecimals(3)
        control.setRange(0.001, 1000.0)
        control.setSingleStep(0.25)
        control.setValue(max(0.001, value))
        return control

    @staticmethod
    def _tool_button(tool: SelectionTool, text: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setIcon(_tool_icon(tool))
        button.setIconSize(QSize(28, 28))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setCheckable(True)
        button.setMinimumWidth(76)
        return button

    @staticmethod
    def _selection_mode_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        return button

    def _set_tool(self, tool: SelectionTool) -> None:
        self.active_tool = tool
        self.tool_options.setCurrentIndex(
            0 if tool is SelectionTool.FILL else 1
        )
        self.statusBar().showMessage(
            "Fill selects one connected area. Magic Wand can select connected "
            "or all matching pixels.",
            5000,
        )

    def _set_selection_mode(self, mode: SelectionMode) -> None:
        self.selection_mode = mode
        buttons = {
            SelectionMode.REPLACE: self.replace_mode_button,
            SelectionMode.ADD: self.add_mode_button,
            SelectionMode.SUBTRACT: self.subtract_mode_button,
        }
        buttons[mode].setChecked(True)
        self.statusBar().showMessage(
            f"Selection mode: {mode.value}. Shift temporarily adds; Alt temporarily subtracts.",
            5000,
        )

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        save_action = QAction("&Save Manifest", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_manifest)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        close_action = QAction("&Close", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        view_menu = self.menuBar().addMenu("&View")
        self.show_assigned_action = QAction("Assigned", self)
        self.show_assigned_action.setCheckable(True)
        self.show_assigned_action.setChecked(True)
        self.show_assigned_action.toggled.connect(self._view_visibility_changed)
        view_menu.addAction(self.show_assigned_action)

        self.show_unassigned_action = QAction("Unassigned", self)
        self.show_unassigned_action.setCheckable(True)
        self.show_unassigned_action.setChecked(True)
        self.show_unassigned_action.toggled.connect(self._view_visibility_changed)
        view_menu.addAction(self.show_unassigned_action)
        view_menu.addSeparator()

        opacity_menu = view_menu.addMenu("Assigned Opacity")
        self.opacity_group = QActionGroup(self)
        self.opacity_group.setExclusive(True)
        for label, value in (("25%", 0.25), ("50%", 0.5), ("75%", 0.75), ("100%", 1.0)):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(value == 1.0)
            action.triggered.connect(
                lambda _checked=False, opacity=value: self._set_assigned_opacity(opacity)
            )
            self.opacity_group.addAction(action)
            opacity_menu.addAction(action)

        saturation_menu = view_menu.addMenu("Assigned Saturation")
        self.saturation_group = QActionGroup(self)
        self.saturation_group.setExclusive(True)
        for label, value in (
            ("Grayscale", 0.0),
            ("25%", 0.25),
            ("50%", 0.5),
            ("100%", 1.0),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(value == 1.0)
            action.triggered.connect(
                lambda _checked=False, saturation=value: self._set_assigned_saturation(
                    saturation
                )
            )
            self.saturation_group.addAction(action)
            saturation_menu.addAction(action)

        self.invert_assigned_action = QAction("Invert Assigned", self)
        self.invert_assigned_action.setCheckable(True)
        self.invert_assigned_action.toggled.connect(self._invert_assigned_changed)
        view_menu.addAction(self.invert_assigned_action)

        preview_menu = self.menuBar().addMenu("&Preview")
        render_action = QAction("&Render 3D Preview", self)
        render_action.setShortcut("Ctrl+R")
        render_action.triggered.connect(self.show_render_preview)
        preview_menu.addAction(render_action)

    def _view_visibility_changed(self, _checked: bool = False) -> None:
        self.view_settings = replace(
            self.view_settings,
            show_assigned=self.show_assigned_action.isChecked(),
            show_unassigned=self.show_unassigned_action.isChecked(),
        )
        self._refresh_image_view()

    def _set_assigned_opacity(self, opacity: float) -> None:
        self.view_settings = replace(self.view_settings, assigned_opacity=opacity)
        self._refresh_image_view()

    def _set_assigned_saturation(self, saturation: float) -> None:
        self.view_settings = replace(
            self.view_settings, assigned_saturation=saturation
        )
        self._refresh_image_view()

    def _invert_assigned_changed(self, checked: bool) -> None:
        self.view_settings = replace(self.view_settings, invert_assigned=checked)
        self._refresh_image_view()

    def _assigned_pixels(self) -> set[tuple[int, int]]:
        return {
            coordinate
            for stack in self.stacks
            for coordinate in stack.pixels
        }

    def _refresh_image_view(self) -> None:
        self.canvas.set_image_view(self._assigned_pixels(), self.view_settings)

    def show_render_preview(self) -> None:
        error: Exception | None = None
        colored_meshes = []
        cursor_set = False
        try:
            self._sync_global_settings()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            cursor_set = True
            from .stack_preview import build_stack_preview_meshes

            colored_meshes = build_stack_preview_meshes(
                self.source_path,
                self.pixel_data,
                self.config,
                self.stacks,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            error = exc
        finally:
            if cursor_set:
                QApplication.restoreOverrideCursor()

        if error is not None:
            QMessageBox.critical(self, "Could not render preview", str(error))
            return

        from .stack_preview_widget import InteractivePreviewDialog

        dialog = InteractivePreviewDialog(colored_meshes, self)
        dialog.exec()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if not getattr(self, "_did_fit", False):
            self.canvas.fit_image()
            self._did_fit = True

    def _select_at(self, x: int, model_y: int, modifiers: object) -> None:
        contiguous = (
            self.active_tool is SelectionTool.FILL
            or self.magic_wand_contiguous.isChecked()
        )
        matched = set(
            matching_color_pixels(
                self.pixel_data,
                (x, model_y),
                contiguous=contiguous,
            )
        )
        if not matched:
            return
        if not isinstance(modifiers, Qt.KeyboardModifier):
            return
        keyboard_modifiers = modifiers
        mode = self.selection_mode
        if keyboard_modifiers & Qt.KeyboardModifier.AltModifier:
            mode = SelectionMode.SUBTRACT
        elif keyboard_modifiers & Qt.KeyboardModifier.ShiftModifier:
            mode = SelectionMode.ADD
        if mode is SelectionMode.SUBTRACT:
            self.selection.difference_update(matched)
        elif mode is SelectionMode.ADD:
            self.selection.update(matched)
        else:
            self.selection = matched
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
        self._set_selection_mode(SelectionMode.ADD)
        self.canvas.set_selection(self.selection)
        self._update_status()

    def _new_stack(self) -> None:
        self.stack_list.clearSelection()
        self.stack_list.setCurrentRow(-1)
        self.editing_stack_id = None
        self._set_selection_mode(SelectionMode.REPLACE)
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
        self._refresh_image_view()
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
        self._refresh_image_view()
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
    *,
    resume: bool,
) -> tuple[PixelData, list[StackDefinition]]:
    """Replay an existing draft or initialize an explicitly new project."""

    data = None
    if resume:
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest does not exist: {manifest_path}")
        data = load_stack_manifest(manifest_path)
        source = data.get("source")
        expected = source.get("sha256") if isinstance(source, dict) else None
        if expected and sha256(source_path.read_bytes()).hexdigest() != expected:
            raise ValueError("Manifest source SHA-256 does not match the selected image")
        apply_stack_manifest_settings(data, config)
    elif manifest_path.exists():
        raise FileExistsError(
            f"Manifest already exists: {manifest_path}. Resume it instead of creating it."
        )
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
    *,
    resume: bool,
) -> int:
    """Launch the editor and return the Qt application exit code."""

    source = Path(source_path)
    output = Path(manifest_path)
    pixels, stacks = load_stack_editor_state(
        source, output, config, resume=resume
    )
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])
    window = StackEditorWindow(source, output, pixels, config, stacks)
    window.show()
    if owns_app:
        return app.exec()
    return 0
