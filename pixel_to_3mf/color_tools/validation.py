"""
Color validation functions to check if a hex code matches a color name.
Uses fuzzy matching and perceptual color distance (Delta E 2000).
Useful for validating imported color data or user input.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from fuzzywuzzy import process
from .palette import Palette
from .conversions import hex_to_rgb, rgb_to_lab
from .distance import delta_e_2000

# Load the default color palette once to be used by the validation function
_palette = Palette.load_default()
_color_names = [r.name for r in _palette.records]

@dataclass(frozen=True)
class ColorValidationRecord:
    """
    A record holding the results of a color validation check.
    """
    is_match: bool
    name_match: Optional[str]
    name_confidence: float
    hex_value: str
    suggested_hex: Optional[str]
    delta_e: float
    message: str


def validate_color(
    color_name: str,
    hex_code: str,
    de_threshold: float = 20.0
) -> ColorValidationRecord:
    """
    Validates if a given hex code approximately matches a given color name.

    Args:
        color_name: The name of the color to check (e.g., "light red").
        hex_code: The hex code to validate (e.g., "#FFC0CB").
        de_threshold: The Delta E 2000 threshold for a color to be considered a match.
                      Lower is stricter. Default is 20.0.

    Returns:
        A ColorValidationRecord with the validation results.
    """
    # 1. Find the best matching color name from our CSS palette
    match_result = process.extractOne(color_name, _color_names)

    if match_result is None:
        return ColorValidationRecord(
            is_match=False,
            name_match=None,
            name_confidence=0.0,
            hex_value=hex_code,
            suggested_hex=None,
            delta_e=float('inf'),
            message="No matching color name could be found."
        )
    
    best_match, name_confidence_raw = match_result[0], match_result[1]
    name_confidence = float(name_confidence_raw) / 100.0
    
    # 2. Get the official record for the best matching color name
    matched_color_record = _palette.find_by_name(best_match)
    if not matched_color_record:
        # This should theoretically never happen if _color_names is in sync
        return ColorValidationRecord(
            is_match=False,
            name_match=best_match,
            name_confidence=name_confidence,
            hex_value=hex_code,
            suggested_hex=None,
            delta_e=float('inf'),
            message="Could not find the matched color in the palette."
        )

    suggested_hex = matched_color_record.hex
    suggested_lab = matched_color_record.lab

    # 3. Convert the user's input hex to LAB for comparison
    input_rgb = hex_to_rgb(hex_code)
    if input_rgb is None:
        return ColorValidationRecord(
            is_match=False,
            name_match=best_match,
            name_confidence=name_confidence,
            hex_value=hex_code,
            suggested_hex=suggested_hex,
            delta_e=float('inf'),
            message=f"Invalid hex code format: {hex_code}"
        )
    input_lab = rgb_to_lab(input_rgb)

    # 4. Calculate the perceptual distance (Delta E 2000)
    delta_e = delta_e_2000(input_lab, suggested_lab)

    # 5. Determine if it's a match
    is_match = delta_e <= de_threshold
    
    message = "Match" if is_match else "No Match"
    if not is_match:
        message += f" (Delta E of {delta_e:.2f} is above threshold of {de_threshold})"

    return ColorValidationRecord(
        is_match=is_match,
        name_match=best_match,
        name_confidence=name_confidence,
        hex_value=hex_code,
        suggested_hex=suggested_hex,
        delta_e=delta_e,
        message=message
    )


