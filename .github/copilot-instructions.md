# Pixel Art to 3MF Converter - AI Agent Instructions

## General Best Practices

These principles apply to ALL code changes in this project:

### Communication and Context

- **Avoid making assumptions.** If you need additional context to accurately answer the user, ask the user for the missing information. Be specific about which context you need.
- **Never abbreviate or abridge code.** Always provide the full code as it appears in the source files. Never use placeholders like `// previous code here` or `... existing code ...`.
- **Specify exact locations.** When providing fixes or updates, specify the exact file path and location where changes should be made.
- **Don't jump ahead.** Don't make code changes if the user has not yet requested them; instead, offer suggestions or ask clarifying questions first.

### Code Organization and Maintainability

- **Break up code intelligently.** Always organize code into modules and components so it can be easily reused. Don't overload a function with hundreds of lines when it should be broken into logical pieces. This facilitates unit testing and maintainability.
- **Separation of concerns.** CLI/presentation layer must be strictly separated from business logic (see detailed section below).
- **DRY principle.** Extract duplicate code to shared functions. No duplicate validation, formatting, or error messages.
- **Proper error handling.** Use exceptions in business logic, display errors in CLI layer. Include appropriate error context and recovery guidance.

### Documentation and Testing

- **Keep documentation updated.** When making significant changes, update:
  - `README.md` - User-facing documentation, examples, features
  - `CHANGELOG.md` - Version history with Added/Changed/Fixed sections
  - Docstrings - Explain WHY code exists, not just WHAT it does
- **Maintain test coverage.** Add unit tests for new features. Update tests when changing functionality. All tests must pass before committing.
- **Document reasoning.** Include comments explaining design decisions, trade-offs, and non-obvious implementation choices.

### Logging and User Communication

- **NO print statements in business logic.** Only CLI layer (`cli.py`) should use print statements or Rich console output.
- **Use proper communication channels:**
  - Business logic → Use progress callbacks, raise exceptions, return data
  - CLI layer → Display to user via print/Rich, handle exceptions, format output
  - Internal debugging → Use logging module with appropriate levels
- **Logging best practices:**
  - Use `logger.debug()` for detailed internal steps
  - Use `logger.info()` for major milestones
  - Use `logger.warning()` for recoverable issues
  - Use `logger.error()` for failures
  - Configure logging in CLI layer only (see `--log-file` implementation)

## Custom AI Agents

This project has specialized custom agents for specific tasks located in `.github/agents/`. **Always consider using the appropriate custom agent** when working in their domain. Custom agents have deep expertise in their area and understand project conventions.

### Available Custom Agents

- **3d-printing-specialist**: Expert in FDM printing, Bambu Lab printers, filament behavior, G-code, 3MF format, and HueForge-style layered printing
- **bug-specialist**: Fixes bugs, detects code smells, creates bug reports, ensures type hints
- **cleanup-specialist**: Removes dead code, eliminates duplication, improves maintainability
- **color-science-specialist**: Color space expert for RGB/Lab/HSL conversions, Delta E metrics, gamut mapping, and color accuracy
- **custom-agent-generator**: Creates new custom agent definition files
- **docstring-specialist**: Creates/updates docstrings that explain WHY over WHAT
- **implementation-planner**: Creates detailed implementation plans for new features
- **readme-specialist**: Maintains README and project documentation
- **refactoring-specialist**: Large-scale refactoring with deep architecture knowledge
- **test-specialist**: Expert in creating comprehensive unit tests and test coverage
- **type-specialist**: Adds type hints, fixes Pyright/Pylance errors (Python 3.10+)
- **ui-specialist**: CLI design, progress reporting, error messages, user communication

### When to Trigger Custom Agents

**Context-based triggering** - Use the appropriate agent when working on:

