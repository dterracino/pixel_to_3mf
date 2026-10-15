"""Interaction tests for the stack editor's live 3D preview."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from pixel_to_3mf.mesh import Mesh
from pixel_to_3mf.stack_preview_widget import InteractiveMeshPreview


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return cast(QApplication, existing) if existing is not None else QApplication([])


def _widget() -> InteractiveMeshPreview:
    mesh = Mesh(
        [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 2.0)],
        [(0, 1, 2)],
    )
    return InteractiveMeshPreview([(mesh, (255, 0, 0))])


def _drag(widget: InteractiveMeshPreview, button: Qt.MouseButton) -> None:
    start = QPoint(20, 30)
    end = QPoint(45, 55)
    QTest.mousePress(widget, button, pos=start)
    QTest.mouseMove(widget, end)
    QTest.mouseRelease(widget, button, pos=end)


def test_left_drag_orbits_camera(qapp) -> None:
    widget = _widget()
    before = widget.camera_position

    _drag(widget, Qt.MouseButton.LeftButton)

    assert widget.camera_position != before


def test_middle_drag_pans_camera(qapp) -> None:
    widget = _widget()
    before = widget.view_projection(4.0 / 3.0)

    _drag(widget, Qt.MouseButton.MiddleButton)

    assert not np.array_equal(widget.view_projection(4.0 / 3.0), before)


def test_right_drag_moves_light(qapp) -> None:
    widget = _widget()
    before = widget.light_direction

    _drag(widget, Qt.MouseButton.RightButton)

    assert widget.light_direction != before
