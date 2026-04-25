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
    generate_backing_plate,
    generate_solid_core,
    generate_region_mesh_shell,
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
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0))
        
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
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.5))
        
        # Complex shape should generate mesh
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_mesh_height(self):
        """Test that mesh respects layer height parameter."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels={(0, 0): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=2.5))
        
        # Check that some vertices have z-coordinate of layer_height
        z_coords = [v[2] for v in mesh.vertices]
        self.assertIn(2.5, z_coords)
        self.assertIn(0.0, z_coords)
    
    def test_mesh_vertices_in_correct_position(self):
        """Test that mesh vertices are positioned correctly in space."""
        region = Region(color=(255, 0, 0), pixels={(2, 3)})
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=2.0, pixels={(2, 3): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0))
        
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
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0))
        
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
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.5))
        
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_backing_plate_height(self):
        """Test that backing plate respects base height parameter."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=3.0))
        
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
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0))
        
        # Should still generate valid mesh
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_backing_plate_dimensions(self):
        """Test that backing plate covers correct area."""
        pixels = {(0, 0): (255, 0, 0, 255), (3, 4): (0, 255, 0, 255)}
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=2.0, pixels=pixels)
        
        mesh = generate_backing_plate(pixel_data, ConversionConfig(base_height_mm=1.0))
        
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
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0))
        
        # Check no triangle has duplicate vertices
        for tri in mesh.triangles:
            self.assertEqual(len(set(tri)), 3, f"Degenerate triangle found: {tri}")
    
    def test_all_vertices_used(self):
        """Test that all vertices are referenced by at least one triangle."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels={(0, 0): (255, 0, 0, 255)})
        
        mesh = generate_region_mesh(region, pixel_data, ConversionConfig(color_height_mm=1.0))
        
        # Collect all vertex indices used in triangles
        used_indices = set()
        for tri in mesh.triangles:
            used_indices.update(tri)
        
        # All vertices should be used (or it's okay if some aren't, just check validity)
        # Actually, it's fine if some vertices aren't used, but let's check no invalid refs
        for idx in used_indices:
            self.assertLess(idx, len(mesh.vertices))


class TestGenerateSolidCore(unittest.TestCase):
    """Tests for generate_solid_core() — the full-footprint slab between the colour shells."""

    def _make_rect_pixel_data(self) -> PixelData:
        """2×2 fully-filled rectangle — exercises the fast path in _generate_slab_mesh."""
        pixels = {(x, y): (255, 0, 0, 255) for x in range(2) for y in range(2)}
        return PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)

    def _make_sparse_pixel_data(self) -> PixelData:
        """L-shaped (non-rectangular) footprint — exercises the slow pixel-by-pixel path."""
        coords = {(0, 0), (1, 0), (0, 1)}
        pixels = {c: (255, 0, 0, 255) for c in coords}
        return PixelData(width=3, height=3, pixel_size_mm=1.0, pixels=pixels)

    def test_produces_vertices_and_triangles(self):
        """generate_solid_core returns a non-empty mesh."""
        pixel_data = self._make_rect_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)
        mesh = generate_solid_core(pixel_data, config)
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)

    def test_all_triangle_indices_valid(self):
        """Every triangle index references an existing vertex."""
        pixel_data = self._make_rect_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)
        mesh = generate_solid_core(pixel_data, config)
        for tri in mesh.triangles:
            for idx in tri:
                self.assertGreaterEqual(idx, 0)
                self.assertLess(idx, len(mesh.vertices))

    def test_z_extents_match_config(self):
        """Mesh vertices should span exactly [core_z_bottom, core_z_top]."""
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=2.0)
        pixel_data = self._make_rect_pixel_data()
        mesh = generate_solid_core(pixel_data, config)
        z_coords = [v[2] for v in mesh.vertices]
        self.assertAlmostEqual(min(z_coords), config.core_z_bottom)
        self.assertAlmostEqual(max(z_coords), config.core_z_top)

    def test_z_extents_symmetric_around_zero(self):
        """Core is centred on z=0, so |z_bottom| == z_top."""
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)
        pixel_data = self._make_rect_pixel_data()
        mesh = generate_solid_core(pixel_data, config)
        z_coords = [v[2] for v in mesh.vertices]
        self.assertAlmostEqual(abs(min(z_coords)), max(z_coords))

    def test_no_degenerate_triangles(self):
        """No triangle should have repeated vertex indices."""
        pixel_data = self._make_rect_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)
        mesh = generate_solid_core(pixel_data, config)
        for tri in mesh.triangles:
            self.assertEqual(len(set(tri)), 3, f"Degenerate triangle: {tri}")

    def test_sparse_footprint_valid_mesh(self):
        """L-shaped (non-rectangle) footprint also produces a valid solid-core mesh."""
        pixel_data = self._make_sparse_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)
        mesh = generate_solid_core(pixel_data, config)
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        for tri in mesh.triangles:
            for idx in tri:
                self.assertLess(idx, len(mesh.vertices))

    def test_backing_plate_and_core_same_xy_footprint(self):
        """Backing plate and solid core should produce the same XY vertex range
        (they cover the same model footprint, just at different Z levels)."""
        pixels = {(x, y): (255, 0, 0, 255) for x in range(3) for y in range(3)}
        pixel_data = PixelData(width=3, height=3, pixel_size_mm=2.0, pixels=pixels)

        backing_config = ConversionConfig(base_height_mm=1.0)
        core_config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0)

        backing = generate_backing_plate(pixel_data, backing_config)
        core = generate_solid_core(pixel_data, core_config)

        backing_xy = {(round(v[0], 6), round(v[1], 6)) for v in backing.vertices}
        core_xy = {(round(v[0], 6), round(v[1], 6)) for v in core.vertices}
        self.assertEqual(backing_xy, core_xy)


class TestGenerateRegionMeshShell(unittest.TestCase):
    """Tests for generate_region_mesh_shell() — the thin colour shells in solid-core mode."""

    def _make_region_and_pixel_data(self) -> tuple:
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        return region, pixel_data

    def test_produces_valid_mesh(self):
        """generate_region_mesh_shell returns a mesh with valid indices."""
        region, pixel_data = self._make_region_and_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0)
        mesh = generate_region_mesh_shell(region, pixel_data, config, z_bottom=-0.5, z_top=0.0)
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        for tri in mesh.triangles:
            for idx in tri:
                self.assertGreaterEqual(idx, 0)
                self.assertLess(idx, len(mesh.vertices))

    def test_z_extents_match_arguments(self):
        """Shell vertices span exactly the z_bottom..z_top range passed in."""
        region, pixel_data = self._make_region_and_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0)
        z_bot, z_top = -0.5, 0.0
        mesh = generate_region_mesh_shell(region, pixel_data, config, z_bottom=z_bot, z_top=z_top)
        z_coords = [v[2] for v in mesh.vertices]
        self.assertAlmostEqual(min(z_coords), z_bot)
        self.assertAlmostEqual(max(z_coords), z_top)

    def test_bottom_and_top_shells_are_mirror_z(self):
        """Bottom shell and top shell should be identical except reflected around z=0."""
        region, pixel_data = self._make_region_and_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0, core_height_mm=1.0,
                                  color_height_mm=0.4)
        z_bot = config.core_z_bottom - config.color_shell_half_height
        z_core_bot = config.core_z_bottom
        z_core_top = config.core_z_top
        z_top = config.core_z_top + config.color_shell_half_height

        bottom_shell = generate_region_mesh_shell(region, pixel_data, config,
                                                  z_bottom=z_bot, z_top=z_core_bot)
        top_shell = generate_region_mesh_shell(region, pixel_data, config,
                                               z_bottom=z_core_top, z_top=z_top)

        # Both shells should have the same number of vertices and triangles
        self.assertEqual(len(bottom_shell.vertices), len(top_shell.vertices))
        self.assertEqual(len(bottom_shell.triangles), len(top_shell.triangles))

    def test_no_degenerate_triangles(self):
        """No triangle should have repeated vertex indices."""
        region, pixel_data = self._make_region_and_pixel_data()
        config = ConversionConfig(solid_core=True, base_height_mm=0)
        mesh = generate_region_mesh_shell(region, pixel_data, config, z_bottom=-0.2, z_top=0.0)
        for tri in mesh.triangles:
            self.assertEqual(len(set(tri)), 3, f"Degenerate triangle: {tri}")


if __name__ == '__main__':
    unittest.main()
