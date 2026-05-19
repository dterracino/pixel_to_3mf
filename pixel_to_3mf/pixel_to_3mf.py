"""
Core conversion logic for pixel art to 3MF.

This module contains the pure business logic for converting pixel art
images into 3MF files. It's completely separate from the CLI layer,
making it easy to use programmatically or test.

No print statements, no argparse, just clean conversion logic! 🎯
"""

import math
import os
import logging

from typing import Optional, Callable, Dict, Any, List, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

from .image_processor import load_image, PixelData
from .region_merger import merge_regions, trim_disconnected_pixels, Region, denoise_blob_pixels
from .mesh_generator import generate_region_mesh, generate_backing_plate, generate_solid_core, generate_region_mesh_shell
from .threemf_writer import write_3mf
from .config import ConversionConfig
from .constants import COORDINATE_PRECISION
from .pipeline_context import PipelineContext, generate_previews

def _create_filtered_pixel_data(regions: List[Region], original_pixel_data: PixelData) -> PixelData:
    """
    Create a PixelData object filtered to only include pixels from the given regions.
    
    This ensures the backing plate matches the actual colored regions, excluding
    any pixels that were filtered out during region merging or optimization.
    
    WHY: When regions are filtered (e.g., disconnected pixels removed during
    polygon optimization), the backing plate must stay in sync with the colored
    layers above. Otherwise, isolated pixels appear in the backing plate but not
    in the colored regions, creating unprintable geometry.
    
    Args:
        regions: List of Region objects that will be included in the final model
        original_pixel_data: Original PixelData with all pixels
    
    Returns:
        New PixelData with only pixels that exist in the provided regions
    """
    # Collect all pixel coordinates from all regions
    included_pixels: Set[Tuple[int, int]] = set()
    for region in regions:
        included_pixels.update(region.pixels)
    
    # Filter original pixels to only those in regions
    filtered_pixels = {
        coord: rgba
        for coord, rgba in original_pixel_data.pixels.items()
        if coord in included_pixels
    }
    
    # Create new PixelData with filtered pixels
    # Width, height, and pixel_size_mm remain the same
    return PixelData(
        width=original_pixel_data.width,
        height=original_pixel_data.height,
        pixel_size_mm=original_pixel_data.pixel_size_mm,
        pixels=filtered_pixels
    )


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
    
    # Reset optimization statistics if optimization is enabled
    from . import mesh_generator as mg
    if mg.USE_OPTIMIZED_MESH_GENERATION:
        try:
            from .polygon_optimizer import reset_optimization_stats
            reset_optimization_stats()
        except ImportError:
            pass  # Optimization not available

    # Validate input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    
    # Set source image information in config
    # WHY: This allows the config to auto-generate the model title and makes
    # the information available throughout the pipeline without changing function signatures
    config.source_image_path = str(input_path)
    config.source_image_name = input_file.name

    # Config validates itself in __post_init__, so we don't need to validate parameters here

    # Pipeline context — accumulates PixelData snapshots for preview generation
    ctx = PipelineContext()

    # Step 1: Load and process image (with optional iterative quantization)
    # Note: Auto-crop (if enabled) happens inside load_image() as part of the pipeline
    _progress("load", f"Loading image: {input_file.name}")

    regions = None  # May be set inside the iterate block; checked in Step 2 below

    if config.iterate_quantize and config.quantize:
        # ITERATIVE MODE: Start at quantize_colors and decrement until the merged color
        # count fits within max_colors. This gives accent colors a better chance of
        # surviving quantization — more initial colors means the quantizer has less
        # reason to collapse small-but-important clusters into nearby larger ones.
        from .threemf_writer import get_color_name

        start_colors = config.quantize_colors if config.quantize_colors is not None else config.max_colors
        min_colors = config.max_colors  # don't go below max_colors; normal rules apply there
        current_q = start_colors

        pixel_data = None
        regions = None
        final_q = current_q

        while current_q >= min_colors:
            config.quantize_colors = current_q
            _progress("load", f"Trying quantize-colors={current_q}...")
            candidate_pixel_data = load_image(str(input_path), config)

            if config.denoise_min_size > 0:
                _progress("denoise", f"Denoising blobs smaller than {config.denoise_min_size}px...")
                candidate_pixel_data.pixels = denoise_blob_pixels(
                    candidate_pixel_data.pixels, config.denoise_min_size, config.connectivity
                )
                _progress("denoise", "Complete!")

            candidate_regions = merge_regions(candidate_pixel_data, config)
            if config.trim_disconnected:
                candidate_regions = trim_disconnected_pixels(candidate_regions, candidate_pixel_data.pixels)

            # Count how many unique color names (slots) the merge step would produce
            unique_region_colors = list({r.color for r in candidate_regions})
            unique_names: set[str | Tuple[int, int, int]]
            if config.merge_similar_colors:
                unique_names = {get_color_name(rgb, config) for rgb in unique_region_colors}
            else:
                unique_names = set(unique_region_colors)  # no merging → count raw RGBs

            # Account for backing color slot reservation.
            # Slot 1 is always the backing color when no_backing_color=False.
            # If the backing color appears in the image it shares slot 1 (discard it so
            # it isn't double-counted). Either way, image colors can only use
            # max_colors-1 slots (2..max_colors), so compare against that limit.
            if not config.no_backing_color:
                if config.merge_similar_colors:
                    unique_names.discard(get_color_name(config.backing_color, config))
                else:
                    unique_names.discard(config.backing_color)

            effective_limit = config.max_colors if config.no_backing_color else config.max_colors - 1

            merged_count = len(unique_names)
            _progress("load", f"  → {merged_count} merged colors (target: ≤{effective_limit})")

            if merged_count <= effective_limit:
                pixel_data = candidate_pixel_data
                regions = candidate_regions
                final_q = current_q
                break
            current_q -= 1

        if pixel_data is None:
            # Fell through — even at min_colors it didn't fit; use the last attempt
            # (load_image at min_colors will raise the normal error if still too many)
            config.quantize_colors = min_colors
            pixel_data = load_image(str(input_path), config)
            ctx.snapshot_original(pixel_data)
            if config.quantize:
                ctx.snapshot_quantized(pixel_data)
            if config.denoise_min_size > 0:
                _progress("denoise", f"Denoising blobs smaller than {config.denoise_min_size}px...")
                pixel_data.pixels = denoise_blob_pixels(
                    pixel_data.pixels, config.denoise_min_size, config.connectivity
                )
                ctx.snapshot_denoised(pixel_data)
                _progress("denoise", "Complete!")
            regions = merge_regions(pixel_data, config)
            if config.trim_disconnected:
                regions = trim_disconnected_pixels(regions, pixel_data.pixels)
            final_q = min_colors
        else:
            # Capture snapshots for the winning candidate
            # Reconstruct: load without quantize to get original, then the
            # quantized result is already in pixel_data.
            original_config_q = config.quantize_colors
            config.quantize = False
            original_pixel_data = load_image(str(input_path), config)
            config.quantize = True
            config.quantize_colors = original_config_q
            ctx.snapshot_original(original_pixel_data)
            ctx.snapshot_quantized(pixel_data)
            if config.denoise_min_size > 0:
                ctx.snapshot_denoised(pixel_data)

        if final_q < start_colors:
            _progress("load", f"Settled on quantize-colors={final_q} (started at {start_colors})")
        else:
            _progress("load", f"quantize-colors={final_q} already fits within max-colors={config.max_colors}")

    else:
        # Normal (non-iterative) load
        if config.quantize and config.generate_preview:
            # Load without quantize first to capture a true "original" snapshot,
            # then load again with quantize to get the actual working pixel_data.
            # WHY: quantization happens inside load_image(), so to show a
            # before/after comparison we need the pre-quantize state separately.
            original_config_quantize = config.quantize
            config.quantize = False
            original_pixel_data = load_image(str(input_path), config)
            config.quantize = original_config_quantize
            ctx.snapshot_original(original_pixel_data)

            pixel_data = load_image(str(input_path), config)
            ctx.snapshot_quantized(pixel_data)
        else:
            pixel_data = load_image(str(input_path), config)
            ctx.snapshot_original(pixel_data)

        if config.denoise_min_size > 0:
            _progress("denoise", f"Denoising blobs smaller than {config.denoise_min_size}px...")
            pixel_data.pixels = denoise_blob_pixels(
                pixel_data.pixels, config.denoise_min_size, config.connectivity
            )
            ctx.snapshot_denoised(pixel_data)
            _progress("denoise", "Complete!")

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
    
    # Step 2: Merge regions (skip if already done inside the iterate loop above)
    if regions is None:
        _progress("merge", "Merging connected pixels into regions...")
        regions = merge_regions(pixel_data, config)
        _progress("merge", f"Found {len(regions)} connected regions")

        # Step 2.5: Trim disconnected pixels if enabled
        if config.trim_disconnected:
            _progress("merge", "Trimming disconnected pixels...")
            original_count = len(regions)
            regions = trim_disconnected_pixels(regions, pixel_data.pixels)
            if len(regions) < original_count:
                _progress("merge", f"Trimmed to {len(regions)} regions (removed {original_count - len(regions)} empty regions)")
    else:
        _progress("merge", f"Found {len(regions)} connected regions")

    # Step 2.7: Smooth region boundaries (optional — disabled by default)
    smoothed_regions = None
    if config.smooth_boundaries:
        _progress("smooth", f"Smoothing boundaries (tolerance={config.smooth_simplify_tolerance}, "
                             f"iterations={config.smooth_chaikin_iterations})...")
        from .boundary_smoother import smooth_region_boundaries
        smoothed_regions = smooth_region_boundaries(regions, pixel_data, config)
        _progress("smooth", f"  {len(smoothed_regions)} smoothed regions")

    # Step 3: Generate meshes
    _progress("mesh", "Generating 3D geometry...")
    meshes = []
    region_colors = []

    if config.has_solid_core:
        # Solid-core mode: each region becomes two thin shells (bottom + top).
        # A single solid core object spans the full model footprint between them.
        z_core_bot = config.core_z_bottom
        z_core_top = config.core_z_top
        z_shell_bot = z_core_bot - config.color_shell_half_height  # below the core
        z_shell_top = z_core_top + config.color_shell_half_height  # above the core

        for i, region in enumerate(regions, start=1):
            _progress("mesh", f"Region {i}/{len(regions)}: {len(region.pixels)} pixels (dual shell)")
            bottom_shell = generate_region_mesh_shell(region, pixel_data, config, z_shell_bot, z_core_bot)
            top_shell = generate_region_mesh_shell(region, pixel_data, config, z_core_top, z_shell_top)
            meshes.append((bottom_shell, f"region_{i}_bottom"))
            meshes.append((top_shell, f"region_{i}_top"))
            region_colors.append(region.color)  # one color entry per logical region

        _progress("mesh", "Generating solid core...")
        filtered_pixel_data = _create_filtered_pixel_data(regions, pixel_data)
        core_mesh = generate_solid_core(filtered_pixel_data, config)
        meshes.append((core_mesh, "solid_core"))
    else:
        if smoothed_regions is not None:
            # Smooth path: each SmoothedRegion already has a Shapely polygon.
            from .polygon_optimizer import generate_region_mesh_from_smoothed
            for i, sregion in enumerate(smoothed_regions, start=1):
                _progress("mesh", f"Region {i}/{len(smoothed_regions)}: smooth polygon (color={sregion.color})")
                mesh = generate_region_mesh_from_smoothed(sregion, pixel_data.pixel_size_mm, config)
                meshes.append((mesh, f"region_{i}"))
                region_colors.append(sregion.color)
        else:
            for i, region in enumerate(regions, start=1):
                _progress("mesh", f"Region {i}/{len(regions)}: {len(region.pixels)} pixels")
                mesh = generate_region_mesh(region, pixel_data, config)
                meshes.append((mesh, f"region_{i}"))
                region_colors.append(region.color)

        # Generate backing plate (if enabled and not omitted by --no-backing-plate)
        if config.has_backing_plate:
            _progress("mesh", "Generating backing plate...")
            # CRITICAL FIX: Filter pixel_data to only include pixels from regions
            # This ensures backing plate matches the colored regions exactly,
            # even if some pixels were filtered out during region merging/optimization
            filtered_pixel_data = _create_filtered_pixel_data(regions, pixel_data)
            backing_mesh = generate_backing_plate(filtered_pixel_data, config)
            meshes.append((backing_mesh, "backing_plate"))
        else:
            if config.no_backing_plate:
                _progress("mesh", "Skipping backing plate (--no-backing-plate)")
            elif config.base_height_mm == 0:
                _progress("mesh", "Skipping backing plate (base height is 0)")
    
    # Step 3.5: Post-process and validate meshes if requested
    validation_results = []  # Collect diagnostics for later display
    if config.validate_mesh:
        from .mesh_postprocessor import validate_and_fix_mesh
        
        _progress("postprocess", "Post-processing meshes...")
        
        for i, (mesh, name) in enumerate(meshes):
            _progress("postprocess", f"Validating and repairing {name}...")
            
            # Run post-processing with verbose output disabled for progress callback
            # (verbose Rich output would conflict with progress bars)
            fixed_mesh, diagnostics = validate_and_fix_mesh(
                mesh,
                name=name,
                verbose=False,  # Don't use Rich output here (conflicts with progress)
                progress_callback=lambda msg: _progress("postprocess", msg)
            )
            
            # Update mesh in list
            meshes[i] = (fixed_mesh, name)
            
            # Collect diagnostics for display after progress completes
            validation_results.append({
                'name': name,
                'diagnostics': diagnostics
            })
            
            # Log results
            if diagnostics['is_valid']:
                _progress("postprocess", f"✓ {name}: Manifold and valid")
            else:
                _progress("postprocess", f"⚠ {name}: Still has issues after repair")
    
    # # Step 4: Validate meshes
    # validation_results = []
    # _progress("validate", "Validating meshes...")
    # for i, (mesh, name) in enumerate(meshes, start=1):
    #     _progress("validate", f"Mesh {i}/{len(meshes)}: {name}")
    #     validation = validate_mesh(mesh, name)
    #     validation_results.append((name, validation))
    
    # Step 5: Repair meshes (TODO - implement in future PR)
    # ========================================================================
    # TODO: Implement mesh repair stage
    # 
    # Plan:
    # - Filter validation_results to find meshes with errors
    # - Create mesh_repair.py module with repair_mesh() function
    # - Loop through failed meshes calling repair_mesh()
    # - Update meshes list with repaired versions
    # - Re-validate repaired meshes to confirm fixes
    # 
    # Example:
    # failed_meshes = [(i, mesh, name) for i, (mesh, name) in enumerate(meshes)
    #                  if not validation_results[i][1].is_valid]
    # if failed_meshes:
    #     _progress("repair", "Repairing meshes...")
    #     for idx, (mesh_idx, mesh, name) in enumeratde(failed_meshes, start=1):
    #         _progress("repair", f"Mesh {idx}/{len(failed_meshes)}: {name}")
    #         repaired = repair_mesh(mesh, validation_results[mesh_idx][1])
    #         meshes[mesh_idx] = (repaired, name)
    #         # Re-validate
    #         revalidation = validate_mesh(repaired, name)
    #         validation_results[mesh_idx] = (name, revalidation)
    # ========================================================================
    
    # Step 6: Write 3MF
    _progress("export", "Writing 3MF file...")
    
    summary_path, preview_mapping, color_mapping = write_3mf(
        output_path, 
        meshes, 
        region_colors, 
        pixel_data, 
        config, 
        progress_callback
    )
    _progress("export", "Complete!")
    
    # Step 6.5: Generate preview images if requested
    preview_paths: list[str] = []
    if config.generate_preview:
        ctx.color_mapping = preview_mapping or {}
        _progress("preview", "Generating preview images...")
        preview_paths = generate_previews(ctx, output_path, progress_callback)
        _progress("preview", "Complete!")
    
    # Step 6.6: Generate color swatches if requested
    swatches_path = None
    if config.generate_swatches and color_mapping:
        from .swatch_generator import generate_swatches_image
        
        _progress("swatches", "Generating color swatches...")
        # Extract colors and names from color_mapping (slot, name, rgb)
        swatch_colors = [rgb for _, _, rgb in color_mapping]
        swatch_names = [name for _, name, _ in color_mapping]
        swatches_path = str(generate_swatches_image(Path(output_path), swatch_colors, swatch_names))
        _progress("swatches", f"Swatches saved to: {swatches_path}")
    
    # Step 7: Render model if requested
    render_path = None
    if config.render_model:
        _progress("render", "Rendering 3D model preview...")
        from .render_model import render_meshes_to_file, generate_render_path
        
        render_path = generate_render_path(output_path)
        render_meshes_to_file(
            meshes=meshes,
            region_colors=region_colors,
            output_path=render_path,
            model_width_mm=pixel_data.model_width_mm,
            model_height_mm=pixel_data.model_height_mm,
            backing_color=config.backing_color
        )
        _progress("render", f"Render saved to: {render_path}")
    
    # Count mesh statistics (extract Mesh objects from tuples)
    mesh_objects = [mesh for mesh, _ in meshes]
    total_vertices = sum(len(mesh.vertices) for mesh in mesh_objects)
    total_triangles = sum(len(mesh.triangles) for mesh in mesh_objects)
    
    # Return statistics
    stats = {
        'image_width': pixel_data.width,
        'image_height': pixel_data.height,
        'pixel_size_mm': pixel_data.pixel_size_mm,
        'model_width_mm': pixel_data.model_width_mm,
        'model_height_mm': pixel_data.model_height_mm,
        'num_pixels': len(pixel_data.pixels),
        'num_colors': len(color_mapping),  # Count unique color names after mapping (not RGB values)
        'num_regions': len(regions),
        'num_vertices': total_vertices,
        'num_triangles': total_triangles,
        'output_path': output_path,
        'file_size': format_filesize(os.path.getsize(output_path)),
        'color_mapping': color_mapping,  # AMS slot assignments
        'config': config  # Store config for batch checking
    }
    
    # Add validation results if available
    if validation_results:
        stats['validation_results'] = validation_results
    
    # Add summary path if generated
    if summary_path:
        stats['summary_path'] = summary_path
    
    # Add preview paths if generated
    if preview_paths:
        # Keep singular key for the primary _preview.png for backward compatibility
        primary = next((p for p in preview_paths if p.endswith('_preview.png')), None)
        if primary:
            stats['preview_path'] = primary
        stats['preview_paths'] = preview_paths
    
    # Add swatches path if generated
    if swatches_path:
        stats['swatches_path'] = swatches_path
    
    # Add render path if generated
    if render_path:
        stats['render_path'] = render_path
    
    # Write model info file for batch checking
    from .model_info import write_model_info
    try:
        info_path = write_model_info(output_path, stats, converter_version="0.x.x")
        stats['info_path'] = info_path
    except Exception as e:
        logger.warning(f"Failed to write model info file: {e}")
    
    return stats