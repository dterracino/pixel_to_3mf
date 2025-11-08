"""
Tests for trimming disconnected pixels.

This module tests the functionality that removes pixels which only connect
to their region via corners (diagonally), as these are unreliable for 3D printing.
"""

import unittest
from pixel_to_3mf.region_merger import Region, is_pixel_disconnected, trim_disconnected_pixels


class TestIsPixelDisconnected(unittest.TestCase):
    """Test the is_pixel_disconnected() function."""
    
    def test_isolated_pixel_is_disconnected(self):
        """Test that a completely isolated pixel is disconnected."""
        region_pixels = {(5, 5)}
        result = is_pixel_disconnected(5, 5, region_pixels)
        self.assertTrue(result)
    
    def test_edge_connected_pixel_not_disconnected(self):
        """Test that a pixel with edge connections is not disconnected."""
        # Horizontal line: (0,0) - (1,0) - (2,0)
        region_pixels = {(0, 0), (1, 0), (2, 0)}
        
        # Middle pixel has edge neighbors on both sides
        result = is_pixel_disconnected(1, 0, region_pixels)
        self.assertFalse(result)
    
    def test_corner_only_connection_is_disconnected(self):
        """Test the classic disconnected pixel case from the problem statement."""
        # Pattern:
        # BBBBBBX
        # BBBBXXB  <- This B at (6,1) is disconnected
        # BBBBXXX
        
        # B pixels form the region
        region_pixels = {
            # Row 0 (top): 6 B's
            (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),
            # Row 1 (middle): 4 B's on left, then XX, then 1 B on right
            (0, 1), (1, 1), (2, 1), (3, 1), (6, 1),
            # Row 2 (bottom): 4 B's on left
            (0, 2), (1, 2), (2, 2), (3, 2),
        }
        
        # The B at (6,1) only connects via corner to (5,0)
        result = is_pixel_disconnected(6, 1, region_pixels)
        self.assertTrue(result)
        
        # The B at (3,1) has edge neighbors and should not be disconnected
        result = is_pixel_disconnected(3, 1, region_pixels)
        self.assertFalse(result)
    
    def test_diagonal_line_pixels_are_disconnected(self):
        """Test that pixels in a diagonal line are all disconnected."""
        # Diagonal: (0,0), (1,1), (2,2), (3,3)
        # Each pixel only touches the next via corner
        region_pixels = {(0, 0), (1, 1), (2, 2), (3, 3)}
        
        # All pixels should be disconnected (no edge neighbors)
        for x, y in region_pixels:
            result = is_pixel_disconnected(x, y, region_pixels)
            self.assertTrue(result, f"Pixel ({x},{y}) should be disconnected")
    
    def test_l_shape_corner_pixel(self):
        """Test an L-shaped pattern - corner pixel has edge connections."""
        # L shape:
        # B
        # BB
        region_pixels = {(0, 0), (0, 1), (1, 1)}
        
        # Corner pixel (0,1) has edge neighbors in both directions
        result = is_pixel_disconnected(0, 1, region_pixels)
        self.assertFalse(result)
        
        # Top pixel (0,0) has one edge neighbor
        result = is_pixel_disconnected(0, 0, region_pixels)
        self.assertFalse(result)
        
        # Right pixel (1,1) has one edge neighbor
        result = is_pixel_disconnected(1, 1, region_pixels)
        self.assertFalse(result)
    
    def test_checkerboard_pattern(self):
        """Test checkerboard pattern where pixels are all disconnected."""
        # Checkerboard (only diagonal connections):
        # B.B.
        # .B.B
        # B.B.
        region_pixels = {
            (0, 0), (2, 0),
            (1, 1), (3, 1),
            (0, 2), (2, 2),
        }
        
        # All pixels should be disconnected
        for x, y in region_pixels:
            result = is_pixel_disconnected(x, y, region_pixels)
            self.assertTrue(result, f"Pixel ({x},{y}) should be disconnected")


