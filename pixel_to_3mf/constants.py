"""
Configuration constants for pixel art to 3MF conversion.

All the magic numbers live here! Want to change your defaults? 
Just edit these values and all your conversions will use the new settings.
No hunting through code required! 🎯
"""

# ============================================================================
# Version Information
# ============================================================================

# Semantic version of the converter
__version__ = "1.0.0"

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

# Height of the solid core layer in millimeters (when --solid-core is enabled)
# The solid core is a single object spanning the full model footprint sandwiched
# between two thin color shells. It lets you print the bulk of the model in one
# filament quickly and only swap filaments for the thin visible color surfaces.
SOLID_CORE_HEIGHT_MM = 1.0

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
# 0 = disabled (default), >0 = padding size in pixels
PADDING_SIZE_PX = 0

# Default padding color (RGB tuple)
# White is a good default to create a visible border
PADDING_COLOR = (255, 255, 255)  # White

# Default padding type - determines the shape of the padding outline
# - "circular": Euclidean distance, smooth rounded corners
# - "square": Chebyshev distance, sharp 90° corners (perfect for framing)
# - "diamond": Manhattan distance, 45° diagonal cuts
PADDING_TYPE_DEFAULT = "circular"

# TODO: Add --padding-ignore-holes flag to only pad outer edges,
#       not internal transparent areas (useful for cutout designs)

# ============================================================================
# Color Naming
# ============================================================================

# Color naming mode - how to name objects in the 3MF file
# - "color": Use nearest CSS color name (e.g., "red", "coral")
# - "filament": Use nearest filament name based on filters (e.g., "Bambu Lab PLA Basic Red")
# - "hex": Use hex color code (e.g., "#FF5733")
# - "generated": Use descriptive generated names (e.g., "very dark blue", "medium bright blue")
COLOR_NAMING_MODE = "filament"

# Merge similar colors to same filament
# When True (default): Multiple RGB colors can map to same filament name (they share AMS slot)
# When False: Each unique RGB color gets unique filament assignment (greedy matching)
# Use False to preserve subtle color variations in images with many similar shades
MERGE_SIMILAR_COLORS = True

# Default filament filters when using filament mode
DEFAULT_FILAMENT_MAKER = "Bambu Lab"
DEFAULT_FILAMENT_TYPE = "PLA"
DEFAULT_FILAMENT_FINISH = ["Basic", "Matte"]  # Multiple finishes allowed

# Hue-aware matching: prioritizes hue preservation over pure perceptual distance
# When True, penalizes hue shifts to avoid mapping blue→purple, red→orange, etc.
PREFER_HUE_MATCHING = True

# RGB-based boundary detection for blue/purple distinction
# This is a workaround for filament palettes with gaps between blue and purple
# Uses red component analysis: R < 50 = blue, R > 80 = purple, 50-80 = boundary zone
# Disable if your palette has good coverage and you want pure Delta E matching
USE_RGB_BOUNDARY_DETECTION = True

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
# AMS Configuration
# ============================================================================

# Number of AMS units (Automatic Material System)
# Each Bambu Lab AMS unit holds 4 spools, and you can chain up to 4 units
# Default is 4 units (maximum configuration = 16 total slots)
AMS_COUNT = 4

# Number of filament slots per AMS unit
# Each Bambu Lab AMS unit holds exactly 4 spools
AMS_SLOTS_PER_UNIT = 4

# ============================================================================
# Geometry Processing
# ============================================================================

# Trim disconnected pixels (pixels connected only via corner/diagonal)
# These pixels are unreliable for 3D printing as they only share a vertex
# with neighboring pixels, not an edge
TRIM_DISCONNECTED_PIXELS = False

# Minimum region size for blob denoising (0 = disabled).
# Any connected same-colour region with fewer than this many pixels is merged
# into its dominant neighbour colour.  Removes compression artefacts and stray
# pixels before region merging, reducing the final 3MF region count.
# Empirical sweet spot for pixel art: 2 (Score 0.870, ~51% region reduction,
# only 6.2% of pixels changed).
DENOISE_MIN_SIZE = 0

# ============================================================================
# Boundary Smoothing
# ============================================================================

# Enable smooth boundary mode (disabled by default — existing pixel-art mesh
# path is used unless --smooth is passed on the CLI).
SMOOTH_BOUNDARIES = False

# RDP (Ramer-Douglas-Peucker) simplification tolerance in pixels.
# Lower = more detail preserved; higher = smoother / fewer vertices.
SMOOTH_SIMPLIFY_TOLERANCE = 0.5

# Number of Chaikin corner-cutting iterations applied after RDP simplification.
# Each iteration halves the polygon vertex count and rounds corners.
# 0 = no smoothing; 1–4 practical range; 2 is a good default.
SMOOTH_CHAIKIN_ITERATIONS = 2

# ============================================================================
# Output Generation
# ============================================================================

# Generate color swatches image showing each color with its name/hex code
GENERATE_SWATCHES = False

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