- **3D printing/geometry issues**: Use **3d-printing-specialist** for mesh topology, 3MF format, printer-specific optimizations
- **Color matching/conversion**: Use **color-science-specialist** for color space conversions, Delta E calculations, filament color matching
- **Editing Python code**: Consider **type-specialist** for type hints, **bug-specialist** for code smells
- **Fixing bugs**: Use **bug-specialist** for root cause analysis and fixes
- **Adding CLI arguments**: Use **ui-specialist** for argument design and user feedback
- **Writing docstrings**: Use **docstring-specialist** for WHY-focused documentation
- **Large refactoring**: Use **refactoring-specialist** for architectural changes
- **Creating new agents**: Use **custom-agent-generator** for agent definitions
- **Updating README**: Use **readme-specialist** for documentation
- **Cleaning up code**: Use **cleanup-specialist** for removing duplication
- **Planning features**: Use **implementation-planner** for breaking down complex work
- **Writing tests**: Use **test-specialist** for comprehensive test coverage

### Using Multiple Custom Agents

For complex tasks, use agents sequentially:

1. **implementation-planner** to break down the feature
2. **bug-specialist** to fix the issue
3. **type-specialist** to add type hints
4. **test-specialist** to create comprehensive tests
5. **docstring-specialist** to document the changes
6. **refactoring-specialist** to clean up and finalize

**Example:**
```
Use bug-specialist to fix the mesh topology issue, then use type-specialist to add proper type hints to the changes.
```

## Python Version and Standards

### Python Version

This project requires **Python 3.10+** and uses modern Python syntax:

**Modern Type Syntax (Python 3.10+):**
```python
# ✅ Modern syntax (use this)
def process(value: str | None) -> list[str]:
    pass

# ❌ Old syntax (don't use)
from typing import Optional, List
def process(value: Optional[str]) -> List[str]:
    pass
```

**Key Features to Use:**
- Union types with `|` instead of `Union[]` or `Optional[]`
- Built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, int]`
- Pattern matching (if beneficial)
- Parenthesized context managers
- Precise exception types in except clauses

### Type Hinting Standards

**Required on ALL functions:**
```python
def my_function(param1: str, param2: int | None = None) -> bool:
    """Docstring explaining WHY this function exists."""
    pass
```

**For complex types:**
```python
from typing import Callable, TypedDict, Literal

# Callbacks
ProgressCallback = Callable[[str, str], None]

# Structured dicts
class ConversionStats(TypedDict):
    num_regions: int
    num_colors: int
    model_width_mm: float

# Literal values
ColorMode = Literal["color", "filament", "hex"]
```

### Docstring Standards

**Explain WHY, not just WHAT:**

```python
# ❌ Bad - just states the obvious
def flip_image(img):
    """Flip image vertically."""
    return img.transpose(Image.FLIP_TOP_BOTTOM)

# ✅ Good - explains WHY
def flip_image(img: Image.Image) -> Image.Image:
    """
    Flip image vertically so Y=0 is at bottom instead of top.
    
    Images have origin at top-left (Y=0 at top), but 3D coordinate
    systems have origin at bottom-left (Y=0 at bottom). We flip during
    image loading so the 3D model appears right-side-up in slicers.
    
    Without this flip, models would be upside-down when imported.
    """
    return img.transpose(Image.FLIP_TOP_BOTTOM)
```

**Follow Google-style format:**
- Brief one-line summary
- Detailed explanation of WHY and HOW
- Args section with parameter descriptions
- Returns section
- Raises section if applicable
- Examples for complex functions

### Separation of Concerns and DRY Principles

**CRITICAL: Strict Separation of Concerns**

The architecture **strictly separates** CLI/presentation from business logic:

```
CLI Layer (cli.py):
✅ All print statements
✅ All argparse code
✅ All user interaction
✅ Progress callbacks
✅ Error display
✅ Output formatting

Business Logic (all other modules):
❌ NO print statements
❌ NO argparse
❌ NO user interaction
✅ Progress via callbacks
✅ Raise exceptions
✅ Return data
```

**This separation must NEVER be violated.**

**DRY Principles:**

1. **No duplicate code** - Extract to shared functions
2. **No magic numbers** - ALL constants in `constants.py`
3. **No duplicate validation** - Create validation functions
4. **No duplicate formatting** - Create formatting functions
5. **No duplicate error messages** - Use message templates

**Example of proper separation:**
```python
# ✅ Business logic (pixel_to_3mf.py)
def convert_image(
    path: str,
    callback: Callable[[str, str], None] | None = None
) -> dict:
    """Convert image to 3MF format."""
    if callback:
        callback("Loading", "Reading image file")
    # ... do work
    if callback:
        callback("Processing", "Merging regions")
    return stats

