"""
Unit tests for the threemf_core module.

Tests the generic 3MF file writer, dataclasses, and utility functions.
These tests focus on the reusable 3MF writing infrastructure that is
independent of the pixel-art-specific layer.
"""

import unittest
import sys
import os
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.threemf_core import (
    ThreeMFWriter, ThreeMFMesh, ThreeMFObject,
    format_float, count_mesh_stats, validate_triangle_winding,
    calculate_model_bounds, calculate_model_center, create_centering_transform,
    prettify_xml
)
from tests.helpers import validate_3mf_structure


# ============================================================================
# Test Fixtures
# ============================================================================

def create_simple_mesh() -> ThreeMFMesh:
    """Create a simple triangle mesh for testing."""
    return ThreeMFMesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
        metadata={'color_name': 'Red', 'color_rgb': (255, 0, 0)}
    )


def create_square_mesh() -> ThreeMFMesh:
    """Create a square mesh (2 triangles) for testing."""
    return ThreeMFMesh(
        vertices=[
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)
        ],
        triangles=[(0, 1, 2), (0, 2, 3)],
        metadata={'name': 'Square'}
    )


def create_cube_mesh() -> ThreeMFMesh:
    """
    Create a cube mesh for testing manifold properties.
    
    The cube has 8 vertices and 12 triangles (2 per face, 6 faces).
    All triangles use CCW winding for outward-facing normals.
    """
    vertices = [
        (0.0, 0.0, 0.0),  # 0: front-bottom-left
        (1.0, 0.0, 0.0),  # 1: front-bottom-right
        (1.0, 1.0, 0.0),  # 2: front-top-right
        (0.0, 1.0, 0.0),  # 3: front-top-left
        (0.0, 0.0, 1.0),  # 4: back-bottom-left
        (1.0, 0.0, 1.0),  # 5: back-bottom-right
        (1.0, 1.0, 1.0),  # 6: back-top-right
        (0.0, 1.0, 1.0),  # 7: back-top-left
    ]
    
    triangles = [
        # Front face (z=0) - normal pointing -Z
        (0, 2, 1), (0, 3, 2),
        # Back face (z=1) - normal pointing +Z
        (4, 5, 6), (4, 6, 7),
        # Bottom face (y=0) - normal pointing -Y
        (0, 1, 5), (0, 5, 4),
        # Top face (y=1) - normal pointing +Y (CCW from above)
        (3, 6, 2), (3, 7, 6),
        # Left face (x=0) - normal pointing -X
        (0, 4, 7), (0, 7, 3),
        # Right face (x=1) - normal pointing +X
        (1, 2, 6), (1, 6, 5),
    ]
    
    return ThreeMFMesh(vertices=vertices, triangles=triangles, metadata={'name': 'Cube'})


def create_empty_mesh() -> ThreeMFMesh:
    """Create an empty mesh for edge case testing."""
    return ThreeMFMesh(vertices=[], triangles=[], metadata={})


# ============================================================================
# Test Classes
# ============================================================================

class TestFormatFloat(unittest.TestCase):
    """Test float formatting for 3MF files."""
    
    def test_format_integer_value(self):
        """Test formatting a whole number removes trailing zeros."""
        result = format_float(2.0)
        self.assertEqual(result, "2")
    
    def test_format_decimal_value(self):
        """Test formatting a decimal value."""
        result = format_float(2.5)
        self.assertEqual(result, "2.5")
    
    def test_format_strips_trailing_zeros(self):
        """Test that trailing zeros are removed."""
        result = format_float(2.500, precision=3)
        self.assertEqual(result, "2.5")
    
    def test_format_with_custom_precision(self):
        """Test formatting with specified precision."""
        result = format_float(3.14159, precision=2)
        self.assertEqual(result, "3.14")
    
    def test_format_very_small_number(self):
        """Test formatting very small numbers preserves precision."""
        result = format_float(0.001, precision=3)
        self.assertEqual(result, "0.001")
    
    def test_format_negative_number(self):
        """Test formatting negative numbers."""
        result = format_float(-1.5, precision=2)
        self.assertEqual(result, "-1.5")
    
    def test_format_zero(self):
        """Test formatting zero."""
        result = format_float(0.0)
        self.assertEqual(result, "0")
    
    def test_format_large_number(self):
        """Test formatting large numbers."""
        result = format_float(12345.678, precision=2)
        self.assertEqual(result, "12345.68")


