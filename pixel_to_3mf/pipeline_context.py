"""
Pipeline context for tracking intermediate image states during conversion.

WHY: The conversion pipeline transforms the source image through up to three
stages before producing the final 3MF — quantization, denoising, and filament
colour matching.  When the user requests --preview, we want a side-by-side PNG
for each transformation that was actually applied:

  _quantized.png   original  → after colour quantization
  _denoised.png    previous  → after blob denoising
  _preview.png     previous  → after filament colour matching  (always last)

Rather than scattering snapshot logic and preview generation across
pixel_to_3mf.py and threemf_writer.py, PipelineContext holds every
intermediate PixelData and colour-mapping as they are produced, then
generate_previews() walks the chain and emits only the images that are
relevant for the flags the user passed.

All snapshots are shallow copies of the pixels dict so mutations in later
stages do not corrupt earlier snapshots.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:
    from .image_processor import PixelData


@dataclass
class PipelineContext:
    """
    Accumulates intermediate PixelData snapshots as the pipeline runs.

    Each attribute is None until that stage has executed.  The pipeline
    sets them via the snapshot_* helpers, which make a shallow copy of the
    pixels dict so later mutations don't corrupt earlier snapshots.

    Attributes:
        original_pixels:    PixelData right after load_image() — always set.
        quantized_pixels:   PixelData after colour quantization, or None.
        denoised_pixels:    PixelData after blob denoising, or None.
        color_mapping:      Dict mapping detected RGB → filament/CSS RGB,
                            populated by write_3mf() via the preview_mapping
                            return value.  Used to render the matched preview.
    """

    original_pixels: PixelData | None = None
    quantized_pixels: PixelData | None = None
    denoised_pixels: PixelData | None = None
    color_mapping: Dict[Tuple[int, int, int], Tuple[int, int, int]] | None = None

    # ------------------------------------------------------------------ #
    # Snapshot helpers                                                     #
    # ------------------------------------------------------------------ #

    def snapshot_original(self, pixel_data: PixelData) -> None:
        """Store a snapshot of pixel_data as the original (post-load) state."""
        self.original_pixels = _copy_pixel_data(pixel_data)

    def snapshot_quantized(self, pixel_data: PixelData) -> None:
        """Store a snapshot after quantization."""
        self.quantized_pixels = _copy_pixel_data(pixel_data)

    def snapshot_denoised(self, pixel_data: PixelData) -> None:
        """Store a snapshot after denoising."""
        self.denoised_pixels = _copy_pixel_data(pixel_data)

    # ------------------------------------------------------------------ #
    # Convenience: the "most recent" snapshot before colour matching      #
    # ------------------------------------------------------------------ #

    def pre_match_pixels(self) -> PixelData | None:
        """
        Return the last snapshot taken before filament colour matching.

        This is what the right-hand panel of _preview.png should compare
        against — the image as it entered write_3mf(), not the raw original.
        """
        return self.denoised_pixels or self.quantized_pixels or self.original_pixels


# ------------------------------------------------------------------ #
# Preview generation                                                   #
# ------------------------------------------------------------------ #

def generate_previews(
    ctx: PipelineContext,
    output_path: str,
    progress_callback=None,
) -> list[str]:
    """
    Generate all applicable side-by-side preview PNGs from the pipeline context.

    Produces up to three images, each only if the corresponding stage ran:

    * ``{stem}_quantized.png`` — original vs quantized colours
    * ``{stem}_denoised.png``  — previous stage vs denoised colours
    * ``{stem}_preview.png``   — previous stage vs matched filament colours

    The "left panel" of each image is always the state immediately before that
    transformation, so the user can see exactly what each step changed.

    Args:
        ctx:              PipelineContext populated during conversion.
        output_path:      Path to the .3mf output file (used to derive PNG names).
        progress_callback: Optional ``(stage, message)`` callback.

    Returns:
        List of paths to the generated preview files.
    """
    def _progress(msg: str) -> None:
        if progress_callback:
            progress_callback("preview", msg)

    generated: list[str] = []
    stem = output_path.replace('.3mf', '')

    # --- 1. Quantized preview ---
    if ctx.quantized_pixels is not None and ctx.original_pixels is not None:
        path = f"{stem}_quantized.png"
        _progress("Generating quantized preview...")
        _save_side_by_side(
            left=ctx.original_pixels,
            right=ctx.quantized_pixels,
            left_label="Original Colors",
            right_label="After Quantization",
            output_path=path,
        )
        generated.append(path)
        _progress(f"Quantized preview saved to: {path}")

    # --- 2. Denoised preview ---
    if ctx.denoised_pixels is not None:
        path = f"{stem}_denoised.png"
        before = ctx.quantized_pixels or ctx.original_pixels
        assert before is not None  # original_pixels is always set
        _progress("Generating denoised preview...")
        _save_side_by_side(
            left=before,
            right=ctx.denoised_pixels,
            left_label="Before Denoising",
            right_label="After Denoising",
            output_path=path,
        )
        generated.append(path)
        _progress(f"Denoised preview saved to: {path}")

    # --- 3. Matched-filament preview ---
    if ctx.color_mapping is not None:
        path = f"{stem}_preview.png"
        before = ctx.pre_match_pixels()
        assert before is not None
        _progress("Generating colour preview...")
        _save_side_by_side_mapped(
            pixel_data=before,
            color_mapping=ctx.color_mapping,
            left_label="Before Matching",
            right_label="Matched Filament Colors",
            output_path=path,
        )
        generated.append(path)
        _progress(f"Colour preview saved to: {path}")

    return generated


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

def _copy_pixel_data(pixel_data: PixelData) -> PixelData:
    """
    Return a PixelData whose pixels dict is a shallow copy.

    WHY: pixel_data.pixels is mutated in-place during denoising (dict
    values are reassigned).  A shallow copy of the dict is sufficient
    because RGBA tuples are immutable — the copy holds independent
    references to the same immutable tuples, so later reassignments
    to the original dict don't affect the snapshot.
    """
    from .image_processor import PixelData as _PixelData
    return _PixelData(
        width=pixel_data.width,
        height=pixel_data.height,
        pixel_size_mm=pixel_data.pixel_size_mm,
        pixels=dict(pixel_data.pixels),  # shallow copy — tuples are immutable
    )


def _pixels_to_image(pixel_data: PixelData):
    """Render a PixelData to a PIL RGBA Image (Y-flipped for display)."""
    from PIL import Image
    import numpy as np

    arr = np.zeros((pixel_data.height, pixel_data.width, 4), dtype=np.uint8)
    for (x, y), (r, g, b, a) in pixel_data.pixels.items():
        arr[pixel_data.height - 1 - y, x] = (r, g, b, a)
    return Image.fromarray(arr, 'RGBA')


def _save_side_by_side(
    left: PixelData,
    right: PixelData,
    left_label: str,
    right_label: str,
    output_path: str,
) -> None:
    """
    Render two PixelData snapshots as a labelled side-by-side PNG.
    Both panels are drawn at the same (width, height) — the right panel
    uses the same canvas size as the left so the comparison is pixel-perfect.
    """
    from PIL import Image, ImageDraw, ImageFont

    left_img = _pixels_to_image(left)
    right_img = _pixels_to_image(right)

    _write_comparison(left_img, right_img, left_label, right_label, output_path)


def _save_side_by_side_mapped(
    pixel_data: PixelData,
    color_mapping: Dict[Tuple[int, int, int], Tuple[int, int, int]],
    left_label: str,
    right_label: str,
    output_path: str,
) -> None:
    """
    Render the pre-match PixelData alongside its filament-mapped version.
    """
    from PIL import Image
    import numpy as np

    h, w = pixel_data.height, pixel_data.width
    left_arr = np.zeros((h, w, 4), dtype=np.uint8)
    right_arr = np.zeros((h, w, 4), dtype=np.uint8)

    for (x, y), (r, g, b, a) in pixel_data.pixels.items():
        iy = h - 1 - y
        left_arr[iy, x] = (r, g, b, a)
        matched = color_mapping.get((r, g, b), (r, g, b))
        right_arr[iy, x] = (*matched, a)

    left_img = Image.fromarray(left_arr, 'RGBA')
    right_img = Image.fromarray(right_arr, 'RGBA')
    _write_comparison(left_img, right_img, left_label, right_label, output_path)


def _write_comparison(left_img, right_img, left_label: str, right_label: str, output_path: str) -> None:
    """Compose two RGBA images into a labelled side-by-side RGB PNG and save it."""
    from PIL import Image, ImageDraw, ImageFont

    gap = 20
    label_height = 30
    w = left_img.width
    h = left_img.height
    total_width = w * 2 + gap
    total_height = h + label_height

    comparison = Image.new('RGB', (total_width, total_height), (255, 255, 255))
    comparison.paste(left_img, (0, label_height), left_img)
    comparison.paste(right_img, (w + gap, label_height), right_img)

    draw = ImageDraw.Draw(comparison)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for label, x_offset in [(left_label, 0), (right_label, w + gap)]:
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        x = x_offset + (w - text_w) // 2
        draw.text((x, 5), label, fill=(0, 0, 0), font=font)

    comparison.save(output_path)