# ✅ CLI layer (cli.py)
def progress_callback(stage: str, message: str) -> None:
    """Display progress to user."""
    print(f"[{stage}] {message}")

result = convert_image(args.input, callback=progress_callback)
print(f"✅ Successfully converted {args.input}")
```

**Example of DRY violations to avoid:**
```python
# ❌ Bad - duplicate validation
if not user.email or '@' not in user.email:
    raise ValueError("Invalid email")
# ... later in same file
if not admin.email or '@' not in admin.email:
    raise ValueError("Invalid email")

# ✅ Good - extract to function
def validate_email(email: str) -> None:
    """Validate email format."""
    if not email or '@' not in email:
        raise ValueError("Invalid email")

validate_email(user.email)
validate_email(admin.email)
```

**Example of logging violations to avoid:**
```python
# ❌ Bad - logger.warning() prints to console by default
import logging
logger = logging.getLogger(__name__)

def process_data(data):
    """Process data in business logic."""
    logger.warning("This will appear in console!")  # BREAKS Rich output!
    # ... process data

# ✅ Good - use logging but configure it properly
# In cli.py:
import logging
if args.log_file:
    logging.basicConfig(filename=args.log_file, level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.CRITICAL + 1)  # Disable console output

# In business logic (polygon_optimizer.py):
import logging
logger = logging.getLogger(__name__)

def process_data(data):
    """Process data in business logic."""
    logger.warning("Only goes to log file, not console!")  # ✅ Correct
    # ... process data
```

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
Image Load → Auto-Crop (optional) → Padding (optional) → Y-Flip → Color Validation → 
Quantization (optional) → Exact Scaling → Region Merging (configurable connectivity) → 
Trim Disconnected Pixels (optional) → Manifold Mesh Generation (Original or Optimized) → 
Color Naming → 3MF Export → Summary Generation (optional)
```

### Module Responsibilities

- **`constants.py`**: ALL magic numbers live here (defaults, precision, line width, color limits, padding defaults)
- **`config.py`**: ConversionConfig dataclass that holds all conversion parameters - keeps function signatures clean and API maintainable
- **`image_processor.py`**: PIL loading, auto-crop, padding integration, Y-axis flipping, color validation, exact scaling (no rounding), quantization
- **`padding_processor.py`**: Smart padding implementation - traces outer edges and internal holes, uses circular distance (Euclidean) for smooth outlines, expands canvas
- **`region_merger.py`**: Flood-fill with **configurable connectivity** (0/4/8), bounds calculation, trim disconnected pixels feature
- **`mesh_generator.py`**: Generates **manifold** meshes (shared vertices, CCW winding, proper topology) - original per-pixel path
- **`polygon_optimizer.py`**: Polygon-based mesh optimization using shapely and triangle - merges pixel squares into polygons, constrained Delaunay triangulation, 20-77% reduction
- **`threemf_writer.py`**: Creates ZIP with XML files (3MF spec compliance)
- **`summary_writer.py`**: Generates .summary.txt files listing colors/filaments used in conversion
- **`find_filament_by_color.py`**: Filament color matching utilities with maker/type/finish filters

## Key Design Patterns

### 1. Constants Centralization
All defaults in `constants.py`. Change defaults there, NOT in function signatures:
```python
# CORRECT: Use constant as default
def my_func(height: float = COLOR_LAYER_HEIGHT_MM, max_colors: int = MAX_COLORS):
```

### 2. ConversionConfig Dataclass
`config.py` defines a ConversionConfig dataclass that holds all conversion parameters. This keeps function signatures clean and makes the API maintainable as new features are added. Pass config objects instead of individual parameters.

### 3. PixelData Container
`image_processor.py` returns a `PixelData` object bundling all image info. Pass this around instead of separate width/height/pixels variables.

