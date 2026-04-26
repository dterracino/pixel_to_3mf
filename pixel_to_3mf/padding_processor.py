"""
Padding processor module for adding outlines around pixel art.

This module implements smart padding that:
- Traces the outside edges of non-transparent pixels
- Traces internal holes (transparent areas inside the sprite)
- Expands the canvas to accommodate the padding
- Helps with diagonally-connected pixels in 3D printing

The algorithm works by finding all edge pixels (pixels adjacent to transparent
areas) and adding padding pixels around them.
"""

from typing import Tuple, Dict, Set
from PIL import Image
import numpy as np


def add_padding(
    img: Image.Image,
    padding_size: int,
    padding_color: Tuple[int, int, int],
    padding_type: str = "circular"
) -> Image.Image:
    """
    Add padding/outline around non-transparent pixels in an image.
    
    This creates a stroke around the sprite that traces both the outside edge
    and any internal holes. The canvas is expanded to fit the padding.
    
    The algorithm:
    1. Find all edge pixels (non-transparent pixels adjacent to transparent ones)
    2. For each edge pixel, mark padding pixels around it within padding_size distance
    3. Expand the canvas by padding_size on all sides
    4. Draw the padding pixels on the expanded canvas
    5. Draw the original image on top
    
    This helps with 3D printing by filling gaps between diagonally-connected pixels
    and providing structural support around thin features.
    
    Args:
        img: PIL Image in RGBA mode
        padding_size: Size of padding in pixels (e.g., 5 means 5-pixel border)
        padding_color: RGB color for the padding
        padding_type: Distance metric - "circular" (Euclidean, rounded corners),
                     "square" (Manhattan, sharp corners), or "diamond" (Chebyshev)
        
    Returns:
        New PIL Image with padding applied (expanded canvas)
        
    Raises:
        ValueError: If padding_size <= 0 or padding_color is invalid
        
    Examples:
        >>> from PIL import Image
        >>> img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))  # Transparent
        >>> img.putpixel((5, 5), (255, 0, 0, 255))  # One red pixel
        >>> padded = add_padding(img, 2, (255, 255, 255), "circular")
        >>> padded.size  # Should be expanded by 2*2 = 4 pixels in each dimension
        (14, 14)
    """
    if padding_size <= 0:
        raise ValueError(f"padding_size must be positive, got {padding_size}")
    
    if not isinstance(padding_color, tuple) or len(padding_color) != 3:
        raise ValueError(f"padding_color must be an RGB tuple, got {padding_color}")
    
    if not all(0 <= c <= 255 for c in padding_color):
        raise ValueError(f"padding_color RGB values must be 0-255, got {padding_color}")
    
    valid_padding_types = {"circular", "square", "diamond"}
    if padding_type not in valid_padding_types:
        raise ValueError(f"padding_type must be one of {valid_padding_types}, got {padding_type}")
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    width, height = img.size
    
    # Convert to numpy array for efficient processing
    img_array = np.array(img)
    
    # Find all non-transparent pixels
    non_transparent = set()
    for y in range(height):
        for x in range(width):
            if img_array[y, x, 3] > 0:  # Alpha > 0
                non_transparent.add((x, y))
    
    # If image is empty, just return the original
    if not non_transparent:
        return img
    
    # Find edge pixels - non-transparent pixels adjacent to transparent ones
    # We use 8-connectivity to check all surrounding pixels
    edge_pixels = set()
    
    for x, y in non_transparent:
        # Check all 8 neighbors
        is_edge = False
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                
                # If neighbor is out of bounds or transparent, this is an edge pixel
                if (nx < 0 or nx >= width or ny < 0 or ny >= height or
                    (nx, ny) not in non_transparent):
                    is_edge = True
                    break
            
            if is_edge:
                break
        
        if is_edge:
            edge_pixels.add((x, y))
    
    # Generate padding pixels around each edge pixel
    # We use circular distance to create a smooth outline
    padding_pixels = set()
    
    for x, y in edge_pixels:
        # Add all pixels within padding_size distance
        for dx in range(-padding_size, padding_size + 1):
            for dy in range(-padding_size, padding_size + 1):
                # Calculate distance based on padding type
                if padding_type == "circular":
                    # Euclidean distance - smooth rounded corners
                    distance = (dx * dx + dy * dy) ** 0.5
                elif padding_type == "square":
                    # Chebyshev distance - sharp 90° corners (perfect square)
                    distance = max(abs(dx), abs(dy))
                elif padding_type == "diamond":
                    # Manhattan distance - 45° diagonal cuts (diamond shape)
                    distance = abs(dx) + abs(dy)
                
                # Only add if within padding_size radius
                if distance <= padding_size:
                    px, py = x + dx, y + dy
                    
                    # Don't overwrite existing non-transparent pixels
                    if (px, py) not in non_transparent:
                        # Adjust for expanded canvas
                        padding_pixels.add((px + padding_size, py + padding_size))
    
    # Create expanded canvas
    new_width = width + 2 * padding_size
    new_height = height + 2 * padding_size
    
    # Create new image with transparent background
    padded_img = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
    
    # Draw padding pixels
    for px, py in padding_pixels:
        if 0 <= px < new_width and 0 <= py < new_height:
            padded_img.putpixel((px, py), (*padding_color, 255))
    
    # Paste original image on top (shifted by padding_size)
    padded_img.paste(img, (padding_size, padding_size), img)
    
    return padded_img


def should_apply_padding(padding_size: int) -> bool:
    """
    Check if padding should be applied based on size.
    
    This is a simple helper to determine if padding is enabled.
    Padding is disabled when size is 0 or negative.
    
    Args:
        padding_size: The padding size in pixels
        
    Returns:
        True if padding should be applied, False otherwise
    """
    return padding_size > 0
