"""Image-analysis workflow shared by palette-relief CLI operations."""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
from pathlib import Path

from PIL import Image

from .config import ConversionConfig
from .image_processor import PixelData, load_image
from .region_merger import Region, denoise_blob_pixels, merge_regions, trim_disconnected_pixels
from .relief_manifest import build_relief_manifest, write_relief_manifest
from .iterative_quantizer import select_iterative_quantization


def prepare_relief_image(
    image_path: str | Path, config: ConversionConfig
) -> tuple[PixelData, list[Region]]:
    """Run the preprocessing stages which define a relief manifest palette."""

    if config.iterate_quantize and config.quantize:
        pixels, regions, _, _ = select_iterative_quantization(str(image_path), config)
        return pixels, regions
    pixels = load_image(str(image_path), config)
    if config.denoise_min_size > 0:
        pixels.pixels = denoise_blob_pixels(
            pixels.pixels, config.denoise_min_size, config.connectivity
        )
    regions = merge_regions(pixels, config)
    if config.trim_disconnected:
        regions = trim_disconnected_pixels(regions, pixels.pixels)
    return pixels, regions


def filter_pixel_data_to_regions(
    pixel_data: PixelData, regions: list[Region]
) -> PixelData:
    """Return the exact post-region pixel map used by final geometry."""

    included = {coordinate for region in regions for coordinate in region.pixels}
    return PixelData(
        pixel_data.width,
        pixel_data.height,
        pixel_data.pixel_size_mm,
        {
            coordinate: rgba
            for coordinate, rgba in pixel_data.pixels.items()
            if coordinate in included
        },
    )


def generate_relief_manifest_file(
    image_path: str | Path,
    output_path: str | Path,
    config: ConversionConfig,
) -> Path:
    """Analyze an image and write its editable palette-relief manifest."""

    pre_quantization_pixels = None
    if config.quantize:
        pre_quantization_config = deepcopy(config)
        pre_quantization_config.quantize = False
        pre_quantization_config.iterate_quantize = False
        pre_quantization_config.no_backing_color = True
        pre_quantization_config.max_colors = 1_000_000
        pre_quantization_pixels = load_image(str(image_path), pre_quantization_config)
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(
        image_path,
        pixels,
        regions,
        config,
        pre_quantization_pixels=pre_quantization_pixels,
    )
    generate_relief_section_images(pixels, data, Path(output_path).parent)
    return write_relief_manifest(output_path, data)


def generate_relief_section_images(
    pixel_data: PixelData,
    manifest_data: dict,
    output_directory: str | Path,
) -> list[Path]:
    """Write one full-canvas reference PNG for every editable color section.

    PixelData uses a bottom-left model origin, while PNG files use a top-left
    image origin. Converting the Y coordinate here keeps section images aligned
    with the processed image seen by the user and by geometry generation.
    """

    model = manifest_data.get("model")
    sections = manifest_data.get("sections")
    if not isinstance(model, dict) or not isinstance(sections, list):
        raise ValueError("Relief manifest data is missing model or sections")

    background = model.get("background_color")
    if (
        not isinstance(background, list)
        or len(background) != 3
        or any(not isinstance(channel, int) or not 0 <= channel <= 255 for channel in background)
    ):
        raise ValueError("Relief manifest background_color must be an RGB array")
    background_rgb = tuple(background)

    coordinates_by_color: dict[tuple[int, int, int], list[tuple[int, int]]] = defaultdict(list)
    for (x, model_y), rgba in pixel_data.pixels.items():
        coordinates_by_color[rgba[:3]].append((x, pixel_data.height - 1 - model_y))

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Relief manifest section must be an object")
        color = section.get("color")
        image_name = section.get("section_image")
        if not isinstance(color, dict) or not isinstance(image_name, str):
            raise ValueError("Relief manifest section is missing color or section_image")
        rgb_value = color.get("rgb")
        if not isinstance(rgb_value, list) or len(rgb_value) != 3:
            raise ValueError("Relief manifest section color must be an RGB array")
        rgb = tuple(rgb_value)

        image = Image.new("RGB", (pixel_data.width, pixel_data.height), background_rgb)
        for coordinate in coordinates_by_color.get(rgb, []):
            image.putpixel(coordinate, rgb)
        image_path = destination / image_name
        image.save(image_path, "PNG")
        written.append(image_path)

    return written


def color_at_image_coordinate(pixel_data: PixelData, x: int, y: int) -> tuple[int, int, int, int]:
    """Sample a conventional top-left-origin image coordinate after preprocessing."""

    if x < 0 or y < 0 or x >= pixel_data.width or y >= pixel_data.height:
        raise ValueError(
            f"Coordinate ({x},{y}) is outside processed image bounds "
            f"0..{pixel_data.width - 1},0..{pixel_data.height - 1}"
        )
    model_y = pixel_data.height - 1 - y
    rgba = pixel_data.pixels.get((x, model_y))
    if rgba is None:
        raise ValueError(f"Coordinate ({x},{y}) is transparent after preprocessing")
    return rgba