class TestTrimDisconnectedPixels(unittest.TestCase):
    """Test the trim_disconnected_pixels() function."""
    
    def test_no_disconnected_pixels_unchanged(self):
        """Test that regions without disconnected pixels remain unchanged."""
        # Solid 3x3 square - all pixels edge-connected
        pixels = {
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
            (0, 2), (1, 2), (2, 2),
        }
        region = Region(color=(255, 0, 0), pixels=pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].color, (255, 0, 0))
        self.assertEqual(result[0].pixels, pixels)
    
    def test_removes_single_disconnected_pixel(self):
        """Test removing a single disconnected pixel from the problem statement."""
        # Pattern:
        # BBBBBBX
        # BBBBXXB  <- Remove this B at (6,1)
        # BBBBXXX
        
        region_pixels = {
            # Row 0: 6 B's
            (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),
            # Row 1: 4 B's + disconnected B
            (0, 1), (1, 1), (2, 1), (3, 1), (6, 1),
            # Row 2: 4 B's
            (0, 2), (1, 2), (2, 2), (3, 2),
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        # The disconnected pixel (6,1) should be removed
        self.assertNotIn((6, 1), result[0].pixels)
        # All other pixels should remain
        expected_pixels = region_pixels - {(6, 1)}
        self.assertEqual(result[0].pixels, expected_pixels)
    
    def test_removes_diagonal_line(self):
        """Test that a diagonal line of disconnected pixels is completely removed."""
        # Diagonal: (0,0), (1,1), (2,2), (3,3)
        region_pixels = {(0, 0), (1, 1), (2, 2), (3, 3)}
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        # All pixels were disconnected, so region should be empty and filtered out
        self.assertEqual(len(result), 0)
    
    def test_iterative_removal(self):
        """Test that removal is iterative (removing one pixel can expose another)."""
        # Pattern that creates iterative removal:
        # BB.B  <- (3,0) only connects via corner to (2,1) 
        # .BB.
        # ....
        # After removing (3,0), the region is still intact
        
        region_pixels = {
            (0, 0), (1, 0), (3, 0),  # Top row - (3,0) is disconnected
            (1, 1), (2, 1),  # Middle row
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        # (3,0) should be removed as it's disconnected
        expected_pixels = {(0, 0), (1, 0), (1, 1), (2, 1)}
        self.assertEqual(result[0].pixels, expected_pixels)
    
    def test_multiple_regions(self):
        """Test trimming multiple regions."""
        # Region 1: Solid block (no disconnected pixels)
        region1_pixels = {(0, 0), (1, 0), (0, 1), (1, 1)}
        region1 = Region(color=(255, 0, 0), pixels=region1_pixels)
        
        # Region 2: Has a disconnected pixel
        region2_pixels = {(5, 5), (6, 5), (5, 6), (6, 6), (8, 5)}  # (8,5) is disconnected
        region2 = Region(color=(0, 0, 255), pixels=region2_pixels)
        
        result = trim_disconnected_pixels([region1, region2])
        
        self.assertEqual(len(result), 2)
        
        # Find regions by color
        red_region = next(r for r in result if r.color == (255, 0, 0))
        blue_region = next(r for r in result if r.color == (0, 0, 255))
        
        # Red region unchanged
        self.assertEqual(red_region.pixels, region1_pixels)
        
        # Blue region should have disconnected pixel removed
        expected_blue = {(5, 5), (6, 5), (5, 6), (6, 6)}
        self.assertEqual(blue_region.pixels, expected_blue)
    
    def test_empty_region_filtered_out(self):
        """Test that completely disconnected regions are filtered out."""
        # Two regions: one solid, one all disconnected
        region1 = Region(color=(255, 0, 0), pixels={(0, 0), (1, 0)})  # Edge connected
        region2 = Region(color=(0, 0, 255), pixels={(5, 5)})  # Isolated pixel
        
        result = trim_disconnected_pixels([region1, region2])
        
        # Only region1 should remain
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].color, (255, 0, 0))
    
    def test_checkerboard_all_removed(self):
        """Test that a checkerboard pattern is completely removed."""
        region_pixels = {
            (0, 0), (2, 0), (4, 0),
            (1, 1), (3, 1), (5, 1),
            (0, 2), (2, 2), (4, 2),
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        # All pixels are disconnected
        self.assertEqual(len(result), 0)
    
    def test_complex_pattern(self):
        """Test a more complex pattern with mixed connectivity."""
        # Pattern:
        # BBBBB..B  <- (7,0) is disconnected (no edge neighbors)
        # BBBBB...
        # BBB.....
        
        region_pixels = {
            # Top row - (7,0) only touches (6,0) diagonally from below
            (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (7, 0),
            # Middle row
            (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (6, 1),
            # Bottom row
            (0, 2), (1, 2), (2, 2),
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        # (7,0) should be removed (no edge neighbors)
        # (6,1) should also be removed after (7,0) or on its own (no edge neighbors)
        expected = region_pixels - {(7, 0), (6, 1)}
        self.assertEqual(result[0].pixels, expected)
    
    def test_isolated_single_pixel(self):
        """Test that a single completely isolated pixel is removed."""
        # Pattern:
        # BBBXXX
        # BBBXBX  <- isolated pixel at (4,1)
        # BBBXXX
        
        region_pixels = {
            # Main 3x3 block
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
            (0, 2), (1, 2), (2, 2),
            # Isolated pixel with no edge neighbors
            (4, 1),
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        # Isolated pixel should be removed
        expected = region_pixels - {(4, 1)}
        self.assertEqual(result[0].pixels, expected)
    
    def test_stairstep_disconnected_pixels(self):
        """Test that stair-step disconnected pixels are all removed."""
        # Pattern:
        # BBBXXXX
        # BBBXBXX  <- disconnected at (4,1)
        # BBBXXBX  <- disconnected at (5,2)
        
        region_pixels = {
            # Main 3x3 block
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
            (0, 2), (1, 2), (2, 2),
            # Stair-step disconnected pixels
            (4, 1),
            (5, 2),
        }
        region = Region(color=(255, 0, 0), pixels=region_pixels)
        
        result = trim_disconnected_pixels([region])
        
        self.assertEqual(len(result), 1)
        # Both stair-step pixels should be removed
        expected = region_pixels - {(4, 1), (5, 2)}
        self.assertEqual(result[0].pixels, expected)


if __name__ == '__main__':
    unittest.main()
