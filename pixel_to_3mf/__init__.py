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

# Optimization statistics functions (only available if polygon_optimizer is installed)
try:
    from .polygon_optimizer import (
        reset_optimization_stats,
        get_optimization_stats,
        log_optimization_summary
    )
    _OPTIMIZATION_AVAILABLE = True
except ImportError:
    _OPTIMIZATION_AVAILABLE = False

__all__ = [
    "main",
    "convert_image_to_3mf",
    "ConversionConfig",
    "count_mesh_stats",
    "validate_triangle_winding"
]

# Add optimization stats functions to exports if available
if _OPTIMIZATION_AVAILABLE:
    __all__.extend([
        "reset_optimization_stats",
        "get_optimization_stats",
        "log_optimization_summary"
    ])
