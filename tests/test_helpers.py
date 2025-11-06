"""
Test helper utilities for creating test fixtures and sample data.

This module provides utilities for creating test images and data structures
used across multiple test files.
"""

from PIL import Image
from typing import Tuple, Dict
import tempfile
import os


def create_test_image(
    width: int,
    height: int,
    colors: Dict[Tuple[int, int, int, int], list],
    filepath: str = None
) -> str:
    """
    Create a test image with specified colors at specified positions.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        colors: Dictionary mapping RGBA tuples to lists of (x, y) coordinates
        filepath: Optional path to save image (defaults to temp file)
    
    Returns:
        Path to the created image file
    """
    # Create blank transparent image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    pixels = img.load()
    
    # Fill in specified colors
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


def cleanup_test_file(filepath: str):
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
