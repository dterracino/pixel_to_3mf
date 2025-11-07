# --optimize-mesh Reimplementation Plan

## Background
The current polygon optimization path (`polygon_optimizer.py`) was bolted onto the legacy per-pixel meshing logic. It relies on `shapely` boolean unions to merge pixel squares and delegates triangulation to the `triangle` library. This combination fails for the complex, high-polygon-count sprites that motivated the feature:

* Unions of tens of thousands of squares regularly produce `MultiPolygon` geometries or numerically fragile rings. We currently fall back to the slow path instead of recovering usable geometry.
* The `triangle` bindings crash the interpreter (SIGSEGV) when fed large inputs or polygons with many reflex vertices/holes, so we had to add aggressive pre-validation that rejects most interesting regions.
* Because we create the polygon by throwing every pixel square at Shapely, we pay O(n log n) robustness overhead and allocate huge intermediate geometries (hundreds of MB for a 320×200 bitmap). This erases the intended performance gains.

As a result the `--optimize-mesh` flag only works for trivial regions even though we already merge the per-color regions successfully.

## Goals
* Produce valid, manifold meshes for arbitrarily complex pixel regions (including large sprites with dozens of holes) without segfaults.
* Reduce triangle/vertex counts by merging adjacent pixels into real polygons before triangulation.
* Keep memory usage acceptable for ~100k pixel regions (< 1 GB peak).
* Maintain deterministic output so repeated runs produce identical meshes.
* Preserve compatibility with the existing CLI/config APIs while ensuring the optimized path handles every polygon without falling back.

## Constraints & Requirements
* Transparent pixels must become literal holes in the final mesh. The algorithm must preserve donut-shaped regions as polygons with interior rings.
* Pixel coordinates are integral in the source art; we can exploit this to avoid floating-point drift until the final mm scaling.
* The slicer requires outward-facing normals; top/bottom winding must remain CCW/CW consistent.
* We can add new third-party pure-Python dependencies if they are widely used and pip-installable (no system compilation steps in CI).

## High-Level Strategy
1. **Remove the legacy Shapely/Triangle pipeline** so the optimized flag invokes only the new contour-based implementation.
2. **Replace Shapely unioning** with a deterministic contour-tracing stage tailored to rectilinear pixel grids. This creates exact outer and inner loops directly from the region bitmap without intermediate geometry explosions.
3. **Represent polygons using integer lattice coordinates** (pixel corners) and only scale to millimeters when writing vertices. Integer grids eliminate robustness issues when detecting shared edges.
4. **Use Clipper/pyclipper** (robust polygon clipping on integer coordinates) as the geometry engine for union/normalization. Clipper handles self-touching rectilinear polygons exactly and can merge overlapping spans efficiently without geometric distortion.
5. **Triangulate with `mapbox-earcut`** (ear clipping optimized for simple polygons with holes). Earcut runs in linear time with respect to triangle count, never segfaults, and easily handles thousands of vertices per ring.
6. **Extrude the triangulated polygon** using our existing `extrude_polygon_to_mesh` concept, but adapted to the new data structures (no Shapely objects).

## Detailed Plan
### 1. Dependencies & Build
* Add `pyclipper` and `mapbox_earcut` to `requirements.txt` (both are pure Python wheels on PyPI).
* Remove `shapely` and `triangle` from runtime dependencies once the new implementation lands, and delete their import/usage sites immediately during the refactor.
* Update the packaging/setup docs to mention the new dependencies and the removal of the previous stack.
* Gate new code behind the existing `--optimize-mesh` flag, but have that flag invoke only the new pipeline.

### 2. Data Preparation
* Extend `Region` (or create a helper) to expose bounding box and fast lookup of pixel occupancy (`bool is_filled(x, y)`).
* Allocate a compact 2D boolean array for the region: size `(height+2) × (width+2)` to include a sentinel border. Use `numpy` for large regions to keep operations vectorized.
* Precompute `pixel_size_mm` scaling factors once.

### 3. Contour Extraction
* Implement a rectilinear contour tracer inspired by the "marching squares" / "Moore neighborhood" algorithm:
  * Walk the padded bitmap and collect all edges where a filled cell borders an empty cell.
  * Build directed half-edges with lattice coordinates (e.g., corner `(x, y)` to `(x, y+1)`).
  * For each unvisited half-edge, follow the left-hand rule to create a closed loop; store orientation (counter-clockwise for outer boundaries, clockwise for holes).
  * Because the grid is rectilinear, every vertex lies on integer coordinates, so loops are guaranteed simple.