### 4. Manifold Mesh Generation
**Critical**: Meshes MUST be manifold for slicers:
- **Shared vertices**: Adjacent pixels share corner vertices (no duplicates)
- **Edge connectivity**: Every edge shared by exactly 2 triangles
- **CCW winding**: All triangles use counter-clockwise winding for outward normals
- **No degenerate triangles**: All triangles have non-zero area

### 5. Y-Axis Coordinate Flipping
Images have Y=0 at top (origin: top-left). We flip during loading so Y=0 is at bottom (origin: bottom-left), matching 3D coordinate systems. This ensures models appear right-side-up in slicers.

### 6. Configurable Connectivity
`region_merger.py` uses **iterative BFS** with configurable connectivity:
- **0 (per-pixel)**: No merging - each pixel becomes separate object (debugging/special effects)
- **4 (edge-only)**: Pixels connected via edges only - simpler geometry, more regions
- **8 (diagonal, default)**: Includes diagonal connections - fewer objects, may create complex shapes

Without diagonal connectivity (8), a diagonal line would be N separate regions instead of 1.

### 7. Padding with Circular Distance
`padding_processor.py` adds outlines using circular (Euclidean) distance for smooth results. Traces both outer edges and internal holes. Canvas expands to accommodate padding - original pixels are never overwritten.

### 8. Polygon Optimization
`polygon_optimizer.py` provides an alternative mesh generation path:
- Merges pixel squares into larger polygons using shapely
- Triangulates using constrained Delaunay (triangle library)
- 20-77% reduction in vertices/triangles
- 100% reliable - never crashes, fills holes if needed
- Maintains all manifold properties
- Enabled with `--optimize-mesh` flag

**When to use**: Large images with many pixels per region (>20), solid color areas, when smaller file sizes are desired.

### 9. Exact Scaling (No Rounding)
Pixel size calculation is exact: `pixel_size_mm = max_size_mm / max_dimension_px`. The largest dimension equals max_size exactly. **No rounding** - this was removed for predictable scaling.

### 10. Line Width Validation
The converter warns if pixel size < line width (unreliable printing). Uses `LINE_WIDTH_MM` constant (default 0.42mm).

### 11. Summary File Generation
`summary_writer.py` can generate .summary.txt files listing all colors/filaments used. Enabled with `--summary` flag. Written to same location as 3MF with pattern: `{output_name}.summary.txt`.

### 12. 3MF Format
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

The `color-match-tools` package is a **published external dependency**:

- **Package name**: `color-match-tools` (PyPI)
- **Import name**: `color_tools` (Python module)
- **DO NOT MODIFY** - This is a published third-party package
- **Import pattern**: `from color_tools import Palette, FilamentPalette, rgb_to_lab`
- **Usage**: `Palette.from_css()` loads 147 CSS colors, `find_nearest()` uses Delta E 2000
- **Color space**: RGB → LAB → Delta E 2000 for perceptual distance
- **Installation**: Listed in `requirements.txt`

## Running & Testing

**Run converter**:
```powershell
python run_converter.py image.png --max-size 200 --color-height 1.0 --max-colors 16
```

