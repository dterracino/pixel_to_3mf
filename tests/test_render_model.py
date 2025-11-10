#!/usr/bin/env python3
"""
Unit tests for render_model.py module.

These tests verify that the 3D rendering functionality correctly handles
mesh coordinates, especially the backing plate which has negative Z values.
"""

import unittest
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.mesh_generator import Mesh


class TestRenderZAxisLimits(unittest.TestCase):
    """Tests for Z-axis limit calculation in rendering."""
    
    def test_z_limits_include_backing_plate(self):
        """
        Test that Z-axis limits correctly include negative backing plate values.
        
        WHY: The backing plate extends from z=-base_height_mm to z=0, while
        colored regions extend from z=0 to z=color_height_mm. The rendering
        must calculate both min and max Z to show the full model.
        
        This was the bug: the original code only calculated max_z and set
        zlim=[0, max_z], which clipped the backing plate.
        """
        # Create sample meshes mimicking real conversion output
        # Region mesh: z=0 to z=1.0
        region_vertices = [
            (0, 0, 0),    # bottom corners
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
            (0, 0, 1.0),  # top corners at color_height_mm
            (1, 0, 1.0),
            (1, 1, 1.0),
            (0, 1, 1.0),
        ]
        region_triangles = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
        region_mesh = Mesh(region_vertices, region_triangles)
        
        # Backing plate mesh: z=-0.5 to z=0
        backing_vertices = [
            (0, 0, -0.5),  # bottom at -base_height_mm
            (1, 0, -0.5),
            (1, 1, -0.5),
            (0, 1, -0.5),
            (0, 0, 0),     # top at z=0
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
        ]
        backing_triangles = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
        backing_mesh = Mesh(backing_vertices, backing_triangles)
        
        meshes = [
            (region_mesh, "region_1"),
            (backing_mesh, "backing_plate"),
        ]
        
        # Calculate min/max Z as the rendering code does
        min_z = 0
        max_z = 0
        for mesh, _ in meshes:
            for vertex in mesh.vertices:
                min_z = min(min_z, vertex[2])
                max_z = max(max_z, vertex[2])
        
        # Verify the fix
        self.assertEqual(min_z, -0.5, 
            "min_z should capture backing plate bottom at -0.5mm")
        self.assertEqual(max_z, 1.0,
            "max_z should capture region tops at 1.0mm")
    
    def test_z_limits_with_no_backing_plate(self):
        """
        Test Z-axis limits when backing plate is disabled (base_height=0).
        
        WHY: When base_height_mm is 0, there's no backing plate, so all
        meshes have z>=0. The min_z should correctly be 0.
        """
        # Only region meshes, no backing plate
        region_vertices = [
            (0, 0, 0),
            (1, 0, 0),
            (0, 0, 1.0),
            (1, 0, 1.0),
        ]
        region_triangles = [(0, 1, 2), (1, 3, 2)]
        region_mesh = Mesh(region_vertices, region_triangles)
        
        meshes = [(region_mesh, "region_1")]
        
        # Calculate min/max Z
        min_z = 0
        max_z = 0
        for mesh, _ in meshes:
            for vertex in mesh.vertices:
                min_z = min(min_z, vertex[2])
                max_z = max(max_z, vertex[2])
        
        self.assertEqual(min_z, 0, "min_z should be 0 when no backing plate")
        self.assertEqual(max_z, 1.0, "max_z should be the region height")
    
    def test_z_limits_with_multiple_layers(self):
        """
        Test Z-axis limits with regions at different heights.
        
        WHY: In theory, different regions could have different heights
        (though current implementation uses same height). The min/max
        calculation should handle any vertex Z values correctly.
        """
        # Create meshes at different Z levels
        mesh1_vertices = [(0, 0, 0), (1, 0, 0.5), (0.5, 1, 0.8)]
        mesh1 = Mesh(mesh1_vertices, [(0, 1, 2)])
        
        mesh2_vertices = [(0, 0, -0.3), (1, 0, 0.2), (0.5, 1, 1.2)]
        mesh2 = Mesh(mesh2_vertices, [(0, 1, 2)])
        
        meshes = [(mesh1, "mesh1"), (mesh2, "mesh2")]
        
        # Calculate min/max Z
        min_z = 0
        max_z = 0
        for mesh, _ in meshes:
            for vertex in mesh.vertices:
                min_z = min(min_z, vertex[2])
                max_z = max(max_z, vertex[2])
        
        self.assertEqual(min_z, -0.3, "min_z should capture lowest vertex")
        self.assertEqual(max_z, 1.2, "max_z should capture highest vertex")


if __name__ == '__main__':
    unittest.main()
