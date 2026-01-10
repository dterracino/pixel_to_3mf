<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Batch compatibility checker**: Fixed bug where filenames containing dots (e.g., `3.5-floppy-ornament_model`) would not be recognized when passed without the `.3mf` extension. Now correctly uses `endswith('.3mf')` check instead of relying on Path.suffix property.
- **Quantization bug**: Fixed quantization target using `config.max_colors` instead of `effective_max_colors`, causing 15 colors when 16 were expected (when backing color is in the image)
- **Backing plate message**: Fixed "Skipping backing plate (base height is 0)" message appearing even when backing plate was generated (duplicate code block removed)
- **Blue/purple color matching**: Implemented RGB-based boundary detection to prevent pure blues (#0000FF) from matching to purple filaments. This resolves an issue specific to the Bambu Lab filament palette which has a gap between Purple (#5E43B7) and Blue (#0A2989) with no intermediate colors

### Added

- **Color preview generation**: New `--preview` flag generates a preview image showing what the model will look like with mapped filament colors
  - Saved as `{output_name}_preview.png` alongside the 3MF file
  - Shows exact RGB values of matched filaments applied to source image
  - Useful for verifying color accuracy before printing
  - Listed in conversion summary output
  - Separate progress stage in CLI output

- **RGB boundary detection for blue/purple matching**: Smart color matching to prevent categorical mismatches in filament palettes with gaps (specifically resolves Bambu Lab palette issue)
  - Uses red component analysis on BOTH target and candidate colors: R < 50 = blue, R > 80 = purple, 50-80 = boundary zone
  - No string matching on filament names - works for ANY naming scheme ("Ocean", "Sky", "Lavender", etc.)
  - Safe for all filament brands - only penalizes clear categorical mismatches
  - Configurable via `USE_RGB_BOUNDARY_DETECTION` constant (default: enabled)
  - Prevents pure blues (#0000FF) from matching to purple when Bambu Lab palette has no perfect blue match
  - Allows bluish-purples (#686CE8) to correctly match purple filaments
  - More accurate color matching - may produce slightly different (better) results than previous name-based approach
  - Documented in `docs/RGB_BOUNDARY_DETECTION.md`
  - Marked with TODO comments for future migration to color-tools library

- **Padding type selection**: New `--padding-type` flag allows choosing padding shape
  - `circular` (default): Euclidean distance - smooth, rounded corners
  - `square`: Chebyshev distance - sharp 90° corners, perfect for framing
  - `diamond`: Manhattan distance - 45° diagonal cuts
  - Configurable via `PADDING_TYPE_DEFAULT` constant

- **Bambu Lab printer integration** for querying printer status and AMS information
  - New `bambu_ams_info.py` module to query printer via local HTTP API
  - Retrieves AMS info: slot status, filament types, colors, humidity
  - Retrieves printer status: job state, temperatures, errors
  - `--test-connection` flag for debugging and raw JSON output
  - Configuration system with priority order:
    1. Command-line arguments (highest priority)
    2. Environment variables
    3. `.env` file (project-level config)
    4. BambuStudio.conf file (application config)
  - `--use-conf` flag to load credentials from BambuStudio's configuration
  - Auto-detects BambuStudio.conf location based on OS (Windows/macOS/Linux)
  - Added `python-dotenv` dependency for .env file support
  - Comprehensive configuration guide in `docs/BAMBU_CONFIG_GUIDE.md`

- **Batch compatibility checker** for multi-model printing
  - New `--check-batch` command to analyze compatibility of multiple 3MF files
  - New `--check-batch-folder` command to check all .3mf files in a directory
    - Scans folder for all .3MF files automatically
    - No need to type individual filenames
    - Defaults to current directory if no folder specified
    - Example: `python run_converter.py --check-batch-folder samples/output/`
  - Flexible path handling: supports full paths, relative paths, or simple filenames (auto-adds .3mf)
  - Color aggregation across all models with usage tracking
  - Intelligent batch optimization algorithm:
    - **Maximizes number of models** that can print in first batch
    - Most common white → Slot A-1 (automatic priority)
    - Most common black/charcoal → Slot A-2 (automatic priority)
    - Greedy optimization: iteratively selects models that enable most additional printable models
    - Minimizes color swaps needed for subsequent batches
    - Frequency-based slot filling for remaining colors
  - Three-tier visual highlighting in results:
    - Bold green: Colors in ALL models (never need swapping)
    - Dim: Colors only in remaining models (could defer loading)
    - Normal: Colors needed for first batch
  - First batch recommendations: shows which models can print immediately
  - Remaining batch analysis: lists models needing color swaps with specific colors required
  - Hash verification: detects if 3MF files modified since conversion
  - Requires `.info.json` files generated during conversion (automatic with `--summary`)
  - Examples:
    - `python run_converter.py --check-batch model1.3mf model2.3mf model3.3mf`
    - `python run_converter.py --check-batch-folder samples/output/`

- **JSON formatting utilities** for consistent output styling
  - New `json_utils.py` module with reusable JSON formatting functions
  - `dumps_compact_arrays()` function keeps arrays on single lines while maintaining indentation
  - Used in model info files to format RGB arrays compactly: `[255, 0, 0]` instead of multi-line
  - Configurable to compact specific fields or all numeric arrays

- **Mesh validation and post-processing infrastructure** (experimental)
  - New `mesh_postprocessor.py` module for detecting and repairing mesh issues
  - Added `--validate-mesh` flag to manually enable validation on any conversion
  - Automatic validation when using `--optimize-mesh` flag
  - Three-pass system: scan for issues, apply fixes, validate results
  - Rich console output showing detected issues and applied fixes per mesh
  - Detects: unreferenced vertices, degenerate faces, non-manifold edges, boundary edges
  - Applies: vertex merging, degenerate face removal, duplicate face removal, winding fixes, hole filling, normal correction
  - Uses `trimesh` library for mesh analysis and repair operations
  - Added dependencies: `scipy`, `networkx` (required by trimesh)
  - **Note**: Currently detects many non-manifold edges that may be false positives due to analyzing separate mesh objects independently. These edges occur at boundaries between region layers and backing plate, which is expected for multi-object 3MF files. Further investigation needed to determine if aggressive repair is required or if current mesh quality is acceptable for slicing/printing.

### Changed

- **Major refactoring**: Separated generic 3MF writer logic into reusable core module
  - Created new `threemf_core.py` module (991 lines) with generic 3MF file generation
  - Refactored `threemf_writer.py` from 954 → 379 lines (now pixel art application layer only)
  - Introduced `ThreeMFWriter` class with callback-based architecture for extensibility
  - Moved utility functions to core: `count_mesh_stats`, `validate_triangle_winding`, `format_float`, `prettify_xml`
  - Added new utilities: `calculate_model_bounds`, `calculate_model_center`, `create_centering_transform`
  - Created `ThreeMFMesh` and `ThreeMFObject` dataclasses for generic mesh representation
  - Callback system allows customization of: object naming, material slots, transforms, thumbnails
  - Backward compatible: existing `write_3mf()` function maintains same API
  - Test helpers: Added adapter functions for converting between internal `Mesh` and `ThreeMFMesh` types

### Added

- AMS (Automatic Material System) integration with automatic slot assignments
  - Each color assigned to specific AMS slot (1-16) in 3MF metadata
  - Backing plate color always assigned to slot 1
  - Other colors sorted alphabetically and assigned slots 2-N
- `--ams-count` parameter to specify number of AMS units (1-4, default 4)
  - Total slots calculated as `ams_count × ams_slots_per_unit`
  - Validation warning when `max_colors` exceeds available AMS slots
- AMS location information in summary files
  - Shows global slot number (1-16)
  - Shows AMS unit (A-D) and slot within unit (1-4)
  - Format: `Location: 5 (AMS B, Slot 1)`
- AMS Slot Assignments table displayed in CLI after conversion
  - Shows extruder number, AMS location, color/filament name, and hex code
  - Always visible (not dependent on `--summary` flag)
  - Uses actual config values for accurate AMS unit display
- Configuration table displays AMS units and total slots available
- Automatic thumbnail generation for 3MF files (5 types embedded in `/Metadata/`)
  - `top_1.png`: 512x512 overhead view (scaled source image)
  - `pick_1.png`: 512x512 gray silhouette (50% gray where pixels exist)
  - `plate_1.png`: 512x512 isometric view (-30° rotation)
  - `plate_1_small.png`: 128x128 downscaled isometric view
  - `plate_no_light_1.png`: 512x512 isometric view (identical to plate_1.png)
- Aspect ratio preservation in thumbnails with transparent padding
- Title metadata in 3MF files (auto-formatted from filename)
- PNG and gcode content type declarations in `[Content_Types].xml`
- Thumbnail references in 3MF metadata (Thumbnail_Middle, Thumbnail_Small)
- Mesh statistics displayed in conversion summary (triangle and vertex counts)
- Triangle winding order validation (confirms CCW winding for proper normals)
- Helper functions for 3MF structure validation in tests
- Comprehensive mesh statistics test suite
- Comprehensive test coverage for AMS location conversion function

### Fixed

- Color count in conversion summary now matches AMS table and summary file
  - Previously counted unique RGB values (15 for ken-sf2.png example)
  - Now counts unique color/filament names after mapping (14 for same example)
  - Multiple RGB values that map to same color name are counted once
  - Provides accurate count of filaments needed for printing
- AMS Slot Assignments now groups by color name instead of RGB values, eliminating duplicate entries when multiple pixel colors map to the same filament/CSS color name
- Hex values in AMS Slot Assignments now show the matched filament/color RGB instead of detected pixel RGB for clarity
- Trim disconnected pixels feature (`--trim`) now correctly identifies disconnected pixels without removing pixels inside connected areas
- Isometric thumbnail rotation now uses NEAREST resampling to avoid anti-aliasing artifacts on pixel art edges
- User prompts now display correctly with Rich console (changed from `[y/N]` to `(y/N)` to avoid markup conflict)
- Manifold mesh generation for diagonal-only pixel connections in 8-connectivity mode
  - Pixels touching only at corners now use unique vertices to prevent non-manifold edges
  - Prevents 4 triangles meeting at single edge (maintains manifold property: 2 triangles per edge)
  - Regions remain merged for color assignment, but meshes are geometrically separate
  - Ensures reliable 3D printing without mesh topology errors
- Path separators in render output now use forward slashes on all platforms for cross-platform consistency
- Test suite now uses system-appropriate temp directories instead of hardcoded `/tmp/` paths for cross-platform compatibility (Windows, Linux, macOS)

### Removed

- Removed `trimesh` library dependency (no longer needed for core conversion)
- Removed `mesh_validation.py` module (validation code that required trimesh)
  - Validation/repair functionality will be reimplemented without external dependencies in future release
  - Does not affect main conversion pipeline (validation was only used in tests/analysis scripts)

## [1.0.0] - 2025-11-09

### Added

- Batch processing mode with `--batch` flag for converting multiple images
- Recursive folder processing with `--recurse` flag (preserves folder structure)
- Polygon-based mesh optimization with `--optimize-mesh` flag (50-90% file size reduction)
- Optional backing plate (set `--base-height 0` to disable)
- Batch summary generation (Markdown report of conversion results)
- Color naming modes: `--color-mode` (color/filament/hex)
- Filament color matching with maker/type/finish filters
- Progress reporting with Rich library (spinners, progress bars)
- Summary file generation with `--summary` flag
- Auto-crop feature for transparent borders
- Configurable connectivity modes (0/4/8) for region merging
- Smart padding with `--padding` flag (circular distance tracing)
- Trim disconnected pixels with `--trim` flag
- Color quantization with `--quantize` flag (reduces color count)
- Version information with `--version` flag
- Semantic versioning support

### Changed

- Improved CLI with better help text and examples
- Enhanced error messages to stderr for proper stream handling
- Mesh generation now uses manifold-preserving algorithms
- Backing plate generation optimized for rectangular images
- Y-axis flipping for correct 3D orientation

### Fixed

- Type errors in Shapely geometry handling
- Rich Console API usage (proper stderr handling)
- Manifold mesh generation for all region types
- Backing plate now properly optional
- Exact scaling without rounding for predictable dimensions

## [0.1.0] - 2025-01-01

### Added

- Basic pixel art to 3MF conversion
- Color layer height configuration
- Backing plate generation
- 8-connectivity flood-fill region merging
- Color naming using CSS color names
- Delta E 2000 color matching
- Support for PNG, JPG, BMP, GIF formats
- Command-line interface
- Unit test suite

[Unreleased]: https://github.com/dterracino/pixel_to_3mf/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dterracino/pixel_to_3mf/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/dterracino/pixel_to_3mf/releases/tag/v0.1.0
