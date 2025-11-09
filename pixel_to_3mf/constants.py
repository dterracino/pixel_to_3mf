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

# Line width in millimeters (typical nozzle extrusion width)
# Used to calculate maximum recommended pixel resolution
# If pixels are smaller than this, printing may be unreliable
LINE_WIDTH_MM = 0.42

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
# Color Limits
# ============================================================================

# Maximum number of unique colors allowed in the input image
# Most slicers support 16 filaments max, and even that's a lot!
# This prevents accidentally converting huge photos with thousands of colors
MAX_COLORS = 16

# Default backing plate color (RGB tuple)
# If the image doesn't contain this color, we reserve one color slot for it
# This is typically white, but users can customize it via CLI
BACKING_COLOR = (255, 255, 255)  # White

# ============================================================================
# Padding
# ============================================================================

# Default padding size in pixels
# Padding creates an outline around non-transparent pixels to help with
# diagonally-connected pixels that can be problematic in 3D printing
PADDING_SIZE_PX = 5

# Default padding color (RGB tuple)
# White is a good default to create a visible border
PADDING_COLOR = (255, 255, 255)  # White

# ============================================================================
# Color Naming
# ============================================================================

# Color naming mode - how to name objects in the 3MF file
# - "color": Use nearest CSS color name (e.g., "red", "coral")
# - "filament": Use nearest filament name based on filters (e.g., "Bambu Lab PLA Basic Red")
# - "hex": Use hex color code (e.g., "#FF5733")
COLOR_NAMING_MODE = "filament"

# Default filament filters when using filament mode
DEFAULT_FILAMENT_MAKER = "Bambu Lab"
DEFAULT_FILAMENT_TYPE = "PLA"
DEFAULT_FILAMENT_FINISH = ["Basic", "Matte"]  # Multiple finishes allowed

# ============================================================================
# Color Quantization
# ============================================================================

# Whether to enable automatic color quantization when image has too many colors
ENABLE_QUANTIZATION = False

# Quantization algorithm - "none" for simple nearest color, "floyd" for Floyd-Steinberg dithering
QUANTIZATION_ALGORITHM = "none"

# Number of colors to quantize to (defaults to MAX_COLORS if not specified)
# Only used when quantization is enabled
QUANTIZATION_COLORS = None

# ============================================================================
# Batch Processing
# ============================================================================

# Supported image file extensions for batch processing
# These are the formats PIL/Pillow can reliably load
# This is not user-configurable - if we add support for new formats (like HEIC, AVIF),
# we just update this list here
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# ============================================================================
# Geometry Processing
# ============================================================================

# Trim disconnected pixels (pixels connected only via corner/diagonal)
# These pixels are unreliable for 3D printing as they only share a vertex
# with neighboring pixels, not an edge
TRIM_DISCONNECTED_PIXELS = False

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