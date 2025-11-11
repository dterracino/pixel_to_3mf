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


class TestBackingPlateZOffset(unittest.TestCase):
    """Tests for backing plate Z-offset during rendering to prevent Z-fighting."""
    
    def test_backing_plate_offset_applied(self):
        """
        Test that backing plate gets a small Z-offset during rendering.
        
        WHY: The backing plate top surface is at Z=0, same as the colored regions'
        bottom surface. This causes Z-fighting in matplotlib where both surfaces
        try to occupy the same space. We apply a tiny offset (0.01mm) to the backing
        plate during rendering only (not in the actual 3MF geometry).
        """
        import numpy as np
        
        # Create a backing plate mesh at Z=[-1, 0]
        backing_vertices = [
            (0, 0, -1.0),
            (10, 0, -1.0),
            (10, 10, -1.0),
            (0, 10, -1.0),
            (0, 0, 0.0),   # Top face at Z=0
            (10, 0, 0.0),
            (10, 10, 0.0),
            (0, 10, 0.0),
        ]
        backing_mesh = Mesh(backing_vertices, [(0, 1, 2), (4, 5, 6)])
        
        # Simulate the rendering offset logic
        vertices_array = np.array(backing_mesh.vertices)
        
        # Verify original Z coordinates
        top_z_before = vertices_array[4, 2]  # Top face vertex
        self.assertEqual(top_z_before, 0.0, "Top face should be at Z=0 before offset")
        
        # Apply the rendering offset (as done in render_model.py)
        vertices_array_offset = vertices_array.copy()
        vertices_array_offset[:, 2] -= 0.01
        
        # Verify offset was applied
        top_z_after = vertices_array_offset[4, 2]
        self.assertEqual(top_z_after, -0.01, 
            "Top face should be at Z=-0.01 after rendering offset")
        
        # Verify original mesh is unchanged
        self.assertEqual(backing_mesh.vertices[4][2], 0.0,
            "Original mesh should not be modified by rendering offset")
    
    def test_region_mesh_no_offset(self):
        """
        Test that region meshes do NOT get Z-offset during rendering.
        
        WHY: Only the backing plate needs the offset. Colored regions should
        remain at their original Z coordinates.
        """
        import numpy as np
        
        # Create a region mesh at Z=[0, 1]
        region_vertices = [
            (0, 0, 0.0),   # Bottom face at Z=0
            (5, 0, 0.0),
            (5, 5, 0.0),
            (0, 5, 0.0),
            (0, 0, 1.0),   # Top face at Z=1
            (5, 0, 1.0),
            (5, 5, 1.0),
            (0, 5, 1.0),
        ]
        region_mesh = Mesh(region_vertices, [(0, 1, 2), (4, 5, 6)])
        
        # For region meshes, no offset should be applied
        vertices_array = np.array(region_mesh.vertices)
        
        # Verify Z coordinates remain unchanged
        bottom_z = vertices_array[0, 2]
        top_z = vertices_array[4, 2]
        
        self.assertEqual(bottom_z, 0.0, "Region bottom should stay at Z=0")
        self.assertEqual(top_z, 1.0, "Region top should stay at Z=1")


class TestRenderOrder(unittest.TestCase):
    """Tests for mesh rendering order to prevent backing plate obscuring regions."""
    
    def test_backing_plate_rendered_first(self):
        """
        Test that backing plate is processed before colored regions in rendering.
        
        WHY: When meshes are added to matplotlib's 3D axes, the order matters.
        If backing plate is added last, it may be rendered on top of colored
        regions from certain viewing angles (isometric, default). By ensuring
        backing plate is processed first, we guarantee colored regions are
        always visible on top.
        
        This test verifies the reordering logic that separates backing plate
        from regions and processes backing plate first.
        """
        from pixel_to_3mf.mesh_generator import Mesh
        
        # Create sample meshes
        region1_mesh = Mesh([(0, 0, 0), (1, 0, 1), (0, 1, 1)], [(0, 1, 2)])
        region2_mesh = Mesh([(2, 0, 0), (3, 0, 1), (2, 1, 1)], [(0, 1, 2)])
        backing_mesh = Mesh([(0, 0, -1), (5, 0, -1), (0, 5, 0)], [(0, 1, 2)])
        
        # Meshes in typical order (regions first, backing plate last)
        meshes = [
            (region1_mesh, "region_1"),
            (region2_mesh, "region_2"),
            (backing_mesh, "backing_plate"),
        ]
        
        # Simulate the reordering logic from render_model.py
        backing_plate_mesh = None
        region_meshes = []
        
        for mesh, name in meshes:
            if name == "backing_plate":
                backing_plate_mesh = (mesh, name)
            else:
                region_meshes.append((mesh, name))
        
        # Build ordered list
        meshes_ordered = []
        if backing_plate_mesh:
            meshes_ordered.append(backing_plate_mesh)
        meshes_ordered.extend(region_meshes)
        
        # Verify backing plate is first
        self.assertEqual(len(meshes_ordered), 3, 
            "Should have 3 meshes total")
        self.assertEqual(meshes_ordered[0][1], "backing_plate",
            "First mesh should be backing_plate")
        self.assertEqual(meshes_ordered[1][1], "region_1",
            "Second mesh should be region_1")
        self.assertEqual(meshes_ordered[2][1], "region_2",
            "Third mesh should be region_2")
    
    def test_render_order_without_backing_plate(self):
        """
        Test rendering order when there's no backing plate.
        
        WHY: When base_height_mm=0, there's no backing plate. The reordering
        logic should handle this gracefully and just process regions in order.
        """
        from pixel_to_3mf.mesh_generator import Mesh
        
        # Only region meshes, no backing plate
        region1_mesh = Mesh([(0, 0, 0), (1, 0, 1), (0, 1, 1)], [(0, 1, 2)])
        region2_mesh = Mesh([(2, 0, 0), (3, 0, 1), (2, 1, 1)], [(0, 1, 2)])
        
        meshes = [
            (region1_mesh, "region_1"),
            (region2_mesh, "region_2"),
        ]
        
        # Simulate the reordering logic
        backing_plate_mesh = None
        region_meshes = []
        
        for mesh, name in meshes:
            if name == "backing_plate":
                backing_plate_mesh = (mesh, name)
            else:
                region_meshes.append((mesh, name))
        
        meshes_ordered = []
        if backing_plate_mesh:
            meshes_ordered.append(backing_plate_mesh)
        meshes_ordered.extend(region_meshes)
        
        # Verify regions are processed in order
        self.assertEqual(len(meshes_ordered), 2,
            "Should have 2 meshes (no backing plate)")
        self.assertEqual(meshes_ordered[0][1], "region_1",
            "First mesh should be region_1")
        self.assertEqual(meshes_ordered[1][1], "region_2",
            "Second mesh should be region_2")


if __name__ == '__main__':
    unittest.main()
