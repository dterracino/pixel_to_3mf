#!/usr/bin/env python3
"""
Tests for color quantization functionality.

This module tests the automatic color reduction feature that allows users
to convert images with too many colors without preprocessing.
"""

import unittest
import sys
from pathlib import Path
from PIL import Image
import tempfile
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.image_processor import quantize_image, load_image
from pixel_to_3mf.config import ConversionConfig
from tests.test_helpers import cleanup_test_file


class TestQuantizeImage(unittest.TestCase):
    """Test the quantize_image function."""
    
    def test_quantize_reduces_colors(self):
        """Test that quantization actually reduces color count."""
        # Create image with 100 different colors
        width, height = 10, 10
        img = Image.new('RGBA', (width, height))
        pixels = []
        for i in range(100):
            r = (i * 7) % 256
            g = (i * 13) % 256
            b = (i * 19) % 256
            pixels.append((r, g, b, 255))
        img.putdata(pixels)
        
        # Verify it has 100 unique colors
        unique_before = len(set(img.getdata()))  # type: ignore[arg-type]
        self.assertEqual(unique_before, 100)
        
        # Quantize to 10 colors
        quantized = quantize_image(img, 10, "none")
        
        # Check it now has <= 10 unique colors
        unique_after = len(set(quantized.getdata()))  # type: ignore[arg-type]
        self.assertLessEqual(unique_after, 10)
    
    def test_quantize_preserves_alpha(self):
        """Test that quantization preserves the alpha channel exactly."""
        # Create image with various alpha values
        width, height = 4, 4
        img = Image.new('RGBA', (width, height))
        pixels = [
            (255, 0, 0, 255),    # Opaque red
            (0, 255, 0, 128),    # Semi-transparent green
            (0, 0, 255, 0),      # Fully transparent blue
            (128, 128, 128, 64), # Quarter-transparent gray
        ] * 4
        img.putdata(pixels)
        
        # Quantize
        quantized = quantize_image(img, 2, "none")
        
        # Extract alpha values
        img_data = img.getdata()
        quantized_data = quantized.getdata()
        original_alphas = [p[3] for p in img_data]  # type: ignore[index]
        quantized_alphas = [p[3] for p in quantized_data]  # type: ignore[index]
        
        # Alpha channel should be exactly the same
        self.assertEqual(original_alphas, quantized_alphas)
    
    def test_quantize_none_vs_floyd(self):
        """Test that 'none' and 'floyd' algorithms work (may produce similar results for small images)."""
        # Create gradient image
        width, height = 20, 20
        img = Image.new('RGBA', (width, height))
        pixels = []
        for y in range(height):
            for x in range(width):
                gray = int((x / width) * 255)
                pixels.append((gray, gray, gray, 255))
        img.putdata(pixels)
        
        # Quantize with both algorithms - both should work
        quantized_none = quantize_image(img, 4, "none")
        quantized_floyd = quantize_image(img, 4, "floyd")
        
        # Both should be RGBA
        self.assertEqual(quantized_none.mode, 'RGBA')
        self.assertEqual(quantized_floyd.mode, 'RGBA')
        
        # Both should have reduced colors
        unique_none = len(set(quantized_none.getdata()))  # type: ignore[arg-type]
        unique_floyd = len(set(quantized_floyd.getdata()))  # type: ignore[arg-type]
        self.assertLessEqual(unique_none, 10)  # Should be much less than original
        self.assertLessEqual(unique_floyd, 10)  # Should be much less than original
    
    def test_quantize_invalid_num_colors(self):
        """Test that invalid num_colors raises ValueError."""
        img = Image.new('RGBA', (10, 10), (255, 0, 0, 255))
        
        with self.assertRaises(ValueError):
            quantize_image(img, 0, "none")  # Zero colors
        
        with self.assertRaises(ValueError):
            quantize_image(img, -5, "none")  # Negative colors
    
    def test_quantize_invalid_algorithm(self):
        """Test that invalid algorithm raises ValueError."""
        img = Image.new('RGBA', (10, 10), (255, 0, 0, 255))
        
        with self.assertRaises(ValueError):
            quantize_image(img, 8, "invalid_algo")
    
    def test_quantize_converts_to_rgba(self):
        """Test that quantization works on non-RGBA images."""
        # Create RGB image (no alpha)
        img = Image.new('RGB', (10, 10), (255, 0, 0))
        
        # Should work and return RGBA
        quantized = quantize_image(img, 4, "none")
        self.assertEqual(quantized.mode, 'RGBA')


