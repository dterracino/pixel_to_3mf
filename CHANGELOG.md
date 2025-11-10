<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Mesh statistics displayed in conversion summary (triangle and vertex counts)
- Triangle winding order validation (confirms CCW winding for proper normals)
- Helper functions for 3MF structure validation in tests
- Comprehensive mesh statistics test suite

### Fixed

- Trim disconnected pixels feature (`--trim`) now correctly identifies disconnected pixels without removing pixels inside connected areas

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
