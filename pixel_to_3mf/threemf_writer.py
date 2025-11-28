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

@lru_cache(maxsize=256)
def _get_filament_name_cached(
    rgb: Tuple[int, int, int],
    maker_tuple: Optional[Tuple[str, ...]],
    type_tuple: Optional[Tuple[str, ...]],
    finish_tuple: Optional[Tuple[str, ...]]
) -> str:
    """
    Cached filament name lookup. Uses tuples for hashability.
    
    This is the expensive operation - loading palette and calculating Delta E 2000.
    By caching it, we only do the lookup once per unique (color, filters) combination.
    """
    # Load palette once per cache entry
    palette = FilamentPalette.load_default()
    
    try:
        nearest_filament, distance = palette.nearest_filament(
            target_rgb=rgb,
            metric="de2000",
            maker=list(maker_tuple) if maker_tuple else None,
            type_name=list(type_tuple) if type_tuple else None,
            finish=list(finish_tuple) if finish_tuple else None
        )
        return f"{nearest_filament.maker} {nearest_filament.type} {nearest_filament.finish} {nearest_filament.color}"
    except ValueError:
        # If no filaments match the filters, fall back to hex
        return rgb_to_hex(rgb)


@lru_cache(maxsize=256)
def _get_filament_with_rgb_cached(
    rgb: Tuple[int, int, int],
    maker_tuple: Optional[Tuple[str, ...]],
    type_tuple: Optional[Tuple[str, ...]],
    finish_tuple: Optional[Tuple[str, ...]]
) -> Tuple[str, Tuple[int, int, int]]:
    """
    Cached filament lookup returning both name and matched filament's RGB.
    
    Returns:
        Tuple of (filament_name, matched_rgb)
    """
    palette = FilamentPalette.load_default()
    
    try:
        nearest_filament, distance = palette.nearest_filament(
            target_rgb=rgb,
            metric="de2000",
            maker=list(maker_tuple) if maker_tuple else None,
            type_name=list(type_tuple) if type_tuple else None,
            finish=list(finish_tuple) if finish_tuple else None
        )
        filament_name = f"{nearest_filament.maker} {nearest_filament.type} {nearest_filament.finish} {nearest_filament.color}"
        matched_rgb = nearest_filament.rgb
        return (filament_name, matched_rgb)
    except ValueError:
        # If no filaments match the filters, fall back to hex and use detected RGB
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
    
    Supports three modes:
    - "color": Find nearest CSS color name using Delta E 2000
    - "filament": Find nearest filament based on maker/type/finish filters
    - "hex": Use hex color code as the name
    
    This function uses caching internally to avoid redundant lookups for
    the same color/filter combination, which significantly speeds up
    processing when images have many regions but few unique colors.
    
    Args:
        rgb: RGB tuple (0-255 for each channel)
        config: ConversionConfig with color_naming_mode and filament filters
    
    Returns:
        Color name string (e.g., "red", "Bambu PLA Basic Red", "#FF5733")
    """
    if config.color_naming_mode == "hex":
        # Hex mode: just return the hex code (no lookup needed)
        return rgb_to_hex(rgb)
    
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
        
        return _get_filament_name_cached(rgb, maker_tuple, type_tuple, finish_tuple)
    
    else:  # "color" mode (default)
        return _get_css_color_name_cached(rgb)


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
        
        return _get_filament_with_rgb_cached(rgb, maker_tuple, type_tuple, finish_tuple)
    
    else:  # "color" mode (default)
        return _get_css_color_with_rgb_cached(rgb)


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
) -> Tuple[Optional[str], List[Tuple[int, str, Tuple[int, int, int]]]]:
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
        Tuple of (summary_path, color_mapping):
        - summary_path: Path to summary file if generated, None otherwise
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
    
    # Build AMS slot mapping based on UNIQUE COLOR NAMES (not RGB values)
    # WHY: Multiple RGB values can map to the same color name.
    # We want them to share the same AMS slot.
    backing_color_name = get_color_name(config.backing_color, config)
    
    # Create mapping from color_name -> slot
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
    name_to_rgb: Dict[str, Tuple[int, int, int]] = {}
    
    # Build name_to_rgb mapping using matched RGB values
    _, backing_matched_rgb = get_color_name_and_rgb(config.backing_color, config)
    name_to_rgb[backing_color_name] = backing_matched_rgb
    
    for _, detected_rgb, color_name in region_data:
        if color_name not in name_to_rgb:
            _, matched_rgb = get_color_name_and_rgb(detected_rgb, config)
            name_to_rgb[color_name] = matched_rgb
    
    # Build slot_to_color using unique names and matched RGB values
    for color_name, slot in name_to_slot.items():
        matched_rgb = name_to_rgb[color_name]
        slot_to_color[slot] = (color_name, matched_rgb)
    
    # Convert to sorted list
    color_mapping = [(slot, name, rgb) for slot, (name, rgb) in sorted(slot_to_color.items())]
    
    return summary_path, color_mapping