# Feature Suggestions

This document contains feature ideas and enhancements that align with the pixel art to 3MF converter's core purpose. These are stretch goals that could improve the user experience and expand capabilities.

## High-Value Features

### 1. Support for Multi-Material Filament Mapping

**Description:** Allow users to define custom filament color mappings for their specific printer setup.

**Use Case:** A user has 4 AMS slots with specific colors loaded. They want to automatically map image colors to their available filaments.

**Implementation:**
```python
# New file: pixel_to_3mf/filament_mapping.py

class FilamentMapping:
    """Map image colors to available printer filaments."""
    
    def __init__(self, available_filaments: List[Tuple[str, Tuple[int, int, int]]]):
        """
        Initialize with available filaments.
        
        Args:
            available_filaments: List of (name, rgb) tuples
                Example: [
                    ("AMS Slot 1 - Red", (255, 0, 0)),
                    ("AMS Slot 2 - Blue", (0, 0, 255)),
                    ("AMS Slot 3 - White", (255, 255, 255)),
                    ("AMS Slot 4 - Black", (0, 0, 0))
                ]
        """
        pass
    
    def map_image(self, image_path: str) -> Dict[Tuple[int, int, int], str]:
        """
        Map image colors to available filaments using Delta E 2000.
        
        Returns mapping of image_color -> filament_name
        """
        pass
    
    def validate_image(self, image_path: str) -> Tuple[bool, str]:
        """
        Check if image can be printed with available filaments.
        
        Returns: (can_print, message)
        """
        pass

# CLI usage:
# python run_converter.py sprite.png --filament-mapping ams_config.json

# ams_config.json:
# {
#   "slots": [
#     {"name": "Red PLA", "rgb": [255, 0, 0]},
#     {"name": "Blue PLA", "rgb": [0, 0, 255]},
#     {"name": "White PLA", "rgb": [255, 255, 255]},
#     {"name": "Black PLA", "rgb": [0, 0, 0]}
#   ]
# }
```

**Benefits:**
- Helps users plan which filaments to load
- Warns if image colors don't match available filaments
- Generates accurate color names for slicer
- Could suggest color substitutions

**Complexity:** Medium

---

### 2. Preview Rendering

**Description:** Generate a 2D preview showing how the model will look with assigned colors.

**Use Case:** User wants to visualize the final model before printing.

**Implementation:**
```python
# New file: pixel_to_3mf/preview.py

def generate_preview(
    input_path: str,
    output_path: str,
    config: ConversionConfig,
    show_grid: bool = False,
    show_dimensions: bool = True
):
    """
    Generate a preview image showing the 3D model from above.
    
    Args:
        input_path: Original image
        output_path: Where to save preview (PNG)
        config: Conversion configuration
        show_grid: Overlay a mm grid
        show_dimensions: Show width/height labels
    """
    # Use PIL to:
    # 1. Load original image
    # 2. Apply region merging visualization (outline regions)
    # 3. Add grid overlay if requested
    # 4. Add dimension annotations
    # 5. Save as PNG
    pass

# CLI usage:
# python run_converter.py sprite.png --preview sprite_preview.png
```

**Benefits:**
- Helps users verify region merging worked correctly
- Shows actual dimensions in mm
- Visual confirmation before starting print
- Could show layer height coloring

**Complexity:** Low-Medium (mostly PIL image manipulation)

---

### 3. Automatic Color Reduction/Quantization

**Description:** Automatically reduce image colors to fit within max_colors limit.

**Use Case:** User has a 32-color image but printer only supports 16 filaments.

**Implementation:**
```python
# In image_processor.py

def reduce_colors(
    image: Image,
    max_colors: int,
    method: str = "kmeans"
) -> Image:
    """
    Reduce image to maximum number of colors.
    
    Args:
        image: PIL Image
        max_colors: Target color count
        method: "kmeans" or "median_cut" or "octree"
    
    Returns:
        Color-reduced image
    """
    # Use PIL.Image.quantize() with max_colors
    # Could also use sklearn.cluster.KMeans for better results
    pass

# CLI usage:
# python run_converter.py sprite.png --auto-reduce-colors
# python run_converter.py sprite.png --reduce-method median_cut
```

