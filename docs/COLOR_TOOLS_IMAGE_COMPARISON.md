# color_tools: Image Comparison Module Design

Design notes for a robust image comparison feature to be added to the
`color_tools` library. These ideas were developed while building region
reduction tooling for pixel_to_3mf and generalise cleanly to any
palette-aware image quality workflow.

---

## Motivation

When evaluating image filters (denoising, downscaling, smoothing), you need
more than a single number. Different metrics capture different axes of quality,
and the "right" composite depends entirely on what you are comparing and why.
The goal is a library module that:

- Computes **all** raw metrics unconditionally (no opinions baked in)
- Detects image type automatically so callers don't have to classify manually
- Lets callers plug in their own scoring rules — via code **or** a simple JSON
  file — without touching library internals
- Returns a typed result that always includes raw metrics alongside any
  composite score

---

## Architecture: Three Layers

### Layer 1 — Raw Metrics (always computed)

Pure measurement, no weighting, no opinions.

| Metric | Description | Range | Notes |
| --- | --- | --- | --- |
| `mse` | Mean Squared Error | 0 → ∞ | Lower is better. Resolution-dependent |
| `psnr` | Peak Signal-to-Noise Ratio (dB) | 0 → ∞ (inf = identical) | Higher is better. Clamp at 50 dB for normalisation |
| `ssim` | Structural Similarity Index | 0 → 1 | Higher is better. Requires scikit-image |
| `pct_changed` | % of pixels that differ (any channel) | 0 → 100 | Lower is better |
| `histogram_sim` | Colour distribution similarity (e.g. Bhattacharyya or correlation) | 0 → 1 | Higher is better |
| `edge_sharpness` | Impulse-ratio of Sobel edge response | 0 → 1 | Pixel art scores high; photos score low |
| `unique_colors` | Number of unique RGB colours in image | 1 → N | Descriptor, not a quality metric per se |
| `spatial_freq_energy` | High-frequency energy ratio (FFT-based) | 0 → 1 | Pixel art scores high |

The raw metrics dict is always present in `ComparisonResult`, regardless of
which scoring rule (if any) is used.

### Layer 2 — Image Type Detection (optional, feeds Layer 3)

Uses a subset of Layer 1 metrics to classify the image. Can always be
overridden by the caller.

```python
class ImageType(enum.Enum):
    AUTO        = "auto"       # detect automatically
    PIXEL_ART   = "pixel_art"  # < ~256 colours, high edge sharpness
    PHOTO       = "photo"      # many colours, smooth gradients
    ILLUSTRATION = "illustration"  # low-ish colours, smooth edges
    TECHNICAL   = "technical"  # diagrams, maps, schematics
```

**Detection heuristics** (all computable from Layer 1 metrics with no ML):

- `unique_colors < 256` AND `edge_sharpness > 0.7` → `PIXEL_ART`
- `unique_colors > 10_000` AND `edge_sharpness < 0.4` → `PHOTO`
- `unique_colors < 2_000` AND `edge_sharpness < 0.4` → `ILLUSTRATION`
- Fallback → `PHOTO`

These thresholds are a starting point and should be tuned empirically.

### Layer 3 — Scoring Rules (pluggable, opinionated)

A `ScoringRule` is anything that maps a `ComparisonResult` to a `float` in
`[0, 1]`. Three construction paths, all producing the same type:

```python
ScoringRule.from_preset("pixel_art")     # built-in weight presets
ScoringRule.from_json("my_rule.json")    # user-defined JSON rule file
ScoringRule.from_callable(fn)            # arbitrary Python function
```

---

## Built-in Presets

### `pixel_art`

Cares most about exact palette fidelity and hard-edge preservation.

| Metric | Weight | Direction |
| --- | --- | --- |
| `ssim` | 0.45 | higher is better |
| `pct_changed` | 0.35 | lower is better |
| `psnr` | 0.20 | higher is better |

### `photo`

Cares most about perceptual smoothness and colour distribution.

| Metric | Weight | Direction |
| --- | --- | --- |
| `psnr` | 0.40 | higher is better |
| `ssim` | 0.35 | higher is better |
| `histogram_sim` | 0.25 | higher is better |

### `technical`

Cares about structural/edge preservation over colour accuracy.

| Metric | Weight | Direction |
| --- | --- | --- |
| `ssim` | 0.50 | higher is better |
| `edge_sharpness` | 0.30 | higher is better |
| `pct_changed` | 0.20 | lower is better |

---

## Perceptual Thresholds

The SSIM literature and practical pixel art experience suggest these rough
cutoffs for the composite score (pixel-art preset):

| SSIM range | Composite (approx.) | Perceptual meaning |
| --- | --- | --- |
| > 0.95 | > 0.87 | Essentially imperceptible — needs side-by-side to notice |
| 0.90–0.95 | 0.83–0.87 | Trained eye might spot it; casual viewer won't |
| 0.80–0.90 | 0.75–0.83 | Visible on close inspection; acceptable for many uses |
| < 0.80 | < 0.75 | Noticeable degradation — starts to look "processed" |

The recommended default **pass threshold is 0.80** (composite), which
corresponds to SSIM ≈ 0.90. Below this the filter is considered too
destructive for faithful pixel art reproduction.

These values were established empirically on `sf2_ryu_level.png`
(384×224, 16 colours after quantise). The composite score generalises
reasonably across images because it is perceptually calibrated, not
resolution-dependent.

---

## JSON Rule Format

Users define their own composite without writing Python:

```json
{
  "name": "my_pixel_art_rule",
  "image_type_hint": "pixel_art",
  "metrics": [
    { "metric": "ssim",        "weight": 0.45, "direction": "higher_is_better" },
    { "metric": "pct_changed", "weight": 0.35, "direction": "lower_is_better"  },
    { "metric": "psnr",        "weight": 0.20, "direction": "higher_is_better" }
  ],
  "normalize": true,
  "threshold": 0.80
}
```

**Field notes:**

- `direction` — required. Controls whether the metric is inverted before
  weighting. `"lower_is_better"` metrics are transformed as `1 - normalised`
- `normalize` — if `true`, all metrics are clamped to `[0, 1]` before
  weighting and the composite is also `[0, 1]`
- `threshold` — optional pass/fail gate. If set, `ComparisonResult.passed`
  is `True` when composite ≥ threshold

**Normalisation ranges** (must be documented clearly so users know what
they are weighting):

| Metric | Normalised as |
| --- | --- |
| `psnr` | `min(psnr, 50) / 50` |
| `mse` | `1 - min(mse, 65025) / 65025` (65025 = 255²) |
| `pct_changed` | `value / 100` |
| `ssim` | already `[0, 1]` |
| `histogram_sim` | already `[0, 1]` |
| `edge_sharpness` | already `[0, 1]` |

---

## API Design

```python
from color_tools import compare_images, detect_image_type, ScoringRule, ImageType

# Simplest call — all metrics, no composite
result = compare_images(ref_img, result_img)

# With automatic type detection and built-in preset
result = compare_images(ref_img, result_img,
                        image_type=ImageType.AUTO,
                        scoring_rule=ScoringRule.from_preset("auto"))

# With user JSON rule
result = compare_images(ref_img, result_img,
                        scoring_rule=ScoringRule.from_json("rules/my_rule.json"))

# With callable rule (full access to all raw metrics)
result = compare_images(ref_img, result_img,
                        scoring_rule=ScoringRule.from_callable(
                            lambda m: 0.7 * m.ssim + 0.3 * (1 - m.pct_changed / 100)
                        ))

# Standalone type detection
image_type = detect_image_type(img)  # returns ImageType enum value

# Fast mode — skips expensive metrics (SSIM, frequency analysis)
result = compare_images(ref_img, result_img, fast=True)
```

### `ComparisonResult` dataclass

```python
@dataclass
class ComparisonResult:
    # Raw metrics — always present
    mse:             float
    psnr:            float
    ssim:            float | None   # None if scikit-image not installed
    pct_changed:     float
    histogram_sim:   float | None   # None if fast=True
    edge_sharpness:  float | None   # None if fast=True
    unique_colors:   int
    spatial_freq_energy: float | None

    # Type detection
    detected_type:   ImageType

    # Composite — None if no scoring_rule was provided
    composite_score: float | None
    passed:          bool | None    # None if no threshold in rule
    scoring_rule:    str            # name of rule used, or "none"
```

Always include raw metrics alongside the composite. Composite scores are
opaque; raw metrics let callers understand *why* two results differ.

---

## Notes on Specific Metrics

### SSIM vs PSNR for pixel art

SSIM is the better primary metric for pixel art. PSNR treats all pixel
errors equally regardless of location — replacing a character's eye with sky
colour counts the same as replacing a uniform background pixel. SSIM accounts
for local structure, so it correctly penalises changes that disrupt edges and
detail clusters.

**Observed values on sf2_ryu_level.png** (384×224, 16 colours after quantise):

| Filter | Region reduction | %Chg | PSNR | SSIM |
| --- | --- | --- | --- | --- |
| Blob min=2px | 51% | 6.2% | 29.0 | 0.945 |
| Blob min=4px | 77% | 14.4% | 25.3 | 0.868 |
| Mode k=3 | 61% | 33.6% | 22.9 | 0.743 |
| Mode k=7 | 86% | 47.5% | 19.8 | 0.517 |
| NN 75% | 33% | 20.5% | 25.1 | 0.853 |
| NN 50% | 60% | 36.0% | 22.4 | 0.728 |

Key takeaway: blob denoising at min=2px achieves 51% region reduction with
SSIM=0.945 — essentially imperceptible. Mode window achieves similar region
reduction at far greater structural cost (SSIM=0.743 at 60% reduction).

### Histogram similarity

Useful as a "colour distribution preserved?" check, but can be misleading as
a primary quality metric. A filter that replaces a 2px speck with surrounding
colour will score *better* on histogram similarity (distribution barely
changes) while making a visible structural change. Treat as supplementary,
not primary.

### SIFT / ORB / AKAZE

Feature-point detectors designed for matching different photos of the same
scene (scale/rotation invariant). For same-resolution same-palette image
pairs, SSIM measures structure preservation more directly and cheaply.
These are worth considering if the library is extended to compare images at
different resolutions or from different cameras.

---

## Implementation Notes

- **Normalisation must be documented** in the schema so users know what
  they are weighting. PSNR's theoretical upper bound is ∞; clamp at 50 dB.
  MSE is resolution-dependent; normalise against max possible (255²).
- **Always return all raw metrics**, even when a composite is computed.
  Users should always be able to audit why two images scored differently.
- **`fast=True` flag** skips expensive metrics (SSIM, frequency analysis)
  for callers who need throughput over completeness.
- **Optional dependencies**: scikit-image for SSIM. If not installed,
  `ssim` field is `None` and any scoring rule that references it raises a
  clear `MissingDependencyError` rather than silently using 0.
