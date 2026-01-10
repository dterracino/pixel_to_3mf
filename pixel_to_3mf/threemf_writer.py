"""
3MF file writer module - Pixel art specific implementation.

This module provides pixel art specific 3MF export functionality built on top
of the generic threemf_core module. It handles:

1. Color naming (CSS colors, filament matching, hex codes)
2. AMS slot assignment based on color grouping
3. Model centering and positioning
4. Pixel art thumbnail generation
5. Summary file generation

The write_3mf() function is the main entry point and maintains backward
compatibility with the original API. It uses ThreeMFWriter from threemf_core
with pixel art specific callbacks.

For reusable 3MF writing in other applications, use threemf_core directly!
"""

from typing import List, Tuple, Dict, TYPE_CHECKING, Optional, Callable, Any
from pathlib import Path
from PIL import Image
from functools import lru_cache
import colorsys
import math

from .mesh_generator import Mesh
from .threemf_core import ThreeMFWriter, ThreeMFMesh
from color_tools import Palette, FilamentPalette, rgb_to_lab, rgb_to_hex

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .image_processor import PixelData
    from .config import ConversionConfig

# ============================================================================
# Color Naming Functions (Pixel Art Specific)
# ============================================================================

# TODO: This hue-aware matching should be moved to color-tools library
# The color-tools library currently only provides Delta E 2000 matching,
# which prioritizes perceptual distance over hue preservation. This can
# cause undesirable matches like blue→purple when no perfect match exists.
# A hue-weighted matching metric should be added to color-tools.

def _get_color_category(hue: float, saturation: float) -> str:
    """
    Determine the color category based on HSL hue value.
    
    This helps prevent categorical mismatches like blue→purple.
    Categories are based on standard hue ranges in the HSL color wheel.
    
    Args:
        hue: Hue value in [0, 1] range (0=red, 0.333=green, 0.667=blue)
        saturation: Saturation in [0, 1] range (used to detect grays)
        
    Returns:
        Color category: 'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 
        'purple', 'magenta', or 'gray'
    """
    # Desaturated colors are gray regardless of hue
    if saturation < 0.15:
        return 'gray'
    
    # Convert hue to degrees for easier reasoning
    hue_deg = hue * 360
    
    # Define category boundaries (degrees)
    if hue_deg < 15 or hue_deg >= 345:
        return 'red'
    elif hue_deg < 45:
        return 'orange'
    elif hue_deg < 75:
        return 'yellow'
    elif hue_deg < 150:
        return 'green'
    elif hue_deg < 195:
        return 'cyan'
    elif hue_deg < 270:
        return 'blue'
    elif hue_deg < 315:
        return 'purple'
    else:
        return 'magenta'


def _rgb_to_blue_purple_category(rgb: Tuple[int, int, int]) -> str | None:
    """
    Determine if an RGB color is blue, purple, or boundary zone based on RGB components.
    
    TODO: This function should be moved to color-tools library.
    
    Uses RGB component analysis to categorize colors in the blue/purple range:
    - **Blue**: Low red component (R < 50), high blue (B > 150)
    - **Purple**: Significant red component (R > 80), high blue (B > 150)
      - Purple in RGB = Red + Blue, so purple has more red than pure blue
    - **Boundary zone**: 50 ≤ R ≤ 80, can match either
    - **None**: Not in blue/purple range (B < 150)
    
    This is more robust than string matching on filament names, which breaks
    for names like "Ocean", "Sky", "Lavender", "Violet", etc.
    
    Args:
        rgb: RGB tuple (0-255 for each component)
        
    Returns:
        'blue', 'purple', 'boundary', or None
    """
    r, g, b = rgb
    
    # Must have significant blue component to be in this range
    if b < 150:
        return None
    
    # Distinguish based on red component
    # Purple = Red + Blue in RGB, so purple has more red
    BLUE_MAX_RED = 50  # Blue should have R < 50
    PURPLE_MIN_RED = 80  # Purple should have R > 80
    
    if r < BLUE_MAX_RED:
        return 'blue'
    elif r > PURPLE_MIN_RED:
        return 'purple'
    else:
        return 'boundary'  # 50 <= R <= 80, could be either


