"""Animated selection outlines for pixel-based Qt editors."""

from __future__ import annotations

import math
from collections.abc import Collection
from typing import TypeAlias

from PySide6.QtCore import QLineF, QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen

MaskEdge: TypeAlias = tuple[int, int, int, int]


def pixel_selection_edges(
    pixels: Collection[tuple[int, int]], image_height: int
) -> list[MaskEdge]:
    """Return the exposed edges of model-origin pixels in top-origin coordinates."""

    top_origin = {(x, image_height - 1 - model_y) for x, model_y in pixels}
    edges: list[MaskEdge] = []
    for x, y in sorted(top_origin):
        if (x, y - 1) not in top_origin:
            edges.append((x, y, x + 1, y))
        if (x + 1, y) not in top_origin:
            edges.append((x + 1, y, x + 1, y + 1))
        if (x, y + 1) not in top_origin:
            edges.append((x, y + 1, x + 1, y + 1))
        if (x - 1, y) not in top_origin:
            edges.append((x, y, x, y + 1))
    return edges


class SelectionOutlineAnimator(QObject):
    """Draw screen-space marching ants for axis-aligned pixel-mask edges."""

    frame_changed = Signal()

    _DASH_LENGTH = 4.0
    _PERIOD = _DASH_LENGTH * 2.0
    _INTERVAL_MS = 100

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(self._INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def set_active(self, active: bool) -> None:
        if active:
            if not self._timer.isActive():
                self._timer.start()
            return
        self._timer.stop()
        self._phase = 0.0

    def draw(
        self,
        painter: QPainter,
        edges: list[MaskEdge],
        *,
        origin_x: float,
        origin_y: float,
        zoom: float,
    ) -> None:
        if not edges:
            return
        lines = [
            QLineF(
                origin_x + start_x * zoom,
                origin_y + start_y * zoom,
                origin_x + end_x * zoom,
                origin_y + end_y * zoom,
            )
            for start_x, start_y, end_x, end_y in edges
        ]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawLines(lines)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawLines(self._white_segments(lines))
        painter.restore()

    def _advance(self) -> None:
        self._phase = (self._phase + 1.0) % self._PERIOD
        self.frame_changed.emit()

    def _white_segments(self, lines: list[QLineF]) -> list[QLineF]:
        segments: list[QLineF] = []
        for line in lines:
            horizontal = abs(line.dx()) >= abs(line.dy())
            start = min(line.x1(), line.x2()) if horizontal else min(line.y1(), line.y2())
            end = max(line.x1(), line.x2()) if horizontal else max(line.y1(), line.y2())
            interval = (
                math.floor((start + self._phase) / self._PERIOD) * self._PERIOD
                - self._phase
            )
            while interval < end:
                dash_start = max(start, interval)
                dash_end = min(end, interval + self._DASH_LENGTH)
                if dash_end > dash_start:
                    if horizontal:
                        segments.append(QLineF(dash_start, line.y1(), dash_end, line.y1()))
                    else:
                        segments.append(QLineF(line.x1(), dash_start, line.x1(), dash_end))
                interval += self._PERIOD
        return segments
