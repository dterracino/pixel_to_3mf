"""Morphological pixel art region smoothing.

Each unique-colour region is eroded by ``radius`` pixels — distance is measured
only to *other* non-transparent colour regions, so the image boundary does not
cause erosion of edge-touching regions.  Features narrower than 2·radius
(thin lines, isolated specks) disappear and their pixels are absorbed by the
nearest surviving neighbour region.

The surviving region "cores" are then re-expanded via Voronoi nearest-core
assignment: every valid pixel is given the colour whose surviving core is
closest.  This produces smooth, mathematically-clean boundaries with no gaps
or overlaps — regardless of how complex the original region topology is.

This module runs entirely in raster space and returns a PixelData with the
same width, height, and pixel_size_mm, so the rest of the pipeline (region
merger, mesh generator, …) requires no changes.

Typical usage
-------------
::

    from pixel_to_3mf.morph_smoother import smooth_pixel_regions

    smoothed = smooth_pixel_regions(pixel_data, radius=1.5)

The returned ``smoothed`` can be passed directly to ``merge_regions()`` in
place of the original ``pixel_data``.
"""
from __future__ import annotations

import logging

import numpy as np
from scipy.ndimage import distance_transform_edt

logger = logging.getLogger(__name__)


def smooth_pixel_regions(pixel_data, radius: float = 1.5):
    """Apply morphological erode-then-Voronoi smoothing to pixel art regions.

    Each unique colour is eroded by ``radius`` pixels (measuring distance only
    to other non-transparent colour pixels, so image-edge-touching regions are
    not shrunk by the image boundary).  Any region narrower than ``2 * radius``
    — thin lines, isolated specks — is eroded away and its pixels are absorbed
    by whichever neighbouring region's core is closest.

    The surviving cores are re-expanded by Voronoi nearest-core assignment,
    producing smooth, rounded inter-region boundaries.

    Args:
        pixel_data: PixelData produced by ``load_image()``.  Pixels are stored
            as ``(x, y) → (R, G, B, A)`` with y=0 at the *bottom* of the image.
        radius: Erosion radius in pixels.  1.5 preserves features ≥ 3 px wide
            and removes thinner ones.  Increase for more aggressive smoothing
            and more pronounced corner rounding; decrease to preserve finer
            detail at the cost of less smoothing.

    Returns:
        New PixelData with the same ``width``, ``height``, and
        ``pixel_size_mm`` but with smoothed pixel colours.  The set of
        transparent pixels (positions absent from the ``pixels`` dict) is
        unchanged.
    """
    # Local import avoids a circular dependency when morph_smoother is imported
    # before image_processor has finished loading.
    from pixel_to_3mf.image_processor import PixelData  # type: ignore[attr-defined]

    width = pixel_data.width
    height = pixel_data.height

    if not pixel_data.pixels:
        return pixel_data

    # -----------------------------------------------------------------------
    # 1. Build integer label image.
    #
    #    PixelData uses y=0 at the *bottom* (Y-flipped convention).
    #    NumPy images use row=0 at the *top*, so:  row = (height - 1 - y).
    # -----------------------------------------------------------------------
    color_to_idx: dict[tuple[int, int, int], int] = {}
    idx_to_color: list[tuple[int, int, int]] = []

    label_img = np.full((height, width), -1, dtype=np.int32)

    for (x, y), rgba in pixel_data.pixels.items():
        rgb: tuple[int, int, int] = (rgba[0], rgba[1], rgba[2])
        if rgb not in color_to_idx:
            color_to_idx[rgb] = len(idx_to_color)
            idx_to_color.append(rgb)
        label_img[height - 1 - y, x] = color_to_idx[rgb]

    n_colors = len(idx_to_color)
    if n_colors == 0:
        return pixel_data

    logger.debug("morph_smoother: %d colours, %dx%d, radius=%.2f", n_colors, width, height, radius)

    # Mask of all non-transparent (occupied) pixels.
    valid_mask = label_img >= 0

    # -----------------------------------------------------------------------
    # 2. Per-colour: erode then compute distance-to-surviving-core.
    #
    #    For each colour idx:
    #      a) Build a mask of *other non-transparent* pixels.  These are the
    #         only pixels that cause erosion — transparent and same-colour
    #         pixels are treated as neutral so the image boundary does not
    #         shrink edge-touching regions.
    #      b) Compute the Euclidean distance from every pixel to the nearest
    #         other-colour pixel ("inside distance").
    #      c) Core = pixels of this colour where inside_dist >= radius.
    #      d) If no core survives, skip (pixels will be absorbed by neighbours).
    #      e) Compute distance from every valid pixel to the nearest core pixel
    #         and update the global Voronoi nearest-core tracker.
    # -----------------------------------------------------------------------
    best_dist = np.full((height, width), np.inf)
    best_label = np.full((height, width), -1, dtype=np.int32)

    for idx in range(n_colors):
        # Pixels of *other* non-transparent colours define the erosion boundary.
        other_mask: np.ndarray = valid_mask & (label_img != idx)

        # distance_transform_edt(mask) → distance to nearest *False* pixel.
        # ~other_mask is True where there is no other-colour pixel (same colour
        # or transparent), so the result is distance to nearest other-colour pixel.
        dist_to_other: np.ndarray = distance_transform_edt(~other_mask)

        # Eroded core: pixels of this colour at least `radius` from any other colour.
        core: np.ndarray = (label_img == idx) & (dist_to_other >= radius)

        if not np.any(core):
            logger.debug(
                "morph_smoother: colour %s eroded away completely",
                idx_to_color[idx],
            )
            continue

        # Distance from every valid pixel to the nearest surviving core pixel.
        dist_to_core: np.ndarray = distance_transform_edt(~core)

        update: np.ndarray = valid_mask & (dist_to_core < best_dist)
        best_dist[update] = dist_to_core[update]
        best_label[update] = idx

    # -----------------------------------------------------------------------
    # 3. Fallback: valid pixels not claimed by any surviving core keep their
    #    original label.  This handles pathological cases where every colour
    #    in a neighbourhood eroded away (e.g. a cluster of colours all thinner
    #    than 2·radius packed tightly together).
    # -----------------------------------------------------------------------
    output_label = np.where(best_label >= 0, best_label, label_img)

    # -----------------------------------------------------------------------
    # 4. Rebuild PixelData from the smoothed label image.
    #    Only positions that were non-transparent in the input are included.
    # -----------------------------------------------------------------------
    new_pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for (x, y), original_rgba in pixel_data.pixels.items():
        row = height - 1 - y
        lbl = output_label[row, x]
        if lbl >= 0:
            r, g, b = idx_to_color[lbl]
            new_pixels[(x, y)] = (r, g, b, original_rgba[3])
        else:
            new_pixels[(x, y)] = original_rgba  # should not happen in practice

    return PixelData(
        width=width,
        height=height,
        pixel_size_mm=pixel_data.pixel_size_mm,
        pixels=new_pixels,
    )