def _calculate_hue_weighted_distance(
    target_rgb: Tuple[int, int, int],
    candidate_rgb: Tuple[int, int, int],
    candidate_name: str,
    base_delta_e: float,
    use_rgb_boundary_detection: bool = True,
    category_mismatch_penalty: float = 50.0
) -> float:
    """
    Calculate distance with smart category mismatch penalty based on RGB composition.
    
    TODO: This entire function should be moved to color-tools library.
          It's a workaround for filament palette gaps and should be part of
          the palette matching logic, not the 3MF writer.
    
    IMPORTANT: This is a workaround for filament palettes with gaps!
    ---------------------------------------------------------------------------
    When a palette lacks intermediate colors (e.g., Bambu Lab has Purple #5E43B7
    and Blue #0A2989, but no colors between), pure Delta E 2000 can match colors
    across categorical boundaries. For example:
    
    - Pure blue #0000FF might match to purple (ΔE=14.37) instead of darker blue (ΔE=15.04)
    - Bluish-purple #686CE8 might match to blue when it should match purple
    
    This function uses RGB component analysis to detect these boundary cases:
    - **Blue**: Low red component (R < 50), high blue (B > 150)
    - **Purple**: Significant red component (R > 80), high blue (B > 150)
    - **Boundary zone**: 50 ≤ R ≤ 80 can match either (decided by Delta E)
    
    The penalty is applied when:
    1. use_rgb_boundary_detection is enabled
    2. BOTH target and candidate are in blue/purple range (B > 150)
    3. Target clearly leans toward one category (R < 50 or R > 80)
    4. Candidate clearly leans toward the opposite category
    
    This means:
    - Works for ANY filament naming scheme (no string matching!)
    - Other palettes with better coverage are unaffected
    - Non-blue/purple colors work normally
    - Boundary zone colors still use pure Delta E
    
    Args:
        target_rgb: Target color to match
        candidate_rgb: Candidate color from palette
        candidate_name: Name of the candidate filament (unused after refactor, kept for compatibility)
        base_delta_e: Already-calculated Delta E 2000 distance
        use_rgb_boundary_detection: Enable RGB component analysis (default True)
        category_mismatch_penalty: Penalty for matching across categories (default 50.0)
        
    Returns:
        Weighted distance combining Delta E and category mismatch penalty
    """
    # TODO: Move to color-tools library as part of palette.find_nearest() logic
    # Skip if RGB boundary detection is disabled
    if not use_rgb_boundary_detection:
        return base_delta_e
    
    # Analyze both target and candidate colors using RGB components
    # TODO: These functions should move to color-tools
    target_category = _rgb_to_blue_purple_category(target_rgb)
    candidate_category = _rgb_to_blue_purple_category(candidate_rgb)
    
    # Only apply penalty if both colors are in blue/purple range
    if target_category and candidate_category:
        # Check for clear category mismatch
        # 'boundary' can match either blue or purple, so only penalize clear mismatches
        if target_category in ('blue', 'purple') and candidate_category in ('blue', 'purple'):
            if target_category != candidate_category:
                # Clear mismatch: blue target → purple candidate (or vice versa)
                return base_delta_e + category_mismatch_penalty
    
    return base_delta_e


