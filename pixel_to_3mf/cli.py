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
from datetime import datetime
from typing import Dict, List, Any

from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    DEFAULT_OUTPUT_SUFFIX,
    MAX_COLORS,
    BACKING_COLOR,
    COORDINATE_PRECISION,
    SUPPORTED_IMAGE_EXTENSIONS
)
from .config import ConversionConfig
from .pixel_to_3mf import convert_image_to_3mf


def is_image_file(filepath: Path) -> bool:
    """Check if a file is a supported image format."""
    return filepath.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def generate_batch_summary(
    results: Dict[str, List[Dict[str, Any]]],
    output_folder: Path,
    start_time: datetime,
    end_time: datetime
) -> str:
    """
    Generate a Markdown summary of batch processing results.
    
    Args:
        results: Dictionary with 'success', 'skipped', and 'failed' lists
        output_folder: Where to write the summary file
        start_time: When batch processing started
        end_time: When batch processing finished
        
    Returns:
        Path to the generated summary file
    """
    timestamp = start_time.strftime("%Y%m%d%H%M%S")
    summary_path = output_folder / f"batch_summary_{timestamp}.md"
    
    duration = end_time - start_time
    
    # Build the markdown content
    lines = []
    lines.append("# Batch Conversion Summary")
    lines.append(f"**Date:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Duration:** {duration.total_seconds():.1f} seconds")
    lines.append("")
    
    # Results overview
    lines.append("## Results Overview")
    lines.append(f"- ✅ **Successful:** {len(results['success'])} files")
    lines.append(f"- ⚠️  **Skipped:** {len(results['skipped'])} files")
    lines.append(f"- ❌ **Failed:** {len(results['failed'])} files")
    lines.append(f"- 📁 **Total processed:** {len(results['success']) + len(results['skipped']) + len(results['failed'])} files")
    lines.append("")
    
    # Successful conversions
    if results['success']:
        lines.append("## ✅ Successful Conversions")
        lines.append("")
        lines.append("| Input File | Output File | Regions | Colors | Model Size | File Size |")
        lines.append("|------------|-------------|---------|--------|------------|-----------|")
        
        for item in results['success']:
            lines.append(
                f"| {item['input_file']} | {item['output_file']} | "
                f"{item['num_regions']} | {item['num_colors']} | "
                f"{item['model_width_mm']:.1f}x{item['model_height_mm']:.1f}mm | "
                f"{item['file_size']} |"
            )
        lines.append("")
    
    # Skipped files
    if results['skipped']:
        lines.append("## ⚠️  Skipped Files")
        lines.append("")
        lines.append("These files were skipped due to resolution warnings:")
        lines.append("")
        
        for item in results['skipped']:
            lines.append(f"### {item['input_file']}")
            lines.append(f"**Reason:** {item['reason']}")
            lines.append("")
    
    # Failed files
    if results['failed']:
        lines.append("## ❌ Failed Files")
        lines.append("")
        lines.append("These files encountered errors during conversion:")
        lines.append("")
        
        for item in results['failed']:
            lines.append(f"### {item['input_file']}")
            lines.append(f"**Error:** {item['error']}")
            lines.append("")
    
    # Write the summary
    summary_path.write_text('\n'.join(lines), encoding='utf-8')
    
    return str(summary_path)


