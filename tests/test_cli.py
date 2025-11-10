"""
Tests for CLI-specific functionality including batch processing.

This module tests the command-line interface functionality including:
- Batch processing (process_batch function)
- Batch summary generation (generate_batch_summary function)
- Image file detection (is_image_file function)
- CLI argument validation
- skip_checks flag behavior
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.cli import is_image_file, process_batch, generate_batch_summary
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import (
    create_simple_square_image,
    create_two_region_image,
    create_test_image,
    cleanup_test_file
)


class TestIsImageFile(unittest.TestCase):
    """Test the is_image_file function."""
    
    def test_png_file(self):
        """Test that PNG files are recognized as images."""
        path = Path("test.png")
        self.assertTrue(is_image_file(path))
    
    def test_jpg_file(self):
        """Test that JPG files are recognized as images."""
        path = Path("test.jpg")
        self.assertTrue(is_image_file(path))
    
    def test_jpeg_file(self):
        """Test that JPEG files are recognized as images."""
        path = Path("test.jpeg")
        self.assertTrue(is_image_file(path))
    
    def test_gif_file(self):
        """Test that GIF files are recognized as images."""
        path = Path("test.gif")
        self.assertTrue(is_image_file(path))
    
    def test_bmp_file(self):
        """Test that BMP files are recognized as images."""
        path = Path("test.bmp")
        self.assertTrue(is_image_file(path))
    
    def test_uppercase_extension(self):
        """Test that uppercase extensions are recognized."""
        path = Path("test.PNG")
        self.assertTrue(is_image_file(path))
    
    def test_mixed_case_extension(self):
        """Test that mixed case extensions are recognized."""
        path = Path("test.JpEg")
        self.assertTrue(is_image_file(path))
    
    def test_non_image_file(self):
        """Test that non-image files are not recognized."""
        path = Path("test.txt")
        self.assertFalse(is_image_file(path))
    
    def test_3mf_file(self):
        """Test that 3MF files are not recognized as images."""
        path = Path("test.3mf")
        self.assertFalse(is_image_file(path))
    
    def test_no_extension(self):
        """Test that files without extensions are not recognized."""
        path = Path("test")
        self.assertFalse(is_image_file(path))


class TestProcessBatch(unittest.TestCase):
    """Test the process_batch function."""
    
    def setUp(self):
        """Set up temporary directories for testing."""
        self.test_files = []
        self.temp_dirs = []
        
        # Create temporary input and output directories
        self.input_dir = Path(tempfile.mkdtemp())
        self.output_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.extend([self.input_dir, self.output_dir])
    
    def tearDown(self):
        """Clean up test files and directories."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
        
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_process_empty_folder(self):
        """Test batch processing with empty input folder."""
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config)
        
        self.assertEqual(len(results['success']), 0)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 0)
    
    def test_process_single_image(self):
        """Test batch processing with a single image."""
        # Create a test image in input folder
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        dest_path = self.input_dir / "test.png"
        shutil.move(img_path, dest_path)
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should have 1 successful conversion
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 0)
        
        # Check that output file was created
        self.assertTrue((self.output_dir / "test_model.3mf").exists())
        
        # Check success result structure
        success_item = results['success'][0]
        self.assertEqual(success_item['input_file'], 'test.png')
        self.assertEqual(success_item['output_file'], 'test_model.3mf')
        self.assertIn('num_regions', success_item)
        self.assertIn('num_colors', success_item)
        self.assertIn('file_size', success_item)
    
    def test_process_multiple_images(self):
        """Test batch processing with multiple images."""
        # Create multiple test images
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        img2_path = create_two_region_image()
        
        shutil.move(img1_path, self.input_dir / "image1.png")
        shutil.move(img2_path, self.input_dir / "image2.png")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should have 2 successful conversions
        self.assertEqual(len(results['success']), 2)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 0)
        
        # Check output files exist
        self.assertTrue((self.output_dir / "image1_model.3mf").exists())
        self.assertTrue((self.output_dir / "image2_model.3mf").exists())
    
    def test_process_with_skip_checks(self):
        """Test batch processing with skip_checks enabled."""
        # Create a small high-resolution image that would normally trigger a warning
        # We use a small image (50x50) but adjust max_size to make it exceed the threshold
        test_size = 50
        
        # Create solid color image (fast with numpy optimization)
        positions = [(x, y) for x in range(test_size) for y in range(test_size)]
        colors = {(255, 0, 0, 255): positions}
        img_path = create_test_image(test_size, test_size, colors)
        
        dest_path = self.input_dir / "highres.png"
        shutil.move(img_path, dest_path)
        
        # With skip_checks=True, should process successfully
        # Set max_size small enough that our 50px image exceeds the recommended resolution
        # max_recommended_px = max_size_mm / line_width_mm
        # We want 50 > max_size_mm / 0.42, so max_size_mm < 21
        config = ConversionConfig(skip_checks=True, batch_mode=True, max_size_mm=20.0)
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should succeed (not be skipped)
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 0)
    
    def test_process_without_skip_checks_high_resolution(self):
        """Test batch processing without skip_checks on high-resolution image."""
        # Create a small high-resolution image that exceeds the recommended resolution
        # We use a small image (50x50) but adjust max_size to make it exceed the threshold
        test_size = 50
        
        # Create solid color image (fast with numpy optimization)
        positions = [(x, y) for x in range(test_size) for y in range(test_size)]
        colors = {(255, 0, 0, 255): positions}
        img_path = create_test_image(test_size, test_size, colors)
        
        dest_path = self.input_dir / "highres.png"
        shutil.move(img_path, dest_path)
        
        # With batch_mode=True but skip_checks=False, should skip due to resolution warning
        # Set max_size small enough that our 50px image exceeds the recommended resolution
        # max_recommended_px = max_size_mm / line_width_mm
        # We want 50 > max_size_mm / 0.42, so max_size_mm < 21
        config = ConversionConfig(skip_checks=False, batch_mode=True, max_size_mm=20.0)
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should be skipped (resolution warning)
        self.assertEqual(len(results['success']), 0)
        self.assertEqual(len(results['skipped']), 1)
        self.assertEqual(len(results['failed']), 0)
        
        # Check skipped result structure
        skipped_item = results['skipped'][0]
        self.assertEqual(skipped_item['input_file'], 'highres.png')
        self.assertIn('resolution too high', skipped_item['reason'].lower())
    
    def test_process_with_too_many_colors(self):
        """Test batch processing with image having too many colors."""
        # Create image with 3 colors but set max_colors=2
        colors = {
            (255, 0, 0, 255): [(0, 0)],
            (0, 255, 0, 255): [(1, 0)],
            (0, 0, 255, 255): [(0, 1)]
        }
        img_path = create_test_image(2, 2, colors)
        dest_path = self.input_dir / "multicolor.png"
        shutil.move(img_path, dest_path)
        
        config = ConversionConfig(max_colors=2)
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should fail (too many colors)
        self.assertEqual(len(results['success']), 0)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 1)
        
        # Check failed result structure
        failed_item = results['failed'][0]
        self.assertEqual(failed_item['input_file'], 'multicolor.png')
        self.assertIn('error', failed_item)
    
    def test_process_ignores_non_image_files(self):
        """Test that batch processing ignores non-image files."""
        # Create a test image and a non-image file
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        shutil.move(img_path, self.input_dir / "test.png")
        
        # Create a non-image file
        (self.input_dir / "readme.txt").write_text("Not an image")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should only process the image file
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(results['success'][0]['input_file'], 'test.png')
    
    def test_process_creates_output_folder(self):
        """Test that batch processing creates output folder if it doesn't exist."""
        # Delete the output folder
        shutil.rmtree(self.output_dir)
        self.assertFalse(self.output_dir.exists())
        
        # Create a test image
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        shutil.move(img_path, self.input_dir / "test.png")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Output folder should now exist
        self.assertTrue(self.output_dir.exists())
        self.assertEqual(len(results['success']), 1)
    
    def test_process_mixed_results(self):
        """Test batch processing with mix of successful, skipped, and failed conversions."""
        # Create a successful image (low resolution)
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        shutil.move(img1_path, self.input_dir / "good.png")
        
        # Create a high-resolution image (will be skipped)
        # Use small 50x50 image but adjust max_size to trigger warning
        test_size = 50
        positions = [(x, y) for x in range(test_size) for y in range(test_size)]
        colors = {(255, 0, 0, 255): positions}
        img2_path = create_test_image(test_size, test_size, colors)
        shutil.move(img2_path, self.input_dir / "highres.png")
        
        # Create an image with too many colors (will fail)
        colors = {
            (255, 0, 0, 255): [(0, 0)],
            (0, 255, 0, 255): [(1, 0)],
            (0, 0, 255, 255): [(0, 1)]
        }
        img3_path = create_test_image(2, 2, colors)
        shutil.move(img3_path, self.input_dir / "multicolor.png")
        
        # Configure: max_colors=2 (causes fail), max_size=20 (causes skip)
        config = ConversionConfig(max_colors=2, batch_mode=True, max_size_mm=20.0)
        results = process_batch(self.input_dir, self.output_dir, config)
        
        # Should have 1 success, 1 skipped, 1 failed
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(len(results['skipped']), 1)
        self.assertEqual(len(results['failed']), 1)
    
    def test_process_recursive_single_level(self):
        """Test batch processing with recurse=True on a single subfolder level."""
        # Create folder structure with images at different levels
        subfolder = self.input_dir / "subfolder"
        subfolder.mkdir()
        
        # Create images at root and subfolder level
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        img2_path = create_simple_square_image(size=4, color=(0, 255, 0))
        
        shutil.move(img1_path, self.input_dir / "root.png")
        shutil.move(img2_path, subfolder / "sub.png")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config, recurse=True)
        
        # Should process both images
        self.assertEqual(len(results['success']), 2)
        self.assertEqual(len(results['skipped']), 0)
        self.assertEqual(len(results['failed']), 0)
        
        # Check that output files exist in correct locations
        self.assertTrue((self.output_dir / "root_model.3mf").exists())
        self.assertTrue((self.output_dir / "subfolder" / "sub_model.3mf").exists())
        
        # Check relative paths in results
        input_files = [item['input_file'] for item in results['success']]
        output_files = [item['output_file'] for item in results['success']]
        self.assertIn('root.png', input_files)
        # Use os.path.join or normalize path separators for cross-platform compatibility
        self.assertIn(str(Path('subfolder/sub.png')), input_files)
        self.assertIn('root_model.3mf', output_files)
        self.assertIn(str(Path('subfolder/sub_model.3mf')), output_files)
    
    def test_process_recursive_multiple_levels(self):
        """Test batch processing with recurse=True on multiple nested levels."""
        # Create nested folder structure
        level1 = self.input_dir / "level1"
        level2 = level1 / "level2"
        level3 = level2 / "level3"
        level1.mkdir()
        level2.mkdir()
        level3.mkdir()
        
        # Create images at different nesting levels
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        img2_path = create_simple_square_image(size=4, color=(0, 255, 0))
        img3_path = create_simple_square_image(size=4, color=(0, 0, 255))
        img4_path = create_simple_square_image(size=4, color=(255, 255, 0))
        
        shutil.move(img1_path, self.input_dir / "root.png")
        shutil.move(img2_path, level1 / "l1.png")
        shutil.move(img3_path, level2 / "l2.png")
        shutil.move(img4_path, level3 / "l3.png")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config, recurse=True)
        
        # Should process all 4 images
        self.assertEqual(len(results['success']), 4)
        
        # Verify folder structure is preserved
        self.assertTrue((self.output_dir / "root_model.3mf").exists())
        self.assertTrue((self.output_dir / "level1" / "l1_model.3mf").exists())
        self.assertTrue((self.output_dir / "level1" / "level2" / "l2_model.3mf").exists())
        self.assertTrue((self.output_dir / "level1" / "level2" / "level3" / "l3_model.3mf").exists())
        
        # Check relative paths are correct
        input_files = [item['input_file'] for item in results['success']]
        self.assertIn('root.png', input_files)
        self.assertIn(str(Path('level1/l1.png')), input_files)
        self.assertIn(str(Path('level1/level2/l2.png')), input_files)
        self.assertIn(str(Path('level1/level2/level3/l3.png')), input_files)
    
    def test_process_non_recursive_ignores_subfolders(self):
        """Test that process_batch with recurse=False ignores images in subfolders."""
        # Create folder structure with images at different levels
        subfolder = self.input_dir / "subfolder"
        subfolder.mkdir()
        
        # Create images at root and subfolder level
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        img2_path = create_simple_square_image(size=4, color=(0, 255, 0))
        
        shutil.move(img1_path, self.input_dir / "root.png")
        shutil.move(img2_path, subfolder / "sub.png")
        
        config = ConversionConfig()
        results = process_batch(self.input_dir, self.output_dir, config, recurse=False)
        
        # Should only process the root image
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(results['success'][0]['input_file'], 'root.png')
        
        # Only root file should exist in output
        self.assertTrue((self.output_dir / "root_model.3mf").exists())
        self.assertFalse((self.output_dir / "subfolder" / "sub_model.3mf").exists())
    
    def test_process_recursive_with_mixed_results(self):
        """Test recursive batch processing with mix of success, skip, and fail."""
        # Create folder structure
        subfolder = self.input_dir / "subfolder"
        subfolder.mkdir()
        
        # Create a successful image at root
        img1_path = create_simple_square_image(size=4, color=(255, 0, 0))
        shutil.move(img1_path, self.input_dir / "good.png")
        
        # Create a high-resolution image in subfolder (will be skipped)
        # Use small 50x50 image but adjust max_size to trigger warning
        test_size = 50
        positions = [(x, y) for x in range(test_size) for y in range(test_size)]
        colors = {(255, 0, 0, 255): positions}
        img2_path = create_test_image(test_size, test_size, colors)
        shutil.move(img2_path, subfolder / "highres.png")
        
        # Configure with max_size=20 to trigger skip on 50px image
        config = ConversionConfig(batch_mode=True, max_size_mm=20.0)
        results = process_batch(self.input_dir, self.output_dir, config, recurse=True)
        
        # Should have 1 success, 1 skipped
        self.assertEqual(len(results['success']), 1)
        self.assertEqual(len(results['skipped']), 1)
        
        # Check relative paths include subfolder
        self.assertEqual(results['success'][0]['input_file'], 'good.png')
        self.assertEqual(results['skipped'][0]['input_file'], str(Path('subfolder/highres.png')))