@lru_cache(maxsize=256)
def _get_filament_name_cached(
    rgb: Tuple[int, int, int],
    maker_tuple: Optional[Tuple[str, ...]],
    type_tuple: Optional[Tuple[str, ...]],
    finish_tuple: Optional[Tuple[str, ...]],
    hue_aware: bool = True
) -> str:
    """
    Cached filament name lookup. Uses tuples for hashability.
    
    This is the expensive operation - loading palette and calculating Delta E 2000.
    By caching it, we only do the lookup once per unique (color, filters) combination.
    
    Args:
        rgb: Target RGB color to match
        maker_tuple: Tuple of maker names (for caching)
        type_tuple: Tuple of filament types (for caching)
        finish_tuple: Tuple of finish types (for caching)
        hue_aware: If True, penalize hue shifts to avoid blue→purple mismatches
    """
    # Load palette once per cache entry
    palette = FilamentPalette.load_default()
    
    try:
        # Get filtered palette (returns list of FilamentRecord objects)
        filtered = palette.filter(
            maker=list(maker_tuple) if maker_tuple else None,
            type_name=list(type_tuple) if type_tuple else None,
            finish=list(finish_tuple) if finish_tuple else None
        )
        
        if not filtered:
            # No filaments match filters, fall back to hex
            return rgb_to_hex(rgb)
        
        if not hue_aware:
            # Use standard Delta E 2000 matching
            nearest_filament, distance = palette.nearest_filament(
                target_rgb=rgb,
                metric="de2000",
                maker=list(maker_tuple) if maker_tuple else None,
                type_name=list(type_tuple) if type_tuple else None,
                finish=list(finish_tuple) if finish_tuple else None
            )
            return f"{nearest_filament.maker} {nearest_filament.type} {nearest_filament.finish} {nearest_filament.color}"
        
        # TODO: This hue-aware search should be in color-tools library
        # Manually search with hue weighting
        from color_tools import delta_e_2000, rgb_to_lab
        target_lab = rgb_to_lab(rgb)
        
        best_filament = None
        best_distance = float('inf')
        
        for filament in filtered:
            # Calculate base Delta E
            de = delta_e_2000(target_lab, filament.lab)
            
            # Add category mismatch penalty
            # TODO: Move this logic to color-tools library
            filament_name = f"{filament.maker} {filament.type} {filament.finish} {filament.color}"
            weighted_distance = _calculate_hue_weighted_distance(
                rgb, filament.rgb, filament_name, de, 
                use_rgb_boundary_detection=hue_aware
            )
            
            if weighted_distance < best_distance:
                best_distance = weighted_distance
                best_filament = filament
        
        if best_filament:
            return f"{best_filament.maker} {best_filament.type} {best_filament.finish} {best_filament.color}"
        else:
            return rgb_to_hex(rgb)
            
    except (ValueError, AttributeError):
        # If anything fails, fall back to hex
        return rgb_to_hex(rgb)


@lru_cache(maxsize=256)
def _get_filament_with_rgb_cached(
    rgb: Tuple[int, int, int],
    maker_tuple: Optional[Tuple[str, ...]],
    type_tuple: Optional[Tuple[str, ...]],
    finish_tuple: Optional[Tuple[str, ...]],
    hue_aware: bool = True
) -> Tuple[str, Tuple[int, int, int]]:
    """
    Cached filament lookup returning both name and matched filament's RGB.
    
    Returns:
        Tuple of (filament_name, matched_rgb)
    """
    palette = FilamentPalette.load_default()
    
    try:
        # Get filtered palette (returns list of FilamentRecord objects)
        filtered = palette.filter(
            maker=list(maker_tuple) if maker_tuple else None,
            type_name=list(type_tuple) if type_tuple else None,
            finish=list(finish_tuple) if finish_tuple else None
        )
        
        if not filtered:
            return (rgb_to_hex(rgb), rgb)
        
        if not hue_aware:
            # Use standard Delta E 2000 matching
            nearest_filament, distance = palette.nearest_filament(
                target_rgb=rgb,
                metric="de2000",
                maker=list(maker_tuple) if maker_tuple else None,
                type_name=list(type_tuple) if type_tuple else None,
                finish=list(finish_tuple) if finish_tuple else None
            )
            filament_name = f"{nearest_filament.maker} {nearest_filament.type} {nearest_filament.finish} {nearest_filament.color}"
            return (filament_name, nearest_filament.rgb)
        
        # TODO: This hue-aware search should be in color-tools library
        # Manually search with hue weighting
        from color_tools import delta_e_2000, rgb_to_lab
        target_lab = rgb_to_lab(rgb)
        
        best_filament = None
        best_distance = float('inf')
        
        for filament in filtered:
            de = delta_e_2000(target_lab, filament.lab)
            # TODO: Move RGB boundary detection logic to color-tools library
            filament_name = f"{filament.maker} {filament.type} {filament.finish} {filament.color}"
            weighted_distance = _calculate_hue_weighted_distance(
                rgb, filament.rgb, filament_name, de,
                use_rgb_boundary_detection=hue_aware
            )
            
            if weighted_distance < best_distance:
                best_distance = weighted_distance
                best_filament = filament
        
        if best_filament:
            filament_name = f"{best_filament.maker} {best_filament.type} {best_filament.finish} {best_filament.color}"
            return (filament_name, best_filament.rgb)
        else:
            return (rgb_to_hex(rgb), rgb)
            
    except (ValueError, AttributeError):
        return (rgb_to_hex(rgb), rgb)


@lru_cache(maxsize=256)
def _get_css_color_name_cached(rgb: Tuple[int, int, int]) -> str:
    """
    Cached CSS color name lookup.
    
    Loads palette and finds nearest CSS color using Delta E 2000.
    """
    palette = Palette.load_default()
    lab = rgb_to_lab(rgb)
    nearest_color, distance = palette.nearest_color(lab, space="lab", metric="de2000")
    return nearest_color.name


