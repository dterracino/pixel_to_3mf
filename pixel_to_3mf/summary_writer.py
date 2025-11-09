"""
Summary file writer module.

This module handles the generation of summary files that list the filaments
or colors used in a 3MF conversion. The summary is written as a plain text
file alongside the output 3MF file.
"""

from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING

from color_tools import rgb_to_hex

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig


def write_summary_file(
    output_path: str,
    region_colors: List[Tuple[int, int, int]],
    color_names: List[str],
    config: 'ConversionConfig'
) -> str:
    """
    Write a summary file listing the colors/filaments used in the conversion.
    
    The summary file is written to the same location as the output 3MF file
    with the name pattern: {filetitle}.summary.txt
    
    Args:
        output_path: Path to the output 3MF file
        region_colors: List of RGB tuples for each region
        color_names: List of color/filament names (already resolved by get_color_name)
        config: ConversionConfig with color_naming_mode
    
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
            
            lines.append(f"{i}. {filament_name}")
            lines.append(f"   Hex: {hex_code}")
            lines.append(f"   RGB: {rgb}")
            lines.append(f"   Regions: {region_count}")
            lines.append("")
    
    elif config.color_naming_mode == "hex":
        lines.append("Colors Used (Hex):")
        lines.append("-" * 70)
        lines.append("")
        
        for i, (hex_code, rgb_list) in enumerate(sorted_colors, start=1):
            rgb = rgb_list[0]
            region_count = len(rgb_list)
            
            lines.append(f"{i}. {hex_code}")
            lines.append(f"   RGB: {rgb}")
            lines.append(f"   Regions: {region_count}")
            lines.append("")
    
    else:  # "color" mode (CSS color names)
        lines.append("Colors Used:")
        lines.append("-" * 70)
        lines.append("")
        
        for i, (color_name, rgb_list) in enumerate(sorted_colors, start=1):
            rgb = rgb_list[0]
            hex_code = rgb_to_hex(rgb)
            region_count = len(rgb_list)
            
            lines.append(f"{i}. {color_name}")
            lines.append(f"   Hex: {hex_code}")
            lines.append(f"   RGB: {rgb}")
            lines.append(f"   Regions: {region_count}")
            lines.append("")
    
    lines.append("=" * 70)
    
    # Write the summary file
    summary_path.write_text('\n'.join(lines), encoding='utf-8')
    
    return str(summary_path)
