"""Interactive Qt/ModernGL view of finalized stack-relief triangle meshes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

import moderngl
import numpy as np
from numpy.typing import NDArray
from preview_renderer import (
    DirectionalLight,
    OrbitCamera,
    PreviewInteraction,
    RenderMaterial,
    RenderMesh,
    RenderSettings,
    SceneBounds,
    load_triangle_shaders,
    material_batches,
    scene_bounds,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QMouseEvent, QSurfaceFormat, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .mesh import Mesh

RGB = tuple[int, int, int]
ColoredMesh = tuple[Mesh, RGB]


class InteractiveMeshPreview(QOpenGLWidget):
    """Render arbitrary colored meshes with shared camera/light interaction."""

    def __init__(
        self,
        colored_meshes: Sequence[ColoredMesh],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        surface_format = QSurfaceFormat()
        surface_format.setVersion(3, 3)
        surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        surface_format.setDepthBufferSize(24)
        surface_format.setSamples(4)
        self.setFormat(surface_format)
        self.setMinimumSize(640, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._settings = RenderSettings()
        self._scene = [
            RenderMesh(mesh=mesh, material=RenderMaterial(color=color))
            for mesh, color in colored_meshes
        ]
        bounds = scene_bounds(self._scene) or SceneBounds(
            (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
        )
        self._camera = OrbitCamera(
            bounds,
            yaw_degrees=self._settings.camera_azimuth_degrees,
            pitch_degrees=self._settings.camera_elevation_degrees,
        )
        self._light = DirectionalLight()
        self._interaction = PreviewInteraction(self._camera, self._light)
        self._prepared_batches = material_batches(self._scene)
        self._context: moderngl.Context | None = None
        self._program: moderngl.Program | None = None
        self._resources: list[
            tuple[moderngl.Buffer, moderngl.VertexArray, RGB, float]
        ] = []

    @property
    def camera_position(self) -> tuple[float, float, float]:
        return self._camera.position

    @property
    def light_direction(self) -> tuple[float, float, float]:
        return self._light.direction

    def view_projection(self, aspect: float) -> NDArray[np.float32]:
        return self._camera.view_projection(aspect)

    def reset_view(self) -> None:
        self._interaction.reset()
        self.update()

    def initializeGL(self) -> None:  # noqa: N802 - Qt override
        context = moderngl.create_context(require=330)
        vertex_shader, fragment_shader = load_triangle_shaders()
        program = context.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader,
        )
        create_vertex_array = cast(
            "Callable[..., moderngl.VertexArray]",
            getattr(context, "vertex_array"),
        )
        resources: list[
            tuple[moderngl.Buffer, moderngl.VertexArray, RGB, float]
        ] = []
        for (color, finish), vertex_data in self._prepared_batches:
            vertex_buffer = context.buffer(vertex_data.tobytes())
            vertex_array = create_vertex_array(
                program,
                [(vertex_buffer, "3f 3f", "in_position", "in_normal")],
            )
            resources.append((vertex_buffer, vertex_array, color, finish))
        context.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        context.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._context = context
        self._program = program
        self._resources = resources

    def paintGL(self) -> None:  # noqa: N802 - Qt override
        if self._context is None or self._program is None:
            return
        framebuffer = self._context.detect_framebuffer(
            self.defaultFramebufferObject()
        )
        framebuffer.use()
        scale = self.devicePixelRatioF()
        self._context.viewport = (
            0,
            0,
            max(1, round(self.width() * scale)),
            max(1, round(self.height() * scale)),
        )
        self._context.clear(0.065, 0.07, 0.085, 1.0, depth=1.0)
        if not self._resources:
            return
        aspect = self.width() / max(1, self.height())
        _uniform(self._program, "view_projection").write(
            self._camera.view_projection(aspect).tobytes(order="F")
        )
        _uniform(self._program, "light_direction").value = self._light.direction
        _uniform(self._program, "camera_position").value = self._camera.position
        _uniform(self._program, "ambient_light").value = self._settings.ambient_light
        _uniform(self._program, "diffuse_light").value = self._settings.diffuse_light
        for _buffer, vertex_array, color, finish in self._resources:
            _uniform(self._program, "material_color").value = (
                color[0] / 255.0,
                color[1] / 255.0,
                color[2] / 255.0,
                1.0,
            )
            _uniform(self._program, "material_finish").value = finish
            vertex_array.render(mode=moderngl.TRIANGLES)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            if event.button() == Qt.MouseButton.RightButton:
                mode = "light"
            elif event.button() == Qt.MouseButton.MiddleButton or bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                mode = "pan"
            else:
                mode = "orbit"
            self._interaction.begin_drag(
                mode, event.position().x(), event.position().y()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._interaction.dragging:
            super().mouseMoveEvent(event)
            return
        self._interaction.drag_to(event.position().x(), event.position().y())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._interaction.dragging:
            self._interaction.end_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        self._interaction.zoom(event.angleDelta().y() / 120.0)
        self.update()
        event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.makeCurrent()
        for vertex_buffer, vertex_array, _color, _finish in self._resources:
            vertex_array.release()
            vertex_buffer.release()
        if self._program is not None:
            self._program.release()
        self.doneCurrent()
        self._resources = []
        self._program = None
        self._context = None
        super().closeEvent(event)


class InteractivePreviewDialog(QDialog):
    """Modal shell matching LayerForge's interactive preview controls."""

    def __init__(
        self,
        colored_meshes: Sequence[ColoredMesh],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("3D Stack Preview")
        self.resize(960, 720)
        self.preview = InteractiveMeshPreview(colored_meshes)
        instructions = QLabel(
            "Left-drag to orbit · Middle-drag or Shift+left-drag to pan · "
            "Right-drag to move light · Mouse wheel to zoom"
        )
        instructions.setWordWrap(True)
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.preview.reset_view)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(instructions)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(reset_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)


def _uniform(program: moderngl.Program, name: str) -> moderngl.Uniform:
    return cast("moderngl.Uniform", program[name])
