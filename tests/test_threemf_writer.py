"""
Unit tests for the threemf_writer module.

Tests 3MF file generation and formatting utilities.
"""

import unittest
import sys
import os
import zipfile
import tempfile
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.threemf_writer import (
    format_float,
    write_3mf
)
from pixel_to_3mf.mesh_generator import Mesh
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import validate_3mf_structure


class TestFormatFloat(unittest.TestCase):
    """Test float formatting for 3MF files."""
    
    def test_format_integer(self):
        """Test formatting integer value."""
        result = format_float(2.0)
        self.assertEqual(result, "2")
    
    def test_format_decimal(self):
        """Test formatting decimal value."""
        result = format_float(2.5, precision=3)
        self.assertEqual(result, "2.5")
    
    def test_format_strips_trailing_zeros(self):
        """Test that trailing zeros are removed."""
        result = format_float(2.500, precision=3)
        self.assertEqual(result, "2.5")
    
    def test_format_precision(self):
        """Test formatting with specified precision."""
        result = format_float(3.14159, precision=2)
        self.assertEqual(result, "3.14")
    
    def test_format_very_small(self):
        """Test formatting very small numbers."""
        result = format_float(0.001, precision=3)
        self.assertEqual(result, "0.001")


class TestWrite3MF(unittest.TestCase):
    """Test 3MF file writing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []
    
    def tearDown(self):
        """Clean up temporary files."""
        for filepath in self.temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def test_write_simple_3mf(self):
        """Test writing a simple 3MF file."""
        # Create simple mesh (triangle)
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles = [(0, 1, 2)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        # Create pixel data
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        # Create config
        config = ConversionConfig()
        
        # Write 3MF
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh, "region_1")]
        region_colors = [(255, 0, 0)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
    
    def test_3mf_is_valid_zip(self):
        """Test that generated 3MF file is a valid ZIP archive."""
        # Create simple mesh
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles = [(0, 1, 2)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh, "region_1")]
        region_colors = [(255, 0, 0)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Test that it's a valid 3MF with proper structure
        validate_3mf_structure(output_path)
    
    def test_3mf_contains_required_files(self):
        """Test that 3MF contains required files."""
        # Create simple mesh
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles = [(0, 1, 2)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh, "region_1")]
        region_colors = [(255, 0, 0)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Check contents
        with zipfile.ZipFile(output_path, 'r') as zf:
            namelist = zf.namelist()
            
            # Required files according to 3MF spec
            self.assertIn('[Content_Types].xml', namelist)
            self.assertIn('_rels/.rels', namelist)
            
            # Our custom structure
            self.assertTrue(any('3D/3dmodel.model' in name for name in namelist))
            self.assertTrue(any('3D/Objects' in name for name in namelist))
    
    def test_3mf_multiple_meshes(self):
        """Test writing 3MF with multiple meshes."""
        # Create two meshes
        vertices1 = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles1 = [(0, 1, 2)]
        mesh1 = Mesh(vertices=vertices1, triangles=triangles1)
        
        vertices2 = [(2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.5, 1.0, 0.0)]
        triangles2 = [(0, 1, 2)]
        mesh2 = Mesh(vertices=vertices2, triangles=triangles2)
        
        pixels = {(0, 0): (255, 0, 0, 255), (1, 0): (0, 0, 255, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh1, "region_1"), (mesh2, "region_2")]
        region_colors = [(255, 0, 0), (0, 0, 255)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)
    
    def test_3mf_with_backing_plate(self):
        """Test writing 3MF with backing plate mesh."""
        # Create region mesh and backing plate
        vertices1 = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        triangles1 = [(0, 1, 2)]
        mesh1 = Mesh(vertices=vertices1, triangles=triangles1)
        
        vertices2 = [(0.0, 0.0, -1.0), (2.0, 0.0, -1.0), (1.0, 2.0, -1.0)]
        triangles2 = [(0, 1, 2)]
        backing_mesh = Mesh(vertices=vertices2, triangles=triangles2)
        
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh1, "region_1"), (backing_mesh, "backing_plate")]
        region_colors = [(255, 0, 0)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_path))
    
    def test_3mf_large_mesh(self):
        """Test writing 3MF with a larger mesh."""
        # Create mesh with many vertices
        vertices = [(float(i), float(i), 0.0) for i in range(100)]
        triangles = [(i, i+1, i+2) for i in range(0, 97, 3)]
        mesh = Mesh(vertices=vertices, triangles=triangles)
        
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        config = ConversionConfig()
        
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        meshes = [(mesh, "region_1")]
        region_colors = [(255, 0, 0)]
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Verify file was created
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)


class TestWrite3MFIntegration(unittest.TestCase):
    """Integration tests for 3MF writing with real pixel data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []
    
    def tearDown(self):
        """Clean up temporary files."""
        for filepath in self.temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def test_3mf_from_single_pixel(self):
        """Test creating 3MF from single pixel."""
        from pixel_to_3mf.region_merger import Region, merge_regions
        from pixel_to_3mf.mesh_generator import generate_region_mesh, generate_backing_plate
        from pixel_to_3mf.config import ConversionConfig

        # Create pixel data
        pixels = {(0, 0): (255, 0, 0, 255)}
        pixel_data = PixelData(width=1, height=1, pixel_size_mm=1.0, pixels=pixels)
        config = ConversionConfig()

        # Create region and mesh
        regions = merge_regions(pixel_data, config)
        meshes = []
        region_colors = []

        for region in regions:
            mesh = generate_region_mesh(region, pixel_data, config)
            meshes.append((mesh, "region_1"))
            region_colors.append(region.color)

        backing_mesh = generate_backing_plate(pixel_data, config)
        meshes.append((backing_mesh, "backing_plate"))
        
        # Write 3MF
        fd, output_path = tempfile.mkstemp(suffix='.3mf')
        os.close(fd)
        self.temp_files.append(output_path)
        
        write_3mf(output_path, meshes, region_colors, pixel_data, config)
        
        # Verify
        self.assertTrue(os.path.exists(output_path))
        validate_3mf_structure(output_path)


if __name__ == '__main__':
    unittest.main()
