"""
Configuration constants for pixel art to 3MF conversion.

All the magic numbers live here! Want to change your defaults? 
Just edit these values and all your conversions will use the new settings.
No hunting through code required! 🎯
"""

# ============================================================================
# Print Bed & Scaling
# ============================================================================

# Maximum dimension (width or height) for the output model in millimeters
# This is typically your print bed size - we'll scale the model so the 
# longest dimension fits within this limit
MAX_MODEL_SIZE_MM = 200.0

# Pixel size rounding increment in millimeters
# After calculating the ideal pixel size, we round to the nearest multiple
# of this value to get nice round numbers (e.g., 3.125mm → 3.0mm)
PIXEL_ROUNDING_MM = 0.5

# ============================================================================
# Layer Heights
# ============================================================================

# Height of the colored top layer in millimeters
# Each colored region gets extruded to this height
COLOR_LAYER_HEIGHT_MM = 1.0

# Height of the backing plate in millimeters
# This is the solid base layer that spans the entire model
BASE_LAYER_HEIGHT_MM = 1.0

# ============================================================================
# 3MF File Generation
# ============================================================================

# Default output filename suffix
# If no output file is specified, we'll use: {input_name}_model.3mf
DEFAULT_OUTPUT_SUFFIX = "_model"

# Decimal places for coordinate precision in 3MF file
# More precision = larger files, but we don't need sub-micron accuracy!
# 3 decimal places = 0.001mm precision, which is way more than enough
COORDINATE_PRECISION = 3
