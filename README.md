# Pixel Art to 3MF Converter 🎨🖨️

Convert pixel art images into 3D printable 3MF files with automatic color detection and smart region merging!

## Table of Contents

- [Features](#features-)
- [Installation](#installation-)
- [Quick Start](#quick-start-)
- [Usage](#usage-)
- [Examples](#examples-)
- [How It Works](#how-it-works-)
- [Technical Details](#technical-details-)
- [Tips & Best Practices](#tips--best-practices-)
- [Troubleshooting](#troubleshooting-)
- [Project Structure](#project-structure-)
- [Contributing](#contributing-)
- [License](#license-)

## Features ✨

- **Exact Scaling**: Scales your pixel art so the largest dimension exactly matches your target size (default 200mm)
- **Smart Region Merging**: Uses flood-fill algorithm with configurable connectivity (4-way, 8-way, or per-pixel) to merge connected same-color pixels into single manifold objects
- **Auto-Crop**: Optional automatic cropping of fully transparent edges to optimize model size
- **Automatic Color Quantization**: Reduce image colors on-the-fly when exceeding limits - no external preprocessing needed!
- **Flexible Color Naming**: Choose between CSS color names, filament names (with maker/type/finish filters), or hex codes
- **Perceptual Color Matching**: Uses Delta E 2000 (industry standard) for accurate color distance calculations
- **Transparent Pixel Support**: Transparent areas become holes in the model
- **Flexible Layer Design**: Colored regions on top (default 1mm) + optional solid backing plate (default 1mm, set to 0 to disable)
- **Color Limiting**: Prevents accidentally converting images with too many colors (default max: 16)
- **Manifold Meshes**: Generates properly manifold geometry that slicers love (no repair needed!)
- **Correct Orientation**: Models appear right-side-up in slicers
- **Batch Processing**: Process entire folders of pixel art in one command with automatic summaries
- **Polygon Optimization**: Optional mesh optimization for 20-77% reduction in file size with 100% reliability (use `--optimize-mesh`)

## Installation 📦

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install Pillow numpy rich shapely triangle
```

### Project Structure

The `color_tools` library is included in the repository. Your directory structure should look like:

```text
pixel_to_3mf/
├── pixel_to_3mf/          # Main package
│   ├── __init__.py
│   ├── constants.py
│   ├── cli.py
│   └── ...
├── color_tools/           # Color matching library (included)
│   ├── __init__.py
│   ├── palette.py
│   └── ...
├── samples/               # Sample images and outputs
│   ├── input/            # Example pixel art
│   └── output/           # Example 3MF files
├── run_converter.py       # CLI entry point
└── requirements.txt
```

## Quick Start 🚀

Convert your first pixel art image in seconds:

```bash
# Basic conversion - uses defaults (200mm max size, 1mm layers)
python run_converter.py your_image.png

# Your 3MF file will be created as: your_image_model.3mf
```

That's it! Open the generated `.3mf` file in your slicer (Bambu Studio, PrusaSlicer, Cura, etc.).

## Usage 📖

### Single File Conversion

**Basic usage** - Convert one image with default settings:

```bash
python run_converter.py your_pixel_art.png
```

Creates `your_pixel_art_model.3mf` with:

- Largest dimension: 200mm
- Color layer: 1mm thick
- Base layer: 1mm thick
- Maximum 16 colors

**Custom settings:**

```bash
python run_converter.py image.png \
  --output custom_name.3mf \
  --max-size 150 \
  --color-height 1.5 \
  --base-height 2.0 \
  --max-colors 20
```

### Batch Processing

Process multiple images at once:

```bash
# Process all images in batch/input/
python run_converter.py --batch

# Custom input/output folders
python run_converter.py --batch \
  --batch-input my_sprites \
  --batch-output my_models

# With custom settings for all files
python run_converter.py --batch \
  --max-size 150 \
  --max-colors 20 \
  --skip-checks
```

**Batch mode features:**

- ✅ Processes all PNG, JPG, JPEG, GIF, BMP, and WEBP images.
- ✅ Generates timestamped Markdown summary with statistics
- ✅ Continues processing if individual files fail
- ✅ Use `--skip-checks` to bypass resolution warnings

### Command-Line Options Reference

#### Single File Mode

| Option | Description | Default |
|--------|-------------|---------|
| `image_file` | Input pixel art image (PNG, JPG, etc.) | Required |
| `-o, --output` | Output 3MF file path | `{input}_model.3mf` |
| `--max-size` | Maximum model dimension in mm | 200 |
| `--line-width` | Nozzle line width for printability checks (mm) | 0.42 |
| `--color-height` | Height of colored layer (mm) | 1.0 |
| `--base-height` | Height of backing plate (mm) - set to 0 to disable | 1.0 |
| `--max-colors` | Maximum unique colors allowed | 16 |
| `--backing-color` | Backing plate color as R,G,B | `255,255,255` (white) |
| `--quantize` | Automatically reduce colors when exceeding max-colors | Off |
| `--quantize-algo` | Quantization algorithm: `none` (fast/sharp), `floyd` (smooth) | `none` |
| `--quantize-colors` | Target color count for quantization (defaults to max-colors) | `max-colors` |
| `--auto-crop` | Automatically crop away fully transparent edges | Off |
| `--connectivity` | Pixel connectivity mode: 0 (per-pixel), 4 (edges), 8 (diagonals) | 8 |
| `--color-mode` | Color naming: `color` (CSS), `filament`, `hex` | `color` |
| `--filament-maker` | Filament maker filter(s), comma-separated (for `filament` mode) | `Bambu Lab` |
| `--filament-type` | Filament type filter(s), comma-separated (for `filament` mode) | `PLA` |
| `--filament-finish` | Filament finish filter(s), comma-separated (for `filament` mode) | `Basic, Matte` |
| `--optimize-mesh` | Use polygon-based mesh optimization | Off |

#### Batch Mode

| Option | Description | Default |
|--------|-------------|---------|
| `--batch` | Enable batch processing | Off |
| `--batch-input` | Input folder with images | `batch/input` |
| `--batch-output` | Output folder for 3MF files | `batch/output` |
| `--skip-checks` | Skip resolution warnings | Off |

> **Note:** All single file options apply to batch mode

### Optimized Mesh Generation 🚀

The converter includes polygon-based mesh optimization that significantly reduces file sizes and triangle counts while maintaining 100% reliability.

**Enable with:**

```bash
python run_converter.py image.png --optimize-mesh
```

**Benefits:**

- 📉 **20-77% reduction** in vertices and triangles for typical pixel art
- 📦 **Smaller 3MF files** (proportional to mesh reduction)
- ⚡ **Faster slicing** (fewer triangles = faster processing)
- ✅ **Same visual results** (both paths produce manifold meshes)
- ✅ **100% reliable** (never crashes, works on all images)

**How it works:**

- Merges pixel squares into larger polygons using shapely
- Triangulates polygons using constrained Delaunay triangulation (triangle library)
- Maintains all manifold properties (shared vertices, CCW winding, edge connectivity)

**When to use:**

- Any image where you want smaller file sizes
- Large images with many pixels per region (>20 pixels/region)
- Images with large solid-color areas

**Note:** The optimization fills any holes created by complex pixel merging (rare in pixel art). This produces identical visual results while ensuring 100% reliability.

### Using as a Python Library

```python
from pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.config import ConversionConfig

# Option 1: Use defaults
stats = convert_image_to_3mf(
    input_path="sprite.png",
    output_path="sprite.3mf"
)

# Option 2: Custom configuration
config = ConversionConfig(
    max_size_mm=150,
    color_height_mm=2.0,
    base_height_mm=2.0,
    max_colors=16,
    backing_color=(255, 255, 255),  # RGB tuple
    auto_crop=True,                  # Crop transparent edges
    connectivity=8,                   # 0, 4, or 8
    color_mode="filament",            # "color", "filament", or "hex"
    filament_maker="Bambu Lab",       # Single maker or ["Bambu Lab", "Polymaker"]
    filament_type="PLA",              # Single type or ["PLA", "PETG"]
    filament_finish=["Basic", "Matte"],  # Single finish or list
    optimize_mesh=False
)

stats = convert_image_to_3mf(
    input_path="sprite.png",
    output_path="sprite.3mf",
    config=config,
    progress_callback=lambda stage, msg: print(f"{stage}: {msg}")
)

# Access statistics
print(f"Model size: {stats['model_width_mm']:.1f}x{stats['model_height_mm']:.1f}mm")
print(f"Pixel size: {stats['pixel_size_mm']:.3f}mm")
print(f"Regions: {stats['num_regions']}")
print(f"Colors: {stats['num_colors']}")
```

## Examples 📸

### Sample Files

The `samples/` directory contains example conversions:

| Input Image | Dimensions | Description |
|-------------|------------|-------------|
| `nes-samus.png` | Small sprite | Classic NES character |
| `ms-pac-man.png` | 224x288px | Arcade game sprite |
| `c64ready.png` | Retro sprite | Commodore 64 style |
| `super-mario-nes-screenshot.png` | Game screenshot | More complex scene |

All samples have corresponding `.3mf` files in `samples/output/`.

### Usage Examples

#### Small Sprite (Default Settings)

```bash
python run_converter.py samples/input/nes-samus.png
```

- **Input:** Small pixel art sprite
- **Output:** 200mm model (scaled proportionally)
- **Perfect for:** Quick prints, testing

#### Detailed Pixel Art

```bash
python run_converter.py samples/input/ms-pac-man.png
```

- **Input:** 224x288 pixels
- **Output:** 155.6mm × 200mm (0.694mm per pixel)
- **Note:** Taller dimension (288px) scales to exactly 200mm

#### Custom Size for Smaller Printer

```bash
python run_converter.py image.png --max-size 150
```

- **Result:** Fits within 150mm × 150mm build area
- **Use case:** Smaller printers, multiple prints on one plate

#### Thick & Sturdy (Coasters, Tiles)

```bash
python run_converter.py coaster.png \
  --color-height 2.0 \
  --base-height 3.0
```

- **Total height:** 5mm (2mm color + 3mm base)
- **Use case:** Functional items that need durability

#### More Colors Allowed

```bash
python run_converter.py detailed_art.png --max-colors 32
```

- **Raises limit:** From 16 to 32 unique colors
- **Note:** More colors = longer print time with filament changes

#### Automatic Color Reduction

```bash
# Automatically reduce colors when image exceeds max-colors
python run_converter.py photo.png --quantize

# Use Floyd-Steinberg dithering for smoother gradients
python run_converter.py artwork.png --quantize --quantize-algo floyd

# Reduce to specific color count
python run_converter.py complex_art.png --quantize --quantize-colors 8
```

- **Benefit:** No need to preprocess images in external applications
- **Algorithms:**
  - `none`: Simple nearest color (faster, sharper edges)
  - `floyd`: Floyd-Steinberg dithering (slower, smoother gradients)
- **Use case:** Images with slightly more colors than your max-colors setting

#### No Backing Plate (Decals, Stickers)

```bash
python run_converter.py decal.png --base-height 0
```

- **Output:** Only colored regions, no backing plate
- **Total height:** Just the color layer (default 1mm)
- **Use case:** Decals, stickers, or if you want to add your own backing

#### Batch Convert Sprite Collection

```bash
python run_converter.py --batch \
  --batch-input game_sprites \
  --batch-output 3d_models \
  --max-size 100 \
  --skip-checks
```

- **Process:** All sprites in `game_sprites/` folder
- **Output:** Individual 3MF files in `3d_models/`
- **Size:** All scaled to 100mm max
- **Summary:** Creates timestamped report in output folder

#### Auto-Crop Transparent Edges

```bash
python run_converter.py sprite.png --auto-crop
```

- **Effect:** Automatically removes fully transparent borders
- **Result:** Tighter model bounds, smaller file size
- **Use case:** Images with large transparent padding, optimizing material usage

#### Custom Connectivity Modes

```bash
# Per-pixel mode (debugging/special effects)
python run_converter.py image.png --connectivity 0

# Classic 4-connectivity (edge-only, simpler geometry)
python run_converter.py image.png --connectivity 4

# Default 8-connectivity (includes diagonals, fewer objects)
python run_converter.py image.png --connectivity 8
```

- **0 (per-pixel):** Each pixel becomes a separate object - useful for debugging or intentional effects
- **4 (edge-only):** Pixels connected via edges only - simpler geometry, more separate regions
- **8 (diagonals):** Includes diagonal connections - fewer objects, may create complex shapes

**When to use each:**

- **0:** Debugging region merging issues, or creating artistic "pixelated" effects
- **4:** When you want cleaner geometry separation, or traditional flood-fill behavior
- **8 (default):** Best for most pixel art - merges diagonal lines properly

#### Filament-Based Color Naming

```bash
# Use Bambu Lab PLA filament names (default)
python run_converter.py image.png --color-mode filament

# Use specific filament maker/type
python run_converter.py image.png \
  --color-mode filament \
  --filament-maker "Polymaker" \
  --filament-type "PLA"

# Filter by multiple makers (comma-separated)
python run_converter.py image.png \
  --color-mode filament \
  --filament-maker "Bambu Lab,Polymaker" \
  --filament-type "PLA"

# Filter by multiple types (comma-separated)
python run_converter.py image.png \
  --color-mode filament \
  --filament-maker "Bambu Lab" \
  --filament-type "PLA,PETG"

# Filter by finish (comma-separated for multiple)
python run_converter.py image.png \
  --color-mode filament \
  --filament-maker "Bambu Lab" \
  --filament-type "PLA" \
  --filament-finish "Silk,Matte"

# Combine multiple filters
python run_converter.py image.png \
  --color-mode filament \
  --filament-maker "Bambu Lab,Polymaker,eSun" \
  --filament-type "PLA,PETG" \
  --filament-finish "Silk,Matte,Basic"

# Use hex color codes instead
python run_converter.py image.png --color-mode hex
```

- **`color` mode:** Uses CSS color names (e.g., "Red", "SkyBlue") - best for general use
- **`filament` mode:** Matches to real filament colors with maker/type/finish filters - perfect for planning prints
- **`hex` mode:** Uses hex codes (e.g., "#FF5733") - precise color identification

**Filament mode benefits:**

- See actual filament names in your slicer (e.g., "Bambu Lab PLA Basic Red")
- Filter by your available filament inventory (supports multiple makers/types/finishes)
- Plan multi-color prints with real products in mind

## How It Works 🔧

The converter follows a precise pipeline to transform 2D images into 3D printable files:

```text
Image Loading → Auto-Crop (optional) → Color Validation → Exact Scaling → 
Region Merging → Mesh Generation → Color Naming → 3MF Export
```

### Step-by-Step Process

1. **Load & Prepare Image**
   - Reads your pixel art using PIL/Pillow
   - Converts to RGBA format (supports transparency)
   - Flips Y-axis so models appear right-side-up in slicers
   - Optionally crops away fully transparent edges (if `--auto-crop` is enabled)

2. **Validate Colors**
   - Counts unique colors in the image
   - Ensures it doesn't exceed your color limit (default: 16)
   - Reserves one color slot for backing plate if needed

3. **Calculate Exact Scaling**
   - Determines pixel size: `pixel_size = max_size_mm / largest_dimension_px`
   - Largest dimension scales to **exactly** max_size_mm
   - No rounding - predictable, precise scaling

4. **Merge Regions (Flood Fill)**
   - Groups connected same-color pixels into regions
   - Configurable connectivity: **0** (per-pixel), **4** (edges only), or **8** (includes diagonals)
   - Each region becomes one 3D object
   - Transparent pixels create holes

5. **Generate Manifold Meshes**
   - Creates 3D geometry for each region:
     - Top face (colored layer)
     - Bottom face
     - Perimeter walls connecting them
   - **Shared vertices** between adjacent pixels
   - **Counter-clockwise winding** for correct normals
   - Generates optional backing plate with holes for transparent areas (if base_height > 0)

6. **Name Colors**
   - Multiple naming modes available:
     - **CSS mode**: Converts RGB → LAB, uses Delta E 2000 to find nearest CSS color name
     - **Filament mode**: Matches to real filament colors (with maker/type/finish filters)
     - **Hex mode**: Uses hex color codes (e.g., "#FF5733")
   - Examples (CSS mode): RGB(255, 0, 0) → "Red", RGB(135, 206, 235) → "SkyBlue"

7. **Export 3MF File**
   - Packages meshes into 3MF format (ZIP archive)
   - Includes object names (color names) for slicer UI
   - 3MF structure:

     ```text
     .3mf (ZIP)
     ├── 3D/
     │   ├── 3dmodel.model         # Assembly
     │   └── Objects/object_1.model # Geometry
     ├── Metadata/
     │   └── model_settings.config  # Object names
     └── [Content_Types].xml
     ```

## Technical Details 🤓

### Region Merging: Configurable Connectivity

The region merger supports three connectivity modes to control how pixels are grouped:

#### 8-Connectivity (Default)

Pixels are considered connected if they share an edge **or a diagonal corner**. This prevents diagonal lines from being split into separate objects.

```text
Diagonal line in 8-connectivity: 1 region ✅
X . .
. X .
. . X
```

#### 4-Connectivity (Edge-Only)

Pixels are connected only if they share an edge (not diagonals). Results in simpler geometry but more separate regions.

```text
Diagonal line in 4-connectivity: 3 separate regions
X . .
. X .
. . X
```

#### 0-Connectivity (Per-Pixel)

No merging - each pixel becomes a separate object. Useful for debugging or creating intentional "pixelated" effects.

**Algorithm:** Iterative breadth-first search (BFS)
**Time complexity:** O(n) where n = number of pixels
**Result:** Connected same-color pixels become single 3D object

### Manifold Mesh Generation

All meshes are **manifold** - no repair needed in slicers!

**Manifold properties:**

- ✅ **No duplicate vertices:** Adjacent pixels share corner vertices
- ✅ **Consistent winding:** Counter-clockwise triangles = outward normals
- ✅ **Edge connectivity:** Every edge shared by exactly 2 triangles
- ✅ **Closed surface:** No gaps or holes (except intentional transparency)

**Mesh structure per region:**

```text
Top face: 2 triangles per pixel
Bottom face: 2 triangles per pixel  
Walls: Up to 8 triangles per perimeter pixel
```

### Coordinate System & Orientation

**Image coordinates:**

- Origin: Top-left (0,0)
- Y-axis: Points down

**3D coordinates (after Y-flip):**

- Origin: Bottom-left (0,0,0)
- Y-axis: Points up
- Z-axis: Height (0 = bottom, height_mm = top)

This ensures pixel art appears **right-side-up** when loaded in slicers.

### Color Naming: Multiple Modes

The converter supports three color naming modes for labeling objects in the 3MF file:

#### CSS Color Mode (Default)

Uses perceptual color matching with Delta E 2000:

1. **RGB → LAB conversion**
   - RGB: Device-dependent color space
   - LAB: Perceptually uniform color space

2. **Delta E 2000 calculation**
   - Industry standard for color difference
   - Accounts for human color perception
   - More accurate than simple RGB distance

3. **Nearest color selection**
   - Compares to 147 CSS color names
   - Finds minimum Delta E 2000 value
   - Example matches:
     - RGB(255, 0, 0) → "Red"
     - RGB(135, 206, 235) → "SkyBlue"
     - RGB(255, 215, 0) → "Gold"

#### Filament Color Mode

Matches colors to real filament products with configurable filters:

- **Maker filter**: e.g., "Bambu Lab", "Polymaker", "eSun" (supports multiple, comma-separated)
- **Type filter**: e.g., "PLA", "PETG", "ABS" (supports multiple, comma-separated)
- **Finish filter**: e.g., "Basic", "Matte", "Silk" (supports multiple, comma-separated)

Uses the same Delta E 2000 algorithm but compares against filtered filament database.

**Example result:** "Bambu Lab PLA Basic Red" instead of just "Red"

#### Hex Code Mode

Simply uses hex color codes for precise color identification:

- RGB(255, 87, 51) → "#FF5733"
- No perceptual matching, exact representation

### Exact Scaling Mathematics

The scaling formula ensures predictable results:

```python
pixel_size_mm = max_size_mm / max(width_px, height_px)
model_width_mm = width_px * pixel_size_mm
model_height_mm = height_px * pixel_size_mm
```

**Examples:**

- 64×32 image, max_size=200 → 200÷64 = 3.125mm/pixel → 200×100mm model
- 288×224 image, max_size=200 → 200÷288 = 0.694mm/pixel → 200×155.6mm model
- 100×100 image, max_size=200 → 200÷100 = 2.0mm/pixel → 200×200mm model

The larger dimension **always equals** max_size exactly.

### 3MF File Format

3MF is a modern 3D printing format (ZIP archive containing XML):

**Structure:**

```text
model.3mf (ZIP archive)
├── [Content_Types].xml          # MIME types
├── _rels/.rels                  # Relationships
├── 3D/
│   ├── 3dmodel.model           # Main assembly
│   └── Objects/
│       └── object_1.model      # Mesh geometry (vertices + triangles)
└── Metadata/
    └── model_settings.config   # Object names (color labels)
```

**Advantages over STL:**

- ✅ Supports multiple objects with names
- ✅ Smaller file size (compressed)
- ✅ Richer metadata
- ✅ Industry standard (Bambu, Prusa, etc.)

## Tips & Best Practices 💡

### For Best Results

✅ **Use PNG files** with transparency for holes in your design
✅ **Keep pixel art reasonable** - under 300×300px for practical print times  
✅ **Use indexed color mode** in your image editor (no anti-aliasing)
✅ **Use distinct colors** - regions merge only with exact RGB matches
✅ **Test with samples** - try converting `samples/input/*.png` first

### Understanding Pixel Sizes

The converter warns if pixel size < 0.42mm (typical nozzle width):

| Image Size | Max Size | Pixel Size | Printability |
|------------|----------|------------|--------------|
| 64×64 | 200mm | 3.125mm | ✅ Excellent |
| 100×100 | 200mm | 2.0mm | ✅ Good |
| 200×200 | 200mm | 1.0mm | ⚠️ Challenging |
| 300×300 | 200mm | 0.67mm | ⚠️ Difficult |
| 500×500 | 200mm | 0.4mm | ❌ Too small |

**Solutions for high-resolution images:**

- Reduce image resolution before converting
- Increase `--max-size` parameter
- Use larger nozzle (0.6mm, 0.8mm)

### Choosing the Right Connectivity Mode

**Use 8-connectivity (default)** for:

- Most pixel art with diagonal lines
- Minimizing number of objects in slicer
- Natural-looking merged regions

**Use 4-connectivity** when:

- You want cleaner geometry separation
- Traditional flood-fill behavior is needed
- Diagonal connections create unwanted merges

**Use 0-connectivity (per-pixel)** for:

- Debugging region merging issues
- Creating intentional "pixelated/voxel" artistic effects
- Testing individual pixel extrusion

### When to Use Auto-Crop

The `--auto-crop` feature is helpful when:

- Your image has large transparent borders (from export padding)
- You want to minimize model size and material usage
- Processing screenshots with UI padding
- Batch processing images with inconsistent padding

**Note:** Only fully transparent edges are cropped. Partially transparent pixels are preserved.

### Choosing a Color Naming Mode

**Use CSS mode (`--color-mode color`)** when:

- You want simple, recognizable color names
- General-purpose printing without specific filament planning
- Quick identification of regions in slicer

**Use Filament mode (`--color-mode filament`)** when:

- Planning prints with specific filament brands/types
- Matching to your actual filament inventory
- You want slicer to show real product names
- Working with specific maker's color palette

**Use Hex mode (`--color-mode hex`)** when:

- You need precise color identification
- Doing color-accurate reproduction
- Programmatic processing of output files

### Consistent Pixel Sizes Across Multiple Images

**Problem:** Different sized images will have different pixel sizes

**Solution:** Resize all images to same dimensions first:

```bash
# Using ImageMagick
mogrify -resize 64x64! *.png

# Then convert all with same pixel size
python run_converter.py --batch --batch-input resized_sprites
```

### Slicer Setup

1. **Open 3MF in your slicer** (Bambu Studio, PrusaSlicer, Cura, etc.)
2. **Check orientation** - should be right-side-up automatically
3. **Assign filaments:**
   - Each region is named with its color (e.g., "Red", "Blue")
   - Match filament colors or customize
   - The "Backing" object is your base layer (if you didn't disable it with `--base-height 0`)
4. **No repair needed** - meshes are manifold!
5. **Slice and print** 🎉

## Troubleshooting 🔧

### Common Issues

#### "Too many colors" error

**Problem:** Image has more unique colors than allowed (default: 16)

**Solutions:**

```bash
# Option 1: Use automatic quantization (easiest!)
python run_converter.py image.png --quantize

# Option 2: Quantize with Floyd-Steinberg dithering for smoother results
python run_converter.py image.png --quantize --quantize-algo floyd

# Option 3: Increase color limit
python run_converter.py image.png --max-colors 32

# Option 4: Reduce colors in image editor
# - Use posterize/index color mode
# - Reduce to 16 colors or less
```

**Recommended:** Use `--quantize` for automatic color reduction without needing external tools!

#### Colors not merging (too many small regions)

**Problem:** Anti-aliasing or JPEG compression creates subtle color variations

**Solutions:**

- ✅ Save as PNG (not JPEG - JPEG adds compression artifacts)
- ✅ Use indexed color mode in image editor
- ✅ Disable anti-aliasing when creating pixel art
- ✅ Use "nearest neighbor" scaling if resizing

**Example in GIMP:**

```text
Image → Mode → Indexed
  Maximum colors: 16
  ☑ Remove unused colors
```

#### Model appears upside-down

**Symptoms:** Text or recognizable elements inverted

**This shouldn't happen** - the converter auto-flips images. If it does:

1. Check if image was pre-flipped before conversion
2. Report as bug with sample image

#### Pixel size warning

**Warning:** "Pixel size (0.3mm) is smaller than typical line width (0.42mm)"

**Meaning:** Pixels may be too small to print reliably

**Solutions:**

```bash
# Increase model size
python run_converter.py image.png --max-size 300

# Or reduce image resolution first
# Then convert with normal settings
```

#### File won't open in slicer

**Rare, but possible causes:**

1. **3MF corrupted** - Try re-converting
2. **Slicer compatibility** - Try different slicer (Bambu, Prusa, Cura)
3. **Invalid geometry** - Report as bug with sample image

The converter generates valid manifold meshes, but edge cases may exist.

#### Out of memory on large images

**Problem:** Very large images (>1000×1000px) may consume significant RAM

**Solutions:**

```bash
# Reduce image resolution first
# Pixel art shouldn't need high resolution anyway

# Or convert smaller regions at a time (manual cropping)
```

## Project Structure 📁

### Code Organization

```text
pixel_to_3mf/
├── __init__.py           # Package entry point
├── constants.py          # All default values (edit here to change defaults)
├── config.py             # ConversionConfig dataclass
├── cli.py                # Command-line interface (argparse, output)
├── pixel_to_3mf.py      # Core conversion logic (main pipeline)
├── image_processor.py    # Image loading, Y-flip, scaling, validation
├── region_merger.py      # Flood-fill algorithm (8-connectivity)
├── mesh_generator.py     # 3D geometry generation (manifold meshes)
├── threemf_writer.py     # 3MF file export (ZIP + XML)
└── color_tools/          # External color matching library
    ├── __init__.py
    ├── palette.py        # CSS color database
    └── conversions.py    # RGB ↔ LAB conversions
```

### Architecture: Clean Separation

The codebase separates **CLI layer** from **business logic**:

**CLI layer** (`cli.py`, `run_converter.py`):

- Command-line argument parsing
- User-facing output (print statements, progress)
- Error messages and formatting

**Business logic** (all other modules):

- Pure conversion functions
- No print statements
- Fully programmatic API
- Testable independently

This allows using the converter as:

1. **Command-line tool** - `python run_converter.py image.png`
2. **Python library** - `from pixel_to_3mf import convert_image_to_3mf`

### Customizing Defaults

Edit `pixel_to_3mf/constants.py` to change default values:

```python
# Maximum model size (mm) - largest dimension scales to this
MAX_MODEL_SIZE_MM = 200.0

# Layer heights (mm)
COLOR_LAYER_HEIGHT_MM = 1.0
BASE_LAYER_HEIGHT_MM = 1.0

# Color limit (most slicers support ~16 filaments)
MAX_COLORS = 16

# Default backing plate color (RGB tuple)
BACKING_COLOR = (255, 255, 255)  # White

# Nozzle line width for printability warnings (mm)
LINE_WIDTH_MM = 0.42

# Coordinate precision (decimal places = 0.001mm)
COORDINATE_PRECISION = 3

# Color naming mode - "color", "filament", or "hex"
COLOR_NAMING_MODE = "color"

# Default filament filters for filament mode
DEFAULT_FILAMENT_MAKER = "Bambu Lab"
DEFAULT_FILAMENT_TYPE = "PLA"
DEFAULT_FILAMENT_FINISH = ["Basic", "Matte"]
```

After editing, the new defaults apply to all conversions.

## Contributing 🤝

Contributions are welcome! This project follows clean code principles:

### Development Setup

```bash
# Clone repository
git clone https://github.com/dterracino/pixel_to_3mf.git
cd pixel_to_3mf

# Install dependencies
pip install -r requirements.txt

# Run tests
python tests/run_tests.py
```

### Testing

The test suite uses Python's built-in `unittest` framework:

```bash
# Run all tests
python tests/run_tests.py

# Run specific test module
python -m unittest tests.test_image_processor
python -m unittest tests.test_region_merger
python -m unittest tests.test_mesh_generator
```

See [`tests/README.md`](tests/README.md) for detailed testing documentation.

### Code Style

- **Type hints** on all function signatures
- **Docstrings** explaining WHY, not just WHAT
- **No magic numbers** - use constants from `constants.py`
- **Separation of concerns** - keep CLI separate from logic
- **Manifold meshes** - all geometry must be valid

### Areas for Contribution

- 🎨 Additional color palettes beyond CSS colors
- 🚀 Performance optimizations (polygon merging using shapely/triangle - see [`docs/OPTIMIZATION_PLAN.MD`](docs/OPTIMIZATION_PLAN.MD))
- 🧪 More test coverage
- 📝 Documentation improvements
- 🐛 Bug fixes

## License 📄

Created for personal and educational use. The `color_tools` library is a separate component with its own licensing.

## Credits 🙌

Built with love for the 3D printing and pixel art communities!

**Technologies:**

- **Pillow** - Image processing
- **NumPy** - Fast array operations  
- **Rich** - Beautiful terminal output
- **Shapely & Triangle** - Geometric operations (planned optimization)
- **Delta E 2000** - Perceptual color science

Special thanks to the color science research that makes perceptual color matching possible.

---

**Happy Printing!** 🎉

*Transform your pixel art into tangible 3D objects - one layer at a time.*
