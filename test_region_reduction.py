#!/usr/bin/env python3
"""
Region Reduction Test Script

Tests three approaches for reducing the region (segment) count in pixel art
images before converting to 3MF:

  Blob denoise
      Region-aware filter.  Flood-fills to find every connected same-colour
      region, then iteratively merges any region smaller than *min_size* into
      its dominant neighbour colour.  Only removes isolated blobs; large region
      edges are untouched.

  Mode window
      Pixel-level sliding-window filter.  Each pixel is replaced with the most
      common colour in its K×K neighbourhood.  Operates entirely within the
      original palette (never creates new colours).  Smooths jagged edges on
      large regions in addition to absorbing isolated pixels.  Uses an integral
      image per palette entry for O(h·w·n_colors) computation.

  NN downscale
      Nearest-neighbour resampling at a fractional scale.  NN is the only
      algorithm that preserves hard pixel edges without blending.  Reduces
      region count by shrinking the image.

Usage:
    python test_region_reduction.py
    python test_region_reduction.py path/to/image.png
    python test_region_reduction.py path/to/image.png -o samples/test/rr
    python test_region_reduction.py --iterate-quantize --quantize-colors 32

Output:
    • A formatted statistics table printed to stdout.
    • For each variant: a standalone PNG and a side-by-side comparison PNG.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Set, Tuple

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from skimage.metrics import structural_similarity as _ssim_fn
    HAVE_SSIM = True
except ImportError:
    HAVE_SSIM = False

# ── project root on sys.path so we can import pixel_to_3mf ──────────────────
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from pixel_to_3mf.region_merger import Region, flood_fill, merge_regions
from pixel_to_3mf.image_processor import load_image
from pixel_to_3mf.config import ConversionConfig

# ── test parameters ───────────────────────────────────────────────────────────
DEFAULT_IMAGE   = PROJECT_ROOT / "samples" / "input" / "large" / "sf2_ryu_level.png"
DEFAULT_OUT_DIR = PROJECT_ROOT / "samples" / "test" / "region_reduction"

BLOB_MIN_SIZES:    list[int]   = [2, 4, 8, 16, 32, 64]
MODE_KERNEL_SIZES: list[int]   = [3, 5, 7, 9, 13, 21]
RADIANT_RADII:     list[int]   = [1, 2, 3, 5, 7, 10]
DOWNSCALE_FACTORS: list[float] = [0.75, 0.50, 0.33, 0.25]

# ── preview constants ─────────────────────────────────────────────────────────
DEFAULT_ZOOM  = 3        # nearest-neighbour upscale so pixels are legible
HEADER_H      = 26       # height of text label row in each panel
PANEL_PAD     = 6        # padding inside each panel
BG_COLOR      = (30,  30,  30,  255)
DIVIDER_COLOR = (80,  80,  80,  255)
TEXT_COLOR    = (220, 220, 220, 255)

# ── 8-connected offsets (used by blob denoiser) ───────────────────────────────
_OFFSETS_8 = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]

# ── disk offset cache (used by radiant denoiser) ────────────────────────────
_DISK_OFFSETS_CACHE: dict[int, list[tuple[int, int]]] = {}


def _disk_offsets(radius: int) -> list[tuple[int, int]]:
    """Return all (dx, dy) offsets within Euclidean distance *radius* (cached)."""
    if radius not in _DISK_OFFSETS_CACHE:
        offsets = [
            (dx, dy)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if dx * dx + dy * dy <= radius * radius
        ]
        _DISK_OFFSETS_CACHE[radius] = offsets
    return _DISK_OFFSETS_CACHE[radius]

PixelDict = Dict[Tuple[int, int], Tuple[int, int, int, int]]


# ═══════════════════════════════════════════════════════════════════════════════
# Image ↔ pixel-dict helpers
# ═══════════════════════════════════════════════════════════════════════════════

def image_to_pixel_dict(img: Image.Image) -> PixelDict:
    """Convert an RGBA PIL Image to {(x, y): (r,g,b,a)}, skipping transparent pixels."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    ys, xs = np.where(arr[:, :, 3] > 0)
    pixels: PixelDict = {}
    for y, x in zip(ys.tolist(), xs.tolist()):
        r, g, b, a = arr[y, x]
        pixels[(int(x), int(y))] = (int(r), int(g), int(b), int(a))
    return pixels


