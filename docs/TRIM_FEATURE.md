# Disconnected Pixel Trimming Feature

## Overview

The `--trim` flag removes "disconnected" pixels from your pixel art before converting to 3D. These are pixels that only connect to the rest of the image through corner vertices (diagonally), making them unreliable for 3D printing.

## What are Disconnected Pixels?

A pixel is "disconnected" if it has NO edge-connected neighbors (up/down/left/right) in its region - only diagonal connections through corners.

### Example from the Problem Statement

```
BBBBBBX
BBBBXXB  <- This B is disconnected (only touches via corner)
BBBBXXX
```

The B pixel at position (6,1) only touches other B pixels diagonally. In 3D printing:
- It would only share a single vertex with neighboring geometry
- This creates a weak connection point that's unreliable to print
- The printer may struggle with such fine details

## Usage

### Basic Usage

```bash
python run_converter.py image.png --trim
```

### Combined with Other Options

```bash
python run_converter.py sprite.png --trim --connectivity 8 --max-size 150
```

## How It Works

1. **Region Merging**: First, pixels are grouped into regions using the connectivity mode (4 or 8)
2. **Disconnection Detection**: Each pixel is checked for edge-connected neighbors
3. **Iterative Removal**: Disconnected pixels are removed iteratively (removing one may expose another)
4. **Empty Region Filtering**: Regions that become empty are removed from the output

## Examples

### Example 1: Simple Disconnected Pixel

**Input Pattern:**
```
RRRR...
RRRR.R.  <- Single disconnected red pixel
RRRR...
```

**Without --trim:** 2 regions (main block + isolated pixel)  
**With --trim:** 1 region (isolated pixel removed)

### Example 2: Diagonal Line

**Input Pattern:**
```
R......
.R.....
..R....
...R...
```

**Without --trim (8-connectivity):** 1 region (diagonal pixels connected)  
**With --trim:** 0 regions (all pixels disconnected, entire region removed)

### Example 3: Multiple Colors

**Input Pattern:**
```
RRRR...B
RRRR.R.B
RRRR...B
```

**Without --trim:** 3 regions (red main, red isolated, blue line)  
**With --trim:** 2 regions (red main, blue line - red isolated removed)

## Technical Details

### Algorithm

The trimming algorithm:

1. For each region:
   - Identify all pixels with no edge-connected neighbors
   - Remove those pixels
   - Repeat until no more disconnected pixels exist
   
2. Filter out empty regions

3. Continue with mesh generation

### Edge vs Diagonal Connectivity

- **Edge-connected neighbors:** Up, down, left, right (4-connectivity)
- **Diagonal neighbors:** Top-left, top-right, bottom-left, bottom-right
- **Disconnected:** Has diagonal neighbors only, NO edge neighbors

### Performance

The trim operation runs after region merging but before mesh generation, adding minimal overhead to the conversion process.

## When to Use --trim

### Use --trim when:

✅ Your pixel art has stray pixels that touch the main design only at corners  
✅ You're using 8-connectivity and want cleaner geometry  
✅ You want to ensure all printed parts have strong edge connections  
✅ You're experiencing print failures on corner-connected pixels

### Don't use --trim when:

❌ You intentionally want isolated single pixels  
❌ Your design relies on diagonal-only connections  
❌ You're using 4-connectivity (most isolated pixels are already separate)

## Testing

The feature includes comprehensive test coverage:

- **Unit tests:** `tests/test_trim_disconnected.py` (14 tests)
- **Integration tests:** `tests/test_trim_integration.py` (5 tests)

Run tests with:
```bash
python tests/run_tests.py
```

## Compatibility

- **Connectivity modes:** Works with all modes (0, 4, 8)
- **Other features:** Compatible with padding, quantization, auto-crop, etc.
- **Default:** Disabled (must explicitly use `--trim`)

## Sample Images

Sample images demonstrating the feature are in `samples/input/`:
- `disconnected_pixel_example.png` - The exact pattern from the problem statement

Converted outputs in `samples/output/`:
- `disconnected_no_trim.3mf` - Without trimming
- `disconnected_with_trim.3mf` - With trimming enabled
