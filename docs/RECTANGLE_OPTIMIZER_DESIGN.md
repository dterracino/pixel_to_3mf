# Rectangle-Based Mesh Optimization Design

## Problem Statement

The current `polygon_optimizer.py` uses shapely polygon union + triangle library triangulation. This approach:
- Creates 54+ non-manifold edges on simple models
- Is over-engineered for axis-aligned pixel grids
- Produces unreliable mesh topology
- Requires complex polygon operations and external dependencies

## Solution: Rectangle-Based Merging

Instead of treating pixels as arbitrary polygons, treat them as what they are: **axis-aligned squares on a grid**.

### Core Insight

**Region merger connectivity ≠ Mesh topology connectivity**

- Region merger can use 8-connectivity for color grouping (includes diagonals)
- Mesh optimizer MUST use 4-connectivity only (edge-adjacent only)
- Diagonal pixel connections = point-to-point contact = non-manifold topology

## Algorithm Design

### Phase 1: 4-Connectivity Region Splitting

**Input**: Region with pixels grouped by color (may have 8-connectivity)

**Process**:
1. For each color region from region_merger
2. Extract the set of pixel coordinates
3. Run 4-connectivity flood-fill on those pixels
4. Split into one or more 4-connected sub-regions

**Output**: List of 4-connected sub-regions per color

**Why**: Ensures no diagonal-only connections exist in mesh topology

### Phase 2: Horizontal Scanline Merging

**Input**: 4-connected sub-region (set of pixel coordinates)

**Process**:
1. Sort pixels by (y, x) - row-by-row, left-to-right
2. For each row (same y-coordinate):
   - Find runs of consecutive x-coordinates
   - Create horizontal strip: `(x_start, x_end, y)`
3. Result: List of horizontal strips

**Example**:
```
Pixels: (0,0), (1,0), (2,0), (4,0), (5,0), (0,1), (1,1)
Row 0: (0,0)-(2,0) gap (4,0)-(5,0) → strips [(0,2,0), (4,5,0)]
Row 1: (0,1)-(1,1) → strip [(0,1,1)]
```

**Output**: List of horizontal strips `[(x_start, x_end, y), ...]`

**Why**: Reduces horizontal complexity first, makes vertical merging simpler

### Phase 3: Vertical Rectangle Merging

**Input**: List of horizontal strips

**Process**:
1. Sort strips by (y, x_start)
2. For each strip, try to merge with strips from row below:
   - If strip[row].x_start == strip[row+1].x_start
   - AND strip[row].x_end == strip[row+1].x_end
   - Merge into rectangle spanning both rows
3. Continue merging while consecutive rows match
4. Result: List of rectangles

**Example**:
```
Strips: [(0,2,0), (4,5,0), (0,2,1), (0,2,2)]
Strip (0,2,0) matches (0,2,1) → merge to (0,2,0-1)
Rectangle (0,2,0-1) matches (0,2,2) → merge to (0,2,0-2)
Strip (4,5,0) has no match → stays as (4,5,0)

Rectangles: [(0,2,0,2), (4,5,0,0)]
```

**Output**: List of rectangles `[(x_start, x_end, y_start, y_end), ...]`

**Why**: Maximizes merging, creates minimal rectangle count

### Phase 4: Vertex Generation

**Input**: List of rectangles

**Process**:
1. For each rectangle (x_start, x_end, y_start, y_end):
   - Calculate 4 corners in pixel coordinates
   - Convert to world coordinates (mm) using pixel_size
   - Add 8 vertices (4 top + 4 bottom)
2. Build vertex lookup dict: `corner_coord -> vertex_index`
3. When adjacent rectangles share corners, reuse vertex index

**Data Structure**:
```python
# Vertex lookup for manifold sharing
vertex_map: Dict[Tuple[float, float, float], int] = {}

# For rectangle corner at (x_mm, y_mm, z_mm):
key = (x_mm, y_mm, z_mm)
if key in vertex_map:
    vertex_idx = vertex_map[key]  # Reuse
else:
    vertex_idx = len(vertices)
    vertices.append((x_mm, y_mm, z_mm))
    vertex_map[key] = vertex_idx
```

**Output**: 
- `vertices: List[Tuple[float, float, float]]`
- `vertex_map: Dict[corner_coord, vertex_index]`

**Why**: Shared vertices = manifold mesh, no duplicate points

### Phase 5: Triangle Generation

**Input**: Rectangles + vertices + vertex_map

**Process**: For each rectangle, generate triangles:

**Top face** (2 triangles, CCW winding when viewed from above):
```
   v1 ---- v2
   |  \     |
   |    \   |
   |      \ |
   v0 ---- v3

Triangle 1: (v0, v1, v2)  # Bottom-left, top-left, top-right
Triangle 2: (v0, v2, v3)  # Bottom-left, top-right, bottom-right
```

**Bottom face** (2 triangles, CCW winding when viewed from below = CW from above):
```
Triangle 1: (v4, v6, v5)  # Bottom-left, top-right, top-left (reversed)
Triangle 2: (v4, v7, v6)  # Bottom-left, bottom-right, top-right (reversed)
```

**Side walls** (8 triangles total, 2 per side):
```
Left wall (x=x_start):
  Triangle 1: (v0, v5, v1)
  Triangle 2: (v0, v4, v5)

Right wall (x=x_end):
  Triangle 1: (v2, v3, v6)
  Triangle 2: (v3, v7, v6)

Bottom wall (y=y_start):
  Triangle 1: (v0, v3, v7)
  Triangle 2: (v0, v7, v4)

Top wall (y=y_end):
  Triangle 1: (v1, v6, v2)
  Triangle 2: (v1, v5, v6)
```