class TestGenerateBatchSummary(unittest.TestCase):
    """Test the generate_batch_summary function."""
    
    def setUp(self):
        """Set up temporary directories for testing."""
        self.temp_dirs = []
        self.output_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(self.output_dir)
    
    def tearDown(self):
        """Clean up test directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_generate_summary_empty_results(self):
        """Test generating summary with no results."""
        results = {
            'success': [],
            'skipped': [],
            'failed': []
        }
        
        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 12, 0, 30)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        # Check file was created
        self.assertTrue(Path(summary_path).exists())
        
        # Read and verify content (specify UTF-8 to handle emojis)
        content = Path(summary_path).read_text(encoding='utf-8')
        self.assertIn("Batch Conversion Summary", content)
        self.assertIn("2025-01-01", content)
        self.assertIn("30.0 seconds", content)
        self.assertIn("**Successful:** 0 files", content)
        self.assertIn("**Skipped:** 0 files", content)
        self.assertIn("**Failed:** 0 files", content)
    
    def test_generate_summary_with_success(self):
        """Test generating summary with successful conversions."""
        results = {
            'success': [
                {
                    'input_file': 'test1.png',
                    'output_file': 'test1_model.3mf',
                    'num_regions': 5,
                    'num_colors': 3,
                    'model_width_mm': 100.0,
                    'model_height_mm': 150.0,
                    'file_size': '1.2 KB'
                },
                {
                    'input_file': 'test2.png',
                    'output_file': 'test2_model.3mf',
                    'num_regions': 10,
                    'num_colors': 4,
                    'model_width_mm': 200.0,
                    'model_height_mm': 200.0,
                    'file_size': '2.5 KB'
                }
            ],
            'skipped': [],
            'failed': []
        }
        
        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 12, 1, 0)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        content = Path(summary_path).read_text(encoding='utf-8')
        self.assertIn("**Successful:** 2 files", content)
        self.assertIn("test1.png", content)
        self.assertIn("test2.png", content)
        self.assertIn("100.0x150.0mm", content)
        self.assertIn("200.0x200.0mm", content)
        self.assertIn("1.2 KB", content)
        self.assertIn("2.5 KB", content)
    
    def test_generate_summary_with_skipped(self):
        """Test generating summary with skipped files."""
        results = {
            'success': [],
            'skipped': [
                {
                    'input_file': 'highres.png',
                    'reason': 'Image resolution too high for reliable printing.'
                }
            ],
            'failed': []
        }
        
        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 12, 0, 10)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        content = Path(summary_path).read_text(encoding='utf-8')
        self.assertIn("**Skipped:** 1 files", content)
        self.assertIn("highres.png", content)
        self.assertIn("resolution too high", content)
    
    def test_generate_summary_with_failed(self):
        """Test generating summary with failed conversions."""
        results = {
            'success': [],
            'skipped': [],
            'failed': [
                {
                    'input_file': 'bad.png',
                    'error': 'Too many unique colors'
                }
            ]
        }
        
        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 12, 0, 5)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        content = Path(summary_path).read_text(encoding='utf-8')
        self.assertIn("**Failed:** 1 files", content)
        self.assertIn("bad.png", content)
        self.assertIn("Too many unique colors", content)
    
    def test_generate_summary_mixed_results(self):
        """Test generating summary with mixed results."""
        results = {
            'success': [
                {
                    'input_file': 'good.png',
                    'output_file': 'good_model.3mf',
                    'num_regions': 5,
                    'num_colors': 3,
                    'model_width_mm': 100.0,
                    'model_height_mm': 100.0,
                    'file_size': '1.0 KB'
                }
            ],
            'skipped': [
                {
                    'input_file': 'highres.png',
                    'reason': 'Resolution warning'
                }
            ],
            'failed': [
                {
                    'input_file': 'bad.png',
                    'error': 'Some error'
                }
            ]
        }
        
        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 12, 0, 15)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        content = Path(summary_path).read_text(encoding='utf-8')
        self.assertIn("**Successful:** 1 files", content)
        self.assertIn("**Skipped:** 1 files", content)
        self.assertIn("**Failed:** 1 files", content)
        self.assertIn("**Total processed:** 3 files", content)
    
    def test_summary_filename_format(self):
        """Test that summary filename includes timestamp."""
        results = {'success': [], 'skipped': [], 'failed': []}
        start_time = datetime(2025, 1, 15, 14, 30, 45)
        end_time = datetime(2025, 1, 15, 14, 30, 50)
        
        summary_path = generate_batch_summary(results, self.output_dir, start_time, end_time)
        
        # Check filename format: batch_summary_YYYYMMDDHHMMSS.md
        filename = Path(summary_path).name
        self.assertTrue(filename.startswith("batch_summary_"))
        self.assertTrue(filename.endswith(".md"))
        self.assertIn("20250115143045", filename)


class TestConversionConfigBatchFlags(unittest.TestCase):
    """Test ConversionConfig with batch-related flags."""
    
    def test_default_skip_checks_is_false(self):
        """Test that skip_checks defaults to False."""
        config = ConversionConfig()
        self.assertFalse(config.skip_checks)
    
    def test_default_batch_mode_is_false(self):
        """Test that batch_mode defaults to False."""
        config = ConversionConfig()
        self.assertFalse(config.batch_mode)
    
    def test_set_skip_checks_true(self):
        """Test setting skip_checks to True."""
        config = ConversionConfig(skip_checks=True)
        self.assertTrue(config.skip_checks)
    
    def test_set_batch_mode_true(self):
        """Test setting batch_mode to True."""
        config = ConversionConfig(batch_mode=True)
        self.assertTrue(config.batch_mode)
    
    def test_both_flags_true(self):
        """Test setting both flags to True."""
        config = ConversionConfig(skip_checks=True, batch_mode=True)
        self.assertTrue(config.skip_checks)
        self.assertTrue(config.batch_mode)


class TestFilamentFilters(unittest.TestCase):
    """Test filament filter configuration with single values and lists."""
    
    def test_default_filament_filters(self):
        """Test that filament filters use default values when not specified."""
        config = ConversionConfig()
        self.assertEqual(config.filament_maker, "Bambu Lab")
        self.assertEqual(config.filament_type, "PLA")
        self.assertEqual(config.filament_finish, ["Basic", "Matte"])
    
    def test_single_string_filament_maker(self):
        """Test setting filament_maker as a single string."""
        config = ConversionConfig(filament_maker="Polymaker")
        self.assertEqual(config.filament_maker, "Polymaker")
    
    def test_list_filament_maker(self):
        """Test setting filament_maker as a list."""
        config = ConversionConfig(filament_maker=["Bambu Lab", "Polymaker"])
        self.assertEqual(config.filament_maker, ["Bambu Lab", "Polymaker"])
    
    def test_single_string_filament_type(self):
        """Test setting filament_type as a single string."""
        config = ConversionConfig(filament_type="PETG")
        self.assertEqual(config.filament_type, "PETG")
    
    def test_list_filament_type(self):
        """Test setting filament_type as a list."""
        config = ConversionConfig(filament_type=["PLA", "PETG"])
        self.assertEqual(config.filament_type, ["PLA", "PETG"])
    
    def test_single_string_filament_finish(self):
        """Test setting filament_finish as a single string."""
        config = ConversionConfig(filament_finish="Silk")
        self.assertEqual(config.filament_finish, "Silk")
    
    def test_list_filament_finish(self):
        """Test setting filament_finish as a list."""
        config = ConversionConfig(filament_finish=["Silk", "Matte"])
        self.assertEqual(config.filament_finish, ["Silk", "Matte"])
    
    def test_all_filters_as_lists(self):
        """Test setting all filament filters as lists."""
        config = ConversionConfig(
            filament_maker=["Bambu Lab", "Polymaker"],
            filament_type=["PLA", "PETG"],
            filament_finish=["Basic", "Silk"]
        )
        self.assertEqual(config.filament_maker, ["Bambu Lab", "Polymaker"])
        self.assertEqual(config.filament_type, ["PLA", "PETG"])
        self.assertEqual(config.filament_finish, ["Basic", "Silk"])


if __name__ == '__main__':
    unittest.main()
