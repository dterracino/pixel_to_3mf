"""
Image processing module for pixel art to 3MF conversion.

This module handles:
- Loading images with transparency support
- Applying padding to create outlines around sprites
- Calculating appropriate scaling for print bed sizing
- Extracting pixel data in a convenient format for further processing
"""

from PIL import Image
from typing import Tuple, Dict, Set, TYPE_CHECKING
import numpy as np
from .constants import MAX_MODEL_SIZE_MM
from .padding_processor import add_padding, should_apply_padding

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig


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
    config: 'ConversionConfig'
) -> float:
    """
    Calculate the size of each pixel in millimeters.
    
    Simple and predictable: scales the largest dimension to exactly match
    the max_size_mm from config. No rounding, no surprises!
    
    Example:
        64x32 image with max_size=200mm
        → width is bigger (64 > 32)
        → pixel size: 200mm / 64px = 3.125mm per pixel
        → final model: 200mm x 100mm ✅
    
    Example:
        224x288 image with max_size=200mm
        → height is bigger (288 > 224)
        → pixel size: 200mm / 288px = 0.694mm per pixel
        → final model: 155.6mm x 200mm ✅
    
    Args:
        image_width: Width of image in pixels
        image_height: Height of image in pixels
        config: ConversionConfig object with max_size_mm and other parameters
    
    Returns:
        Pixel size in millimeters (exact, no rounding)
    """
    # Find the larger dimension
    max_dimension_px = max(image_width, image_height)
    
    # Calculate exact pixel size to fit that dimension to max_size_mm
    pixel_size_mm = config.max_size_mm / max_dimension_px
    
    return pixel_size_mm


