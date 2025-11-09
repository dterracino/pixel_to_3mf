"""
Unit tests for backing plate synchronization with colored regions.

These tests ensure that the backing plate matches the exact footprint of
the colored regions, even after pixels are filtered during region merging
or optimization.
"""

import unittest
import sys
from pathlib import Path
from typing import Set, Tuple

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.pixel_to_3mf import _create_filtered_pixel_data
from pixel_to_3mf.region_merger import Region, merge_regions
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.mesh_generator import generate_backing_plate
from pixel_to_3mf.config import ConversionConfig


class TestFilteredPixelData(unittest.TestCase):
    """Test the _create_filtered_pixel_data helper function."""
    
    def test_filter_keeps_all_region_pixels(self):
        """Test that filtered pixel_data includes all pixels from regions."""
        # Create pixel data with 6 pixels
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255),
            (0, 1): (0, 255, 0, 255),
            (1, 1): (0, 255, 0, 255),
            (2, 1): (0, 255, 0, 255),
        }
        pixel_data = PixelData(width=3, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        # Create regions that include all pixels
        red_region = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0), (2, 0)})
        green_region = Region(color=(0, 255, 0), pixels={(0, 1), (1, 1), (2, 1)})
        regions = [red_region, green_region]
        
        # Filter pixel data
        filtered = _create_filtered_pixel_data(regions, pixel_data)
        
        # All pixels should be included
        self.assertEqual(len(filtered.pixels), 6)
        self.assertEqual(filtered.width, pixel_data.width)
        self.assertEqual(filtered.height, pixel_data.height)
        self.assertEqual(filtered.pixel_size_mm, pixel_data.pixel_size_mm)
    
    def test_filter_removes_excluded_pixels(self):
        """Test that filtered pixel_data excludes pixels not in regions."""
        # Create pixel data with 6 pixels
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255),
            (0, 1): (0, 255, 0, 255),
            (1, 1): (0, 255, 0, 255),
            (2, 1): (0, 255, 0, 255),
        }
        pixel_data = PixelData(width=3, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        # Create regions that only include 4 pixels (middle row pixels excluded)
        red_region = Region(color=(255, 0, 0), pixels={(0, 0), (2, 0)})
        green_region = Region(color=(0, 255, 0), pixels={(0, 1), (2, 1)})
        regions = [red_region, green_region]
        
        # Filter pixel data
        filtered = _create_filtered_pixel_data(regions, pixel_data)
        
        # Only 4 pixels should be included
        self.assertEqual(len(filtered.pixels), 4)
        self.assertIn((0, 0), filtered.pixels)
        self.assertIn((2, 0), filtered.pixels)
        self.assertIn((0, 1), filtered.pixels)
        self.assertIn((2, 1), filtered.pixels)
        # Middle pixels should be excluded
        self.assertNotIn((1, 0), filtered.pixels)
        self.assertNotIn((1, 1), filtered.pixels)
    
    def test_filter_with_empty_regions(self):
        """Test filtering with an empty regions list."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
        }
        pixel_data = PixelData(width=2, height=1, pixel_size_mm=1.0, pixels=pixels)
        
        # Empty regions list
        regions = []
        
        # Filter pixel data
        filtered = _create_filtered_pixel_data(regions, pixel_data)
        
        # No pixels should be included
        self.assertEqual(len(filtered.pixels), 0)
        self.assertEqual(filtered.width, pixel_data.width)
        self.assertEqual(filtered.height, pixel_data.height)


class TestBackingPlateSynchronization(unittest.TestCase):
    """Test that backing plate matches colored regions exactly."""
    
    def test_backing_plate_matches_all_regions(self):
        """Test backing plate includes all pixels from all regions."""
        # Create pixel data with 4 pixels in a 2x2 grid
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (0, 1): (0, 255, 0, 255),
            (1, 1): (0, 255, 0, 255),
        }
        pixel_data = PixelData(width=2, height=2, pixel_size_mm=1.0, pixels=pixels)
        
        # Merge regions (should create 2 regions for the 2 colors)
        config = ConversionConfig(base_height_mm=1.0)
        regions = merge_regions(pixel_data, config)
        
        # Create filtered pixel data
        filtered_pixel_data = _create_filtered_pixel_data(regions, pixel_data)
        
        # Generate backing plate from filtered data
        backing_mesh = generate_backing_plate(filtered_pixel_data, config)
        
        # Verify backing mesh was created
        self.assertIsNotNone(backing_mesh)
        self.assertGreater(len(backing_mesh.vertices), 0)
        self.assertGreater(len(backing_mesh.triangles), 0)
        
        # Verify filtered pixel data matches regions
        region_pixels: Set[Tuple[int, int]] = set()
        for region in regions:
            region_pixels.update(region.pixels)
        
        self.assertEqual(set(filtered_pixel_data.pixels.keys()), region_pixels)
    
    def test_backing_plate_excludes_filtered_pixels(self):
        """Test that backing plate excludes pixels not in regions."""
        # Create pixel data with a pattern that might get filtered
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255),
            # Isolated pixel that might be in a separate region
            (10, 10): (255, 0, 0, 255),
        }
        pixel_data = PixelData(width=11, height=11, pixel_size_mm=1.0, pixels=pixels)
        
        # Merge regions - isolated pixel forms its own region
        config = ConversionConfig(base_height_mm=1.0, connectivity=4)  # 4-connectivity
        regions = merge_regions(pixel_data, config)
        
        # We should have 2 regions (one for the row, one for the isolated pixel)
        self.assertEqual(len(regions), 2)
        
        # Now simulate filtering out single-pixel regions
        filtered_regions = [r for r in regions if len(r.pixels) > 1]
        self.assertEqual(len(filtered_regions), 1)  # Only the 3-pixel region remains
        
        # Create filtered pixel data from filtered regions
        filtered_pixel_data = _create_filtered_pixel_data(filtered_regions, pixel_data)
        
        # Verify isolated pixel was excluded
        self.assertEqual(len(filtered_pixel_data.pixels), 3)
        self.assertNotIn((10, 10), filtered_pixel_data.pixels)
        
        # Generate backing plate from filtered data
        backing_mesh = generate_backing_plate(filtered_pixel_data, config)
        
        # Backing plate should only cover the 3-pixel region
        self.assertIsNotNone(backing_mesh)
        self.assertGreater(len(backing_mesh.vertices), 0)
    
    def test_backing_plate_with_all_pixels_filtered(self):
        """Test backing plate generation when all pixels are filtered out."""
        # Create pixel data
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
        }
        pixel_data = PixelData(width=2, height=1, pixel_size_mm=1.0, pixels=pixels)
        
        # Create empty regions list (all pixels filtered)
        filtered_regions = []
        
        # Create filtered pixel data
        filtered_pixel_data = _create_filtered_pixel_data(filtered_regions, pixel_data)
        
        # Verify no pixels remain
        self.assertEqual(len(filtered_pixel_data.pixels), 0)
        
        # Generate backing plate from empty data
        config = ConversionConfig(base_height_mm=1.0)
        backing_mesh = generate_backing_plate(filtered_pixel_data, config)
        
        # Should return empty mesh or minimal geometry
        self.assertIsNotNone(backing_mesh)
        # Empty pixel data should result in empty mesh
        if len(filtered_pixel_data.pixels) == 0:
            # Backing plate for no pixels should be empty
            self.assertEqual(len(backing_mesh.vertices), 0)
            self.assertEqual(len(backing_mesh.triangles), 0)


if __name__ == '__main__':
    unittest.main()
