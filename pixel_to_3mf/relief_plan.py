"""Typed material/Z plan between manifest validation and mesh generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .region_merger import Region
from .relief_manifest import ReliefManifest


@dataclass(frozen=True)
class ReliefMaterialSpan:
    """One material occupying an XY footprint over an explicit Z interval."""

    rgb: tuple[int, int, int]
    pixels: frozenset[tuple[int, int]]
    z_bottom: float
    z_top: float
    role: str


@dataclass(frozen=True)
class PaletteReliefPlan:
    """Geometry-ready palette relief plan with no JSON interpretation."""

    backing_color: tuple[int, int, int]
    backing_height_mm: float
    footprint: frozenset[tuple[int, int]]
    spans: tuple[ReliefMaterialSpan, ...]


def create_palette_relief_plan(
    manifest: ReliefManifest,
    regions: Iterable[Region],
) -> PaletteReliefPlan:
    """Resolve validated sections into explicit material footprints and Z spans."""

    pixels_by_color: dict[tuple[int, int, int], set[tuple[int, int]]] = {}
    footprint: set[tuple[int, int]] = set()
    for region in regions:
        pixels_by_color.setdefault(region.color, set()).update(region.pixels)
        footprint.update(region.pixels)

    spans: list[ReliefMaterialSpan] = []
    background_pixels = pixels_by_color.get(manifest.background_color)
    if background_pixels:
        spans.append(
            ReliefMaterialSpan(
                manifest.background_color,
                frozenset(background_pixels),
                0.0,
                manifest.background_height_mm,
                "background",
            )
        )

    for section in manifest.sections:
        pixels = pixels_by_color.get(section.rgb)
        if not pixels:
            raise ValueError(f"Manifest section RGB{section.rgb} has no processed pixels")
        split_z = (
            section.height_mm - section.interface_depth_mm
            if section.color_depth_mode == "top_cap"
            else section.interface_depth_mm
        )
        spans.append(
            ReliefMaterialSpan(
                manifest.backing_color,
                frozenset(pixels),
                0.0,
                split_z,
                "section_backing_fill",
            )
        )
        spans.append(
            ReliefMaterialSpan(
                section.rgb,
                frozenset(pixels),
                split_z,
                section.height_mm,
                "section_color",
            )
        )

    return PaletteReliefPlan(
        backing_color=manifest.backing_color,
        backing_height_mm=manifest.backing_height_mm,
        footprint=frozenset(footprint),
        spans=tuple(spans),
    )
