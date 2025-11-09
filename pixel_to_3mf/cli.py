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

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    DEFAULT_OUTPUT_SUFFIX,
    MAX_COLORS,
    BACKING_COLOR,
    COORDINATE_PRECISION,
    SUPPORTED_IMAGE_EXTENSIONS,
    COLOR_NAMING_MODE,
    DEFAULT_FILAMENT_MAKER,
    DEFAULT_FILAMENT_TYPE,
    DEFAULT_FILAMENT_FINISH,
    PADDING_COLOR,
    __version__
)
from .config import ConversionConfig
from .pixel_to_3mf import convert_image_to_3mf

# Create Rich consoles for output and errors
console = Console()
error_console = Console(stderr=True)


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
    config: ConversionConfig,
    recurse: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process all images in a folder in batch mode.
    
    Args:
        input_folder: Folder containing input images
        output_folder: Folder where output files should be written
        config: ConversionConfig object with conversion parameters (including skip_checks and batch_mode flags)
        recurse: If True, process subfolders recursively and maintain folder structure
        
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
    
    # Find all image files (recursively or not)
    if recurse:
        image_files = [f for f in input_folder.rglob('*') if f.is_file() and is_image_file(f)]
    else:
        image_files = [f for f in input_folder.iterdir() if f.is_file() and is_image_file(f)]
    
    if not image_files:
        console.print(f"[yellow]⚠️  No image files found in {input_folder}[/yellow]")
        return results
    
    console.print(f"[cyan]📁 Found {len(image_files)} image(s) to process[/cyan]")
    console.print()
    
    # Process each file
    for i, input_path in enumerate(sorted(image_files), start=1):
        console.print(f"[cyan][{i}/{len(image_files)}] Processing: {input_path.name}[/cyan]")
        
        # Determine output path - preserve folder structure if recursive
        if recurse:
            # Calculate relative path from input folder
            relative_path = input_path.relative_to(input_folder)
            # Create the same subfolder structure in output
            output_file_path = output_folder / relative_path.parent / (relative_path.stem + DEFAULT_OUTPUT_SUFFIX + '.3mf')
            # Ensure the subfolder exists
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Flat structure - all files go to output folder root
            output_filename = input_path.stem + DEFAULT_OUTPUT_SUFFIX + '.3mf'
            output_file_path = output_folder / output_filename
        
        try:
            # Try to convert the image
            # All settings including skip_checks and batch_mode are in the config!
            stats = convert_image_to_3mf(
                input_path=str(input_path),
                output_path=str(output_file_path),
                config=config,
                progress_callback=None  # No progress in batch mode
            )
            
            # Success!
            # Store relative path for better reporting in recursive mode
            if recurse:
                output_display = str(output_file_path.relative_to(output_folder))
            else:
                output_display = output_file_path.name
                
            results['success'].append({
                'input_file': str(input_path.relative_to(input_folder)) if recurse else input_path.name,
                'output_file': output_display,
                'num_regions': stats['num_regions'],
                'num_colors': stats['num_colors'],
                'model_width_mm': stats['model_width_mm'],
                'model_height_mm': stats['model_height_mm'],
                'file_size': stats['file_size']
            })
            console.print(f"[green]   ✅ Success: {stats['num_regions']} regions, {stats['file_size']}[/green]")
            
        except ValueError as e:
            error_msg = str(e)
            
            # Determine input file display name
            input_display = str(input_path.relative_to(input_folder)) if recurse else input_path.name
            
            # Check if this is a resolution warning
            # The error message from the resolution check contains this specific text
            if "resolution too high" in error_msg.lower():
                results['skipped'].append({
                    'input_file': input_display,
                    'reason': error_msg
                })
                console.print(f"[yellow]   ⚠️  Skipped: Resolution warning[/yellow]")
            else:
                # Other ValueError = actual failure (e.g., too many colors)
                results['failed'].append({
                    'input_file': input_display,
                    'error': error_msg
                })
                error_console.print(f"[red]   ❌ Failed: {error_msg}[/red]")
                
        except Exception as e:
            # Any other error = failure
            input_display = str(input_path.relative_to(input_folder)) if recurse else input_path.name
            results['failed'].append({
                'input_file': input_display,
                'error': str(e)
            })
            error_console.print(f"[red]   ❌ Failed: {e}[/red]")
        
        console.print()
    
    return results


