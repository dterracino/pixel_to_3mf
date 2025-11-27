"""
Tests for the operation order in the image processing pipeline.

This test module verifies that when multiple processing options are enabled,
operations execute in the correct order:
1. Auto-crop (remove transparent edges)
2. Padding (add outline)
3. Pixel extraction (with Y-flip)
4. Quantization (reduce colors, including padding color)
"""

import unittest
import tempfile
import os
from PIL import Image
import numpy as np
from pathlib import Path

from pixel_to_3mf.image_processor import load_image
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import cleanup_test_file


class TestOperationOrder(unittest.TestCase):
    """Test that image processing operations execute in the correct order."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def _create_test_image_with_padding(self) -> str:
        """
        Create a test image with transparent padding around a colored center.
        
        Returns 20x20 image:
        - 5px transparent border on all sides
        - 10x10 red center
        """
        img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
        pixels = img.load()
        assert pixels is not None  # Type narrowing for Pyright
        
        # Fill center 10x10 with red
        for y in range(5, 15):
            for x in range(5, 15):
                pixels[x, y] = (255, 0, 0, 255)
        
        # Save to temp file
        fd, test_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        img.save(test_path)
        self.test_files.append(test_path)
        return test_path
    
    def test_autocrop_happens_before_padding(self):
        """
        Test that auto-crop removes transparent edges BEFORE padding is applied.
        
        Expected behavior:
        1. Start with 20x20 image (10x10 red center, 5px transparent border)
        2. Auto-crop removes the 5px border → 10x10
        3. Padding adds 2px white outline → 14x14
        
        If auto-crop happened AFTER padding, we'd get:
        1. Add 2px padding to 20x20 → 24x24
        2. Crop to content → back to ~14x14 (wasted work)
        """
        img_path = self._create_test_image_with_padding()
        
        config = ConversionConfig(
            auto_crop=True,
            padding_size=2,
            padding_color=(255, 255, 255)
        )
        
        pixel_data = load_image(img_path, config)
        
        # After auto-crop (20x20 → 10x10) and padding (+2px on each side)
        # Expected: 14x14
        self.assertEqual(pixel_data.width, 14, 
                        "Width should be 14 (10 content + 2*2 padding)")
        self.assertEqual(pixel_data.height, 14,
                        "Height should be 14 (10 content + 2*2 padding)")
        
        # Verify we have both red pixels (content) and white pixels (padding)
        colors = pixel_data.get_unique_colors()
        self.assertIn((255, 0, 0), colors, "Should have red content pixels")
        self.assertIn((255, 255, 255), colors, "Should have white padding pixels")
    
    def test_quantize_happens_after_padding(self):
        """
        Test that quantization includes the padding color in the palette.
        
        If quantization happened before padding, the padding color might not
        be in the reduced palette.
        """
        # Create image with multiple colors
        img = Image.new('RGBA', (10, 10))
        pixels = img.load()
        assert pixels is not None  # Type narrowing for Pyright
        
        # Create a gradient of 20 different colors
        for i in range(10):
            for j in range(10):
                # Each pixel gets a slightly different red value
                r = 100 + (i * 10) + j
                pixels[j, i] = (r, 0, 0, 255)
        
        fd, test_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        img.save(test_path)
        self.test_files.append(test_path)
        
        # Enable quantization and padding
        config = ConversionConfig(
            padding_size=2,
            padding_color=(0, 255, 0),  # Green padding
            quantize=True,
            quantize_colors=8  # Reduce to 8 colors
        )
        
        pixel_data = load_image(test_path, config)
        
        # Verify padding was applied (10x10 + 2*2 = 14x14)
        self.assertEqual(pixel_data.width, 14)
        self.assertEqual(pixel_data.height, 14)
        
        # Verify we have at most 8 unique colors (quantization worked)
        colors = pixel_data.get_unique_colors()
        self.assertLessEqual(len(colors), 8, 
                            "Should have at most 8 colors after quantization")
        
        # Critical check: padding color should be in the palette
        # (or a very close match after quantization)
        # Green is (0, 255, 0), should be preserved or very close
        has_green_padding = any(
            g > 200 and r < 50 and b < 50 
            for r, g, b in colors
        )
        self.assertTrue(has_green_padding,
                       "Padding color should be in the quantized palette")
    
    def test_autocrop_without_padding_still_works(self):
        """Test that auto-crop works correctly without padding enabled."""
        img_path = self._create_test_image_with_padding()
        
        config = ConversionConfig(
            auto_crop=True,
            padding_size=0  # No padding
        )
        
        pixel_data = load_image(img_path, config)
        
        # Should be 10x10 (just the red center after cropping)
        self.assertEqual(pixel_data.width, 10)
        self.assertEqual(pixel_data.height, 10)
        
        # Should only have red pixels
        colors = pixel_data.get_unique_colors()
        self.assertEqual(len(colors), 1)
        self.assertIn((255, 0, 0), colors)
    
    def test_padding_without_autocrop_still_works(self):
        """Test that padding works correctly without auto-crop enabled."""
        img_path = self._create_test_image_with_padding()
        
        config = ConversionConfig(
            auto_crop=False,
            padding_size=2,
            padding_color=(255, 255, 255)
        )
        
        pixel_data = load_image(img_path, config)
        
        # Should be 24x24 (20x20 original + 2*2 padding)
        self.assertEqual(pixel_data.width, 24)
        self.assertEqual(pixel_data.height, 24)
    
    def test_all_operations_together(self):
        """
        Test all operations together: auto-crop + padding + quantization.
        
        This is the most complex case and tests the full pipeline.
        """
        # Create image with MANY distinct colors and transparent padding
        img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
        pixels = img.load()
        assert pixels is not None  # Type narrowing for Pyright
        
        # Fill center with many distinct colors (100 different colors)
        # This ensures we definitely exceed the quantization target
        color_idx = 0
        for y in range(5, 15):
            for x in range(5, 15):
                r = color_idx % 256
                g = (color_idx // 10) % 256
                pixels[x, y] = (r, g, 0, 255)
                color_idx += 1
        
        fd, test_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        img.save(test_path)
        self.test_files.append(test_path)
        
        # Count original colors before processing
        # Note: pixels[x, y] returns RGBA tuple for RGBA images
        pixel_colors = set()
        for y in range(5, 15):
            for x in range(5, 15):
                pixel = pixels[x, y]
                assert isinstance(pixel, tuple) and len(pixel) >= 3
                pixel_colors.add(pixel[:3])
        original_colors = len(pixel_colors)
        
        config = ConversionConfig(
            auto_crop=True,        # Remove transparent border
            padding_size=2,        # Add 2px outline
            padding_color=(0, 255, 0),  # Green
            quantize=True,         # Reduce colors
            quantize_colors=8      # To 8 colors (more realistic target)
        )
        
        pixel_data = load_image(test_path, config)
        
        # Verify dimensions: 10x10 content + 2*2 padding = 14x14
        self.assertEqual(pixel_data.width, 14)
        self.assertEqual(pixel_data.height, 14)
        
        # Verify color count is reduced from original
        colors = pixel_data.get_unique_colors()
        self.assertLess(len(colors), original_colors,
                       f"Color count should be reduced from {original_colors}")
        
        # Should be reasonably close to target (allow some tolerance for quantization)
        # PIL may not hit exact target, but should be in reasonable range
        self.assertLessEqual(len(colors), 15,
                            "Should have significantly fewer colors after quantization")
        
        # Verify green padding is present (or close after quantization)
        has_green = any(g > 200 and r < 50 and b < 50 for r, g, b in colors)
        self.assertTrue(has_green, "Green padding should be in the palette")


if __name__ == '__main__':
    unittest.main()
