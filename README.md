# Pixel Art to 3MF Converter 🎨🖨️

Convert pixel art images into 3D printable 3MF files with automatic color detection and smart region merging!

## Features ✨

- **Automatic Scaling**: Intelligently scales your pixel art to fit your print bed (default 200mm max dimension)
- **Smart Rounding**: Rounds pixel sizes to nice numbers for easier slicer setup (default 0.5mm increments)
- **Region Merging**: Uses flood-fill algorithm to merge connected same-color pixels into single manifold objects
- **Perceptual Color Names**: Uses Delta E 2000 (industry standard) to find the nearest CSS color name for each region
- **Transparent Pixel Support**: Transparent areas become holes in the model
- **Dual-Layer Design**: Colored regions on top (default 1mm) + solid backing plate with matching footprint (default 1mm)
- **Color Limiting**: Prevents accidentally converting images with too many colors (default max: 16)
- **Manifold Meshes**: Generates properly manifold geometry that slicers love (no repair needed!)
- **Correct Orientation**: Models appear right-side-up in slicers

## Requirements 📋

- Python 3.7+
- PIL/Pillow (for image loading)
- NumPy (for fast pixel processing)
- color_tools library (for perceptual color matching)

Install dependencies:

```bash
pip install Pillow numpy
```

### Setting Up color_tools

Place your `color_tools` folder in the same directory as `pixel_to_3mf`:

```text
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
  --pixel-rounding 0.1 \
  --color-height 1.5 \
  --base-height 2.0 \
  --max-colors 20
```

### All Options

- `image_file` (required): Input pixel art image (PNG, JPG, etc.)
- `-o, --output`: Output 3MF file path (default: `{input_name}_model.3mf`)
- `--max-size`: Maximum model dimension in mm (default: 200)
- `--pixel-rounding`: Round pixel size to nearest multiple (default: 0.5mm)
- `--color-height`: Height of colored layer in mm (default: 1.0)
- `--base-height`: Height of backing plate in mm (default: 1.0)
- `--max-colors`: Maximum unique colors allowed (default: 16)

## How It Works 🔧

1. **Load Image**: Reads your pixel art, converts to RGBA, and flips Y-axis for correct orientation
2. **Validate Colors**: Checks that the image doesn't exceed the color limit
3. **Calculate Scaling**: Determines pixel size to fit your print bed (respecting the max size limit)
4. **Merge Regions**: Groups connected same-color pixels using flood-fill algorithm
5. **Generate Meshes**: Creates manifold 3D geometry for each region + backing plate
6. **Name Colors**: Uses color science (Delta E 2000) to find nearest color names
7. **Export 3MF**: Packages everything into a proper 3MF file with object names

## Examples 📸

### Simple Sprite

```bash
python run_converter.py mario.png
```

- 64x32 pixel sprite
- Scales to fit within 200mm
- Results in ~5-10 colored regions
- Total height: 2mm (1mm color + 1mm base)

### Large Detailed Art (Use Finer Rounding!)

```bash
python run_converter.py ms-pac-man.png --pixel-rounding 0.1
```

- For images with 200+ pixels, use `--pixel-rounding 0.1` instead of the default 0.5mm
- This gives much better scaling (closer to your target size)
- Example: 224x288px image will be ~201mm instead of 144mm

### Thick Layers for Durability

```bash
python run_converter.py coaster.png --color-height 2.0 --base-height 3.0
```

- Makes a sturdier coaster with thicker layers
- Total thickness: 5mm

### Allow More Colors

```bash
python run_converter.py complex_art.png --max-colors 32
```

- Raises the color limit from 16 to 32
- Useful for more detailed artwork (but longer print times!)

## Project Structure 📁

```text
pixel_to_3mf/
├── __init__.py              # Package initialization
├── constants.py             # All configurable defaults
├── cli.py                   # Command-line interface (argparse, pretty printing)
├── pixel_to_3mf.py         # Core conversion logic (pure business logic)
├── image_processor.py       # Image loading, Y-flip, scaling, color validation
├── region_merger.py         # Flood-fill region detection
├── mesh_generator.py        # Manifold 3D geometry generation
└── threemf_writer.py        # 3MF file export with proper structure
```

### Architecture Notes

The code follows clean separation between the **CLI layer** and the **business logic**:

- **cli.py** - Handles all command-line stuff (argparse, error messages, progress output)
- **pixel_to_3mf.py** - Pure conversion function that can be imported and used programmatically

This means you can use the converter in two ways:

**As a CLI tool:**

```bash
python run_converter.py image.png
```

**As a Python library:**

```python
from pixel_to_3mf import convert_image_to_3mf

stats = convert_image_to_3mf(
    input_path="sprite.png",
    output_path="sprite.3mf",
    max_size_mm=150,
    color_height_mm=2.0,
    max_colors=16
)
print(f"Created model with {stats['num_regions']} regions!")
```

This separation makes testing easier and keeps concerns properly separated! 🎯

