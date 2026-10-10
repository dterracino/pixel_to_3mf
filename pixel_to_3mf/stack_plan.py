"""Compile validated stack selections into explicit material/Z volumes."""

from __future__ import annotations

from dataclasses import dataclass

from .image_processor import PixelData
from .relief_plan import ReliefMaterialSpan
from .stack_manifest import StackManifest


@dataclass(frozen=True)
class StackReliefPlan:
    """Renderer/export-neutral material plan for stack relief geometry."""

    backing_color: tuple[int, int, int]
    backing_height_mm: float
    footprint: frozenset[tuple[int, int]]
    spans: tuple[ReliefMaterialSpan, ...]


def create_stack_relief_plan(
    manifest: StackManifest,
    pixel_data: PixelData,
) -> StackReliefPlan:
    """Resolve stack masks into background-fill and per-pixel-color spans."""

    spans: list[ReliefMaterialSpan] = []
    for stack in manifest.stacks:
        fill_height = stack.stack_height_mm - stack.color_height_mm
        if fill_height > 0:
            spans.append(
                ReliefMaterialSpan(
                    manifest.background_color,
                    stack.pixels,
                    0.0,
                    fill_height,
                    "background_fill",
                )
            )

        pixels_by_color: dict[tuple[int, int, int], set[tuple[int, int]]] = {}
        for coordinate in stack.pixels:
            rgba = pixel_data.pixels.get(coordinate)
            if rgba is None:
                raise ValueError(f"Stack '{stack.name}' contains transparent pixel {coordinate}")
            pixels_by_color.setdefault(rgba[:3], set()).add(coordinate)
        for rgb in sorted(pixels_by_color):
            spans.append(
                ReliefMaterialSpan(
                    rgb,
                    frozenset(pixels_by_color[rgb]),
                    fill_height,
                    stack.stack_height_mm,
                    "pixel_color",
                )
            )

    return StackReliefPlan(
        manifest.backing_color,
        manifest.backing_height_mm,
        frozenset(pixel_data.pixels),
        tuple(spans),
    )
