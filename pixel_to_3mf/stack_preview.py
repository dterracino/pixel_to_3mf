"""Compile in-memory stack editor state through the production renderer."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .config import ConversionConfig
from .image_processor import PixelData
from .mesh import Mesh
from .palette_relief import build_palette_relief_meshes
from .render_model import render_meshes_to_png
from .stack_manifest import (
    StackDefinition,
    build_stack_manifest_data,
    validate_stack_manifest,
)
from .stack_plan import create_stack_relief_plan

ColoredMesh = tuple[Mesh, tuple[int, int, int]]


def build_stack_preview_meshes(
    source_path: str | Path,
    pixel_data: PixelData,
    config: ConversionConfig,
    stacks: Iterable[StackDefinition],
) -> list[ColoredMesh]:
    """Compile a possibly incomplete editor draft into finalized colored meshes."""

    data = build_stack_manifest_data(source_path, pixel_data, config, stacks)
    manifest, errors, _ = validate_stack_manifest(
        data,
        pixel_data,
        require_complete=False,
    )
    if errors or manifest is None:
        raise ValueError("Cannot render stack preview: " + "; ".join(errors))
    plan = create_stack_relief_plan(manifest, pixel_data)
    meshes, colors = build_palette_relief_meshes(plan, pixel_data, config)
    return [
        (mesh, color)
        for (mesh, _name), color in zip(meshes, colors, strict=True)
    ]


def render_stack_preview(
    source_path: str | Path,
    pixel_data: PixelData,
    config: ConversionConfig,
    stacks: Iterable[StackDefinition],
    *,
    image_size_px: int = 800,
) -> bytes:
    """Render a draft manifest, allowing incomplete pixel assignment."""

    colored_meshes = build_stack_preview_meshes(
        source_path, pixel_data, config, stacks
    )
    return render_meshes_to_png(colored_meshes, image_size_px)
