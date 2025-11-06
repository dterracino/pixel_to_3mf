# Pixel Art to 3MF Converter - AI Agent Instructions

## Project Overview

This tool converts pixel art images into 3D-printable 3MF files. It performs region merging (flood-fill with 8-connectivity), color naming via perceptual Delta E 2000 matching, and generates **manifold** 3MF meshes with proper topology.

**Entry points**: `run_converter.py` (CLI wrapper) → `pixel_to_3mf.cli.main()`

## Architecture: Clean Separation of Concerns

The codebase strictly separates **CLI layer** from **business logic**:

- **`cli.py`**: All argparse, print statements, error display, progress callbacks
- **`pixel_to_3mf.py`**: Pure conversion logic - NO print/argparse, fully programmatic
- This separation is CRITICAL - never add print statements to business logic modules

**Pipeline flow**:
```
Image Load → Y-Flip → Color Validation → Exact Scaling → Region Merging (8-connectivity flood-fill) 
→ Manifold Mesh Generation → 3MF Export
```

### Module Responsibilities

- **`constants.py`**: ALL magic numbers live here (defaults, precision, line width, color limits)
- **`image_processor.py`**: PIL loading, Y-axis flipping, color validation, exact scaling (no rounding)
- **`region_merger.py`**: Flood-fill with **8-connectivity** (includes diagonals), bounds calculation
- **`mesh_generator.py`**: Generates **manifold** meshes (shared vertices, CCW winding, proper topology)
- **`threemf_writer.py`**: Creates ZIP with XML files (3MF spec compliance)

## Key Design Patterns

### 1. Constants Centralization
All defaults in `constants.py`. Change defaults there, NOT in function signatures:
```python
# CORRECT: Use constant as default
def my_func(height: float = COLOR_LAYER_HEIGHT_MM, max_colors: int = MAX_COLORS):
```

### 2. PixelData Container
`image_processor.py` returns a `PixelData` object bundling all image info. Pass this around instead of separate width/height/pixels variables.

### 3. Manifold Mesh Generation
**Critical**: Meshes MUST be manifold for slicers:
- **Shared vertices**: Adjacent pixels share corner vertices (no duplicates)
- **Edge connectivity**: Every edge shared by exactly 2 triangles
- **CCW winding**: All triangles use counter-clockwise winding for outward normals
- **No degenerate triangles**: All triangles have non-zero area

### 4. Y-Axis Coordinate Flipping
Images have Y=0 at top (origin: top-left). We flip during loading so Y=0 is at bottom (origin: bottom-left), matching 3D coordinate systems. This ensures models appear right-side-up in slicers.

### 5. Flood-Fill with 8-Connectivity
`region_merger.py` uses **iterative BFS** with **8-connectivity** (includes diagonals) to avoid creating too many separate objects. Without diagonal connectivity, a diagonal line would be N separate regions instead of 1.

### 6. Exact Scaling (No Rounding)
Pixel size calculation is exact: `pixel_size_mm = max_size_mm / max_dimension_px`. The largest dimension equals max_size exactly. **No rounding** - this was removed for predictable scaling.

### 7. Line Width Validation
The converter warns if pixel size < line width (unreliable printing). Uses `LINE_WIDTH_MM` constant (default 0.42mm).

### 8. 3MF Format
`threemf_writer.py` generates a ZIP containing XML files. The 3MF is NOT a single XML file - it's a structured archive:
```
.3mf (ZIP archive)
├── 3D/3dmodel.model              # Main assembly
├── 3D/Objects/object_1.model     # Mesh geometry
├── Metadata/model_settings.config # Object names (color names!)
├── [Content_Types].xml
└── _rels/.rels
```

## Color Tools Integration

The `color_tools/` subpackage is an **external library** (embedded but not part of this project):

