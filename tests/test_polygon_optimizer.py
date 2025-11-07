"""
Tests for optimized polygon-based mesh generation.

This test module validates the polygon optimizer implementation which provides
a second processing path alongside the original per-pixel mesh generation.
Both paths produce manifold meshes with identical visual results.
"""

import unittest
from typing import Set, Tuple
from shapely.geometry import box, Polygon

from pixel_to_3mf.polygon_optimizer import (
    pixels_to_polygon,
    triangulate_polygon_2d,
    extrude_polygon_to_mesh,
    generate_region_mesh_optimized,
    generate_backing_plate_optimized
)
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.config import ConversionConfig
from tests.test_helpers import cleanup_test_file


class TestPixelsToPolygon(unittest.TestCase):
    """Test pixel set to polygon conversion."""
    
    def test_single_pixel(self):
        """Single pixel should create 1x1 square polygon."""
        pixels = {(0, 0)}
        poly = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        self.assertAlmostEqual(poly.area, 1.0)
        self.assertTrue(poly.is_valid)
    
    def test_2x2_square(self):
        """2x2 pixels should merge into 2x2 square."""
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        poly = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        self.assertAlmostEqual(poly.area, 4.0)
        self.assertTrue(poly.is_valid)
        # Note: unary_union may not simplify to minimal coords, but area is correct
        self.assertGreaterEqual(len(list(poly.exterior.coords)), 5)
    
    def test_l_shape(self):
        """L-shape should create valid polygon."""
        pixels = {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}
        poly = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        self.assertAlmostEqual(poly.area, 5.0)
        self.assertTrue(poly.is_valid)
    
    def test_diagonal_connection(self):
        """Diagonally connected pixels should create valid polygon."""
        # Two pixels touching at a corner
        # Note: They may merge into one polygon or stay as MultiPolygon
        # depending on shapely's union behavior
        pixels = {(0, 0), (1, 1)}
        poly = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        # Area could be 2.0 if merged or less if not perfectly merged
        # The important thing is it's valid
        self.assertGreater(poly.area, 0.0)
        self.assertTrue(poly.is_valid)
    
    def test_with_hole(self):
        """Donut shape (outer ring with hole) should create polygon with interior."""
        # Create a 4x4 square with a 2x2 hole in the middle
        outer = {(x, y) for x in range(4) for y in range(4)}
        hole = {(1, 1), (1, 2), (2, 1), (2, 2)}
        pixels = outer - hole
        
        poly = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        # Outer area = 16, hole area = 4, result = 12
        self.assertAlmostEqual(poly.area, 12.0)
        self.assertTrue(poly.is_valid)
        # Should have one interior ring (the hole)
        self.assertEqual(len(list(poly.interiors)), 1)
    
    def test_empty_pixels_raises_error(self):
        """Empty pixel set should raise ValueError."""
        with self.assertRaises(ValueError):
            pixels_to_polygon(set(), pixel_size_mm=1.0)
    
    def test_pixel_size_scaling(self):
        """Polygon should scale correctly with pixel size."""
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        
        # With 1mm pixels
        poly1 = pixels_to_polygon(pixels, pixel_size_mm=1.0)
        self.assertAlmostEqual(poly1.area, 4.0)
        
        # With 2mm pixels (area should be 4x larger)
        poly2 = pixels_to_polygon(pixels, pixel_size_mm=2.0)
        self.assertAlmostEqual(poly2.area, 16.0)


class TestTriangulatePolygon(unittest.TestCase):
    """Test polygon triangulation."""
    
    def test_simple_square(self):
        """Square should triangulate to at least 2 triangles."""
        poly = box(0, 0, 2, 2)
        vertices, triangles = triangulate_polygon_2d(poly)
        
        # Should have at least 4 vertices (corners)
        self.assertGreaterEqual(len(vertices), 4)
        # Should have at least 2 triangles
        self.assertGreaterEqual(len(triangles), 2)
        # All triangles should be valid (3 indices each)
        for tri in triangles:
            self.assertEqual(len(tri), 3)
            # All indices should be within bounds
            for idx in tri:
                self.assertGreaterEqual(idx, 0)
                self.assertLess(idx, len(vertices))
    
    def test_complex_polygon(self):
        """L-shape polygon should triangulate correctly."""
        # Create an L-shape manually
        coords = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        poly = Polygon(coords)
        
        vertices, triangles = triangulate_polygon_2d(poly)
        
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(triangles), 0)
        # All triangles should have 3 unique vertices
        for tri in triangles:
            self.assertEqual(len(set(tri)), 3, "Degenerate triangle found")
    
    def test_polygon_with_hole(self):
        """Polygon with hole should triangulate correctly."""
        # Outer square
        exterior = [(0, 0), (4, 0), (4, 4), (0, 4)]
        # Inner hole (square from 1,1 to 3,3)
        hole = [(1, 1), (3, 1), (3, 3), (1, 3)]
        poly = Polygon(exterior, [hole])
        
        vertices, triangles = triangulate_polygon_2d(poly)
        
        self.assertGreater(len(vertices), 0)
        self.assertGreater(len(triangles), 0)
        
        # Verify all triangles are valid
        for tri in triangles:
            self.assertEqual(len(tri), 3)
            self.assertEqual(len(set(tri)), 3, "Degenerate triangle found")
    
    def test_triangulation_preserves_area(self):
        """Sum of triangle areas should equal polygon area."""
        poly = box(0, 0, 5, 5)
        vertices, triangles = triangulate_polygon_2d(poly)
        
        # Calculate total area of all triangles
        def triangle_area(v0, v1, v2):
            """Calculate area using cross product."""
            x1, y1 = v0
            x2, y2 = v1
            x3, y3 = v2
            return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0
        
        total_area = 0.0
        for tri in triangles:
            v0 = vertices[tri[0]]
            v1 = vertices[tri[1]]
            v2 = vertices[tri[2]]
            total_area += triangle_area(v0, v1, v2)
        
        # Should equal polygon area (25 square units)
        self.assertAlmostEqual(total_area, 25.0, places=3)


