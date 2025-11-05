"""
Command-line interface for color_tools.

Provides three main commands:
- color: Search and query CSS colors
- filament: Search and query 3D printing filaments
- convert: Convert between color spaces and check gamut

This is the "top" of the dependency tree - it imports from everywhere
but nothing imports from it (except __main__.py).
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from .constants import ColorConstants
from .config import set_dual_color_mode
from .conversions import rgb_to_lab, lab_to_rgb, rgb_to_hsl, hsl_to_rgb, rgb_to_lch, lch_to_lab, lch_to_rgb
from .gamut import is_in_srgb_gamut, find_nearest_in_gamut
from .palette import Palette, FilamentPalette, load_colors, load_filaments


def _get_program_name() -> str:
    """
    Determine the appropriate program name based on how the script was invoked.
    
    Returns:
        A user-friendly program name for help text
    """
    argv0 = sys.argv[0]
    
    # Case 1: Running as a module (python -m color_tools)
    if argv0.endswith('__main__.py') or '__main__' in argv0:
        return "python -m color_tools"
    
    # Case 2: Running the script directly (python color_tools.py)
    elif argv0.endswith('color_tools.py'):
        return "python color_tools.py"
    
    # Case 3: Installed as a console script (color-tools)
    elif 'color_tools' in argv0 or 'color-tools' in argv0:
        # Extract just the command name without path
        from pathlib import Path
        return Path(argv0).name
    
    # Case 4: Unknown/fallback - use the basename
    else:
        from pathlib import Path
        return Path(argv0).name


def main():
    """
    Main entry point for the CLI.
    
    Note: No `if __name__ == "__main__":` here! That's __main__.py's job.
    This function is just the CLI logic - pure and testable.
    """
    # Determine the proper program name based on how we were invoked
    prog_name = _get_program_name()
    
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Color search and conversion tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Find nearest CSS color to an RGB value
  {prog_name} color --nearest --value 128 64 200
  
  # Find color by name
  {prog_name} color --name "coral"
  
  # Find nearest filament to an RGB color
  {prog_name} filament --nearest --value 255 0 0
  
  # Find all PLA filaments from two different makers
  {prog_name} filament --type PLA --maker "Bambu Lab" "Sunlu"

  # List all filament makers
  {prog_name} filament --list-makers
  
  # Convert between color spaces
  {prog_name} convert --from rgb --to lab --value 255 128 0
  
  # Check if LAB color is in sRGB gamut
  {prog_name} convert --check-gamut --value 50 100 50
        """
    )
    
    # Global arguments (apply to all subcommands)
    parser.add_argument(
        "--json", 
        type=str, 
        default=None,  # Will use default package data if None
        help="Path to JSON data file (default: uses package data)"
    )
    parser.add_argument(
        "--verify-constants",
        action="store_true",
        help="Verify integrity of color science constants before proceeding"
    )
    
    # Create subparsers for the three main commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # ==================== COLOR SUBCOMMAND ====================
    color_parser = subparsers.add_parser(
        "color",
        help="Work with CSS colors",
        description="Search and query CSS color database"
    )
    
    color_parser.add_argument(
        "--nearest", 
        action="store_true", 
        help="Find nearest color to the given value"
    )
    color_parser.add_argument(
        "--name", 
        type=str, 
        help="Find an exact color by name"
    )
    color_parser.add_argument(
        "--value", 
        nargs=3, 
        type=float, 
        metavar=("V1", "V2", "V3"),
        help="Color value tuple (RGB: r g b | HSL: h s l | LAB: L a b | LCH: L C h)"
    )
    color_parser.add_argument(
        "--space", 
        choices=["rgb", "hsl", "lab", "lch"], 
        default="lab",
        help="Color space of the input value (default: lab)"
    )
    color_parser.add_argument(
        "--metric",
        choices=["euclidean", "de76", "de94", "de2000", "cmc", "cmc21", "cmc11"],
        default="de2000",
        help="Distance metric for LAB space (default: de2000). 'cmc21'=CMC(2:1), 'cmc11'=CMC(1:1)"
    )
    color_parser.add_argument(
        "--cmc-l", 
        type=float, 
        default=ColorConstants.CMC_L_DEFAULT, 
        help="CMC lightness parameter (default: 2.0)"
    )
    color_parser.add_argument(
        "--cmc-c", 
        type=float, 
        default=ColorConstants.CMC_C_DEFAULT, 
        help="CMC chroma parameter (default: 1.0)"
    )
    
    # ==================== FILAMENT SUBCOMMAND ====================
    filament_parser = subparsers.add_parser(
        "filament",
        help="Work with 3D printing filaments",
        description="Search and query 3D printing filament database"
    )
    
    filament_parser.add_argument(
        "--nearest", 
        action="store_true", 
        help="Find nearest filament to the given RGB color"
    )
    filament_parser.add_argument(
        "--value", 
        nargs=3, 
        type=int, 
        metavar=("R", "G", "B"),
        help="RGB color value (0-255 for each component)"
    )
    filament_parser.add_argument(
        "--metric",
        choices=["euclidean", "de76", "de94", "de2000", "cmc"],
        default="de2000",
        help="Distance metric (default: de2000)"
    )
    filament_parser.add_argument(
        "--cmc-l", 
        type=float, 
        default=ColorConstants.CMC_L_DEFAULT, 
        help="CMC lightness parameter (default: 2.0)"
    )
    filament_parser.add_argument(
        "--cmc-c", 
        type=float, 
        default=ColorConstants.CMC_C_DEFAULT, 
        help="CMC chroma parameter (default: 1.0)"
    )
    
    # List operations
    filament_parser.add_argument(
        "--list-makers", 
        action="store_true", 
        help="List all filament makers"
    )
    filament_parser.add_argument(
        "--list-types", 
        action="store_true", 
        help="List all filament types"
    )
    filament_parser.add_argument(
        "--list-finishes", 
        action="store_true", 
        help="List all filament finishes"
    )
    
    # Filter operations
    filament_parser.add_argument(
        "--maker", 
        nargs='+',
        type=str, 
        help="Filter by one or more makers (e.g., --maker \"Bambu Lab\" \"Polymaker\")"
    )
    filament_parser.add_argument(
        "--type", 
        nargs='+',
        type=str, 
        help="Filter by one or more types (e.g., --type PLA \"PLA+\")"
    )
    filament_parser.add_argument(
        "--finish", 
        nargs='+',
        type=str, 
        help="Filter by one or more finishes (e.g., --finish Matte \"Silk+\")"
    )
    filament_parser.add_argument(
        "--color", 
        type=str, 
        help="Filter by color name"
    )
    filament_parser.add_argument(
        "--dual-color-mode",
        choices=["first", "last", "mix"],
        default="first",
        help="How to handle dual-color filaments: 'first' (default), 'last', or 'mix' (perceptual blend)"
    )
    
    # ==================== CONVERT SUBCOMMAND ====================
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert between color spaces",
        description="Convert colors between RGB, HSL, LAB, and LCH spaces"
    )
    
    convert_parser.add_argument(
        "--from",
        dest="from_space",
        choices=["rgb", "hsl", "lab", "lch"],
        help="Source color space"
    )
    convert_parser.add_argument(
        "--to",
        dest="to_space",
        choices=["rgb", "hsl", "lab", "lch"],
        help="Target color space"
    )
    convert_parser.add_argument(
        "--value", 
        nargs=3, 
        type=float, 
        metavar=("V1", "V2", "V3"),
        help="Color value tuple"
    )
    convert_parser.add_argument(
        "--check-gamut", 
        action="store_true", 
        help="Check if LAB/LCH color is in sRGB gamut (requires --value)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Verify constants integrity if requested
    if args.verify_constants:
        if not ColorConstants.verify_integrity():
            print("ERROR: ColorConstants integrity check FAILED!", file=sys.stderr)
            print("The color science constants have been modified.", file=sys.stderr)
            print(f"Expected hash: {ColorConstants._EXPECTED_HASH}", file=sys.stderr)
            print(f"Current hash:  {ColorConstants._compute_hash()}", file=sys.stderr)
            sys.exit(1)
        print("✓ ColorConstants integrity verified")
        # If only verifying constants (no other command), exit after success
        if not args.command:
            sys.exit(0)
    
    # Handle no subcommand
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Convert json_path to Path if provided
    json_path = Path(args.json) if args.json else None
    
    # ==================== COLOR COMMAND HANDLER ====================
    if args.command == "color":
        # Load color palette
        palette = Palette(load_colors(json_path))
        
        if args.name:
            rec = palette.find_by_name(args.name)
            if not rec:
                print(f"Color '{args.name}' not found")
                sys.exit(1)
            print(f"Name: {rec.name}")
            print(f"Hex:  {rec.hex}")
            print(f"RGB:  {rec.rgb}")
            print(f"HSL:  ({rec.hsl[0]:.1f}°, {rec.hsl[1]:.1f}%, {rec.hsl[2]:.1f}%)")
            print(f"LAB:  ({rec.lab[0]:.2f}, {rec.lab[1]:.2f}, {rec.lab[2]:.2f})")
            print(f"LCH:  ({rec.lch[0]:.2f}, {rec.lch[1]:.2f}, {rec.lch[2]:.1f}°)")
            sys.exit(0)
        
        if args.nearest:
            if not args.value:
                print("Error: --nearest requires --value")
                sys.exit(2)
            
            val = tuple(args.value)
            
            # Use the specified color space directly
            rec, d = palette.nearest_color(
                val,
                space=args.space,
                metric=args.metric,
                cmc_l=args.cmc_l,
                cmc_c=args.cmc_c,
            )
            print(f"Nearest color: {rec.name} (distance={d:.2f})")
            print(f"Hex:  {rec.hex}")
            print(f"RGB:  {rec.rgb}")
            print(f"HSL:  ({rec.hsl[0]:.1f}°, {rec.hsl[1]:.1f}%, {rec.hsl[2]:.1f}%)")
            print(f"LAB:  ({rec.lab[0]:.2f}, {rec.lab[1]:.2f}, {rec.lab[2]:.2f})")
            print(f"LCH:  ({rec.lch[0]:.2f}, {rec.lch[1]:.2f}, {rec.lch[2]:.1f}°)")
            sys.exit(0)
        
        # If we get here, no valid color operation was specified
        color_parser.print_help()
        sys.exit(0)
    
    # ==================== FILAMENT COMMAND HANDLER ====================
    elif args.command == "filament":
        # Set dual-color mode BEFORE loading any filaments
        # This is CRITICAL - the mode affects how FilamentRecord.rgb works!
        if hasattr(args, 'dual_color_mode'):
            set_dual_color_mode(args.dual_color_mode)
        
        # Load filament palette
        filament_palette = FilamentPalette(load_filaments(json_path))
        
        if args.list_makers:
            print("Available makers:")
            for maker in filament_palette.makers:
                count = len(filament_palette.find_by_maker(maker))
                print(f"  {maker} ({count} filaments)")
            sys.exit(0)
        
        if args.list_types:
            print("Available types:")
            for type_name in filament_palette.types:
                count = len(filament_palette.find_by_type(type_name))
                print(f"  {type_name} ({count} filaments)")
            sys.exit(0)
        
        if args.list_finishes:
            print("Available finishes:")
            for finish in filament_palette.finishes:
                count = len(filament_palette.find_by_finish(finish))
                print(f"  {finish} ({count} filaments)")
            sys.exit(0)
        
        if args.nearest:
            if not args.value:
                print("Error: --nearest requires --value with RGB components")
                sys.exit(2)
            
            rgb_val = tuple(args.value)
            
            try:
                rec, d = filament_palette.nearest_filament(
                    rgb_val,
                    metric=args.metric,
                    maker=args.maker,
                    type_name=args.type,
                    finish=args.finish,
                    cmc_l=args.cmc_l,
                    cmc_c=args.cmc_c,
                )
                print(f"Nearest filament: (distance={d:.2f})")
                print(f"  {rec}")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
            sys.exit(0)

        if args.maker or args.type or args.finish or args.color:
            # Filter and display filaments
            results = filament_palette.filter(
                maker=args.maker,
                type_name=args.type,
                finish=args.finish,
                color=args.color
            )
            
            if not results:
                print("No filaments found matching the criteria")
                sys.exit(1)
            
            print(f"Found {len(results)} filament(s):")
            for rec in results:
                print(f"  {rec}")
            sys.exit(0)
        
        # If we get here, no valid filament operation was specified
        filament_parser.print_help()
        sys.exit(0)
    
    # ==================== CONVERT COMMAND HANDLER ====================
    elif args.command == "convert":
        if args.check_gamut:
            if not args.value:
                print("Error: --check-gamut requires --value")
                sys.exit(2)
            
            val = tuple(args.value)
            
            # Assume LAB unless otherwise specified
            if args.from_space == "lch":
                lab = lch_to_lab(val)
            else:
                lab = val
            
            in_gamut = is_in_srgb_gamut(lab)
            print(f"LAB({lab[0]:.2f}, {lab[1]:.2f}, {lab[2]:.2f}) is {'IN' if in_gamut else 'OUT OF'} sRGB gamut")
            
            if not in_gamut:
                nearest = find_nearest_in_gamut(lab)
                nearest_rgb = lab_to_rgb(nearest)
                print(f"Nearest in-gamut color:")
                print(f"  LAB: ({nearest[0]:.2f}, {nearest[1]:.2f}, {nearest[2]:.2f})")
                print(f"  RGB: {nearest_rgb}")
            
            sys.exit(0)
        
        if args.from_space and args.to_space and args.value:
            val = tuple(args.value)
            from_space = args.from_space
            to_space = args.to_space
            
            # Convert to RGB as intermediate (everything goes through RGB)
            if from_space == "rgb":
                rgb = (int(val[0]), int(val[1]), int(val[2]))
            elif from_space == "hsl":
                rgb = hsl_to_rgb(val)
            elif from_space == "lab":
                rgb = lab_to_rgb(val)
            elif from_space == "lch":
                rgb = lch_to_rgb(val)
            
            # Convert from RGB to target
            if to_space == "rgb":
                result = rgb
            elif to_space == "hsl":
                result = rgb_to_hsl(rgb)
            elif to_space == "lab":
                result = rgb_to_lab(rgb)
            elif to_space == "lch":
                result = rgb_to_lch(rgb)
            
            print(f"Converted {from_space.upper()}{val} -> {to_space.upper()}{result}")
            sys.exit(0)
        
        # If we get here, no valid convert operation was specified
        convert_parser.print_help()
        sys.exit(0)

