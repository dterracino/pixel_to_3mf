#!/usr/bin/env python3
"""Standalone preview for morphological pixel art region smoothing.

Loads a pixel art image, applies ``morph_smoother.smooth_pixel_regions()``,
and saves a side-by-side comparison PNG so the smoothing effect can be
evaluated visually before wiring it into the full pipeline.

Usage
-----
::

    python morph_preview.py <input_image> [options]

Examples
--------
::

    python morph_preview.py samples/input/duckhunt-nes.png --radius 1.5

    python morph_preview.py samples/input/large/sf2_ryu_level.png \\
        --max-colors 12 --radius 2.0 --scale 3

    python morph_preview.py samples/input/cute-pixel-frog.png \\
        --radius 1.0 --scale 6 --output frog_morph.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _pixel_data_to_pil(pixel_data, scale: int = 1) -> Image.Image:
    """Render a PixelData to a PIL RGB image with optional integer upscale.

    Transparent positions (absent from pixel_data.pixels) are rendered as
    mid-grey so gaps are visible against both light and dark content.
    """
    pw = pixel_data.width * scale
    ph = pixel_data.height * scale
    img = Image.new("RGB", (pw, ph), (180, 180, 180))
    draw = ImageDraw.Draw(img)
    for (x, y), rgba in pixel_data.pixels.items():
        # Y-flip: PixelData y=0 is at the bottom; PIL y=0 is at the top.
        px = x * scale
        py = (pixel_data.height - 1 - y) * scale
        rgb = (rgba[0], rgba[1], rgba[2])
        if scale == 1:
            img.putpixel((px, py), rgb)
        else:
            draw.rectangle([px, py, px + scale - 1, py + scale - 1], fill=rgb)
    return img


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Morphological pixel art smoothing — side-by-side preview",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_image", help="Path to input pixel art image")
    parser.add_argument(
        "--radius",
        type=float,
        default=1.5,
        help="Erosion radius in pixels. 1.5 preserves features ≥3 px wide.",
    )
    parser.add_argument(
        "--max-colors",
        type=int,
        default=None,
        metavar="N",
        help="Quantize to N colours before smoothing (mirrors the main pipeline).",
    )
    parser.add_argument(
        "--quantize-colors",
        type=int,
        default=None,
        metavar="N",
        help="Start quantization at N colours and iterate down to --max-colors. "
             "Use when --max-colors alone produces a poor palette.",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=3,
        help="Integer upscale factor for the output PNG.",
    )
    parser.add_argument(
        "--output",
        help="Output PNG path. Defaults to <input>_morph.png in the same directory.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_image)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_morph.png"
    )

    # ------------------------------------------------------------------
    # Load image through the normal pipeline so quantization, auto-crop,
    # and Y-flip all happen exactly as they would in a real conversion.
    # ------------------------------------------------------------------
    from pixel_to_3mf.config import ConversionConfig
    from pixel_to_3mf.image_processor import load_image
    from pixel_to_3mf.morph_smoother import smooth_pixel_regions

    config = ConversionConfig()
    if args.max_colors is not None:
        # Add 1 extra slot for the backing-colour reservation so that an image
        # with exactly N unique colours never triggers the "N > max_colors - 1"
        # validation error in load_image().
        config.max_colors = args.max_colors + 1
        config.quantize = True
        config.quantize_colors = args.quantize_colors if args.quantize_colors else args.max_colors
        config.iterate_quantize = args.quantize_colors is not None
    else:
        # Set a generous limit so validation never rejects the image.
        config.max_colors = 1024

    print(f"Loading {input_path.name} ...")
    pixel_data = load_image(str(input_path), config)
    before_colors = len(pixel_data.get_unique_colors())
    print(f"  {pixel_data.width}×{pixel_data.height}, {before_colors} colour(s)")

    print(f"Smoothing (radius={args.radius}) ...")
    smoothed = smooth_pixel_regions(pixel_data, radius=args.radius)
    after_colors = len(smoothed.get_unique_colors())
    print(f"  Done — {after_colors} colour(s) remain after smoothing")

    if after_colors < before_colors:
        removed = before_colors - after_colors
        print(f"  {removed} colour(s) eroded away and absorbed by neighbours")

    print(f"Rendering side-by-side at {args.scale}× ...")
    before_img = _pixel_data_to_pil(pixel_data, scale=args.scale)
    after_img = _pixel_data_to_pil(smoothed, scale=args.scale)

    gap = 6
    combined = Image.new(
        "RGB",
        (before_img.width + gap + after_img.width, max(before_img.height, after_img.height)),
        (60, 60, 60),
    )
    combined.paste(before_img, (0, 0))
    combined.paste(after_img, (before_img.width + gap, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.save(str(output_path))
    print(f"Saved → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
