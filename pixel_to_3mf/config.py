"""
Configuration dataclass for pixel art to 3MF conversion.

This module defines the ConversionConfig dataclass that holds all the
parameters for the conversion process. This keeps function signatures
clean and makes it easy to add new parameters in the future without
breaking the API.
"""

import re
from dataclasses import dataclass, field
from typing import Tuple, List, Union
from pathlib import Path
from .constants import (
    MAX_MODEL_SIZE_MM,
    LINE_WIDTH_MM,
    COLOR_LAYER_HEIGHT_MM,
    BASE_LAYER_HEIGHT_MM,
    MAX_COLORS,
    BACKING_COLOR,
    COLOR_NAMING_MODE,
    MERGE_SIMILAR_COLORS,
    DEFAULT_FILAMENT_MAKER,
    DEFAULT_FILAMENT_TYPE,
    DEFAULT_FILAMENT_FINISH,
    PREFER_HUE_MATCHING,
    USE_RGB_BOUNDARY_DETECTION,
    ENABLE_QUANTIZATION,
    QUANTIZATION_ALGORITHM,
    QUANTIZATION_COLORS,
    PADDING_SIZE_PX,
    PADDING_COLOR,
    PADDING_TYPE_DEFAULT,
    TRIM_DISCONNECTED_PIXELS,
    AMS_COUNT,
    AMS_SLOTS_PER_UNIT,
    GENERATE_SWATCHES
)