**Output**: `triangles: List[Tuple[int, int, int]]`

**Why**: CCW winding = outward normals, proper manifold topology

## Data Structures

### Region (from region_merger.py)
```python
class Region:
    color: Tuple[int, int, int]  # RGB
    pixels: Set[Tuple[int, int]]  # (x, y) coordinates
```

### Sub-Region (internal)
```python
# 4-connected split of original region
SubRegion = Set[Tuple[int, int]]  # Pixel coordinates
```

### Horizontal Strip (internal)
```python
# Consecutive horizontal run of pixels
Strip = Tuple[int, int, int]  # (x_start, x_end, y)
```

### Rectangle (internal)
```python
# Merged vertical strips
Rectangle = Tuple[int, int, int, int]  # (x_start, x_end, y_start, y_end)
```

### Mesh (output, from mesh_generator.py)
```python
class Mesh:
    vertices: List[Tuple[float, float, float]]  # (x_mm, y_mm, z_mm)
    triangles: List[Tuple[int, int, int]]  # (v0_idx, v1_idx, v2_idx)
```

## Expected Results

### Manifold Properties
- ✅ Every edge shared by exactly 2 triangles
- ✅ No boundary edges (0 edges with only 1 triangle)
- ✅ No non-manifold edges (0 edges with 3+ triangles)
- ✅ Shared vertices at rectangle corners
- ✅ CCW winding on all triangles

### Reduction Estimates
- Small pixel art (16x16): 10-30% reduction
- Medium pixel art (64x64): 30-50% reduction
- Large screenshots (320x200): 50-70% reduction
- Solid color blocks: 90%+ reduction

### Reliability
- 100% success rate (no fallback needed)
- No external dependencies (shapely, triangle)
- Simple pure Python + NumPy
- Predictable, deterministic output

## Implementation Plan

### New Module: `rectangle_optimizer.py`

**Main entry point**:
```python
def optimize_region_rectangles(
    region: Region,
    pixel_data: PixelData,
    config: ConversionConfig
) -> Mesh:
    """
    Generate optimized mesh using rectangle merging.
    
    Guaranteed to produce manifold meshes with 0 non-manifold edges.
    """
    pass
```

**Internal functions**:
```python
def split_to_4_connectivity(pixels: Set[Tuple[int, int]]) -> List[Set[Tuple[int, int]]]:
    """Phase 1: Split 8-connectivity region into 4-connected sub-regions."""
    pass

def merge_horizontal_strips(pixels: Set[Tuple[int, int]]) -> List[Tuple[int, int, int]]:
    """Phase 2: Merge consecutive horizontal pixels into strips."""
    pass

def merge_vertical_rectangles(strips: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int, int]]:
    """Phase 3: Merge vertically aligned strips into rectangles."""
    pass

def generate_vertices(
    rectangles: List[Tuple[int, int, int, int]],
    pixel_data: PixelData,
    config: ConversionConfig
) -> Tuple[List[Tuple[float, float, float]], Dict[Tuple[float, float, float], int]]:
    """Phase 4: Generate shared vertices for all rectangles."""
    pass

def generate_triangles(
    rectangles: List[Tuple[int, int, int, int]],
    vertex_map: Dict[Tuple[float, float, float], int]
) -> List[Tuple[int, int, int]]:
    """Phase 5: Generate triangles with proper winding."""
    pass
```

### Integration

Update `pixel_to_3mf.py`:
```python
# Replace polygon_optimizer import with rectangle_optimizer
from .rectangle_optimizer import optimize_region_rectangles

# In mesh generation code:
if config.optimize_mesh:
    mesh = optimize_region_rectangles(region, pixel_data, config)
else:
    mesh = generate_region_mesh_original(region, pixel_data, config)
```

### Testing Strategy

1. **Unit tests**: Test each phase independently
2. **Integration test**: baby-yoda-xmas-ornament.png (known problem case)
3. **Scale test**: 320x200 screenshots (measure reduction)
4. **Manifold validation**: count_all_nm.py should report 0 non-manifold edges
5. **Visual test**: Load in Bambu Studio, verify no errors, print test model

## Comparison to Current Approach

| Aspect | Polygon + Triangulation | Rectangle Merging |
|--------|------------------------|-------------------|
| Dependencies | shapely, triangle | None (pure Python) |
| Manifold edges | 54 non-manifold ❌ | 0 non-manifold ✅ |
| Reliability | Fails on some models | 100% success ✅ |
| Code complexity | High (935 lines) | Low (est. 300 lines) |
| Reduction | 20-77% (when works) | 30-70% (predictable) |
| Handles diagonals | Yes (creates bugs) | No (by design) ✅ |
| Maintenance | Complex, hard to debug | Simple, easy to understand |

## Migration Path

1. Implement `rectangle_optimizer.py` as new module
2. Add flag `--optimize-method [polygon|rectangle]` for comparison
3. Test on all sample images
4. Make rectangle default, keep polygon as legacy option
5. After validation period, remove polygon code entirely
6. Update documentation to reflect simpler approach

## Success Criteria

- ✅ 0 non-manifold edges on all test images
- ✅ 0 boundary edges on all test images
- ✅ Loads in Bambu Studio without errors or warnings
- ✅ At least 30% reduction on large screenshots (320x200)
- ✅ All existing tests pass
- ✅ Simpler codebase (fewer lines, fewer dependencies)