def auto_crop_image(img: Image.Image) -> Image.Image:
    """
    Crop away fully transparent edges from a PIL Image.
    
    This operates at the PIL Image level (before pixel extraction), finding
    the bounding box of all non-transparent pixels and cropping to that area.
    This removes wasted space and ensures the model is as compact as possible.
    
    Why this happens BEFORE padding and quantization:
    - Auto-crop removes transparent edges from the original image first
    - Then padding adds an outline around the remaining content
    - Then quantization reduces colors including the padding color
    
    If we did padding first, then auto-crop, we'd waste time adding padding
    just to remove it again.
    
    Args:
        img: PIL Image in RGBA mode
    
    Returns:
        New PIL Image cropped to non-transparent bounds, or original if no cropping needed
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    width, height = img.size
    pixel_array = np.array(img)
    
    # Find all non-transparent pixels
    non_transparent_coords = []
    for y in range(height):
        for x in range(width):
            alpha = pixel_array[y, x, 3]
            if alpha > 0:
                non_transparent_coords.append((x, y))
    
    # If image is completely transparent, return original
    if not non_transparent_coords:
        return img
    
    # Find bounding box
    min_x = min(x for x, y in non_transparent_coords)
    max_x = max(x for x, y in non_transparent_coords)
    min_y = min(y for x, y in non_transparent_coords)
    max_y = max(y for x, y in non_transparent_coords)
    
    # If already at edges, no cropping needed
    if min_x == 0 and min_y == 0 and max_x == width - 1 and max_y == height - 1:
        return img
    
    # Crop to bounding box (box is left, upper, right, lower)
    # Note: right and lower are exclusive in PIL.crop()
    cropped = img.crop((min_x, min_y, max_x + 1, max_y + 1))
    
    return cropped


def quantize_image(
    img: Image.Image,
    num_colors: int,
    algorithm: str = "none"
) -> Image.Image:
    """
    Reduce the number of colors in an image using quantization.
    
    This allows users to automatically reduce color count without preprocessing
    in external applications. Useful when an image has slightly more colors
    than max_colors.
    
    Args:
        img: PIL Image object (should be in RGBA mode)
        num_colors: Target number of colors (must be > 0)
        algorithm: Quantization algorithm
                  - "none": Simple nearest color without dithering (faster, sharper)
                  - "floyd": Floyd-Steinberg dithering (slower, smoother gradients)
    
    Returns:
        New PIL Image with reduced colors (in RGBA mode)
        
    Raises:
        ValueError: If num_colors <= 0 or algorithm is invalid
    """
    if num_colors <= 0:
        raise ValueError(f"num_colors must be positive, got {num_colors}")
    
    valid_algos = {"none", "floyd"}
    if algorithm not in valid_algos:
        raise ValueError(f"algorithm must be one of {valid_algos}, got {algorithm}")
    
    # Separate alpha channel (we'll preserve it exactly)
    # Quantization should only affect RGB channels
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Split into RGB and alpha
    rgb_img = img.convert('RGB')
    alpha = img.split()[3]  # Extract alpha channel
    
    # Perform quantization on RGB only
    # PIL's quantize method uses median cut algorithm
    if algorithm == "none":
        # No dithering - simpler, sharper color reduction
        quantized_rgb = rgb_img.quantize(colors=num_colors, dither=Image.Dither.NONE)
    else:  # "floyd"
        # Floyd-Steinberg dithering - smoother gradients
        quantized_rgb = rgb_img.quantize(colors=num_colors, dither=Image.Dither.FLOYDSTEINBERG)
    
    # Convert back to RGB mode (quantize returns palette mode)
    quantized_rgb = quantized_rgb.convert('RGB')
    
    # Recombine with original alpha channel
    quantized_rgba = Image.merge('RGBA', (*quantized_rgb.split(), alpha))
    
    return quantized_rgba


def load_image(
    image_path: str,
    config: 'ConversionConfig'
) -> PixelData:
    """
    Load an image file and extract pixel data with automatic scaling.

    This is the main entry point for image processing. It follows a specific
    pipeline order to ensure operations are performed correctly:
    
    PIPELINE ORDER (this order is critical):
    1. Auto-crop - Remove transparent edges from original image
    2. Padding - Add padding around the remaining content
    3. Pixel extraction - Convert to pixel coordinates with Y-flip
    4. Quantize - Reduce colors AFTER padding so padding color is included
    
    Why this order matters:
    - Auto-crop must happen first to remove wasted space from the original image
    - Padding must happen after cropping, so we pad the actual content not the waste
    - Quantization must happen last so the padding color gets included in the palette
    
    If we did padding before auto-crop, we'd add an outline then immediately remove it.
    If we did quantization before padding, the padding color might not be in the palette.

    Args:
        image_path: Path to the image file (PNG, JPG, etc.)
        config: ConversionConfig object with all conversion parameters

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
    
    # STEP 1: Auto-crop transparent edges (if enabled)
    # This removes wasted space from the original image BEFORE we do anything else
    if config.auto_crop:
        img = auto_crop_image(img)
    
    # STEP 2: Apply padding (if enabled)
    # This adds an outline around the content we just cropped
    # Must happen AFTER auto-crop but BEFORE pixel extraction
    if should_apply_padding(config.padding_size):
        img = add_padding(img, config.padding_size, config.padding_color, config.padding_type)

    # Get image dimensions (after auto-crop and padding)
    width, height = img.size

    # Calculate appropriate pixel size
    pixel_size_mm = calculate_pixel_size(width, height, config)
    
    # STEP 3: Extract pixel data as numpy array for fast processing
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
    
    # Check color count with backing color reservation
    unique_colors = {(r, g, b) for r, g, b, a in pixels.values()}
    num_colors = len(unique_colors)

    # Check if we need to reserve a color slot for the backing plate
    backing_in_image = config.backing_color in unique_colors

    if backing_in_image:
        # Backing color is already in the image, no reservation needed
        effective_max_colors = config.max_colors
        color_status_msg = f"(including backing color)"
    else:
        # Need to reserve one slot for the backing color
        effective_max_colors = config.max_colors - 1
        color_status_msg = f"(backing color not in image - reserving 1 slot)"

    # STEP 4: Quantize if needed (AFTER padding so padding color is included)
    if num_colors > effective_max_colors:
        # Too many colors - check if quantization is enabled
        if config.quantize:
            # Quantize the image to reduce colors
            # Use effective_max_colors (accounts for backing color) instead of config.max_colors
            target_colors = config.quantize_colors if config.quantize_colors is not None else effective_max_colors
            
            # Make sure we don't try to quantize to more colors than we have
            if target_colors >= num_colors:
                # No need to quantize if target is >= current color count
                pass
            else:
                # Perform quantization
                img = quantize_image(img, target_colors, config.quantize_algo)
                
                # Re-extract pixel data from quantized image
                pixel_array = np.array(img)
                pixels = {}
                
                for y in range(height):
                    for x in range(width):
                        r, g, b, a = pixel_array[y, x]
                        
                        if a > 0:
                            flipped_y = height - 1 - y
                            pixels[(x, flipped_y)] = (int(r), int(g), int(b), int(a))
                
                # Recalculate color count after quantization
                unique_colors = {(r, g, b) for r, g, b, a in pixels.values()}
                num_colors = len(unique_colors)
                
                # Check again if we're within limits now
                backing_in_image = config.backing_color in unique_colors
                if backing_in_image:
                    effective_max_colors = config.max_colors
                    color_status_msg = f"(including backing color)"
                else:
                    effective_max_colors = config.max_colors - 1
                    color_status_msg = f"(backing color not in image - reserving 1 slot)"
                
                # If still too many colors after quantization, raise error
                if num_colors > effective_max_colors:
                    backing_name = f"RGB{config.backing_color}"
                    
                    # Build error message with correct backing color status
                    if backing_in_image:
                        error_msg = (
                            f"Image has {num_colors} unique colors after quantization, but maximum allowed is {config.max_colors}.\n"
                            f"Backing color {backing_name} is already in the image.\n"
                            f"Try reducing --quantize-colors further or increase --max-colors."
                        )
                    else:
                        error_msg = (
                            f"Image has {num_colors} unique colors after quantization, but maximum allowed is {effective_max_colors} (backing color not in image - reserving 1 slot).\n"
                            f"Backing color {backing_name} is not in the image, so 1 slot is reserved.\n"
                            f"Try reducing --quantize-colors further or increase --max-colors."
                        )
                    
                    raise ValueError(error_msg)
        else:
            # Quantization not enabled, raise the original error
            backing_name = f"RGB{config.backing_color}"
            
            # Build error message with correct backing color status
            if backing_in_image:
                error_msg = (
                    f"Image has {num_colors} unique colors, but maximum allowed is {config.max_colors}.\n"
                    f"Backing color {backing_name} is already in the image.\n"
                    f"Try reducing colors in your image editor, enable --quantize, or increase --max-colors."
                )
            else:
                error_msg = (
                    f"Image has {num_colors} unique colors, but maximum allowed is {effective_max_colors} (backing color not in image - reserving 1 slot).\n"
                    f"Backing color {backing_name} is not in the image, so 1 slot is reserved.\n"
                    f"Try reducing colors in your image editor, enable --quantize, or increase --max-colors."
                )
            
            raise ValueError(error_msg)
    
    return PixelData(
        width=width,
        height=height,
        pixel_size_mm=pixel_size_mm,
        pixels=pixels
    )


