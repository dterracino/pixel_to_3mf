# Boundary Smoothing — Implementation Spec

## Overview

This document specifies how to add optional **boundary smoothing** to the pixel_to_3mf
pipeline. The goal is to let users choose between the current pixel-exact geometry and a
smoothed alternative where the blocky staircase edges between color regions are replaced by
smooth curves — while preserving the side-by-side manifold constraint (no gaps, no overlaps).

Enabled via a new flag: `--smooth-boundaries`.

---

## Background: Why This Is Different

The current pipeline processes **each region independently**. Each region's pixels are meshed
in isolation and the results happen to align because all pixels are the same integer size.

Boundary smoothing requires processing **all regions together**. Shared edges must be smoothed
exactly once and then reused by both neighboring regions. This means:

- You cannot insert smoothing into the existing per-region mesh loop
- A new cross-region pre-processing stage is needed between region merging and mesh generation
- The output of that stage is a set of shaped polygons, not pixel sets — but the existing
  triangulation/extrusion infrastructure in `polygon_optimizer.py` handles polygons already

---

## Proposed Architecture

### New insertion point in the pipeline

```text
Image Load
  → Region Merge  (existing: region_merger.py)
  → [NEW] Boundary Smooth  (new: boundary_smoother.py)   ← only when --smooth-boundaries
  → Mesh Generation  (existing: polygon_optimizer.py triangulation path)
  → 3MF Export  (existing: threemf_writer.py)
```

The boundary smoother consumes `List[Region]` and emits `List[SmoothedRegion]`, where each
`SmoothedRegion` carries a `shapely.Polygon` instead of a pixel set. The mesh generation
step already knows how to triangulate and extrude shapely polygons (see
`polygon_optimizer.py`), so no changes to the mesh generator are needed.

---

## New Module: `pixel_to_3mf/boundary_smoother.py`

### Responsibility

Take all regions, extract their shared boundary graph, simplify and smooth those boundaries,
then re-polygonize back into a set of shapely polygons with color assignments.

### Input / Output

```python
def smooth_region_boundaries(
    regions: list[Region],
    pixel_data: PixelData,
    config: ConversionConfig,
) -> list[SmoothedRegion]:
    ...
```

**Input:** `List[Region]` (same output as `region_merger.merge_regions`)

**Output:** `List[SmoothedRegion]`

```python
@dataclass
class SmoothedRegion:
    color: tuple[int, int, int]   # same RGB as source Region
    polygon: Polygon               # shapely Polygon in pixel-space coordinates
```

The `polygon` is in pixel-space (not yet scaled to mm). Scaling happens later, consistent
with how `polygon_optimizer.py` currently works.

---

## Algorithm — Stage by Stage

### Stage 1: Build Label Map

Create a 2D array mapping each pixel coordinate to a region index:

```python
label_map: dict[tuple[int, int], int]  # (x, y) → region_index
```

Transparent/missing pixels get label `-1`.

**Source:** Iterate `region.pixels` for each region in the input list.

---

### Stage 2: Extract Boundary Segments

For every pixel `(x, y)`, compare with its right neighbor `(x+1, y)` and bottom neighbor
`(x, y+1)`. If the labels differ, emit a boundary segment.

```python
@dataclass
class BoundarySegment:
    p0: tuple[float, float]   # start point in pixel-space
    p1: tuple[float, float]   # end point in pixel-space
    left_label: int
    right_label: int
```

Segments run along pixel edges. For a boundary between `(x, y)` and `(x+1, y)` (horizontal
neighbor), the segment runs vertically: from `(x+1, y)` to `(x+1, y+1)`. For a boundary
between `(x, y)` and `(x, y+1)` (vertical neighbor), the segment runs horizontally: from
`(x, y+1)` to `(x+1, y+1)`.

Each boundary is created once (never duplicated between the two sides).

Also emit boundary segments between any pixel and the outside border of the image.

**Total segments:** approximately `W*(H-1) + H*(W-1)` worst case, much fewer in practice.

---

### Stage 3: Build Boundary Paths

Chain segments into polylines by following connected endpoints. Stop at junctions where 3 or
more different labels meet — these are T/X intersections that cannot be smoothed through.

```python
@dataclass
class BoundaryPath:
    points: list[tuple[float, float]]
    label_pair: tuple[int, int]   # (smaller_label, larger_label) — canonical order
    is_closed: bool
```

**Algorithm:**

1. Build adjacency: `endpoint_map: dict[point, list[segment]]`
2. For each unvisited segment, walk in both directions, stopping at junctions
3. Record whether the resulting path is closed (start == end)

Segments with different label pairs must NOT be merged into the same path.

---

### Stage 4: Simplification (RDP)

Apply the Ramer–Douglas–Peucker algorithm to each path to remove collinear staircase noise.

```python
from shapely.geometry import LineString

def _simplify_path(path: BoundaryPath, tolerance: float) -> BoundaryPath:
    line = LineString(path.points)
    simplified = line.simplify(tolerance, preserve_topology=True)
    ...
```

**Recommended default tolerance:** `0.5` (in pixel units). Expose as config:

