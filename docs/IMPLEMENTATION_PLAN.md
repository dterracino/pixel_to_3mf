# Implementation Plan: Config Refactor + Backing Plate Optimization + Auto-Crop

## Overview

This document outlines the changes needed to improve the pixel_to_3mf converter:

1. Create a config object to clean up function signatures
2. Optimize backing plate generation for rectangular images
3. Add auto-crop feature for transparent borders
4. Add connectivity mode flag for debugging

---

## 1. Update Config Object

### Current State

The `ConversionConfig` object already exists in your codebase!

### What We Need to Add

Just add the new fields for the features we're implementing:

#### Update `config.py`

```python
@dataclass
class ConversionConfig:
    # ... existing fields ...
    
    # ADD THESE NEW FIELDS:
    # Processing options
    auto_crop: bool = False
    connectivity: int = 8  # 0 (no merge), 4 (edge only), or 8 (includes diagonals)
```

#### Update validation in `__post_init__`

```python
def __post_init__(self):
    """Validate config values."""
    # ... existing validations ...
    
    # ADD THIS VALIDATION:
    if self.connectivity not in (0, 4, 8):
        raise ValueError(f"connectivity must be 0, 4, or 8, got {self.connectivity}")
```

That's it! The config infrastructure is already there, we just need to add two new fields.

---

## 2. Optimize Backing Plate for Rectangles

### Problem

For large rectangular images (like 320x200 c64ready.png), the backing plate:

- Has 144+ vertices (traces outline of all colored pixels)
- Can't be optimized (too complex)
- Results in huge file with thousands of triangles
- Makes slicer slow and unresponsive

### Solution

Detect when an image is a simple rectangle (no transparency) and generate a trivial 8-vertex, 12-triangle rectangular prism instead.

#### Add to `mesh_generator.py`

```python
def generate_backing_plate(pixel_data: PixelData, config: ConversionConfig):
    """
    Generate the backing plate mesh.
    
    Automatically uses optimized path for simple rectangles!
    """
    # Fast path: check if it's just a simple rectangle
    if _is_simple_rectangle(pixel_data):
        return _create_simple_rectangle_backing_plate(pixel_data, config.base_height_mm)
    
    # Complex path: use the current union approach for sprites with holes
    return _create_complex_backing_plate(pixel_data, config.base_height_mm)


def _is_simple_rectangle(pixel_data: PixelData) -> bool:
    """
    Check if all pixels form a complete rectangle (no transparency).
    
    This is perfect for full-frame images like screenshots or large pixel art.
    """
    total_expected = pixel_data.width * pixel_data.height
    total_actual = len(pixel_data.pixels)
    return total_expected == total_actual


def _create_simple_rectangle_backing_plate(pixel_data: PixelData, base_height_mm: float):
    """
    Create a simple rectangular backing plate - just 12 triangles!
    
    Perfect for images with no transparency or holes.
    Way more efficient than tracing complex outlines.
    """
    width_mm = pixel_data.width * pixel_data.pixel_size_mm
    height_mm = pixel_data.height * pixel_data.pixel_size_mm
    
    # 8 vertices (rectangular prism)
    # Bottom 4 corners at z=0
    # Top 4 corners at z=base_height_mm
    vertices = [
        (0, 0, 0),                              # 0: bottom-left-front
        (width_mm, 0, 0),                       # 1: bottom-right-front
        (width_mm, height_mm, 0),               # 2: bottom-right-back
        (0, height_mm, 0),                      # 3: bottom-left-back
        (0, 0, base_height_mm),                 # 4: top-left-front
        (width_mm, 0, base_height_mm),          # 5: top-right-front
        (width_mm, height_mm, base_height_mm),  # 6: top-right-back
        (0, height_mm, base_height_mm),         # 7: top-left-back
    ]
    
    # 12 triangles (2 per face, 6 faces)
    # Use counter-clockwise winding for outward-facing normals
    triangles = [
        # Bottom face (z=0) - looking up from below
        (0, 2, 1), (0, 3, 2),
        # Top face (z=base_height_mm) - looking down from above
        (4, 5, 6), (4, 6, 7),
        # Front face (y=0)
        (0, 1, 5), (0, 5, 4),
        # Back face (y=height_mm)
        (2, 3, 7), (2, 7, 6),
        # Left face (x=0)
        (0, 4, 7), (0, 7, 3),
        # Right face (x=width_mm)
        (1, 2, 6), (1, 6, 5),
    ]
    
    return {"vertices": vertices, "triangles": triangles}


def _create_complex_backing_plate(pixel_data: PixelData, base_height_mm: float):
    """
    Create backing plate using the current union approach.
    
    This is the existing implementation - handles sprites with holes,
    irregular shapes, etc.
    """
    # ... existing implementation ...
```

