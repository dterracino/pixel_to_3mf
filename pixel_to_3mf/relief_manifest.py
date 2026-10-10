"""Schema, persistence, and validation for palette-relief manifests.

This module deliberately knows nothing about meshes or 3MF packaging.  It
describes the editable contract between image preprocessing and palette-relief
geometry generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
from typing import Any, Iterable

from .config import ConversionConfig
from .image_processor import PixelData
from .region_merger import Region


SCHEMA_VERSION = 1
DEPTH_MODES = {"top_cap", "deep_color"}
HEIGHT_REFERENCE = "backing_top"


@dataclass(frozen=True)
class ReliefSection:
    """Validated editable settings for one processed image colour."""

    rgb: tuple[int, int, int]
    pixel_count: int
    component_count: int
    height_mm: float
    color_depth_mode: str
    interface_depth_mm: float


@dataclass(frozen=True)
class ReliefManifest:
    """Validated geometry-relevant portion of a relief manifest."""

    background_color: tuple[int, int, int]
    backing_color: tuple[int, int, int]
    backing_height_mm: float
    background_height_mm: float
    processed_pixel_sha256: str
    width: int
    height: int
    sections: tuple[ReliefSection, ...]


def pixel_fingerprint(pixel_data: PixelData) -> str:
    """Return a stable fingerprint of processed dimensions and RGBA pixels."""

    digest = sha256()
    digest.update(f"{pixel_data.width}x{pixel_data.height}\n".encode("ascii"))
    for (x, y), rgba in sorted(pixel_data.pixels.items()):
        digest.update(struct.pack(">II4B", x, y, *rgba))
    return digest.hexdigest()


def _rgb_list(rgb: tuple[int, int, int]) -> list[int]:
    return [int(channel) for channel in rgb]


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def build_relief_manifest(
    source_path: str | Path,
    pixel_data: PixelData,
    regions: Iterable[Region],
    config: ConversionConfig,
    pre_quantization_pixels: PixelData | None = None,
) -> dict[str, Any]:
    """Build an editable manifest from the fully preprocessed image palette."""

    if config.base_height_mm <= 0 or config.no_backing_plate or config.solid_core:
        raise ValueError("Palette relief requires a physical backing plate with positive height")
    if config.smooth_boundaries:
        raise ValueError("Palette relief does not currently support boundary smoothing")
    if config.optimize_mesh:
        raise ValueError("Palette relief does not currently support optimized mesh generation")
    source = Path(source_path)
    region_list = list(regions)
    pixels_by_color: dict[tuple[int, int, int], int] = {}
    components_by_color: dict[tuple[int, int, int], int] = {}
    for region in region_list:
        pixels_by_color[region.color] = pixels_by_color.get(region.color, 0) + len(region.pixels)
        components_by_color[region.color] = components_by_color.get(region.color, 0) + 1
    if config.relief_background_color not in pixels_by_color:
        raise ValueError(
            "The selected background color "
            f"RGB{config.relief_background_color} is not present after preprocessing"
        )

    sections: list[dict[str, Any]] = []
    ordered = [
        rgb
        for rgb in sorted(pixels_by_color, key=lambda color: (-pixels_by_color[color], color))
        if rgb != config.relief_background_color
    ]
    for index, rgb in enumerate(ordered, start=1):
        section_name = f"{source.stem}.section_{index:02d}"
        color_info: dict[str, Any] = {"rgb": _rgb_list(rgb), "hex": _hex(rgb)}
        try:
            from .threemf_writer import get_color_name_and_rgb

            name, matched_rgb = get_color_name_and_rgb(rgb, config)
            color_info.update(
                name=name,
                matched_rgb=_rgb_list(matched_rgb),
                matched_hex=_hex(matched_rgb),
            )
        except Exception:
            # Manifest generation must remain usable when an optional palette
            # lookup is unavailable. Exact source RGB is still authoritative.
            color_info.update(name=_hex(rgb), matched_rgb=_rgb_list(rgb), matched_hex=_hex(rgb))

        contributing_colors: list[dict[str, Any]] = []
        if pre_quantization_pixels is not None:
            counts = Counter(
                pre_quantization_pixels.pixels[coord][:3]
                for region in region_list
                if region.color == rgb
                for coord in region.pixels
                if coord in pre_quantization_pixels.pixels
            )
            contributing_colors = [
                {"rgb": _rgb_list(source_rgb), "hex": _hex(source_rgb), "pixel_count": count}
                for source_rgb, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ]

        sections.append(
            {
                "section_number": index,
                "section_name": section_name,
                "section_image": f"{section_name}.png",
                "color": color_info,
                "pixel_count": pixels_by_color[rgb],
                "component_count": components_by_color[rgb],
                "pre_quantization_colors": contributing_colors,
                "height_mm": None,
                "color_depth_mode": "top_cap",
                "interface_depth_mm": 1.0,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "palette_relief",
        "source": {
            "path": str(source.resolve()),
            "name": source.name,
            "sha256": sha256(source.read_bytes()).hexdigest(),
        },
        "processing": {
            "max_size_mm": config.max_size_mm,
            "scale_mm_per_pixel": config.scale_mm_per_pixel,
            "max_colors": config.max_colors,
            "auto_crop": config.auto_crop,
            "padding_size": config.padding_size,
            "padding_color": _rgb_list(config.padding_color),
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
        },
        "model": {
            "height_mode": "exact",
            "height_reference": HEIGHT_REFERENCE,
            "units": "mm",
            "background_color": _rgb_list(config.relief_background_color),
            "background_height_mm": config.color_height_mm,
            "backing_color": _rgb_list(config.backing_color),
            "backing_height_mm": config.base_height_mm,
            "backing_color_selection": config.backing_color_selection,
            "backing_color_coordinate": (
                list(config.backing_color_coordinate)
                if config.backing_color_coordinate is not None
                else None
            ),
        },
        "processed_image": {
            "width": pixel_data.width,
            "height": pixel_data.height,
            "opaque_pixel_count": len(pixel_data.pixels),
            "color_count": len(pixels_by_color),
            "pixel_sha256": pixel_fingerprint(pixel_data),
            "pre_quantization_color_count": (
                len(pre_quantization_pixels.get_unique_colors())
                if pre_quantization_pixels is not None
                else len(pixels_by_color)
            ),
        },
        "sections": sections,
    }


def write_relief_manifest(path: str | Path, data: dict[str, Any]) -> Path:
    """Write a manifest using stable, human-editable formatting."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return output