@lru_cache(maxsize=256)
def _get_css_color_with_rgb_cached(rgb: Tuple[int, int, int]) -> Tuple[str, Tuple[int, int, int]]:
    """
    Cached CSS color lookup returning both name and matched color's RGB.
    
    Returns:
        Tuple of (color_name, matched_rgb)
    """
    palette = Palette.load_default()
    lab = rgb_to_lab(rgb)
    nearest_color, distance = palette.nearest_color(lab, space="lab", metric="de2000")
    return (nearest_color.name, nearest_color.rgb)


def get_color_name(rgb: Tuple[int, int, int], config: 'ConversionConfig') -> str:
    """
    Get the name for an RGB color based on the configured naming mode.
    
    Supports four modes:
    - "color": Find nearest CSS color name using Delta E 2000
    - "filament": Find nearest filament based on maker/type/finish filters
    - "hex": Use hex color code as the name
    - "generated": Use descriptive generated name (e.g., "very dark blue", "medium bright red")
    
    This function uses caching internally to avoid redundant lookups for
    the same color/filter combination, which significantly speeds up
    processing when images have many regions but few unique colors.
    
    Args:
        rgb: RGB tuple (0-255 for each channel)
        config: ConversionConfig with color_naming_mode and filament filters
    
    Returns:
        Color name string (e.g., "red", "Bambu PLA Basic Red", "#FF5733", "dark blue")
    """
    if config.color_naming_mode == "hex":
        # Hex mode: just return the hex code (no lookup needed)
        return rgb_to_hex(rgb)
    
    elif config.color_naming_mode == "generated":
        # Generated mode: use color_tools.naming.generate_color_name()
        from color_tools.naming import generate_color_name
        name, _ = generate_color_name(rgb)
        return name
    
    elif config.color_naming_mode == "filament":
        # Convert lists/strings to tuples for hashability (lru_cache requires hashable args)
        # Handle str, List[str], or None cases
        def to_tuple(value):
            if value is None:
                return None
            elif isinstance(value, str):
                return (value,)  # Single string becomes 1-element tuple
            else:
                return tuple(value)  # List becomes tuple
        
        maker_tuple = to_tuple(config.filament_maker)
        type_tuple = to_tuple(config.filament_type)
        finish_tuple = to_tuple(config.filament_finish)
        
        return _get_filament_name_cached(rgb, maker_tuple, type_tuple, finish_tuple, config.hue_aware_matching)
    
    else:  # "color" mode (default)
        return _get_css_color_name_cached(rgb)


def greedy_filament_matching(
    unique_rgbs: List[Tuple[int, int, int]],
    config: 'ConversionConfig'
) -> Dict[Tuple[int, int, int], Tuple[str, Tuple[int, int, int]]]:
    """
    Greedily assign unique filaments to each RGB color.
    
    Algorithm:
    1. Calculate Delta E distances from each RGB to all available filaments
    2. Find the closest RGB-filament pair (minimum distance)
    3. Assign that filament to that RGB
    4. Remove that filament from the available pool
    5. Repeat until all RGBs are assigned
    
    This ensures each RGB gets a DIFFERENT actual filament, even if it's not
    the best match. Used when --no-merge-colors is specified.
    
    Args:
        unique_rgbs: List of unique RGB colors to assign filaments to
        config: Conversion configuration with filament settings
    
    Returns:
        Dict mapping RGB → (filament_name, filament_rgb)
    """
    from color_tools import FilamentPalette, rgb_to_lab, delta_e_2000
    
    # Load filament palette
    palette = FilamentPalette.load_default()
    
    # Convert filter values
    def to_list(value):
        if value is None:
            return None
        elif isinstance(value, str):
            return [value]
        else:
            return list(value)
    
    maker_list = to_list(config.filament_maker)
    type_list = to_list(config.filament_type)
    finish_list = to_list(config.filament_finish)
    
    # Get all available filaments (filtered by user preferences)
    filtered = palette.filter(
        maker=maker_list,
        type_name=type_list,
        finish=finish_list
    )
    
    if not filtered:
        # No filaments match the filters - fall back to hex mode
        assignments = {}
        for rgb in unique_rgbs:
            assignments[rgb] = (rgb_to_hex(rgb), rgb)
        return assignments
    
    # Track assignments
    assignments: Dict[Tuple[int, int, int], Tuple[str, Tuple[int, int, int]]] = {}
    remaining_rgbs = unique_rgbs.copy()
    remaining_filaments = list(filtered)  # List of FilamentRecord objects
    
    # Greedy matching loop
    while remaining_rgbs and remaining_filaments:
        # Calculate all distances
        best_distance = float('inf')
        best_rgb = None
        best_filament = None
        
        # Find the closest RGB-filament pair
        for rgb in remaining_rgbs:
            rgb_lab = rgb_to_lab(rgb)
            for filament in remaining_filaments:
                fil_lab = rgb_to_lab(filament.rgb)
                distance = delta_e_2000(rgb_lab, fil_lab)
                
                if distance < best_distance:
                    best_distance = distance
                    best_rgb = rgb
                    best_filament = filament
        
        # Assign the best match
        if best_rgb and best_filament:
            filament_name = f"{best_filament.maker} {best_filament.type} {best_filament.finish} {best_filament.color}"
            assignments[best_rgb] = (filament_name, best_filament.rgb)
            
            # Remove from remaining pools
            remaining_rgbs.remove(best_rgb)
            remaining_filaments.remove(best_filament)
    
    # Handle case where we run out of filaments (unlikely but possible)
    if remaining_rgbs:
        # Fall back to generated color names for remaining RGBs
        from color_tools.naming import generate_color_name
        for rgb in remaining_rgbs:
            color_name = generate_color_name(rgb)
            assignments[rgb] = (color_name, rgb)
    
    return assignments


