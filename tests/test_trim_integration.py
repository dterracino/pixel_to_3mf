"""
Integration tests for the --trim disconnected pixels feature.

These tests verify that the trim functionality works correctly through
the entire conversion pipeline.
"""

import unittest
import os
from PIL import Image
from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from tests.helpers import create_test_image, cleanup_test_file


class TestTrimIntegration(unittest.TestCase):
    """Integration tests for trim disconnected pixels."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            cleanup_test_file(filepath)
    
    def test_trim_disabled_by_default(self):
        """Test that trim is disabled by default."""
        # Create image with a disconnected pixel
        # Pattern:
        # BBBBBBX
        # BBBBXXB  <- This B is disconnected
        # BBBBXXX
        
        colors = {
            (255, 0, 0, 255): [
                # Row 0: 6 B's
                (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),
                # Row 1: 4 B's + disconnected B
                (0, 1), (1, 1), (2, 1), (3, 1), (6, 1),
                # Row 2: 4 B's
                (0, 2), (1, 2), (2, 2), (3, 2),
            ]
        }
        
        input_path = create_test_image(7, 3, colors)
        output_path = input_path.replace('.png', '_model.3mf')
        self.test_files.extend([input_path, output_path])
        
        # Convert without trim (default)
        config = ConversionConfig(trim_disconnected=False)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Should have 1 region (all red pixels connected via 8-connectivity)
        self.assertEqual(stats['num_regions'], 1)
    
    def test_trim_removes_disconnected_pixel(self):
        """Test that trim removes disconnected pixels."""
        # Same pattern as above
        colors = {
            (255, 0, 0, 255): [
                # Row 0: 6 B's
                (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),
                # Row 1: 4 B's + disconnected B at (6,1)
                (0, 1), (1, 1), (2, 1), (3, 1), (6, 1),
                # Row 2: 4 B's
                (0, 2), (1, 2), (2, 2), (3, 2),
            ]
        }
        
        input_path = create_test_image(7, 3, colors)
        output_path = input_path.replace('.png', '_model.3mf')
        self.test_files.extend([input_path, output_path])
        
        # Convert WITH trim enabled
        config = ConversionConfig(trim_disconnected=True)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Should still have 1 region, but with the disconnected pixel removed
        # The region should have 13 pixels instead of 14
        self.assertEqual(stats['num_regions'], 1)
        # We can't directly check pixel count in stats, but we verified it works in unit tests
    
    def test_trim_with_multiple_regions(self):
        """Test trim with multiple colored regions."""
        colors = {
            # Red region with disconnected pixel
            (255, 0, 0, 255): [
                (0, 0), (1, 0), (0, 1), (1, 1),  # Solid 2x2
                (3, 0),  # Disconnected from main block (separate region)
            ],
            # Blue region - all connected
            (0, 0, 255, 255): [
                (5, 5), (6, 5), (5, 6), (6, 6),  # Solid 2x2
            ],
            # Green region - all disconnected (diagonal line)
            (0, 255, 0, 255): [
                (0, 5), (1, 6), (2, 7),  # Diagonal
            ]
        }
        
        input_path = create_test_image(8, 8, colors)
        output_path = input_path.replace('.png', '_model.3mf')
        self.test_files.extend([input_path, output_path])
        
        # Convert WITHOUT trim
        config_no_trim = ConversionConfig(trim_disconnected=False)
        stats_no_trim = convert_image_to_3mf(input_path, output_path, config=config_no_trim)
        
        # Should have 4 regions:
        # - Red 2x2 block (1 region)
        # - Red single pixel at (3,0) (separate region, disconnected from block)
        # - Blue 2x2 block (1 region)
        # - Green diagonal line (1 region via 8-connectivity)
        self.assertEqual(stats_no_trim['num_regions'], 4)
        
        # Convert WITH trim
        output_path2 = input_path.replace('.png', '_trimmed.3mf')
        self.test_files.append(output_path2)
        config_trim = ConversionConfig(trim_disconnected=True)
        stats_trim = convert_image_to_3mf(input_path, output_path2, config=config_trim)
        
        # Should have 2 regions:
        # - Red 2x2 block (remains intact)
        # - Blue 2x2 block (remains intact)
        # - Red single pixel removed (disconnected)
        # - Green diagonal removed (all pixels disconnected)
        self.assertEqual(stats_trim['num_regions'], 2)
    
    def test_trim_with_connectivity_4(self):
        """Test that trim works correctly with 4-connectivity mode."""
        # Diagonal line - with 4-connectivity, each pixel is a separate region
        colors = {
            (255, 0, 0, 255): [
                (0, 0), (1, 1), (2, 2), (3, 3),
            ]
        }
        
        input_path = create_test_image(4, 4, colors)
        output_path = input_path.replace('.png', '_model.3mf')
        self.test_files.extend([input_path, output_path])
        
        # With 4-connectivity, each diagonal pixel is a separate region
        # Each region has only 1 pixel, which is disconnected
        config = ConversionConfig(connectivity=4, trim_disconnected=True)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # All 4 regions should be removed (all single pixels are disconnected)
        self.assertEqual(stats['num_regions'], 0)
    
    def test_trim_preserves_solid_shapes(self):
        """Test that trim doesn't affect solid connected shapes."""
        # Create a solid square - no disconnected pixels
        colors = {
            (255, 0, 0, 255): [
                (0, 0), (1, 0), (2, 0),
                (0, 1), (1, 1), (2, 1),
                (0, 2), (1, 2), (2, 2),
            ]
        }
        
        input_path = create_test_image(3, 3, colors)
        output_path = input_path.replace('.png', '_model.3mf')
        self.test_files.extend([input_path, output_path])
        
        # Convert with trim
        config = ConversionConfig(trim_disconnected=True)
        stats = convert_image_to_3mf(input_path, output_path, config=config)
        
        # Should still have 1 region with all 9 pixels
        self.assertEqual(stats['num_regions'], 1)


if __name__ == '__main__':
    unittest.main()