- **DO NOT MODIFY** - Treat as read-only third-party dependency
- **Import pattern**: `from .color_tools import Palette, rgb_to_lab`
- **Usage**: `Palette.from_css()` loads 147 CSS colors, `find_nearest()` uses Delta E 2000
- **Color space**: RGB → LAB → Delta E 2000 for perceptual distance

## Running & Testing

**Run converter**:
```powershell
python run_converter.py image.png --max-size 200 --color-height 1.0 --max-colors 16
```

**Programmatic usage** (for tests/scripts):
```python
from pixel_to_3mf import convert_image_to_3mf

stats = convert_image_to_3mf(
    input_path="test.png",
    output_path="test.3mf",
    max_size_mm=150,
    max_colors=16,
    progress_callback=lambda stage, msg: print(f"{stage}: {msg}")
)
print(f"Generated {stats['num_regions']} regions from {stats['num_colors']} colors")
print(f"Model: {stats['model_width_mm']:.1f}x{stats['model_height_mm']:.1f}mm")
print(f"Pixel size: {stats['pixel_size_mm']:.3f}mm")
```

**Run tests**:
```powershell
python tests/run_tests.py
```

**Test structure** (`tests/` directory):
- **`test_helpers.py`**: Utilities for creating test images programmatically
- **`test_image_processor.py`**: Image loading, Y-flip, scaling, color validation
- **`test_region_merger.py`**: Flood-fill, 8-connectivity, bounds calculation
- **`test_mesh_generator.py`**: Manifold mesh generation, vertex sharing, winding
- **`test_threemf_writer.py`**: 3MF ZIP structure, XML generation, formatting
- **`test_pixel_to_3mf.py`**: Integration tests for complete pipeline
- **`run_tests.py`**: Test runner using Python's built-in unittest framework

**Sample images**: `samples/input/` contains test pixel art (nes-samus.png, ms-pac-man.png, c64ready.png). Corresponding 3MF outputs in `samples/output/`.

## Common Tasks

### Adding a New Parameter
1. Add constant to `constants.py`
2. Add parameter to `convert_image_to_3mf()` in `pixel_to_3mf.py` (business logic)
3. Add argparse argument in `cli.py` (CLI layer)
4. Add test cases in appropriate test file
5. Update README examples

### Modifying Mesh Generation
- Edit `mesh_generator.py` - see `generate_region_mesh()` and `generate_backing_plate()`
- Meshes use vertex list + triangle index list (standard 3D format)
- Triangle winding: counter-clockwise = outward normal
- **Add tests** in `test_mesh_generator.py` to verify manifold properties

### Changing Region Merging Logic
- Edit `region_merger.py` flood-fill algorithm
- Current: 8-connectivity (includes diagonals) - changing this affects output significantly
- **Add tests** in `test_region_merger.py` for new connectivity patterns

### Changing 3MF Output Format
- Edit `threemf_writer.py` XML generation functions
- Use `prettify_xml()` for debugging (makes XML human-readable)
- Test with Bambu Studio or PrusaSlicer to validate
- **Add tests** in `test_threemf_writer.py` for structure validation

### Writing Tests
Tests use Python's built-in `unittest` framework. Pattern:
```python
import unittest
from tests.test_helpers import create_simple_square_image, cleanup_test_file

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        self.test_files = []
    
    def tearDown(self):
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_something(self):
        # Create test image programmatically
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(img_path)
        # Test your feature...
```

## Critical Conventions

1. **No business logic in CLI**: Keep `cli.py` purely presentational
2. **Type hints everywhere**: Function signatures must have types
3. **Docstrings matter**: Explain WHY, not just WHAT (see existing style)
4. **Coordinate precision**: Use `COORDINATE_PRECISION` from constants (3 decimal places = 0.001mm)
5. **Progress callbacks**: Optional parameter for library users, used by CLI for pretty output

## Dependencies

- **Pillow**: Image loading (PIL.Image)
- **NumPy**: Fast pixel array operations
- Built-in: zipfile, xml.etree.ElementTree, argparse

Install: `pip install -r requirements.txt`
