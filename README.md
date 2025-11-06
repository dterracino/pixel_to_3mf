# Pixel Art to 3MF Converter 🎨🖨️

Convert pixel art images into 3D printable 3MF files with automatic color detection and smart region merging!

## Features ✨

- **Exact Scaling**: Scales your pixel art so the largest dimension exactly matches your target size (default 200mm)
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
  --color-height 1.5 \
  --base-height 2.0 \
  --max-colors 20
```

### All Options

- `image_file` (required): Input pixel art image (PNG, JPG, etc.)
- `-o, --output`: Output 3MF file path (default: `{input_name}_model.3mf`)
- `--max-size`: Maximum model dimension in mm (default: 200) - the largest dimension will scale to exactly this size
- `--color-height`: Height of colored layer in mm (default: 1.0)
- `--base-height`: Height of backing plate in mm (default: 1.0)
- `--max-colors`: Maximum unique colors allowed (default: 16)

## How It Works 🔧

1. **Load Image**: Reads your pixel art, converts to RGBA, and flips Y-axis for correct orientation
2. **Validate Colors**: Checks that the image doesn't exceed the color limit
3. **Calculate Scaling**: Determines exact pixel size so largest dimension = max_size_mm
4. **Merge Regions**: Groups connected same-color pixels using flood-fill algorithm
5. **Generate Meshes**: Creates manifold 3D geometry for each region + backing plate
6. **Name Colors**: Uses color science (Delta E 2000) to find nearest color names
7. **Export 3MF**: Packages everything into a proper 3MF file with object names

## Examples 📸

### Simple 8-bit Sprite

```bash
python run_converter.py mario.png
```

- Input: 64x32 pixel sprite
- Output: 200mm x 100mm model (3.125mm per pixel)
- Results in ~5-10 colored regions
- Total height: 2mm (1mm color + 1mm base)

### Detailed Pixel Art

```bash
python run_converter.py ms-pac-man.png
```

- Input: 224x288 pixel image
- Output: 155.6mm x 200mm model (0.694mm per pixel)
- The taller dimension (288px) scales to exactly 200mm
- Smaller pixels = more detail!

### Custom Size for Smaller Bed

```bash
python run_converter.py image.png --max-size 150
```

- Scales to fit a 150mm x 150mm build area
- Perfect for smaller printers

### Thick & Sturdy

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
├── cli.py                   # Command-line interface
├── pixel_to_3mf.py         # Core conversion logic
├── image_processor.py       # Image loading, Y-flip, scaling, color validation
├── region_merger.py         # Flood-fill region detection
├── mesh_generator.py        # Manifold 3D geometry generation
└── threemf_writer.py        # 3MF file export with proper structure
```

### Architecture Notes

The code follows clean separation between the **CLI layer** and the **business logic**:

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
print(f"Created {stats['model_width_mm']:.1f}x{stats['model_height_mm']:.1f}mm model")
print(f"Pixel size: {stats['pixel_size_mm']:.3f}mm")
print(f"Regions: {stats['num_regions']}")
```

## Editing Defaults 🔧

Want to change the default settings? Just edit `pixel_to_3mf/constants.py`:

```python
# Your print bed size - largest dimension will scale to this
MAX_MODEL_SIZE_MM = 200.0

# Layer heights
COLOR_LAYER_HEIGHT_MM = 1.0
BASE_LAYER_HEIGHT_MM = 1.0

# Color limit (most slicers support 16 filaments max)
MAX_COLORS = 16
```

## Tips & Tricks 💡

### For Best Results

- **Use PNG files** with transparency for holes in your design
- **Keep pixel art reasonable** (under 300x300px) for practical print times
- **Use distinct colors** - the algorithm merges adjacent pixels with the exact same RGB value
- **Consistent pixel sizes across images?** Resize all your images to the same dimensions first (e.g., using ImageMagick)

### Understanding Scaling

The scaling is **exact and predictable**:

- A 64px wide image with `--max-size 200` → 200mm ÷ 64 = 3.125mm per pixel → 200mm x 100mm model
- A 288px tall image with `--max-size 200` → 200mm ÷ 288 = 0.694mm per pixel → 155.6mm x 200mm model
- A 100px square image with `--max-size 200` → 200mm ÷ 100 = 2.0mm per pixel → 200mm x 200mm model

The largest dimension always equals your max-size, and the smaller dimension scales proportionally!

### Slicer Setup

1. Open the 3MF file in Bambu Studio, PrusaSlicer, Orca Slicer, etc.
2. You'll see each colored region as a separate object with its color name
3. Assign filament colors to match (or get creative!)
4. The "Backing" object is your solid base layer
5. The meshes are manifold - no repair needed! ✅

### Common Issues

**"Too many colors" error:**

- Your image has more unique colors than the limit allows
- Solution 1: Reduce colors in your image editor (posterize/index mode)
- Solution 2: Increase the limit with `--max-colors 32` (but longer prints!)

**Colors not merging:**

- Regions only merge if they're the exact same RGB value
- Anti-aliasing and compression can create subtle color variations
- Solution: Use indexed color mode in your image editor (no anti-aliasing)

**Want consistent pixel sizes across multiple images?**

- Don't rely on the converter to do this!
- Resize all images to the same dimensions first using an image editor
- Example: Make all sprites 64x64px before converting

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

- ✅ **Removed pixel rounding** - Scaling is now exact and predictable!
- ✅ Fixed manifold geometry (no more repair needed!)
- ✅ Fixed triangle winding for correct normals
- ✅ Fixed Y-axis orientation (models appear right-side-up)
- ✅ Fixed backing plate to match pixel footprint with holes
- ✅ Fixed vertex sharing in merged regions
- ✅ Added color limiting with `--max-colors` parameter
- ✅ Updated all type hints for Pylance compatibility

## License 📄

Created for personal and educational use. The color_tools library is a separate component with its own licensing.

## Credits 🙌

Built with love for the 3D printing and pixel art communities! Special thanks to the Delta E color science research that makes perceptual color matching possible.

---

**Happy Printing!** 🎉
