# Pixel Art to Smoothed Side-by-Side 3MF Geometry Workflow

## Goal

Convert pixel art into **smoothed, side-by-side 3D printable geometry** for 3MF output.

This is not image resizing. This is:

> pixel art → vector-like regions → smoothed shared boundaries → triangulated solids

---

## High-Level Pipeline

```
image
→ label map
→ boundary extraction
→ shared-edge paths
→ simplify
→ smooth
→ polygonize
→ assign colors
→ triangulate
→ extrude
→ 3MF
```

---

## Core Principle

**All adjacent regions must share the exact same boundary geometry.**

Do NOT smooth regions independently.

Correct model:

```
one shared boundary → reused by both neighboring regions
```

---

## Stage 1: Image → Label Map

Convert image to discrete labels:

```python
label_map[y, x] = label_id
```

Rules:

- Ignore transparent pixels
- Optionally quantize colors
- Optionally remove tiny regions

---

## Stage 2: Boundary Extraction

For each pixel, compare with right and bottom neighbors:

```
if label != neighbor:
    create boundary segment
```

Store:

```python
BoundarySegment:
    p0, p1
    left_label
    right_label
```

Important:

- Each boundary is created once
- Includes boundaries vs transparent

---

## Stage 3: Build Boundary Paths

Merge segments into paths:

```python
BoundaryPath:
    points[]
    left_label
    right_label
    is_closed
```

Rules:

- Merge only segments with same label pair
- Stop at junctions (3+ colors)

---

## Stage 4: Simplification

Apply RDP:

```python
line.simplify(tolerance, preserve_topology=True)
```

Suggested:

```
tolerance ≈ 0.5 px
```

Purpose:

- Remove pixel staircase noise
- Reduce vertex count

---

## Stage 5: Smoothing

Apply **Chaikin smoothing**:

```
iterations = 1–2
ratio = 0.25
```

For segment p0 → p1:

```
q = 0.75*p0 + 0.25*p1
r = 0.25*p0 + 0.75*p1
```

Rules:

- Closed paths: smooth all points
- Open paths: preserve endpoints

Critical:

> Smooth each boundary ONCE, not per region.

---

## Stage 6: Build Edge Network

After smoothing, you now have:

```
smoothed boundary graph (shared edges)
```

Ensure:

- Endpoints align exactly
- Junctions are preserved

Optional:

```
snap tolerance ≈ 1e-5
```

---

## Stage 7: Polygonization

Convert edge network to faces:

```python
from shapely.ops import polygonize

faces = list(polygonize(multiline))
```

Each face = one region candidate.

---

## Stage 8: Assign Colors

For each polygon:

```python
p = polygon.representative_point()
label = label_map[int(p.y), int(p.x)]
```

Assign:

```
polygon → label → color
```

Discard empty regions.

---

## Stage 9: Merge Same-Color Regions

```python
unary_union(polygons_by_label)
```

Cleanup:

- remove tiny regions
- remove tiny holes
- make_valid / buffer(0)

---

## Stage 10: Scale to Model Space

```
scale = target_mm / image_px
```

Apply:

```
x = x * scale
y = -y * scale
```

Optional:

- center on origin

---

## Stage 11: Triangulation

Use your existing **Shapely + triangle** pipeline.

For each polygon:

```
exterior → segments
interiors → hole segments + hole points
```

Important:

- Constrained triangulation required
- Preserve boundaries

---

## Stage 12: Extrusion

For each triangle:

Top:

```
(x, y, height)
```

Bottom:

```
(x, y, 0)
```

Add:

- top faces
- bottom faces (reversed winding)
- side walls along edges

Side wall per edge:

```
p0_bottom, p1_bottom, p1_top, p0_top
```

Split into 2 triangles.

---

## Stage 13: 3MF Output

Each region becomes geometry:

Options:

- one mesh per region
- or per color

Assign material/color accordingly.

---

## Critical Constraint (Side-by-Side)

Must avoid:

- gaps between regions
- overlapping geometry
- independently smoothed seams

Must enforce:

```
shared edges → identical vertices → perfect seams
```

---

## Suggested Config

```python
class Config:
    simplify_px = 0.5
    chaikin_iterations = 2
    snap_tolerance = 1e-5
    min_region_area = 2.0
    min_hole_area = 1.0
    height_mm = 1.0
```

---

## Key Insight

This is NOT image scaling.

This is:

```
pixel grid → geometric interpretation → smoothed subdivision → mesh generation
```

---

## Implementation Strategy

Start simple:

1. boundary extraction → debug SVG
2. smoothing → debug SVG
3. polygonize → colored SVG
4. triangulate → preview mesh
5. export 3MF

---

## Final Summary

```
Extract shared boundaries from raster →
Simplify →
Smooth →
Polygonize →
Assign colors →
Triangulate →
Extrude →
Export 3MF
```

Most important rule:

> **Never smooth regions independently. Always smooth shared boundaries.**
