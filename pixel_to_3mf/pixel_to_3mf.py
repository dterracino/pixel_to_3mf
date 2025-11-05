"""
Core conversion logic for pixel art to 3MF.

This module contains the pure business logic for converting pixel art
images into 3MF files. It's completely separate from the CLI layer,
making it easy to use programmatically or test.

No print statements, no argparse, just clean conversion logic! 🎯
"""

from typing import Optional, Callable, Dict, Any
from pathlib import Path

from .image_processor import load_image
from .region_merger import merge_regions
from .mesh_generator import generate_region_mesh, generate_backing_plate
from .threemf_writer import write_3mf
from .constants import (
    MAX_MODEL_SIZE_MM,
    PIXEL_ROUNDING_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
)


def convert_image_to_3mf(
    input_path: str,
    output_path: str,
    max_size_mm: float = MAX_MODEL_SIZE_MM,
    pixel_rounding_mm: float = PIXEL_ROUNDING_MM,
    color_height_mm: float = COLOR_LAYER_HEIGHT_MM,
    base_height_mm: float = BASE_LAYER_HEIGHT_MM,
    progress_callback: Optional[Callable[[str, str], None]] = None
) -> Dict[str, Any]:
    """
    Convert a pixel art image to a 3MF file.
    
    This is the main conversion function that orchestrates the entire process.
    It's designed to be called programmatically - no CLI stuff here!
    
    The process:
    1. Load and scale the image
    2. Merge connected same-color pixels into regions
    3. Generate 3D meshes for each region + backing plate
    4. Export to 3MF with color names
    
    Args:
        input_path: Path to input image file
        output_path: Path where 3MF file should be written
        max_size_mm: Maximum model dimension in millimeters
        pixel_rounding_mm: Round pixel size to nearest multiple of this
        color_height_mm: Height of colored layer in millimeters
        base_height_mm: Height of backing plate in millimeters
        progress_callback: Optional function to call with progress updates
                          Signature: callback(stage: str, message: str)
    
    Returns:
        Dictionary with conversion statistics:
        {
            'image_width': int,
            'image_height': int,
            'pixel_size_mm': float,
            'model_width_mm': float,
            'model_height_mm': float,
            'num_pixels': int,
            'num_colors': int,
            'num_regions': int,
            'output_path': str
        }
    
    Raises:
        FileNotFoundError: If input image doesn't exist
        IOError: If image can't be loaded or 3MF can't be written
        ValueError: If parameters are invalid
    """
    
    # Helper to send progress updates
    def _progress(stage: str, message: str):
        if progress_callback:
            progress_callback(stage, message)
    
    # Validate input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    
    # Validate parameters
    if max_size_mm <= 0:
        raise ValueError(f"max_size_mm must be positive, got {max_size_mm}")
    if pixel_rounding_mm <= 0:
        raise ValueError(f"pixel_rounding_mm must be positive, got {pixel_rounding_mm}")
    if color_height_mm <= 0:
        raise ValueError(f"color_height_mm must be positive, got {color_height_mm}")
    if base_height_mm <= 0:
        raise ValueError(f"base_height_mm must be positive, got {base_height_mm}")
    
    # Step 1: Load and process image
    _progress("load", f"Loading image: {input_file.name}")
    pixel_data = load_image(
        str(input_path),
        max_size_mm=max_size_mm,
        rounding_mm=pixel_rounding_mm
    )
    
    _progress("load", f"Image loaded: {pixel_data.width}x{pixel_data.height}px, "
                     f"{pixel_data.pixel_size_mm}mm per pixel")
    
    # Step 2: Merge regions
    _progress("merge", "Merging connected pixels into regions...")
    regions = merge_regions(pixel_data)
    _progress("merge", f"Found {len(regions)} connected regions")
    
    # Step 3: Generate meshes
    _progress("mesh", "Generating 3D geometry...")
    meshes = []
    region_colors = []
    
    for i, region in enumerate(regions, start=1):
        _progress("mesh", f"Region {i}/{len(regions)}: {len(region.pixels)} pixels")
        mesh = generate_region_mesh(region, pixel_data, layer_height=color_height_mm)
        meshes.append((mesh, f"region_{i}"))
        region_colors.append(region.color)
    
    # Generate backing plate
    _progress("mesh", "Generating backing plate...")
    backing_mesh = generate_backing_plate(pixel_data, base_height=base_height_mm)
    meshes.append((backing_mesh, "backing_plate"))
    
    # Step 4: Write 3MF
    _progress("export", "Writing 3MF file...")
    write_3mf(output_path, meshes, region_colors)
    _progress("export", f"3MF written to: {output_path}")
    
    # Return statistics
    return {
        'image_width': pixel_data.width,
        'image_height': pixel_data.height,
        'pixel_size_mm': pixel_data.pixel_size_mm,
        'model_width_mm': pixel_data.model_width_mm,
        'model_height_mm': pixel_data.model_height_mm,
        'num_pixels': len(pixel_data.pixels),
        'num_colors': len(pixel_data.get_unique_colors()),
        'num_regions': len(regions),
        'output_path': output_path
    }
