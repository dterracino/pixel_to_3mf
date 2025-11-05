"""
Pixel Art to 3MF Converter Package

Convert pixel art images into 3D printable 3MF files with automatic color
detection, region merging, and proper object naming for slicers.
"""

__version__ = "1.0.0"

# Make the main function easily accessible
from .pixel_to_3mf import main

__all__ = ["main"]
