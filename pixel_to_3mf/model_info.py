"""
Model information file writer and reader.

Writes .info.json files alongside 3MF output files containing:
- Colors and filament mappings used
- AMS slot assignments
- Model dimensions
- File hash for verification
- Conversion metadata

These files enable batch compatibility checking across multiple models.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from .json_utils import dumps_compact_arrays


def calculate_file_hash(filepath: str | Path) -> str:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        filepath: Path to file to hash
        
    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read in 64kb chunks for memory efficiency
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def write_model_info(
    output_path: str | Path,
    stats: Dict[str, Any],
    converter_version: str = "0.x.x"
) -> str:
    """
    Write model information file alongside the 3MF output.
    
    Creates a .info.json file containing colors, dimensions, and metadata
    that can be used for batch compatibility checking.
    
    Args:
        output_path: Path to the 3MF file that was written
        stats: Statistics dictionary from conversion (contains color_mapping, dimensions, etc.)
        converter_version: Version string of the converter
        
    Returns:
        Path to the written .info.json file
    """
    output_path = Path(output_path)
    
    # Create info file path: baby-yoda.3mf -> baby-yoda.info.json
    if output_path.suffix.lower() == '.3mf':
        info_path = output_path.with_suffix('.info.json')
    else:
        # Shouldn't happen, but handle it gracefully
        info_path = output_path.parent / (output_path.name + '.info.json')
    
    # Calculate hash of the 3MF file
    file_hash = calculate_file_hash(output_path)
    
    # Extract color information from stats
    # color_mapping is a list of (slot, name, rgb) tuples
    from .summary_writer import index_to_ams_slot
    from .config import ConversionConfig
    
    # Get AMS configuration from stats or use defaults
    config = stats.get('config')
    if config:
        ams_count = config.ams_count
        ams_slots_per_unit = config.ams_slots_per_unit
    else:
        # Fallback to defaults if config not in stats
        ams_count = 4
        ams_slots_per_unit = 4
    
    colors = []
    if 'color_mapping' in stats:
        for slot, color_name, rgb in stats['color_mapping']:
            # Convert 1-based slot to 0-based index for index_to_ams_slot
            slot_index = slot - 1
            ams_slot_name = index_to_ams_slot(slot_index, ams_count, ams_slots_per_unit)
            colors.append({
                'name': color_name,
                'hex': f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
                'rgb': list(rgb),
                'ams_slot': ams_slot_name
            })
    
    # Build info structure
    info = {
        'filename': output_path.name,
        'filepath': str(output_path.absolute()),
        'file_hash': file_hash,
        'timestamp': datetime.now().isoformat(),
        'converter_version': converter_version,
        'colors': colors,
        'model_dimensions': {
            'width_mm': stats.get('model_width_mm', 0),
            'height_mm': stats.get('model_height_mm', 0),
            'pixel_size_mm': stats.get('pixel_size_mm', 0)
        },
        'mesh_stats': {
            'num_vertices': stats.get('num_vertices', 0),
            'num_triangles': stats.get('num_triangles', 0),
            'num_regions': stats.get('num_regions', 0),
            'num_colors': stats.get('num_colors', 0)
        }
    }
    
    # Write JSON file with compact RGB arrays
    json_str = dumps_compact_arrays(info, indent=2, array_fields=['rgb'])
    
    with open(info_path, 'w', encoding='utf-8') as f:
        f.write(json_str)
    
    return str(info_path)


def read_model_info(info_path: str | Path) -> Dict[str, Any]:
    """
    Read a model information file.
    
    Args:
        info_path: Path to the .info.json file
        
    Returns:
        Dictionary containing model information
        
    Raises:
        FileNotFoundError: If info file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(info_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_model_info(info_path: str | Path) -> tuple[Dict[str, Any], bool, str]:
    """
    Read and verify a model information file against its 3MF file.
    
    Checks if the 3MF file still matches the recorded hash.
    
    Args:
        info_path: Path to the .info.json file
        
    Returns:
        Tuple of (info_dict, hash_valid, message)
        - info_dict: The loaded information
        - hash_valid: True if hash matches, False if file changed/missing
        - message: Human-readable status message
        
    Raises:
        FileNotFoundError: If info file doesn't exist
    """
    info = read_model_info(info_path)
    
    # Check if 3MF file exists
    model_path = Path(info['filepath'])
    if not model_path.exists():
        return info, False, f"3MF file not found at recorded location: {model_path}"
    
    # Calculate current hash
    current_hash = calculate_file_hash(model_path)
    recorded_hash = info['file_hash']
    
    if current_hash == recorded_hash:
        return info, True, "File hash matches - data is current"
    else:
        return info, False, "File has been modified since conversion - data may be stale"


def find_info_file_for_model(model_path: str | Path) -> Path | None:
    """
    Find the .info.json file for a given 3MF model file.
    
    Args:
        model_path: Path to the 3MF file
        
    Returns:
        Path to .info.json file if it exists, None otherwise
    """
    model_path = Path(model_path)
    
    # Expected location: baby-yoda.3mf -> baby-yoda.info.json
    if model_path.suffix.lower() == '.3mf':
        info_path = model_path.with_suffix('.info.json')
    else:
        info_path = model_path.parent / (model_path.name + '.info.json')
    
    return info_path if info_path.exists() else None