**Benefits:**
- Automatic handling of high-color images
- No need for manual editing
- Maintains visual quality
- Could preserve important colors (e.g., never merge black/white)

**Complexity:** Low (PIL has built-in quantization)

---

### 4. STL Export Option

**Description:** Also export to STL format in addition to 3MF.

**Use Case:** User wants to use a slicer that doesn't support multi-material 3MF files.

**Implementation:**
```python
# New file: pixel_to_3mf/stl_writer.py

def write_stl(
    output_path: str,
    meshes: List[Mesh],
    merge_all: bool = True
):
    """
    Export meshes to STL format.
    
    Args:
        output_path: Path to .stl file
        meshes: List of meshes to export
        merge_all: If True, merge into single STL; if False, create separate files
    """
    # STL format:
    # - Binary or ASCII
    # - Single mesh per file (or merge all)
    # - No color information (!)
    pass

# CLI usage:
# python run_converter.py sprite.png --also-stl
# python run_converter.py sprite.png --format stl  # STL only
```

**Benefits:**
- Wider slicer compatibility
- Single-color models still useful
- Could export regions as separate STL files

**Drawbacks:**
- Loses color information
- Less useful for multi-color prints

**Complexity:** Low (STL is simpler than 3MF)

---

### 5. Sprite Sheet Processing

**Description:** Process a sprite sheet with multiple sprites, generating separate 3MF files.

**Use Case:** User has a sheet of pixel art icons and wants to convert them all at once.

**Implementation:**
```python
# New file: pixel_to_3mf/sprite_sheet.py

def process_sprite_sheet(
    sheet_path: str,
    output_dir: str,
    sprite_width: int,
    sprite_height: int,
    padding: int = 0,
    naming_pattern: str = "sprite_{row}_{col}.3mf"
):
    """
    Split sprite sheet into individual sprites and convert each.
    
    Args:
        sheet_path: Path to sprite sheet image
        output_dir: Where to save individual 3MF files
        sprite_width: Width of each sprite in pixels
        sprite_height: Height of each sprite in pixels
        padding: Pixels between sprites
        naming_pattern: Filename pattern (supports {row}, {col}, {index})
    """
    # 1. Load sprite sheet
    # 2. Calculate grid dimensions
    # 3. Extract each sprite
    # 4. Skip empty sprites (all transparent)
    # 5. Convert each to 3MF
    pass

# CLI usage:
# python run_converter.py sheet.png --sprite-sheet 16x16 --output-dir sprites/
# python run_converter.py sheet.png --sprite-sheet 32x32 --padding 1
```

**Benefits:**
- Batch process entire sprite sheets
- Automatic naming
- Skip empty/transparent sprites
- Great for game developers

**Complexity:** Medium (image slicing + batch conversion)

---

### 6. Height Map Support

**Description:** Use grayscale values to control layer heights (relief/emboss effect).

**Use Case:** Create models with varying depths based on image brightness.

**Implementation:**
```python
# In config.py
class ConversionConfig:
    # ... existing fields ...
    height_mode: str = "flat"  # "flat" or "relief"
    min_height_mm: float = 0.5  # Black color height
    max_height_mm: float = 3.0  # White color height

# In mesh_generator.py
def generate_region_mesh_relief(
    region: Region,
    pixel_data: PixelData,
    config: ConversionConfig
):
    """Generate mesh with height based on color brightness."""
    # For each pixel, calculate height from brightness
    # brightness = (R + G + B) / 3
    # height = lerp(min_height, max_height, brightness / 255)
    # Generate variable-height mesh
    pass

# CLI usage:
# python run_converter.py image.png --relief --min-height 0.5 --max-height 3.0
```

**Benefits:**
- Create embossed/relief models
- Add depth to flat pixel art
- Artistic possibilities

**Drawbacks:**
- More complex mesh generation
- Loses flat, clean aesthetic
- May not work well with pixel art

**Complexity:** High (variable-height mesh generation is tricky)

---

## Medium-Value Features

### 7. Custom Object Grouping

**Description:** Allow users to manually group regions into named objects.

**Use Case:** A character sprite where you want "Head", "Body", "Arms" as separate objects in the slicer instead of individual color regions.

