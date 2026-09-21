"""
Unit tests for the image_processor module.

Tests image loading, scaling calculations, and PixelData functionality.
"""

import unittest
import os
import sys
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.image_processor import (
    PixelData,
    calculate_pixel_size,
    load_image,
    get_pixel_bounds_mm
)
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import (
    create_simple_square_image,
    create_test_image,
    create_two_region_image,
    create_transparent_image,
    cleanup_test_file
)


class TestPixelData(unittest.TestCase):
    """Test the PixelData container class."""
    
    def test_pixel_data_initialization(self):
        """Test PixelData can be created with valid parameters."""
        pixels = {(0, 0): (255, 0, 0, 255), (1, 0): (0, 255, 0, 255)}
        data = PixelData(width=10, height=20, pixel_size_mm=2.0, pixels=pixels)
        
        self.assertEqual(data.width, 10)
        self.assertEqual(data.height, 20)
        self.assertEqual(data.pixel_size_mm, 2.0)
        self.assertEqual(len(data.pixels), 2)
    
    def test_model_dimensions_calculated(self):
        """Test that model dimensions are calculated correctly."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        data = PixelData(width=10, height=20, pixel_size_mm=2.0, pixels=pixels)
        
        self.assertEqual(data.model_width_mm, 20.0)  # 10 * 2.0
        self.assertEqual(data.model_height_mm, 40.0)  # 20 * 2.0
    
    def test_get_unique_colors(self):
        """Test getting unique colors from pixel data."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (0, 255, 0, 255),
            (3, 0): (0, 0, 255, 255)
        }
        data = PixelData(width=4, height=1, pixel_size_mm=1.0, pixels=pixels)
        
        colors = data.get_unique_colors()
        self.assertEqual(len(colors), 3)
        self.assertIn((255, 0, 0), colors)
        self.assertIn((0, 255, 0), colors)
        self.assertIn((0, 0, 255), colors)
    
    def test_get_unique_colors_ignores_alpha(self):
        """Test that alpha channel is ignored in unique colors."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 128),  # Same RGB, different alpha
        }
        data = PixelData(width=2, height=1, pixel_size_mm=1.0, pixels=pixels)
        
        colors = data.get_unique_colors()
        self.assertEqual(len(colors), 1)
        self.assertIn((255, 0, 0), colors)
    
    def test_repr(self):
        """Test string representation of PixelData."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        data = PixelData(width=10, height=20, pixel_size_mm=2.0, pixels=pixels)
        
        repr_str = repr(data)
        self.assertIn("10x20px", repr_str)
        self.assertIn("20.0x40.0mm", repr_str)


class TestCalculatePixelSize(unittest.TestCase):
    """Test pixel size calculation for different image dimensions."""
    
    def test_square_image(self):
        """Test pixel size for square image."""
        config = ConversionConfig(max_size_mm=200.0)
        pixel_size = calculate_pixel_size(100, 100, config)
        self.assertEqual(pixel_size, 2.0)  # 200 / 100
    
    def test_landscape_image(self):
        """Test pixel size for landscape (wider than tall) image."""
        config = ConversionConfig(max_size_mm=200.0)
        pixel_size = calculate_pixel_size(200, 100, config)
        self.assertEqual(pixel_size, 1.0)  # 200 / 200 (width is larger)
    
    def test_portrait_image(self):
        """Test pixel size for portrait (taller than wide) image."""
        config = ConversionConfig(max_size_mm=200.0)
        pixel_size = calculate_pixel_size(100, 200, config)
        self.assertEqual(pixel_size, 1.0)  # 200 / 200 (height is larger)
    
    def test_non_round_dimension(self):
        """Test pixel size calculation with non-round dimensions."""
        config = ConversionConfig(max_size_mm=200.0)
        pixel_size = calculate_pixel_size(64, 32, config)
        self.assertAlmostEqual(pixel_size, 3.125, places=6)  # 200 / 64
    
    def test_different_max_size(self):
        """Test pixel size with different max_size_mm."""
        config = ConversionConfig(max_size_mm=150.0)
        pixel_size = calculate_pixel_size(100, 100, config)
        self.assertEqual(pixel_size, 1.5)  # 150 / 100

    def test_explicit_scale_overrides_max_size(self):
        """Test that explicit scale sets the physical size of every pixel."""
        config = ConversionConfig(max_size_mm=200.0, scale_mm_per_pixel=1.4)
        pixel_size = calculate_pixel_size(100, 50, config)
        self.assertEqual(pixel_size, 1.4)

    def test_explicit_scale_must_be_positive(self):
        """Test that zero and negative explicit scales are rejected."""
        for scale in (0.0, -1.0):
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError):
                    ConversionConfig(scale_mm_per_pixel=scale)


