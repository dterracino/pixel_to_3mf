"""
Tests for mesh statistics and validation.

Tests that mesh generation produces the expected number of triangles/vertices
and validates triangle winding order.
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.mesh_generator import generate_region_mesh, generate_backing_plate
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.threemf_writer import count_mesh_stats, validate_triangle_winding
from tests.helpers import (
    create_simple_square_image,
    cleanup_test_file,
    calculate_expected_triangle_count,
    calculate_expected_vertex_count
)


class TestMeshStatistics(unittest.TestCase):
    """Test mesh statistics counting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_simple_square_triangle_count(self):
        """Test that a simple square image produces expected triangle count."""
        # Create a 4x4 image (16 pixels)
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_path)
        
        # Convert with backing plate
        config = ConversionConfig(base_height_mm=1.0)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Verify we got mesh stats
        self.assertIn('num_triangles', stats)
        self.assertIn('num_vertices', stats)
        
        # Should have triangles (exact count depends on mesh generator)
        self.assertGreater(stats['num_triangles'], 0)
        self.assertGreater(stats['num_vertices'], 0)
        
        # Rough sanity check: 16 pixels should have at least 32 triangles
        # (2 per pixel top, plus backing, plus sides)
        self.assertGreater(stats['num_triangles'], 32)
    
    def test_no_backing_plate_reduces_triangles(self):
        """Test that disabling backing plate reduces triangle count."""
        # Create a 4x4 image
        input_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(input_path)
        
        # Convert with backing
        fd, output_with_backing = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_with_backing)
        
        config_with_backing = ConversionConfig(base_height_mm=1.0)
        stats_with = convert_image_to_3mf(input_path, output_with_backing, config=config_with_backing)
        
        # Convert without backing
        fd, output_no_backing = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_no_backing)
        
        config_no_backing = ConversionConfig(base_height_mm=0)
        stats_without = convert_image_to_3mf(input_path, output_no_backing, config=config_no_backing)
        
        # Should have fewer triangles without backing plate
        self.assertLess(stats_without['num_triangles'], stats_with['num_triangles'])
        self.assertLess(stats_without['num_vertices'], stats_with['num_vertices'])
    
    def test_larger_image_more_triangles(self):
        """Test that larger images produce more triangles."""
        # Create small image (4x4 = 16 pixels)
        small_path = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(small_path)
        
        # Create larger image (8x8 = 64 pixels = 4x more pixels)
        large_path = create_simple_square_image(size=8, color=(255, 0, 0))
        self.test_files.append(large_path)
        
        # Convert small
        fd, output_small = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_small)
        stats_small = convert_image_to_3mf(small_path, output_small)
        
        # Convert large
        fd, output_large = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.test_files.append(output_large)
        stats_large = convert_image_to_3mf(large_path, output_large)
        
        # Larger image should have more triangles (approximately 4x)
        self.assertGreater(stats_large['num_triangles'], stats_small['num_triangles'])
        self.assertGreater(stats_large['num_vertices'], stats_small['num_vertices'])
        
        # Should be roughly 4x (64 pixels vs 16 pixels)
        ratio = stats_large['num_triangles'] / stats_small['num_triangles']
        self.assertGreater(ratio, 3.0)  # Allow some variance due to shared edges
        self.assertLess(ratio, 5.0)


class TestTriangleWinding(unittest.TestCase):
    """Test triangle winding order validation."""
    
    def test_region_mesh_has_ccw_winding(self):
        """Test that generated region meshes use CCW winding."""
        # Create a simple region (2x2 square of pixels)
        region = Region(
            color=(255, 0, 0),
            pixels={(0, 0), (1, 0), (0, 1), (1, 1)}
        )
        
        # Create pixel data
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (0, 1): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)
        }
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        # Generate mesh
        mesh = generate_region_mesh(region, pixel_data, config)
        
        # Validate winding
        winding = validate_triangle_winding(mesh)
        self.assertEqual(winding, "CCW",
                        f"Region mesh should use CCW winding, got {winding}")
    
    def test_backing_plate_has_ccw_winding(self):
        """Test that backing plate uses CCW winding."""
        # Create pixel data
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (0, 1): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)
        }
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig(base_height_mm=1.0)
        
        # Generate backing plate
        mesh = generate_backing_plate(pixel_data, config)
        
        # Validate winding - backing plate top surface should also be CCW
        winding = validate_triangle_winding(mesh)
        self.assertEqual(winding, "CCW",
                        f"Backing plate should use CCW winding, got {winding}")


class TestCountMeshStats(unittest.TestCase):
    """Test the count_mesh_stats utility function."""
    
    def test_count_single_mesh(self):
        """Test counting stats for a single mesh."""
        from pixel_to_3mf.mesh_generator import Mesh
        
        # Create simple mesh (1 triangle)
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles = [(0, 1, 2)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        meshes = [(mesh, "test_mesh")]
        total_vertices, total_triangles = count_mesh_stats(meshes)
        
        self.assertEqual(total_vertices, 3)
        self.assertEqual(total_triangles, 1)
    
    def test_count_multiple_meshes(self):
        """Test counting stats for multiple meshes."""
        from pixel_to_3mf.mesh_generator import Mesh
        
        # Create two meshes
        vertices1 = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles1 = [(0, 1, 2)]
        mesh1 = Mesh(vertices=vertices1, triangles=triangles1)
        
        vertices2 = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        triangles2 = [(0, 1, 2), (0, 2, 3)]
        mesh2 = Mesh(vertices=vertices2, triangles=triangles2)
        
        meshes = [(mesh1, "mesh1"), (mesh2, "mesh2")]
        total_vertices, total_triangles = count_mesh_stats(meshes)
        
        self.assertEqual(total_vertices, 7)  # 3 + 4
        self.assertEqual(total_triangles, 3)  # 1 + 2


if __name__ == '__main__':
    unittest.main()
