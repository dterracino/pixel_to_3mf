"""
JSON formatting utilities.

Provides helpers for formatting JSON output with specific styling requirements,
such as compact arrays while maintaining overall indentation.
"""

import json
import re
from typing import Any


def dumps_compact_arrays(
    data: Any,
    indent: int = 2,
    array_fields: list[str] | None = None
) -> str:
    """
    Format JSON with compact arrays on single lines.
    
    Standard json.dumps() with indent will format arrays across multiple lines:
        "rgb": [
          255,
          0,
          0
        ]
    
    This function compacts specified arrays to single lines:
        "rgb": [255, 0, 0]
    
    WHY: Compact arrays are more readable for coordinate data (RGB values,
    vertices, etc.) while keeping overall structure indented and clear.
    
    Args:
        data: Data structure to serialize
        indent: Number of spaces for indentation (default: 2)
        array_fields: List of field names whose arrays should be compacted.
                     If None, compacts all arrays of numbers.
    
    Returns:
        JSON string with compact arrays and indented structure
    
    Example:
        >>> data = {"colors": [{"name": "Red", "rgb": [255, 0, 0]}]}
        >>> print(dumps_compact_arrays(data, array_fields=["rgb"]))
        {
          "colors": [
            {
              "name": "Red",
              "rgb": [255, 0, 0]
            }
          ]
        }
    """
    # First, dump with standard indentation
    json_str = json.dumps(data, indent=indent, ensure_ascii=False)
    
    if array_fields is None:
        # Compact all arrays that contain only numbers
        # Pattern: matches arrays like [1, 2, 3] or [1.0, 2.5, 3.14] spread across lines
        json_str = re.sub(
            r'\[\s*\n\s*([\d\.\-\+eE,\s]+)\n\s*\]',
            lambda m: '[' + re.sub(r'\s+', ' ', m.group(1).strip()) + ']',
            json_str
        )
    else:
        # Compact only specified field arrays
        for field in array_fields:
            # Pattern: "field_name": [\n    123,\n    456\n  ] -> "field_name": [123, 456]
            pattern = rf'"{field}":\s*\[\s*\n\s*([\d\.\-\+eE,\s]+)\n\s*\]'
            json_str = re.sub(
                pattern,
                lambda m: f'"{field}": [' + re.sub(r'\s+', ' ', m.group(1).strip()) + ']',
                json_str
            )
    
    return json_str
