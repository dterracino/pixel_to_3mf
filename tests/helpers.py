"""
Test helper utilities for creating test fixtures and sample data.

This module provides utilities for creating test images and data structures
used across multiple test files.
"""

from PIL import Image
from typing import Tuple, Dict, Optional
import tempfile
import os
import numpy as np


def create_test_image(
    width: int,
    height: int,
    colors: Dict[Tuple[int, int, int, int], list],
    filepath: Optional[str] = None
) -> str:
    """
    Create a test image with specified colors at specified positions.
    
    Uses numpy for efficiency when dealing with large images.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        colors: Dictionary mapping RGBA tuples to lists of (x, y) coordinates
        filepath: Optional path to save image (defaults to temp file)
    
    Returns:
        Path to the created image file
    """
    # Check if this is a simple solid-color image (optimization)
    total_pixels = width * height
    if len(colors) == 1:
        color, positions = next(iter(colors.items()))
        if len(positions) == total_pixels:
            # Solid color image - use numpy for speed
            arr = np.full((height, width, 4), color, dtype=np.uint8)
            img = Image.fromarray(arr, mode='RGBA')
        else:
            # Sparse image - use standard approach
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            pixels = img.load()
            if pixels is None:
                raise RuntimeError("Failed to load image pixels")
            for x, y in positions:
                if 0 <= x < width and 0 <= y < height:
                    pixels[x, y] = color
    else:
        # Multiple colors - use standard approach
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        pixels = img.load()
        if pixels is None:
            raise RuntimeError("Failed to load image pixels")
        for color, positions in colors.items():
            for x, y in positions:
                if 0 <= x < width and 0 <= y < height:
                    pixels[x, y] = color
    
    # Save to file
    if filepath is None:
        fd, filepath = tempfile.mkstemp(suffix='.png')
        os.close(fd)
    
    img.save(filepath)
    return filepath


def create_simple_square_image(size: int = 4, color: Tuple[int, int, int] = (255, 0, 0)) -> str:
    """
    Create a simple square test image filled with one color.
    
    Args:
        size: Width and height in pixels
        color: RGB color tuple
    
    Returns:
        Path to the created image file
    """
    positions = [(x, y) for x in range(size) for y in range(size)]
    colors = {color + (255,): positions}
    return create_test_image(size, size, colors)


def create_two_region_image() -> str:
    """
    Create an image with two separate colored regions.
    
    Returns a 4x4 image with:
    - Top-left 2x2: Red
    - Bottom-right 2x2: Blue
    
    Returns:
        Path to the created image file
    """
    red_positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    blue_positions = [(2, 2), (3, 2), (2, 3), (3, 3)]
    
    colors = {
        (255, 0, 0, 255): red_positions,
        (0, 0, 255, 255): blue_positions
    }
    
    return create_test_image(4, 4, colors)


def create_transparent_image() -> str:
    """
    Create an image with transparent areas.
    
    Returns a 4x4 image with a 2x2 red square in the center.
    
    Returns:
        Path to the created image file
    """
    red_positions = [(1, 1), (2, 1), (1, 2), (2, 2)]
    colors = {(255, 0, 0, 255): red_positions}
    return create_test_image(4, 4, colors)


def create_diagonal_pattern_image() -> str:
    """
    Create an image with a diagonal pattern to test flood fill.
    
    Returns a 4x4 image with red pixels in a diagonal line.
    
    Returns:
        Path to the created image file
    """
    red_positions = [(0, 0), (1, 1), (2, 2), (3, 3)]
    colors = {(255, 0, 0, 255): red_positions}
    return create_test_image(4, 4, colors)


def cleanup_test_file(filepath: str) -> None:
    """
    Remove a test file if it exists.
    
    Args:
        filepath: Path to file to remove
    """
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass


def get_sample_image() -> str:
    """
    Get path to a sample test image.
    
    Returns a deterministic test image path from the samples/test directory.
    The image is expected to exist in the repository for testing purposes.
    
    Returns:
        Absolute path to the sample test image
    
    Raises:
        FileNotFoundError: If the sample image doesn't exist
    """
    from pathlib import Path
    
    # Path from tests/ to samples/test/sample_image.png
    test_samples_dir = Path(__file__).parent.parent / "samples" / "test"
    sample_image = test_samples_dir / "sample-image.png"
    
    if not sample_image.exists():
        raise FileNotFoundError(
            f"Sample test image not found: {sample_image}\n"
            f"Please ensure samples/test/sample-image.png exists in the repository."
        )
    
    return str(sample_image)