#### Expected Results

- **c64ready.png (320x200):** Backing plate goes from thousands of triangles → 12 triangles!
- **Small sprites with holes:** Still uses complex method (works as before)
- **File size:** Potentially 50KB+ smaller for large rectangular images
- **Slicer performance:** Much faster loading and manipulation

---

## 3. Add Auto-Crop Feature

### Current Issue: Transparent Border Waste

Images with transparent borders:

- Fail the "simple rectangle" check
- Process unnecessary transparent pixels
- Result in larger models and files than needed

### Proposed Solution: Auto-Crop Transparent Edges

Add `--auto-crop` flag that trims fully transparent edges before processing.

#### Add to `image_processor.py`

```python
def auto_crop_transparency(pixel_data: PixelData) -> PixelData:
    """
    Crop away fully transparent edges.
    
    Finds the bounding box of all non-transparent pixels and crops
    the image to just that area. This removes wasted space and can
    enable optimizations like simple rectangle backing plates.
    
    Args:
        pixel_data: The pixel data to crop
    
    Returns:
        New PixelData with adjusted dimensions, or original if no cropping needed
    """
    if not pixel_data.pixels:
        return pixel_data  # Empty image, nothing to crop
    
    # Find the actual bounds of non-transparent pixels
    pixel_coords = pixel_data.pixels.keys()
    min_x = min(x for x, y in pixel_coords)
    max_x = max(x for x, y in pixel_coords)
    min_y = min(y for x, y in pixel_coords)
    max_y = max(y for x, y in pixel_coords)
    
    # If already at edges, no cropping needed
    if (min_x == 0 and min_y == 0 and 
        max_x == pixel_data.width - 1 and 
        max_y == pixel_data.height - 1):
        return pixel_data
    
    # Calculate new dimensions
    new_width = max_x - min_x + 1
    new_height = max_y - min_y + 1
    
    # Remap pixel coordinates to new origin (0, 0)
    new_pixels = {}
    for (x, y), color in pixel_data.pixels.items():
        new_x = x - min_x
        new_y = y - min_y
        new_pixels[(new_x, new_y)] = color
    
    # Create new PixelData with cropped dimensions
    # Pixel size stays the same!
    return PixelData(
        width=new_width,
        height=new_height,
        pixels=new_pixels,
        pixel_size_mm=pixel_data.pixel_size_mm
    )
```

#### Update `pixel_to_3mf.py`

```python
def convert_image_to_3mf(...):
    # Step 1: Load image
    _progress("load", f"Loading image: {input_file.name}")
    pixel_data = load_image(str(input_path), config)
    
    # Step 1.5: Auto-crop if requested
    if config.auto_crop:
        original_size = f"{pixel_data.width}x{pixel_data.height}"
        pixel_data = auto_crop_transparency(pixel_data)
        new_size = f"{pixel_data.width}x{pixel_data.height}"
        
        if original_size != new_size:
            _progress("crop", f"Auto-cropped from {original_size} to {new_size}")
        else:
            _progress("crop", "No cropping needed (image already at bounds)")
    
    _progress("load", f"Image loaded: {pixel_data.width}x{pixel_data.height}px, "
                     f"{pixel_data.pixel_size_mm}mm per pixel")
    
    # ... continue with resolution check, etc.
```

#### Update `cli.py`

```python
parser.add_argument(
    "--auto-crop",
    action="store_true",
    help="Automatically crop away fully transparent edges before processing"
)
```

#### Use Cases

