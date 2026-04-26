"""
Generate color swatches image showing each color with its name/hex code.

This module creates a PNG image displaying rectangular color swatches alongside
their names or hex codes, providing a visual reference for what colors/filaments
are needed for printing.
"""

from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont


def generate_swatches_image(
    output_path: Path,
    colors: List[Tuple[int, int, int]],
    names: List[str]
) -> Path:
    """
    Generate a color swatches PNG image.
    
    Creates an image with rectangular color swatches and their corresponding
    names/hex codes. Each swatch is a colored rectangle with the name displayed
    next to it.
    
    Args:
        output_path: Path to the output 3MF file (swatches saved alongside it)
        colors: List of RGB tuples (one per color)
        names: List of color names/hex codes (same length as colors)
        
    Returns:
        Path to the generated swatches PNG file
        
    Raises:
        ValueError: If colors and names lists have different lengths
    """
    if len(colors) != len(names):
        raise ValueError(f"Colors and names must have same length (got {len(colors)} colors, {len(names)} names)")
    
    if len(colors) == 0:
        raise ValueError("Cannot generate swatches for empty color list")
    
    # Image dimensions
    swatch_width = 100
    swatch_height = 50
    text_width = 350
    margin = 20
    row_height = swatch_height + margin
    
    img_width = margin + swatch_width + margin + text_width + margin
    img_height = margin + (row_height * len(colors)) + margin
    
    # Create image with white background
    img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        # Try to load a nice monospace font at reasonable size
        font = ImageFont.truetype("consola.ttf", 16)  # Windows Consolas
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", 16)  # Linux
        except Exception:
            # Fall back to default PIL font
            font = ImageFont.load_default()
    
    # Draw each swatch and its name
    y_offset = margin
    for rgb, name in zip(colors, names):
        # Draw the color swatch rectangle
        x1 = margin
        y1 = y_offset
        x2 = margin + swatch_width
        y2 = y_offset + swatch_height
        
        draw.rectangle([x1, y1, x2, y2], fill=rgb, outline=(0, 0, 0), width=2)
        
        # Draw the color name/hex code
        text_x = x2 + margin
        text_y = y_offset + (swatch_height // 2) - 8  # Vertically center the text
        
        draw.text((text_x, text_y), name, fill=(0, 0, 0), font=font)
        
        y_offset += row_height
    
    # Determine output path
    swatches_path = output_path.parent / f"{output_path.stem}_swatches.png"
    
    # Save the image
    img.save(swatches_path, "PNG")
    
    return swatches_path
