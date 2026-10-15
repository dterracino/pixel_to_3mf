"""Tests for pixel selection boundary generation and animation."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QWidget
import pytest

from pixel_to_3mf.selection_outline import (
    SelectionOutlineAnimator,
    pixel_selection_edges,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return cast(QApplication, existing) if existing is not None else QApplication([])


def test_adjacent_pixels_share_no_internal_selection_edge() -> None:
    edges = pixel_selection_edges({(0, 1), (1, 1)}, image_height=2)

    assert len(edges) == 6
    assert (1, 0, 1, 1) not in edges


def test_model_origin_is_converted_to_top_origin() -> None:
    assert pixel_selection_edges({(2, 0)}, image_height=3) == [
        (2, 2, 3, 2),
        (3, 2, 3, 3),
        (2, 3, 3, 3),
        (2, 2, 2, 3),
    ]


def test_animation_runs_only_while_outline_is_active(qapp: QApplication) -> None:
    parent = QWidget()
    animator = SelectionOutlineAnimator(parent)
    frames = QSignalSpy(animator.frame_changed)

    assert not animator.active
    animator.set_active(True)
    assert animator.active
    QTest.qWait(120)
    qapp.processEvents()
    assert frames.count() >= 1

    animator.set_active(False)
    assert not animator.active
    parent.close()