def get_color_name_and_rgb(rgb: Tuple[int, int, int], config: 'ConversionConfig') -> Tuple[str, Tuple[int, int, int]]:
    """
    Get the name AND matched RGB for a color based on the configured naming mode.
    
    WHY: When displaying AMS slot assignments, we want to show the hex value of the
    matched filament/color, not the detected pixel color. This allows users to see
    what color they should actually load in the AMS.
    
    Supports three modes:
    - "color": Find nearest CSS color name + RGB using Delta E 2000
    - "filament": Find nearest filament + RGB based on maker/type/finish filters
    - "hex": Use hex code as name, keep detected RGB
    
    Args:
        rgb: Detected RGB tuple (0-255 for each channel)
        config: ConversionConfig with color_naming_mode and filament filters
    
    Returns:
        Tuple of (color_name, matched_rgb) where matched_rgb is the RGB of the
        actual color/filament that was matched
    """
    if config.color_naming_mode == "hex":
        # Hex mode: just return the hex code and the detected RGB
        return (rgb_to_hex(rgb), rgb)
    
    elif config.color_naming_mode == "filament":
        # Convert lists/strings to tuples for hashability
        def to_tuple(value):
            if value is None:
                return None
            elif isinstance(value, str):
                return (value,)
            else:
                return tuple(value)
        
        maker_tuple = to_tuple(config.filament_maker)
        type_tuple = to_tuple(config.filament_type)
        finish_tuple = to_tuple(config.filament_finish)
        
        return _get_filament_with_rgb_cached(rgb, maker_tuple, type_tuple, finish_tuple, config.hue_aware_matching)
    
    else:  # "color" mode (default)
        return _get_css_color_with_rgb_cached(rgb)


# ============================================================================
# Color Preview Generation
# ============================================================================

def generate_color_preview(
    pixel_data: 'PixelData',
    color_mapping: Dict[Tuple[int, int, int], Tuple[int, int, int]],
    output_path: str
) -> None:
    """
    Generate a preview image showing what colors will look like with mapped filaments.
    
    This creates a version of the source image with all colors replaced by their
    matched filament colors. Useful for previewing color accuracy before printing.
    
    Args:
        pixel_data: Original pixel data from image processing
        color_mapping: Dict mapping detected RGB → filament RGB
        output_path: Path where preview image should be saved
    """
    from PIL import Image
    import numpy as np
    
    # Create a blank RGBA image
    preview = Image.new('RGBA', (pixel_data.width, pixel_data.height), (0, 0, 0, 0))
    preview_array = np.array(preview)
    
    # Replace each pixel with its mapped filament color
    for (x, y), (r, g, b, a) in pixel_data.pixels.items():
        # Flip Y coordinate back (pixel_data has Y=0 at bottom, image has Y=0 at top)
        image_y = pixel_data.height - 1 - y
        
        detected_rgb = (r, g, b)
        if detected_rgb in color_mapping:
            filament_rgb = color_mapping[detected_rgb]
            preview_array[image_y, x] = (*filament_rgb, a)
        else:
            # Shouldn't happen, but fallback to original color
            preview_array[image_y, x] = (r, g, b, a)
    
    # Save the preview
    preview_img = Image.fromarray(preview_array, 'RGBA')
    preview_img.save(output_path)


