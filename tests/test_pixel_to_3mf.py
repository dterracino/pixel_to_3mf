"""
Integration tests for the main pixel_to_3mf conversion function.

Tests the complete conversion pipeline from image to 3MF.
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf, format_filesize
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import (
    create_simple_square_image,
    create_two_region_image,
    create_transparent_image,
    cleanup_test_file,
    get_sample_image,
    validate_3mf_structure
)


class TestConvertImageTo3MF(unittest.TestCase):
    """Test the main conversion function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_convert_simple_image(self):
        """Test converting a simple single-color image."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        stats = convert_image_to_3mf(input_path, output_path)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
        
        # Check stats
        self.assertEqual(stats['image_width'], 4)
        self.assertEqual(stats['image_height'], 4)
        self.assertEqual(stats['num_pixels'], 16)
        self.assertEqual(stats['num_colors'], 1)
        self.assertEqual(stats['num_regions'], 1)
        self.assertEqual(stats['output_path'], output_path)
        
        # Verify it's a valid 3MF with proper structure
        validate_3mf_structure(output_path)
    
    def test_convert_two_region_image(self):
        """Test converting image with two separate regions."""
        input_path = create_two_region_image()
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        stats = convert_image_to_3mf(input_path, output_path)
        
        # Should have 2 colors and 2 regions
        self.assertEqual(stats['num_colors'], 2)
        self.assertEqual(stats['num_regions'], 2)
        
        # Verify output
        self.assertTrue(os.path.exists(output_path))
        validate_3mf_structure(output_path)
    
    def test_convert_transparent_image(self):
        """Test converting image with transparent areas."""
        input_path = create_transparent_image()
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        stats = convert_image_to_3mf(input_path, output_path)
        
        # Only 4 pixels (2x2 center) are non-transparent
        self.assertEqual(stats['num_pixels'], 4)
        self.assertEqual(stats['num_regions'], 1)
        
        # Verify output
        self.assertTrue(os.path.exists(output_path))
    
    def test_convert_with_custom_size(self):
        """Test conversion with custom max_size_mm."""
        input_path = create_simple_square_image(size=100, color=(255, 0, 0))
        self.test_files.append(input_path)

        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)

        config = ConversionConfig(max_size_mm=150.0)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Check dimensions
        self.assertEqual(stats['model_width_mm'], 150.0)
        self.assertEqual(stats['model_height_mm'], 150.0)
        self.assertEqual(stats['pixel_size_mm'], 1.5)  # 150 / 100
    
    def test_convert_with_custom_heights(self):
        """Test conversion with custom layer heights."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Test with custom heights (should not raise error)
        config = ConversionConfig(color_height_mm=2.0, base_height_mm=3.0)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        self.assertTrue(os.path.exists(output_path))
    
    def test_convert_landscape_image(self):
        """Test conversion of landscape image."""
        # Create 8x4 image
        positions = [(x, y) for x in range(8) for y in range(4)]
        from tests.helpers import create_test_image
        colors = {(255, 0, 0, 255): positions}
        input_path = create_test_image(8, 4, colors)
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # max_size_mm=200.0 is the default, no need to specify config
        stats = convert_image_to_3mf(input_path, output_path)

        # Width is larger, so it should be 200mm
        self.assertEqual(stats['model_width_mm'], 200.0)
        self.assertEqual(stats['model_height_mm'], 100.0)  # 4 * 25
        self.assertEqual(stats['pixel_size_mm'], 25.0)  # 200 / 8

    def test_convert_portrait_image(self):
        """Test conversion of portrait image."""
        # Create 4x8 image
        positions = [(x, y) for x in range(4) for y in range(8)]
        from tests.helpers import create_test_image
        colors = {(255, 0, 0, 255): positions}
        input_path = create_test_image(4, 8, colors)
        self.test_files.append(input_path)

        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)

        # max_size_mm=200.0 is the default, no need to specify config
        stats = convert_image_to_3mf(input_path, output_path)
        
        # Height is larger, so it should be 200mm
        self.assertEqual(stats['model_width_mm'], 100.0)  # 4 * 25
        self.assertEqual(stats['model_height_mm'], 200.0)
        self.assertEqual(stats['pixel_size_mm'], 25.0)  # 200 / 8
    
    def test_progress_callback(self):
        """Test that progress callback is called during conversion."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Track progress calls
        progress_calls = []
        
        def callback(stage, message):
            progress_calls.append((stage, message))
        
        stats = convert_image_to_3mf(input_path, output_path, progress_callback=callback)
        
        # Should have received progress updates
        self.assertGreater(len(progress_calls), 0)
        
        # Check that different stages were reported
        stages = [stage for stage, msg in progress_calls]
        self.assertIn("load", stages)
        self.assertIn("merge", stages)
        self.assertIn("mesh", stages)
        self.assertIn("export", stages)


class TestConvertImageTo3MFErrors(unittest.TestCase):
    """Test error handling in conversion function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_nonexistent_input_file(self):
        """Test error when input file doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            convert_image_to_3mf("/nonexistent/file.png", "/tmp/output.3mf")
    
    def test_invalid_max_size(self):
        """Test error with invalid max_size_mm."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)

        with self.assertRaises(ValueError):
            config = ConversionConfig(max_size_mm=0)
            convert_image_to_3mf(input_path, "/tmp/output.3mf", config=config)

        with self.assertRaises(ValueError):
            config = ConversionConfig(max_size_mm=-10)
            convert_image_to_3mf(input_path, "/tmp/output.3mf", config=config)

    def test_invalid_color_height(self):
        """Test error with invalid color_height_mm."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)

        with self.assertRaises(ValueError):
            config = ConversionConfig(color_height_mm=0)
            convert_image_to_3mf(input_path, "/tmp/output.3mf", config=config)

    def test_invalid_base_height(self):
        """Test error with invalid base_height_mm (negative values)."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)

        with self.assertRaises(ValueError):
            config = ConversionConfig(base_height_mm=-1)
            convert_image_to_3mf(input_path, "/tmp/output.3mf", config=config)
    
    def test_zero_base_height(self):
        """Test that base_height_mm=0 is allowed (disables backing plate)."""
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Should not raise an error
        config = ConversionConfig(base_height_mm=0)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
    
    def test_too_many_colors(self):
        """Test error when image has too many colors."""
        # Create image with 3 colors
        from tests.helpers import create_test_image
        colors = {
            (255, 0, 0, 255): [(0, 0)],
            (0, 255, 0, 255): [(1, 0)],
            (0, 0, 255, 255): [(0, 1)]
        }
        input_path = create_test_image(2, 2, colors)
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Should fail with max_colors=2 (3 colors in image, but backing reserves 1 slot)
        with self.assertRaises(ValueError) as context:
            config = ConversionConfig(max_colors=2)
            convert_image_to_3mf(input_path, output_path, config=config)

        self.assertIn("unique colors", str(context.exception))


