"""Turn a validated palette-relief manifest into explicitly coloured meshes."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Protocol

from .config import ConversionConfig
from .image_processor import PixelData
from .mesh import Mesh
from .mesh_generator import (
    check_mesh_manifold,
    generate_backing_plate,
    generate_region_mesh_shell,
)
from .region_merger import Region
from .relief_plan import ReliefMaterialSpan


class MaterialReliefPlan(Protocol):
    """Structural contract shared by palette and selection-stack relief."""

    @property
    def backing_color(self) -> tuple[int, int, int]: ...

    @property
    def backing_height_mm(self) -> float: ...

    @property
    def footprint(self) -> frozenset[tuple[int, int]]: ...

    @property
    def spans(self) -> tuple[ReliefMaterialSpan, ...]: ...


def combine_meshes(meshes: Iterable[Mesh]) -> Mesh:
    """Combine disconnected closed meshes without changing their geometry."""

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    for mesh in meshes:
        offset = len(vertices)
        vertices.extend(mesh.vertices)
        triangles.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.triangles)
    return Mesh(vertices, triangles)


def build_palette_relief_meshes(
    plan: MaterialReliefPlan,
    pixel_data: PixelData,
    config: ConversionConfig,
) -> tuple[list[tuple[Mesh, str]], list[tuple[int, int, int]]]:
    """Build one aggregate 3MF object per material RGB."""

    parts: dict[tuple[int, int, int], list[Mesh]] = defaultdict(list)
    for span in plan.spans:
        region = Region(span.rgb, set(span.pixels))
        parts[span.rgb].append(
            generate_region_mesh_shell(
                region, pixel_data, config, span.z_bottom, span.z_top
            )
        )

    if plan.backing_height_mm > 0:
        # Reuse the normal footprint builder, with manifest dimensions applied
        # to the config by the caller. Its slab spans -base_height_mm..0.
        parts[plan.backing_color].append(generate_backing_plate(pixel_data, config))

    colors = sorted(parts)
    meshes = [
        (combine_meshes(parts[rgb]), f"palette_{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
        for rgb in colors
    ]
    return meshes, colors


def validate_palette_relief_geometry(
    plan: MaterialReliefPlan,
    pixel_data: PixelData,
    config: ConversionConfig,
) -> list[str]:
    """Dry-run all material meshes and return printable geometry errors."""

    filtered_pixels = PixelData(
        pixel_data.width,
        pixel_data.height,
        pixel_data.pixel_size_mm,
        {
            coord: rgba
            for coord, rgba in pixel_data.pixels.items()
            if coord in plan.footprint
        },
    )
    meshes, colors = build_palette_relief_meshes(plan, filtered_pixels, config)
    errors: list[str] = []
    for (mesh, _), color in zip(meshes, colors):
        if not mesh.vertices or not mesh.triangles:
            errors.append(f"RGB{color} produced empty geometry")
            continue
        result = check_mesh_manifold(mesh)
        if not result["is_valid"]:
            errors.append(
                f"RGB{color} geometry is invalid: "
                f"{result['boundary_edges']} boundary edges, "
                f"{result['non_manifold_edges']} non-manifold edges, "
                f"winding={result['winding']}"
            )
    return errors
