"""
Configuration dataclass for pixel art to 3MF conversion.

This module defines the ConversionConfig dataclass that holds all the
parameters for the conversion process. This keeps function signatures
clean and makes it easy to add new parameters in the future without
breaking the API.
"""

from dataclasses import dataclass
from typing import Tuple
from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    MAX_COLORS,
    BACKING_COLOR
)


@dataclass
class ConversionConfig:
    """
    Configuration for pixel art to 3MF conversion.

    This dataclass holds all the parameters needed for the conversion process.
    By using a config object instead of individual parameters, we make the API
    more maintainable and easier to extend in the future.

    Attributes:
        max_size_mm: Maximum dimension (width or height) in millimeters
        line_width_mm: Nozzle line width for printability check
        color_height_mm: Height of colored regions in millimeters
        base_height_mm: Height of backing plate in millimeters
        max_colors: Maximum unique colors allowed
        backing_color: RGB color for the backing plate (reserved if not in image)
    """

    max_size_mm: float = MAX_MODEL_SIZE_MM
    line_width_mm: float = LINE_WIDTH_MM
    color_height_mm: float = COLOR_LAYER_HEIGHT_MM
    base_height_mm: float = BASE_LAYER_HEIGHT_MM
    max_colors: int = MAX_COLORS
    backing_color: Tuple[int, int, int] = BACKING_COLOR

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_size_mm <= 0:
            raise ValueError(f"max_size_mm must be positive, got {self.max_size_mm}")
        if self.color_height_mm <= 0:
            raise ValueError(f"color_height_mm must be positive, got {self.color_height_mm}")
        if self.base_height_mm <= 0:
            raise ValueError(f"base_height_mm must be positive, got {self.base_height_mm}")
        if self.line_width_mm <= 0:
            raise ValueError(f"line_width_mm must be positive, got {self.line_width_mm}")
        if self.max_colors <= 0:
            raise ValueError(f"max_colors must be positive, got {self.max_colors}")
        if not isinstance(self.backing_color, tuple) or len(self.backing_color) != 3:
            raise ValueError(f"backing_color must be an RGB tuple, got {self.backing_color}")
        if not all(0 <= c <= 255 for c in self.backing_color):
            raise ValueError(f"backing_color RGB values must be 0-255, got {self.backing_color}")