def pixel_dict_to_image(pixels: PixelDict, width: int, height: int) -> Image.Image:
    """Reconstruct a PIL RGBA image from a pixel dict."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for (x, y), (r, g, b, a) in pixels.items():
        arr[y, x] = (r, g, b, a)
    return Image.fromarray(arr, "RGBA")


def flip_v(img: Image.Image) -> Image.Image:
    """Flip an image vertically to restore Y=0-at-top display orientation."""
    return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


# ═══════════════════════════════════════════════════════════════════════════════
# Region counting
# ═══════════════════════════════════════════════════════════════════════════════

def get_regions(pixels: PixelDict, connectivity: int = 8) -> list[Region]:
    """Flood-fill all pixels and return every connected same-colour region."""
    regions: list[Region] = []
    visited: Set[Tuple[int, int]] = set()
    for (x, y), rgba in pixels.items():
        if (x, y) in visited:
            continue
        color = (rgba[0], rgba[1], rgba[2])
        region_pixels = flood_fill(x, y, color, pixels, visited, connectivity=connectivity)
        regions.append(Region(color=color, pixels=region_pixels))
    return regions


def region_count(img: Image.Image, connectivity: int = 8) -> int:
    return len(get_regions(image_to_pixel_dict(img), connectivity))


# ═══════════════════════════════════════════════════════════════════════════════
# Filter algorithms
# ═══════════════════════════════════════════════════════════════════════════════

def denoise_blob(pixels: PixelDict, min_region_size: int, connectivity: int = 8) -> PixelDict:
    """
    Region-aware blob denoiser.

    Iteratively merges every connected same-colour region with fewer than
    *min_region_size* pixels into the most common colour found along its
    boundary.  Processes smallest blobs first so lone pixels are absorbed
    before slightly-larger ones, producing more natural results.

    Repeats until no undersized regions remain, or no further progress is
    possible (safety valve for fully-isolated islands).
    """
    working = dict(pixels)

    while True:
        regions = get_regions(working, connectivity)
        small   = [r for r in regions if len(r.pixels) < min_region_size]

        if not small:
            break

        small.sort(key=lambda r: len(r.pixels))
        changed = False

        for region in small:
            neighbour_colours: list[Tuple[int, int, int]] = []
            for x, y in region.pixels:
                for dx, dy in _OFFSETS_8:
                    nb = (x + dx, y + dy)
                    if nb in working:
                        nc = working[nb][:3]
                        if nc != region.color:
                            neighbour_colours.append(nc)

            if not neighbour_colours:
                continue   # fully isolated island — skip

            replacement = Counter(neighbour_colours).most_common(1)[0][0]
            for x, y in region.pixels:
                a = working[(x, y)][3]
                working[(x, y)] = (replacement[0], replacement[1], replacement[2], a)

            changed = True

        if not changed:
            break

    return working


def mode_window(img: Image.Image, kernel_size: int) -> Image.Image:
    """
    Sliding-window mode filter: replace each pixel with the most common colour
    in its K×K neighbourhood.

    Palette-safe: only ever produces colours already present in the image, so
    region counting after filtering stays meaningful.  Smooths jagged edges on
    large regions as well as absorbing isolated noise pixels — complementary to
    the blob denoiser which only removes small blobs.

    Uses an integral image (summed-area table) per palette entry so the window
    sum at every pixel is computed in O(1) after O(h·w) preprocessing, giving
    total complexity O(h·w·n_colors) rather than O(h·w·k²·n_colors).

    Integral image formula for window sum over padded[y:y+k, x:x+k]:
        sum = I[y+k, x+k] − I[y, x+k] − I[y+k, x] + I[y, x]
    where I[r, c] = Σ padded[0:r, 0:c]  (exclusive upper bound, zero-padded).
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    k    = kernel_size
    pad  = k // 2

    rgb   = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Palette: unique opaque colours present in the image
    opaque_rgb    = rgb[alpha > 0]
    unique_colors = np.unique(opaque_rgb.reshape(-1, 3), axis=0)   # (n, 3)
    n_colors      = len(unique_colors)

    if n_colors == 0:
        return img.copy()

    votes      = np.zeros((h, w, n_colors), dtype=np.int32)
    ph, pw     = h + 2 * pad, w + 2 * pad

    for i, color in enumerate(unique_colors):
        mask     = np.all(rgb == color, axis=2).astype(np.float32)
        padded   = np.pad(mask, pad, mode="edge")

        # Integral image: I[r, c] = sum of padded[0:r, 0:c]
        integral            = np.zeros((ph + 1, pw + 1), dtype=np.float32)
        integral[1:, 1:]    = np.cumsum(np.cumsum(padded, axis=0), axis=1)

        # Vectorised window sum for all (y, x) simultaneously
        votes[:, :, i] = (
            integral[k : k + h,  k : k + w]
          - integral[0 : h,      k : k + w]
          - integral[k : k + h,  0 : w    ]
          + integral[0 : h,      0 : w    ]
        ).astype(np.int32)

    winner_idx     = votes.argmax(axis=2)       # (h, w)
    output_rgb     = unique_colors[winner_idx]  # (h, w, 3)

    out             = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, :3]   = output_rgb
    out[:, :, 3]    = alpha
    return Image.fromarray(out, "RGBA")


