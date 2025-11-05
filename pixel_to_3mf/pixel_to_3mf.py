#!/usr/bin/env python3
"""
Pixel Art to 3MF Converter

Convert pixel art images into 3D printable 3MF files with automatic color
detection and region merging. Perfect for making colorful pixel art coasters,
wall art, or any other flat 3D printed designs! 🎨🖨️

Usage:
    python pixel_to_3mf.py input_image.png [options]

Example:
    python pixel_to_3mf.py mario.png --max-size 150 --output mario_3d.3mf
"""

import argparse
import sys
from pathlib import Path

from .constants import (
    MAX_MODEL_SIZE_MM,
    PIXEL_ROUNDING_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    DEFAULT_OUTPUT_SUFFIX
)
from .image_processor import load_image
from .region_merger import merge_regions
from .mesh_generator import generate_region_mesh, generate_backing_plate
from .threemf_writer import write_3mf


def main():
    """Main entry point for the pixel art to 3MF converter."""
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(
        description="Convert pixel art images to 3D printable 3MF files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sprite.png
  %(prog)s mario.png --output mario_model.3mf
  %(prog)s pixel_art.png --max-size 150 --color-height 1.5
  %(prog)s icon.png --pixel-rounding 1.0 --base-height 2.0

The program will:
  1. Load your pixel art image
  2. Calculate appropriate scaling to fit your print bed
  3. Merge connected same-color pixels into regions
  4. Generate 3D geometry (extruded regions + backing plate)
  5. Export to 3MF with color names for easy slicer setup
        """
    )
    
    # Positional argument: input file
    parser.add_argument(
        "image_file",
        type=str,
        help="Input pixel art image file (PNG, JPG, etc.)"
    )
    
    # Optional arguments
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output 3MF file path (default: {input_name}_model.3mf)"
    )
    
    parser.add_argument(
        "--max-size",
        type=float,
        default=MAX_MODEL_SIZE_MM,
        help=f"Maximum dimension (width or height) in mm (default: {MAX_MODEL_SIZE_MM})"
    )
    
    parser.add_argument(
        "--pixel-rounding",
        type=float,
        default=PIXEL_ROUNDING_MM,
        help=f"Round pixel size to nearest multiple of this value in mm (default: {PIXEL_ROUNDING_MM})"
    )
    
    parser.add_argument(
        "--color-height",
        type=float,
        default=COLOR_LAYER_HEIGHT_MM,
        help=f"Height of colored regions in mm (default: {COLOR_LAYER_HEIGHT_MM})"
    )
    
    parser.add_argument(
        "--base-height",
        type=float,
        default=BASE_LAYER_HEIGHT_MM,
        help=f"Height of backing plate in mm (default: {BASE_LAYER_HEIGHT_MM})"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate input file exists
    input_path = Path(args.image_file)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.image_file}", file=sys.stderr)
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Default: same name as input with _model.3mf suffix
        output_path = str(input_path.with_suffix('')) + DEFAULT_OUTPUT_SUFFIX + '.3mf'
    
    # Override constants with command-line arguments if provided
    # (This lets users tweak settings without editing constants.py)
    max_size = args.max_size
    pixel_rounding = args.pixel_rounding
    color_height = args.color_height
    base_height = args.base_height
    
    print("=" * 70)
    print("🎨 Pixel Art to 3MF Converter")
    print("=" * 70)
    print()
    
    # Step 1: Load and process image
    print(f"📁 Loading image: {input_path.name}")
    try:
        pixel_data = load_image(
            str(input_path),
            max_size_mm=max_size,
            rounding_mm=pixel_rounding
        )
    except Exception as e:
        print(f"❌ Error loading image: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"   Image size: {pixel_data.width} x {pixel_data.height} pixels")
    print(f"   Pixel size: {pixel_data.pixel_size_mm} mm")
    print(f"   Model size: {pixel_data.model_width_mm:.1f} x {pixel_data.model_height_mm:.1f} mm")
    print(f"   Non-transparent pixels: {len(pixel_data.pixels)}")
    print(f"   Unique colors: {len(pixel_data.get_unique_colors())}")
    print()
    
    # Step 2: Merge regions
    print("🧩 Merging connected pixels into regions...")
    regions = merge_regions(pixel_data)
    print(f"   Found {len(regions)} connected regions")
    print()
    
    # Step 3: Generate meshes for each region
    print("🎲 Generating 3D geometry...")
    meshes = []
    region_colors = []
    
    for i, region in enumerate(regions, start=1):
        print(f"   Region {i}/{len(regions)}: {len(region.pixels)} pixels, color RGB{region.color}")
        mesh = generate_region_mesh(region, pixel_data, layer_height=color_height)
        meshes.append((mesh, f"region_{i}"))
        region_colors.append(region.color)
    
    # Generate backing plate
    print(f"   Backing plate: {pixel_data.model_width_mm:.1f} x {pixel_data.model_height_mm:.1f} mm")
    backing_mesh = generate_backing_plate(pixel_data, base_height=base_height)
    meshes.append((backing_mesh, "backing_plate"))
    print()
    
    # Step 4: Write 3MF file
    print("📦 Writing 3MF file...")
    try:
        write_3mf(output_path, meshes, region_colors)
    except Exception as e:
        print(f"❌ Error writing 3MF: {e}", file=sys.stderr)
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("✅ Conversion complete!")
    print("=" * 70)
    print(f"Output file: {output_path}")
    print()
    print("Next steps:")
    print("  1. Open the 3MF file in your slicer (Bambu Studio, PrusaSlicer, etc.)")
    print("  2. Assign filament colors to each named object")
    print("  3. Slice and print!")
    print()


if __name__ == "__main__":
    main()