class TestThreeMFMesh(unittest.TestCase):
    """Test ThreeMFMesh dataclass."""
    
    def test_create_mesh_with_all_fields(self):
        """Test creating a mesh with all required fields."""
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)],
            triangles=[(0, 1, 2)],
            metadata={'key': 'value'}
        )
        
        self.assertEqual(len(mesh.vertices), 3)
        self.assertEqual(len(mesh.triangles), 1)
        self.assertEqual(mesh.metadata['key'], 'value')
    
    def test_mesh_stores_vertices_correctly(self):
        """Test that vertex coordinates are stored correctly."""
        vertices = [(1.5, 2.5, 3.5), (4.0, 5.0, 6.0)]
        mesh = ThreeMFMesh(vertices=vertices, triangles=[], metadata={})
        
        self.assertEqual(mesh.vertices[0], (1.5, 2.5, 3.5))
        self.assertEqual(mesh.vertices[1], (4.0, 5.0, 6.0))
    
    def test_mesh_stores_triangles_correctly(self):
        """Test that triangle indices are stored correctly."""
        triangles = [(0, 1, 2), (2, 3, 0)]
        mesh = ThreeMFMesh(vertices=[], triangles=triangles, metadata={})
        
        self.assertEqual(mesh.triangles[0], (0, 1, 2))
        self.assertEqual(mesh.triangles[1], (2, 3, 0))
    
    def test_mesh_empty_metadata(self):
        """Test mesh with empty metadata dictionary."""
        mesh = ThreeMFMesh(vertices=[], triangles=[], metadata={})
        self.assertEqual(mesh.metadata, {})


class TestThreeMFObject(unittest.TestCase):
    """Test ThreeMFObject dataclass."""
    
    def test_create_object_with_all_fields(self):
        """Test creating an object with all required fields."""
        mesh = create_simple_mesh()
        obj = ThreeMFObject(
            object_id=1,
            name="Test Object",
            extruder_slot=2,
            transform=(10.0, 20.0, 30.0),
            mesh=mesh
        )
        
        self.assertEqual(obj.object_id, 1)
        self.assertEqual(obj.name, "Test Object")
        self.assertEqual(obj.extruder_slot, 2)
        self.assertEqual(obj.transform, (10.0, 20.0, 30.0))
        self.assertIs(obj.mesh, mesh)
    
    def test_object_stores_transform_correctly(self):
        """Test that transform coordinates are stored correctly."""
        mesh = create_simple_mesh()
        obj = ThreeMFObject(
            object_id=1,
            name="Test",
            extruder_slot=1,
            transform=(-5.5, 10.25, 0.0),
            mesh=mesh
        )
        
        self.assertEqual(obj.transform[0], -5.5)
        self.assertEqual(obj.transform[1], 10.25)
        self.assertEqual(obj.transform[2], 0.0)


class TestCountMeshStats(unittest.TestCase):
    """Test count_mesh_stats function."""
    
    def test_single_mesh_stats(self):
        """Test counting stats for a single mesh."""
        mesh = create_simple_mesh()  # 3 vertices, 1 triangle
        
        vertices, triangles = count_mesh_stats([mesh])
        
        self.assertEqual(vertices, 3)
        self.assertEqual(triangles, 1)
    
    def test_multiple_meshes_stats(self):
        """Test counting stats for multiple meshes."""
        mesh1 = create_simple_mesh()  # 3 vertices, 1 triangle
        mesh2 = create_square_mesh()  # 4 vertices, 2 triangles
        
        vertices, triangles = count_mesh_stats([mesh1, mesh2])
        
        self.assertEqual(vertices, 7)  # 3 + 4
        self.assertEqual(triangles, 3)  # 1 + 2
    
    def test_empty_meshes_list(self):
        """Test counting stats for empty list."""
        vertices, triangles = count_mesh_stats([])
        
        self.assertEqual(vertices, 0)
        self.assertEqual(triangles, 0)
    
    def test_mesh_with_no_geometry(self):
        """Test counting stats for mesh with no vertices or triangles."""
        mesh = create_empty_mesh()
        
        vertices, triangles = count_mesh_stats([mesh])
        
        self.assertEqual(vertices, 0)
        self.assertEqual(triangles, 0)