# ============================================================================
# Pixel Art Specific Callbacks for ThreeMFWriter
# ============================================================================

def _pixel_art_thumbnail_callback(output_path: str, context: Any) -> List[Tuple[str, bytes]]:
    """
    Generate pixel art thumbnails from source image.
    
    This callback generates all 5 required thumbnail types for Bambu Studio:
    - top_1.png: 512x512 overhead view
    - pick_1.png: 512x512 gray silhouette
    - plate_1.png: 512x512 isometric with shadow
    - plate_1_small.png: 128x128 downscaled
    - plate_no_light_1.png: 512x512 isometric no shadow
    
    Args:
        output_path: Path where 3MF will be saved (unused, kept for API consistency)
        context: config object with source_image_path attribute
    
    Returns:
        List of (zip_path, image_bytes) tuples for each thumbnail
    """
    from .thumbnail_generator import (
        generate_top_view,
        generate_pick_view,
        generate_plate_view,
        generate_plate_small,
        generate_plate_no_light
    )
    
    config = context
    thumbnails = []
    
    # Load source image in RGBA mode for thumbnail generation
    source_path = Path(config.source_image_path) if config.source_image_path else None
    if source_path and source_path.exists():
        source_img = Image.open(source_path).convert('RGBA')
        
        # Generate all 5 thumbnail types
        thumbnails.append(("Metadata/top_1.png", generate_top_view(source_img)))
        thumbnails.append(("Metadata/pick_1.png", generate_pick_view(source_img)))
        
        plate_view = generate_plate_view(source_img)
        thumbnails.append(("Metadata/plate_1.png", plate_view))
        thumbnails.append(("Metadata/plate_1_small.png", generate_plate_small(plate_view)))
        thumbnails.append(("Metadata/plate_no_light_1.png", generate_plate_no_light(source_img)))
    
    return thumbnails


# ============================================================================
# Main Export Function (Backward Compatible API)
# ============================================================================

