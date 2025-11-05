# Pixel Art to 3MF Converter - AI Agent Instructions

## Project Overview

This tool converts pixel art images into 3D-printable 3MF files. It performs region merging (flood-fill), color naming via perceptual Delta E 2000 matching, and generates proper 3MF ZIP archives with XML mesh data.

**Entry points**: `run_converter.py` (CLI wrapper) → `pixel_to_3mf.cli.main()`

## Architecture: Clean Separation of Concerns

The codebase strictly separates **CLI layer** from **business logic**:

- **`cli.py`**: All argparse, print statements, error display, progress callbacks
- **`pixel_to_3mf.py`**: Pure conversion logic - NO print/argparse, fully programmatic
- This separation is CRITICAL - never add print statements to business logic modules

**Pipeline flow**:
```
Image Load → Scale Calculation → Region Merging (flood-fill) → Mesh Generation → 3MF Export
```

### Module Responsibilities

- **`constants.py`**: ALL magic numbers live here (defaults, precision, etc.)
- **`image_processor.py`**: PIL loading, scaling math, returns `PixelData` container
- **`region_merger.py`**: Flood-fill algorithm, edge-only connectivity (no diagonals)
- **`mesh_generator.py`**: Extrudes 2D regions to 3D, generates backing plate
- **`threemf_writer.py`**: Creates ZIP with XML files (3MF spec compliance)

## Key Design Patterns

### 1. Constants Centralization
All defaults in `constants.py`. Change defaults there, NOT in function signatures:
```python
# CORRECT: Use constant as default
def my_func(height: float = COLOR_LAYER_HEIGHT_MM):
```

### 2. PixelData Container
`image_processor.py` returns a `PixelData` object bundling all image info. Pass this around instead of separate width/height/pixels variables.

### 3. Flood-Fill Implementation
`region_merger.py` uses **iterative BFS** (not recursion) to avoid stack overflow on large regions. Only considers edge-adjacent pixels (4-connectivity).

### 4. 3MF Format
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
python run_converter.py image.png --max-size 200 --color-height 1.0
```

**Programmatic usage** (for tests/scripts):
```python
from pixel_to_3mf import convert_image_to_3mf

stats = convert_image_to_3mf(
    input_path="test.png",
    output_path="test.3mf",
    max_size_mm=150,
    progress_callback=lambda stage, msg: print(f"{stage}: {msg}")
)
print(f"Generated {stats['num_regions']} regions")
```

**No test framework present** - use manual testing with sample images.

## Common Tasks

### Adding a New Parameter
1. Add constant to `constants.py`
2. Add parameter to `convert_image_to_3mf()` in `pixel_to_3mf.py` (business logic)
3. Add argparse argument in `cli.py` (CLI layer)
4. Update README examples

### Modifying Mesh Generation
- Edit `mesh_generator.py` - see `generate_region_mesh()` and `generate_backing_plate()`
- Meshes use vertex list + triangle index list (standard 3D format)
- Triangle winding: counter-clockwise = outward normal

### Changing 3MF Output Format
- Edit `threemf_writer.py` XML generation functions
- Use `prettify_xml()` for debugging (makes XML human-readable)
- Test with Bambu Studio or PrusaSlicer to validate

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
