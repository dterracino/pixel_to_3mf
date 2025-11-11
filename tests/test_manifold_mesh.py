"""
Tests for manifold mesh generation.

Ensures that generated meshes are always manifold regardless of connectivity mode.
A manifold mesh has every edge shared by exactly 2 triangles.
"""

import unittest
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.mesh_generator import generate_region_mesh, Mesh
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.config import ConversionConfig


def check_mesh_is_manifold(mesh: Mesh) -> tuple[bool, list[str]]:
    """
    Check if a mesh is manifold.
    
    A mesh is manifold if every edge is shared by exactly 2 triangles.
    
    Args:
        mesh: The mesh to check
    
    Returns:
        Tuple of (is_manifold, list_of_errors)
    """
    # Count how many triangles share each edge
    edge_count = defaultdict(int)
    
    for tri in mesh.triangles:
        v0, v1, v2 = tri
        # Create edges (sorted to be undirected)
        edges = [
            tuple(sorted([v0, v1])),
            tuple(sorted([v1, v2])),
            tuple(sorted([v2, v0]))
        ]
        for edge in edges:
            edge_count[edge] += 1
    
    # Check for non-manifold edges
    errors = []
    for edge, count in edge_count.items():
        if count != 2:
            v0, v1 = edge
            pos0 = mesh.vertices[v0]
            pos1 = mesh.vertices[v1]
            errors.append(
                f"Edge {edge} (from {pos0} to {pos1}) is used by {count} "
                f"triangles (should be 2)"
            )
    
    # Check for degenerate triangles
    for i, tri in enumerate(mesh.triangles):
        if len(set(tri)) != 3:
            errors.append(f"Triangle {i} is degenerate: {tri}")
    
    is_manifold = len(errors) == 0
    return is_manifold, errors


class TestManifoldMeshGeneration(unittest.TestCase):
    """Test that mesh generation always produces manifold meshes."""
    
    def test_single_pixel_is_manifold(self):
        """Test that a single pixel produces a manifold mesh."""
        region = Region(color=(255, 0, 0), pixels={(0, 0)})
        pixel_data = PixelData(
            width=2, height=2, pixel_size_mm=1.0,
            pixels={(0, 0): (255, 0, 0, 255)}
        )
        config = ConversionConfig()
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"Single pixel mesh should be manifold. Errors: {errors}"
        )
    
    def test_two_horizontal_pixels_manifold(self):
        """Test that two horizontally adjacent pixels produce a manifold mesh."""
        region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0)})
        pixel_data = PixelData(
            width=3, height=3, pixel_size_mm=1.0,
            pixels={(0, 0): (255, 0, 0, 255), (1, 0): (255, 0, 0, 255)}
        )
        config = ConversionConfig()
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"Horizontal pixels should be manifold. Errors: {errors}"
        )
    
    def test_two_vertical_pixels_manifold(self):
        """Test that two vertically adjacent pixels produce a manifold mesh."""
        region = Region(color=(255, 0, 0), pixels={(0, 0), (0, 1)})
        pixel_data = PixelData(
            width=3, height=3, pixel_size_mm=1.0,
            pixels={(0, 0): (255, 0, 0, 255), (0, 1): (255, 0, 0, 255)}
        )
        config = ConversionConfig()
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"Vertical pixels should be manifold. Errors: {errors}"
        )
    
    def test_diagonal_pixels_connectivity_8_manifold(self):
        """
        Test that two diagonally adjacent pixels in 8-connectivity mode
        produce a manifold mesh.
        
        This is the critical test case! In 8-connectivity, diagonal pixels
        are merged into one region. The mesh generator must handle this
        correctly to avoid non-manifold edges at the shared corner.
        """
        # Two pixels touching diagonally:
        #  X
        #   X
        region = Region(color=(255, 0, 0), pixels={(0, 1), (1, 0)})
        pixel_data = PixelData(
            width=3, height=3, pixel_size_mm=1.0,
            pixels={(0, 1): (255, 0, 0, 255), (1, 0): (255, 0, 0, 255)}
        )
        config = ConversionConfig(connectivity=8)
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"Diagonal pixels in 8-connectivity should be manifold. "
            f"Errors: {errors}"
        )
    
    def test_l_shape_connectivity_4_manifold(self):
        """Test L-shaped region with 4-connectivity."""
        region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0), (0, 1)})
        pixel_data = PixelData(
            width=3, height=3, pixel_size_mm=1.0,
            pixels={
                (0, 0): (255, 0, 0, 255),
                (1, 0): (255, 0, 0, 255),
                (0, 1): (255, 0, 0, 255)
            }
        )
        config = ConversionConfig(connectivity=4)
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"L-shape in 4-connectivity should be manifold. Errors: {errors}"
        )
    
    def test_l_shape_connectivity_8_manifold(self):
        """Test L-shaped region with 8-connectivity."""
        region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0), (0, 1)})
        pixel_data = PixelData(
            width=3, height=3, pixel_size_mm=1.0,
            pixels={
                (0, 0): (255, 0, 0, 255),
                (1, 0): (255, 0, 0, 255),
                (0, 1): (255, 0, 0, 255)
            }
        )
        config = ConversionConfig(connectivity=8)
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"L-shape in 8-connectivity should be manifold. Errors: {errors}"
        )
    
    def test_complex_diagonal_pattern_manifold(self):
        """
        Test a more complex pattern with multiple diagonal connections.
        
        Pattern:
          X
         X
        X
        """
        region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 1), (2, 2)})
        pixel_data = PixelData(
            width=4, height=4, pixel_size_mm=1.0,
            pixels={
                (0, 0): (255, 0, 0, 255),
                (1, 1): (255, 0, 0, 255),
                (2, 2): (255, 0, 0, 255)
            }
        )
        config = ConversionConfig(connectivity=8)
        
        mesh = generate_region_mesh(region, pixel_data, config)
        is_manifold, errors = check_mesh_is_manifold(mesh)
        
        self.assertTrue(
            is_manifold,
            f"Diagonal staircase should be manifold. Errors: {errors}"
        )


if __name__ == '__main__':
    unittest.main()
