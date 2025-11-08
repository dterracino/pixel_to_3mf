"""
Tests for diagonal connectivity handling in polygon optimization.

This test module verifies that regions with only diagonal connections
(8-connected but not 4-connected) are handled correctly by falling back
to the original mesh generation instead of attempting polygon optimization.

Background:
-----------
When using 8-connectivity for region merging, pixels that only touch at
corners (diagonally) are merged into the same region. However, when treated
as squares for polygon union, these pixels form disconnected polygon components
because squares only share vertices, not edges.

The fix:
--------
Before attempting polygon optimization, check if all pixels in the region
are 4-connected (edge-sharing). If not, fall back to the original per-pixel
mesh generation to avoid MultiPolygon errors.
"""

import unittest
from pixel_to_3mf.polygon_optimizer import (
    generate_region_mesh_optimized,
    _is_4_connected
)
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.config import ConversionConfig


class TestDiagonalConnectivityDetection(unittest.TestCase):
    """Test the _is_4_connected helper function."""
    
    def test_diagonal_only_connection_detected(self):
        """Two pixels touching only diagonally should return False."""
        pixels = {(0, 0), (1, 1)}
        self.assertFalse(_is_4_connected(pixels))
    
    def test_edge_connection_detected(self):
        """Two pixels sharing an edge should return True."""
        # Horizontal edge
        pixels_h = {(0, 0), (1, 0)}
        self.assertTrue(_is_4_connected(pixels_h))
        
        # Vertical edge
        pixels_v = {(0, 0), (0, 1)}
        self.assertTrue(_is_4_connected(pixels_v))
    
    def test_mixed_connectivity(self):
        """Region with both edge and diagonal connections."""
        # Three pixels in a row, then one diagonal
        # ███X
        # (0,0), (1,0), (2,0), (3,1) - last one only diagonal
        pixels = {(0, 0), (1, 0), (2, 0), (3, 1)}
        self.assertFalse(_is_4_connected(pixels))
    
    def test_l_shape_all_connected(self):
        """L-shape with all edge connections should return True."""
        # ███
        # █
        # █
        pixels = {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}
        self.assertTrue(_is_4_connected(pixels))
    
    def test_empty_set(self):
        """Empty pixel set should return True (vacuously true)."""
        pixels = set()
        self.assertTrue(_is_4_connected(pixels))
    
    def test_single_pixel(self):
        """Single pixel should return True."""
        pixels = {(0, 0)}
        self.assertTrue(_is_4_connected(pixels))
    
    def test_multiple_diagonal_connections(self):
        """Chain of diagonal connections should return False."""
        # Staircase pattern:
        # █
        #  █
        #   █
        pixels = {(0, 0), (1, 1), (2, 2)}
        self.assertFalse(_is_4_connected(pixels))


class TestDiagonalRegionFallback(unittest.TestCase):
    """Test that diagonal-only regions fall back gracefully."""
    
    def test_diagonal_region_no_error(self):
        """Region with diagonal-only connections should not raise exception."""
        # Two diagonally connected pixels
        pixels = {(0, 0), (1, 1)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Should fall back to original implementation without error
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Verify mesh was created
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_edge_connected_uses_optimization(self):
        """Region with edge connections should use optimization."""
        # 2x2 square (all edge-connected)
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Should use optimization
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Verify mesh exists
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        
        # Optimized mesh should have fewer vertices than per-pixel approach
        # Per-pixel creates a 3x3 grid of vertices on top and bottom (18 total)
        # Optimized triangulates the square with ~8-12 vertices
        self.assertLess(len(mesh.vertices), 18)
    
    def test_complex_diagonal_pattern(self):
        """Complex pattern with diagonal connections should fall back."""
        # Create a pattern like:
        # █ █
        #  █
        # █ █
        # This has edge connections in the middle but diagonal corners
        pixels = {(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)}
        region = Region(color=(0, 255, 0), pixels=pixels)
        pixel_dict = {p: (0, 255, 0, 255) for p in pixels}
        pixel_data = PixelData(width=3, height=3, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Should fall back gracefully
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Verify mesh was created
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)


class TestRealWorldDiagonalPatterns(unittest.TestCase):
    """Test patterns that occur in real pixel art."""
    
    def test_diagonal_line(self):
        """Diagonal line pattern (common in pixel art)."""
        # Create a diagonal line:
        # █
        #  █
        #   █
        #    █
        pixels = {(0, 0), (1, 1), (2, 2), (3, 3)}
        region = Region(color=(255, 255, 0), pixels=pixels)
        pixel_dict = {p: (255, 255, 0, 255) for p in pixels}
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Should handle gracefully
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
    
    def test_checkerboard_corner(self):
        """Checkerboard pattern (diagonal only)."""
        # █ █
        #  █ █
        pixels = {(0, 0), (2, 0), (1, 1), (3, 1)}
        region = Region(color=(128, 128, 128), pixels=pixels)
        pixel_dict = {p: (128, 128, 128, 255) for p in pixels}
        pixel_data = PixelData(width=4, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Should fall back (no edge connections)
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)


if __name__ == '__main__':
    unittest.main()
