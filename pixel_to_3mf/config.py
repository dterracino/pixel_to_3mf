"""
Configuration dataclass for pixel art to 3MF conversion.

This module defines the ConversionConfig dataclass that holds all the
parameters for the conversion process. This keeps function signatures
clean and makes it easy to add new parameters in the future without
breaking the API.
"""

from dataclasses import dataclass
from typing import Tuple, List, Union
from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    MAX_COLORS,
    BACKING_COLOR,
    COLOR_NAMING_MODE,
    DEFAULT_FILAMENT_MAKER,
    DEFAULT_FILAMENT_TYPE,
    DEFAULT_FILAMENT_FINISH
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
        skip_checks: If True, skip resolution warnings entirely
        batch_mode: If True, raise errors immediately instead of prompting user
        color_naming_mode: How to name objects - "color", "filament", or "hex"
        filament_maker: Filament maker filter(s) (for filament mode) - can be str or list
        filament_type: Filament type filter(s) (for filament mode) - can be str or list
        filament_finish: Filament finish filter(s) (for filament mode) - can be str or list
        auto_crop: If True, automatically crop away fully transparent edges before processing
        connectivity: Pixel connectivity mode - 0 (no merge), 4 (edge-connected only), or 8 (includes diagonals)
    """

    max_size_mm: float = MAX_MODEL_SIZE_MM
    line_width_mm: float = LINE_WIDTH_MM
    color_height_mm: float = COLOR_LAYER_HEIGHT_MM
    base_height_mm: float = BASE_LAYER_HEIGHT_MM
    max_colors: int = MAX_COLORS
    backing_color: Tuple[int, int, int] = BACKING_COLOR
    skip_checks: bool = False
    batch_mode: bool = False
    color_naming_mode: str = COLOR_NAMING_MODE
    filament_maker: Union[str, List[str]] = None  # Will be set in __post_init__
    filament_type: Union[str, List[str]] = None  # Will be set in __post_init__
    filament_finish: Union[str, List[str]] = None  # Will be set in __post_init__
    
    # Processing options
    auto_crop: bool = False
    connectivity: int = 8  # 0 (no merge), 4 (edge only), or 8 (includes diagonals)

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_size_mm <= 0:
            raise ValueError(f"max_size_mm must be positive, got {self.max_size_mm}")
        if self.color_height_mm <= 0:
            raise ValueError(f"color_height_mm must be positive, got {self.color_height_mm}")
        if self.base_height_mm < 0:
            raise ValueError(f"base_height_mm must be non-negative, got {self.base_height_mm}")
        if self.line_width_mm <= 0:
            raise ValueError(f"line_width_mm must be positive, got {self.line_width_mm}")
        if self.max_colors <= 0:
            raise ValueError(f"max_colors must be positive, got {self.max_colors}")
        if not isinstance(self.backing_color, tuple) or len(self.backing_color) != 3:
            raise ValueError(f"backing_color must be an RGB tuple, got {self.backing_color}")
        if not all(0 <= c <= 255 for c in self.backing_color):
            raise ValueError(f"backing_color RGB values must be 0-255, got {self.backing_color}")
        
        # Validate color naming mode
        valid_modes = {"color", "filament", "hex"}
        if self.color_naming_mode not in valid_modes:
            raise ValueError(f"color_naming_mode must be one of {valid_modes}, got {self.color_naming_mode}")
        
        # Validate connectivity mode
        if self.connectivity not in (0, 4, 8):
            raise ValueError(f"connectivity must be 0, 4, or 8, got {self.connectivity}")
        
        # Set default filament filters if None
        if self.filament_maker is None:
            self.filament_maker = DEFAULT_FILAMENT_MAKER
        if self.filament_type is None:
            self.filament_type = DEFAULT_FILAMENT_TYPE
        if self.filament_finish is None:
            self.filament_finish = DEFAULT_FILAMENT_FINISH