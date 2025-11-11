"""
Find the dominant color in an image and match it to a filament.

This script extracts the most common color from an image (excluding transparency),
finds the nearest CSS color name, and then finds the nearest filament match using
the default configuration filters.

Usage:
    python find_dominant_filament.py <image_path>
"""

import sys
from pathlib import Path
from collections import Counter
from PIL import Image

from pixel_to_3mf.config import ConversionConfig
from color_tools import Palette, FilamentPalette, rgb_to_lab


def get_dominant_color(image_path: str) -> tuple[int, int, int]:
    """
    Extract the dominant (most common) color from an image.
    
    Ignores fully transparent pixels and returns the RGB color that
    appears most frequently.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        RGB tuple of the dominant color
    """
    # Load image and convert to RGBA
    img = Image.open(image_path).convert('RGBA')
    
    # Get all pixels (type hint issue is spurious - getdata() is iterable)
    pixels = list(img.getdata())  # type: ignore
    
    # Filter out fully transparent pixels (alpha == 0)
    opaque_pixels = [
        (r, g, b) for r, g, b, a in pixels if a > 0
    ]
    
    if not opaque_pixels:
        raise ValueError("Image contains no opaque pixels")
    
    # Count color occurrences
    color_counts = Counter(opaque_pixels)
    
    # Get most common color
    dominant_color, count = color_counts.most_common(1)[0]
    
    print(f"Found {len(color_counts)} unique colors in image")
    print(f"Dominant color: RGB{dominant_color} ({count} pixels, {count/len(opaque_pixels)*100:.1f}%)")
    
    return dominant_color


def find_nearest_css_color(rgb: tuple[int, int, int]) -> tuple[str, float]:
    """
    Find the nearest CSS color name using Delta E 2000.
    
    Args:
        rgb: RGB color tuple
        
    Returns:
        Tuple of (CSS color name, Delta E distance)
    """
    # Load default CSS color palette
    css_palette = Palette.load_default()  # type: ignore
    
    # Convert RGB to LAB for proper Delta E 2000 matching
    lab = rgb_to_lab(rgb)
    
    # Find nearest color using LAB color space
    color_record, delta_e = css_palette.nearest_color(lab, space='lab')  # type: ignore
    
    return color_record.name, delta_e  # type: ignore


def main():
    if len(sys.argv) != 2:
        print("Usage: python find_dominant_filament.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Validate file exists
    if not Path(image_path).exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)
    
    print(f"Analyzing image: {image_path}")
    print("=" * 70)
    
    # Extract dominant color
    dominant_rgb = get_dominant_color(image_path)
    
    print()
    print("CSS Color Match:")
    print("-" * 70)
    
    # Find nearest CSS color
    css_color, css_delta_e = find_nearest_css_color(dominant_rgb)
    print(f"Nearest CSS color: {css_color} (Delta E: {css_delta_e:.2f})")
    
    print()
    print("Filament Match:")
    print("-" * 70)
    
    # Create config with defaults (uses DEFAULT_FILAMENT_MAKER, etc.)
    config = ConversionConfig()
    
    print(f"Using filters:")
    print(f"  Maker(s): {config.filament_maker}")
    print(f"  Type(s): {config.filament_type}")
    print(f"  Finish(es): {config.filament_finish}")
    print()
    
    # Load filament palette and find nearest match
    filament_palette = FilamentPalette.load_default()  # type: ignore
    
    # nearest_filament expects RGB and does LAB conversion internally
    result, delta_e = filament_palette.nearest_filament(  # type: ignore
        dominant_rgb,
        maker=config.filament_maker,
        type_name=config.filament_type,
        finish=config.filament_finish
    )
    
    print(f"Nearest filament: {result.color}")  # type: ignore
    print(f"  RGB: {result.rgb}")  # type: ignore
    print(f"  Maker: {result.maker}, Type: {result.type}, Finish: {result.finish}")  # type: ignore
    print(f"  Delta E: {delta_e:.2f}")
    print()
    print("=" * 70)
    print("✅ Analysis complete!")


if __name__ == "__main__":
    main()
