"""
Core conversion logic for pixel art to 3MF.

This module contains the pure business logic for converting pixel art
images into 3MF files. It's completely separate from the CLI layer,
making it easy to use programmatically or test.

No print statements, no argparse, just clean conversion logic! 🎯
"""

import math
import os

from typing import Optional, Callable, Dict, Any
from pathlib import Path

from .image_processor import load_image
from .region_merger import merge_regions
from .mesh_generator import generate_region_mesh, generate_backing_plate
from .threemf_writer import write_3mf
from .config import ConversionConfig
from .constants import COORDINATE_PRECISION

def format_filesize(size_bytes: int) -> str:
    """
    Convert a file size in bytes to a human-readable format.
    
    Args:
        size_bytes: File size in bytes
    
    Returns:
        Formatted string like "1.5 KB", "2.3 MB", etc.
    
    Examples:
        >>> format_filesize(0)
        '0B'
        >>> format_filesize(1024)
        '1 KB'
        >>> format_filesize(1536)
        '1.5 KB'
    """
    if size_bytes == 0:
        return "0B"
    # Define the size units
    size_units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    # Calculate the logarithm base 1024 to find the correct unit index
    i = math.floor(math.log(size_bytes, 1024))
    # 'pow' is 1024 raised to the power of i
    p = math.pow(1024, i)
    # Divide the size in bytes by the appropriate power of 1024
    s = round(size_bytes / p, 2)
    # Return the formatted string
    return f"{s} {size_units[i]}"

def convert_image_to_3mf(
    input_path: str,
    output_path: str,
    config: Optional[ConversionConfig] = None,
    progress_callback: Optional[Callable[[str, str], None]] = None,
    warning_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None
) -> Dict[str, Any]:
    """
    Convert a pixel art image to a 3MF file.

    This is the main conversion function that orchestrates the entire process.
    It's designed to be called programmatically - no CLI stuff here!

    The process:
    1. Load and scale the image (largest dimension → max_size_mm exactly)
    2. Check if resolution is appropriate for the line width (interactive prompt if too high)
    3. Merge connected same-color pixels into regions
    4. Generate 3D meshes for each region + backing plate
    5. Export to 3MF with color names

    Args:
        input_path: Path to input image file
        output_path: Path where 3MF file should be written
        config: ConversionConfig object with all conversion parameters (uses defaults if None)
        progress_callback: Optional function to call with progress updates
                          Signature: callback(stage: str, message: str)
        warning_callback: Optional function to call for warnings that need user decision
                         Signature: callback(warning_type: str, data: Dict) -> bool
                         Should return True to continue, False to cancel

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
        ValueError: If parameters are invalid or resolution check fails
    """

    # Helper to send progress updates
    def _progress(stage: str, message: str):
        if progress_callback:
            progress_callback(stage, message)

    # Use default config if none provided
    if config is None:
        config = ConversionConfig()

    # Validate input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    # Config validates itself in __post_init__, so we don't need to validate parameters here
    
    # Step 1: Load and process image
    # Note: Auto-crop (if enabled) happens inside load_image() as part of the pipeline
    _progress("load", f"Loading image: {input_file.name}")
    pixel_data = load_image(str(input_path), config)

    _progress("load", f"Image loaded: {pixel_data.width}x{pixel_data.height}px, "
                     f"{round(pixel_data.pixel_size_mm, COORDINATE_PRECISION)}mm per pixel")

    # Check if resolution is too high for the line width
    max_dimension_px = max(pixel_data.width, pixel_data.height)
    max_recommended_px = int(config.max_size_mm / config.line_width_mm)
    
    if max_dimension_px > max_recommended_px:
        # Pixels are smaller than line width!
        
        if config.skip_checks:
            # Skip the check entirely - just continue silently
            pass
        elif config.batch_mode:
            # Batch mode - raise error immediately without prompting
            # The batch processor will catch this and skip the file
            raise ValueError(
                f"Image resolution too high for reliable printing. "
                f"Image: {pixel_data.width}x{pixel_data.height}px ({max_dimension_px}px max), "
                f"Recommended max: {max_recommended_px}px for {config.line_width_mm}mm line width. "
                f"Pixel size would be {pixel_data.pixel_size_mm:.3f}mm (smaller than line width)."
            )
        else:
            # Interactive mode - use callback to warn user
            if warning_callback:
                # Provide warning data to callback
                warning_data = {
                    'image_width': pixel_data.width,
                    'image_height': pixel_data.height,
                    'max_dimension_px': max_dimension_px,
                    'line_width_mm': config.line_width_mm,
                    'max_recommended_px': max_recommended_px,
                    'max_size_mm': config.max_size_mm,
                    'pixel_size_mm': pixel_data.pixel_size_mm
                }
                
                # Ask callback if we should continue
                should_continue = warning_callback('resolution_warning', warning_data)
                if not should_continue:
                    raise ValueError("Image resolution too high for specified line width")
            else:
                # No callback provided - raise error
                raise ValueError(
                    f"Image resolution too high for reliable printing. "
                    f"Image: {pixel_data.width}x{pixel_data.height}px ({max_dimension_px}px max), "
                    f"Recommended max: {max_recommended_px}px for {config.line_width_mm}mm line width. "
                    f"Pixel size would be {pixel_data.pixel_size_mm:.3f}mm (smaller than line width)."
                )
    
    # Step 2: Merge regions
    _progress("merge", "Merging connected pixels into regions...")
    regions = merge_regions(pixel_data, config)
    _progress("merge", f"Found {len(regions)} connected regions")
    
    # Step 3: Generate meshes
    _progress("mesh", "Generating 3D geometry...")
    meshes = []
    region_colors = []

    for i, region in enumerate(regions, start=1):
        _progress("mesh", f"Region {i}/{len(regions)}: {len(region.pixels)} pixels")
        mesh = generate_region_mesh(region, pixel_data, config)
        meshes.append((mesh, f"region_{i}"))
        region_colors.append(region.color)

    # Generate backing plate (if base_height > 0)
    if config.base_height_mm > 0:
        _progress("mesh", "Generating backing plate...")
        backing_mesh = generate_backing_plate(pixel_data, config)
        meshes.append((backing_mesh, "backing_plate"))
    else:
        _progress("mesh", "Skipping backing plate (base height is 0)")
    
    # Step 4: Write 3MF
    _progress("export", "Writing 3MF file...")
    summary_path = write_3mf(output_path, meshes, region_colors, pixel_data, config, progress_callback)
    _progress("export", f"3MF written to: {output_path}")
    
    # Return statistics
    stats = {
        'image_width': pixel_data.width,
        'image_height': pixel_data.height,
        'pixel_size_mm': pixel_data.pixel_size_mm,
        'model_width_mm': pixel_data.model_width_mm,
        'model_height_mm': pixel_data.model_height_mm,
        'num_pixels': len(pixel_data.pixels),
        'num_colors': len(pixel_data.get_unique_colors()),
        'num_regions': len(regions),
        'output_path': output_path,
        'file_size': format_filesize(os.path.getsize(output_path))
    }
    
    # Add summary path if generated
    if summary_path:
        stats['summary_path'] = summary_path
    
    return stats