"""
Color science tools for matching, conversion, and analysis.

A comprehensive toolkit for working with colors in multiple color spaces,
finding nearest color matches, and working with 3D printing filament colors.

Quick Start:
    >>> from color_tools import rgb_to_lab, delta_e_2000, Palette
    >>> 
    >>> # Convert RGB to LAB
    >>> lab = rgb_to_lab((255, 128, 64))
    >>> 
    >>> # Find nearest CSS color
    >>> palette = Palette.load_default()
    >>> nearest, distance = palette.nearest_color(lab)
    >>> print(f"Nearest color: {nearest.name}")

Three Ways to Use:
    1. As a library: from color_tools import rgb_to_lab
    2. As a CLI tool: python -m color_tools color --name coral
    3. As installed command: color_tools filament --list-makers (needs pip install)
"""

__version__ = "1.0.0"

# ============================================================================
# Core Conversion Functions (Most Commonly Used)
# ============================================================================

from .conversions import (
    # Hex ↔ RGB (basic web colors)
    hex_to_rgb,
    rgb_to_hex,
    
    # RGB ↔ LAB (the main event!)
    rgb_to_lab,
    lab_to_rgb,
    
    # RGB ↔ LCH (cylindrical LAB - great for hue/chroma work)
    rgb_to_lch,
    lch_to_rgb,
    
    # LAB ↔ LCH (convert between rectangular and cylindrical)
    lab_to_lch,
    lch_to_lab,
    
    # RGB ↔ XYZ (the universal translator)
    rgb_to_xyz,
    xyz_to_rgb,
    
    # XYZ ↔ LAB (for power users)
    xyz_to_lab,
    lab_to_xyz,
    
    # RGB ↔ HSL (common web dev color space)
    rgb_to_hsl,
    hsl_to_rgb,
    rgb_to_winhsl,  # Windows HSL (0-240 range)
)

# ============================================================================
# Distance Metrics (Color Difference Formulas)
# ============================================================================

from .distance import (
    # The main Delta E formulas
    delta_e_2000,   # 👈 Use this one! Gold standard
    delta_e_94,
    delta_e_76,
    delta_e_cmc,
    
    # Simple distance functions
    euclidean,
    hsl_euclidean,
)

# ============================================================================
# Gamut Operations (Can Your Monitor Show This Color?)
# ============================================================================

from .gamut import (
    is_in_srgb_gamut,
    find_nearest_in_gamut,
    clamp_to_gamut,
)

# ============================================================================
# Palettes & Data Classes (The Search Engine!)
# ============================================================================

from .palette import (
    # Main palette classes
    Palette,
    FilamentPalette,
    
    # Data classes
    ColorRecord,
    FilamentRecord,
    
    # Loading functions
    load_colors,
    load_filaments,
)

# ============================================================================
# Configuration (Usually Don't Need These Directly)
# ============================================================================

from .config import (
    set_dual_color_mode,
    get_dual_color_mode,
)

# ============================================================================
# Submodules Available for Import
# ============================================================================
# Power users can access these for advanced features:
#   from color_tools import constants    # ColorConstants class
#   from color_tools import config       # All config functions
#   from color_tools import conversions  # All conversion functions
#   from color_tools import distance     # All distance functions
#   from color_tools import gamut        # All gamut functions
#   from color_tools import palette      # Everything palette-related

# ============================================================================
# Public API Definition
# ============================================================================

__all__ = [
    # Version
    "__version__",
    
    # Conversion functions (most commonly used)
    "hex_to_rgb",
    "rgb_to_hex",
    "rgb_to_lab",
    "lab_to_rgb",
    "rgb_to_lch",
    "lch_to_rgb",
    "lab_to_lch",
    "lch_to_lab",
    "rgb_to_xyz",
    "xyz_to_rgb",
    "xyz_to_lab",
    "lab_to_xyz",
    "rgb_to_hsl",
    "hsl_to_rgb",
    "rgb_to_winhsl",
    
    # Distance metrics
    "delta_e_2000",
    "delta_e_94",
    "delta_e_76",
    "delta_e_cmc",
    "euclidean",
    "hsl_euclidean",
    
    # Gamut operations
    "is_in_srgb_gamut",
    "find_nearest_in_gamut",
    "clamp_to_gamut",
    
    # Palettes and data classes
    "Palette",
    "FilamentPalette",
    "ColorRecord",
    "FilamentRecord",
    "load_colors",
    "load_filaments",
    
    # Config functions
    "set_dual_color_mode",
    "get_dual_color_mode",
]