def auto_crop_transparency(pixel_data: PixelData) -> PixelData:
    """
    Crop away fully transparent edges from PixelData.
    
    DEPRECATED: This function operates on PixelData after pixel extraction.
    The new auto_crop_image() function operates on PIL Images before extraction,
    which is part of the correct processing pipeline order in load_image().
    
    This function is kept for backward compatibility but should not be used
    in new code. Use config.auto_crop=True instead, which triggers auto_crop_image()
    at the correct point in the pipeline.
    
    Finds the bounding box of all non-transparent pixels and crops
    the image to just that area. This removes wasted space and can
    enable optimizations like simple rectangle backing plates.
    
    Args:
        pixel_data: The pixel data to crop
    
    Returns:
        New PixelData with adjusted dimensions, or original if no cropping needed
    """
    if not pixel_data.pixels:
        return pixel_data  # Empty image, nothing to crop
    
    # Find the actual bounds of non-transparent pixels
    pixel_coords = pixel_data.pixels.keys()
    min_x = min(x for x, y in pixel_coords)
    max_x = max(x for x, y in pixel_coords)
    min_y = min(y for x, y in pixel_coords)
    max_y = max(y for x, y in pixel_coords)
    
    # If already at edges, no cropping needed
    if (min_x == 0 and min_y == 0 and 
        max_x == pixel_data.width - 1 and 
        max_y == pixel_data.height - 1):
        return pixel_data
    
    # Calculate new dimensions
    new_width = max_x - min_x + 1
    new_height = max_y - min_y + 1
    
    # Remap pixel coordinates to new origin (0, 0)
    new_pixels = {}
    for (x, y), color in pixel_data.pixels.items():
        new_x = x - min_x
        new_y = y - min_y
        new_pixels[(new_x, new_y)] = color
    
    # Create new PixelData with cropped dimensions
    # Pixel size stays the same!
    return PixelData(
        width=new_width,
        height=new_height,
        pixels=new_pixels,
        pixel_size_mm=pixel_data.pixel_size_mm
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