class TestValidateTriangleWinding(unittest.TestCase):
    """Test validate_triangle_winding function."""
    
    def test_empty_mesh_returns_unknown(self):
        """Test that empty mesh returns UNKNOWN."""
        mesh = create_empty_mesh()
        result = validate_triangle_winding(mesh)
        self.assertEqual(result, "UNKNOWN")
    
    def test_ccw_top_surface_returns_ccw(self):
        """Test that CCW winding on top surface is detected correctly."""
        # Create a flat triangle on the XY plane at Z=1
        # CCW winding: (0,0,1) -> (1,0,1) -> (1,1,1) gives +Z normal
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0)],
            triangles=[(0, 1, 2)],
            metadata={}
        )
        
        result = validate_triangle_winding(mesh)
        self.assertEqual(result, "CCW")
    
    def test_cw_top_surface_returns_cw(self):
        """Test that CW winding on top surface is detected correctly."""
        # CW winding: (0,0,1) -> (1,1,1) -> (1,0,1) gives -Z normal
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 1.0), (1.0, 1.0, 1.0), (1.0, 0.0, 1.0)],
            triangles=[(0, 1, 2)],
            metadata={}
        )
        
        result = validate_triangle_winding(mesh)
        self.assertEqual(result, "CW")
    
    def test_cube_mesh_winding(self):
        """Test winding detection for a full cube mesh."""
        mesh = create_cube_mesh()
        result = validate_triangle_winding(mesh)
        # The cube is constructed with CCW winding on top face
        self.assertEqual(result, "CCW")


class TestCalculateModelBounds(unittest.TestCase):
    """Test calculate_model_bounds function."""
    
    def test_single_mesh_bounds(self):
        """Test calculating bounds for a single mesh."""
        mesh = create_simple_mesh()  # Triangle at (0,0,0), (1,0,0), (0.5,1,0)
        
        min_x, max_x, min_y, max_y, min_z, max_z = calculate_model_bounds([mesh])
        
        self.assertEqual(min_x, 0.0)
        self.assertEqual(max_x, 1.0)
        self.assertEqual(min_y, 0.0)
        self.assertEqual(max_y, 1.0)
        self.assertEqual(min_z, 0.0)
        self.assertEqual(max_z, 0.0)
    
    def test_multiple_meshes_bounds(self):
        """Test calculating bounds for multiple meshes."""
        mesh1 = ThreeMFMesh(
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            triangles=[],
            metadata={}
        )
        mesh2 = ThreeMFMesh(
            vertices=[(2.0, 3.0, 4.0), (5.0, 6.0, 7.0)],
            triangles=[],
            metadata={}
        )
        
        min_x, max_x, min_y, max_y, min_z, max_z = calculate_model_bounds([mesh1, mesh2])
        
        self.assertEqual(min_x, 0.0)
        self.assertEqual(max_x, 5.0)
        self.assertEqual(min_y, 0.0)
        self.assertEqual(max_y, 6.0)
        self.assertEqual(min_z, 0.0)
        self.assertEqual(max_z, 7.0)
    
    def test_empty_meshes_list_returns_zeros(self):
        """Test that empty mesh list returns all zeros."""
        bounds = calculate_model_bounds([])
        self.assertEqual(bounds, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    
    def test_mesh_with_no_vertices_returns_zeros(self):
        """Test that mesh with no vertices returns zeros."""
        mesh = create_empty_mesh()
        bounds = calculate_model_bounds([mesh])
        self.assertEqual(bounds, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    
    def test_negative_coordinates(self):
        """Test bounds calculation with negative coordinates."""
        mesh = ThreeMFMesh(
            vertices=[(-5.0, -3.0, -2.0), (5.0, 3.0, 2.0)],
            triangles=[],
            metadata={}
        )
        
        min_x, max_x, min_y, max_y, min_z, max_z = calculate_model_bounds([mesh])
        
        self.assertEqual(min_x, -5.0)
        self.assertEqual(max_x, 5.0)
        self.assertEqual(min_y, -3.0)
        self.assertEqual(max_y, 3.0)
        self.assertEqual(min_z, -2.0)
        self.assertEqual(max_z, 2.0)


class TestCalculateModelCenter(unittest.TestCase):
    """Test calculate_model_center function."""
    
    def test_center_of_simple_mesh(self):
        """Test calculating center of a simple mesh."""
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 0.0), (10.0, 20.0, 0.0)],
            triangles=[],
            metadata={}
        )
        
        center_x, center_y = calculate_model_center([mesh])
        
        self.assertEqual(center_x, 5.0)
        self.assertEqual(center_y, 10.0)
    
    def test_center_of_symmetric_mesh(self):
        """Test center calculation for symmetric mesh."""
        mesh = ThreeMFMesh(
            vertices=[
                (-5.0, -5.0, 0.0), (5.0, -5.0, 0.0),
                (5.0, 5.0, 0.0), (-5.0, 5.0, 0.0)
            ],
            triangles=[],
            metadata={}
        )
        
        center_x, center_y = calculate_model_center([mesh])
        
        self.assertEqual(center_x, 0.0)
        self.assertEqual(center_y, 0.0)
    
    def test_empty_meshes_returns_zero_center(self):
        """Test that empty mesh list returns (0, 0)."""
        center_x, center_y = calculate_model_center([])
        self.assertEqual(center_x, 0.0)
        self.assertEqual(center_y, 0.0)


