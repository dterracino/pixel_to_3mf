"""
Tests for padding_processor module.

Tests the smart padding functionality that adds outlines around non-transparent
pixels in pixel art images.
"""

import unittest
from typing import Tuple
from PIL import Image
import numpy as np
from pathlib import Path

from pixel_to_3mf.padding_processor import add_padding, should_apply_padding
from tests.helpers import cleanup_test_file


def _get_rgba_pixel(img: Image.Image, x: int, y: int) -> Tuple[int, int, int, int]:
    """
    Get RGBA pixel values from image.
    
    Helper to work around Pyright's inability to infer getpixel() return type.
    """
    pixel = img.getpixel((x, y))
    assert isinstance(pixel, tuple) and len(pixel) == 4
    r, g, b, a = pixel
    return (int(r), int(g), int(b), int(a))


class TestShouldApplyPadding(unittest.TestCase):
    """Test the should_apply_padding helper function."""
    
    def test_enabled_with_positive_size(self):
        """Test that positive size enables padding."""
        self.assertTrue(should_apply_padding(1))
        self.assertTrue(should_apply_padding(5))
        self.assertTrue(should_apply_padding(100))
    
    def test_disabled_with_zero(self):
        """Test that zero size disables padding."""
        self.assertFalse(should_apply_padding(0))
    
    def test_disabled_with_negative(self):
        """Test that negative size disables padding."""
        self.assertFalse(should_apply_padding(-1))
        self.assertFalse(should_apply_padding(-5))


