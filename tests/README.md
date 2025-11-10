# Tests for pixel_to_3mf

This directory contains comprehensive unit tests for the pixel_to_3mf package.

## Running Tests

To run all tests:

```bash
cd /home/runner/work/pixel_to_3mf/pixel_to_3mf
python tests/run_tests.py
```

Or run individual test modules:

```bash
python -m unittest tests.test_image_processor
python -m unittest tests.test_region_merger
python -m unittest tests.test_mesh_generator
python -m unittest tests.test_threemf_writer
python -m unittest tests.test_pixel_to_3mf
```

## Test Structure

- **`helpers.py`**: Helper utilities for creating test images, validation, and fixtures
- **`test_image_processor.py`**: Tests for image loading, scaling, and PixelData class
- **`test_region_merger.py`**: Tests for flood fill algorithm and region merging
- **`test_mesh_generator.py`**: Tests for mesh generation (regions and backing plate)
- **`test_mesh_stats.py`**: Tests for mesh statistics and winding order validation
- **`test_threemf_writer.py`**: Tests for 3MF file writing and formatting
- **`test_pixel_to_3mf.py`**: Integration tests for the complete conversion pipeline
- **`run_tests.py`**: Test runner that executes all test suites

## Test Coverage

The test suite covers:

### Image Processing (`test_image_processor.py`)

- PixelData container class functionality
- Pixel size calculation for different image aspect ratios
- Image loading with transparency support
- Y-axis coordinate flipping
- Color limit enforcement
- Pixel bounds calculation in millimeters

### Region Merging (`test_region_merger.py`)

- Region class functionality
- Flood fill algorithm (single pixel, squares, complex shapes)
- Diagonal connectivity (8-connectivity)
- Multiple separate regions
- Transparent areas
- Region bounds calculation

### Mesh Generation (`test_mesh_generator.py`)

- Mesh class functionality
- Region mesh generation (single pixel, squares, L-shapes)
- Layer height configuration
- Vertex positioning
- Backing plate generation
- Backing plate with holes (transparent areas)
- Mesh validity (no degenerate triangles)

### Mesh Statistics (`test_mesh_stats.py`)

- Triangle and vertex counting across meshes
- Mesh complexity validation (larger images = more triangles)
- Backing plate impact on triangle count
- Triangle winding order validation (CCW vs CW)
- Mesh statistics utility functions
- Winding order consistency checks

### 3MF Writing (`test_threemf_writer.py`)

- Float formatting for coordinates
- Simple 3MF file creation
- ZIP archive validation with comprehensive structure checks
- Required 3MF file structure (all required XML files present)
- Multiple meshes in one file
- Backing plate inclusion
- Large meshes
- XML validity and parseability

### Integration (`test_pixel_to_3mf.py`)

- Complete conversion pipeline
- Single color images
- Multiple regions
- Transparent images
- Custom dimensions and heights
- Landscape and portrait images
- Progress callbacks
- Error handling (invalid parameters, missing files, too many colors)
- Real sample image conversion

## Test Philosophy

Tests follow the project's architecture principles:

1. **Separation of concerns**: Tests focus on business logic, not CLI
2. **No color_tools tests**: color_tools is an external library
3. **Programmatic testing**: Tests use the conversion functions directly
4. **Clean fixtures**: Test images are created programmatically and cleaned up
5. **Comprehensive coverage**: All main functionality is tested

## Dependencies

Tests use Python's built-in `unittest` framework - no additional test dependencies required.

The main package dependencies (Pillow, NumPy) are required to run tests.
