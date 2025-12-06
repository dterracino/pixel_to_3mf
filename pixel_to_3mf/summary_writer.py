"""
Summary file writer module.

This module handles the generation of summary files that list the filaments
or colors used in a 3MF conversion. The summary is written as a plain text
file alongside the output 3MF file.
"""

from pathlib import Path
from typing import List, Tuple, Dict, TYPE_CHECKING

from color_tools import rgb_to_hex

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig


def index_to_ams_slot(index: int, ams_count: int, ams_slots_per_unit: int) -> str:
    """
    Convert a 0-based slot index to AMS slot name.
    
    Index mapping (example with 4 units, 4 slots per unit):
    - Index 0:  A-1
    - Index 1:  A-2
    - Index 3:  A-4
    - Index 4:  B-1
    - Index 15: D-4
    
    Args:
        index: 0-based slot index (0 to ams_count * ams_slots_per_unit - 1)
        ams_count: Number of AMS units (1-4)
        ams_slots_per_unit: Number of slots per AMS unit (typically 4)
    
    Returns:
        AMS slot name (e.g., "A-1", "B-3", "D-4")
        
        If index is out of range, returns "?-{index}"
    """
    max_slots = ams_count * ams_slots_per_unit
    if index < 0 or index >= max_slots:
        return f"?-{index}"
    
    # Calculate AMS unit (A, B, C, D, ...) and slot within unit
    ams_index = index // ams_slots_per_unit
    slot_number = (index % ams_slots_per_unit) + 1
    
    ams_id = chr(ord('A') + ams_index)
    return f"{ams_id}-{slot_number}"


def _extruder_to_ams_location(extruder: int, ams_count: int, ams_slots_per_unit: int) -> Tuple[str, int]:
    """
    Convert an extruder number to AMS location.
    
    Extruder mapping (example with 4 units, 4 slots per unit):
    - Extruders 1-4:   AMS A, Slot 1-4
    - Extruders 5-8:   AMS B, Slot 1-4
    - Extruders 9-12:  AMS C, Slot 1-4
    - Extruders 13-16: AMS D, Slot 1-4
    
    Args:
        extruder: Extruder number (1 to ams_count * ams_slots_per_unit)
        ams_count: Number of AMS units (1-4)
        ams_slots_per_unit: Number of slots per AMS unit (typically 4)
    
    Returns:
        Tuple of (ams_id, ams_slot) where:
        - ams_id is a letter 'A', 'B', 'C', 'D', etc.
        - ams_slot is a number 1 to ams_slots_per_unit
        
        If extruder is out of range, returns ('?', extruder)
    """
    max_extruders = ams_count * ams_slots_per_unit
    if extruder < 1 or extruder > max_extruders:
        return ('?', extruder)
    
    # Calculate AMS unit (A, B, C, D, ...) and slot within unit
    ams_index = (extruder - 1) // ams_slots_per_unit
    ams_slot = ((extruder - 1) % ams_slots_per_unit) + 1
    
    ams_id = chr(ord('A') + ams_index)
    
    return (ams_id, ams_slot)