class TestAddPadding(unittest.TestCase):
    """Test the add_padding function."""
    
    def test_invalid_padding_size(self):
        """Test that invalid padding_size raises ValueError."""
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        with self.assertRaises(ValueError):
            add_padding(img, 0, (255, 255, 255))
        
        with self.assertRaises(ValueError):
            add_padding(img, -1, (255, 255, 255))
    
    def test_invalid_padding_color(self):
        """Test that invalid padding_color raises ValueError."""
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        # Not a tuple
        with self.assertRaises(ValueError):
            add_padding(img, 5, [255, 255, 255])  # type: ignore[arg-type]
        
        # Wrong length
        with self.assertRaises(ValueError):
            add_padding(img, 5, (255, 255))  # type: ignore[arg-type]
        
        # Out of range
        with self.assertRaises(ValueError):
            add_padding(img, 5, (256, 0, 0))
        
        with self.assertRaises(ValueError):
            add_padding(img, 5, (-1, 0, 0))
    
    def test_converts_to_rgba(self):
        """Test that non-RGBA images are converted."""
        # Create RGB image
        img = Image.new('RGB', (10, 10), (255, 0, 0))
        
        # Should not raise error - should convert internally
        result = add_padding(img, 2, (255, 255, 255))
        
        # Result should be RGBA
        self.assertEqual(result.mode, 'RGBA')
    
    def test_empty_image_returns_original(self):
        """Test that completely transparent image returns original."""
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        result = add_padding(img, 5, (255, 255, 255))
        
        # Should return original since there's nothing to pad
        self.assertEqual(result.size, img.size)
        # Type assertion for ImagingCore - convert to list explicitly
        result_data: list = list(result.getdata())  # type: ignore[arg-type]
        img_data: list = list(img.getdata())  # type: ignore[arg-type]
        self.assertEqual(result_data, img_data)
    
    def test_expands_canvas(self):
        """Test that canvas is expanded by padding_size on all sides."""
        # Create 10x10 image
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        # Add one pixel in the center
        img.putpixel((5, 5), (255, 0, 0, 255))
        
        # Add 3px padding
        result = add_padding(img, 3, (255, 255, 255))
        
        # Canvas should be expanded by 3*2 = 6 in each dimension
        self.assertEqual(result.size, (16, 16))
    
    def test_single_pixel_gets_padded(self):
        """Test that a single pixel gets padding around it."""
        # Create image with single pixel
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        img.putpixel((5, 5), (255, 0, 0, 255))
        
        # Add 2px padding
        result = add_padding(img, 2, (255, 255, 255))
        
        # Canvas should be 14x14
        self.assertEqual(result.size, (14, 14))
        
        # Original pixel should be at (5+2, 5+2) = (7, 7)
        r, g, b, a = _get_rgba_pixel(result, 7, 7)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        # Padding pixels should exist around it
        # Check a few positions that should have white padding
        # At distance 1 from center (should have padding)
        r, g, b, a = _get_rgba_pixel(result, 6, 7)  # Left
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        r, g, b, a = _get_rgba_pixel(result, 8, 7)  # Right
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
    
    def test_padding_traces_edges(self):
        """Test that padding only appears at edges, not in filled areas."""
        # Create a 3x3 solid square
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        for y in range(4, 7):
            for x in range(4, 7):
                img.putpixel((x, y), (255, 0, 0, 255))
        
        # Add 1px padding
        result = add_padding(img, 1, (255, 255, 255))
        
        # Canvas should be 12x12 (10 + 2*1)
        self.assertEqual(result.size, (12, 12))
        
        # Center of square should still be red (not padded over)
        # Original (5, 5) -> shifted to (6, 6)
        r, g, b, a = _get_rgba_pixel(result, 6, 6)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        # Just outside the square should be white padding
        # Original (3, 5) was transparent, should now have padding
        # -> shifted to (4, 6)
        r, g, b, a = _get_rgba_pixel(result, 4, 6)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
    
    def test_padding_with_internal_hole(self):
        """Test that padding traces internal holes as well."""
        # Create a 5x5 square with a hole in the middle
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        # Outer square
        for y in range(3, 8):
            for x in range(3, 8):
                img.putpixel((x, y), (255, 0, 0, 255))
        
        # Create hole in center
        img.putpixel((5, 5), (0, 0, 0, 0))
        
        # Add 1px padding
        result = add_padding(img, 1, (255, 255, 255))
        
        # The hole should have padding around its edges
        # Original hole at (5, 5) -> shifted to (6, 6)
        r, g, b, a = _get_rgba_pixel(result, 6, 6)
        # The hole itself should have padding
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
    
    def test_diagonal_pixels_get_connected(self):
        """Test that diagonally-connected pixels get padding that connects them."""
        # Create two pixels connected diagonally
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        img.putpixel((5, 5), (255, 0, 0, 255))
        img.putpixel((6, 6), (255, 0, 0, 255))
        
        # Add 1px padding
        result = add_padding(img, 1, (255, 255, 255))
        
        # The gap between diagonals should now have padding filling it
        # Original (5, 5) -> (6, 6) in padded
        # Original (6, 6) -> (7, 7) in padded
        
        # Check that padding exists between them
        # The pixel at (6, 7) should be either red or white (filled)
        r, g, b, a = _get_rgba_pixel(result, 6, 7)
        self.assertGreater(a, 0)  # Should not be transparent
    
    def test_padding_color_is_correct(self):
        """Test that padding uses the specified color."""
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        img.putpixel((5, 5), (255, 0, 0, 255))
        
        # Use blue padding
        result = add_padding(img, 2, (0, 0, 255))
        
        # Check that padding pixels are blue
        r, g, b, a = _get_rgba_pixel(result, 6, 7)  # Should be padding
        self.assertEqual((r, g, b), (0, 0, 255))
        self.assertEqual(a, 255)
    
    def test_preserves_original_pixels(self):
        """Test that original non-transparent pixels are preserved."""
        # Create image with multiple colored pixels
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        img.putpixel((3, 3), (255, 0, 0, 255))  # Red
        img.putpixel((3, 4), (0, 255, 0, 255))  # Green
        img.putpixel((4, 3), (0, 0, 255, 255))  # Blue
        
        result = add_padding(img, 2, (255, 255, 255))
        
        # Original pixels should be preserved (shifted by padding_size)
        r, g, b, a = _get_rgba_pixel(result, 3 + 2, 3 + 2)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        r, g, b, a = _get_rgba_pixel(result, 3 + 2, 4 + 2)
        self.assertEqual((r, g, b, a), (0, 255, 0, 255))
        
        r, g, b, a = _get_rgba_pixel(result, 4 + 2, 3 + 2)
        self.assertEqual((r, g, b, a), (0, 0, 255, 255))
    
    def test_transparent_outer_edges_with_padding(self):
        """Test that padding follows the shape of non-transparent pixels when outer edges are transparent."""
        # Create image with transparent outer edges and a sprite in the center
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        # Create a small cross-shaped sprite in the center
        # Vertical bar
        for y in range(3, 7):
            img.putpixel((5, y), (255, 0, 0, 255))
        # Horizontal bar
        for x in range(3, 7):
            img.putpixel((x, 5), (255, 0, 0, 255))
        
        # Add 2px padding
        result = add_padding(img, 2, (255, 255, 255))
        
        # Canvas should be expanded: 10 + 2*2 = 14x14
        self.assertEqual(result.size, (14, 14))
        
        # Original cross center at (5, 5) -> shifted to (7, 7)
        r, g, b, a = _get_rgba_pixel(result, 7, 7)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        # Padding should surround the cross shape
        # Check padding around the top of vertical bar
        # Original (5, 2) was transparent, should have padding around (5, 3)
        # Shifted position of (5, 3) -> (7, 5)
        # Position (7, 4) should have padding (1px above the top of vertical bar)
        r, g, b, a = _get_rgba_pixel(result, 7, 4)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        # Check corners don't have padding (cross shape, not filled square)
        # Original (3, 3) was transparent and far from sprite
        # Shifted to (5, 5) - should remain transparent or have less padding
        # Let's check a corner that's definitely outside padding range
        # Original (1, 1) -> (3, 3) should be transparent
        r, g, b, a = _get_rgba_pixel(result, 3, 3)
        self.assertEqual(a, 0)  # Should be transparent
    
    def test_internal_hole_gets_filled_by_padding(self):
        """Test that padding fills in internal holes up to the padding size."""
        # Create a donut shape - outer ring with hole in center
        img = Image.new('RGBA', (12, 12), (0, 0, 0, 0))
        
        # Create outer ring (3x3 grid with hole in middle)
        for y in range(4, 8):
            for x in range(4, 8):
                img.putpixel((x, y), (255, 0, 0, 255))
        
        # Create a 2x2 hole in the center
        for y in range(5, 7):
            for x in range(5, 7):
                img.putpixel((x, y), (0, 0, 0, 0))
        
        # Add 1px padding - should fill part of the hole
        result = add_padding(img, 1, (255, 255, 255))
        
        # Canvas expanded: 12 + 2*1 = 14x14
        self.assertEqual(result.size, (14, 14))
        
        # Check that the hole has padding filling it
        # Original hole pixel at (5, 5) -> shifted to (6, 6)
        r, g, b, a = _get_rgba_pixel(result, 6, 6)
        # This should have white padding (filling the hole)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        # Another hole pixel at (6, 6) -> shifted to (7, 7)
        r, g, b, a = _get_rgba_pixel(result, 7, 7)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        # The red ring should still be preserved
        # Original (4, 4) -> shifted to (5, 5)
        r, g, b, a = _get_rgba_pixel(result, 5, 5)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
    
    def test_padding_follows_complex_shape(self):
        """Test that padding accurately follows a complex shape with both outer edges and internal holes."""
        # Create an L-shape with transparent areas
        img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        
        # Vertical part of L
        for y in range(2, 8):
            img.putpixel((3, y), (255, 0, 0, 255))
        
        # Horizontal part of L
        for x in range(3, 7):
            img.putpixel((x, 7), (255, 0, 0, 255))
        
        # Add 1px padding
        result = add_padding(img, 1, (255, 255, 255))
        
        # Canvas: 10 + 2*1 = 12x12
        self.assertEqual(result.size, (12, 12))
        
        # Original L-shape should be preserved (shifted by 1)
        # Check vertical part: (3, 3) -> (4, 4)
        r, g, b, a = _get_rgba_pixel(result, 4, 4)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        # Check horizontal part: (5, 7) -> (6, 8)
        r, g, b, a = _get_rgba_pixel(result, 6, 8)
        self.assertEqual((r, g, b, a), (255, 0, 0, 255))
        
        # Check padding on outer edge of vertical part
        # Left side of (3, 3) -> (4, 4): position (3, 4) should have padding
        r, g, b, a = _get_rgba_pixel(result, 3, 4)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        # Check padding on outer edge of horizontal part
        # Below (5, 7) -> (6, 8): position (6, 9) should have padding
        r, g, b, a = _get_rgba_pixel(result, 6, 9)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)
        
        # Check internal corner (inside the L) has padding
        # Position (4, 6) was transparent and next to L
        # Shifted to (5, 7) should have padding
        r, g, b, a = _get_rgba_pixel(result, 5, 7)
        self.assertEqual((r, g, b), (255, 255, 255))
        self.assertEqual(a, 255)


if __name__ == '__main__':
    unittest.main()