```python
smooth_simplify_tolerance: float = 0.5  # pixels
```

For **open paths**, endpoints must be preserved exactly (shapely's `simplify` does this by
default for LineStrings).

For **closed paths**, treat as a ring — use `LinearRing.simplify()`.

---

### Stage 5: Chaikin Smoothing

Apply Chaikin's corner-cutting algorithm to each simplified path.

```python
def _chaikin_smooth(
    points: list[tuple[float, float]],
    iterations: int,
    is_closed: bool,
) -> list[tuple[float, float]]:
    for _ in range(iterations):
        new_points = []
        pairs = zip(points, points[1:] + [points[0]]) if is_closed else zip(points, points[1:])
        for p0, p1 in pairs:
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            new_points.extend([q, r])
        if not is_closed:
            new_points[0] = points[0]      # preserve start endpoint
            new_points[-1] = points[-1]    # preserve end endpoint
        points = new_points
    return points
```

**Rules:**

- Closed paths: all points are smoothed (no fixed endpoints)
- Open paths: first and last points are always preserved exactly
- Junctions: junction points are shared across paths — they must stay fixed. Because open
  path endpoints are always preserved, this is automatic.

**Recommended default iterations:** `2`. Expose as config:

```python
smooth_chaikin_iterations: int = 2
```

---

### Stage 6: Build Edge Network

Collect all smoothed paths into a single `MultiLineString` for polygonization:

```python
from shapely.geometry import MultiLineString

all_lines = MultiLineString([path.points for path in smoothed_paths])
```

No special snapping is needed here because open-path endpoints are preserved exactly through
simplification and smoothing. If floating-point drift is observed during testing, apply:

```python
snap_tolerance: float = 1e-5
```

---

### Stage 7: Polygonization

```python
from shapely.ops import polygonize, unary_union

raw_polygons = list(polygonize(all_lines))
```

This reconstructs closed regions from the edge network. Each polygon is one candidate region.

---

### Stage 8: Assign Colors

For each candidate polygon, sample the label map at the polygon's representative point:

```python
pt = polygon.representative_point()
label = label_map.get((round(pt.x), round(pt.y)), -1)
```

If `label == -1` (transparent or outside), discard the polygon.

Assign the color from `regions[label].color`.

---

### Stage 9: Merge Same-Color Polygons

Group polygons by label, then union each group:

```python
from shapely.ops import unary_union

per_label_polygons: dict[int, list[Polygon]] = defaultdict(list)
for poly, label in assignments:
    per_label_polygons[label].append(poly)

merged: dict[int, Polygon] = {}
for label, polys in per_label_polygons.items():
    result = unary_union(polys)
    result = result.buffer(0)          # heal any self-intersections
    merged[label] = result
```

Also remove tiny artifact polygons whose area is below a threshold:

```python
smooth_min_area_px: float = 1.0  # pixel-space square pixels
```

---

### Stage 10: Output SmoothedRegion List

```python
output = []
for label, polygon in merged.items():
    output.append(SmoothedRegion(
        color=regions[label].color,
        polygon=polygon,
    ))
return output
```

Coordinates remain in pixel-space. Scaling to mm happens in the mesh generation step,
consistent with the existing `polygon_optimizer.py` path.

---

## Integration in `pixel_to_3mf.py`

In the main conversion function, after `merge_regions()` and before mesh generation, add:

```python
if config.smooth_boundaries:
    smoothed_regions = smooth_region_boundaries(regions, pixel_data, config)
    meshes = [
        generate_mesh_from_smoothed_region(r, pixel_data, config)
        for r in smoothed_regions
    ]
else:
    meshes = [
        generate_region_mesh(r, pixel_data, config)
        for r in regions
    ]
```

### New helper: `generate_mesh_from_smoothed_region()`

This function bridges `SmoothedRegion` → `Mesh`. It reuses the existing functions in
`polygon_optimizer.py`:

```python
def generate_mesh_from_smoothed_region(
    region: SmoothedRegion,
    pixel_data: PixelData,
    config: ConversionConfig,
) -> Mesh:
    # Scale polygon from pixel-space to mm
    scale = pixel_data.pixel_size_mm
    scaled_poly = affinity.scale(region.polygon, xfact=scale, yfact=scale, origin=(0, 0))

    # Flip Y axis (pixel origin top-left → 3D origin bottom-left)
    scaled_poly = affinity.scale(scaled_poly, xfact=1, yfact=-1, origin=(0, 0))

    # Triangulate using existing infrastructure
    vertices_2d, triangles, segments = triangulate_polygon_2d(scaled_poly)

    # Extrude to 3D mesh
    z_bottom = config.base_height_mm  # or 0 if no backing plate
    z_top = z_bottom + config.color_height_mm
    return extrude_polygon_to_mesh(scaled_poly, triangles, vertices_2d, segments, z_bottom, z_top)
```

This reuses `triangulate_polygon_2d()` and `extrude_polygon_to_mesh()` already in
`polygon_optimizer.py` — no duplication.

---

## Config Changes (`config.py`)

Add four new fields to `ConversionConfig`:

```python
# Boundary smoothing
smooth_boundaries: bool = False
smooth_simplify_tolerance: float = field(default_factory=lambda: SMOOTH_SIMPLIFY_TOLERANCE)
smooth_chaikin_iterations: int = field(default_factory=lambda: SMOOTH_CHAIKIN_ITERATIONS)
smooth_min_area_px: float = field(default_factory=lambda: SMOOTH_MIN_AREA_PX)
```

Add to `constants.py`:

```python
# Boundary smoothing defaults
SMOOTH_SIMPLIFY_TOLERANCE: float = 0.5   # RDP tolerance in pixel units
SMOOTH_CHAIKIN_ITERATIONS: int = 2       # Chaikin passes
SMOOTH_MIN_AREA_PX: float = 1.0          # Minimum polygon area to keep (pixel²)
```

---

## CLI Changes (`cli.py`)

Add to the mesh options argument group:

```python
mesh_group.add_argument(
    "--smooth-boundaries",
    action="store_true",
    default=False,
    help=(
        "Smooth region boundaries using RDP simplification and Chaikin subdivision. "
        "Replaces blocky pixel-grid edges with smooth curves. "
        "Requires --optimize-mesh to be compatible."
    ),
)
mesh_group.add_argument(
    "--smooth-tolerance",
    type=float,
    default=None,
    metavar="PX",
    help=f"RDP simplification tolerance in pixel units (default: {SMOOTH_SIMPLIFY_TOLERANCE})",
)
mesh_group.add_argument(
    "--smooth-iterations",
    type=int,
    default=None,
    metavar="N",
    help=f"Chaikin smoothing passes (default: {SMOOTH_CHAIKIN_ITERATIONS}, range: 1–4)",
)
```

Map parsed args to config in the `build_config()` function.

---

## Files to Create / Modify

| File | Change |
| --- | --- |
| `pixel_to_3mf/boundary_smoother.py` | **New** — entire smoothing pipeline |
| `pixel_to_3mf/constants.py` | Add 3 new smoothing constants |
| `pixel_to_3mf/config.py` | Add 4 new `ConversionConfig` fields |
| `pixel_to_3mf/pixel_to_3mf.py` | Add smoothing branch in main pipeline |
| `pixel_to_3mf/cli.py` | Add 3 new CLI arguments |
| `tests/test_boundary_smoother.py` | **New** — unit tests |

No changes needed to: `region_merger.py`, `mesh_generator.py`, `polygon_optimizer.py`,
`threemf_writer.py`.

---

## New Test File: `tests/test_boundary_smoother.py`

Suggested test cases:

| Test | Description |
| --- | --- |
| `test_two_color_grid` | 2×1 image with 2 colors — boundary is a single vertical segment; verify one polygon per color |
| `test_chaikin_preserves_endpoints` | Open path smoothing — endpoints must not move |
| `test_chaikin_closed` | Closed path — verify no endpoint constraint, shape shrinks inward |
| `test_simplify_diagonal` | Staircase diagonal input — verify vertex count drops after RDP |
| `test_no_gaps` | Two adjacent smoothed polygons — verify `unary_union(both).area ≈ total_pixel_area` |
| `test_no_overlaps` | Two adjacent smoothed polygons — verify intersection area ≈ 0 |
| `test_transparent_pixels_excluded` | RGBA image with alpha=0 pixels — verify label -1 polygons are discarded |
| `test_small_region_removed` | Polygon below `smooth_min_area_px` — verify it is removed |
| `test_full_pipeline_integration` | End-to-end: small PNG → 3MF with `smooth_boundaries=True` |

---

## Known Limitations and Edge Cases

**Diagonal-only connections:** The existing `region_merger.py` splits regions that only touch
diagonally to prevent non-manifold geometry. The smoothing pipeline must run **after** this
split so it receives already-valid regions.

**Very small regions:** Single-pixel regions may produce degenerate polygons after smoothing.
The `smooth_min_area_px` threshold handles this.

**Concave junctions:** At T/X intersections (3+ colors meeting), open path endpoints are
preserved exactly. This may leave visible sharp corners at those junctions, which is correct
and unavoidable without a more complex junction-rounding pass.

**Polygonization failures:** `shapely.ops.polygonize()` may not reconstruct every region if
the edge network has gaps. Fallback: detect missing labels after color assignment and
re-insert their original pixel-union polygons (from `polygon_optimizer.pixels_to_polygon()`).

**Performance:** For large images (>200×200 pixels), the boundary segment count can reach
tens of thousands. The algorithm is O(W×H) in the extraction and path-building stages, which
should be acceptable. Profile before optimizing.

---

## Implementation Order

1. Add constants to `constants.py`
2. Add fields to `ConversionConfig` in `config.py`
3. Implement `boundary_smoother.py` (Stages 1–9 above)
4. Add `generate_mesh_from_smoothed_region()` in `pixel_to_3mf.py`
5. Wire in the pipeline branch in `pixel_to_3mf.py`
6. Add CLI arguments in `cli.py`
7. Write `tests/test_boundary_smoother.py`
8. Test end-to-end with `samples/input/nes-samus.png`
