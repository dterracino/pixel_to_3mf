"""
Tests for the summary file writer module.

This module tests the generation of summary files that list colors/filaments
used in a 3MF conversion.
"""

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
import os

from pixel_to_3mf.summary_writer import write_summary_file
from pixel_to_3mf.config import ConversionConfig


class TestWriteSummaryFile(unittest.TestCase):
    """Test summary file generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            if os.path.exists(filepath):
                os.unlink(filepath)
    
    def test_summary_file_created_with_correct_name(self):
        """Test that summary file is created with correct naming pattern."""
        # Create a temporary 3MF file
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        # Create config
        config = ConversionConfig(color_naming_mode="color")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 0, 0): 2,
            (0, 255, 0): 3,
            (0, 0, 255): 4
        }
        
        # Write summary
        region_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        color_names = ["red", "lime", "blue"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Verify the summary path
        expected_path = output_path.replace('.3mf', '.summary.txt')
        self.assertEqual(summary_path, expected_path)
        
        # Verify the file exists
        self.assertTrue(os.path.exists(summary_path))
    
    def test_summary_contains_color_information(self):
        """Test that summary file contains color names and hex codes."""
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        config = ConversionConfig(color_naming_mode="color")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 0, 0): 2,
            (0, 255, 0): 3
        }
        
        region_colors = [(255, 0, 0), (0, 255, 0)]
        color_names = ["red", "lime"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read the summary file
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify it contains the color names
        self.assertIn("red", content)
        self.assertIn("lime", content)
        
        # Verify it contains hex codes
        self.assertIn("#ff0000", content.lower())
        self.assertIn("#00ff00", content.lower())
        
        # Verify it contains RGB values
        self.assertIn("(255, 0, 0)", content)
        self.assertIn("(0, 255, 0)", content)
    
    def test_summary_filament_mode(self):
        """Test summary file in filament mode."""
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        config = ConversionConfig(
            color_naming_mode="filament",
            filament_maker="Bambu Lab",
            filament_type="PLA",
            filament_finish="Basic"
        )
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 0, 0): 2,
            (0, 255, 0): 3
        }
        
        # Use actual filament names that would be returned by get_color_name
        region_colors = [(255, 0, 0), (0, 255, 0)]
        color_names = [
            "Bambu Lab PLA Basic Red",
            "Bambu Lab PLA Basic Green"
        ]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read the summary file
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify filament names are included
        self.assertIn("Bambu Lab PLA Basic Red", content)
        self.assertIn("Bambu Lab PLA Basic Green", content)
        
        # Verify it says "Filaments Used"
        self.assertIn("Filaments Used:", content)
    
    def test_summary_hex_mode(self):
        """Test summary file in hex mode."""
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        config = ConversionConfig(color_naming_mode="hex")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 0, 0): 2,
            (0, 255, 0): 3
        }
        
        region_colors = [(255, 0, 0), (0, 255, 0)]
        color_names = ["#ff0000", "#00ff00"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read the summary file
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify hex codes are included
        self.assertIn("#ff0000", content.lower())
        self.assertIn("#00ff00", content.lower())
        
        # Verify it says "Colors Used (Hex)"
        self.assertIn("Colors Used (Hex):", content)
    
    def test_summary_groups_same_colors(self):
        """Test that summary groups regions with the same color."""
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        config = ConversionConfig(color_naming_mode="color")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 0, 0): 2,
            (0, 255, 0): 3
        }
        
        # Three regions, but only two unique colors
        region_colors = [(255, 0, 0), (255, 0, 0), (0, 255, 0)]
        color_names = ["red", "red", "lime"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read the summary file
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify it shows 2 regions for red
        self.assertIn("Regions: 2", content)
        
        # Verify it shows 1 region for lime
        lines = content.split('\n')
        lime_index = None
        for i, line in enumerate(lines):
            if 'lime' in line.lower():
                lime_index = i
                break
        
        self.assertIsNotNone(lime_index)
        assert lime_index is not None  # Type narrowing for Pyright
        # Find the "Regions:" line after the lime color
        found_regions = False
        for line in lines[lime_index:lime_index+5]:
            if "Regions: 1" in line:
                found_regions = True
                break
        self.assertTrue(found_regions)


class TestExtruderToAmsLocation(unittest.TestCase):
    """Test AMS location conversion function."""
    
    def test_extruder_1_maps_to_ams_a_slot_1(self):
        """Test that extruder 1 maps to AMS A, Slot 1."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(1, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'A')
        self.assertEqual(ams_slot, 1)
    
    def test_extruder_4_maps_to_ams_a_slot_4(self):
        """Test that extruder 4 maps to AMS A, Slot 4."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(4, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'A')
        self.assertEqual(ams_slot, 4)
    
    def test_extruder_5_maps_to_ams_b_slot_1(self):
        """Test that extruder 5 maps to AMS B, Slot 1."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(5, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'B')
        self.assertEqual(ams_slot, 1)
    
    def test_extruder_8_maps_to_ams_b_slot_4(self):
        """Test that extruder 8 maps to AMS B, Slot 4."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(8, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'B')
        self.assertEqual(ams_slot, 4)
    
    def test_extruder_9_maps_to_ams_c_slot_1(self):
        """Test that extruder 9 maps to AMS C, Slot 1."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(9, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'C')
        self.assertEqual(ams_slot, 1)
    
    def test_extruder_12_maps_to_ams_c_slot_4(self):
        """Test that extruder 12 maps to AMS C, Slot 4."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(12, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'C')
        self.assertEqual(ams_slot, 4)
    
    def test_extruder_13_maps_to_ams_d_slot_1(self):
        """Test that extruder 13 maps to AMS D, Slot 1."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(13, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'D')
        self.assertEqual(ams_slot, 1)
    
    def test_extruder_16_maps_to_ams_d_slot_4(self):
        """Test that extruder 16 maps to AMS D, Slot 4."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(16, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, 'D')
        self.assertEqual(ams_slot, 4)
    
    def test_invalid_extruder_0_returns_question_mark(self):
        """Test that extruder 0 returns '?' for invalid input."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(0, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, '?')
        self.assertEqual(ams_slot, 0)
    
    def test_invalid_extruder_17_returns_question_mark(self):
        """Test that extruder 17 returns '?' for invalid input."""
        from pixel_to_3mf.summary_writer import _extruder_to_ams_location
        ams_id, ams_slot = _extruder_to_ams_location(17, ams_count=4, ams_slots_per_unit=4)
        self.assertEqual(ams_id, '?')
        self.assertEqual(ams_slot, 17)