def write_3mf(
    output_path: str,
    meshes: List[Tuple[Mesh, str]],
    region_colors: List[Tuple[int, int, int]],
    pixel_data: 'PixelData',
    config: 'ConversionConfig',
    progress_callback: Optional[Callable[[str, str], None]] = None
) -> Tuple[Optional[str], Optional[Dict[Tuple[int, int, int], Tuple[int, int, int]]], List[Tuple[int, str, Tuple[int, int, int]]]]:
    """
    Write all meshes to a 3MF file (pixel art specific wrapper).

    This is the main export function! It takes all our generated meshes,
    figures out color names, and packages everything into a proper 3MF file
    using the generic ThreeMFWriter from threemf_core.

    The 3MF structure:
    - [Content_Types].xml (required metadata)
    - _rels/.rels (required relationships)
    - 3D/3dmodel.model (main assembly)
    - 3D/Objects/object_1.model (all the mesh geometry)
    - Metadata/model_settings.config (object names/colors)

    Args:
        output_path: Path where to write the .3mf file
        meshes: List of (Mesh, name) tuples (regions + optional backing plate)
        region_colors: List of RGB colors for each region (for naming)
        pixel_data: PixelData object with model dimensions
        config: ConversionConfig object with conversion parameters
        progress_callback: Optional function to call with progress updates
    
    Returns:
        Tuple of (summary_path, preview_mapping, color_mapping):
        - summary_path: Path to summary file if generated, None otherwise
        - preview_mapping: Dict mapping detected RGB to filament RGB if preview requested, None otherwise
        - color_mapping: List of (slot, color_name, rgb) tuples sorted by slot number
    """
    # Helper to send progress updates
    def _progress(message: str):
        if progress_callback:
            progress_callback("export", message)

    # Determine if we have a backing plate
    has_backing_plate = config.base_height_mm > 0
    num_regions = len(region_colors)

    _progress(f"Assigning names to {num_regions} color regions...")

    # Calculate model center for positioning
    model_center_x = pixel_data.model_width_mm / 2.0
    model_center_y = pixel_data.model_height_mm / 2.0

    # Create region data: (mesh_index, rgb, color_name) for each region
    region_data = []
    for i, rgb in enumerate(region_colors):
        color_name = get_color_name(rgb, config)
        region_data.append((i, rgb, color_name))
    
    # Sort alphabetically by color name for easier slicer workflow
    region_data.sort(key=lambda x: x[2])
    
    # Build AMS slot mapping
    # Two modes:
    # 1. merge_similar_colors=True: Multiple RGB values can map to same color name (share slot)
    # 2. merge_similar_colors=False: Each unique RGB gets unique slot (greedy matching)
    backing_color_name = get_color_name(config.backing_color, config)
    
    if config.merge_similar_colors:
        # MERGE MODE: Group by color name (current behavior)
        # Multiple RGB values with same color name share one AMS slot
        name_to_slot: Dict[str, int] = {backing_color_name: 1}
        
        # Assign slots 2-N to other unique color names
        next_slot = 2
        for _, rgb, color_name in region_data:
            if color_name not in name_to_slot:
                name_to_slot[color_name] = next_slot
                next_slot += 1
        
        # Maintain color_to_slot for backward compatibility
        color_to_slot: Dict[Tuple[int, int, int], int] = {config.backing_color: 1}
        for _, rgb, color_name in region_data:
            color_to_slot[rgb] = name_to_slot[color_name]
    
    else:
        # NO-MERGE MODE: Each unique RGB gets its own slot with unique filament
        # Use greedy algorithm to assign different filaments to each RGB
        
        # Collect all unique RGB values (excluding backing color)
        unique_rgbs = []
        for _, rgb, _ in region_data:
            if rgb not in unique_rgbs and rgb != config.backing_color:
                unique_rgbs.append(rgb)
        
        # Use greedy matching to assign unique filaments
        rgb_to_name_and_matched_rgb = greedy_filament_matching(unique_rgbs, config)
        
        # Build slot mappings
        rgb_to_slot: Dict[Tuple[int, int, int], int] = {config.backing_color: 1}
        name_to_slot: Dict[str, int] = {backing_color_name: 1}
        
        next_slot = 2
        for rgb in unique_rgbs:
            filament_name, _ = rgb_to_name_and_matched_rgb[rgb]
            rgb_to_slot[rgb] = next_slot
            name_to_slot[filament_name] = next_slot
            next_slot += 1
        
        # For backward compatibility, create color_to_slot
        color_to_slot = rgb_to_slot
    
    # Reorder meshes to match the sorted color order
    sorted_meshes = [meshes[mesh_idx] for mesh_idx, _, _ in region_data]
    if has_backing_plate:
        sorted_meshes.append(meshes[-1])
    
    # Convert to ThreeMFMesh objects with metadata
    threemf_meshes = []
    for idx, (mesh, _) in enumerate(sorted_meshes):
        # Determine color name and slot based on position
        if idx < len(region_data):
            _, rgb, color_name = region_data[idx]
            
            # In no-merge mode, find the actual unique name we assigned
            if not config.merge_similar_colors:
                # Search name_to_slot for the key that corresponds to this rgb's slot
                target_slot = rgb_to_slot[rgb]
                # Find the name that maps to this slot
                for name, slot in name_to_slot.items():
                    if slot == target_slot:
                        color_name = name
                        break
                ams_slot = target_slot
            else:
                ams_slot = name_to_slot[color_name]
        else:
            # Backing plate
            color_name = "Backing"
            ams_slot = 1
        
        threemf_mesh = ThreeMFMesh(
            vertices=mesh.vertices,
            triangles=mesh.triangles,
            metadata={
                'color_name': color_name,
                'ams_slot': ams_slot,
                'model_center_x': model_center_x,
                'model_center_y': model_center_y
            }
        )
        threemf_meshes.append(threemf_mesh)
    
    # Define callbacks for ThreeMFWriter
    def naming_callback(obj_id: int, mesh: ThreeMFMesh) -> str:
        return mesh.metadata['color_name']
    
    def slot_callback(obj_id: int, mesh: ThreeMFMesh) -> int:
        return mesh.metadata['ams_slot']
    
    def transform_callback(obj_id: int, mesh: ThreeMFMesh, context: Any) -> Tuple[float, float, float]:
        # All objects centered on model center, z=0
        return (mesh.metadata['model_center_x'], mesh.metadata['model_center_y'], 0.0)
    
    # Create ThreeMFWriter with pixel art callbacks
    writer = ThreeMFWriter(
        naming_callback=naming_callback,
        slot_callback=slot_callback,
        transform_callback=transform_callback,
        thumbnail_callback=_pixel_art_thumbnail_callback,
        progress_callback=progress_callback,
        container_name="PixelArt3D",
        model_title=config.model_title
    )
    
    # Write the 3MF file
    writer.write(output_path, threemf_meshes, context=config)
    
    # Report completion
    _progress(f"✨ 3MF file written to: {output_path}")
    if has_backing_plate:
        _progress(f"{len(region_colors)} colored regions + 1 backing plate")
    else:
        _progress(f"{len(region_colors)} colored regions (no backing plate)")
    _progress(f"Total objects: {len(meshes)}")
    
    # Generate summary file if requested
    summary_path = None
    if config.generate_summary:
        from .summary_writer import write_summary_file
        
        _progress("Generating summary file...")
        
        # Extract RGB colors and names from region_data
        summary_colors = [rgb for _, rgb, _ in region_data]
        summary_names = [color_name for _, _, color_name in region_data]
        
        # Add backing plate color as a separate region
        if has_backing_plate:
            backing_name = get_color_name(config.backing_color, config)
            summary_colors.append(config.backing_color)
            summary_names.append(backing_name)
        
        summary_path = write_summary_file(
            output_path, summary_colors, summary_names,
            color_to_slot, config, has_backing_plate
        )
        _progress(f"📄 Summary written to: {summary_path}")
    
    # Build color mapping for CLI display
    # Use MATCHED RGB values (from filament/color lookup), not detected pixel RGB
    slot_to_color: Dict[int, Tuple[str, Tuple[int, int, int]]] = {}
    
    # Build slot_to_color using matched RGB values
    _, backing_matched_rgb = get_color_name_and_rgb(config.backing_color, config)
    slot_to_color[1] = (backing_color_name, backing_matched_rgb)
    
    # Process each unique color/filament assignment
    for unique_name, slot in name_to_slot.items():
        if slot == 1:  # Skip backing plate (already added)
            continue
        
        # Find the RGB and matched values for this slot
        if not config.merge_similar_colors:
            # In no-merge mode, use the greedy assignment results
            for rgb, rgb_slot in rgb_to_slot.items():
                if rgb_slot == slot:
                    # Get the matched filament RGB from greedy matching
                    filament_name, matched_rgb = rgb_to_name_and_matched_rgb[rgb]
                    slot_to_color[slot] = (filament_name, matched_rgb)
                    break
        else:
            # In merge mode, find any RGB with this color name
            for _, detected_rgb, color_name in region_data:
                if color_name == unique_name:
                    _, matched_rgb = get_color_name_and_rgb(detected_rgb, config)
                    slot_to_color[slot] = (unique_name, matched_rgb)
                    break
                if color_name == unique_name:
                    _, matched_rgb = get_color_name_and_rgb(detected_rgb, config)
                    slot_to_color[slot] = (unique_name, matched_rgb)
                    break
    
    # Convert to sorted list
    color_mapping = [(slot, name, rgb) for slot, (name, rgb) in sorted(slot_to_color.items())]
    
    # Build preview color mapping if requested (generation happens in caller)
    preview_mapping = None
    if config.generate_preview:
        # Build color mapping: detected RGB → matched filament RGB
        preview_mapping = {}
        
        # Always include backing color mapping
        _, backing_matched_rgb = get_color_name_and_rgb(config.backing_color, config)
        preview_mapping[config.backing_color] = backing_matched_rgb
        
        if not config.merge_similar_colors:
            # In no-merge mode, use the greedy assignment results
            for rgb, (filament_name, matched_rgb) in rgb_to_name_and_matched_rgb.items():
                preview_mapping[rgb] = matched_rgb
        else:
            # In merge mode, look up matched RGB for each detected RGB
            for _, detected_rgb, color_name in region_data:
                if detected_rgb not in preview_mapping:
                    # Find the matched RGB from slot_to_color
                    for slot, (name, matched_rgb) in slot_to_color.items():
                        if name == color_name:
                            preview_mapping[detected_rgb] = matched_rgb
                            break
    
    return summary_path, preview_mapping, color_mapping