class TestConvertImageTo3MFWithRealSamples(unittest.TestCase):
    """Test conversion with real sample images if available."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_convert_sample_image(self):
        """Test converting a real sample image."""
        try:
            input_path = get_sample_image()
        except FileNotFoundError as e:
            self.skipTest(str(e))
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Convert (may need to increase color limit for real images)
        config = ConversionConfig(max_colors=50)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Verify output
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
        validate_3mf_structure(output_path)
        
        # Verify stats make sense
        self.assertGreater(stats['image_width'], 0)
        self.assertGreater(stats['image_height'], 0)
        self.assertGreater(stats['num_regions'], 0)


class TestFormatFilesize(unittest.TestCase):
    """Test the format_filesize utility function."""
    
    def test_zero_bytes(self):
        """Test formatting zero bytes."""
        self.assertEqual(format_filesize(0), "0B")
    
    def test_bytes(self):
        """Test formatting bytes (less than 1 KB)."""
        self.assertEqual(format_filesize(1), "1.0 B")
        self.assertEqual(format_filesize(500), "500.0 B")
        self.assertEqual(format_filesize(1023), "1023.0 B")
    
    def test_kilobytes(self):
        """Test formatting kilobytes."""
        self.assertEqual(format_filesize(1024), "1.0 KB")
        self.assertEqual(format_filesize(1536), "1.5 KB")
        self.assertEqual(format_filesize(2048), "2.0 KB")
    
    def test_megabytes(self):
        """Test formatting megabytes."""
        self.assertEqual(format_filesize(1048576), "1.0 MB")  # 1024^2
        self.assertEqual(format_filesize(1572864), "1.5 MB")  # 1.5 * 1024^2
        self.assertEqual(format_filesize(5242880), "5.0 MB")  # 5 * 1024^2
    
    def test_gigabytes(self):
        """Test formatting gigabytes."""
        self.assertEqual(format_filesize(1073741824), "1.0 GB")  # 1024^3
        self.assertEqual(format_filesize(2147483648), "2.0 GB")  # 2 * 1024^3
    
    def test_rounding(self):
        """Test that values are rounded to 2 decimal places."""
        # 1234 bytes = 1.205078125 KB -> should round to 1.21 KB
        result = format_filesize(1234)
        self.assertEqual(result, "1.21 KB")
        
        # 1234567 bytes = 1.177376747131348 MB -> should round to 1.18 MB
        result = format_filesize(1234567)
        self.assertEqual(result, "1.18 MB")


class TestConvertWithPadding(unittest.TestCase):
    """Test conversion with padding enabled."""
    
    def test_convert_with_padding_expands_canvas(self):
        """Test that padding expands the canvas."""
        # Create a simple 10x10 image
        img_path = create_simple_square_image(size=10, color=(255, 0, 0))
        output_path = img_path.replace('.png', '_padded.3mf')
        
        try:
            # Convert with 3px padding
            config = ConversionConfig(
                max_size_mm=50,
                padding_size=3,
                padding_color=(255, 255, 255)
            )
            
            stats = convert_image_to_3mf(
                input_path=img_path,
                output_path=output_path,
                config=config
            )
            
            # Image should be expanded by 3px on each side
            # 10 + 2*3 = 16x16
            self.assertEqual(stats['image_width'], 16)
            self.assertEqual(stats['image_height'], 16)
            
            # Should have added the padding color
            # Original: 1 color (red)
            # With padding: 2 colors (red + white padding)
            self.assertEqual(stats['num_colors'], 2)
            
            # Output file should exist
            self.assertTrue(os.path.exists(output_path))
            
        finally:
            cleanup_test_file(img_path)
            cleanup_test_file(output_path)
    
    def test_convert_without_padding_no_expansion(self):
        """Test that no padding means no canvas expansion."""
        # Create a simple 10x10 image
        img_path = create_simple_square_image(size=10, color=(255, 0, 0))
        output_path = img_path.replace('.png', '_no_padding.3mf')
        
        try:
            # Convert without padding (padding_size=0)
            config = ConversionConfig(
                max_size_mm=50,
                padding_size=0
            )
            
            stats = convert_image_to_3mf(
                input_path=img_path,
                output_path=output_path,
                config=config
            )
            
            # Image should remain 10x10
            self.assertEqual(stats['image_width'], 10)
            self.assertEqual(stats['image_height'], 10)
            
            # Should have only 1 color
            self.assertEqual(stats['num_colors'], 1)
            
        finally:
            cleanup_test_file(img_path)
            cleanup_test_file(output_path)


if __name__ == '__main__':
    unittest.main()