class TestSummaryWithAmsLocation(unittest.TestCase):
    """Test summary file generation includes AMS location information."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_files = []
    
    def tearDown(self):
        """Clean up test files."""
        for filepath in self.test_files:
            if os.path.exists(filepath):
                os.unlink(filepath)
    
    def test_summary_includes_ams_location_in_filament_mode(self):
        """Test that summary file includes AMS location information."""
        # Create a temporary 3MF file
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        # Create config
        config = ConversionConfig(color_naming_mode="filament")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 255, 255): 1,  # White backing - AMS A, Slot 1
            (255, 0, 0): 2,      # Red - AMS A, Slot 2
            (0, 255, 0): 5,      # Green - AMS B, Slot 1
            (0, 0, 255): 9,      # Blue - AMS C, Slot 1
        }
        
        # Write summary
        region_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        color_names = ["Bambu Lab PLA Basic Red", "Bambu Lab PLA Basic Green", "Bambu Lab PLA Basic Blue"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read and verify content
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify AMS location information is present
        self.assertIn("Location: 2 (AMS A, Slot 2)", content)
        self.assertIn("Location: 5 (AMS B, Slot 1)", content)
        self.assertIn("Location: 9 (AMS C, Slot 1)", content)
    
    def test_summary_includes_ams_location_in_hex_mode(self):
        """Test that summary file includes AMS location in hex mode."""
        # Create a temporary 3MF file
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        # Create config
        config = ConversionConfig(color_naming_mode="hex")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 255, 255): 1,  # White backing
            (255, 0, 0): 2,      # Red
        }
        
        # Write summary
        region_colors = [(255, 0, 0)]
        color_names = ["#FF0000"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read and verify content
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify AMS location information is present
        self.assertIn("Location: 2 (AMS A, Slot 2)", content)
    
    def test_summary_includes_ams_location_in_color_mode(self):
        """Test that summary file includes AMS location in color mode."""
        # Create a temporary 3MF file
        with NamedTemporaryFile(suffix='.3mf', delete=False) as tmp:
            output_path = tmp.name
            self.test_files.append(output_path)
        
        # Create config
        config = ConversionConfig(color_naming_mode="color")
        
        # Create color-to-slot mapping
        color_to_slot = {
            (255, 255, 255): 1,  # White backing
            (255, 0, 0): 13,     # Red - AMS D, Slot 1
        }
        
        # Write summary
        region_colors = [(255, 0, 0)]
        color_names = ["red"]
        
        summary_path = write_summary_file(output_path, region_colors, color_names, color_to_slot, config)
        self.test_files.append(summary_path)
        
        # Read and verify content
        with open(summary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify AMS location information is present
        self.assertIn("Location: 13 (AMS D, Slot 1)", content)


if __name__ == '__main__':
    unittest.main()