**Implementation:**
```python
# New file: grouping_config.json
{
  "groups": {
    "Head": {
      "colors": ["#FFDBAC", "#8B4513"],  # Skin and hair
      "regions": [1, 2, 3]  # Region indices
    },
    "Body": {
      "colors": ["#FF0000", "#0000FF"],  # Shirt colors
      "regions": [4, 5, 6, 7]
    }
  }
}

# CLI usage:
# python run_converter.py sprite.png --groups grouping_config.json
```

**Benefits:**
- Better organization in slicer
- Logical grouping for complex models
- Easier to assign filaments

**Complexity:** Medium (modify 3MF structure to support nested groups)

---

### 8. Dithering Support

**Description:** Apply dithering when reducing colors to preserve visual detail.

**Use Case:** Convert photos or high-color images while maintaining detail.

**Implementation:**
```python
# In image_processor.py
def apply_dithering(
    image: Image,
    palette: List[Tuple[int, int, int]],
    algorithm: str = "floyd_steinberg"
) -> Image:
    """Apply dithering to reduce colors while preserving detail."""
    # Floyd-Steinberg, Ordered (Bayer), or Atkinson dithering
    # Could use PIL.Image.quantize with dither parameter
    pass

# CLI usage:
# python run_converter.py photo.png --dither --max-colors 16
```

**Benefits:**
- Better photo conversion
- Preserves gradients and details
- Creates interesting pixel art effects

**Drawbacks:**
- May create very complex regions
- Larger file sizes
- Pixel art loses clean edges

**Complexity:** Low-Medium (PIL supports dithering)

---

### 9. Hollow/Shell Mode

**Description:** Generate hollow models (just the shell) to save filament.

**Use Case:** Large models where solid fill wastes material.

**Implementation:**
```python
# In config.py
class ConversionConfig:
    # ... existing fields ...
    hollow: bool = False
    wall_thickness_mm: float = 2.0  # Thickness of walls

# In mesh_generator.py
def generate_hollow_mesh(region, pixel_data, config):
    """Generate hollow mesh with specified wall thickness."""
    # For each region:
    # 1. Generate outer perimeter at full height
    # 2. Generate inner perimeter (inset by wall_thickness)
    # 3. Connect with walls
    # 4. No solid fill
    pass
```

**Benefits:**
- Saves filament
- Faster prints
- Good for large decorative pieces

**Drawbacks:**
- More complex geometry
- May need supports
- Less structurally sound

**Complexity:** High (complex geometry generation)

---

### 10. Multi-Layer Support

**Description:** Stack multiple images vertically to create layered models.

**Use Case:** Create a 3D model from multiple 2D layers (like animation frames).

**Implementation:**
```python
# New file: pixel_to_3mf/layered.py

def convert_layered_image_to_3mf(
    layer_images: List[str],
    output_path: str,
    layer_spacing_mm: float = 1.0,
    config: ConversionConfig
):
    """
    Convert multiple images into a layered 3D model.
    
    Args:
        layer_images: List of image paths (bottom to top)
        output_path: Output 3MF path
        layer_spacing_mm: Vertical spacing between layers
        config: Conversion configuration
    """
    # 1. Load all layers
    # 2. Generate meshes for each layer
    # 3. Stack vertically with spacing
    # 4. Export to single 3MF
    pass

# CLI usage:
# python run_converter.py --layered layer1.png layer2.png layer3.png --spacing 1.5
```

**Benefits:**
- Create true 3D models from 2D layers
- Interesting artistic possibilities
- Animation frame visualization

**Complexity:** Medium (mostly coordinate offsetting)

---

## Low-Priority/Nice-to-Have Features

### 11. Web Interface

**Description:** Browser-based interface for conversion.

**Implementation:** Flask/FastAPI backend + simple HTML frontend

**Benefits:**
- No installation required
- Easy to use for non-technical users
- Could show preview immediately

**Complexity:** High (full web application)

---

### 12. Prusa Connect Integration

**Description:** Directly upload converted models to Prusa Connect.

**Benefits:** Streamlined workflow for Prusa users

**Complexity:** Medium (API integration)

---

### 13. Fusion 360/CAD Export

**Description:** Export to STEP or F3D format for further editing in CAD software.

**Benefits:** Advanced users can modify models

**Complexity:** High (complex CAD formats)

---

### 14. Edge Smoothing

**Description:** Option to smooth/round edges of pixel blocks.