def process_batch(
    input_folder: Path,
    output_folder: Path,
    config: ConversionConfig
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process all images in a folder in batch mode.
    
    Args:
        input_folder: Folder containing input images
        output_folder: Folder where output files should be written
        config: ConversionConfig object with conversion parameters (including skip_checks and batch_mode flags)
        
    Returns:
        Dictionary with 'success', 'skipped', and 'failed' results
    """
    results = {
        'success': [],
        'skipped': [],
        'failed': []
    }
    
    # Make sure output folder exists
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Find all image files
    image_files = [f for f in input_folder.iterdir() if f.is_file() and is_image_file(f)]
    
    if not image_files:
        print(f"⚠️  No image files found in {input_folder}")
        return results
    
    print(f"📁 Found {len(image_files)} image(s) to process")
    print()
    
    # Process each file
    for i, input_path in enumerate(sorted(image_files), start=1):
        print(f"[{i}/{len(image_files)}] Processing: {input_path.name}")
        
        # Determine output path
        output_filename = input_path.stem + DEFAULT_OUTPUT_SUFFIX + '.3mf'
        output_path = output_folder / output_filename
        
        try:
            # Try to convert the image
            # All settings including skip_checks and batch_mode are in the config!
            stats = convert_image_to_3mf(
                input_path=str(input_path),
                output_path=str(output_path),
                config=config,
                progress_callback=None  # No progress in batch mode
            )
            
            # Success!
            results['success'].append({
                'input_file': input_path.name,
                'output_file': output_filename,
                'num_regions': stats['num_regions'],
                'num_colors': stats['num_colors'],
                'model_width_mm': stats['model_width_mm'],
                'model_height_mm': stats['model_height_mm'],
                'file_size': stats['file_size']
            })
            print(f"   ✅ Success: {stats['num_regions']} regions, {stats['file_size']}")
            
        except ValueError as e:
            error_msg = str(e)
            
            # Check if this is a resolution warning
            # The error message from the resolution check contains this specific text
            if "resolution too high" in error_msg.lower():
                results['skipped'].append({
                    'input_file': input_path.name,
                    'reason': error_msg
                })
                print(f"   ⚠️  Skipped: Resolution warning")
            else:
                # Other ValueError = actual failure (e.g., too many colors)
                results['failed'].append({
                    'input_file': input_path.name,
                    'error': error_msg
                })
                print(f"   ❌ Failed: {error_msg}")
                
        except Exception as e:
            # Any other error = failure
            results['failed'].append({
                'input_file': input_path.name,
                'error': str(e)
            })
            print(f"   ❌ Failed: {e}")
        
        print()
    
    return results


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
    
    # Positional argument: input file (optional if using batch mode)
    parser.add_argument(
        "image_file",
        type=str,
        nargs='?',  # Makes it optional
        help="Input pixel art image file (PNG, JPG, etc.) - not used in batch mode"
    )
    
    # Batch mode arguments
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Enable batch mode to process multiple images from a folder"
    )
    
    parser.add_argument(
        "--batch-input",
        type=str,
        default="batch/input",
        help="Input folder for batch mode (default: batch/input)"
    )
    
    parser.add_argument(
        "--batch-output",
        type=str,
        default="batch/output",
        help="Output folder for batch mode (default: batch/output)"
    )
    
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip resolution warnings in batch mode (process all files regardless of pixel size)"
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
        help=f"Height of backing plate in mm (default: {BASE_LAYER_HEIGHT_MM}). Set to 0 to disable backing plate."
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
    
    parser.add_argument(
        "--optimize-mesh",
        action="store_true",
        help="Use optimized polygon-based mesh generation (50-90%% reduction in vertices/triangles). "
             "Both optimized and original modes produce manifold meshes with identical visual results."
    )

    # Parse arguments
    args = parser.parse_args()
    
    # Validate batch mode vs single-file mode
    if args.batch:
        # Batch mode - image_file should not be provided
        if args.image_file:
            print("❌ Error: Don't specify an image file when using --batch mode", file=sys.stderr)
            print("   Use --batch-input to specify the input folder instead", file=sys.stderr)
            sys.exit(1)
    else:
        # Single-file mode - image_file is required
        if not args.image_file:
            print("❌ Error: Image file is required (or use --batch mode)", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    # Parse backing color if provided
    backing_color = BACKING_COLOR
    if args.backing_color:
        try:
            parts = args.backing_color.split(',')
            if len(parts) != 3:
                raise ValueError("Must have exactly 3 values (R,G,B)")
            r, g, b = (int(p.strip()) for p in parts)
            backing_color = (r, g, b)  # Explicitly create 3-tuple
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
            backing_color=backing_color,
            skip_checks=args.skip_checks,
            batch_mode=args.batch
        )
    except ValueError as e:
        print(f"❌ Error: Invalid configuration: {e}", file=sys.stderr)
        sys.exit(1)
    
    # =========================================================================
    # Enable optimized mesh generation if requested
    # =========================================================================
    if args.optimize_mesh:
        import pixel_to_3mf.mesh_generator as mg
        mg.USE_OPTIMIZED_MESH_GENERATION = True

    # =========================================================================
    # BATCH MODE
    # =========================================================================
    if args.batch:
        print("=" * 70)
        print("🎨 Pixel Art to 3MF Converter - BATCH MODE")
        print("=" * 70)
        print()
        
        input_folder = Path(args.batch_input)
        output_folder = Path(args.batch_output)
        
        # Validate input folder exists
        if not input_folder.exists():
            print(f"❌ Error: Input folder not found: {input_folder}", file=sys.stderr)
            sys.exit(1)
        
        if not input_folder.is_dir():
            print(f"❌ Error: Input path is not a directory: {input_folder}", file=sys.stderr)
            sys.exit(1)
        
        print(f"📂 Input folder:  {input_folder}")
        print(f"📂 Output folder: {output_folder}")
        print(f"⚙️  Skip checks:   {args.skip_checks}")
        print()
        
        # Process the batch
        start_time = datetime.now()
        results = process_batch(input_folder, output_folder, config)
        end_time = datetime.now()
        
        # Generate summary
        summary_path = generate_batch_summary(results, output_folder, start_time, end_time)
        
        # Print final results
        print("=" * 70)
        print("✅ Batch processing complete!")
        print("=" * 70)
        print(f"📊 Results:")
        print(f"   ✅ Successful: {len(results['success'])} files")
        print(f"   ⚠️  Skipped:    {len(results['skipped'])} files")
        print(f"   ❌ Failed:     {len(results['failed'])} files")
        print()
        print(f"📄 Summary: {summary_path}")
        print()
        
        # Exit with error code if there were failures
        if results['failed']:
            sys.exit(1)
        
        return

    # =========================================================================
    # SINGLE-FILE MODE
    # =========================================================================

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