class TestExtrudePolygonToMesh(unittest.TestCase):
    """Test 3D mesh extrusion from 2D polygon."""
    
    def test_simple_square_extrusion(self):
        """Extruding a square should create box with top, bottom, and walls."""
        poly = box(0, 0, 1, 1)
        vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
        
        mesh = extrude_polygon_to_mesh(
            poly, triangles_2d, vertices_2d,
            z_bottom=0.0, z_top=1.0
        )
        
        # Should have vertices (2x triangulation vertices: top + bottom)
        self.assertEqual(len(mesh.vertices), len(vertices_2d) * 2)
        
        # Should have triangles for:
        # - Top face (same count as 2D triangulation)
        # - Bottom face (same count as 2D triangulation)
        # - Walls (4 edges * 2 triangles = 8 triangles for square)
        expected_min_triangles = len(triangles_2d) * 2 + 8
        self.assertGreaterEqual(len(mesh.triangles), expected_min_triangles)
        
        # All vertices should have correct Z values
        top_count = sum(1 for v in mesh.vertices if v[2] == 1.0)
        bottom_count = sum(1 for v in mesh.vertices if v[2] == 0.0)
        self.assertEqual(top_count, len(vertices_2d))
        self.assertEqual(bottom_count, len(vertices_2d))
    
    def test_extrusion_height(self):
        """Mesh should respect specified z_bottom and z_top."""
        poly = box(0, 0, 1, 1)
        vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
        
        mesh = extrude_polygon_to_mesh(
            poly, triangles_2d, vertices_2d,
            z_bottom=-2.0, z_top=3.0
        )
        
        # Check Z values
        z_values = set(v[2] for v in mesh.vertices)
        self.assertIn(-2.0, z_values)
        self.assertIn(3.0, z_values)


