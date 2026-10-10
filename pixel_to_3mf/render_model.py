"""
Render generated meshes as shaded, full-color PNG previews.

The renderer consumes the same finalized meshes and colors used by the 3MF
writer. This keeps standalone renders and embedded slicer thumbnails aligned
with relief heights, optimized geometry, solid-core shells, and filament color
matching.
"""

from __future__ import annotations

import io
from pathlib import Path
from collections.abc import Sequence

from preview_renderer import (
    RenderMaterial,
    RenderMesh,
    RenderSettings,
    render_scene_to_image,
)

from .constants import (
    RENDER_AMBIENT_LIGHT,
    RENDER_CAMERA_AZIMUTH_DEG,
    RENDER_CAMERA_ELEVATION_DEG,
    RENDER_DIFFUSE_LIGHT,
    RENDER_IMAGE_SIZE_PX,
    RENDER_LIGHT_DIRECTION,
)
from .mesh_generator import Mesh

RGBColor = tuple[int, int, int]
ColoredMesh = tuple[Mesh, RGBColor]


def render_meshes_to_png(
    colored_meshes: Sequence[ColoredMesh],
    image_size_px: int = RENDER_IMAGE_SIZE_PX,
) -> bytes:
    """
    Render finalized model geometry to transparent PNG bytes.

    A deterministic orbit camera and directional Lambert lighting mirror the
    visual language of Layerforge while remaining headless and suitable for
    CLI use. The actual mesh coordinates drive the render, so relief and all
    other Z-level differences are preserved.

    Args:
        colored_meshes: Meshes paired one-to-one with their exported RGB color.
        image_size_px: Width and height of the square PNG.

    Returns:
        Encoded RGBA PNG bytes.

    Raises:
        ValueError: If image_size_px is invalid.
    """
    if image_size_px <= 0:
        raise ValueError(f"image_size_px must be positive, got {image_size_px}")

    image = render_scene_to_image(
        [
            RenderMesh(mesh=mesh, material=RenderMaterial(color=color))
            for mesh, color in colored_meshes
        ],
        image_size_px,
        settings=RenderSettings(
            camera_elevation_degrees=RENDER_CAMERA_ELEVATION_DEG,
            camera_azimuth_degrees=RENDER_CAMERA_AZIMUTH_DEG,
            light_direction=RENDER_LIGHT_DIRECTION,
            ambient_light=RENDER_AMBIENT_LIGHT,
            diffuse_light=RENDER_DIFFUSE_LIGHT,
        ),
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def render_meshes_to_file(
    colored_meshes: Sequence[ColoredMesh],
    output_path: str,
    image_size_px: int = RENDER_IMAGE_SIZE_PX,
) -> None:
    """
    Save the authoritative model render used by standalone and embedded previews.

    Args:
        colored_meshes: Meshes paired with their exported RGB colors.
        output_path: Destination PNG path.
        image_size_px: Width and height of the square PNG.

    Raises:
        OSError: If the destination cannot be written.
        ValueError: If the render input is invalid.
    """
    Path(output_path).write_bytes(
        render_meshes_to_png(colored_meshes, image_size_px)
    )


def generate_render_path(output_path: str) -> str:
    """
    Derive the standalone render path from a 3MF output path.

    Args:
        output_path: Path to the 3MF output file.

    Returns:
        A sibling path named ``{output_stem}_render.png``.
    """
    output_file = Path(output_path)
    return (output_file.parent / f"{output_file.stem}_render.png").as_posix()