## Editing Defaults 🔧

Want to change the default settings? Just edit `pixel_to_3mf/constants.py`:

```python
# Your print bed size
MAX_MODEL_SIZE_MM = 200.0

# Pixel size rounding (use 0.1 for detailed images)
PIXEL_ROUNDING_MM = 0.5

# Layer heights
COLOR_LAYER_HEIGHT_MM = 1.0
BASE_LAYER_HEIGHT_MM = 1.0

# Color limit (most slicers support 16 filaments max)
MAX_COLORS = 16
```

## Tips & Tricks 💡

### For Best Results

- **Use PNG files** with transparency for holes in your design
- **Keep pixel art small** (under 200x200px) for reasonable print times
- **Use distinct colors** - the algorithm merges adjacent pixels with the exact same RGB value
- **For detailed images** (200+ pixels): Use `--pixel-rounding 0.1` instead of the default 0.5mm

### Understanding Pixel Rounding

The `--pixel-rounding` parameter affects how close your final model size is to the `--max-size` target:

- **Coarse rounding (0.5mm)**: Good for small pixel art (32x32, 64x64), gives nice round numbers
- **Fine rounding (0.1mm)**: Better for detailed images (200x200+), gets closer to target size
- **Trade-off**: Finer rounding means less round numbers, but better size accuracy

Example with a 288-pixel tall image and 200mm max:

```bash
# With default 0.5mm rounding: 288 × 0.5 = 144mm (undersized!)
python run_converter.py image.png

# With 0.1mm rounding: 288 × 0.7 = 201.6mm (much better!)
python run_converter.py image.png --pixel-rounding 0.1
```

### Slicer Setup

1. Open the 3MF file in Bambu Studio, PrusaSlicer, Orca Slicer, etc.
2. You'll see each colored region as a separate object with its color name
3. Assign filament colors to match (or get creative!)
4. The "Backing" object is your solid base layer
5. The meshes are manifold - no repair needed! ✅

### Common Issues

**Model too small after conversion:**

- This happens with detailed images (200+ pixels) using default 0.5mm rounding
- Solution: Use `--pixel-rounding 0.1` for finer control
- See "Understanding Pixel Rounding" section above

**"Too many colors" error:**

- Your image has more unique colors than the limit allows
- Solution 1: Reduce colors in your image editor (posterize/index)
- Solution 2: Increase the limit with `--max-colors 32` (but longer prints!)

**Colors not merging:**

- Regions only merge if they're the exact same RGB value
- Anti-aliasing and compression can create subtle color variations
- Solution: Use indexed color mode in your image editor

**Model appears flipped:**

- This shouldn't happen anymore! We fixed the Y-axis flip.
- If you still see this, please report it as a bug

## Technical Details 🤓

### Manifold Mesh Generation

The meshes are generated with proper topology:

- **No duplicate vertices**: Adjacent pixels share vertices at their corners
- **Consistent winding**: All triangles use counter-clockwise winding for outward-facing normals
- **Proper edge connectivity**: Every edge is shared by exactly 2 triangles
- **Result**: Manifold meshes that slicers can use directly without repair!

### Region Merging Algorithm

Uses breadth-first flood fill to find connected components. Only pixels sharing an edge (not diagonal corners) are merged. Time complexity: O(n) where n = number of pixels.

### Color Naming

Converts RGB → LAB color space, then uses Delta E 2000 formula to find the nearest CSS color name from a database of 147 standard colors. Delta E 2000 is the industry standard for perceptual color difference.

### Y-Axis Coordinate System

Images store pixels with Y=0 at the top (origin: top-left). We flip the Y coordinate during loading so Y=0 is at the bottom (origin: bottom-left), matching standard 3D coordinate systems. This ensures your pixel art appears right-side-up in slicers!

### 3MF Structure

The generated file contains:

- `3D/Objects/object_1.model` - All mesh geometry (vertices and triangles)
- `3D/3dmodel.model` - Main assembly with proper transforms
- `Metadata/model_settings.config` - Object names for slicer UI
- Required metadata files for 3MF spec compliance

The backing plate has the exact same footprint as the colored regions (with holes for transparent pixels), creating a proper unified model.

## Changelog 📝

**Recent Improvements:**

- ✅ Fixed manifold geometry (no more repair needed!)
- ✅ Fixed triangle winding for correct normals
- ✅ Fixed Y-axis orientation (models appear right-side-up)
- ✅ Fixed backing plate to match pixel footprint with holes
- ✅ Fixed vertex sharing in merged regions
- ✅ Added color limiting with `--max-colors` parameter
- ✅ Improved scaling algorithm to respect max size limit
- ✅ Updated all type hints for Pylance compatibility

## License 📄

Created for personal and educational use. The color_tools library is a separate component with its own licensing.

## Credits 🙌

Built with love for the 3D printing and pixel art communities! Special thanks to the Delta E color science research that makes perceptual color matching possible.

---

**Happy Printing!** 🎉
