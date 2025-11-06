#!/usr/bin/env python3
"""
Command-line interface for the Pixel Art to 3MF Converter.

This module handles all the CLI-specific stuff: argument parsing, pretty
printing, error display, etc. The actual conversion logic lives in
pixel_to_3mf.py and can be imported/used programmatically.

Separation of concerns FTW! 🎯
"""

import argparse
import sys
from pathlib import Path

from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    DEFAULT_OUTPUT_SUFFIX,
    MAX_COLORS,
    BACKING_COLOR,
    COORDINATE_PRECISION
)
from .config import ConversionConfig
from .pixel_to_3mf import convert_image_to_3mf


def main():
    """Main CLI entry point."""
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(
        description="Convert pixel art images to 3D printable 3MF files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sprite.png
  %(prog)s mario.png --output mario_model.3mf
  %(prog)s pixel_art.png --max-size 150 --color-height 1.5
  %(prog)s icon.png --base-height 2.0 --max-colors 20

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
        "--line-width",
        type=float,
        default=LINE_WIDTH_MM,
        help=f"Nozzle line width in mm - used to check if pixels are printable (default: {LINE_WIDTH_MM})"
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
    
    parser.add_argument(
        "--max-colors",
        type=int,
        default=MAX_COLORS,
        help=f"Maximum unique colors allowed (default: {MAX_COLORS})"
    )

    parser.add_argument(
        "--backing-color",
        type=str,
        default=None,
        help=f"Backing plate color as R,G,B (e.g., '255,255,255' for white). "
             f"If not in image, reserves 1 color slot. Default: {BACKING_COLOR}"
    )

    # Parse arguments
    args = parser.parse_args()

    # Parse backing color if provided
    backing_color = BACKING_COLOR
    if args.backing_color:
        try:
            parts = args.backing_color.split(',')
            if len(parts) != 3:
                raise ValueError("Must have exactly 3 values (R,G,B)")
            backing_color = tuple(int(p.strip()) for p in parts)
            if not all(0 <= c <= 255 for c in backing_color):
                raise ValueError("RGB values must be 0-255")
        except Exception as e:
            print(f"❌ Error: Invalid backing color '{args.backing_color}': {e}", file=sys.stderr)
            print("   Format: R,G,B (e.g., '255,255,255' for white)", file=sys.stderr)
            sys.exit(1)

    # Build config object from CLI arguments
    try:
        config = ConversionConfig(
            max_size_mm=args.max_size,
            line_width_mm=args.line_width,
            color_height_mm=args.color_height,
            base_height_mm=args.base_height,
            max_colors=args.max_colors,
            backing_color=backing_color
        )
    except ValueError as e:
        print(f"❌ Error: Invalid configuration: {e}", file=sys.stderr)
        sys.exit(1)

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
    
    # Print header
    print("=" * 70)
    print("🎨 Pixel Art to 3MF Converter")
    print("=" * 70)
    print()
    
    # Progress callback to print nice updates
    current_stage = None
    
    def progress_callback(stage: str, message: str):
        nonlocal current_stage
        
        # Print stage header if it changed
        if stage != current_stage:
            current_stage = stage
            stage_icons = {
                'load': '📁',
                'merge': '🧩',
                'mesh': '🎲',
                'export': '📦'
            }
            icon = stage_icons.get(stage, '▶️')
            
            if stage == 'load':
                print(f"{icon} Loading image...")
            elif stage == 'merge':
                print(f"{icon} Merging regions...")
            elif stage == 'mesh':
                print(f"{icon} Generating 3D geometry...")
            elif stage == 'export':
                print(f"{icon} Writing 3MF file...")
        
        # Print the message with indentation
        print(f"   {message}")
    
    # Run the conversion!
    try:
        stats = convert_image_to_3mf(
            input_path=str(input_path),
            output_path=output_path,
            config=config,
            progress_callback=progress_callback
        )
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Invalid parameter: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Print summary
    print()
    print("=" * 70)
    print("✅ Conversion complete!")
    print("=" * 70)
    print(f"📊 Statistics:")
    print(f"   Image: {stats['image_width']} x {stats['image_height']} pixels")
    print(f"   Model: {stats['model_width_mm']:.1f} x {stats['model_height_mm']:.1f} mm")
    print(f"   Pixel size: {round(stats['pixel_size_mm'], COORDINATE_PRECISION)} mm")
    print(f"   Regions: {stats['num_regions']} ({stats['num_colors']} unique colors)")
    print(f"   Output: {stats['output_path']} ({stats['file_size']})")
    print()
    print("🎯 Next steps:")
    print("  1. Open the 3MF file in your slicer (Bambu Studio, PrusaSlicer, etc.)")
    print("  2. Assign filament colors to each named object")
    print("  3. Slice and print!")
    print()


if __name__ == "__main__":
    main()