* Classify loops into outer shells vs holes using winding (positive area ⇒ outer). For ambiguous cases (touching at corners) rely on pyclipper union in the next step.

### 4. Polygon Normalization & Union
* Feed the set of outer loops and hole loops into `pyclipper.Pyclipper()` to produce a clean `PolyTree`:
  * Scale integer lattice coordinates by a large constant (e.g., 1000) to satisfy Clipper's integer requirement while supporting sub-pixel expansions if needed later.
  * Execute a union on all outer loops to merge touching components.
  * Extract resulting hierarchy to produce final polygons with explicit interior rings. Clipper will resolve ambiguous corner-touching connections without geometric cracks.
* Collapse redundant collinear points by comparing successive edges; avoid polygon simplification routines that would distort the artwork.

### 5. Triangulation Pipeline
* Convert each polygon + its holes into the flattened arrays expected by `mapbox_earcut.triangulate_float32`.
* Provide a deterministic vertex ordering (outer ring CCW, holes CW) using signed area tests on the integer coordinates.
* Earcut outputs triangle indices referencing the flattened vertex list; lift them into millimeter space by multiplying coordinates by `pixel_size_mm` and extrude to top/bottom Z as before.
* Construct wall quads by iterating over each ring's edges, mirroring the logic in the original extruder but using the integer coordinate maps.

### 6. Integration with Existing Mesh Generator
* Introduce a new module `polygonizer.py` (or similar) encapsulating the contour → polygon → triangulation pipeline.
* Refactor `generate_region_mesh_optimized` to:
  1. Build contour polygons using the new pipeline.
  2. Call a shared `extrude_polygon` helper that outputs a `Mesh` object.
  3. Surface granular progress updates (e.g., regions processed, contour tracing done, triangulation done) via the CLI logger to keep users informed during long runs.
* Update backing-plate generation to call the same contour pipeline on all non-transparent pixels once (single large polygon with holes) and reuse the earcut triangulation.
* Delete all Shapely/Triangle-specific modules, helpers, and tests as part of the same change, ensuring the optimized flag cannot regress into the legacy logic.

### 7. Performance Considerations
* Profile on large sprites (e.g., 320×200 with many holes) to measure time and memory:
  * Contour tracing is O(number_of_boundary_edges) ≈ O(n) for filled pixels.
  * Pyclipper union is near-linear for rectilinear inputs and uses integer math.
  * Earcut triangulation is linear in output triangles.
* Cache frequently accessed conversions (e.g., vertex index maps) to avoid repeated dict lookups while extruding walls.
* Support streaming/back-pressure by processing one region at a time (current behavior), minimizing global allocations.
* Record timing metrics per pipeline phase (contour extraction, clipping, triangulation, extrusion) to power the user-visible progress logging.

### 8. Testing Strategy
* Unit tests for contour tracing on synthetic shapes (solid rectangle, donut, figure-eight, diagonal connections, single-pixel holes).
* Property tests comparing area/perimeter of generated polygons vs raw pixel counts.
* Regression tests that run full conversion on existing sample images with `--optimize-mesh` enabled and verify:
  * Mesh vertex/triangle counts are reduced compared to the original path.
  * The optimized pipeline completes without errors for known troublesome sprites.
  * Backing plate mesh matches expectations (correct bounding box, hole locations).
* Add fuzz tests that randomize binary grids up to ~32×32 to ensure polygonization never crashes and round-trips when re-rasterized.

### 9. Rollout Steps
1. Land the new polygonization + earcut pipeline and delete the Shapely/Triangle code path in the same change to avoid dual-maintenance confusion.
2. Instrument logging/metrics to report optimization progress (regions processed, vertices generated) so long-running jobs expose activity.
3. Update documentation and README to describe the new algorithm and its advantages.

## Risk Mitigation & Contingencies
* If `pyclipper` union unexpectedly balloons memory, fall back to a pure contour-merging approach by joining loops via shared edges (still deterministic on integer grids).
* If `mapbox-earcut` exposes precision issues for huge coordinate ranges, keep scaling factors moderate (≤ 1e6) and add validation that triangulated area matches polygon area.
* If any pipeline stage raises an exception, fail the conversion with actionable diagnostics instead of silently reverting to the pixel-by-pixel mesher.

## Follow-Up Notes
* Polygon simplification will be avoided so the optimized mesh matches the original pixel art silhouettes exactly.
* Expose progress metrics for large polygons (e.g., number of regions optimized, contour/triangulation milestones) in CLI output to keep users informed during long runs.
* Re-evaluate multi-threading after validating performance on representative sprites; if wall-clock time remains high, introduce parallel region processing in a later iteration.
