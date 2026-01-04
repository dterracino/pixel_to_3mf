# RGB-Based Boundary Detection for Blue/Purple Color Matching

## Overview

This document explains the RGB component analysis logic used to distinguish blue from purple colors during filament matching. This is a **workaround for filament palettes with gaps** and should eventually be moved to the `color-tools` library.

## The Problem

When a filament palette lacks intermediate colors, pure Delta E 2000 matching can produce categorical mismatches. For example, with Bambu Lab PLA Basic/Matte filaments:

- **Bambu Purple**: #5E43B7 (R=94, G=67, B=183)
- **Bambu Blue**: #0A2989 (R=10, G=41, B=137)
- **Gap**: No colors between these two

### Real-World Examples

| Input Color | Description | Delta E Results | Without Fix | With Fix |
| ------------- | ------------- | ---------------- | ------------- | ---------- |
| #0000FF | Pure blue | Purple ΔE=14.37, Blue ΔE=15.04 | → Purple ❌ | → Blue ✅ |
| #686CE8 | Bluish purple (DECAPATTACK title) | Purple ΔE=14.37, Cobalt Blue ΔE=14.48 | → Cobalt Blue ❌ | → Purple ✅ |

Pure Delta E would match **pure blue to purple** because mathematically it's 0.67 units closer, even though this is categorically wrong.

## The Solution

### RGB Component Analysis

The fix uses the **red component** to distinguish blue from purple:

```python
# Blue in RGB: (R=low, G=low, B=high)
# Purple in RGB: (R=high, G=low, B=high)  ← Red component is key!

if R < 50 and B > 150:
    color_leans = "blue"
elif R > 80 and B > 150:
    color_leans = "purple"
else:  # 50 ≤ R ≤ 80
    color_leans = "boundary zone - use pure Delta E"
```

### When Penalty is Applied

The penalty (50 Delta E points) is ONLY applied when ALL of these are true:

1. `use_rgb_boundary_detection` is enabled (default: True)
2. The filament name contains "blue" or "purple"
3. The target color clearly leans toward one category (R < 50 or R > 80)

This means:

- ✅ Other filament palettes with better coverage are unaffected
- ✅ Non-blue/purple colors work normally (red, green, yellow, etc.)
- ✅ Boundary zone colors (50 ≤ R ≤ 80) still use pure Delta E
- ✅ Filaments without "blue" or "purple" in their names are never penalized

## Configuration

### Enabling/Disabling

**Default**: Enabled (recommended for most users)

**Disable if**:

- Your filament palette has excellent blue/purple coverage
- You want pure Delta E 2000 matching without any penalties
- You're experiencing false positives in color matching

**How to disable**:

```python
# In code
config = ConversionConfig(
    use_rgb_boundary_detection=False,  # Disable RGB boundary detection
    ...
)

# Via constants.py
USE_RGB_BOUNDARY_DETECTION = False
```

**Note**: There is currently no CLI flag to disable this. If needed, one could be added similar to `--prefer-hue` / `--no-prefer-hue`.

## Impact Analysis

### Safe for Other Palettes

The logic is **safe for other filament brands** because:

1. **Filament name checking**: Only applies to filaments named "blue" or "purple"
2. **Clear thresholds**: Only penalizes very obvious cases (R < 50 or R > 80)
3. **Boundary zone**: Middle range (50-80) uses pure Delta E

### Example: Other Filament Brands

If you have filaments with better coverage:

```text
Polymaker PLA:
- Sky Blue: #40A0FF (R=64) ← In boundary zone, no penalty
- Royal Blue: #0040C0 (R=0) ← Clear blue, penalty if matched to purple
- Violet: #8040FF (R=128) ← Clear purple, penalty if matched to blue
- Lavender: #C080FF (R=192) ← Clear purple, penalty if matched to blue
```

Even with these filaments, the logic works correctly:

- Pure blue (#0000FF) won't match to Violet or Lavender
- Bluish colors might match Sky Blue (boundary zone - no penalty)
- The penalties only prevent obviously wrong categorical matches

## Code Locations (TODO: Move to color-tools)

All of this logic is marked with `TODO` comments indicating it should move to the `color-tools` library:

### Functions to Move

1. **`_filament_name_category()`** ([threemf_writer.py:77-115](e:\pixel_to_3mf\pixel_to_3mf\threemf_writer.py#L77-L115))
   - Extracts color category from filament name
   - Should be part of `FilamentPalette` class

2. **`_calculate_hue_weighted_distance()`** ([threemf_writer.py:118-185](e:\pixel_to_3mf\pixel_to_3mf\threemf_writer.py#L118-L185))
   - Applies RGB boundary detection
   - Should be integrated into `palette.find_nearest()` logic

3. **Manual search loops** ([threemf_writer.py:258-270](e:\pixel_to_3mf\pixel_to_3mf\threemf_writer.py#L258-L270) and [threemf_writer.py:333-343](e:\pixel_to_3mf\pixel_to_3mf\threemf_writer.py#L333-L343))
   - Iterate through filtered filaments applying weighted distance
   - Should be replaced with enhanced `FilamentPalette.nearest_filament()` method

### Why Not in color-tools Yet?

This is a **workaround** for specific palette gaps. The `color-tools` library should have a more general solution that:

1. Detects palette gaps automatically
2. Applies appropriate penalties based on palette structure
3. Allows users to configure matching strategies
4. Supports multiple color space strategies (HSL, LAB, RGB)

For now, this implementation lives in `pixel_to_3mf` until a proper solution can be designed and implemented in `color-tools`.

## Testing

### Test Cases

```python
# Test blue/purple boundary
test_colors = [
    ((0, 0, 255), "Pure blue", "→ Blue ✅"),
    ((104, 108, 232), "#686CE8 purple title", "→ Purple ✅"),
    ((128, 0, 255), "Pure purple/magenta", "→ Purple ✅"),
    ((45, 50, 200), "Blueish R=45", "→ Blue ✅"),
]
```

### Validation

Run the converter with `--preview` flag to visually verify color accuracy:

```powershell
python run_converter.py --preview input.png
# Check the _preview.png to ensure blues stay blue and purples stay purple
```

## Future Work

### Phase 1: Document (DONE)

- ✅ Add this documentation
- ✅ Mark code with TODO comments
- ✅ Make configurable via `use_rgb_boundary_detection`

### Phase 2: Enhance (Future)

- [ ] Add CLI flags `--rgb-boundary` / `--no-rgb-boundary`
- [ ] Add tests for boundary detection logic
- [ ] Document in README.md and help text

### Phase 3: Migrate to color-tools (Future)

- [ ] Design general palette gap detection algorithm
- [ ] Implement flexible matching strategies in color-tools
- [ ] Remove workaround from pixel_to_3mf
- [ ] Update documentation

## References

- **Issue**: Blue objects (#0000FF) matching to purple filaments
- **Root Cause**: Bambu Lab palette gap (Purple #5E43B7 vs Blue #0A2989)
- **Solution**: RGB component analysis with R < 50 (blue) vs R > 80 (purple)
- **Default**: Enabled (safe for all palettes)
- **Disable**: Set `USE_RGB_BOUNDARY_DETECTION = False` in constants.py
