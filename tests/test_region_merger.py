"""
Unit tests for the region_merger module.

Tests flood fill algorithm and region merging functionality.
"""

import unittest
import os
import sys
from pathlib import Path

# Add parent directory to path to import the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pixel_to_3mf.region_merger import (
    Region,
    flood_fill,
    merge_regions,
    get_region_bounds
)
from pixel_to_3mf.image_processor import load_image, PixelData
from pixel_to_3mf.config import ConversionConfig
from tests.helpers import (
    create_simple_square_image,
    create_two_region_image,
    create_transparent_image,
    create_diagonal_pattern_image,
    cleanup_test_file
)


class TestRegion(unittest.TestCase):
    """Test the Region class."""
    
    def test_region_initialization(self):
        """Test Region can be created with valid parameters."""
        color = (255, 0, 0)
        pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region = Region(color=color, pixels=pixels)
        
        self.assertEqual(region.color, color)
        self.assertEqual(len(region.pixels), 4)
        self.assertIn((0, 0), region.pixels)
    
    def test_region_repr(self):
        """Test string representation of Region."""
        color = (255, 0, 0)
        pixels = {(0, 0), (1, 0)}
        region = Region(color=color, pixels=pixels)
        
        repr_str = repr(region)
        self.assertIn("RGB(255, 0, 0)", repr_str)
        self.assertIn("pixels=2", repr_str)


class TestFloodFill(unittest.TestCase):
    """Test the flood fill algorithm."""
    
    def test_flood_fill_single_pixel(self):
        """Test flood fill on a single pixel."""
        pixels = {(0, 0): (255, 0, 0, 255)}
        visited = set()
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        self.assertEqual(len(result), 1)
        self.assertIn((0, 0), result)
        self.assertIn((0, 0), visited)
    
    def test_flood_fill_2x2_square(self):
        """Test flood fill on a 2x2 square of same color."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (0, 1): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)
        }
        visited = set()
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result, {(0, 0), (1, 0), (0, 1), (1, 1)})
    
    def test_flood_fill_stops_at_different_color(self):
        """Test that flood fill stops at different colors."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (0, 255, 0, 255),  # Different color
            (0, 1): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)
        }
        visited = set()
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        # Should only include red pixels connected to (0, 0)
        self.assertIn((0, 0), result)
        self.assertNotIn((1, 0), result)  # Green pixel not included
    
    def test_flood_fill_diagonal_connectivity(self):
        """Test that flood fill includes diagonal neighbors."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 1): (255, 0, 0, 255)  # Diagonal neighbor
        }
        visited = set()
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        # Should include diagonal neighbor (8-connectivity)
        self.assertEqual(len(result), 2)
        self.assertIn((0, 0), result)
        self.assertIn((1, 1), result)
    
    def test_flood_fill_respects_visited(self):
        """Test that flood fill doesn't revisit pixels."""
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255)
        }
        visited = {(1, 0)}  # Mark (1, 0) as already visited
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        # Should only get (0, 0) since (1, 0) was pre-visited
        self.assertEqual(len(result), 1)
        self.assertIn((0, 0), result)
    
    def test_flood_fill_complex_shape(self):
        """Test flood fill on a more complex connected shape."""
        # Create an L-shape
        pixels = {
            (0, 0): (255, 0, 0, 255),
            (0, 1): (255, 0, 0, 255),
            (0, 2): (255, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255)
        }
        visited = set()
        
        result = flood_fill(0, 0, (255, 0, 0), pixels, visited)
        
        self.assertEqual(len(result), 5)
        self.assertEqual(result, pixels.keys())


class TestMergeRegions(unittest.TestCase):
    """Test region merging on actual images."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_merge_single_color_image(self):
        """Test merging on a single-color image."""
        filepath = create_simple_square_image(size=4, color=(255, 0, 0))
        self.test_files.append(filepath)
        
        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)
        regions = merge_regions(pixel_data, config)
        
        # Should get exactly 1 region for the entire image
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].color, (255, 0, 0))
        self.assertEqual(len(regions[0].pixels), 16)  # 4x4
    
    def test_merge_two_separate_regions(self):
        """Test merging on image with two separate colored regions."""
        filepath = create_two_region_image()
        self.test_files.append(filepath)
        
        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)
        regions = merge_regions(pixel_data, config)
        
        # Should get 2 regions (red and blue)
        self.assertEqual(len(regions), 2)
        
        # Check that we have both colors
        colors = {r.color for r in regions}
        self.assertIn((255, 0, 0), colors)
        self.assertIn((0, 0, 255), colors)
        
        # Each region should have 4 pixels
        for region in regions:
            self.assertEqual(len(region.pixels), 4)
    
    def test_merge_transparent_image(self):
        """Test merging on image with transparent areas."""
        filepath = create_transparent_image()
        self.test_files.append(filepath)
        
        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)
        regions = merge_regions(pixel_data, config)
        
        # Should get 1 region for the red center
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].color, (255, 0, 0))
        self.assertEqual(len(regions[0].pixels), 4)  # 2x2 center
    
    def test_merge_diagonal_pattern(self):
        """Test merging on diagonal pattern."""
        filepath = create_diagonal_pattern_image()
        self.test_files.append(filepath)
        
        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = load_image(filepath, config)
        regions = merge_regions(pixel_data, config)
        
        # All diagonal pixels should merge into 1 region due to diagonal connectivity
        self.assertEqual(len(regions), 1)
        self.assertEqual(len(regions[0].pixels), 4)
    
    def test_merge_empty_image(self):
        """Test merging on completely transparent image."""
        config = ConversionConfig(max_size_mm=200.0)
        pixel_data = PixelData(width=4, height=4, pixel_size_mm=1.0, pixels={})
        regions = merge_regions(pixel_data, config)
        
        # Should get 0 regions
        self.assertEqual(len(regions), 0)


class TestGetRegionBounds(unittest.TestCase):
    """Test getting bounding boxes for regions."""
    
    def test_bounds_single_pixel(self):
        """Test bounds for single pixel region."""
        region = Region(color=(255, 0, 0), pixels={(5, 3)})
        
        min_x, max_x, min_y, max_y = get_region_bounds(region)
        
        self.assertEqual(min_x, 5)
        self.assertEqual(max_x, 5)
        self.assertEqual(min_y, 3)
        self.assertEqual(max_y, 3)
    
    def test_bounds_rectangle(self):
        """Test bounds for rectangular region."""
        pixels = {(2, 3), (3, 3), (4, 3), (2, 4), (3, 4), (4, 4)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        min_x, max_x, min_y, max_y = get_region_bounds(region)
        
        self.assertEqual(min_x, 2)
        self.assertEqual(max_x, 4)
        self.assertEqual(min_y, 3)
        self.assertEqual(max_y, 4)
    
    def test_bounds_irregular_shape(self):
        """Test bounds for irregular shape."""
        # L-shape
        pixels = {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        min_x, max_x, min_y, max_y = get_region_bounds(region)
        
        self.assertEqual(min_x, 0)
        self.assertEqual(max_x, 2)
        self.assertEqual(min_y, 0)
        self.assertEqual(max_y, 2)
    
    def test_bounds_empty_region(self):
        """Test bounds for empty region."""
        region = Region(color=(255, 0, 0), pixels=set())
        
        min_x, max_x, min_y, max_y = get_region_bounds(region)
        
        self.assertEqual(min_x, 0)
        self.assertEqual(max_x, 0)
        self.assertEqual(min_y, 0)
        self.assertEqual(max_y, 0)


if __name__ == '__main__':
    unittest.main()
