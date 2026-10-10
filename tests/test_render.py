"""
Tests for the render_model module.

Tests the 3D model rendering functionality to ensure it generates
PNG images correctly.
"""

import unittest
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.mesh_generator import Mesh
from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.render_model import (
    generate_render_path,
    render_meshes_to_png,
)
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


class TestRenderOutput(unittest.TestCase):
    """Test render encoding behavior independently of conversion orchestration."""

    def test_empty_geometry_produces_transparent_render(self):
        """A fully trimmed model still needs valid embedded thumbnail PNGs."""
        empty_mesh = Mesh(vertices=[], triangles=[])

        rendered = render_meshes_to_png(
            [(empty_mesh, (255, 255, 255))],
            image_size_px=32,
        )

        with Image.open(io.BytesIO(rendered)) as image:
            self.assertEqual(image.size, (32, 32))
            self.assertIsNone(image.getbbox())


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
        
        # Run conversion. The one high-resolution render must feed both the
        # standalone file and the embedded plate thumbnails.
        with patch(
            "pixel_to_3mf.render_model.render_meshes_to_png",
            wraps=render_meshes_to_png,
        ) as render_mock:
            stats = convert_image_to_3mf(
                input_path=img_path,
                output_path=output_path,
                config=config,
            )

        render_mock.assert_called_once()
        self.assertEqual(render_mock.call_args.kwargs["image_size_px"], 1200)
        
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

        with zipfile.ZipFile(output_path) as archive:
            plate = archive.read("Metadata/plate_1.png")
            no_light = archive.read("Metadata/plate_no_light_1.png")
            top = archive.read("Metadata/top_1.png")

        self.assertEqual(plate, no_light)
        self.assertNotEqual(plate, top)
        with Image.open(io.BytesIO(plate)) as plate_image:
            self.assertEqual(plate_image.size, (512, 512))
            self.assertIsNotNone(plate_image.getbbox())
    
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
        self.assertIsNotNone(pixels)
        assert pixels is not None
        
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

    def test_render_uses_relief_mesh_heights(self):
        """The render input must retain the distinct Z levels from relief mode."""
        source = Image.new("RGB", (2, 1))
        source.putdata([(255, 255, 255), (255, 0, 0)])

        fd, img_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        source.save(img_path)
        self.test_files.append(img_path)

        fd, output_path = tempfile.mkstemp(suffix=".3mf")
        os.close(fd)
        self.test_files.append(output_path)

        captured_meshes: list[tuple[Mesh, tuple[int, int, int]]] = []

        def capture_render(
            colored_meshes: list[tuple[Mesh, tuple[int, int, int]]],
            image_size_px: int = 1200,
        ) -> bytes:
            _ = image_size_px
            captured_meshes.extend(colored_meshes)
            output = io.BytesIO()
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(output, format="PNG")
            return output.getvalue()

        config = ConversionConfig(
            max_size_mm=20.0,
            base_height_mm=0.0,
            color_naming_mode="hex",
            relief=True,
            relief_background_color=(255, 255, 255),
            relief_height_mm=2.0,
            render_model=True,
        )

        with patch(
            "pixel_to_3mf.render_model.render_meshes_to_png",
            side_effect=capture_render,
        ):
            convert_image_to_3mf(
                input_path=img_path,
                output_path=output_path,
                config=config,
            )

        max_z_by_color = {
            color: max(vertex[2] for vertex in mesh.vertices)
            for mesh, color in captured_meshes
        }
        self.assertEqual(max_z_by_color[(255, 255, 255)], 1.0)
        self.assertEqual(max_z_by_color[(255, 0, 0)], 3.0)

    def test_solid_core_shells_use_exported_slot_colors(self):
        """Writer-resolved render input must color both shells and the core."""
        source = Image.new("RGB", (2, 1))
        source.putdata([(255, 0, 0), (0, 0, 255)])

        fd, img_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        source.save(img_path)
        self.test_files.append(img_path)

        fd, output_path = tempfile.mkstemp(suffix=".3mf")
        os.close(fd)
        self.test_files.append(output_path)

        captured_colors: list[tuple[int, int, int]] = []

        def capture_render(
            colored_meshes: list[tuple[Mesh, tuple[int, int, int]]],
            image_size_px: int = 1200,
        ) -> bytes:
            self.assertEqual(image_size_px, 512)
            captured_colors.extend(color for _, color in colored_meshes)
            output = io.BytesIO()
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(output, format="PNG")
            return output.getvalue()

        config = ConversionConfig(
            max_size_mm=20.0,
            base_height_mm=0.0,
            color_naming_mode="hex",
            solid_core=True,
            core_height_mm=1.0,
        )

        with patch(
            "pixel_to_3mf.render_model.render_meshes_to_png",
            side_effect=capture_render,
        ):
            convert_image_to_3mf(
                input_path=img_path,
                output_path=output_path,
                config=config,
            )

        self.assertEqual(captured_colors.count((255, 0, 0)), 2)
        self.assertEqual(captured_colors.count((0, 0, 255)), 2)
        self.assertEqual(captured_colors.count((255, 255, 255)), 1)


if __name__ == '__main__':
    unittest.main()
