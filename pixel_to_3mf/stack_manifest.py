"""Stack-based relief manifest schema, selection helpers, and persistence.

The module is intentionally Qt-free.  Both the GUI editor and headless
conversion consume the same validated stack definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .config import ConversionConfig
from .image_processor import PixelData
from .relief_manifest import pixel_fingerprint, validate_processing_settings


STACK_SCHEMA_VERSION = 2
STACK_MODE = "stack_relief"
Coordinate = tuple[int, int]
RGB = tuple[int, int, int]


@dataclass(frozen=True)
class StackDefinition:
    """One saved selection and its vertical material contract."""

    stack_id: str
    name: str
    pixels: frozenset[Coordinate]
    stack_height_mm: float
    color_height_mm: float


@dataclass(frozen=True)
class StackManifest:
    """Validated, geometry-ready stack manifest."""

    background_color: RGB
    backing_color: RGB
    backing_height_mm: float
    width: int
    height: int
    processed_pixel_sha256: str
    stacks: tuple[StackDefinition, ...]


def connected_color_component(
    pixel_data: PixelData,
    start: Coordinate,
) -> frozenset[Coordinate]:
    """Return the exact-RGB 4-connected component containing ``start``."""

    start_rgba = pixel_data.pixels.get(start)
    if start_rgba is None:
        return frozenset()
    target = start_rgba[:3]
    pending = [start]
    visited: set[Coordinate] = {start}
    while pending:
        x, y = pending.pop()
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbor in visited:
                continue
            rgba = pixel_data.pixels.get(neighbor)
            if rgba is not None and rgba[:3] == target:
                visited.add(neighbor)
                pending.append(neighbor)
    return frozenset(visited)


def encode_row_runs(pixels: Iterable[Coordinate], height: int) -> list[list[int]]:
    """Encode model-origin pixels as compact top-left-origin inclusive runs."""

    rows: dict[int, list[int]] = {}
    for x, model_y in pixels:
        top_y = height - 1 - model_y
        rows.setdefault(top_y, []).append(x)
    runs: list[list[int]] = []
    for top_y in sorted(rows):
        xs = sorted(set(rows[top_y]))
        if not xs:
            continue
        start = previous = xs[0]
        for x in xs[1:]:
            if x == previous + 1:
                previous = x
                continue
            runs.append([top_y, start, previous])
            start = previous = x
        runs.append([top_y, start, previous])
    return runs


def decode_row_runs(runs: Any, width: int, height: int) -> frozenset[Coordinate]:
    """Decode validated-looking row runs, raising ValueError on malformed data."""

    if not isinstance(runs, list):
        raise ValueError("selection.runs must be an array")
    pixels: set[Coordinate] = set()
    previous: tuple[int, int] | None = None
    for index, run in enumerate(runs):
        if (
            not isinstance(run, list)
            or len(run) != 3
            or any(not isinstance(value, int) or isinstance(value, bool) for value in run)
        ):
            raise ValueError(f"selection.runs[{index}] must be [Y,X_START,X_END]")
        top_y, x_start, x_end = run
        if not 0 <= top_y < height or not 0 <= x_start <= x_end < width:
            raise ValueError(f"selection.runs[{index}] is outside processed image bounds")
        key = (top_y, x_start)
        if previous is not None and key <= previous:
            raise ValueError("selection.runs must be sorted by row and starting X")
        previous = key
        model_y = height - 1 - top_y
        for x in range(x_start, x_end + 1):
            coordinate = (x, model_y)
            if coordinate in pixels:
                raise ValueError("selection.runs contains overlapping runs")
            pixels.add(coordinate)
    return frozenset(pixels)


def _processing_from_config(config: ConversionConfig) -> dict[str, Any]:
    return {
        "max_size_mm": config.max_size_mm,
        "scale_mm_per_pixel": config.scale_mm_per_pixel,
        "max_colors": config.max_colors,
        "auto_crop": config.auto_crop,
        "padding_size": config.padding_size,
        "padding_color": list(config.padding_color),
        "padding_type": config.padding_type,
        "preprocess_filter": config.preprocess_filter,
        "preprocess_filter_size": config.preprocess_filter_size,
        "quantize": config.quantize,
        "quantize_algorithm": config.quantize_algo,
        "quantize_colors": config.quantize_colors,
        "iterate_quantize": config.iterate_quantize,
        "denoise_min_size": config.denoise_min_size,
        "connectivity": config.connectivity,
        "trim_disconnected": config.trim_disconnected,
    }


def build_stack_manifest_data(
    source_path: str | Path,
    pixel_data: PixelData,
    config: ConversionConfig,
    stacks: Iterable[StackDefinition],
) -> dict[str, Any]:
    """Serialize editor state without requiring it to be export-complete."""

    source = Path(source_path)
    stack_items = []
    for stack in stacks:
        stack_items.append(
            {
                "stack_id": stack.stack_id,
                "stack_name": stack.name,
                "stack_height_mm": stack.stack_height_mm,
                "color_height_mm": stack.color_height_mm,
                "selection": {
                    "encoding": "row_runs",
                    "runs": encode_row_runs(stack.pixels, pixel_data.height),
                    "pixel_count": len(stack.pixels),
                },
            }
        )
    return {
        "schema_version": STACK_SCHEMA_VERSION,
        "mode": STACK_MODE,
        "source": {
            "path": str(source.resolve()),
            "name": source.name,
            "sha256": sha256(source.read_bytes()).hexdigest(),
        },
        "processing": _processing_from_config(config),
        "model": {
            "units": "mm",
            "background_color": list(config.relief_background_color),
            "backing_color": list(config.backing_color),
            "backing_height_mm": config.base_height_mm,
        },
        "processed_image": {
            "width": pixel_data.width,
            "height": pixel_data.height,
            "opaque_pixel_count": len(pixel_data.pixels),
            "pixel_sha256": pixel_fingerprint(pixel_data),
        },
        "stacks": stack_items,
    }


def write_stack_manifest(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return output


def load_stack_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Stack manifest root must be a JSON object")
    return data


def _parse_rgb(value: Any, field: str, errors: list[str]) -> RGB | None:
    if not isinstance(value, list) or len(value) != 3 or any(
        not isinstance(channel, int)
        or isinstance(channel, bool)
        or not 0 <= channel <= 255
        for channel in value
    ):
        errors.append(f"{field} must be an array of three integers from 0 to 255")
        return None
    return value[0], value[1], value[2]


def _positive_number(value: Any, field: str, errors: list[str]) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{field} must be a number")
        return 0.0
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        errors.append(f"{field} must be finite and greater than zero")
    return result


def validate_stack_manifest(
    data: dict[str, Any],
    pixel_data: PixelData | None = None,
    *,
    require_complete: bool = True,
) -> tuple[StackManifest | None, list[str], list[str]]:
    """Validate schema, ownership, dimensions, and optional processed pixels."""

    errors: list[str] = []
    warnings: list[str] = []
    if data.get("schema_version") != STACK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {STACK_SCHEMA_VERSION}")
    if data.get("mode") != STACK_MODE:
        errors.append(f"mode must be '{STACK_MODE}'")
    validate_processing_settings(data, errors)

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        if not isinstance(source.get("path"), str) or not source.get("path"):
            errors.append("source.path must be a non-empty string")
        if not isinstance(source.get("name"), str) or not source.get("name"):
            errors.append("source.name must be a non-empty string")
        digest = source.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in digest
        ):
            errors.append("source.sha256 must be a SHA-256 hex string")

    model = data.get("model")
    processed = data.get("processed_image")
    raw_stacks = data.get("stacks")
    if not isinstance(model, dict):
        errors.append("model must be an object")
        model = {}
    if not isinstance(processed, dict):
        errors.append("processed_image must be an object")
        processed = {}
    if not isinstance(raw_stacks, list):
        errors.append("stacks must be an array")
        raw_stacks = []

    if model.get("units") != "mm":
        errors.append("model.units must be 'mm'")
    background = _parse_rgb(model.get("background_color"), "model.background_color", errors)
    backing = _parse_rgb(model.get("backing_color"), "model.backing_color", errors)
    backing_height = _positive_number(
        model.get("backing_height_mm"), "model.backing_height_mm", errors
    )
    width = processed.get("width")
    height = processed.get("height")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        errors.append("processed_image.width must be a positive integer")
        width = 0
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        errors.append("processed_image.height must be a positive integer")
        height = 0
    fingerprint = processed.get("pixel_sha256")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in fingerprint)
    ):
        errors.append("processed_image.pixel_sha256 must be a SHA-256 hex string")
        fingerprint = ""
    opaque_count = processed.get("opaque_pixel_count")
    if (
        not isinstance(opaque_count, int)
        or isinstance(opaque_count, bool)
        or opaque_count < 0
    ):
        errors.append("processed_image.opaque_pixel_count must be a non-negative integer")

    stacks: list[StackDefinition] = []
    seen_ids: set[str] = set()
    owned: set[Coordinate] = set()
    for index, raw in enumerate(raw_stacks):
        prefix = f"stacks[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        stack_id = raw.get("stack_id")
        name = raw.get("stack_name")
        if not isinstance(stack_id, str) or not stack_id:
            errors.append(f"{prefix}.stack_id must be a non-empty string")
            stack_id = f"invalid_{index}"
        elif stack_id in seen_ids:
            errors.append(f"{prefix}.stack_id duplicates '{stack_id}'")
        seen_ids.add(stack_id)
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}.stack_name must be a non-empty string")
            name = stack_id
        stack_height = _positive_number(
            raw.get("stack_height_mm"), f"{prefix}.stack_height_mm", errors
        )
        color_height = _positive_number(
            raw.get("color_height_mm"), f"{prefix}.color_height_mm", errors
        )
        if color_height > stack_height:
            errors.append(f"{prefix}.color_height_mm must not exceed stack_height_mm")
        selection = raw.get("selection")
        pixels = frozenset()
        if not isinstance(selection, dict):
            errors.append(f"{prefix}.selection must be an object")
        elif selection.get("encoding") != "row_runs":
            errors.append(f"{prefix}.selection.encoding must be 'row_runs'")
        else:
            try:
                pixels = decode_row_runs(selection.get("runs"), width, height)
            except ValueError as exc:
                errors.append(f"{prefix}.{exc}")
            if selection.get("pixel_count") != len(pixels):
                errors.append(f"{prefix}.selection.pixel_count does not match its runs")
        if not pixels:
            errors.append(f"{prefix}.selection must contain at least one pixel")
        overlap = owned & set(pixels)
        if overlap:
            errors.append(f"{prefix}.selection overlaps another stack at {len(overlap)} pixel(s)")
        owned.update(pixels)
        stacks.append(
            StackDefinition(stack_id, str(name), pixels, stack_height, color_height)
        )

    if pixel_data is not None:
        if width != pixel_data.width or height != pixel_data.height:
            errors.append("Processed image dimensions do not match the manifest")
        if fingerprint and pixel_fingerprint(pixel_data) != fingerprint:
            errors.append("Processed image does not match processed_image.pixel_sha256")
        if opaque_count != len(pixel_data.pixels):
            errors.append("Processed image opaque pixel count does not match the manifest")
        invalid_owned = owned - set(pixel_data.pixels)
        if invalid_owned:
            errors.append(f"Stack selections contain {len(invalid_owned)} transparent pixel(s)")
        if background is not None:
            required = {
                coordinate
                for coordinate, rgba in pixel_data.pixels.items()
                if rgba[:3] != background
            }
            missing = required - owned
            if missing:
                message = f"{len(missing)} non-background pixel(s) are unassigned"
                if require_complete:
                    errors.append(message)
                else:
                    warnings.append(message)

    if errors or background is None or backing is None:
        return None, errors, warnings
    return (
        StackManifest(
            background,
            backing,
            backing_height,
            width,
            height,
            str(fingerprint),
            tuple(stacks),
        ),
        errors,
        warnings,
    )


def apply_stack_manifest_settings(data: dict[str, Any], config: ConversionConfig) -> None:
    """Replay frozen preprocessing and global material settings."""

    processing = data.get("processing")
    model = data.get("model")
    if not isinstance(processing, dict) or not isinstance(model, dict):
        raise ValueError("Stack manifest must contain processing and model objects")
    fields = {
        "max_size_mm": "max_size_mm",
        "scale_mm_per_pixel": "scale_mm_per_pixel",
        "max_colors": "max_colors",
        "auto_crop": "auto_crop",
        "padding_size": "padding_size",
        "padding_type": "padding_type",
        "preprocess_filter": "preprocess_filter",
        "preprocess_filter_size": "preprocess_filter_size",
        "quantize": "quantize",
        "quantize_algorithm": "quantize_algo",
        "quantize_colors": "quantize_colors",
        "iterate_quantize": "iterate_quantize",
        "denoise_min_size": "denoise_min_size",
        "connectivity": "connectivity",
        "trim_disconnected": "trim_disconnected",
    }
    for manifest_name, config_name in fields.items():
        if manifest_name in processing:
            setattr(config, config_name, processing[manifest_name])
    padding = processing.get("padding_color")
    if isinstance(padding, list) and len(padding) == 3:
        config.padding_color = (int(padding[0]), int(padding[1]), int(padding[2]))
    background = model.get("background_color")
    backing = model.get("backing_color")
    if isinstance(background, list) and len(background) == 3:
        config.relief_background_color = (
            int(background[0]), int(background[1]), int(background[2])
        )
    if isinstance(backing, list) and len(backing) == 3:
        config.backing_color = (int(backing[0]), int(backing[1]), int(backing[2]))
        config.auto_backing_color = False
    backing_height = model.get("backing_height_mm")
    if isinstance(backing_height, (int, float)) and not isinstance(backing_height, bool):
        config.base_height_mm = float(backing_height)