**Programmatic usage** (for tests/scripts):
```python
from pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.config import ConversionConfig

# Option 1: Use defaults
stats = convert_image_to_3mf(
    input_path="test.png",
    output_path="test.3mf",
    progress_callback=lambda stage, msg: print(f"{stage}: {msg}")
)

# Option 2: Custom configuration with ConversionConfig
config = ConversionConfig(
    max_size_mm=150,
    color_height_mm=1.5,
    base_height_mm=2.0,
    max_colors=16,
    backing_color=(255, 255, 255),
    auto_crop=True,
    padding_size=5,
    padding_color=(255, 255, 255),
    connectivity=8,
    trim_disconnected=False,
    color_naming_mode="filament",
    filament_maker=["Bambu Lab", "Polymaker"],
    filament_type=["PLA", "PETG"],
    filament_finish=["Basic", "Matte"],
    optimize_mesh=True,
    generate_summary=True
)

stats = convert_image_to_3mf(
    input_path="test.png",
    output_path="test.3mf",
    config=config,
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
1. Add constant to `constants.py` (if it needs a default value)
2. Add field to `ConversionConfig` dataclass in `config.py`
3. Add parameter to `convert_image_to_3mf()` in `pixel_to_3mf.py` (business logic)
4. Add argparse argument in `cli.py` (CLI layer)
5. Add test cases in appropriate test file
6. Update README examples
7. Update .github/copilot-instructions.md

### Modifying Mesh Generation
- Edit `mesh_generator.py` - see `generate_region_mesh()` and `generate_backing_plate()` for original path
- Edit `polygon_optimizer.py` for polygon-based optimization path
- Meshes use vertex list + triangle index list (standard 3D format)
- Triangle winding: counter-clockwise = outward normal
- **Add tests** in `test_mesh_generator.py` to verify manifold properties

### Changing Region Merging Logic
- Edit `region_merger.py` flood-fill algorithm
- Current: Configurable connectivity (0/4/8) - changing this affects output significantly
- **Add tests** in `test_region_merger.py` for new connectivity patterns

### Adding Padding Features
- Edit `padding_processor.py` for padding algorithm changes
- Uses circular distance (Euclidean) for smooth outlines
- Traces both outer edges and internal holes
- **Remember**: Padding happens AFTER auto-crop but BEFORE quantization in pipeline

### Modifying Polygon Optimization
- Edit `polygon_optimizer.py` for optimization algorithm changes
- Uses shapely for polygon merging, triangle for Delaunay triangulation
- Must maintain 100% reliability - never crash, always produce valid manifold output
- **Add tests** to verify mesh quality and manifold properties

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

These conventions are **non-negotiable** and must be followed in all code:

1. **No business logic in CLI**: Keep `cli.py` purely presentational
   - NO print statements in business logic modules
   - Use progress callbacks for user feedback
   - Raise exceptions instead of printing errors

2. **Type hints everywhere** (Python 3.10+ syntax):
   - ALL function signatures must have type hints
   - Use modern syntax: `str | None`, `list[str]`, `dict[str, int]`
   - Don't use `Optional[]`, `Union[]`, `List[]`, `Dict[]` from typing module

3. **All magic numbers in constants.py**:
   - NO hardcoded numbers in business logic
   - Extract ALL defaults and configuration to `constants.py`
   - Use descriptive constant names

4. **Docstrings explain WHY, not WHAT**:
   - Don't just describe what code does (code already shows that)
   - Explain WHY it exists and WHY it works this way
   - Document design decisions and trade-offs
   - Follow Google-style docstring format

5. **DRY Principles**:
   - No duplicate code - extract to shared functions
   - No duplicate validation - create validation functions
   - No duplicate messages - use message templates

6. **Coordinate precision**: Use `COORDINATE_PRECISION` from constants (3 decimal places = 0.001mm)

7. **Progress callbacks**: Optional parameter for library users, used by CLI for pretty output

8. **Testing required**:
   - Add tests for new features
   - Use unittest framework
   - Follow existing test patterns
   - All tests must pass before committing

9. **Documentation maintenance**:
   - Update `README.md` when adding features or changing behavior
   - Update `CHANGELOG.md` with all user-visible changes
   - Use `[Unreleased]` section for upcoming changes
   - Follow semantic versioning principles

10. **Proper logging practices**:
    - Configure logging ONLY in CLI layer (`cli.py`)
    - Business logic uses `logging.getLogger(__name__)` for module-level loggers
    - When `--log-file` not specified, logging level set to `CRITICAL + 1` (disabled)
    - When `--log-file` specified, logging level set to `DEBUG`
    - Never use `warnings.warn()` - it breaks Rich console output

## Dependencies

- **Pillow**: Image loading (PIL.Image)
- **NumPy**: Fast pixel array operations
- **Rich**: Beautiful terminal output for CLI
- **Shapely**: Geometric operations for polygon optimization
- **Triangle**: Constrained Delaunay triangulation for mesh optimization
- Built-in: zipfile, xml.etree.ElementTree, argparse

Install: `pip install -r requirements.txt`
