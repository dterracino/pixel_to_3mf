"""
Pixel Art to 3MF Converter Package

Convert pixel art images into 3D printable 3MF files with automatic color
detection, region merging, and proper object naming for slicers.
"""

__version__ = "1.0.0"

# Make the CLI main function easily accessible
from .cli import main

# Core conversion function and configuration
from .pixel_to_3mf import convert_image_to_3mf
from .config import ConversionConfig

# Mesh utility functions for validation and statistics
from .threemf_writer import count_mesh_stats, validate_triangle_winding

__all__ = [
    "main",
    "convert_image_to_3mf",
    "ConversionConfig",
    "count_mesh_stats",
    "validate_triangle_winding"
]