```bash
# Sprite with transparent padding
python run_converter.py sprite.png --auto-crop

# Screenshot with letterboxing
python run_converter.py screenshot.png --auto-crop

# Batch processing mixed images
python run_converter.py *.png --auto-crop
```

---

## 4. Add Connectivity Mode Flag

### Current Issue: Complex Geometries from 8-Connectivity

8-connectivity can create complex geometries that fail optimization:

- Diagonal-only connections create "choke points"
- Results in MultiPolygon (disconnected parts)
- Optimizer falls back to non-optimized mesh

Can't test if 4-connectivity would solve these issues because we removed the flag!

### Proposed Solution: Configurable Connectivity Mode

Add connectivity mode as a config option and CLI flag with validation.

#### Already in Config (from Section 1)

```python
@dataclass
class ConversionConfig:
    # ...
    connectivity: int = 8  # 4 or 8 (diagonal merging), or 0 (no merging)
    
    def __post_init__(self):
        """Validate config values."""
        # ... other validations ...
        if self.connectivity not in (0, 4, 8):
            raise ValueError(f"connectivity must be 0, 4, or 8, got {self.connectivity}")
```

**Connectivity modes:**

- `0` = No merging (each pixel is separate object) - useful for debugging
- `4` = Edge-connected only (classic flood fill)
- `8` = Includes diagonals (fewer objects, may create complex geometry)

#### Update `region_merger.py`

```python
def flood_fill(
    start_x: int,
    start_y: int,
    target_color: Tuple[int, int, int],
    pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]],
    visited: Set[Tuple[int, int]],
    connectivity: int = 8
) -> Set[Tuple[int, int]]:
    """
    Perform flood fill to find all connected pixels of the same color.
    
    Args:
        start_x, start_y: Starting pixel coordinates
        target_color: RGB color we're looking for
        pixels: Dict of all non-transparent pixels
        visited: Set of already-processed pixels
        connectivity: 0 (no merge), 4 (edge-connected), or 8 (includes diagonals)
    
    Returns:
        Set of (x, y) coordinates in this connected region
    """
    region_pixels: Set[Tuple[int, int]] = set()
    queue: List[Tuple[int, int]] = [(start_x, start_y)]
    visited.add((start_x, start_y))
    
    while queue:
        x, y = queue.pop(0)
        region_pixels.add((x, y))
        
        # Connectivity 0 means no merging - just return this single pixel
        if connectivity == 0:
            continue
        
        # Build neighbor list based on connectivity mode
        if connectivity == 8:
            # 8-connectivity: includes diagonals
            neighbors = [
                (x + 1, y),      # right
                (x - 1, y),      # left
                (x, y + 1),      # down
                (x, y - 1),      # up
                (x + 1, y + 1),  # diagonal: down-right
                (x - 1, y - 1),  # diagonal: up-left
                (x + 1, y - 1),  # diagonal: up-right
                (x - 1, y + 1),  # diagonal: down-left
            ]
        else:  # connectivity == 4
            # 4-connectivity: edge-connected only
            neighbors = [
                (x + 1, y),  # right
                (x - 1, y),  # left
                (x, y + 1),  # down
                (x, y - 1),  # up
            ]
        
        # ... rest of flood fill logic ...
```

```python
def merge_regions(pixel_data: PixelData, config: ConversionConfig) -> List[Region]:
    """Merge connected pixels into regions."""
    # ... existing code ...
    
    # Pass connectivity to flood_fill
    region_pixels = flood_fill(
        x, y, target_color, pixels, visited,
        connectivity=config.connectivity
    )
```

#### Add CLI Arguments

```python
parser.add_argument(
    "--connectivity",
    type=int,
    choices=[0, 4, 8],
    default=8,
    help="Pixel connectivity mode: "
         "0 (no merging, each pixel separate - for debugging), "
         "4 (edge-connected only - classic, simple geometry), "
         "8 (includes diagonals - fewer objects, may be complex). "
         "Default: 8"
)
```

#### Testing