def main():
    """Main CLI entry point."""
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(
        description="Convert pixel art images to 3D printable 3MF files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file conversion
  %(prog)s sprite.png
  %(prog)s mario.png --output mario_model.3mf
  %(prog)s pixel_art.png --max-size 150 --color-height 1.5
  %(prog)s icon.png --base-height 2.0 --max-colors 20
  
  # Batch mode
  %(prog)s --batch --batch-input images/ --batch-output models/
  %(prog)s --batch --batch-input sprites/ --batch-output output/ --recurse

The program will:
  1. Load your pixel art image
  2. Calculate appropriate scaling to fit your print bed
  3. Merge connected same-color pixels into regions
  4. Generate 3D geometry (extruded regions + backing plate)
  5. Export to 3MF with color names for easy slicer setup
        """
    )
    
    # Version argument
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit"
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
    
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Process subfolders recursively in batch mode, maintaining folder structure in output"
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
        "--color-mode",
        type=str,
        choices=["color", "filament", "hex"],
        default=COLOR_NAMING_MODE,
        help=f"Color naming mode: 'color' for CSS names, 'filament' for filament colors, 'hex' for hex codes (default: {COLOR_NAMING_MODE})"
    )
    
    parser.add_argument(
        "--filament-maker",
        type=str,
        default=None,
        help=f"Filament maker filter(s) for 'filament' mode. Comma-separated for multiple (default: {DEFAULT_FILAMENT_MAKER})"
    )
    
    parser.add_argument(
        "--filament-type",
        type=str,
        default=None,
        help=f"Filament type filter(s) for 'filament' mode. Comma-separated for multiple (default: {DEFAULT_FILAMENT_TYPE})"
    )
    
    parser.add_argument(
        "--filament-finish",
        type=str,
        default=None,
        help=f"Filament finish filter(s) for 'filament' mode. Comma-separated for multiple (default: {', '.join(DEFAULT_FILAMENT_FINISH)})"
    )
    
    parser.add_argument(
        "--auto-crop",
        action="store_true",
        help="Automatically crop away fully transparent edges before processing"
    )
    
    parser.add_argument(
        "--padding-size",
        type=int,
        default=0,
        help="Add padding/outline around non-transparent pixels (in pixels). "
             "Helps with diagonally-connected pixels in 3D printing. "
             "0 = disabled (default), >0 = padding size. "
             "Canvas will be expanded to accommodate padding."
    )
    
    parser.add_argument(
        "--padding-color",
        type=str,
        default=None,
        help=f"Padding color as R,G,B (e.g., '255,255,255' for white). "
             f"Default: {PADDING_COLOR}. Only used when --padding-size > 0."
    )
    
    parser.add_argument(
        "--connectivity",
        type=int,
        choices=[0, 4, 8],
        default=8,
        help="Pixel connectivity mode: "
             "0 (no merging, each pixel separate - for debugging), "
             "4 (edge-connected only - classic, simple geometry), "
             "8 (includes diagonals - fewer objects, may be complex). "
             "Default: 8"
    )
    
    parser.add_argument(
        "--trim",
        action="store_true",
        help="Remove disconnected pixels (pixels that only connect via corners/diagonals). "
             "These pixels are unreliable for 3D printing as they share only a vertex, not an edge."
    )
    
    parser.add_argument(
        "--optimize-mesh",
        action="store_true",
        help="Use optimized polygon-based mesh generation (50-90%% reduction in vertices/triangles). "
             "Both optimized and original modes produce manifold meshes with identical visual results."
    )
    
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Automatically reduce colors when image exceeds max-colors. "
             "Eliminates need to preprocess images in external applications."
    )
    
    parser.add_argument(
        "--quantize-algo",
        type=str,
        choices=["none", "floyd"],
        default="none",
        help="Quantization algorithm: 'none' for simple nearest color (faster, sharper), "
             "'floyd' for Floyd-Steinberg dithering (slower, smoother). Default: none"
    )
    
    parser.add_argument(
        "--quantize-colors",
        type=int,
        default=None,
        help="Number of colors to quantize to. Defaults to max-colors if not specified. "
             "Only used when --quantize is enabled."
    )
    
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate a summary file listing all colors/filaments used in the conversion. "
             "Summary is saved as {output_name}.summary.txt in the same location as the output file."
    )


    # Parse arguments
    args = parser.parse_args()
    
    # Validate batch mode vs single-file mode
    if args.batch:
        # Batch mode - image_file should not be provided
        if args.image_file:
            error_console.print("[red]❌ Error: Don't specify an image file when using --batch mode[/red]")
            error_console.print("[red]   Use --batch-input to specify the input folder instead[/red]")
            sys.exit(1)
    else:
        # Single-file mode - image_file is required
        if not args.image_file:
            error_console.print("[red]❌ Error: Image file is required (or use --batch mode)[/red]")
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
            error_console.print(f"[red]❌ Error: Invalid backing color '{args.backing_color}': {e}[/red]")
            error_console.print("[red]   Format: R,G,B (e.g., '255,255,255' for white)[/red]")
            sys.exit(1)
    
    # Parse padding color if provided
    padding_color = PADDING_COLOR
    if args.padding_color:
        try:
            parts = args.padding_color.split(',')
            if len(parts) != 3:
                raise ValueError("Must have exactly 3 values (R,G,B)")
            r, g, b = (int(p.strip()) for p in parts)
            padding_color = (r, g, b)  # Explicitly create 3-tuple
            if not all(0 <= c <= 255 for c in padding_color):
                raise ValueError("RGB values must be 0-255")
        except Exception as e:
            error_console.print(f"[red]❌ Error: Invalid padding color '{args.padding_color}': {e}[/red]")
            error_console.print("[red]   Format: R,G,B (e.g., '255,255,255' for white)[/red]")
            sys.exit(1)

    # Parse filament filters if provided (can be comma-separated)
    filament_maker = DEFAULT_FILAMENT_MAKER
    if args.filament_maker:
        filament_maker = [m.strip() for m in args.filament_maker.split(',')]
    
    filament_type = DEFAULT_FILAMENT_TYPE
    if args.filament_type:
        filament_type = [t.strip() for t in args.filament_type.split(',')]
    
    filament_finish = DEFAULT_FILAMENT_FINISH
    if args.filament_finish:
        filament_finish = [f.strip() for f in args.filament_finish.split(',')]

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
            batch_mode=args.batch,
            color_naming_mode=args.color_mode,
            filament_maker=filament_maker,
            filament_type=filament_type,
            filament_finish=filament_finish,
            auto_crop=args.auto_crop,
            connectivity=args.connectivity,
            trim_disconnected=args.trim,
            padding_size=args.padding_size,
            padding_color=padding_color,
            quantize=args.quantize,
            quantize_algo=args.quantize_algo,
            quantize_colors=args.quantize_colors,
            generate_summary=args.summary
        )
    except ValueError as e:
        error_console.print(f"[red]❌ Error: Invalid configuration: {e}[/red]")
        sys.exit(1)
    
    # =========================================================================
    # Enable optimized mesh generation if requested
    # =========================================================================
    if args.optimize_mesh:
        import pixel_to_3mf.mesh_generator as mg
        import logging
        
        # Configure logging for polygon optimizer module only
        # This avoids interfering with other logging configurations
        optimizer_logger = logging.getLogger('pixel_to_3mf.polygon_optimizer')
        optimizer_logger.setLevel(logging.INFO)
        
        # Add handler only if one doesn't exist
        if not optimizer_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('   [OPTIMIZE] %(message)s'))
            optimizer_logger.addHandler(handler)
        
        # Enable optimized mesh generation
        mg.USE_OPTIMIZED_MESH_GENERATION = True

    # =========================================================================
    # BATCH MODE
    # =========================================================================
    if args.batch:
        console.print(Panel.fit(
            "[bold cyan]🎨 Pixel Art to 3MF Converter - BATCH MODE[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
        
        input_folder = Path(args.batch_input)
        output_folder = Path(args.batch_output)
        
        # Validate input folder exists
        if not input_folder.exists():
            console.print(f"[red]❌ Error: Input folder not found: {input_folder}[/red]")
            sys.exit(1)
        
        if not input_folder.is_dir():
            console.print(f"[red]❌ Error: Input path is not a directory: {input_folder}[/red]")
            sys.exit(1)
        
        console.print(f"[cyan]📂 Input folder:  {input_folder}[/cyan]")
        console.print(f"[cyan]📂 Output folder: {output_folder}[/cyan]")
        console.print(f"[cyan]⚙️  Skip checks:   {args.skip_checks}[/cyan]")
        console.print(f"[cyan]🔄 Recursive:     {args.recurse}[/cyan]")
        console.print()
        
        # Process the batch
        start_time = datetime.now()
        results = process_batch(input_folder, output_folder, config, recurse=args.recurse)
        end_time = datetime.now()
        
        # Generate summary
        summary_path = generate_batch_summary(results, output_folder, start_time, end_time)
        
        # Print final results
        console.print(Panel.fit(
            "[bold green]✅ Batch processing complete![/bold green]",
            border_style="green"
        ))
        console.print(f"[bold]📊 Results:[/bold]")
        console.print(f"   [green]✅ Successful: {len(results['success'])} files[/green]")
        console.print(f"   [yellow]⚠️  Skipped:    {len(results['skipped'])} files[/yellow]")
        console.print(f"   [red]❌ Failed:     {len(results['failed'])} files[/red]")
        console.print()
        console.print(f"[cyan]📄 Summary: {summary_path}[/cyan]")
        console.print()
        
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
        console.print(f"[red]❌ Error: Input file not found: {args.image_file}[/red]")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Default: same name as input with _model.3mf suffix
        output_path = str(input_path.with_suffix('')) + DEFAULT_OUTPUT_SUFFIX + '.3mf'
    
    # Print header
    console.print(Panel.fit(
        "[bold cyan]🎨 Pixel Art to 3MF Converter[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Display configuration table
    config_table = Table(title="Configuration", box=box.ROUNDED, show_header=True, header_style="bold cyan")
    config_table.add_column("Parameter", style="bold yellow")
    config_table.add_column("Value", style="white")
    
    # Input/Output
    config_table.add_row("Input File", str(input_path))
    config_table.add_row("Output File", output_path)
    
    # Dimensions
    config_table.add_row("Max Size", f"{config.max_size_mm}mm")
    config_table.add_row("Line Width", f"{config.line_width_mm}mm")
    
    # Heights
    config_table.add_row("Color Layer Height", f"{config.color_height_mm}mm")
    config_table.add_row("Base Layer Height", f"{config.base_height_mm}mm" if config.base_height_mm > 0 else "0mm (disabled)")
    
    # Colors
    config_table.add_row("Max Colors", str(config.max_colors))
    config_table.add_row("Backing Color", f"RGB{config.backing_color}")
    config_table.add_row("Color Naming Mode", config.color_naming_mode)
    
    # Filament filters (if in filament mode)
    if config.color_naming_mode == "filament":
        maker_str = ", ".join(config.filament_maker) if isinstance(config.filament_maker, list) else config.filament_maker
        type_str = ", ".join(config.filament_type) if isinstance(config.filament_type, list) else config.filament_type
        finish_str = ", ".join(config.filament_finish) if isinstance(config.filament_finish, list) else config.filament_finish
        config_table.add_row("  Filament Maker(s)", maker_str)
        config_table.add_row("  Filament Type(s)", type_str)
        config_table.add_row("  Filament Finish(es)", finish_str)
    
    # Processing options
    config_table.add_row("Auto-Crop", "Enabled" if config.auto_crop else "Disabled")
    connectivity_map = {0: "None (separate pixels)", 4: "4-connected (edges only)", 8: "8-connected (includes diagonals)"}
    config_table.add_row("Connectivity", connectivity_map.get(config.connectivity, str(config.connectivity)))
    
    # Padding options
    if config.padding_size > 0:
        config_table.add_row("Padding", f"{config.padding_size}px, RGB{config.padding_color}")
    else:
        config_table.add_row("Padding", "Disabled")
    
    # Mesh optimization
    import pixel_to_3mf.mesh_generator as mg
    config_table.add_row("Mesh Optimization", "Enabled" if mg.USE_OPTIMIZED_MESH_GENERATION else "Disabled")
    
    # Color quantization
    if config.quantize:
        quant_colors = config.quantize_colors if config.quantize_colors is not None else config.max_colors
        config_table.add_row("Color Quantization", f"Enabled ({config.quantize_algo}, {quant_colors} colors)")
    else:
        config_table.add_row("Color Quantization", "Disabled")
    
    console.print(config_table)
    console.print()
    
    # Warning callback for resolution issues
    def warning_callback(warning_type: str, data: Dict[str, Any]) -> bool:
        """Handle warnings during conversion, ask user for confirmation."""
        if warning_type == 'resolution_warning':
            # Display warning panel
            console.print()
            warning_panel = Panel(
                "[bold yellow]⚠️  WARNING: Image resolution may be too high for reliable printing![/bold yellow]\n\n"
                f"[cyan]Image dimensions:[/cyan] {data['image_width']} x {data['image_height']} pixels "
                f"({data['max_dimension_px']}px largest)\n"
                f"[cyan]Your line width:[/cyan]  {data['line_width_mm']}mm\n"
                f"[cyan]Max recommended:[/cyan]  {data['max_recommended_px']} pixels "
                f"({data['max_size_mm']}mm ÷ {data['line_width_mm']}mm)\n\n"
                f"[yellow]Your pixels will be: {data['pixel_size_mm']:.3f}mm each[/yellow]\n"
                f"[yellow]This is SMALLER than your line width ({data['line_width_mm']}mm)![/yellow]\n\n"
                "[dim]The printer may struggle with details this fine.[/dim]",
                title="[bold yellow]Resolution Warning[/bold yellow]",
                border_style="yellow"
            )
            console.print(warning_panel)
            console.print()
            
            # Ask user
            response = console.input("[yellow]Do you want to continue anyway? [y/N]:[/yellow] ").strip().lower()
            
            if response not in ['y', 'yes']:
                console.print()
                error_console.print("[red]Conversion cancelled.[/red]")
                console.print()
                console.print("[bold cyan]💡 Suggestions:[/bold cyan]")
                console.print(f"   • Resize your image to max {data['max_recommended_px']}px in an image editor")
                console.print(f"   • Increase --max-size (e.g., --max-size {int(data['max_dimension_px'] * data['line_width_mm'])})")
                console.print(f"   • Use a smaller nozzle and adjust --line-width accordingly")
                console.print()
                return False
            
            console.print()
            console.print("[green]Continuing with conversion...[/green]")
            console.print()
            return True
        
        return True
    
    # Progress tracking with Rich
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    ) as progress:
        
        # Create tasks for each stage
        load_task = progress.add_task("[cyan]📁 Loading image...", total=None)
        merge_task = None
        mesh_task = None
        export_task = None
        
        # Track current stage and regions
        current_stage = None
        total_regions = 0
        
        def progress_callback(stage: str, message: str):
            nonlocal current_stage, merge_task, mesh_task, export_task, total_regions
            
            # Update stage if it changed
            if stage != current_stage:
                current_stage = stage
                
                if stage == 'load':
                    progress.update(load_task, description=f"[cyan]📁 Loading image... {message}")
                elif stage == 'merge':
                    progress.update(load_task, completed=True)
                    merge_task = progress.add_task("[magenta]🧩 Merging regions...", total=None)
                elif stage == 'mesh':
                    if merge_task is not None:
                        progress.update(merge_task, completed=True)
                    # Extract number of regions from message if available
                    if "Found" in message and "regions" in message:
                        try:
                            total_regions = int(message.split()[1])
                            mesh_task = progress.add_task("[blue]🎲 Generating 3D geometry...", total=total_regions)
                        except:
                            mesh_task = progress.add_task("[blue]🎲 Generating 3D geometry...", total=None)
                    else:
                        mesh_task = progress.add_task("[blue]🎲 Generating 3D geometry...", total=None)
                elif stage == 'export':
                    if mesh_task is not None:
                        progress.update(mesh_task, completed=True)
                    export_task = progress.add_task("[green]📦 Writing 3MF file...", total=None)
            else:
                # Update existing task
                if stage == 'load' and load_task is not None:
                    progress.update(load_task, description=f"[cyan]📁 Loading image... {message}")
                elif stage == 'merge' and merge_task is not None:
                    progress.update(merge_task, description=f"[magenta]🧩 Merging regions... {message}")
                elif stage == 'mesh' and mesh_task is not None:
                    # Check if this is a region progress update
                    if "Region" in message and "/" in message:
                        try:
                            parts = message.split()
                            region_info = parts[1].split("/")
                            current_region = int(region_info[0])
                            progress.update(mesh_task, completed=current_region, description=f"[blue]🎲 Generating 3D geometry... {message}")
                        except:
                            progress.update(mesh_task, description=f"[blue]🎲 Generating 3D geometry... {message}")
                    else:
                        progress.update(mesh_task, description=f"[blue]🎲 Generating 3D geometry... {message}")
                elif stage == 'export' and export_task is not None:
                    progress.update(export_task, description=f"[green]📦 Writing 3MF file... {message}")
        
        # Run the conversion!
        try:
            stats = convert_image_to_3mf(
                input_path=str(input_path),
                output_path=output_path,
                config=config,
                progress_callback=progress_callback,
                warning_callback=warning_callback
            )
            # Mark final task as complete
            if export_task is not None:
                progress.update(export_task, completed=True)
        except FileNotFoundError as e:
            error_console.print(f"\n[red]❌ Error: {e}[/red]")
            sys.exit(1)
        except ValueError as e:
            error_console.print(f"\n[red]❌ Invalid parameter: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            error_console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Print summary
    console.print()
    console.print(Panel.fit(
        "[bold green]✅ Conversion complete![/bold green]",
        border_style="green"
    ))
    
    # Create a table for statistics
    stats_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    stats_table.add_column("Label", style="bold cyan")
    stats_table.add_column("Value", style="white")
    
    stats_table.add_row("Image:", f"{stats['image_width']} x {stats['image_height']} pixels")
    stats_table.add_row("Model:", f"{stats['model_width_mm']:.1f} x {stats['model_height_mm']:.1f} mm")
    stats_table.add_row("Pixel size:", f"{round(stats['pixel_size_mm'], COORDINATE_PRECISION)} mm")
    stats_table.add_row("Regions:", f"{stats['num_regions']} ({stats['num_colors']} unique colors)")
    stats_table.add_row("Output:", f"{stats['output_path']} ({stats['file_size']})")
    
    # Add summary path if generated
    if 'summary_path' in stats:
        stats_table.add_row("Summary:", stats['summary_path'])
    
    console.print(stats_table)
    console.print()
    console.print("[bold yellow]🎯 Next steps:[/bold yellow]")
    console.print("  [cyan]1.[/cyan] Open the 3MF file in your slicer (Bambu Studio, PrusaSlicer, etc.)")
    console.print("  [cyan]2.[/cyan] Assign filament colors to each named object")
    console.print("  [cyan]3.[/cyan] Slice and print!")
    console.print()


if __name__ == "__main__":
    main()