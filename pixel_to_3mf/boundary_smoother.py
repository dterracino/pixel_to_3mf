"""
Boundary smoothing for pixel art regions.

Converts a list of pixel regions into smoothed shapely Polygons by:
  1. Building a label map from the region list
  2. Extracting boundary segments between adjacent differently-labelled pixels
  3. Chaining segments into polylines (stopping at color junctions)
  4. Simplifying each path with RDP to remove pixel staircase noise
  5. Smoothing each path with Chaikin corner-cutting
  6. Re-polygonizing the smoothed edge network with shapely
  7. Assigning colors back from the label map
  8. Optionally collapsing regions that match the same filament color

The critical constraint is that each shared boundary is smoothed ONCE and reused
by both neighbouring regions, guaranteeing no gaps or overlaps at seams.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from shapely.geometry import LinearRing, LineString, MultiLineString, MultiPolygon, Polygon, box as shapely_box
from shapely.ops import polygonize, unary_union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass
class SmoothedRegion:
    """A color region represented as a smoothed shapely Polygon in pixel-space coordinates.

    Coordinates use the same Y-flipped convention as PixelData (Y=0 at the bottom of the
    image). The preview renderer and mesh generator must flip Y when converting to image or
    3D space respectively.
    """
    color: tuple[int, int, int]
    polygon: Polygon


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class _BoundarySegment:
    p0: tuple[float, float]
    p1: tuple[float, float]
    label_pair: tuple[int, int]  # (min_label, max_label); -1 = transparent / outside image


@dataclass
class _BoundaryPath:
    points: list[tuple[float, float]]
    is_closed: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def smooth_region_boundaries(
    regions: list,
    pixel_data,
    config,
) -> list[SmoothedRegion]:
    """Convert pixel regions into smoothed shapely Polygons.

    Extracts the shared boundary graph from all regions together, simplifies and smooths
    each path exactly once, then re-polygonizes to produce geometry where every neighbouring
    pair shares the same edge.

    Args:
        regions: List of Region objects from region_merger.merge_regions().
        pixel_data: PixelData with width, height, and Y-flipped pixels dict.
        config: ConversionConfig. Uses smooth_simplify_tolerance (default 0.5),
            smooth_chaikin_iterations (default 2), and smooth_min_area_px (default 1.0)
            via getattr so these fields are optional until added to ConversionConfig.

    Returns:
        List of SmoothedRegion in pixel-space coordinates.
    """
    tolerance = getattr(config, "smooth_simplify_tolerance", 0.5)
    iterations = getattr(config, "smooth_chaikin_iterations", 2)
    min_area = getattr(config, "smooth_min_area_px", 0.0)

    logger.debug("Building label map from %d regions", len(regions))
    label_map = _build_label_map(regions)

    logger.debug("Extracting boundary segments (%dx%d)", pixel_data.width, pixel_data.height)
    segments = _extract_boundary_segments(label_map, pixel_data.width, pixel_data.height)
    logger.debug("Extracted %d boundary segments", len(segments))

    if not segments:
        logger.warning("No boundary segments produced — returning empty result")
        return []

    # Trace the boundary graph into paths between topological junction nodes.
    # Each shared boundary is smoothed EXACTLY ONCE, so adjacent regions share the
    # same smoothed edge — no sub-pixel gaps can form between them.  This mirrors the
    # algorithm used by Image2Keychain.
    paths = _trace_junction_paths(segments, pixel_data.width, pixel_data.height)
    logger.debug("Traced %d boundary paths", len(paths))

    # Smooth each path; junction endpoints (first/last of open paths) are pinned by
    # _chaikin_smooth's open-path logic, guaranteeing exact matches at T-junctions.
    smoothed_lines: list[list[tuple[float, float]]] = []
    for path in paths:
        smoothed = _simplify_and_smooth(path, tolerance, iterations)
        pts = smoothed.points
        for i in range(len(pts) - 1):
            smoothed_lines.append([pts[i], pts[i + 1]])
        # Re-close loops that aren't already closed by their last point.
        if smoothed.is_closed and len(pts) >= 2 and pts[0] != pts[-1]:
            smoothed_lines.append([pts[-1], pts[0]])

    if not smoothed_lines:
        logger.warning("No smoothed paths produced — returning empty result")
        return []

    logger.debug("Polygonizing %d smoothed line segments", len(smoothed_lines))
    raw_polygons = list(polygonize(MultiLineString(smoothed_lines)))
    logger.debug("Polygonized into %d candidate polygons", len(raw_polygons))

    labeled_polygons = _assign_colors(raw_polygons, label_map, min_area)
    logger.debug("Assigned colors to %d polygons", len(labeled_polygons))

    # Fallback: re-insert any labels that polygonization missed
    labeled_polygons = _restore_missing_regions(labeled_polygons, regions, pixel_data.width)

    result = _merge_by_label(labeled_polygons, regions)
    logger.debug("Merged into %d SmoothedRegion objects", len(result))
    return result


def collapse_by_filament_color(
    regions: list[SmoothedRegion],
    config,
) -> list[SmoothedRegion]:
    """Group SmoothedRegions that map to the same filament color and union their polygons.

    This is the polygon-space equivalent of merge_similar_colors. Two regions with slightly
    different RGB values that both match the same filament will be merged into a single
    polygon, dissolving the shared boundary between them via shapely.unary_union.

    Non-adjacent regions that resolve to the same filament (different islands) produce a
    MultiPolygon which is split back into individual SmoothedRegion entries so downstream
    triangulation receives only simple Polygons.

    Args:
        regions: List of SmoothedRegion from smooth_region_boundaries().
        config: ConversionConfig supplying color_naming_mode, filament_maker, etc.

    Returns:
        List of SmoothedRegion with potentially fewer, larger polygons.
    """
    # Local import avoids a circular dependency since threemf_writer does not import us.
    from pixel_to_3mf.threemf_writer import get_color_name  # type: ignore[attr-defined]

    groups: dict[str, list[SmoothedRegion]] = defaultdict(list)
    for region in regions:
        key = get_color_name(region.color, config)
        groups[key].append(region)

    output: list[SmoothedRegion] = []
    for _key, group in groups.items():
        if len(group) == 1:
            output.append(group[0])
            continue

        merged = unary_union([r.polygon for r in group]).buffer(0)
        # Use the color of the largest constituent polygon as the representative color.
        representative_color = max(group, key=lambda r: r.polygon.area).color

        if isinstance(merged, MultiPolygon):
            for geom in merged.geoms:
                if not geom.is_empty:
                    output.append(SmoothedRegion(color=representative_color, polygon=geom))
        elif not merged.is_empty:
            output.append(SmoothedRegion(color=representative_color, polygon=merged))

    return output


# ---------------------------------------------------------------------------
# Stage 1: Build label map
# ---------------------------------------------------------------------------

def _build_label_map(regions: list) -> dict[tuple[int, int], int]:
    """Map every pixel coordinate to its region index (0-based)."""
    label_map: dict[tuple[int, int], int] = {}
    for idx, region in enumerate(regions):
        for px in region.pixels:
            label_map[px] = idx
    return label_map


# ---------------------------------------------------------------------------
# Stage 2: Extract boundary segments
# ---------------------------------------------------------------------------

def _extract_boundary_segments(
    label_map: dict[tuple[int, int], int],
    width: int,
    height: int,
) -> list[_BoundarySegment]:
    """Extract all boundary segments between pixels with different labels.

    In pixel-space, pixel (x, y) occupies the unit square [x, x+1] × [y, y+1].
    A horizontal segment at integer y separates the row below (y-1) from the row above (y).
    A vertical segment at integer x separates the column to the left (x-1) from the right (x).

    The outside of the image is represented by label -1, so the outer contour of every
    region is automatically captured.
    """
    segments: list[_BoundarySegment] = []

    # Horizontal segments: boundary between pixel row (y-1) and row y, running from x to x+1
    for y in range(height + 1):
        for x in range(width):
            la = label_map.get((x, y), -1)
            lb = label_map.get((x, y - 1), -1)
            if la != lb:
                pair = (min(la, lb), max(la, lb))
                segments.append(_BoundarySegment((x, y), (x + 1, y), pair))

    # Vertical segments: boundary between pixel col (x-1) and col x, running from y to y+1
    for x in range(width + 1):
        for y in range(height):
            la = label_map.get((x, y), -1)
            lb = label_map.get((x - 1, y), -1)
            if la != lb:
                pair = (min(la, lb), max(la, lb))
                segments.append(_BoundarySegment((x, y), (x, y + 1), pair))

    return segments


# ---------------------------------------------------------------------------
# Polygon ring smoothing (post-polygonize)
# ---------------------------------------------------------------------------

def _smooth_polygon(
    poly: Polygon,
    tolerance: float,
    iterations: int,
    clip_box: Polygon,
) -> Polygon | None:
    """Smooth a polygon's exterior and interior rings with RDP + Chaikin, then clip to clip_box.

    Each ring is smoothed independently. Points that fall exactly on the image border
    (x=0, x=width, y=0, y=height) are pinned during Chaikin smoothing so that regions
    touching the image border stay edge-to-edge with hard corners rather than gaining
    rounded corners from the corner-cutting algorithm.
    """
    # Extract image dimensions from clip_box bounds (minx, miny, maxx, maxy).
    minx, miny, maxx, maxy = clip_box.bounds

    def _is_border(pt: tuple[float, float]) -> bool:
        x, y = pt
        return x == minx or x == maxx or y == miny or y == maxy

    def _smooth_ring(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
        pts = list(coords)
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            return coords
        path = _BoundaryPath(pts, is_closed=True)
        smoothed = _simplify_and_smooth(path, tolerance, iterations, pinned=set(
            pt for pt in pts if _is_border(pt)
        ))
        result = smoothed.points
        if result and result[0] != result[-1]:
            result = result + [result[0]]
        return result

    try:
        ext_coords = _smooth_ring(list(poly.exterior.coords))
        if len(ext_coords) < 4:
            return None
        int_rings = [_smooth_ring(list(r.coords)) for r in poly.interiors]
        int_rings = [r for r in int_rings if len(r) >= 4]
        smoothed_poly = Polygon(ext_coords, int_rings)
        if not smoothed_poly.is_valid:
            smoothed_poly = smoothed_poly.buffer(0)
        if smoothed_poly.is_empty:
            return None
        # Clip to image box to restore hard edges where regions touch the image border.
        try:
            clipped = smoothed_poly.intersection(clip_box)
        except Exception:
            clipped = smoothed_poly
        # Extract first Polygon from the result (intersection may return MultiPolygon or
        # GeometryCollection for complex self-touching rings, but keep the largest piece).
        if isinstance(clipped, Polygon):
            return clipped
        if isinstance(clipped, MultiPolygon):
            parts = [g for g in clipped.geoms if isinstance(g, Polygon) and not g.is_empty]
            return max(parts, key=lambda g: g.area) if parts else None
        # GeometryCollection — pick the largest Polygon part if any.
        try:
            parts = [g for g in clipped.geoms if isinstance(g, Polygon) and not g.is_empty]
            return max(parts, key=lambda g: g.area) if parts else None
        except AttributeError:
            return None
    except Exception as exc:
        logger.debug("_smooth_polygon failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Stage 2b: Trace topological boundary paths between junction nodes
# ---------------------------------------------------------------------------

def _trace_junction_paths(
    segments: list[_BoundarySegment],
    width: int,
    height: int,
) -> list[_BoundaryPath]:
    """Trace the pixel boundary graph into paths between topological junction nodes.

    A junction node is any point in the graph where degree ≠ 2 — i.e. an endpoint,
    T-junction, or X-junction where three or more boundary segments meet.  Image corners
    are also forced to be junctions so the right-angle corners of the image boundary
    are never rounded by Chaikin.

    Between two consecutive junction nodes every intermediate point has degree 2 and
    forms a simple chain.  Smoothing each chain independently (with the two junction
    endpoints pinned) means every shared boundary between two adjacent regions is
    smoothed exactly once.  Both neighbours see the same smoothed edge, so no gaps
    or overlaps arise at shared seams — the key property that produces I2K-quality
    gap-free tiling.

    Closed loops (all degree-2, e.g. isolated single-colour islands) have no junction
    nodes inside them and are traced separately after all junction-to-junction paths.
    """
    # 1. Degree count for every segment endpoint.
    degree: dict[tuple[float, float], int] = defaultdict(int)
    for seg in segments:
        degree[seg.p0] += 1
        degree[seg.p1] += 1

    # 2. Identify junction nodes.  Force the four image corners as junctions so the
    #    90° turns at image corners are never smoothed away by Chaikin.
    junctions: set[tuple[float, float]] = {pt for pt, d in degree.items() if d != 2}
    for corner in (
        (0.0, 0.0),
        (float(width), 0.0),
        (0.0, float(height)),
        (float(width), float(height)),
    ):
        if corner in degree:
            junctions.add(corner)

    # 3. Adjacency list: point → [(neighbour, segment_index), ...]
    adj: dict[tuple[float, float], list[tuple[tuple[float, float], int]]] = defaultdict(list)
    for i, seg in enumerate(segments):
        adj[seg.p0].append((seg.p1, i))
        adj[seg.p1].append((seg.p0, i))

    visited: set[int] = set()
    paths: list[_BoundaryPath] = []

    # 4. Trace junction-to-junction paths.
    for start in sorted(junctions):
        for neighbor, seg_idx in adj[start]:
            if seg_idx in visited:
                continue
            visited.add(seg_idx)
            pts: list[tuple[float, float]] = [start, neighbor]
            current = neighbor

            while current not in junctions:
                unvisited = [(n, idx) for n, idx in adj[current] if idx not in visited]
                if not unvisited:
                    break
                next_pt, next_idx = unvisited[0]
                visited.add(next_idx)
                pts.append(next_pt)
                current = next_pt

            paths.append(_BoundaryPath(pts, is_closed=(pts[0] == pts[-1])))

    # 5. Handle remaining closed loops (all degree-2; never reached from a junction).
    for i, seg in enumerate(segments):
        if i in visited:
            continue
        visited.add(i)
        start = seg.p0
        pts = [start, seg.p1]
        current = seg.p1

        while current != start:
            unvisited = [(n, idx) for n, idx in adj[current] if idx not in visited]
            if not unvisited:
                break
            next_pt, next_idx = unvisited[0]
            visited.add(next_idx)
            pts.append(next_pt)
            current = next_pt

        paths.append(_BoundaryPath(pts, is_closed=(pts[-1] == start)))

    logger.debug(
        "Traced %d paths (%d open / %d closed)",
        len(paths),
        sum(1 for p in paths if not p.is_closed),
        sum(1 for p in paths if p.is_closed),
    )
    return paths


# ---------------------------------------------------------------------------
# Stage 3: Build boundary paths (legacy — superseded by _trace_junction_paths)
# ---------------------------------------------------------------------------

def _build_boundary_paths(segments: list[_BoundarySegment]) -> list[_BoundaryPath]:
    """Chain boundary segments with the same label_pair into polylines.

    Stops at junction points where segments from different label_pairs meet. These are
    T or X intersections in the color graph; forcing paths to end here ensures that
    smoothing never bends geometry across a corner shared by 3+ colors.
    """
    # Detect junction points: any endpoint shared by segments of more than one label_pair
    global_pairs_at_point: dict[tuple[float, float], set[tuple[int, int]]] = defaultdict(set)
    for seg in segments:
        global_pairs_at_point[seg.p0].add(seg.label_pair)
        global_pairs_at_point[seg.p1].add(seg.label_pair)

    junction_points: set[tuple[float, float]] = {
        pt for pt, pairs in global_pairs_at_point.items() if len(pairs) > 1
    }

    # Group segments by label_pair then walk each group
    by_pair: dict[tuple[int, int], list[_BoundarySegment]] = defaultdict(list)
    for seg in segments:
        by_pair[seg.label_pair].append(seg)

    paths: list[_BoundaryPath] = []

    for _pair, pair_segs in by_pair.items():
        adj: dict[tuple[float, float], list[_BoundarySegment]] = defaultdict(list)
        for seg in pair_segs:
            adj[seg.p0].append(seg)
            adj[seg.p1].append(seg)

        visited: set[int] = set()

        for start_seg in pair_segs:
            if id(start_seg) in visited:
                continue
            visited.add(id(start_seg))

            # Grow the path in both directions from this seed segment.
            # forward  holds the path from start_seg.p0 → ... (growing at the tail)
            # backward holds extensions from start_seg.p0 → ... (growing away, reversed later)
            forward: list[tuple[float, float]] = [start_seg.p0, start_seg.p1]
            backward: list[tuple[float, float]] = []

            # Extend forward from the current tail
            while True:
                tip = forward[-1]
                if tip in junction_points:
                    break
                nexts = [s for s in adj[tip] if id(s) not in visited]
                if not nexts:
                    break
                nxt = nexts[0]
                visited.add(id(nxt))
                forward.append(nxt.p1 if nxt.p0 == tip else nxt.p0)

            # Extend backward from the current head
            while True:
                tip = backward[-1] if backward else forward[0]
                if tip in junction_points:
                    break
                nexts = [s for s in adj[tip] if id(s) not in visited]
                if not nexts:
                    break
                nxt = nexts[0]
                visited.add(id(nxt))
                backward.append(nxt.p1 if nxt.p0 == tip else nxt.p0)

            all_points = backward[::-1] + forward
            if len(all_points) < 2:
                continue

            is_closed = len(all_points) > 2 and all_points[0] == all_points[-1]
            paths.append(_BoundaryPath(all_points, is_closed))

    return paths


# ---------------------------------------------------------------------------
# Stages 4 & 5: Simplify and smooth
# ---------------------------------------------------------------------------

def _simplify_and_smooth(
    path: _BoundaryPath,
    tolerance: float,
    iterations: int,
    pinned: set[tuple[float, float]] | None = None,
) -> _BoundaryPath:
    """Apply RDP simplification then Chaikin smoothing to a boundary path."""
    pts = path.points
    if len(pts) < 2:
        return path

    try:
        if path.is_closed and len(pts) >= 4:
            ring = LinearRing(pts)
            simplified = ring.simplify(tolerance, preserve_topology=True)
            pts = list(simplified.coords)
        else:
            line = LineString(pts)
            simplified = line.simplify(tolerance, preserve_topology=True)
            pts = list(simplified.coords)
    except Exception:
        logger.debug("Simplification failed for path with %d points, skipping", len(pts))

    pts = _chaikin_smooth(pts, iterations, path.is_closed, pinned=pinned)
    return _BoundaryPath(pts, path.is_closed)


def _chaikin_smooth(
    points: list[tuple[float, float]],
    iterations: int,
    is_closed: bool,
    pinned: set[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """Apply Chaikin's corner-cutting algorithm.

    Each iteration replaces every edge p0→p1 with two new points:
        q = 0.75*p0 + 0.25*p1
        r = 0.25*p0 + 0.75*p1

    Open paths: first and last points are always pinned (junction endpoints).
    Closed paths: points in the optional ``pinned`` set are not moved; they
    are kept exactly and the Chaikin cut is skipped for edges touching them.
    This is used to preserve hard corners on the image border.
    """
    pts = list(points)

    # LinearRing.coords always includes the first point repeated at the end.
    # Remove the duplicate before iterating so we don't produce a degenerate
    # zero-length edge from the last point back to itself, which would corrupt
    # the Chaikin output and cause polygonize() to fail to reconstruct the ring.
    if is_closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]

    for _ in range(iterations):
        n = len(pts)
        if n < 2:
            break

        new_pts: list[tuple[float, float]] = []
        if is_closed:
            pairs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
        else:
            pairs = [(pts[i], pts[i + 1]) for i in range(n - 1)]

        for i, (p0, p1) in enumerate(pairs):
            if pinned and (p0 in pinned):
                # Keep this corner-point exactly; still emit the midpoint toward p1
                # so the next segment starts smoothly.
                new_pts.append(p0)
                r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
                new_pts.append(r)
            elif pinned and (p1 in pinned):
                # Approaching a pinned corner — cut only the q point, keep p1 pinned.
                q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
                new_pts.append(q)
                # p1 will be emitted as p0 in the next iteration.
            else:
                q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
                r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
                new_pts.extend([q, r])

        if not is_closed and new_pts:
            new_pts[0] = points[0]    # preserve original start (junction pin)
            new_pts[-1] = points[-1]  # preserve original end (junction pin)

        pts = new_pts

    # Re-close the ring so polygonize() treats it as a closed loop rather than
    # an open line string (which it would fail to polygonize correctly).
    if is_closed and pts and pts[0] != pts[-1]:
        pts = pts + [pts[0]]

    return pts


# ---------------------------------------------------------------------------
# Stages 7 & 8: Polygonize and assign colors
# ---------------------------------------------------------------------------

def _assign_colors(
    raw_polygons: list[Polygon],
    label_map: dict[tuple[int, int], int],
    min_area: float,
) -> list[tuple[Polygon, int]]:
    """Assign a region label to each polygon by sampling the label map.

    Uses representative_point() to find a point strictly inside the polygon, then looks up
    which pixel (and therefore which region label) that point falls in. Polygons that land
    in transparent space (label -1) or are below min_area are discarded.
    """
    labeled: list[tuple[Polygon, int]] = []
    for poly in raw_polygons:
        if poly.area < min_area:
            continue

        pt = poly.representative_point()
        # Pixel (x, y) occupies [x, x+1) × [y, y+1), so floor gives the pixel coords.
        px = int(pt.x)
        py = int(pt.y)
        label = label_map.get((px, py), -1)

        if label == -1:
            # Fallback: try immediate neighbours in case the point landed on a grid line.
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                label = label_map.get((px + dx, py + dy), -1)
                if label != -1:
                    break

        if label == -1:
            continue

        labeled.append((poly, label))

    return labeled


# ---------------------------------------------------------------------------
# Stage 9: Merge by label
# ---------------------------------------------------------------------------

def _merge_by_label(
    labeled_polygons: list[tuple[Polygon, int]],
    regions: list,
) -> list[SmoothedRegion]:
    """Union all polygons with the same region label into SmoothedRegion objects.

    After polygonization a single source region may produce several fragments (e.g. if the
    edge network had small gaps). unary_union re-assembles them. MultiPolygon results are
    split so downstream code always receives simple Polygons.
    """
    per_label: dict[int, list[Polygon]] = defaultdict(list)
    for poly, label in labeled_polygons:
        per_label[label].append(poly)

    output: list[SmoothedRegion] = []
    for label, polys in per_label.items():
        # Validate each polygon individually before unary_union.  Chaikin
        # smoothing can produce very slightly self-intersecting rings; calling
        # .buffer(0) on each one heals the self-intersection so that
        # unary_union does not raise a TopologyException.
        valid_polys = []
        for p in polys:
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                valid_polys.append(p)
        if not valid_polys:
            continue
        merged = unary_union(valid_polys).buffer(0)
        color = regions[label].color

        if isinstance(merged, MultiPolygon):
            for geom in merged.geoms:
                if not geom.is_empty:
                    output.append(SmoothedRegion(color=color, polygon=geom))
        elif not merged.is_empty:
            output.append(SmoothedRegion(color=color, polygon=merged))

    return output


# ---------------------------------------------------------------------------
# Fallback: restore regions that polygonization missed
# ---------------------------------------------------------------------------

def _restore_missing_regions(
    labeled_polygons: list[tuple[Polygon, int]],
    regions: list,
    image_width: int,
) -> list[tuple[Polygon, int]]:
    """Re-insert any region labels that polygonization failed to reconstruct.

    If the smoothed edge network has gaps (e.g. very thin regions, isolated pixels),
    polygonize() may not produce a polygon for every original region. We fall back to the
    original pixel-union polygon (unsmoothed) for those missing labels so the output is
    always complete.
    """
    found_labels = {label for _, label in labeled_polygons}
    missing_labels = set(range(len(regions))) - found_labels

    if not missing_labels:
        return labeled_polygons

    result = list(labeled_polygons)
    for label in sorted(missing_labels):
        region = regions[label]
        # Build pixel squares directly so we can handle disconnected regions
        # (MultiPolygon) — they arise when 8-connectivity created a region whose
        # pixels only touch at corners rather than edges.
        pixel_squares = [shapely_box(x, y, x + 1, y + 1) for x, y in region.pixels]
        merged = unary_union(pixel_squares)
        if merged.is_empty:
            logger.warning("Skipping empty restore for region %d (color=%s)", label, region.color)
            continue

        if isinstance(merged, MultiPolygon):
            for geom in merged.geoms:
                if isinstance(geom, Polygon) and not geom.is_empty:
                    result.append((geom, label))
            logger.debug(
                "Restored missing region %d (color=%s) as %d disconnected parts",
                label, region.color, len(list(merged.geoms)),
            )
        elif isinstance(merged, Polygon):
            result.append((merged, label))
            logger.debug(
                "Restored missing region %d (color=%s) using pixel-union fallback", label, region.color
            )
        else:
            logger.warning(
                "Unexpected geometry type %s for region %d (color=%s)",
                type(merged).__name__, label, region.color,
            )

    return result
