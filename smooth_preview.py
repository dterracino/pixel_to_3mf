#!/usr/bin/env python3
"""Standalone CLI for visualising boundary smoothing output.

Runs the boundary smoothing pipeline on a pixel art image and saves the result
as a PNG — optionally side-by-side with the original.  No 3MF generation or
mesh code is involved, making this the ideal tool for tuning the smoothing
parameters before wiring the algorithm into the main application.

Usage
-----
    python smooth_preview.py <input_image> [options]

Examples
--------
    # Basic smoothed output
    python smooth_preview.py samples/input/nes-samus.png

    # Quantise to 8 colours, compare side by side
    python smooth_preview.py samples/input/nes-samus.png --max-colors 8 --side-by-side

    # Tune the smoothing strength
    python smooth_preview.py samples/input/nes-samus.png --tolerance 1.0 --iterations 3

    # Skip filament colour collapse
    python smooth_preview.py samples/input/nes-samus.png --no-collapse
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Preprocessing filters
# ---------------------------------------------------------------------------

def _apply_preprocess(
    img: Image.Image,
    mode: str,
    d: int,
    sigma_color: float,
    sigma_space: float,
) -> Image.Image:
    """Apply a preprocessing filter to the image before quantization.

    Bilateral filter smooths gradient bands (e.g. sky colour dithering) while
    preserving hard edges between distinct colour regions.  Mean-shift is more
    aggressive — it merges spatially-close pixels of similar colour into flat blobs.
    Both reduce the effective colour count before quantization, producing larger
    and cleaner regions for the boundary smoother.

    The filter is applied in RGB space; the alpha channel (if present) is not
    touched and is reattached afterwards.
    """
    try:
        import cv2  # type: ignore[import-untyped]
        import numpy as np
    except ImportError:
        print(
            "ERROR: --preprocess requires opencv-python.\n"
            "  pip install opencv-python-headless",
            file=sys.stderr,
        )
        sys.exit(1)

    has_alpha = img.mode == "RGBA"
    rgb = img.convert("RGB")
    arr = np.array(rgb)

    if mode == "bilateral":
        filtered = cv2.bilateralFilter(arr, d=d, sigmaColor=sigma_color, sigmaSpace=sigma_space)
    elif mode == "meanshift":
        # pyrMeanShiftFiltering uses sp (spatial window) and sr (colour range).
        # We map sigma_space → sp and sigma_color → sr for consistent parameter naming.
        filtered = cv2.pyrMeanShiftFiltering(arr, sp=int(sigma_space), sr=int(sigma_color))
    else:
        return img

    result = Image.fromarray(filtered, "RGB")
    if has_alpha:
        result.putalpha(img.getchannel("A"))
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualise boundary-smoothed pixel art as a PNG image.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_image", help="Path to input pixel art image")
    parser.add_argument(
        "--max-colors", type=int, default=None, metavar="N",
        help="Quantise to N colours before smoothing",
    )
    parser.add_argument(
        "--tolerance", type=float, default=0.5, metavar="FLOAT",
        help="RDP simplification tolerance in pixels (lower = more detail)",
    )
    parser.add_argument(
        "--iterations", type=int, default=2, metavar="N",
        help="Chaikin smoothing iterations (1–4; more = smoother but rounder)",
    )
    parser.add_argument(
        "--blob-min-size", type=int, default=0, metavar="N",
        help="Absorb regions smaller than N pixels into neighbours before smoothing (matches --denoise pipeline step)",
    )
    parser.add_argument(
        "--no-collapse", action="store_true",
        help="Skip the filament colour collapse step",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output PNG path (default: <input>_smoothed.png)",
    )
    parser.add_argument(
        "--svg", action="store_true",
        help="Also write an SVG file alongside the PNG (same base name, .svg extension)",
    )
    parser.add_argument(
        "--side-by-side", action="store_true",
        help="Render original and smoothed images side by side for comparison",
    )
    parser.add_argument(
        "--scale", type=int, default=4, metavar="N",
        help="Integer upscale factor applied to both output images for clarity",
    )
    parser.add_argument(
        "--preprocess", choices=["none", "bilateral", "meanshift"], default="none",
        help="Apply a pre-quantization filter to flatten gradient regions (requires opencv-python-headless)",
    )
    parser.add_argument(
        "--sigma-color", type=float, default=60.0, metavar="FLOAT",
        help="Bilateral/meanshift colour sigma — how different two colours can be and still get blended (25=tight, 60=medium, 100=loose)",
    )
    parser.add_argument(
        "--sigma-space", type=float, default=60.0, metavar="FLOAT",
        help="Bilateral/meanshift spatial sigma — neighbourhood radius in pixels (25=local, 60=medium, 100=wide)",
    )
    parser.add_argument(
        "--bilateral-d", type=int, default=9, metavar="N",
        help="Bilateral filter pixel neighbourhood diameter (must be odd; 9=standard, 15=stronger)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_image)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(input_path.stem + "_smoothed.png")
    )

    # ------------------------------------------------------------------
    # Build a minimal ConversionConfig
    # ------------------------------------------------------------------
    from pixel_to_3mf.config import ConversionConfig

    config = ConversionConfig(
        quantize=args.max_colors is not None,
        quantize_colors=args.max_colors,
        quantize_algo="none",
        auto_crop=False,
        max_size_mm=200.0,
        # Raise the colour limit so load_image() doesn't warn on large palettes.
        max_colors=args.max_colors if args.max_colors else 256,
        no_backing_color=True,
    )

    # Smoothing params are not yet fields on ConversionConfig — attach them
    # directly. boundary_smoother.py reads them via getattr() with fallback defaults.
    config.smooth_simplify_tolerance = args.tolerance  # type: ignore[attr-defined]
    config.smooth_chaikin_iterations = args.iterations  # type: ignore[attr-defined]
    config.smooth_min_area_px = 0.0                    # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Optional preprocessing: apply image filter before quantization
    # ------------------------------------------------------------------
    load_path = str(input_path)
    _tmp_file = None
    if args.preprocess != "none":
        print(f"Preprocessing ({args.preprocess}, sigma_color={args.sigma_color}, sigma_space={args.sigma_space})...")
        raw_img = Image.open(input_path)
        filtered_img = _apply_preprocess(
            raw_img,
            mode=args.preprocess,
            d=args.bilateral_d,
            sigma_color=args.sigma_color,
            sigma_space=args.sigma_space,
        )
        _tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        filtered_img.save(_tmp.name)
        _tmp.close()
        _tmp_file = _tmp.name
        load_path = _tmp_file
        print(f"  Filtered image saved to temp file for quantization")

    # ------------------------------------------------------------------
    # Pipeline: load → region merge → smooth → (collapse) → render
    # ------------------------------------------------------------------
    print(f"Loading {input_path.name}...")
    from pixel_to_3mf.image_processor import load_image

    pixel_data = load_image(load_path, config)
    unique_colors = len(pixel_data.get_unique_colors())
    print(f"  {pixel_data.width}×{pixel_data.height} pixels, {unique_colors} unique colours")

    if args.blob_min_size > 0:
        print(f"Denoising (blob-min-size={args.blob_min_size})...")
        from pixel_to_3mf.region_merger import denoise_blob_pixels
        pixel_data.pixels = denoise_blob_pixels(pixel_data.pixels, args.blob_min_size)
        unique_after = len({v[:3] for v in pixel_data.pixels.values()})
        print(f"  {unique_after} unique colours after denoise")

    print("Merging regions...")
    from pixel_to_3mf.region_merger import merge_regions

    regions = merge_regions(pixel_data, config)
    print(f"  {len(regions)} regions")

    print(
        f"Smoothing boundaries "
        f"(tolerance={args.tolerance}, iterations={args.iterations})..."
    )
    from pixel_to_3mf.boundary_smoother import (
        collapse_by_filament_color,
        smooth_region_boundaries,
    )

    smoothed = smooth_region_boundaries(regions, pixel_data, config)
    print(f"  {len(smoothed)} smoothed regions")

    if not args.no_collapse:
        print("Collapsing by filament colour...")
        smoothed = collapse_by_filament_color(smoothed, config)
        print(f"  {len(smoothed)} regions after collapse")

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    scale = args.scale
    width = pixel_data.width
    height = pixel_data.height

    print("Rendering smoothed image...")
    smoothed_img = _render_smoothed(smoothed, width, height, scale)

    if args.side_by_side:
        print("Rendering original image...")
        original_img = _render_original(pixel_data, scale)
        final = _side_by_side(original_img, smoothed_img)
    else:
        final = smoothed_img

    final.save(str(output_path))
    print(f"Saved → {output_path}")

    if args.svg:
        svg_path = output_path.with_suffix(".svg")
        _write_svg(smoothed, pixel_data.width, pixel_data.height, svg_path)
        print(f"Saved → {svg_path}")

    # Clean up temp file created by preprocessing
    if _tmp_file:
        import os
        try:
            os.unlink(_tmp_file)
        except OSError:
            pass

    return 0


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_smoothed(
    regions: list,
    width: int,
    height: int,
    scale: int,
) -> Image.Image:
    """Render smoothed ShapelyPolygon regions to a PIL Image.

    Pixel-space has Y=0 at the bottom (matching the 3D coordinate convention used
    throughout the pipeline). Image space has Y=0 at the top, so we flip with:
        img_y = (height - poly_y) * scale
    """
    img = Image.new("RGB", (width * scale, height * scale), (180, 180, 180))
    draw = ImageDraw.Draw(img)

    def _to_img(x: float, y: float) -> tuple[float, float]:
        return x * scale, (height - y) * scale

    # Draw largest regions first so they act as background. Sub-pixel-area polygons
    # (< 1 px²) may not fill any PIL pixels; with largest-first ordering the
    # neighbouring region's colour shows through rather than the grey background.
    sorted_regions = sorted(regions, key=lambda r: r.polygon.area, reverse=True)

    for region in sorted_regions:
        poly = region.polygon
        fill: tuple[int, int, int] = region.color

        exterior = [_to_img(x, y) for x, y in poly.exterior.coords]
        if len(exterior) >= 3:
            # outline=fill fills the 1-pixel boundary strip, which prevents the
            # tiny corner gaps that Chaikin corner-cutting creates at junctions
            # where three or more coloured regions meet.
            draw.polygon(exterior, fill=fill, outline=fill)

        # Draw holes (interiors) back in the background colour.
        for interior in poly.interiors:
            hole = [_to_img(x, y) for x, y in interior.coords]
            if len(hole) >= 3:
                draw.polygon(hole, fill=(180, 180, 180), outline=(180, 180, 180))

    return img


def _render_original(pixel_data, scale: int) -> Image.Image:
    """Render the original pixels as an upscaled blocky image.

    PixelData stores pixels with Y-flipped coordinates (Y=0 at bottom).
    To render to image space (Y=0 at top), use img_y = height - 1 - py.
    """
    width = pixel_data.width
    height = pixel_data.height
    img = Image.new("RGB", (width * scale, height * scale), (180, 180, 180))
    draw = ImageDraw.Draw(img)

    for (px, py), rgba in pixel_data.pixels.items():
        r, g, b = rgba[0], rgba[1], rgba[2]
        img_y = height - 1 - py
        x0 = px * scale
        y0 = img_y * scale
        x1 = x0 + scale - 1
        y1 = y0 + scale - 1
        draw.rectangle([x0, y0, x1, y1], fill=(r, g, b))

    return img


def _side_by_side(left: Image.Image, right: Image.Image) -> Image.Image:
    """Combine two images side by side with a thin grey divider."""
    gap = 6
    w = left.width + gap + right.width
    h = max(left.height, right.height)
    combined = Image.new("RGB", (w, h), (100, 100, 100))
    combined.paste(left, (0, 0))
    combined.paste(right, (left.width + gap, 0))
    return combined


def _write_svg(regions: list, width: int, height: int, path) -> None:
    """Write smoothed regions as an SVG file.

    Each SmoothedRegion is output as an SVG <path> element filled with the
    region's RGB colour.  The coordinate system matches PIL image space
    (Y increases downward), so we flip Y when writing to SVG (SVG also uses
    Y-down, same as PIL, so no flip is actually needed).  The viewBox matches
    the pixel dimensions exactly so the SVG can be opened at 1px-per-unit.
    """
    from shapely.geometry import MultiPolygon

    def _ring_to_d(coords) -> str:
        pts = list(coords)
        if not pts:
            return ""
        d = f"M {pts[0][0]:.3f},{pts[0][1]:.3f}"
        for x, y in pts[1:]:
            d += f" L {x:.3f},{y:.3f}"
        d += " Z"
        return d

    def _poly_to_d(poly) -> str:
        parts = [_ring_to_d(poly.exterior.coords)]
        for interior in poly.interiors:
            parts.append(_ring_to_d(interior.coords))
        return " ".join(parts)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
    ]
    # Draw largest regions first so smaller ones are not buried beneath them.
    sorted_regions = sorted(regions, key=lambda r: r.polygon.area, reverse=True)
    for region in sorted_regions:
        r, g, b = region.color[:3]
        fill = f"#{r:02x}{g:02x}{b:02x}"
        poly = region.polygon
        geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        for geom in geoms:
            d = _poly_to_d(geom)
            if d:
                lines.append(f'  <path d="{d}" fill="{fill}" stroke="none"/>')
    lines.append("</svg>")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
