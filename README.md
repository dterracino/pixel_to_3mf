# Pixel Art to 3MF Converter 🎨🖨️

Convert pixel art images into 3D printable 3MF files with automatic color detection and smart region merging!

## Features ✨

- **Automatic Scaling**: Intelligently scales your pixel art to fit your print bed (default 200mm max dimension)
- **Smart Rounding**: Rounds pixel sizes to nice numbers (e.g., 3.125mm → 3.0mm) for easier slicer setup
- **Region Merging**: Uses flood-fill algorithm to merge connected same-color pixels into single objects
- **Perceptual Color Names**: Uses Delta E 2000 (industry standard) to find the nearest CSS color name for each region
- **Transparent Pixel Support**: Transparent areas become holes in the model
- **Dual-Layer Design**: Colored regions on top (default 1mm) + solid backing plate (default 1mm)

## Requirements 📋

- Python 3.7+
- PIL/Pillow (for image loading)
- NumPy (for fast pixel processing)
- Your color_tools library (place the color_tools folder in the same directory)

Install dependencies:
```bash
pip install Pillow numpy
```

### Setting Up color_tools

Place your `color_tools` folder in the same directory as `pixel_to_3mf`:
```
your_project/
├── pixel_to_3mf/
│   ├── __init__.py
│   ├── constants.py
│   └── ...
├── color_tools/
│   ├── __init__.py
│   ├── palette.py
│   └── ...
└── run_converter.py
```

The converter imports color_tools directly for perceptual color matching.

## Usage 🚀

### Basic Usage

```bash
python run_converter.py your_pixel_art.png
```

This will create `your_pixel_art_model.3mf` in the same directory.

### Advanced Options

```bash
python run_converter.py image.png \
  --output custom_name.3mf \
  --max-size 150 \
  --pixel-rounding 1.0 \
  --color-height 1.5 \
  --base-height 2.0
```

### All Options

- `image_file` (required): Input pixel art image (PNG, JPG, etc.)
- `-o, --output`: Output 3MF file path (default: `{input_name}_model.3mf`)
- `--max-size`: Maximum model dimension in mm (default: 200)
- `--pixel-rounding`: Round pixel size to nearest multiple (default: 0.5mm)
- `--color-height`: Height of colored layer in mm (default: 1.0)
- `--base-height`: Height of backing plate in mm (default: 1.0)

## How It Works 🔧

1. **Load Image**: Reads your pixel art and converts to RGBA format
2. **Calculate Scaling**: Determines pixel size to fit your print bed
3. **Merge Regions**: Groups connected same-color pixels using flood-fill
4. **Generate Meshes**: Creates 3D geometry for each region + backing plate
5. **Name Colors**: Uses color science (Delta E 2000) to find nearest color names
6. **Export 3MF**: Packages everything into a proper 3MF file

## Examples 📸

### Simple Sprite
```bash
python run_converter.py mario.png
```
- 64x32 pixel sprite
- Scales to 192mm x 96mm (3mm per pixel)
- Results in ~5-10 colored regions

### Large Detailed Art
```bash
python run_converter.py detailed_art.png --max-size 180 --pixel-rounding 1.0
```
- Uses slightly smaller max size for safety margin
- Rounds to whole millimeters for cleaner numbers

### Thick Layers for Durability
```bash
python run_converter.py coaster.png --color-height 2.0 --base-height 3.0
```
- Makes a sturdier coaster with thicker layers
- Total thickness: 5mm

## Project Structure 📁

```
pixel_to_3mf/
├── __init__.py              # Package initialization
├── constants.py             # All configurable defaults
├── pixel_to_3mf.py         # Main CLI entry point
├── image_processor.py       # Image loading and scaling
├── region_merger.py         # Flood-fill region detection
├── mesh_generator.py        # 3D geometry generation
├── threemf_writer.py        # 3MF file export
└── color_tools/             # Color science library
    ├── palette.py           # Color matching
    ├── conversions.py       # RGB/LAB conversions
    └── distance.py          # Delta E metrics
```

## Editing Defaults 🔧

Want to change the default settings? Just edit `pixel_to_3mf/constants.py`:

```python
# Your print bed size
MAX_MODEL_SIZE_MM = 200.0

# Pixel size rounding
PIXEL_ROUNDING_MM = 0.5

# Layer heights
COLOR_LAYER_HEIGHT_MM = 1.0
BASE_LAYER_HEIGHT_MM = 1.0
```

## Tips & Tricks 💡

### For Best Results
- Use PNG files with transparency for holes in your design
- Keep pixel art relatively small (under 200x200px) for reasonable print times
- Use distinct colors - the algorithm will merge similar shades

### Slicer Setup
1. Open the 3MF file in Bambu Studio, PrusaSlicer, etc.
2. You'll see each colored region as a separate object with its color name
3. Assign filament colors to match (or get creative!)
4. The "backing_plate" object is your solid base layer

### Common Issues
- **Model too small**: Decrease `--max-size` or use a larger print bed
- **Colors not merging**: Regions are only merged if they're the same exact RGB value
- **Weird object names**: The color detection uses perceptual matching, so "red" might show up as "crimson" or "firebrick"

## Technical Details 🤓

### Region Merging Algorithm
Uses breadth-first flood fill to find connected components. Only pixels sharing an edge (not diagonal corners) are merged. Time complexity: O(n) where n = number of pixels.

### Color Naming
Converts RGB → LAB color space, then uses Delta E 2000 formula to find the nearest CSS color name from a database of 147 standard colors. Delta E 2000 is the industry standard for perceptual color difference.

### 3MF Structure
The generated file contains:
- `3D/Objects/object_1.model` - All mesh geometry
- `3D/3dmodel.model` - Main assembly
- `Metadata/model_settings.config` - Object names
- Required metadata files for 3MF spec compliance

## License 📄

Created for personal and educational use. The color_tools library included is a separate component with its own licensing.

## Credits 🙌

Built with love for the 3D printing and pixel art communities! Special thanks to the Delta E color science research that makes perceptual color matching possible.

---

**Happy Printing!** 🎉