def write_summary_file(
    output_path: str,
    region_colors: List[Tuple[int, int, int]],
    color_names: List[str],
    color_to_slot: Dict[Tuple[int, int, int], int],
    config: 'ConversionConfig',
    has_backing_plate: bool = False
) -> str:
    """
    Write a summary file listing the colors/filaments used in the conversion.
    
    The summary file is written to the same location as the output 3MF file
    with the name pattern: {filetitle}.summary.txt
    
    Args:
        output_path: Path to the output 3MF file
        region_colors: List of RGB tuples for each region
        color_names: List of color/filament names (already resolved by get_color_name)
        color_to_slot: Mapping of RGB colors to AMS slot numbers (1-16)
        config: ConversionConfig with color_naming_mode
        has_backing_plate: Whether a backing plate was generated
    
    Returns:
        Path to the generated summary file
    """
    # Determine summary file path
    output_file = Path(output_path)
    summary_path = output_file.with_suffix('.summary.txt')
    
    # Build summary content
    lines = []
    lines.append("=" * 70)
    lines.append("3MF Conversion Summary")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"3MF File: {output_file.name}")
    lines.append(f"Total Colors/Regions: {len(region_colors)}")
    lines.append(f"Color Naming Mode: {config.color_naming_mode}")
    lines.append("")
    
    # Group by color name to show unique colors
    # Create a dict of {color_name: [rgb_tuples]}
    color_groups = {}
    for rgb, name in zip(region_colors, color_names):
        if name not in color_groups:
            color_groups[name] = []
        color_groups[name].append(rgb)
    
    # Sort by color name for consistent output
    sorted_colors = sorted(color_groups.items())
    
    if config.color_naming_mode == "filament":
        lines.append("Filaments Used:")
        lines.append("-" * 70)
        lines.append("")
        
        for i, (filament_name, rgb_list) in enumerate(sorted_colors, start=1):
            # Use the first RGB value (all should be same for same name)
            rgb = rgb_list[0]
            hex_code = rgb_to_hex(rgb)
            region_count = len(rgb_list)
            
            # Check if this is the backing color AND we have a backing plate
            is_backing_color = (rgb == config.backing_color)
            
            # Get AMS slot assignment
            extruder = color_to_slot.get(rgb, 0)
            ams_id, ams_slot = _extruder_to_ams_location(extruder, config.ams_count, config.ams_slots_per_unit)
            
            lines.append(f"{i}. {filament_name}")
            lines.append(f"   Hex: {hex_code}")
            lines.append(f"   RGB: {rgb}")
            
            # Show region breakdown if this is backing color AND we generated a backing plate
            if is_backing_color and has_backing_plate and config.base_height_mm > 0:
                # Last occurrence in rgb_list is the backing plate (we appended it in threemf_writer)
                # All other occurrences are color layer regions
                backing_regions = 1
                color_regions = region_count - 1
                lines.append(f"   Regions: {region_count} ({color_regions} color layer, {backing_regions} backing plate)")
            else:
                lines.append(f"   Regions: {region_count}")
            
            lines.append(f"   Location: {extruder} (AMS {ams_id}, Slot {ams_slot})")
            lines.append("")
    
    elif config.color_naming_mode == "hex":
        lines.append("Colors Used (Hex):")
        lines.append("-" * 70)
        lines.append("")
        
        for i, (hex_code, rgb_list) in enumerate(sorted_colors, start=1):
            rgb = rgb_list[0]
            region_count = len(rgb_list)
            
            # Check if this is the backing color AND we have a backing plate
            is_backing_color = (rgb == config.backing_color)
            
            # Get AMS slot assignment
            extruder = color_to_slot.get(rgb, 0)
            ams_id, ams_slot = _extruder_to_ams_location(extruder, config.ams_count, config.ams_slots_per_unit)
            
            lines.append(f"{i}. {hex_code}")
            lines.append(f"   RGB: {rgb}")
            
            # Show region breakdown if this is backing color AND we generated a backing plate
            if is_backing_color and has_backing_plate and config.base_height_mm > 0:
                backing_regions = 1
                color_regions = region_count - 1
                lines.append(f"   Regions: {region_count} ({color_regions} color layer, {backing_regions} backing plate)")
            else:
                lines.append(f"   Regions: {region_count}")
            
            lines.append(f"   Location: {extruder} (AMS {ams_id}, Slot {ams_slot})")
            lines.append("")
    
    else:  # "color" mode (CSS color names)
        lines.append("Colors Used:")
        lines.append("-" * 70)
        lines.append("")
        
        for i, (color_name, rgb_list) in enumerate(sorted_colors, start=1):
            rgb = rgb_list[0]
            hex_code = rgb_to_hex(rgb)
            region_count = len(rgb_list)
            
            # Check if this is the backing color AND we have a backing plate
            is_backing_color = (rgb == config.backing_color)
            
            # Get AMS slot assignment
            extruder = color_to_slot.get(rgb, 0)
            ams_id, ams_slot = _extruder_to_ams_location(extruder, config.ams_count, config.ams_slots_per_unit)
            
            lines.append(f"{i}. {color_name}")
            lines.append(f"   Hex: {hex_code}")
            lines.append(f"   RGB: {rgb}")
            
            # Show region breakdown if this is backing color AND we generated a backing plate
            if is_backing_color and has_backing_plate and config.base_height_mm > 0:
                backing_regions = 1
                color_regions = region_count - 1
                lines.append(f"   Regions: {region_count} ({color_regions} color layer, {backing_regions} backing plate)")
            else:
                lines.append(f"   Regions: {region_count}")
            
            lines.append(f"   Location: {extruder} (AMS {ams_id}, Slot {ams_slot})")
            lines.append("")
    
    lines.append("=" * 70)
    
    # Write the summary file
    summary_path.write_text('\n'.join(lines), encoding='utf-8')
    
    return str(summary_path)
