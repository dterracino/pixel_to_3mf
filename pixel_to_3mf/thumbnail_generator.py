"""
Generate thumbnail images for 3MF files.

This module creates the 5 thumbnail types required by the 3MF specification:
- top_1.png: 512x512 overhead view (scaled source image)
- pick_1.png: 512x512 gray silhouette (50% gray where pixels exist)
- plate_1.png: 512x512 isometric view with shadow
- plate_1_small.png: 128x128 downscaled plate view
- plate_no_light_1.png: 512x512 isometric view without shadow

All thumbnails respect the aspect ratio of the source image, scaling the largest
dimension to fit the target size and centering with transparent padding.
"""

from PIL import Image
from typing import BinaryIO
import io


def _scale_to_fit(
    source_img: Image.Image,
    target_size: int
) -> tuple[Image.Image, int, int]:
    """
    Scale image to fit within target size while preserving aspect ratio.
    
    Scales the largest dimension to target_size and scales the other dimension
    proportionally. Returns the scaled image and the X/Y offsets needed to
    center it in a target_size x target_size canvas.
    
    Args:
        source_img: Source image to scale
        target_size: Target dimension (width and height of square canvas)
        
    Returns:
        Tuple of (scaled_image, x_offset, y_offset) where offsets center
        the scaled image in the target canvas
    """
    src_width, src_height = source_img.size
    
    # Calculate scale factor based on largest dimension
    scale_factor = target_size / max(src_width, src_height)
    
    # Scale both dimensions proportionally
    new_width = int(src_width * scale_factor)
    new_height = int(src_height * scale_factor)
    
    # Resize using LANCZOS for high quality
    scaled_img = source_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Calculate offsets to center in target canvas
    x_offset = (target_size - new_width) // 2
    y_offset = (target_size - new_height) // 2
    
    return scaled_img, x_offset, y_offset


def generate_top_view(source_img: Image.Image) -> bytes:
    """
    Generate top_1.png - 512x512 overhead view of source image.
    
    Scales the source image to fit within 512x512 while preserving aspect
    ratio, centers it, and fills remaining area with transparency.
    
    Args:
        source_img: Source image (must have RGBA mode)
        
    Returns:
        PNG image bytes
    """
    target_size = 512
    
    # Create transparent canvas
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Scale and center source image
    scaled_img, x_offset, y_offset = _scale_to_fit(source_img, target_size)
    canvas.paste(scaled_img, (x_offset, y_offset), scaled_img)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_pick_view(source_img: Image.Image) -> bytes:
    """
    Generate pick_1.png - 512x512 gray silhouette.
    
    Creates a 50% gray (RGB 128, 128, 128) silhouette where the source image
    has colored pixels. Transparent pixels remain transparent. Respects aspect
    ratio and centers in canvas.
    
    Args:
        source_img: Source image (must have RGBA mode)
        
    Returns:
        PNG image bytes
    """
    target_size = 512
    
    # Create transparent canvas
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Scale source image to fit
    scaled_img, x_offset, y_offset = _scale_to_fit(source_img, target_size)
    
    # Create gray silhouette from scaled image
    # For each pixel: if alpha > 0, set to 50% gray, otherwise transparent
    gray_silhouette = Image.new('RGBA', scaled_img.size, (0, 0, 0, 0))
    pixels = scaled_img.load()
    gray_pixels = gray_silhouette.load()
    
    if pixels is None or gray_pixels is None:
        raise RuntimeError("Failed to access pixel data")
    
    for y in range(scaled_img.size[1]):
        for x in range(scaled_img.size[0]):
            pixel = pixels[x, y]
            if not isinstance(pixel, tuple) or len(pixel) != 4:
                continue
            r, g, b, a = pixel
            if a > 0:  # Has color (not fully transparent)
                gray_pixels[x, y] = (128, 128, 128, 255)  # 50% gray, opaque
            else:
                gray_pixels[x, y] = (0, 0, 0, 0)  # Transparent
    
    # Paste silhouette onto canvas
    canvas.paste(gray_silhouette, (x_offset, y_offset), gray_silhouette)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_plate_view(source_img: Image.Image) -> bytes:
    """
    Generate plate_1.png - 512x512 isometric view.
    
    Creates an isometric view by rotating the source image -30 degrees.
    This is a simplified 2D transformation without shadow effects.
    
    Args:
        source_img: Source image (must have RGBA mode)
        
    Returns:
        PNG image bytes
    """
    target_size = 512
    
    # Create transparent canvas
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Scale source image to fit (leaving room for rotation)
    # Use 70% of target size to leave room for rotation expansion
    scaled_img, _, _ = _scale_to_fit(source_img, int(target_size * 0.7))
    
    # Rotate by -30 degrees to create isometric effect
    # Use NEAREST resampling to avoid anti-aliasing artifacts on pixel art edges
    iso_img = scaled_img.rotate(-30, expand=True, resample=Image.Resampling.NEAREST)
    
    # Center in canvas
    img_offset_x = (target_size - iso_img.size[0]) // 2
    img_offset_y = (target_size - iso_img.size[1]) // 2
    canvas.paste(iso_img, (img_offset_x, img_offset_y), iso_img)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_plate_small(plate_img_bytes: bytes) -> bytes:
    """
    Generate plate_1_small.png - 128x128 downscaled plate view.
    
    Simply downscales plate_1.png to 128x128 using high-quality LANCZOS
    resampling. This is more efficient than regenerating the isometric view.
    
    Args:
        plate_img_bytes: PNG bytes from generate_plate_view()
        
    Returns:
        PNG image bytes
    """
    # Load the plate image
    plate_img = Image.open(io.BytesIO(plate_img_bytes))
    
    # Downscale to 128x128
    small_img = plate_img.resize((128, 128), Image.Resampling.LANCZOS)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    small_img.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_plate_no_light(source_img: Image.Image) -> bytes:
    """
    Generate plate_no_light_1.png - 512x512 isometric view.
    
    Creates an isometric view by rotating the source image -30 degrees.
    Identical to plate_1.png (no separate lighting effects).
    
    Args:
        source_img: Source image (must have RGBA mode)
        
    Returns:
        PNG image bytes
    """
    target_size = 512
    
    # Create transparent canvas
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Scale source image to fit (leaving room for rotation)
    # Use 70% of target size to leave room for rotation expansion
    scaled_img, _, _ = _scale_to_fit(source_img, int(target_size * 0.7))
    
    # Rotate by -30 degrees to create isometric effect
    # Use NEAREST resampling to avoid anti-aliasing artifacts on pixel art edges
    iso_img = scaled_img.rotate(-30, expand=True, resample=Image.Resampling.NEAREST)
    
    # Center in canvas
    img_offset_x = (target_size - iso_img.size[0]) // 2
    img_offset_y = (target_size - iso_img.size[1]) // 2
    canvas.paste(iso_img, (img_offset_x, img_offset_y), iso_img)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()