class TestLoadImage(unittest.TestCase):
    """Test image loading and processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_load_simple_image(self):
        """Test loading a simple solid color image."""
        filepath = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(filepath)

        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)

        self.assertEqual(pixel_data.width, 4)
        self.assertEqual(pixel_data.height, 4)
        self.assertEqual(len(pixel_data.pixels), 16)  # 4x4 filled

    def test_load_image_with_transparency(self):
        """Test loading image with transparent areas."""
        filepath = create_transparent_image()
        self.test_files.append(filepath)

        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)

        self.assertEqual(pixel_data.width, 4)
        self.assertEqual(pixel_data.height, 4)
        self.assertEqual(len(pixel_data.pixels), 4)  # Only 2x2 center is opaque

    def test_load_image_y_flip(self):
        """Test that Y coordinates are flipped correctly."""
        # Create image with pixel at top-left in image coordinates (0, 0)
        filepath = create_simple_square_image(size=2, color=(255, 0, 0))
        self.test_files.append(filepath)

        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)

        # In 3D coordinates, top-left should be at (0, height-1)
        self.assertIn((0, 1), pixel_data.pixels)
        self.assertIn((1, 1), pixel_data.pixels)
        self.assertIn((0, 0), pixel_data.pixels)
        self.assertIn((1, 0), pixel_data.pixels)

    def test_color_limit_enforcement(self):
        """Test that color limit is enforced."""
        filepath = create_two_region_image()
        self.test_files.append(filepath)

        # This should succeed (2 colors in image, limit 3 allows 2 colors + 1 backing)
        config = ConversionConfig(max_size_mm=200.0, max_colors=3)
        pixel_data = load_image(filepath, config)
        self.assertEqual(len(pixel_data.get_unique_colors()), 2)

        # This should fail (2 colors in image, but with backing color reservation,
        # max_colors=2 means only 1 effective slot for image colors)
        config_fail = ConversionConfig(max_size_mm=200.0, max_colors=2)
        with self.assertRaises(ValueError) as context:
            load_image(filepath, config_fail)
        self.assertIn("unique colors", str(context.exception))

    def test_auto_backing_color_uses_dominant_image_color(self):
        """Automatic backing shares the most frequently used image RGB."""
        filepath = create_test_image(
            3,
            2,
            {
                (255, 0, 0, 255): [(0, 0), (1, 0), (2, 0), (0, 1)],
                (0, 0, 255, 255): [(1, 1), (2, 1)],
            },
        )
        self.test_files.append(filepath)
        config = ConversionConfig(max_colors=2, auto_backing_color=True)

        pixel_data = load_image(filepath, config)

        self.assertEqual(config.backing_color, (255, 0, 0))
        self.assertEqual(len(pixel_data.get_unique_colors()), 2)

    def test_auto_backing_color_tie_uses_first_scanned_color(self):
        """Equal-frequency colors resolve deterministically in image scan order."""
        filepath = create_test_image(
            2,
            1,
            {
                (0, 255, 0, 255): [(0, 0)],
                (255, 0, 0, 255): [(1, 0)],
            },
        )
        self.test_files.append(filepath)
        config = ConversionConfig(auto_backing_color=True)

        load_image(filepath, config)

        self.assertEqual(config.backing_color, (0, 255, 0))

    def test_auto_backing_color_is_in_quantized_palette(self):
        """Automatic backing is recalculated from the final quantized colors."""
        filepath = create_test_image(
            3,
            1,
            {
                (255, 0, 0, 255): [(0, 0)],
                (0, 255, 0, 255): [(1, 0)],
                (0, 0, 255, 255): [(2, 0)],
            },
        )
        self.test_files.append(filepath)
        config = ConversionConfig(
            max_colors=2,
            auto_backing_color=True,
            quantize=True,
            quantize_colors=2,
        )

        pixel_data = load_image(filepath, config)

        self.assertIn(config.backing_color, pixel_data.get_unique_colors())
        self.assertLessEqual(len(pixel_data.get_unique_colors()), 2)

    def test_auto_backing_color_rejects_fully_transparent_image(self):
        """Automatic selection requires at least one visible pixel."""
        filepath = create_test_image(2, 2, {})
        self.test_files.append(filepath)

        with self.assertRaisesRegex(ValueError, "no non-transparent pixels"):
            load_image(filepath, ConversionConfig(auto_backing_color=True))

    def test_nonexistent_file(self):
        """Test that loading nonexistent file raises error."""
        config = ConversionConfig(max_size_mm=200.0)
        with self.assertRaises(FileNotFoundError):
            load_image("/nonexistent/file.png", config)

    def test_pixel_size_calculation(self):
        """Test that pixel size is calculated correctly."""
        filepath = create_simple_square_image(size=100, color=(255, 0, 0))
        self.test_files.append(filepath)

        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)

        self.assertEqual(pixel_data.pixel_size_mm, 2.0)  # 200 / 100


class TestGetPixelBoundsMm(unittest.TestCase):
    """Test conversion from pixel coordinates to millimeter bounds."""
    
    def test_pixel_bounds_at_origin(self):
        """Test bounds calculation for pixel at origin."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=10, height=10, pixel_size_mm=2.0, pixels=pixels)
        
        min_x, max_x, min_y, max_y = get_pixel_bounds_mm(pixel_data, 0, 0)
        
        self.assertEqual(min_x, 0.0)
        self.assertEqual(max_x, 2.0)
        self.assertEqual(min_y, 0.0)
        self.assertEqual(max_y, 2.0)
    
    def test_pixel_bounds_offset(self):
        """Test bounds calculation for pixel at offset position."""
        pixels = {(5, 3): (255, 0, 0, 255)}
        pixel_data = PixelData(width=10, height=10, pixel_size_mm=2.0, pixels=pixels)
        
        min_x, max_x, min_y, max_y = get_pixel_bounds_mm(pixel_data, 5, 3)
        
        self.assertEqual(min_x, 10.0)  # 5 * 2.0
        self.assertEqual(max_x, 12.0)  # 6 * 2.0
        self.assertEqual(min_y, 6.0)   # 3 * 2.0
        self.assertEqual(max_y, 8.0)   # 4 * 2.0
    
    def test_pixel_bounds_with_fractional_size(self):
        """Test bounds calculation with non-integer pixel size."""
        pixels = {(2, 2): (255, 0, 0, 255)}
        pixel_data = PixelData(width=10, height=10, pixel_size_mm=1.5, pixels=pixels)
        
        min_x, max_x, min_y, max_y = get_pixel_bounds_mm(pixel_data, 2, 2)
        
        self.assertAlmostEqual(min_x, 3.0, places=6)  # 2 * 1.5
        self.assertAlmostEqual(max_x, 4.5, places=6)  # 3 * 1.5
        self.assertAlmostEqual(min_y, 3.0, places=6)  # 2 * 1.5
        self.assertAlmostEqual(max_y, 4.5, places=6)  # 3 * 1.5


if __name__ == '__main__':
    unittest.main()
