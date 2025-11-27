"""
Tests for the render_model module.

Tests the 3D model rendering functionality to ensure it generates
PNG images correctly.
"""

import unittest
import os
import sys
import tempfile
from pathlib import Path
from PIL import Image

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.render_model import generate_render_path
from tests.helpers import create_simple_square_image, cleanup_test_file


class TestRenderPath(unittest.TestCase):
    """Test render path generation."""
    
    def test_generate_render_path_basic(self):
        """Test basic render path generation."""
        output_path = "/tmp/model.3mf"
        render_path = generate_render_path(output_path)
        self.assertEqual(render_path, "/tmp/model_render.png")
    
    def test_generate_render_path_with_subdirectory(self):
        """Test render path generation with subdirectory."""
        output_path = "/tmp/output/test_model.3mf"
        render_path = generate_render_path(output_path)
        self.assertEqual(render_path, "/tmp/output/test_model_render.png")
    
    def test_generate_render_path_complex_name(self):
        """Test render path generation with complex filename."""
        output_path = "/home/user/models/my_pixel_art_model.3mf"
        render_path = generate_render_path(output_path)
        self.assertEqual(render_path, "/home/user/models/my_pixel_art_model_render.png")


class TestRenderIntegration(unittest.TestCase):
    """Test rendering integration with the conversion pipeline."""
    
    def setUp(self):
        """Set up test files list for cleanup."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_render_enabled(self):
        """Test that rendering is performed when enabled in config."""
        # Create a simple test image
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(img_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Create config with rendering enabled
        config = ConversionConfig(
            max_size_mm=50.0,
            render_model=True  # Enable rendering
        )
        
        # Run conversion
        stats = convert_image_to_3mf(
            input_path=img_path,
            output_path=output_path,
            config=config
        )
        
        # Verify render path is in stats
        self.assertIn('render_path', stats)
        
        # Verify render file exists
        render_path = stats['render_path']
        self.test_files.append(render_path)
        self.assertTrue(os.path.exists(render_path))
        
        # Verify it's a valid PNG
        img = Image.open(render_path)
        self.assertEqual(img.format, 'PNG')
        
        # Verify it has reasonable dimensions (should be non-empty)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)
        img.close()
    
    def test_render_disabled_by_default(self):
        """Test that rendering is disabled by default."""
        # Create a simple test image
        img_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(img_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Create config with default settings (render_model=False)
        config = ConversionConfig(max_size_mm=50.0)
        
        # Run conversion
        stats = convert_image_to_3mf(
            input_path=img_path,
            output_path=output_path,
            config=config
        )
        
        # Verify render path is NOT in stats
        self.assertNotIn('render_path', stats)
        
        # Verify render file does NOT exist
        render_path = generate_render_path(output_path)
        self.assertFalse(os.path.exists(render_path))
    
    def test_render_with_multiple_colors(self):
        """Test rendering with multiple colored regions."""
        # Create a 4x4 image with 4 different colored squares
        from PIL import Image as PILImage
        img = PILImage.new('RGB', (4, 4))
        pixels = img.load()
        
        # Top-left: Red
        pixels[0, 0] = (255, 0, 0)
        pixels[1, 0] = (255, 0, 0)
        pixels[0, 1] = (255, 0, 0)
        pixels[1, 1] = (255, 0, 0)
        
        # Top-right: Green
        pixels[2, 0] = (0, 255, 0)
        pixels[3, 0] = (0, 255, 0)
        pixels[2, 1] = (0, 255, 0)
        pixels[3, 1] = (0, 255, 0)
        
        # Bottom-left: Blue
        pixels[0, 2] = (0, 0, 255)
        pixels[1, 2] = (0, 0, 255)
        pixels[0, 3] = (0, 0, 255)
        pixels[1, 3] = (0, 0, 255)
        
        # Bottom-right: Yellow
        pixels[2, 2] = (255, 255, 0)
        pixels[3, 2] = (255, 255, 0)
        pixels[2, 3] = (255, 255, 0)
        pixels[3, 3] = (255, 255, 0)
        
        fd, img_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        img.save(img_path)
        self.test_files.append(img_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Create config with rendering enabled
        config = ConversionConfig(
            max_size_mm=50.0,
            render_model=True
        )
        
        # Run conversion
        stats = convert_image_to_3mf(
            input_path=img_path,
            output_path=output_path,
            config=config
        )
        
        # Verify render was created
        self.assertIn('render_path', stats)
        render_path = stats['render_path']
        self.test_files.append(render_path)
        self.assertTrue(os.path.exists(render_path))
        
        # Verify it's a valid image
        img = Image.open(render_path)
        self.assertEqual(img.format, 'PNG')
        img.close()


if __name__ == '__main__':
    unittest.main()