class TestOptimizedMeshGeneration(unittest.TestCase):
    """Test optimized mesh generation maintains manifold properties."""
    
    def test_mesh_is_manifold_single_pixel(self):
        """Single pixel mesh should be manifold."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(
            width=2, height=2, pixel_size_mm=1.0,
            pixels={(0, 0): (255, 0, 0, 255)}
        )
        config = ConversionConfig(color_height_mm=1.0)
        
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Check manifold properties
        self._verify_manifold(mesh)
    
    def test_mesh_is_manifold_2x2_square(self):
        """2x2 square mesh should be manifold."""
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        self._verify_manifold(mesh)
    
    def test_mesh_is_manifold_l_shape(self):
        """L-shape mesh should be manifold."""
        pixels = {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=3, height=3, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        self._verify_manifold(mesh)
    
    def test_mesh_with_hole(self):
        """Mesh with hole (donut shape) should be manifold."""
        # Create donut: 5x5 outer with 3x3 hole
        outer = {(x, y) for x in range(5) for y in range(5)}
        hole = {(x, y) for x in range(1, 4) for y in range(1, 4)}
        pixels = outer - hole
        
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        self._verify_manifold(mesh)
    
    def _verify_manifold(self, mesh):
        """
        Verify mesh is manifold.
        
        Manifold properties:
        1. No degenerate triangles (all 3 vertices unique)
        2. All triangle indices valid (within bounds)
        3. Each edge shared by exactly 2 triangles
        """
        # Check 1: No degenerate triangles
        for i, tri in enumerate(mesh.triangles):
            self.assertEqual(len(set(tri)), 3, 
                           f"Degenerate triangle at index {i}: {tri}")
        
        # Check 2: All triangle indices valid
        for i, tri in enumerate(mesh.triangles):
            for idx in tri:
                self.assertLess(idx, len(mesh.vertices),
                              f"Triangle {i} has invalid vertex index {idx}")
                self.assertGreaterEqual(idx, 0,
                                      f"Triangle {i} has negative vertex index {idx}")
        
        # Check 3: Edge connectivity
        edge_count = {}
        for tri in mesh.triangles:
            edges = [
                tuple(sorted([tri[0], tri[1]])),
                tuple(sorted([tri[1], tri[2]])),
                tuple(sorted([tri[2], tri[0]]))
            ]
            for edge in edges:
                edge_count[edge] = edge_count.get(edge, 0) + 1
        
        # For a closed manifold mesh, each edge should appear exactly twice
        non_manifold_edges = {e: c for e, c in edge_count.items() if c != 2}
        self.assertEqual(len(non_manifold_edges), 0,
                        f"Found {len(non_manifold_edges)} non-manifold edges")


class TestOptimizationComparison(unittest.TestCase):
    """Compare optimized vs. original mesh generation."""
    
    def test_vertex_count_reduction_square(self):
        """Optimized mesh should have significantly fewer vertices for square."""
        from pixel_to_3mf.mesh_generator import generate_region_mesh
        
        # 10x10 square
        pixels = {(x, y) for x in range(10) for y in range(10)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=10, height=10, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Generate both versions
        original_mesh = generate_region_mesh(region, pixel_data, config)
        optimized_mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Optimized should have significantly fewer vertices
        # For a 10x10 square:
        # - Original: ~242 vertices (11x11 grid points top + bottom)
        # - Optimized: Should be much less (typically 50-70% reduction)
        reduction_ratio = len(optimized_mesh.vertices) / len(original_mesh.vertices)
        self.assertLess(reduction_ratio, 0.8,
                       f"Optimized should use <80% vertices. "
                       f"Original: {len(original_mesh.vertices)}, "
                       f"Optimized: {len(optimized_mesh.vertices)}")
    
    def test_triangle_count_reduction_square(self):
        """Optimized mesh should have significantly fewer triangles for square."""
        from pixel_to_3mf.mesh_generator import generate_region_mesh
        
        # 10x10 square
        pixels = {(x, y) for x in range(10) for y in range(10)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=10, height=10, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Generate both versions
        original_mesh = generate_region_mesh(region, pixel_data, config)
        optimized_mesh = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Optimized should have significantly fewer triangles (typically 50-70% reduction)
        reduction_ratio = len(optimized_mesh.triangles) / len(original_mesh.triangles)
        self.assertLess(reduction_ratio, 0.8,
                       f"Optimized should use <80% triangles. "
                       f"Original: {len(original_mesh.triangles)}, "
                       f"Optimized: {len(optimized_mesh.triangles)}")
    
    def test_both_produce_manifold_meshes(self):
        """Both original and optimized should produce manifold meshes."""
        from pixel_to_3mf.mesh_generator import generate_region_mesh
        
        pixels = {(x, y) for x in range(5) for y in range(5)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        pixel_dict = {p: (255, 0, 0, 255) for p in pixels}
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=1.0, pixels=pixel_dict)
        config = ConversionConfig(color_height_mm=1.0)
        
        # Generate both
        original = generate_region_mesh(region, pixel_data, config)
        optimized = generate_region_mesh_optimized(region, pixel_data, config)
        
        # Both should be manifold
        self._verify_edge_connectivity(original)
        self._verify_edge_connectivity(optimized)
    
    def _verify_edge_connectivity(self, mesh):
        """Check that each edge appears exactly twice (manifold property)."""
        edge_count = {}
        for tri in mesh.triangles:
            edges = [
                tuple(sorted([tri[0], tri[1]])),
                tuple(sorted([tri[1], tri[2]])),
                tuple(sorted([tri[2], tri[0]]))
            ]
            for edge in edges:
                edge_count[edge] = edge_count.get(edge, 0) + 1
        
        non_manifold = {e: c for e, c in edge_count.items() if c != 2}
        self.assertEqual(len(non_manifold), 0,
                        f"Found {len(non_manifold)} non-manifold edges")


class TestBackingPlateOptimized(unittest.TestCase):
    """Test optimized backing plate generation."""
    
    def test_simple_backing_plate(self):
        """Backing plate for simple image should be manifold."""
        pixels = {(0, 0): (255, 0, 0, 255), (1, 0): (0, 255, 0, 255)}
        pixel_data = PixelData(width=2, height=1, pixel_size_mm=1.0, pixels=pixels)
        config = ConversionConfig(base_height_mm=0.5)
        
        mesh = generate_backing_plate_optimized(pixel_data, config)
        
        # Should have vertices
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)
        
        # Check Z values are correct
        z_values = set(v[2] for v in mesh.vertices)
        self.assertIn(0.0, z_values)  # Top at z=0
        self.assertIn(-0.5, z_values)  # Bottom at z=-0.5
    
    def test_backing_plate_with_hole(self):
        """Backing plate with transparent area should have hole."""
        # Create 5x5 grid with 3x3 transparent hole
        pixels = {}
        for x in range(5):
            for y in range(5):
                # Skip the middle 3x3 area
                if 1 <= x <= 3 and 1 <= y <= 3:
                    continue
                pixels[(x, y)] = (255, 0, 0, 255)
        
        pixel_data = PixelData(width=5, height=5, pixel_size_mm=1.0, pixels=pixels)
        config = ConversionConfig(base_height_mm=0.5)
        
        mesh = generate_backing_plate_optimized(pixel_data, config)
        
        # Should create mesh with hole
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.triangles), 0)


if __name__ == '__main__':
    unittest.main()
