"""
Thread-safe runtime configuration for color processing behavior.

Unlike ColorConstants (which are immutable scientific values), these are
user preferences that can be changed and may differ per thread.
"""

import threading


class ColorConfig(threading.local):
    """
    Thread-safe runtime configuration for color processing behavior.
    
    Unlike ColorConstants (which are immutable scientific values), these are
    user preferences that can be changed and may differ per thread. Uses
    threading.local() so each thread gets its own independent config.
    """
    
    def __init__(self):
        # Dual-color filament handling
        self.dual_color_mode = "first"  # Options: "first", "last", "mix"
        
        # Gamut checking parameters
        self.gamut_tolerance = 0.01           # Floating point tolerance
        self.gamut_max_iterations = 20        # Binary search iterations


# Global config instance (thread-local)
_config = ColorConfig()


def set_dual_color_mode(mode: str) -> None:
    """
    Set the global dual-color handling mode for filaments with multiple hex colors.
    
    Args:
        mode: One of "first", "last", or "mix"
            - "first": Use the first color (default)
            - "last": Use the second color
            - "mix": Perceptually blend both colors in LAB space
    
    Raises:
        ValueError: If mode is not one of the valid options
    """
    if mode not in ("first", "last", "mix"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'first', 'last', or 'mix'")
    _config.dual_color_mode = mode


def get_dual_color_mode() -> str:
    """Get the current dual-color handling mode."""
    return _config.dual_color_mode


def set_gamut_tolerance(tolerance: float) -> None:
    """Set the tolerance for gamut boundary checking."""
    _config.gamut_tolerance = tolerance


def get_gamut_tolerance() -> float:
    """Get the current gamut tolerance."""
    return _config.gamut_tolerance


def set_gamut_max_iterations(iterations: int) -> None:
    """Set the maximum iterations for gamut mapping binary search."""
    _config.gamut_max_iterations = iterations


def get_gamut_max_iterations() -> int:
    """Get the current gamut max iterations."""
    return _config.gamut_max_iterations