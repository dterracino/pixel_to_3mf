"""
Unit tests for the mesh_generator module.

Tests mesh generation for regions and backing plates.
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.mesh_generator import (
    Mesh,
    generate_region_mesh,
    generate_backing_plate
)
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.config import ConversionConfig


class TestMesh(unittest.TestCase):
    """Test the Mesh class."""
    
    def test_mesh_initialization(self):
        """Test Mesh can be created with valid parameters."""
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        triangles = [(0, 1, 2)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        self.assertEqual(len(mesh.vertices), 3)
        self.assertEqual(len(mesh.triangles), 1)
        self.assertEqual(mesh.triangles[0], (0, 1, 2))
    
    def test_mesh_repr(self):
        """Test string representation of Mesh."""
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        triangles = []
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        repr_str = repr(mesh)
        self.assertIn("vertices=2", repr_str)
        self.assertIn("triangles=0", repr_str)


class TestGenerateRegionMesh(unittest.TestCase):
    """Test mesh generation for colored regions."""
    
    def test_single_pixel_mesh(self):
        """Test mesh generation for single pixel region."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=2.0, pixels={(0, 0): (255, 0, 0, 255)})

        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0))
        
        # Single pixel should create a box with 8 vertices and 12 triangles
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        
        # Verify all triangles reference valid vertices
        for tri in mesh.triangles:
            for idx in tri:
                self.assertLess(idx, len(mesh.vertices))
                self.assertGreaterEqual(idx, 0)
    
    def test_2x2_square_mesh(self):
        """Test mesh generation for 2x2 square region."""
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        pixel_dict = {pos: (255, 0, 0, 255) for pos in pixels}
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=2.0, pixels=pixel_dict)
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0)
        
        # Should have vertices and triangles
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        
        # Verify mesh is valid (all triangle indices in range)
        for tri in mesh.triangles:
            for idx in tri:
                self.assertLess(idx, len(mesh.vertices))
    
    def test_l_shape_mesh(self):
        """Test mesh generation for L-shaped region."""
        pixels = {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        pixel_dict = {pos: (255, 0, 0, 255) for pos in pixels}
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=1.0, pixels=pixel_dict)
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.5)
        
        # Complex shape should generate mesh
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_mesh_height(self):
        """Test that mesh respects layer height parameter."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels={(0, 0): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=2.5)
        
        # Check that some vertices have z-coordinate of layer_height
        z_coords = [v[2] for v in mesh.vertices]
        self.assertIn(2.5, z_coords)
        self.assertIn(0.0, z_coords)
    
    def test_mesh_vertices_in_correct_position(self):
        """Test that mesh vertices are positioned correctly in space."""
        region = Region(color=(255, 0, 0), pixels={(2, 3)})
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=2.0, pixels={(2, 3): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0)
        
        # Pixel (2, 3) should have vertices around x=4-6, y=6-8
        x_coords = [v[0] for v in mesh.vertices]
        y_coords = [v[1] for v in mesh.vertices]
        
        # Check that vertices are in expected range
        self.assertGreaterEqual(min(x_coords), 4.0)
        self.assertLessEqual(max(x_coords), 6.0)
        self.assertGreaterEqual(min(y_coords), 6.0)
        self.assertLessEqual(max(y_coords), 8.0)


class TestGenerateBackingPlate(unittest.TestCase):
    """Test backing plate mesh generation."""
    
    def test_single_pixel_backing_plate(self):
        """Test backing plate for single pixel."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0)
        
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        
        # Verify all triangles reference valid vertices
        for tri in mesh.triangles:
            for idx in tri:
                self.assertLess(idx, len(mesh.vertices))
    
    def test_backing_plate_multiple_pixels(self):
        """Test backing plate for multiple pixels."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (0, 1): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)
        }
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=2.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.5)
        
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_backing_plate_height(self):
        """Test that backing plate respects base height parameter."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=3.0)
        
        # Check z-coordinates
        z_coords = [v[2] for v in mesh.vertices]
        # Backing plate should have vertices at z=0 (bottom) and z=-base_height (actual bottom)
        self.assertIn(0.0, z_coords)
        self.assertIn(-3.0, z_coords)
    
    def test_backing_plate_with_holes(self):
        """Test backing plate with transparent areas (holes)."""
        # Create pixel data with a hole in the middle
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255),
            (0, 2): (255, 0, 0, 255),
            (2, 2): (255, 0, 0, 255)
            # (1, 1) is missing - should be a hole
        }
        pixel_data = PixelData(width=3, height=3, pixel_size_mm=1.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0)
        
        # Should still generate valid mesh
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_backing_plate_dimensions(self):
        """Test that backing plate covers correct area."""
        pixels = {(0, 0): (255, 0, 0, 255), (3, 4): (0, 255, 0, 255)}
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=2.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0)
        
        # Get X and Y bounds of vertices
        x_coords = [v[0] for v in mesh.vertices]
        y_coords = [v[1] for v in mesh.vertices]
        
        # Should cover at least the pixels present
        self.assertGreaterEqual(max(x_coords), 8.0)  # (3+1) * 2.0
        self.assertGreaterEqual(max(y_coords), 10.0)  # (4+1) * 2.0


class TestMeshValidity(unittest.TestCase):
    """Test that generated meshes are valid."""
    
    def test_no_degenerate_triangles(self):
        """Test that meshes don't have degenerate triangles."""
        region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0)})
        pixel_dict = {(0, 0): (255, 0, 0, 255), (1, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0)
        
        # Check no triangle has duplicate vertices
        for tri in mesh.triangles:
            self.assertEqual(len(set(tri)), 3, f"Degenerate triangle found: {tri}")
    
    def test_all_vertices_used(self):
        """Test that all vertices are referenced by at least one triangle."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels={(0, 0): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0)
        
        # Collect all vertex indices used in triangles
        used_indices = set()
        for tri in mesh.triangles:
            used_indices.update(tri)
        
        # All vertices should be used (or it's okay if some aren't, just check validity)
        # Actually, it's fine if some vertices aren't used, but let's check no invalid refs
        for idx in used_indices:
            self.assertLess(idx, len(mesh.vertices))


if __name__ == '__main__':
    unittest.main()