def validate_3mf_structure(filepath: str) -> None:
    """
    Validate that a 3MF file has the correct structure.
    
    Checks that the file is a valid ZIP and contains the required 3MF components:
    - Valid ZIP file structure
    - Required files: [Content_Types].xml, _rels/.rels
    - Required 3D model files: 3D/3dmodel.model
    - Object library: 3D/Objects/object_1.model
    - Model settings: Metadata/model_settings.config
    - Valid XML structure in key files
    
    This is much more thorough than just checking zipfile.is_zipfile()!
    
    Args:
        filepath: Path to the 3MF file to validate
    
    Raises:
        AssertionError: If validation fails (designed for use in tests)
        FileNotFoundError: If the file doesn't exist
    """
    import zipfile
    import xml.etree.ElementTree as ET
    
    # Basic existence check
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"3MF file not found: {filepath}")
    
    # Must be a valid ZIP file
    assert zipfile.is_zipfile(filepath), f"File is not a valid ZIP: {filepath}"
    
    with zipfile.ZipFile(filepath, 'r') as zf:
        # Get list of files in the archive
        file_list = zf.namelist()
        
        # Required files for 3MF format
        required_files = [
            '[Content_Types].xml',
            '_rels/.rels',
            '3D/3dmodel.model',
            '3D/_rels/3dmodel.model.rels',
            '3D/Objects/object_1.model',
            'Metadata/model_settings.config'
        ]
        
        for required_file in required_files:
            assert required_file in file_list, \
                f"Missing required 3MF file: {required_file}"
        
        # Validate that key XML files are parseable
        xml_files_to_check = [
            '[Content_Types].xml',
            '_rels/.rels',
            '3D/3dmodel.model',
            '3D/_rels/3dmodel.model.rels',
            '3D/Objects/object_1.model'
        ]
        
        for xml_file in xml_files_to_check:
            try:
                xml_content = zf.read(xml_file)
                ET.fromstring(xml_content)
            except ET.ParseError as e:
                raise AssertionError(
                    f"Invalid XML in {xml_file}: {e}"
                )
        
        # Validate 3dmodel.model has at least one build item
        model_content = zf.read('3D/3dmodel.model')
        model_root = ET.fromstring(model_content)
        
        # Find build element (may have namespace)
        build = model_root.find('.//{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}build')
        if build is None:
            build = model_root.find('.//build')
        
        assert build is not None, "3dmodel.model missing <build> element"
        
        # Check for at least one item in the build
        items = build.findall('.//{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}item')
        if not items:
            items = build.findall('.//item')
        
        assert len(items) > 0, "3dmodel.model has no build items"


def calculate_expected_triangle_count(num_pixels: int, has_backing: bool = True) -> int:
    """
    Calculate expected triangle count for a pixel art model.
    
    Each pixel square becomes 2 triangles (top surface) in the original
    mesh generator. The backing plate also has 2 triangles per pixel.
    
    This is useful for validating mesh generation in tests.
    
    Args:
        num_pixels: Number of non-transparent pixels in the image
        has_backing: Whether the model has a backing plate
    
    Returns:
        Expected number of triangles
    """
    # Each pixel region: 2 triangles for top + 4 sides * 2 triangles each = 10 triangles per pixel
    # Backing plate: 2 triangles per pixel
    triangles_per_pixel = 10
    if has_backing:
        triangles_per_pixel += 2
    
    return num_pixels * triangles_per_pixel


def calculate_expected_vertex_count(num_pixels: int, has_backing: bool = True) -> int:
    """
    Calculate expected vertex count for a pixel art model.
    
    With vertex sharing (manifold mesh), adjacent pixels share edge vertices.
    This is a rough estimate based on the mesh generation strategy.
    
    Args:
        num_pixels: Number of non-transparent pixels in the image
        has_backing: Whether the model has a backing plate
    
    Returns:
        Estimated number of vertices
    """
    # This is an estimate - actual count depends on pixel arrangement
    # Each pixel has 8 vertices (4 top, 4 bottom), but shared edges reduce this
    # For a rough estimate: ~6 vertices per pixel with sharing
    vertices_per_pixel = 6
    if has_backing:
        vertices_per_pixel += 2  # Backing adds bottom vertices
    
    return num_pixels * vertices_per_pixel