def nn_downscale(img: Image.Image, scale: float) -> Image.Image:
    """Resize by *scale* using nearest-neighbour resampling (palette-safe)."""
    new_w = max(1, round(img.width  * scale))
    new_h = max(1, round(img.height * scale))
    return img.resize((new_w, new_h), Image.Resampling.NEAREST)


def radiant_denoise(img: Image.Image, radius: int) -> Image.Image:
    """
    Radiant denoiser: circular neighbourhood mode filter with outlier-only
    replacement.

    For every opaque pixel, gather all pixels within Euclidean distance
    *radius* (a disk, not a square).  Find the mode colour among those
    neighbours.  Only replace the pixel if it does NOT already match the
    local mode — i.e. it is an outlier.  Pixels that agree with their
    neighbourhood are left completely untouched.

    This is more conservative than the square mode_window filter:
    - Circular neighbourhood avoids axis bias (diagonal neighbors are
      weighted fairly by distance).
    - Outlier-only replacement means edges between large regions are
      preserved; only isolated pixels that disagree with their surroundings
      are corrected.

    The vote map per colour is built by accumulating shifted binary masks
    over all disk offsets — equivalent to a manual 2D convolution with a
    disk kernel, using only NumPy without scipy.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr   = np.array(img)
    h, w  = arr.shape[:2]
    rgb   = arr[:, :, :3]
    alpha = arr[:, :, 3]

    opaque_rgb    = rgb[alpha > 0]
    unique_colors = np.unique(opaque_rgb.reshape(-1, 3), axis=0)
    n_colors      = len(unique_colors)

    if n_colors == 0:
        return img.copy()

    offsets = _disk_offsets(radius)
    votes   = np.zeros((h, w, n_colors), dtype=np.int32)

    for i, color in enumerate(unique_colors):
        mask     = np.all(rgb == color, axis=2).astype(np.int32)
        vote_map = np.zeros((h, w), dtype=np.int32)
        for dx, dy in offsets:
            # Shift mask by (dx, dy) and accumulate into vote_map
            src_y0 = max(0, -dy);  src_y1 = h - max(0, dy)
            src_x0 = max(0, -dx);  src_x1 = w - max(0, dx)
            dst_y0 = max(0,  dy);  dst_y1 = h - max(0, -dy)
            dst_x0 = max(0,  dx);  dst_x1 = w - max(0, -dx)
            vote_map[dst_y0:dst_y1, dst_x0:dst_x1] += mask[src_y0:src_y1, src_x0:src_x1]
        votes[:, :, i] = vote_map

    winner_idx = votes.argmax(axis=2)       # (h, w)
    winner_rgb = unique_colors[winner_idx]  # (h, w, 3)

    # Outlier-only: only replace pixels that disagree with their local mode
    out        = arr.copy()
    is_outlier = ~np.all(rgb == winner_rgb, axis=2) & (alpha > 0)
    out[is_outlier, :3] = winner_rgb[is_outlier]
    return Image.fromarray(out, "RGBA")


# ═══════════════════════════════════════════════════════════════════════════════
# Image quality metrics
# ═══════════════════════════════════════════════════════════════════════════════

def compare_images(ref: Image.Image, result: Image.Image) -> dict[str, float]:
    """
    Compute image quality metrics for *result* relative to *ref*.

    If the images differ in size (e.g. a downscaled result), *result* is
    NN-upsampled back to *ref*'s dimensions before comparison, so all metrics
    are expressed at the original resolution — i.e. how blocky/lossy does the
    downscaled image look when scaled back up?

    Returns dict with keys:
        pct_changed  — % of pixels that differ at all (any channel)
        psnr         — Peak Signal-to-Noise Ratio in dB (higher = more similar)
        ssim         — Structural Similarity Index 0–1 (higher = more similar,
                       nan if scikit-image is not installed)
        composite    — Weighted quality score 0–1 (pixel-art preset):
                         SSIM×0.45 + (1−%Chg/100)×0.35 + min(PSNR,50)/50×0.20
                       Falls back to PSNR+%Chg only when SSIM unavailable.
    """
    if result.size != ref.size:
        result = result.resize(ref.size, Image.Resampling.NEAREST)

    ref_arr = np.array(ref.convert("RGB"))
    res_arr = np.array(result.convert("RGB"))

    # % pixels changed
    changed     = np.any(ref_arr != res_arr, axis=2)
    pct_changed = float(np.sum(changed)) / float(changed.size) * 100.0

    # PSNR  (computed on uint8 0-255 range)
    mse      = float(np.mean((ref_arr.astype(np.float32) - res_arr.astype(np.float32)) ** 2))
    psnr_val = math.inf if mse == 0.0 else 10.0 * math.log10(255.0 ** 2 / mse)

    # SSIM (optional)
    if HAVE_SSIM:
        ref_f    = ref_arr.astype(np.float32) / 255.0
        res_f    = res_arr.astype(np.float32) / 255.0
        ssim_val = float(_ssim_fn(ref_f, res_f, channel_axis=2, data_range=1.0))
    else:
        ssim_val = float("nan")

    # Composite — pixel-art preset weights
    psnr_norm = 1.0 if math.isinf(psnr_val) else min(psnr_val, 50.0) / 50.0
    pct_norm  = 1.0 - pct_changed / 100.0
    if not math.isnan(ssim_val):
        composite = 0.45 * ssim_val + 0.35 * pct_norm + 0.20 * psnr_norm
    else:
        # fallback without SSIM: redistribute weights proportionally
        composite = 0.64 * pct_norm + 0.36 * psnr_norm

    return {"pct_changed": pct_changed, "psnr": psnr_val, "ssim": ssim_val, "composite": composite}


# ═══════════════════════════════════════════════════════════════════════════════
# Preview helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _get_font(size: int = 11) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_comparison(
    left_img:    Image.Image,
    right_img:   Image.Image,
    left_label:  str,
    right_label: str,
    zoom:        int = DEFAULT_ZOOM,
) -> Image.Image:
    """
    Build a side-by-side comparison image.

    Both images are zoomed up by *zoom* using nearest-neighbour so individual
    pixels remain crisp.  If the right image is smaller (e.g. a downscaled
    result), it sits in the top-left of the right panel with the remaining
    area filled by the background colour, making the size reduction visible.
    """
    lw = left_img.width  * zoom
    lh = left_img.height * zoom
    rw = right_img.width * zoom
    rh = right_img.height * zoom

    left_scaled  = left_img.resize( (lw, lh), Image.Resampling.NEAREST)
    right_scaled = right_img.resize((rw, rh), Image.Resampling.NEAREST)

    panel_w = max(lw, rw) + 2 * PANEL_PAD
    panel_h = max(lh, rh) + HEADER_H + 2 * PANEL_PAD
    total_w = panel_w * 2 + 1   # +1 for the divider line
    total_h = panel_h

    canvas = Image.new("RGBA", (total_w, total_h), BG_COLOR)
    draw   = ImageDraw.Draw(canvas)
    font   = _get_font(11)

    # Vertical divider
    draw.line([(panel_w, 0), (panel_w, total_h - 1)], fill=DIVIDER_COLOR)

    # Left panel
    draw.text((PANEL_PAD, PANEL_PAD), left_label, fill=TEXT_COLOR, font=font)
    canvas.paste(left_scaled, (PANEL_PAD, HEADER_H + PANEL_PAD), left_scaled)

    # Right panel
    rx = panel_w + 1 + PANEL_PAD
    draw.text((rx, PANEL_PAD), right_label, fill=TEXT_COLOR, font=font)
    canvas.paste(right_scaled, (rx, HEADER_H + PANEL_PAD), right_scaled)

    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
# Table output
# ═══════════════════════════════════════════════════════════════════════════════

_W       = 124
_COL     = "{:<40} {:>8} {:>10} {:>6} {:>6} {:>7} {:>8} {:>6} {:>7} {:>6} {:>6}"
_HEADER  = _COL.format("Variant", "Regions", "Reduction", "Width", "Height", "%Chg", "PSNR", "SSIM", "Score", "Pass?", "Time")
_DIVIDER = "─" * _W


def _pct(baseline: int, current: int) -> str:
    if current == baseline:
        return "baseline"
    pct  = (baseline - current) / baseline * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _fmt_metrics(m: dict[str, float]) -> tuple[str, str, str, str]:
    """Format metric dict values as display strings."""
    pct_chg   = m.get("pct_changed", float("nan"))
    psnr      = m.get("psnr",        float("nan"))
    ssim      = m.get("ssim",        float("nan"))
    composite = m.get("composite",   float("nan"))

    pct_str   = f"{pct_chg:.1f}%"   if not math.isnan(pct_chg)   else "N/A"
    psnr_str  = "inf"               if math.isinf(psnr)           else (f"{psnr:.1f}" if not math.isnan(psnr) else "N/A")
    ssim_str  = f"{ssim:.3f}"       if not math.isnan(ssim)       else "N/A"
    score_str = f"{composite:.3f}"  if not math.isnan(composite)  else "N/A"

    return pct_str, psnr_str, ssim_str, score_str


_BASELINE_METRICS: dict[str, float] = {
    "pct_changed": 0.0,
    "psnr":        math.inf,
    "ssim":        1.0 if HAVE_SSIM else float("nan"),
    "composite":   1.0,
}


def print_row(
    name:     str,
    regions:  int,
    baseline: int,
    w: int,
    h: int,
    metrics:  dict[str, float],
    t:        float,
    threshold: float = 0.80,
) -> None:
    pct_str, psnr_str, ssim_str, score_str = _fmt_metrics(metrics)
    composite = metrics.get("composite", float("nan"))
    if math.isnan(composite):
        pass_str = "---"
    elif composite >= threshold:
        pass_str = "YES"
    else:
        pass_str = "NO"
    print(_COL.format(
        name, f"{regions:,}", _pct(baseline, regions),
        w, h, pct_str, psnr_str, ssim_str, score_str, pass_str, f"{t:.1f}s",
    ))


def print_section(title: str) -> None:
    fill = _W - len(title) - 4
    print(f"\n── {title} {'─' * max(0, fill)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test region-reduction techniques on a pixel art image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("image",              nargs="?",       default=str(DEFAULT_IMAGE))
    parser.add_argument("--output",    "-o",  default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-colors", "-m", type=int,        default=16)
    parser.add_argument("--quantize-colors", "-q", type=int,   default=None,
                        help="Starting quantize-colors (default: same as --max-colors)")
    parser.add_argument("--iterate-quantize", "-i", action="store_true",
                        help="Mirror --iterate-quantize from the converter")
    parser.add_argument("--connectivity", "-c", type=int,      default=8, choices=[4, 8])
    parser.add_argument("--zoom",        "-z", type=int,       default=DEFAULT_ZOOM,
                        help=f"Preview zoom factor (default: {DEFAULT_ZOOM})")
    parser.add_argument("--no-blob",      action="store_true", help="Skip blob denoising")
    parser.add_argument("--no-radiant",   action="store_true", help="Skip radiant denoising")
    parser.add_argument("--no-mode",      action="store_true", help="Skip mode window")
    parser.add_argument("--no-downscale", action="store_true", help="Skip downscale")
    parser.add_argument("--threshold",   "-t", type=float, default=0.80,
                        help="Composite score threshold for Pass/Fail column (default: 0.80)")
    args = parser.parse_args()

    image_path = Path(args.image)
    output_dir = Path(args.output)
    conn       = args.connectivity
    zoom       = args.zoom
    threshold  = args.threshold

    if not image_path.exists():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── load via the real converter pipeline ──────────────────────────────────
    print(f"\nSource image : {image_path.resolve()}")
    raw_img = Image.open(image_path).convert("RGBA")
    print(f"Dimensions   : {raw_img.width} × {raw_img.height} px")

    max_colors      = args.max_colors
    quantize_colors = args.quantize_colors if args.quantize_colors is not None else max_colors
    iterate         = args.iterate_quantize

    cfg = ConversionConfig(
        max_colors       = max_colors,
        quantize         = True,
        quantize_colors  = quantize_colors,
        iterate_quantize = iterate,
        connectivity     = conn,
        skip_checks      = True,
        batch_mode       = True,
        no_backing_color = True,
    )

    quant_label = f"{quantize_colors}→{max_colors} (iterate)" if iterate else str(max_colors)
    print(f"Quantizing   : {quant_label} colors  ← matches converter pipeline")

    t0               = time.perf_counter()
    pixel_data       = load_image(str(image_path), cfg)
    baseline_regions = merge_regions(pixel_data, cfg)
    t_baseline       = time.perf_counter() - t0

    baseline     = len(baseline_regions)
    n_unique     = len({rgba[:3] for rgba in pixel_data.pixels.values()})
    img_w, img_h = pixel_data.width, pixel_data.height

    print(f"Unique colors: {n_unique:,} (after quantization)")
    print(f"Output dir   : {output_dir.resolve()}")
    print(f"Connectivity : {conn}\n")

    # pixel_data.pixels uses Y-flipped coords (Y=0 at bottom, matching 3D space).
    # work_img is therefore upside-down relative to the source.  Region counts
    # are identical regardless of orientation; flip_v() restores correct display
    # orientation when saving previews.
    work_img         = pixel_dict_to_image(pixel_data.pixels, img_w, img_h)
    display_baseline = flip_v(work_img)

    raw_img.save(output_dir / "00_original_raw.png")
    display_baseline.save(output_dir / "00_baseline_quantized.png")

    baseline_label = f"Baseline  {baseline:,} regions  {img_w}×{img_h}px"

    # ── table header ──────────────────────────────────────────────────────────
    print(_DIVIDER)
    print(_HEADER)
    print(_DIVIDER)
    print_row("Original (baseline)", baseline, baseline, img_w, img_h, _BASELINE_METRICS, t_baseline, threshold)

    # ── Blob denoising ────────────────────────────────────────────────────────
    if not args.no_blob:
        print_section("Blob denoise  (merge small regions into dominant neighbour)")
        for idx, min_size in enumerate(BLOB_MIN_SIZES, 1):
            t0          = time.perf_counter()
            denoised_px = denoise_blob(image_to_pixel_dict(work_img), min_size, conn)
            regions     = len(get_regions(denoised_px, conn))
            elapsed     = time.perf_counter() - t0

            result_img  = flip_v(pixel_dict_to_image(denoised_px, img_w, img_h))
            metrics     = compare_images(display_baseline, result_img)
            stem        = f"blob_{idx:02d}_min{min_size:03d}px"
            result_img.save(output_dir / f"{stem}.png")

            right_label = (
                f"Blob  min={min_size}px  "
                f"{regions:,} regions  {_pct(baseline, regions)}  {elapsed:.1f}s"
            )
            make_comparison(
                display_baseline, result_img, baseline_label, right_label, zoom
            ).save(output_dir / f"{stem}_compare.png")

            print_row(f"  Blob  min = {min_size:2d} px", regions, baseline, img_w, img_h, metrics, elapsed, threshold)

    # ── Radiant denoising ─────────────────────────────────────────────────────
    if not args.no_radiant:
        print_section("Radiant denoise  (circular neighbourhood mode, outlier-only replacement)")
        for idx, r in enumerate(RADIANT_RADII, 1):
            t0           = time.perf_counter()
            filtered_img = radiant_denoise(work_img, r)
            regions      = region_count(filtered_img, conn)
            elapsed      = time.perf_counter() - t0

            result_img   = flip_v(filtered_img)
            metrics      = compare_images(display_baseline, result_img)
            stem         = f"radiant_{idx:02d}_r{r:02d}"
            result_img.save(output_dir / f"{stem}.png")

            right_label = (
                f"Radiant  r={r}  "
                f"{regions:,} regions  {_pct(baseline, regions)}  {elapsed:.1f}s"
            )
            make_comparison(
                display_baseline, result_img, baseline_label, right_label, zoom
            ).save(output_dir / f"{stem}_compare.png")

            print_row(f"  Radiant  r = {r:2d}", regions, baseline, img_w, img_h, metrics, elapsed, threshold)

    # ── Mode window ───────────────────────────────────────────────────────────
    if not args.no_mode:
        print_section("Mode window  (sliding K×K neighbourhood majority vote)")
        for idx, k in enumerate(MODE_KERNEL_SIZES, 1):
            t0           = time.perf_counter()
            filtered_img = mode_window(work_img, k)
            regions      = region_count(filtered_img, conn)
            elapsed      = time.perf_counter() - t0

            result_img   = flip_v(filtered_img)
            metrics      = compare_images(display_baseline, result_img)
            stem         = f"mode_{idx:02d}_k{k:03d}"
            result_img.save(output_dir / f"{stem}.png")

            right_label = (
                f"Mode  k={k}  "
                f"{regions:,} regions  {_pct(baseline, regions)}  {elapsed:.1f}s"
            )
            make_comparison(
                display_baseline, result_img, baseline_label, right_label, zoom
            ).save(output_dir / f"{stem}_compare.png")

            print_row(f"  Mode window  k = {k:2d}", regions, baseline, img_w, img_h, metrics, elapsed, threshold)

    # ── NN downscale ──────────────────────────────────────────────────────────
    if not args.no_downscale:
        print_section("NN downscale  (nearest-neighbour resampling, palette-safe)")
        for idx, scale in enumerate(DOWNSCALE_FACTORS, 1):
            t0         = time.perf_counter()
            scaled_img = nn_downscale(display_baseline, scale)
            regions    = region_count(scaled_img, conn)
            elapsed    = time.perf_counter() - t0

            # Metrics: NN-upsample back to baseline size so comparison is at
            # original resolution — measures blockiness/information loss.
            metrics      = compare_images(display_baseline, scaled_img)
            pct_int      = round(scale * 100)
            new_w, new_h = scaled_img.size
            stem         = f"downscale_{idx:02d}_{pct_int:03d}pct"
            scaled_img.save(output_dir / f"{stem}.png")

            right_label = (
                f"NN  {pct_int}%  "
                f"{regions:,} regions  {_pct(baseline, regions)}  "
                f"{new_w}×{new_h}px  {elapsed:.1f}s"
            )
            make_comparison(
                display_baseline, scaled_img, baseline_label, right_label, zoom
            ).save(output_dir / f"{stem}_compare.png")

            print_row(f"  NN  {pct_int:3d}%", regions, baseline, new_w, new_h, metrics, elapsed, threshold)

    print(f"\n{_DIVIDER}")
    print(f"\nDone. Saved to: {output_dir.resolve()}\n")


if __name__ == "__main__":
    main()