```bash
# Default: 8-connectivity (fewer objects, may have optimization issues)
python run_converter.py c64ready.png

# Test with 4-connectivity (more objects, simpler geometry)
python run_converter.py c64ready.png --connectivity 4

# Test with no merging (every pixel separate - good for debugging)
python run_converter.py sprite.png --connectivity 0

# Compare results to see if optimization warnings disappear!
```

---

## 5. Clean Up Polygon Optimizer Error Handling

### Current Issue: Messy Error Output

The polygon optimizer raises `ValueError` when it detects unsuitable geometry, which gets caught and re-reported as a warning. This creates messy output with both a traceback AND a warning:

```text
Traceback (most recent call last):
  File "polygon_optimizer.py", line 523, in generate_region_mesh_optimized
    vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
  File "polygon_optimizer.py", line 209, in triangulate_polygon_2d
    _validate_polygon_for_triangulation(poly)
  File "polygon_optimizer.py", line 165, in _validate_polygon_for_triangulation
    raise ValueError("Polygon has 1 holes and complex exterior...")
    
UserWarning: Optimized mesh generation failed for region with 28 pixels, 
falling back to original: Polygon has 1 holes and complex exterior...
```

Users see the error twice, and the traceback makes it look like something crashed (when it's actually working fine via fallback).

### Proposed Solution: Return Validation Results

Change validation to return a result instead of raising an exception.

#### Update `polygon_optimizer.py`

**Current approach (raises exception):**

```python
def _validate_polygon_for_triangulation(poly):
    """
    Validate that polygon is suitable for optimization.
    Raises ValueError if not suitable.
    """
    num_holes = len(poly.interiors)
    num_vertices = len(poly.exterior.coords)
    
    if num_holes > 0 and num_vertices > 20:
        raise ValueError(
            f"Polygon has {num_holes} holes and complex exterior "
            f"({num_vertices} vertices). This geometry is not suitable for optimization."
        )
    
    if num_vertices > MAX_VERTICES:
        raise ValueError(
            f"Polygon exterior has too many vertices ({num_vertices}). "
            f"This geometry is not suitable for optimization."
        )
```

**New approach (returns validation result):**

```python
def _validate_polygon_for_triangulation(poly) -> tuple[bool, str]:
    """
    Validate that polygon is suitable for optimization.
    
    Returns:
        (bool, str): (is_valid, error_message)
                     If valid: (True, "")
                     If invalid: (False, "reason for failure")
    """
    num_holes = len(poly.interiors)
    num_vertices = len(poly.exterior.coords)
    
    # Check for holes with complex exterior
    if num_holes > 0 and num_vertices > 20:
        return (
            False,
            f"Polygon has {num_holes} holes and complex exterior "
            f"({num_vertices} vertices). This geometry is not suitable for optimization."
        )
    
    # Check for too many vertices
    if num_vertices > MAX_VERTICES:
        return (
            False,
            f"Polygon exterior has too many vertices ({num_vertices}). "
            f"This geometry is not suitable for optimization."
        )
    
    # All checks passed!
    return (True, "")
```

**Update callers to check the result:**

```python
def generate_region_mesh_optimized(region, pixel_data, color_height_mm):
    """Generate optimized mesh for a region."""
    try:
        # Convert pixels to polygon
        poly = pixels_to_polygon(region.pixels, pixel_data.pixel_size_mm)
        
        # Validate polygon (no longer raises exception!)
        is_valid, error_msg = _validate_polygon_for_triangulation(poly)
        
        if not is_valid:
            # Clean single warning, no traceback!
            warnings.warn(
                f"Optimized mesh generation failed for region with {len(region.pixels)} pixels, "
                f"falling back to original: {error_msg}"
            )
            return generate_region_mesh_original(region, pixel_data, color_height_mm)
        
        # Continue with optimization...
        vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
        # ... rest of optimization ...
        
    except Exception as e:
        # Only catch truly unexpected errors
        warnings.warn(
            f"Unexpected error during optimization for region with {len(region.pixels)} pixels, "
            f"falling back to original: {e}"
        )
        return generate_region_mesh_original(region, pixel_data, color_height_mm)
```

**Do the same for backing plate validation:**

```python
def generate_backing_plate_optimized(...):
    # ... create polygon ...
    
    # Validate (returns result instead of raising)
    is_valid, error_msg = _validate_polygon_for_triangulation(backing_poly)
    
    if not is_valid:
        warnings.warn(f"Optimized backing plate generation failed, falling back to original: {error_msg}")
        return generate_backing_plate_original(...)
    
    # ... continue with optimization ...
```

### Expected Output After Fix

**Before (messy):**

```text
Traceback (most recent call last):
  [10 lines of traceback]
UserWarning: Optimized mesh generation failed for region with 28 pixels...
```

**After (clean):**

```text
⚠️  Falling back to original mesh for region with 28 pixels: Polygon has 1 hole and complex exterior (26 vertices)
```

Much cleaner! Users see one line explaining what happened, no scary traceback.

### Benefits

- ✅ Cleaner output (one line instead of traceback + warning)
- ✅ Less confusing for users (no "error" when things are working fine)
- ✅ Faster execution (no exception overhead)
- ✅ Better separation of concerns (validation vs. execution)

---

## 6. Implementation Order

**Recommended order:**

1. **Update config object** (add the two new fields)
   - Add `auto_crop` and `connectivity` fields to existing config
   - Add validation for connectivity
   - Update CLI to pass these new fields
   - Test that everything still works

2. **Simple rectangle backing plate** (immediate wins)
   - Add detection and simple mesh generation
   - Test with c64ready.png and sprites
   - Should see huge file size reduction

3. **Auto-crop feature** (enables more optimizations)
   - Add cropping function
   - Wire into conversion pipeline
   - Test with bordered images

4. **Connectivity flag** (for debugging/testing)
   - Update flood_fill to use config.connectivity
   - Test both modes to compare

---

## 7. Testing Checklist

After implementing:

- [ ] Small sprite (64x64) still works
- [ ] Large rectangle (320x200) uses simple backing plate
- [ ] Sprite with holes uses complex backing plate
- [ ] Auto-crop removes transparent borders
- [ ] Auto-crop with no borders does nothing
- [ ] 4-connectivity creates more objects
- [ ] 8-connectivity creates fewer objects
- [ ] Config validation catches bad values
- [ ] CLI arguments map to config correctly
- [ ] Programmatic API works with config object

---

## 8. Expected Benefits

### File Size

- **c64ready.png:** 50KB+ smaller (simple backing plate)
- **Images with borders:** Smaller (auto-crop removes waste)

### Slicer Performance  

- **Large images:** Much faster (simple backing plate loads instantly)
- **Complex sprites:** Same as before (still uses complex method)

### Code Maintainability

- **Function signatures:** Clean (4 params instead of 8+)
- **Adding features:** Easy (just add to config dataclass)
- **Type safety:** Better (config validates itself)

### Flexibility

- **Connectivity mode:** Can test/debug optimization issues
- **Auto-crop:** Handles more image formats automatically

---

## 9. Files to Update

- `config.py` - Add `auto_crop` and `connectivity` fields
- `mesh_generator.py` - Add simple rectangle backing plate
- `image_processor.py` - Add auto-crop function
- `region_merger.py` - Update flood_fill to use connectivity from config
- `cli.py` - Add `--auto-crop` and `--connectivity` arguments
- `pixel_to_3mf.py` - Wire in auto-crop step
- `constants.py` - No changes needed

---

## Notes

- All validation moves to `ConversionConfig.__post_init__()`
- Backwards compatibility: Can still pass individual params and build config internally if needed
- The simple rectangle check is O(1) - just compares two numbers!
- Auto-crop is O(n) where n = number of non-transparent pixels
- Config makes adding future features trivial (just add one field!)

---

## Current Issues Being Addressed

1. **"Polygon exterior has too many vertices (144)"** → Solved by simple rectangle backing plate
2. **"Region produced 2 disconnected polygon parts"** → Can test with 4-connectivity flag
3. **"Polygon has 1 holes"** → Can debug with 4-connectivity to see if 8-connectivity causes it
4. **Bloated function signatures** → Solved by config object
5. **Images with transparent borders** → Solved by auto-crop

---

Ready to implement in the next session! 🚀