class TestLoadImageWithQuantization(unittest.TestCase):
    """Test load_image with quantization enabled."""
    
    def setUp(self):
        """Set up test files."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def _create_multicolor_image(self, num_colors: int) -> str:
        """Helper to create a test image with many colors."""
        # Create temporary image file
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        self.test_files.append(path)
        
        # Create image with specified number of colors
        width = height = 10
        img = Image.new('RGBA', (width, height))
        pixels = []
        for i in range(width * height):
            color_idx = i % num_colors
            r = (color_idx * 7) % 256
            g = (color_idx * 13) % 256
            b = (color_idx * 19) % 256
            pixels.append((r, g, b, 255))
        img.putdata(pixels)
        img.save(path)
        
        return path
    
    def test_load_with_quantization_enabled(self):
        """Test that quantization is applied when enabled and colors exceed max."""
        # Create image with 50 colors
        image_path = self._create_multicolor_image(50)
        
        # Config with quantization enabled, max_colors=16 (effective 15 with backing)
        config = ConversionConfig(
            max_colors=16,
            quantize=True,
            quantize_colors=15,  # Leave room for backing color
            quantize_algo="none"
        )
        
        # Should succeed (quantization reduces colors)
        pixel_data = load_image(image_path, config)
        
        # Check that we have <= 15 colors (to leave room for backing)
        unique_colors = pixel_data.get_unique_colors()
        self.assertLessEqual(len(unique_colors), 15)
    
    def test_load_without_quantization_fails(self):
        """Test that too many colors fails when quantization is disabled."""
        # Create image with 50 colors
        image_path = self._create_multicolor_image(50)
        
        # Config with quantization disabled, max_colors=10
        config = ConversionConfig(
            max_colors=10,
            quantize=False
        )
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            load_image(image_path, config)
        
        self.assertIn("unique colors", str(cm.exception))
        self.assertIn("enable --quantize", str(cm.exception))
    
    def test_load_with_quantization_uses_default_colors(self):
        """Test that quantization defaults to max_colors when quantize_colors is None."""
        # Create image with 50 colors
        image_path = self._create_multicolor_image(50)
        
        # Config with quantization enabled, quantize_colors=None
        config = ConversionConfig(
            max_colors=16,
            quantize=True,
            quantize_colors=None,  # Should default to max_colors
            quantize_algo="none"
        )
        
        # Should succeed
        pixel_data = load_image(image_path, config)
        
        # Check that we have <= 15 colors (accounting for backing reservation)
        unique_colors = pixel_data.get_unique_colors()
        self.assertLessEqual(len(unique_colors), 15)
    
    def test_load_skips_quantization_if_not_needed(self):
        """Test that quantization is skipped if image already has few enough colors."""
        # Create image with only 5 colors
        image_path = self._create_multicolor_image(5)
        
        # Config with quantization enabled, max_colors=10
        config = ConversionConfig(
            max_colors=10,
            quantize=True,
            quantize_colors=3,  # Target fewer colors than we have
            quantize_algo="none"
        )
        
        # Should succeed without quantizing (since 5 < 10)
        pixel_data = load_image(image_path, config)
        
        # Should still have ~5 colors (not quantized to 3)
        unique_colors = pixel_data.get_unique_colors()
        self.assertEqual(len(unique_colors), 5)
    
    def test_load_quantization_respects_backing_color_reservation(self):
        """Test that quantization accounts for backing color slot reservation."""
        # Create image with 20 colors (not including white)
        image_path = self._create_multicolor_image(20)
        
        # Config with white backing color (not in image), max_colors=16
        # This means effective_max = 15 (one reserved for backing)
        config = ConversionConfig(
            max_colors=16,
            backing_color=(255, 255, 255),  # White - not in image
            quantize=True,
            quantize_colors=15,  # Explicitly set to account for reservation
            quantize_algo="none"
        )
        
        # Should succeed (quantize to fit in 15 slots)
        pixel_data = load_image(image_path, config)
        
        # Check that we have <= 15 colors (leaving room for backing)
        unique_colors = pixel_data.get_unique_colors()
        self.assertLessEqual(len(unique_colors), 15)
    
    def test_load_quantization_floyd_algorithm(self):
        """Test that Floyd-Steinberg dithering works."""
        # Create image with 50 colors
        image_path = self._create_multicolor_image(50)
        
        # Config with Floyd-Steinberg dithering
        config = ConversionConfig(
            max_colors=10,
            quantize=True,
            quantize_colors=9,  # Leave room for backing color
            quantize_algo="floyd"
        )
        
        # Should succeed
        pixel_data = load_image(image_path, config)
        
        # Check that we have <= 9 colors (leaving room for backing)
        unique_colors = pixel_data.get_unique_colors()
        self.assertLessEqual(len(unique_colors), 9)


class TestConfigQuantizationValidation(unittest.TestCase):
    """Test ConversionConfig validation for quantization parameters."""
    
    def test_config_invalid_quantize_algo(self):
        """Test that invalid quantize_algo raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            ConversionConfig(quantize_algo="invalid")
        
        self.assertIn("quantize_algo", str(cm.exception))
        self.assertIn("none", str(cm.exception))
        self.assertIn("floyd", str(cm.exception))
    
    def test_config_invalid_quantize_colors(self):
        """Test that invalid quantize_colors raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            ConversionConfig(quantize_colors=0)
        
        self.assertIn("quantize_colors", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            ConversionConfig(quantize_colors=-5)
        
        self.assertIn("quantize_colors", str(cm.exception))
    
    def test_config_valid_quantization_params(self):
        """Test that valid quantization params are accepted."""
        # Should not raise
        config = ConversionConfig(
            quantize=True,
            quantize_algo="floyd",
            quantize_colors=12
        )
        
        self.assertTrue(config.quantize)
        self.assertEqual(config.quantize_algo, "floyd")
        self.assertEqual(config.quantize_colors, 12)
    
    def test_config_quantize_colors_none_is_valid(self):
        """Test that quantize_colors=None is valid (uses max_colors)."""
        # Should not raise
        config = ConversionConfig(
            quantize=True,
            quantize_colors=None
        )
        
        self.assertIsNone(config.quantize_colors)


if __name__ == '__main__':
    unittest.main()
