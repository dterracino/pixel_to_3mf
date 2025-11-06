"""
Image processing module for pixel art to 3MF conversion.

This module handles:
- Loading images with transparency support
- Calculating appropriate scaling for print bed sizing
- Extracting pixel data in a convenient format for further processing
"""

from PIL import Image
from typing import Tuple, Dict, Set, Optional
import numpy as np
from .constants import MAX_MODEL_SIZE_MM, PIXEL_ROUNDING_MM


class PixelData:
    """
    Container for processed pixel art data.
    
    This is basically our "parsed image" - it holds all the info we need
    to generate the 3D model without having to pass around a million separate
    variables. Think of it as the blueprint! 📐
    """
    
    def __init__(
        self,
        width: int,
        height: int,
        pixel_size_mm: float,
        pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]]
    ):
        """
        Initialize pixel data.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            pixel_size_mm: Size of each pixel in millimeters (already rounded)
            pixels: Dict mapping (x, y) coords to RGBA tuples
                   Only non-transparent pixels are included!
        """
        self.width = width
        self.height = height
        self.pixel_size_mm = pixel_size_mm
        self.pixels = pixels
        
        # Calculate actual model dimensions
        self.model_width_mm = width * pixel_size_mm
        self.model_height_mm = height * pixel_size_mm
    
    def get_unique_colors(self) -> Set[Tuple[int, int, int]]:
        """
        Get set of unique RGB colors (excluding alpha).
        
        Returns:
            Set of (R, G, B) tuples
        """
        return {(r, g, b) for r, g, b, a in self.pixels.values()}
    
    def __repr__(self) -> str:
        return (
            f"PixelData({self.width}x{self.height}px, "
            f"{self.model_width_mm:.1f}x{self.model_height_mm:.1f}mm, "
            f"{len(self.pixels)} non-transparent pixels, "
            f"{len(self.get_unique_colors())} unique colors)"
        )


def calculate_pixel_size(
    image_width: int,
    image_height: int,
    max_size_mm: float = MAX_MODEL_SIZE_MM,
    rounding_mm: float = PIXEL_ROUNDING_MM
) -> float:
    """
    Calculate the size of each pixel in millimeters.
    
    This is where the magic scaling happens! We figure out which dimension
    is bigger, scale it to fit the max size, then round to a nice number.
    
    Example:
        64x32 image with max_size=200mm
        → width is bigger (64 > 32)
        → ideal size: 200mm / 64px = 3.125mm per pixel
        → rounded to nearest 0.5mm = 3.0mm per pixel
        → final model: 192mm x 96mm (nice and tidy!)
    
    Args:
        image_width: Width of image in pixels
        image_height: Height of image in pixels
        max_size_mm: Maximum dimension (width or height) in millimeters
        rounding_mm: Round to nearest multiple of this value
    
    Returns:
        Pixel size in millimeters (rounded)
    """
    # Find the larger dimension
    max_dimension_px = max(image_width, image_height)
    
    # Calculate ideal pixel size to fit that dimension to max_size_mm
    ideal_pixel_size = max_size_mm / max_dimension_px
    
    # Round to nearest multiple of rounding_mm
    # The formula: round(value / increment) * increment
    rounded_pixel_size = round(ideal_pixel_size / rounding_mm) * rounding_mm
    
    # Safety check: ensure we don't round down to zero!
    if rounded_pixel_size <= 0:
        rounded_pixel_size = rounding_mm
    
    return rounded_pixel_size


def load_image(
    image_path: str,
    max_size_mm: float = MAX_MODEL_SIZE_MM,
    rounding_mm: float = PIXEL_ROUNDING_MM,
    max_colors: Optional[int] = None
) -> PixelData:
    """
    Load an image file and extract pixel data with automatic scaling.
    
    This is the main entry point for image processing. It loads the image,
    figures out the right scaling, and packages everything up nicely.
    
    Args:
        image_path: Path to the image file (PNG, JPG, etc.)
        max_size_mm: Maximum dimension for scaling (default from constants)
        rounding_mm: Pixel size rounding increment (default from constants)
        max_colors: Maximum allowed unique colors (None = no limit)
    
    Returns:
        PixelData object containing all the goodies
    
    Raises:
        FileNotFoundError: If image doesn't exist
        IOError: If image can't be loaded
        ValueError: If image has too many colors
    """
    # Load image with PIL
    img = Image.open(image_path)
    
    # Convert to RGBA to ensure we have alpha channel
    # (some formats like JPG don't have transparency, so we add it)
    img = img.convert('RGBA')
    
    # Get image dimensions
    width, height = img.size
    
    # Calculate appropriate pixel size
    pixel_size_mm = calculate_pixel_size(width, height, max_size_mm, rounding_mm)
    
    # Extract pixel data as numpy array for fast processing
    # Shape will be (height, width, 4) where 4 = RGBA
    pixel_array = np.array(img)
    
    # Build dictionary of non-transparent pixels
    # We only care about pixels with non-zero alpha!
    pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixel_array[y, x]
            
            # Skip transparent pixels (alpha == 0)
            # These will become holes in the model
            if a > 0:
                # CRITICAL FIX: Flip Y coordinate!
                # Image coordinates: Y=0 is TOP, increases DOWNWARD
                # 3D coordinates: Y=0 is BOTTOM, increases UPWARD
                # So we need to flip: image_y=0 → 3d_y=(height-1)
                flipped_y = height - 1 - y
                pixels[(x, flipped_y)] = (int(r), int(g), int(b), int(a))
    
    # Check color count if max_colors is specified
    if max_colors is not None:
        unique_colors = {(r, g, b) for r, g, b, a in pixels.values()}
        num_colors = len(unique_colors)
        
        if num_colors > max_colors:
            raise ValueError(
                f"Image has {num_colors} unique colors, but maximum is {max_colors}.\n"
                f"Try reducing colors in your image editor or increase --max-colors."
            )
    
    return PixelData(
        width=width,
        height=height,
        pixel_size_mm=pixel_size_mm,
        pixels=pixels
    )


def get_pixel_bounds_mm(
    pixel_data: PixelData,
    x: int,
    y: int
) -> Tuple[float, float, float, float]:
    """
    Get the bounding box of a pixel in millimeters.
    
    This converts pixel coordinates (0, 0), (1, 0), etc. into actual
    millimeter positions in 3D space. We use this when generating meshes.
    
    Args:
        pixel_data: The pixel data containing scale info
        x: Pixel X coordinate
        y: Pixel Y coordinate
    
    Returns:
        Tuple of (min_x, max_x, min_y, max_y) in millimeters
    """
    ps = pixel_data.pixel_size_mm
    
    # Each pixel occupies a square of size pixel_size_mm
    min_x = x * ps
    max_x = (x + 1) * ps
    min_y = y * ps
    max_y = (y + 1) * ps
    
    return min_x, max_x, min_y, max_y