class TestCreateCenteringTransform(unittest.TestCase):
    """Test create_centering_transform function."""
    
    def test_centering_transform_for_simple_mesh(self):
        """Test creating centering transform for a simple mesh."""
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 0.0), (10.0, 20.0, 0.0)],
            triangles=[],
            metadata={}
        )
        
        tx, ty, tz = create_centering_transform([mesh])
        
        self.assertEqual(tx, 5.0)
        self.assertEqual(ty, 10.0)
        self.assertEqual(tz, 0.0)
    
    def test_centering_transform_with_z_offset(self):
        """Test centering transform with custom z_offset."""
        mesh = ThreeMFMesh(
            vertices=[(0.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
            triangles=[],
            metadata={}
        )
        
        tx, ty, tz = create_centering_transform([mesh], z_offset=5.0)
        
        self.assertEqual(tx, 5.0)
        self.assertEqual(ty, 5.0)
        self.assertEqual(tz, 5.0)
    
    def test_empty_meshes_returns_zero_transform(self):
        """Test that empty mesh list returns (0, 0, 0)."""
        tx, ty, tz = create_centering_transform([])
        self.assertEqual(tx, 0.0)
        self.assertEqual(ty, 0.0)
        self.assertEqual(tz, 0.0)


class TestPrettifyXml(unittest.TestCase):
    """Test prettify_xml function."""
    
    def test_returns_valid_xml_string(self):
        """Test that prettify_xml returns a valid XML string."""
        elem = ET.Element("root")
        ET.SubElement(elem, "child", name="test")
        
        result = prettify_xml(elem)
        
        # Should contain XML declaration
        self.assertIn("<?xml", result)
        # Should contain the elements
        self.assertIn("<root>", result)
        self.assertIn("<child", result)
        self.assertIn('name="test"', result)
    
    def test_output_is_indented(self):
        """Test that output contains indentation for readability."""
        elem = ET.Element("root")
        child = ET.SubElement(elem, "child")
        ET.SubElement(child, "grandchild")
        
        result = prettify_xml(elem)
        
        # Should contain newlines and spaces for indentation
        self.assertIn("\n", result)
    
    def test_empty_element(self):
        """Test prettifying an empty element."""
        elem = ET.Element("empty")
        
        result = prettify_xml(elem)
        
        self.assertIn("<?xml", result)
        self.assertIn("empty", result)


class TestThreeMFWriter(unittest.TestCase):
    """Test ThreeMFWriter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []
        
        # Define simple callbacks for testing
        self.naming_callback = lambda obj_id, mesh: mesh.metadata.get('color_name', f'Object {obj_id}')
        self.slot_callback = lambda obj_id, mesh: mesh.metadata.get('slot', 1)
        self.transform_callback = lambda obj_id, mesh, ctx: (0.0, 0.0, 0.0)
    
    def tearDown(self):
        """Clean up temporary files."""
        for filepath in self.temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def _create_temp_file(self, suffix: str = '.3mf') -> str:
        """Create a temporary file and track it for cleanup."""
        fd, filepath = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self.temp_files.append(filepath)
        return filepath
    
    def test_write_single_mesh(self):
        """Test writing a single mesh to 3MF file."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh])
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
        
        # Verify result statistics
        self.assertEqual(result['num_objects'], 1)
        self.assertEqual(result['num_vertices'], 3)
        self.assertEqual(result['num_triangles'], 1)
    
    def test_write_multiple_meshes(self):
        """Test writing multiple meshes to 3MF file."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh1 = create_simple_mesh()
        mesh2 = create_square_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh1, mesh2])
        
        self.assertEqual(result['num_objects'], 2)
        self.assertEqual(result['num_vertices'], 7)  # 3 + 4
        self.assertEqual(result['num_triangles'], 3)  # 1 + 2
    
    def test_write_creates_valid_3mf_structure(self):
        """Test that written 3MF has correct file structure."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Use the helper to validate structure
        validate_3mf_structure(output_path)
    
    def test_write_empty_meshes_raises_error(self):
        """Test that writing empty mesh list raises ValueError."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        output_path = self._create_temp_file()
        
        with self.assertRaises(ValueError) as context:
            writer.write(output_path, [])
        
        self.assertIn("empty", str(context.exception).lower())
    
    def test_naming_callback_is_used(self):
        """Test that naming callback is called and name appears in output."""
        custom_name = "CustomTestObject"
        naming_cb = lambda obj_id, mesh: custom_name
        
        writer = ThreeMFWriter(
            naming_callback=naming_cb,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh])
        
        # Check that the name was assigned to the object
        self.assertEqual(len(result['objects']), 1)
        self.assertEqual(result['objects'][0].name, custom_name)
    
    def test_slot_callback_is_used(self):
        """Test that slot callback is called and slot is assigned."""
        custom_slot = 5
        slot_cb = lambda obj_id, mesh: custom_slot
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=slot_cb,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh])
        
        # Check that the slot was assigned
        self.assertEqual(result['objects'][0].extruder_slot, custom_slot)
    
    def test_transform_callback_is_used(self):
        """Test that transform callback is called and transform is applied."""
        custom_transform = (10.0, 20.0, 30.0)
        transform_cb = lambda obj_id, mesh, ctx: custom_transform
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=transform_cb
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh])
        
        # Check that the transform was applied
        self.assertEqual(result['objects'][0].transform, custom_transform)
    
    def test_context_passed_to_transform_callback(self):
        """Test that context is passed to transform callback."""
        context_received = []
        
        def capture_context(obj_id, mesh, ctx):
            context_received.append(ctx)
            return (0.0, 0.0, 0.0)
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=capture_context
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        test_context = {'width': 100, 'height': 200}
        writer.write(output_path, [mesh], context=test_context)
        
        self.assertEqual(len(context_received), 1)
        self.assertEqual(context_received[0], test_context)
    
    def test_progress_callback_is_called(self):
        """Test that progress callback is called during export."""
        progress_calls = []
        
        def capture_progress(stage, message):
            progress_calls.append((stage, message))
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback,
            progress_callback=capture_progress
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Should have received progress updates
        self.assertGreater(len(progress_calls), 0)
        
        # All calls should have stage "export"
        stages = [call[0] for call in progress_calls]
        self.assertTrue(all(s == "export" for s in stages))
    
    def test_custom_container_name(self):
        """Test that custom container name is used."""
        custom_name = "MyContainer"
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback,
            container_name=custom_name
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Verify container name in model settings
        with zipfile.ZipFile(output_path, 'r') as zf:
            settings_xml = zf.read('Metadata/model_settings.config').decode('utf-8')
            self.assertIn(custom_name, settings_xml)
    
    def test_custom_build_plate_center(self):
        """Test that custom build plate center is used."""
        custom_center = (200.0, 200.0)
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback,
            build_plate_center=custom_center
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Verify build plate center in main model
        with zipfile.ZipFile(output_path, 'r') as zf:
            model_xml = zf.read('3D/3dmodel.model').decode('utf-8')
            # The transform should contain the custom center
            self.assertIn("200", model_xml)
    
    def test_container_id_is_num_objects_plus_one(self):
        """Test that container ID is correctly calculated."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh1 = create_simple_mesh()
        mesh2 = create_square_mesh()
        output_path = self._create_temp_file()
        
        result = writer.write(output_path, [mesh1, mesh2])
        
        # Container ID should be num_objects + 1
        self.assertEqual(result['container_id'], 3)  # 2 meshes + 1
    
    def test_3mf_is_valid_zip(self):
        """Test that written file is a valid ZIP archive."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        self.assertTrue(zipfile.is_zipfile(output_path))
    
    def test_3mf_contains_xml_files(self):
        """Test that 3MF contains required XML files."""
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        with zipfile.ZipFile(output_path, 'r') as zf:
            namelist = zf.namelist()
            
            self.assertIn('[Content_Types].xml', namelist)
            self.assertIn('_rels/.rels', namelist)
            self.assertIn('3D/3dmodel.model', namelist)
            self.assertIn('3D/_rels/3dmodel.model.rels', namelist)
            self.assertIn('3D/Objects/object_1.model', namelist)
            self.assertIn('Metadata/model_settings.config', namelist)
    
    def test_thumbnail_callback_is_called(self):
        """Test that thumbnail callback is called and thumbnails are added."""
        # Create a simple PNG-like header (not a real image, just for testing)
        fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        
        def thumbnail_cb(output_path, context):
            return [("Metadata/test_thumb.png", fake_png)]
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback,
            thumbnail_callback=thumbnail_cb
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Verify thumbnail was added
        with zipfile.ZipFile(output_path, 'r') as zf:
            self.assertIn("Metadata/test_thumb.png", zf.namelist())
    
    def test_model_title_metadata(self):
        """Test that model title appears in metadata."""
        custom_title = "My Custom Model Title"
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback,
            model_title=custom_title
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        writer.write(output_path, [mesh])
        
        # Verify title in main model
        with zipfile.ZipFile(output_path, 'r') as zf:
            model_xml = zf.read('3D/3dmodel.model').decode('utf-8')
            self.assertIn(custom_title, model_xml)


class TestThreeMFWriterEdgeCases(unittest.TestCase):
    """Test edge cases for ThreeMFWriter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []
        self.naming_callback = lambda obj_id, mesh: f'Object {obj_id}'
        self.slot_callback = lambda obj_id, mesh: 1
        self.transform_callback = lambda obj_id, mesh, ctx: (0.0, 0.0, 0.0)
    
    def tearDown(self):
        """Clean up temporary files."""
        for filepath in self.temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def _create_temp_file(self, suffix: str = '.3mf') -> str:
        """Create a temporary file and track it for cleanup."""
        fd, filepath = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self.temp_files.append(filepath)
        return filepath
    
    def test_write_mesh_with_many_vertices(self):
        """Test writing a mesh with many vertices."""
        # Create mesh with 1000 vertices
        vertices = [(float(i), float(i), 0.0) for i in range(1000)]
        triangles = [(i, i+1, i+2) for i in range(0, 997, 3)]
        mesh = ThreeMFMesh(vertices=vertices, triangles=triangles, metadata={})
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        output_path = self._create_temp_file()
        result = writer.write(output_path, [mesh])
        
        self.assertEqual(result['num_vertices'], 1000)
        self.assertTrue(os.path.exists(output_path))
    
    def test_write_many_meshes(self):
        """Test writing many meshes (100 objects)."""
        meshes = [create_simple_mesh() for _ in range(100)]
        
        writer = ThreeMFWriter(
            naming_callback=self.naming_callback,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        output_path = self._create_temp_file()
        result = writer.write(output_path, meshes)
        
        self.assertEqual(result['num_objects'], 100)
        self.assertEqual(result['container_id'], 101)
    
    def test_write_mesh_with_special_characters_in_name(self):
        """Test that special characters in names are handled."""
        special_name = "Test <Object> & \"Name\""
        naming_cb = lambda obj_id, mesh: special_name
        
        writer = ThreeMFWriter(
            naming_callback=naming_cb,
            slot_callback=self.slot_callback,
            transform_callback=self.transform_callback
        )
        
        mesh = create_simple_mesh()
        output_path = self._create_temp_file()
        
        # Should not raise - XML should be properly escaped
        writer.write(output_path, [mesh])
        
        # Verify file was created and is valid
        self.assertTrue(os.path.exists(output_path))
        validate_3mf_structure(output_path)


if __name__ == '__main__':
    unittest.main()