def format_title_from_filename(filename: str) -> str:
    """
    Format a filename into a nice title for 3MF metadata.
    
    Converts filenames like:
    - "gameboy-tetris-titlescreen.png" -> "Gameboy Tetris Titlescreen"
    - "nes-samus.png" -> "Nes Samus"
    - "super-mario-nes-screenshot.png" -> "Super Mario Nes Screenshot"
    - "Donkey_kong-jr screenshot.png" -> "Donkey Kong Jr Screenshot"
    - "c64ready.png" -> "C64ready"
    - "ryu-sf2.png" -> "Ryu Sf2"
    - "image.backup.png" -> "Image Backup"
    - "Kirby's Adventure.png" -> "Kirbys Adventure"
    
    Algorithm:
    1. Remove file extension (only the final .ext, so "image.backup.png" -> "image.backup")
    2. Remove apostrophes (they're part of the word, not separators)
    3. Replace ALL other non-alphanumeric characters (including dots) with single space
    4. Collapse multiple spaces into one
    5. Trim leading/trailing whitespace
    6. Title case each word, preserving existing uppercase sequences
    
    Args:
        filename: Original filename (with or without extension)
    
    Returns:
        Formatted title string (trimmed, single spaces between words)
    """
    # Get the base filename without directory, then remove the final extension
    # WHY: Path.stem removes only the last extension, so "image.backup.png" -> "image.backup"
    # This is what we want! Then the dot becomes a space below.
    name = Path(filename).stem
    
    # Remove apostrophes entirely (they're part of the word, not separators)
    # WHY: "Kirby's" should become "Kirbys", not "Kirby S"
    name = name.replace("'", "")
    
    # Replace ALL non-alphanumeric characters (including underscores, hyphens, dots, etc.)
    # with a single space. [^a-zA-Z0-9] matches anything that's NOT a letter or number
    # WHY: We want ALL separators (-, _, ., etc.) to become spaces
    name = re.sub(r'[^a-zA-Z0-9]+', ' ', name)
    
    # Collapse multiple spaces into one (in case there were consecutive punctuation marks)
    # This is redundant with the + in the regex above, but kept for clarity
    name = re.sub(r'\s+', ' ', name)
    
    # Trim leading/trailing whitespace
    name = name.strip()
    
    # Title case each word, but preserve existing uppercase sequences
    # WHY: We want "nes" -> "Nes" but "NES" -> "NES", "c64" -> "C64" (already caps)
    words = []
    for word in name.split():
        # If word is all uppercase or has mixed case, keep it
        # Otherwise, title case it
        if word.isupper() or any(c.isupper() for c in word[1:]):
            words.append(word)
        else:
            words.append(word.capitalize())
    
    return ' '.join(words)


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
        color_naming_mode: How to name objects - "color", "filament", "hex", or "generated"
        merge_similar_colors: If True, merge similar RGBs to same filament. If False, force unique filament per RGB
        filament_maker: Filament maker filter(s) (for filament mode) - can be str or list
        filament_type: Filament type filter(s) (for filament mode) - can be str or list
        filament_finish: Filament finish filter(s) (for filament mode) - can be str or list
        auto_crop: If True, automatically crop away fully transparent edges before processing
        connectivity: Pixel connectivity mode - 0 (no merge), 4 (edge-connected only), or 8 (includes diagonals)
        padding_size: Size of padding in pixels (0 = disabled, >0 = enabled)
        padding_color: RGB color for the padding outline
        padding_type: Padding shape - "circular" (rounded), "square" (90° corners), or "diamond" (45° cuts)
        trim_disconnected: If True, remove pixels that only connect via corners (diagonals)
        quantize: If True, automatically reduce colors when image exceeds max_colors
        quantize_algo: Quantization algorithm - "none" for simple nearest color, "floyd" for Floyd-Steinberg dithering
        quantize_colors: Number of colors to quantize to (defaults to max_colors if None)
        generate_summary: If True, generate a summary file listing colors/filaments used
        optimize_mesh: If True, use optimized polygon-based mesh generation (enables validate_mesh automatically)
        validate_mesh: If True, run mesh post-processing validation and repair on all meshes
        ams_count: Number of AMS units available (1-4, default 4). Total slots = ams_count × ams_slots_per_unit
        ams_slots_per_unit: Number of filament slots per AMS unit (default 4 for Bambu Lab AMS)
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
    merge_similar_colors: bool = MERGE_SIMILAR_COLORS
    filament_maker: Union[str, List[str], None] = None  # Will be set in __post_init__
    filament_type: Union[str, List[str], None] = None  # Will be set in __post_init__
    filament_finish: Union[str, List[str], None] = None  # Will be set in __post_init__
    hue_aware_matching: bool = PREFER_HUE_MATCHING  # Penalize hue shifts when matching colors
    use_rgb_boundary_detection: bool = USE_RGB_BOUNDARY_DETECTION  # Use RGB analysis for blue/purple boundary
    
    # Processing options
    auto_crop: bool = False
    connectivity: int = 8  # 0 (no merge), 4 (edge only), or 8 (includes diagonals)
    trim_disconnected: bool = TRIM_DISCONNECTED_PIXELS
    
    # Padding options
    padding_size: int = PADDING_SIZE_PX
    padding_color: Tuple[int, int, int] = PADDING_COLOR
    padding_type: str = PADDING_TYPE_DEFAULT
    
    # Color quantization options
    quantize: bool = ENABLE_QUANTIZATION
    quantize_algo: str = QUANTIZATION_ALGORITHM
    quantize_colors: Union[int, None] = QUANTIZATION_COLORS
    
    # Summary file options
    generate_summary: bool = False
    
    # Preview image options
    generate_preview: bool = False
    
    # Color swatches image options
    generate_swatches: bool = GENERATE_SWATCHES
    
    # Mesh optimization and validation
    optimize_mesh: bool = False
    validate_mesh: bool = False
    
    # AMS configuration
    ams_count: int = AMS_COUNT
    ams_slots_per_unit: int = AMS_SLOTS_PER_UNIT
    
    # Rendering options
    render_model: bool = False
    
    # Source image tracking (set programmatically, not by user)
    source_image_path: str | None = field(default=None, repr=False)
    source_image_name: str | None = field(default=None, repr=False)
    model_title: str | None = field(default=None, repr=False)

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
        valid_modes = {"color", "filament", "hex", "generated"}
        if self.color_naming_mode not in valid_modes:
            raise ValueError(f"color_naming_mode must be one of {valid_modes}, got {self.color_naming_mode}")
        
        # Validate connectivity mode
        if self.connectivity not in (0, 4, 8):
            raise ValueError(f"connectivity must be 0, 4, or 8, got {self.connectivity}")
        
        # Validate quantization algorithm
        valid_algos = {"none", "floyd"}
        if self.quantize_algo not in valid_algos:
            raise ValueError(f"quantize_algo must be one of {valid_algos}, got {self.quantize_algo}")
        
        # Validate quantize_colors if set
        if self.quantize_colors is not None and self.quantize_colors <= 0:
            raise ValueError(f"quantize_colors must be positive, got {self.quantize_colors}")
        
        # Validate padding parameters
        if self.padding_size < 0:
            raise ValueError(f"padding_size must be non-negative, got {self.padding_size}")
        
        if not isinstance(self.padding_color, tuple) or len(self.padding_color) != 3:
            raise ValueError(f"padding_color must be an RGB tuple, got {self.padding_color}")
        
        if not all(0 <= c <= 255 for c in self.padding_color):
            raise ValueError(f"padding_color RGB values must be 0-255, got {self.padding_color}")
        
        # Validate padding type
        valid_padding_types = {"circular", "square", "diamond"}
        if self.padding_type not in valid_padding_types:
            raise ValueError(f"padding_type must be one of {valid_padding_types}, got {self.padding_type}")
        
        # Validate AMS count (number of AMS units, not slots)
        if self.ams_count <= 0:
            raise ValueError(f"ams_count must be positive, got {self.ams_count}")
        if self.ams_count > 4:
            raise ValueError(f"ams_count cannot exceed 4 AMS units, got {self.ams_count}")
        
        # Auto-enable validate_mesh when optimize_mesh is used
        # WHY: Optimized mesh generation can produce non-manifold edges in edge cases,
        # so we automatically run post-processing validation/repair for safety
        if self.optimize_mesh and not self.validate_mesh:
            self.validate_mesh = True
        
        # Set default filament filters if None
        if self.filament_maker is None:
            self.filament_maker = DEFAULT_FILAMENT_MAKER
        if self.filament_type is None:
            self.filament_type = DEFAULT_FILAMENT_TYPE
        if self.filament_finish is None:
            self.filament_finish = DEFAULT_FILAMENT_FINISH        
        # Set model_title from source_image_name if available
        # WHY: If source_image_name is set, use it to auto-generate a nice title.
        # If model_title is already set explicitly, keep that (user override).
        # Otherwise, use default "PixelArt3D".
        if self.model_title is None and self.source_image_name:
            self.model_title = format_title_from_filename(self.source_image_name)
        elif self.model_title is None:
            self.model_title = "PixelArt3D"
