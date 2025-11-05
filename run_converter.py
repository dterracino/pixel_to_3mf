#!/usr/bin/env python3
"""
Simple wrapper script to run the pixel art to 3MF converter.

This lets users run the tool from the command line without needing
to worry about Python module paths.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import pixel_to_3mf
sys.path.insert(0, str(Path(__file__).parent))

from pixel_to_3mf import main

if __name__ == "__main__":
    main()