**Implementation:** Add small fillets or chamfers to corners

**Benefits:** Less "blocky" appearance

**Drawbacks:** Loses pixel art aesthetic

**Complexity:** High (mesh modification)

---

### 15. Text Overlay

**Description:** Add text labels or numbers to models.

**Use Case:** Numbering parts, adding dates, etc.

**Complexity:** High (text to 3D mesh conversion)

---

### 16. Scaling Presets

**Description:** Common size presets (keychain, coaster, wall art, etc.)

**Implementation:**
```python
# In constants.py
SCALING_PRESETS = {
    "keychain": {"max_size_mm": 40},
    "coaster": {"max_size_mm": 90},
    "wall_art": {"max_size_mm": 200},
    "giant": {"max_size_mm": 400}
}

# CLI usage:
# python run_converter.py sprite.png --preset keychain
```

**Benefits:** Quick sizing for common use cases

**Complexity:** Very Low (just preset values)

---

### 17. Print Time Estimation

**Description:** Estimate print time based on model complexity.

**Implementation:** Simple heuristic based on layer count, area, and perimeter

**Benefits:** Helps users plan prints

**Complexity:** Low-Medium

---

### 18. Material Cost Estimation

**Description:** Estimate filament usage and cost.

**Implementation:** Calculate volume and multiply by material density and cost

**Benefits:** Budget planning

**Complexity:** Low

---

### 19. Watermarking

**Description:** Add subtle logo or signature to bottom of backing plate.

**Benefits:** Branding, copyright protection

**Complexity:** Medium

---

### 20. Animation Frame Sequencing

**Description:** Generate numbered files from animation frames for sequential printing.

**Use Case:** Print stop-motion frames or create flipbook

**Implementation:** Similar to sprite sheet processing

**Complexity:** Low

---

## Feature Implementation Priority

### Immediate Value (Should Consider)
1. **Filament Mapping** (#1) - High value for multi-material printing
2. **Preview Rendering** (#2) - Helps users verify results
3. **Auto Color Reduction** (#3) - Solves common problem
4. **Scaling Presets** (#16) - Quick win, easy implementation

### Medium-Term (Nice to Have)
5. **Sprite Sheet Processing** (#5) - Great for game developers
6. **STL Export** (#4) - Wider compatibility
7. **Custom Grouping** (#7) - Better organization
8. **Material Cost Estimation** (#18) - Practical utility

### Long-Term (If Requested)
9. **Height Map/Relief** (#6) - Artistic applications
10. **Hollow Mode** (#9) - Material savings
11. **Multi-Layer** (#10) - Advanced 3D modeling
12. **Dithering** (#8) - Photo conversion

### Future/Experimental
13. **Web Interface** (#11) - Accessibility
14. **Edge Smoothing** (#14) - Aesthetic option
15. **CAD Export** (#13) - Advanced users
16. Everything else - As needed

---

## Technical Debt Items

### Performance Optimization
- Profile mesh generation for large images
- Consider Cython for hot paths
- Parallel processing for batch mode
- Incremental progress saving for very large conversions

### Code Organization
- Extract CLI helpers into separate modules
- Create shared utilities module
- Add more integration tests
- Document plugin architecture for extensions

### Build/Distribution
- Create PyPI package
- Add GUI launcher (pyinstaller/cx_Freeze)
- Docker container for web service
- GitHub Actions for releases

---

## Community Suggestions Welcome!

This document should be a living document. If you have feature ideas:

1. Open an issue on GitHub with tag `enhancement`
2. Describe the use case
3. Explain why it aligns with the tool's purpose
4. Suggest implementation approach if possible

**Selection Criteria:**
- ✅ Aligns with pixel art → 3D printing workflow
- ✅ Provides clear value to users
- ✅ Feasible with current architecture
- ✅ Doesn't overcomplicate the core tool
- ✅ Has real-world use cases

**Out of Scope:**
- ❌ General 3D modeling (use Blender)
- ❌ Full photo editing (use GIMP/Photoshop)
- ❌ Slicer functionality (use Bambu Studio/PrusaSlicer)
- ❌ 3D scanning (different domain)
- ❌ Generative AI (out of scope)

Keep the tool focused on what it does best: converting pixel art to 3D printable models! 🎨→🖨️