def load_relief_manifest(path: str | Path) -> dict[str, Any]:
    """Load a manifest JSON object without interpreting geometry settings."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Relief manifest root must be a JSON object")
    return data


def apply_manifest_settings(data: dict[str, Any], config: ConversionConfig) -> None:
    """Apply the frozen preprocessing/model settings needed to reproduce a manifest."""

    processing = data.get("processing")
    model = data.get("model")
    if not isinstance(processing, dict) or not isinstance(model, dict):
        raise ValueError("Relief manifest must contain processing and model objects")

    simple_fields = {
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
    for manifest_name, config_name in simple_fields.items():
        if manifest_name in processing:
            setattr(config, config_name, processing[manifest_name])
    padding = processing.get("padding_color")
    if isinstance(padding, list) and len(padding) == 3:
        config.padding_color = tuple(padding)  # type: ignore[assignment]

    background = model.get("background_color")
    backing = model.get("backing_color")
    if isinstance(background, list) and len(background) == 3:
        config.relief_background_color = tuple(background)  # type: ignore[assignment]
    if isinstance(backing, list) and len(backing) == 3:
        config.backing_color = tuple(backing)  # type: ignore[assignment]
        config.auto_backing_color = False
    selection = model.get("backing_color_selection")
    if isinstance(selection, str):
        config.backing_color_selection = selection
    coordinate = model.get("backing_color_coordinate")
    if isinstance(coordinate, list) and len(coordinate) == 2:
        config.backing_color_coordinate = (int(coordinate[0]), int(coordinate[1]))
    else:
        config.backing_color_coordinate = None
    if isinstance(model.get("background_height_mm"), (int, float)):
        config.color_height_mm = float(model["background_height_mm"])
    if isinstance(model.get("backing_height_mm"), (int, float)):
        config.base_height_mm = float(model["backing_height_mm"])


def _parse_rgb(value: Any, field: str, errors: list[str]) -> tuple[int, int, int] | None:
    if not isinstance(value, list) or len(value) != 3 or any(
        not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel <= 255
        for channel in value
    ):
        errors.append(f"{field} must be an array of three integers from 0 to 255")
        return None
    return tuple(value)  # type: ignore[return-value]


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _validate_processing(data: dict[str, Any], errors: list[str]) -> None:
    processing = data.get("processing")
    if not isinstance(processing, dict):
        errors.append("processing must be an object")
        return

    def finite_positive(field: str, *, optional: bool = False) -> None:
        value = processing.get(field)
        if optional and value is None:
            return
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) <= 0
        ):
            errors.append(f"processing.{field} must be a finite number greater than zero")

    finite_positive("max_size_mm")
    finite_positive("scale_mm_per_pixel", optional=True)
    for field in ("max_colors", "preprocess_filter_size"):
        value = processing.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"processing.{field} must be a positive integer")
    for field in ("padding_size", "denoise_min_size"):
        value = processing.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"processing.{field} must be a non-negative integer")
    for field in ("auto_crop", "quantize", "iterate_quantize", "trim_disconnected"):
        if not isinstance(processing.get(field), bool):
            errors.append(f"processing.{field} must be true or false")

    _parse_rgb(processing.get("padding_color"), "processing.padding_color", errors)
    if processing.get("padding_type") not in {"circular", "square", "diamond"}:
        errors.append("processing.padding_type must be circular, square, or diamond")
    if processing.get("quantize_algorithm") not in {"none", "floyd"}:
        errors.append("processing.quantize_algorithm must be none or floyd")
    quantize_colors = processing.get("quantize_colors")
    if quantize_colors is not None and (
        not isinstance(quantize_colors, int)
        or isinstance(quantize_colors, bool)
        or quantize_colors <= 0
    ):
        errors.append("processing.quantize_colors must be null or a positive integer")
    if processing.get("connectivity") not in {0, 4, 8}:
        errors.append("processing.connectivity must be 0, 4, or 8")
    preprocess_filter = processing.get("preprocess_filter")
    if preprocess_filter not in {None, "mode", "median", "smooth", "smooth_more", "gaussian"}:
        errors.append("processing.preprocess_filter is not supported")
    filter_size = processing.get("preprocess_filter_size")
    if isinstance(filter_size, int) and (filter_size < 3 or filter_size % 2 == 0):
        errors.append("processing.preprocess_filter_size must be an odd integer at least 3")
    if processing.get("iterate_quantize") is True and processing.get("quantize") is not True:
        errors.append("processing.iterate_quantize requires processing.quantize")


def validate_relief_manifest(
    data: dict[str, Any],
    pixel_data: PixelData | None = None,
    regions: Iterable[Region] | None = None,
) -> tuple[ReliefManifest | None, list[str], list[str]]:
    """Validate schema, editable values, and optionally processed-image identity."""

    errors: list[str] = []
    warnings: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("mode") != "palette_relief":
        errors.append("mode must be 'palette_relief'")
    _validate_processing(data, errors)

    source = data.get("source")
    source_stem: str | None = None
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        source_hash = source.get("sha256")
        if not _is_sha256(source_hash):
            errors.append("source.sha256 must be a SHA-256 hex string")
        source_name = source.get("name")
        if not isinstance(source_name, str) or not source_name:
            errors.append("source.name must be a non-empty string")
        else:
            source_stem = Path(source_name).stem

    model = data.get("model")
    processed = data.get("processed_image")
    raw_sections = data.get("sections")
    if not isinstance(model, dict):
        errors.append("model must be an object")
        model = {}
    if not isinstance(processed, dict):
        errors.append("processed_image must be an object")
        processed = {}
    if not isinstance(raw_sections, list):
        errors.append("sections must be an array")
        raw_sections = []

    if model.get("height_mode") != "exact":
        errors.append("model.height_mode must be 'exact'")
    if model.get("height_reference") != HEIGHT_REFERENCE:
        errors.append(f"model.height_reference must be '{HEIGHT_REFERENCE}'")
    if model.get("units") != "mm":
        errors.append("model.units must be 'mm'")

    background = _parse_rgb(model.get("background_color"), "model.background_color", errors)
    backing = _parse_rgb(model.get("backing_color"), "model.backing_color", errors)
    selection = model.get("backing_color_selection")
    if selection not in {"default", "explicit", "auto", "coordinate"}:
        errors.append(
            "model.backing_color_selection must be default, explicit, auto, or coordinate"
        )
    coordinate = model.get("backing_color_coordinate")
    if coordinate is not None and (
        not isinstance(coordinate, list)
        or len(coordinate) != 2
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in coordinate
        )
    ):
        errors.append("model.backing_color_coordinate must be null or non-negative [X,Y]")
    if selection == "coordinate" and coordinate is None:
        errors.append("coordinate backing selection requires model.backing_color_coordinate")

    def positive_number(value: Any, field: str, allow_zero: bool = False) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{field} must be a number")
            return 0.0
        number = float(value)
        if not math.isfinite(number):
            errors.append(f"{field} must be finite")
            return 0.0
        invalid = number < 0 if allow_zero else number <= 0
        if invalid:
            qualifier = "non-negative" if allow_zero else "greater than zero"
            errors.append(f"{field} must be {qualifier}")
        return number

    backing_height = positive_number(model.get("backing_height_mm"), "model.backing_height_mm")
    background_height = positive_number(model.get("background_height_mm"), "model.background_height_mm")
    width = processed.get("width")
    height = processed.get("height")
    fingerprint_value = processed.get("pixel_sha256")
    if not isinstance(width, int) or width <= 0:
        errors.append("processed_image.width must be a positive integer")
        width = 0
    if not isinstance(height, int) or height <= 0:
        errors.append("processed_image.height must be a positive integer")
        height = 0
    if not _is_sha256(fingerprint_value):
        errors.append("processed_image.pixel_sha256 must be a SHA-256 hex string")
        fingerprint = ""
    else:
        fingerprint = str(fingerprint_value)
    for field in ("opaque_pixel_count", "color_count", "pre_quantization_color_count"):
        value = processed.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"processed_image.{field} must be a positive integer")

    sections: list[ReliefSection] = []
    seen: set[tuple[int, int, int]] = set()
    previous_pixel_count: int | None = None
    for index, raw in enumerate(raw_sections):
        prefix = f"sections[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        section_number = index + 1
        if raw.get("section_number") != section_number:
            errors.append(f"{prefix}.section_number must be {section_number}")
        if source_stem is not None:
            expected_name = f"{source_stem}.section_{section_number:02d}"
            if raw.get("section_name") != expected_name:
                errors.append(f"{prefix}.section_name must be '{expected_name}'")
            expected_image = f"{expected_name}.png"
            if raw.get("section_image") != expected_image:
                errors.append(f"{prefix}.section_image must be '{expected_image}'")
        color = raw.get("color")
        if not isinstance(color, dict):
            errors.append(f"{prefix}.color must be an object")
            continue
        rgb = _parse_rgb(color.get("rgb"), f"{prefix}.color.rgb", errors)
        if rgb is None:
            continue
        if rgb in seen:
            errors.append(f"{prefix}.color.rgb duplicates RGB{rgb}")
        seen.add(rgb)
        if background is not None and rgb == background:
            errors.append(f"{prefix} must not describe the background color RGB{rgb}")

        pixel_count = raw.get("pixel_count")
        component_count = raw.get("component_count")
        if not isinstance(pixel_count, int) or pixel_count <= 0:
            errors.append(f"{prefix}.pixel_count must be a positive integer")
            pixel_count = 0
        if previous_pixel_count is not None and pixel_count > previous_pixel_count:
            errors.append("sections must be ordered by descending pixel_count")
        previous_pixel_count = pixel_count
        if not isinstance(component_count, int) or component_count <= 0:
            errors.append(f"{prefix}.component_count must be a positive integer")
            component_count = 0
        contributions = raw.get("pre_quantization_colors")
        contribution_total = 0
        contribution_rgbs: set[tuple[int, int, int]] = set()
        if not isinstance(contributions, list):
            errors.append(f"{prefix}.pre_quantization_colors must be an array")
        else:
            for contribution_index, contribution in enumerate(contributions):
                contribution_prefix = (
                    f"{prefix}.pre_quantization_colors[{contribution_index}]"
                )
                if not isinstance(contribution, dict):
                    errors.append(f"{contribution_prefix} must be an object")
                    continue
                contribution_rgb = _parse_rgb(
                    contribution.get("rgb"), f"{contribution_prefix}.rgb", errors
                )
                contribution_count = contribution.get("pixel_count")
                if (
                    not isinstance(contribution_count, int)
                    or isinstance(contribution_count, bool)
                    or contribution_count <= 0
                ):
                    errors.append(f"{contribution_prefix}.pixel_count must be positive")
                else:
                    contribution_total += contribution_count
                if contribution_rgb is not None:
                    if contribution_rgb in contribution_rgbs:
                        errors.append(f"{contribution_prefix}.rgb is duplicated")
                    contribution_rgbs.add(contribution_rgb)
        processing = data.get("processing")
        if (
            isinstance(processing, dict)
            and processing.get("quantize") is True
            and contribution_total != pixel_count
        ):
            errors.append(
                f"{prefix}.pre_quantization_colors pixel counts must sum to pixel_count"
            )
        height_mm = positive_number(raw.get("height_mm"), f"{prefix}.height_mm")
        interface = positive_number(raw.get("interface_depth_mm"), f"{prefix}.interface_depth_mm")
        mode = raw.get("color_depth_mode")
        if mode not in DEPTH_MODES:
            errors.append(f"{prefix}.color_depth_mode must be one of {sorted(DEPTH_MODES)}")
            mode = "top_cap"
        if height_mm <= interface:
            errors.append(
                f"{prefix}.height_mm must be greater than interface_depth_mm "
                "so both material volumes have positive height"
            )
        sections.append(ReliefSection(rgb, pixel_count, component_count, height_mm, mode, interface))

    if isinstance(processed.get("color_count"), int) and background is not None:
        if processed["color_count"] != len(seen) + 1:
            errors.append(
                "processed_image.color_count must equal section colors plus the background"
            )

    if pixel_data is not None:
        actual = pixel_fingerprint(pixel_data)
        if fingerprint and actual != fingerprint:
            errors.append("Processed image does not match processed_image.pixel_sha256")
        if width != pixel_data.width or height != pixel_data.height:
            errors.append("Processed image dimensions do not match the manifest")
        if processed.get("opaque_pixel_count") != len(pixel_data.pixels):
            errors.append("Processed image opaque pixel count does not match the manifest")
        if processed.get("color_count") != len(pixel_data.get_unique_colors()):
            errors.append("Processed image color count does not match the manifest")

    if regions is not None and background is not None:
        actual_pixels: dict[tuple[int, int, int], int] = {}
        actual_components: dict[tuple[int, int, int], int] = {}
        for region in regions:
            actual_pixels[region.color] = actual_pixels.get(region.color, 0) + len(region.pixels)
            actual_components[region.color] = actual_components.get(region.color, 0) + 1
        expected_colors = set(actual_pixels) - {background}
        if seen != expected_colors:
            errors.append("Manifest section colors do not match the processed image palette")
        for section in sections:
            if section.rgb in actual_pixels and section.pixel_count != actual_pixels[section.rgb]:
                errors.append(f"RGB{section.rgb} pixel_count does not match the processed image")
            if section.rgb in actual_components and section.component_count != actual_components[section.rgb]:
                errors.append(f"RGB{section.rgb} component_count does not match the processed image")

    if errors or background is None or backing is None:
        return None, errors, warnings
    return ReliefManifest(
        background_color=background,
        backing_color=backing,
        backing_height_mm=backing_height,
        background_height_mm=background_height,
        processed_pixel_sha256=fingerprint,
        width=width,
        height=height,
        sections=tuple(sections),
    ), errors, warnings
