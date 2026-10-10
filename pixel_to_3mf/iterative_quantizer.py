"""Shared iterative quantization selection for conversion and manifest analysis."""

from __future__ import annotations

from typing import Callable

from .config import ConversionConfig
from .image_processor import PixelData, load_image
from .region_merger import Region, denoise_blob_pixels, merge_regions, trim_disconnected_pixels


ProgressCallback = Callable[[str, str], None]


def _copy_pixels(pixel_data: PixelData) -> PixelData:
    return PixelData(
        pixel_data.width,
        pixel_data.height,
        pixel_data.pixel_size_mm,
        dict(pixel_data.pixels),
    )


def _required_image_slots(regions: list[Region], config: ConversionConfig) -> int:
    """Count exported image slots using the writer's color grouping rules."""

    unique_colors = {region.color for region in regions}
    if config.merge_similar_colors:
        from .threemf_writer import get_color_name

        grouped: set[str | tuple[int, int, int]] = {
            get_color_name(rgb, config) for rgb in unique_colors
        }
        if not config.no_backing_color:
            grouped.discard(get_color_name(config.backing_color, config))
    else:
        grouped = set(unique_colors)
        if not config.no_backing_color:
            grouped.discard(config.backing_color)
    return len(grouped)


def select_iterative_quantization(
    image_path: str,
    config: ConversionConfig,
    progress_callback: ProgressCallback | None = None,
) -> tuple[PixelData, list[Region], PixelData, int]:
    """Select the highest quantization target that fits available color slots.

    Returns the final (possibly denoised) pixels, final regions, a snapshot taken
    immediately after quantization, and the selected quantization target.
    """

    if not config.quantize or not config.iterate_quantize:
        raise ValueError("Iterative quantization requires quantize and iterate_quantize")

    def progress(stage: str, message: str) -> None:
        if progress_callback:
            progress_callback(stage, message)

    start = config.quantize_colors if config.quantize_colors is not None else config.max_colors
    minimum = config.max_colors
    if start < minimum:
        raise ValueError("--quantize-colors must be at least --max-colors in iterative mode")

    last_result: tuple[PixelData, list[Region], PixelData, int] | None = None
    effective_limit = config.max_colors if config.no_backing_color else config.max_colors - 1
    for target in range(start, minimum - 1, -1):
        config.quantize_colors = target
        progress("load", f"Trying quantize-colors={target}...")
        pixels = load_image(image_path, config)
        quantized_snapshot = _copy_pixels(pixels)
        if config.denoise_min_size > 0:
            progress("denoise", f"Denoising blobs smaller than {config.denoise_min_size}px...")
            pixels.pixels = denoise_blob_pixels(
                pixels.pixels, config.denoise_min_size, config.connectivity
            )
            progress("denoise", "Complete!")
        regions = merge_regions(pixels, config)
        if config.trim_disconnected:
            regions = trim_disconnected_pixels(regions, pixels.pixels)

        last_result = pixels, regions, quantized_snapshot, target
        required = _required_image_slots(regions, config)
        progress("load", f"  → {required} merged colors (target: ≤{effective_limit})")
        if required <= effective_limit:
            return last_result

    # Preserve the historical converter behavior at the lower bound. The
    # writer may still reject an impossible material assignment later.
    assert last_result is not None
    return last_result
