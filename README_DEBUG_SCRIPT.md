# Debug Render Coordinates Script

This directory contains `debug_render_coords.py`, a debugging tool for analyzing 3D model coordinate transformations and rendering issues.

## Purpose

The debug script helps diagnose rendering issues by:
1. Analyzing mesh coordinate data (vertices, triangles, bounds)
2. Generating multi-view renders from different camera angles
3. Displaying detailed coordinate information for troubleshooting

## Usage

```bash
python debug_render_coords.py <input_image> [options]
```

### Basic Example

```bash
python debug_render_coords.py samples/input/sprites/nes-samus.png
```

This will:
- Load and process the image
- Generate meshes for all regions plus backing plate
- Print detailed coordinate analysis to console
- Create 7 different render views in `/tmp/debug_model_*.png`

### Advanced Options

```bash
python debug_render_coords.py samples/input/sprites/nes-samus.png \
    --output /tmp/my_debug \
    --max-size 150 \
    --color-height 1.5 \
    --base-height 0.8
```

Options:
- `--output PATH`: Base path for output files (default: `/tmp/debug_model`)
- `--max-size MM`: Maximum model dimension in mm (default: 200.0)
- `--color-height MM`: Color layer height in mm (default: 1.0)
- `--base-height MM`: Base layer height in mm (default: 1.0)

## Output Files

The script generates 7 different view angles:

1. **top_view** - Looking straight down (elev=90°, azim=0°)
2. **bottom_view** - Looking straight up from below (elev=-90°, azim=0°)
3. **front_view** - Looking from the front along Y axis (elev=0°, azim=0°)
4. **right_view** - Looking from the right along X axis (elev=0°, azim=90°)
5. **left_view** - Looking from the left (elev=0°, azim=-90°)
6. **default_view** - Default 3D perspective (elev=30°, azim=-60°)
7. **isometric_view** - Isometric-style view (elev=45°, azim=-45°)

## Console Output

The script prints detailed analysis including:

- Image dimensions (pixels and mm)
- Number of regions and unique colors
- For each mesh:
  - Vertex and triangle counts
  - X, Y, Z coordinate ranges
  - Sample vertices (first 5 and last 5)
- Overall bounds across all meshes

## Use Cases

### Debugging Z-Fighting Issues

If you see artifacts where surfaces overlap incorrectly, use the script to:
1. Check if any meshes share the same Z coordinates (coplanar surfaces)
2. View from different angles to identify which surfaces are problematic
3. Verify the Z-offset fix is working correctly

### Verifying Mesh Geometry

Use the coordinate analysis to verify:
- Colored regions are at the correct height (Z range should be [0, color_height])
- Backing plate extends below (Z range should be [-base_height, 0])
- Model dimensions match expectations
- No unexpected gaps or overlaps

### Understanding Coordinate Transformations

The script shows how image pixel coordinates transform to 3D mesh coordinates, helping you understand:
- Pixel size calculations
- Y-axis flipping (images have Y=0 at top, 3D has Y=0 at bottom)
- How regions map to mesh vertices

## Example Output

```
================================================================================
COORDINATE ANALYSIS
================================================================================

Model Dimensions: 100.000mm x 200.000mm
Total meshes: 44

region_1 - RGB(216, 40, 0):
  Vertices: 62
  Triangles: 124
  X range: [25.000, 75.000] (width: 50.000mm)
  Y range: [175.000, 200.000] (height: 25.000mm)
  Z range: [0.000, 1.000] (depth: 1.000mm)
  First 5 vertices:
    [0] (50.000, 187.500, 1.000)
    [1] (56.250, 187.500, 1.000)
    ...

backing_plate - RGB(255, 255, 255):
  Vertices: 794
  Triangles: 1584
  X range: [0.000, 100.000] (width: 100.000mm)
  Y range: [0.000, 200.000] (height: 200.000mm)
  Z range: [-1.000, 0.000] (depth: 1.000mm)
  ...

--------------------------------------------------------------------------------
OVERALL BOUNDS (all meshes combined):
  X: [0.000, 100.000]
  Y: [0.000, 200.000]
  Z: [-1.000, 1.000]
--------------------------------------------------------------------------------
```

## Technical Notes

### Z-Offset for Rendering

The script applies a small Z-offset (-0.01mm) to the backing plate during rendering to prevent Z-fighting artifacts in matplotlib. This offset is:
- **Only applied during visualization** (not to the actual mesh data)
- **Invisible to the eye** (10 microns)
- **Necessary** because the backing plate top (Z=0) and region bottoms (Z=0) are coplanar

### Coordinate System

The 3D coordinate system used:
- **X axis**: Left to right (0 to width)
- **Y axis**: Bottom to top (0 to height) - NOTE: Images are Y-flipped during loading
- **Z axis**: Bottom to top (negative = backing plate, positive = colored regions)
