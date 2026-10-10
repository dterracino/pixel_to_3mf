# Palette Relief Design

## Status

Discussion draft. This document defines the proposed contract before production
implementation begins. Existing Two-Level Relief behavior remains unchanged
until an implementation plan is approved.

## Purpose

Palette Relief creates a high-relief model in which every final image color can
have an independently specified height. It is intended for color-driven relief
art such as arcade screenshots, sprites, signs, and illustrations.

This is distinct from LayerForge's layer-authoring workflow. LayerForge lets a
user select arbitrary areas and export semantic depth layers. Palette Relief
uses the final processed color palette as its grouping mechanism: all pixels of
one final RGB share one height and material-depth rule.

## Terminology

- **Two-Level Relief**: The existing `--relief` mode. One exact background RGB
  stays at `--color-height`; every other RGB receives the same additional
  `--relief-height`.
- **Palette Relief**: The proposed manifest-driven mode. Every non-background
  final RGB has its own explicit height.
- **Physical backing**: The full-footprint support plate spanning from
  `z = -base_height_mm` to `z = 0`.
- **Backing color**: The material assigned to the physical backing and to any
  backing-colored fill within Palette Relief sections.
- **Background color**: The final image RGB omitted from the editable section
  list and retained at the normal `color_height_mm` plane.
- **Section**: All processed pixels of one final RGB, including disconnected
  islands.
- **Component**: One connected island within a section.
- **Backing top**: The `z = 0` surface of the physical backing. Exact Palette
  Relief heights are measured upward from this plane.

## Existing Flag Ownership

Palette Relief adopts the existing meanings rather than redefining them:

| Setting | Responsibility |
| --- | --- |
| `--base-height` | Physical backing thickness |
| `--backing-color` | Physical backing material/color |
| `--backing-color auto` | Resolve backing material from the processed image |
| `--background-color` | Final image RGB kept at `--color-height` and excluded from manifest sections |
| `--color-height` | Background-color height above the backing top |
| `--relief-height` | Existing Two-Level Relief only |

Backing and background colors may be identical, but they are separate roles.
For a black-background image, a typical Palette Relief command will specify
both as black. With 1 mm defaults, black areas then have 2 mm total thickness:
1 mm of physical backing plus 1 mm of background-color geometry.

## Coordinate and Height Contract

The first schema version supports only explicit millimeter heights:

```json
{
  "height_mode": "exact",
  "height_reference": "backing_top",
  "unit": "mm"
}
```

For a section with `height_mm = 3.0`:

```text
section bottom = z 0.0
section top    = z 3.0
```

If the physical backing is 2 mm thick, the model spans `z = -2.0` through
`z = 3.0` at that section, for 5 mm total thickness. Changing backing thickness
does not change the section's declared height.

All section heights must be finite and strictly greater than zero. The
background color is not a manifest section; it always uses
`background.height_mm`, initially populated from `--color-height`.

The explicit height fields are recorded even though schema version 1 has only
one mode and reference. This prevents unit ambiguity and leaves a clean path to
future calculated modes without changing the meaning of version 1 files.

## Material-Depth Contract

Palette Relief supports two ways to divide a section between its own color and
the backing color. Names remain provisional until implementation review.

### `top_cap`

Only the topmost configured depth is made from the section color. Backing color
fills the section below it.

```text
section top
+--------------------+
| section color      | top_color_depth_mm
+--------------------+
| backing color fill |
+--------------------+
backing top (z = 0)
```

### `deep_color`

Backing color occupies a configured support depth immediately above the
physical backing. The section color fills the remainder through the top.

```text
section top
+--------------------+
| section color      |
|                    |
+--------------------+
| backing color fill | backing_support_depth_mm
+--------------------+
backing top (z = 0)
```

The initial default interface depth is 1 mm. The manifest records it rather
than embedding it as an undocumented constant. Section-level values are
explicit so future versions can vary the rule by color.

Validation must reject any combination that would create a zero-thickness or
negative-thickness colored volume. A future version may define intentional
omission semantics, but zero currently has no special meaning.

## Proposed CLI Workflow

### Inspect a processed coordinate

```powershell
python run_converter.py image.png --color-at 10,10 [palette options]
```

This is a read-only terminal action. It runs the normal image preprocessing
pipeline and reports the final processed RGB and hex value at the requested
coordinate. Coordinates are zero-based and originate at the original image's
top-left. The command fails if preprocessing removes the coordinate or the
resolved pixel is fully transparent.

The user is responsible for selecting a coordinate that remains meaningful
after cropping and other preprocessing.

### Select the physical backing by coordinate

```powershell
python run_converter.py image.png --backing-color-at 10,10 [palette options]
```

This resolves the physical backing material from the final processed color at
the coordinate. It is mutually exclusive with explicit `--backing-color` and
`--backing-color auto` selection.

It does not implicitly select the background color. A user can inspect with
`--color-at`, then pass the reported RGB to both `--backing-color` and
`--background-color` when the roles should match.

### Generate a manifest

```powershell
python run_converter.py image.png `
  --generate-relief-manifest `
  --background-color 0,0,0 `
  --backing-color 0,0,0 `
  [palette and preprocessing options]
```

An optional explicit output path is supported. The default is:

```text
{input_stem}.manifest.json
```

Manifest generation is a terminal action: it analyzes the image and writes the
manifest plus one reference image per editable section, but does not generate a
3MF. Every generated section initially has an unset height so the file cannot
accidentally be applied without editing. Reference images are named
`{input_stem}.section_NN.png`, use the complete processed canvas, fill all other
pixels with the selected background RGB, and retain only that section's exact
processed RGB. The processed canvas equals the source dimensions under default
settings; explicit crop or padding options change both reference images and
geometry consistently.

### Validate a manifest

```powershell
python run_converter.py `
  --validate-relief-manifest image.manifest.json
```

Validation reruns the frozen preprocessing recipe, verifies source and
processed fingerprints, validates every editable value, constructs provisional
geometry in memory, and reports errors and warnings. It does not write a 3MF.

### Apply a manifest

```powershell
python run_converter.py image.png `
  --relief-manifest image.manifest.json `
  --summary `
  --swatches `
  --quantized `
  --preview `
  --render
```

`--relief-manifest` activates Palette Relief. It is mutually exclusive with
the existing `--relief`, `--relief-height`, and conflicting palette-affecting
arguments.

## Output Artifact Contract

Output requests are independent:

| Flag | Artifact | Meaning |
| --- | --- | --- |
| `--summary` | `{stem}.summary.txt` | Final material and AMS assignment summary |
| `--swatches` | `{stem}_swatches.png` | Final exported materials |
| `--quantized` | `{stem}_quantized.png` | Pre-quantization processed pixels versus final quantized pixels |
| `--preview` | `{stem}_preview.png` | Final model pixels before filament mapping versus final filament colors |
| `--render` | `{stem}_render.png` | Shaded final geometry using final exported materials |

The 3MF always receives embedded thumbnails from the same final geometry used
by `--render`. The `.info.json` metadata sidecar continues to be attempted for
every successful conversion.

At present, `--preview` also causes applicable quantization and denoising
comparison images to be generated. Implementation will separate
`--quantized` from `--preview` while preserving an intentional compatibility
path for existing callers.

## Preprocessing and Reproducibility

Manifest sections describe the final processed palette, not necessarily the
original file palette. Generation occurs after all palette-affecting steps:

1. Load and RGBA conversion
2. Auto-crop
3. Padding
4. Image preprocessing filter
5. Quantization, including iterative quantization
6. Denoising
7. Disconnected-pixel trimming and final model-footprint filtering
8. Region/color analysis

Palette-affecting settings are frozen into the manifest. Applying or validating
the manifest replays that recipe. Conflicting CLI arguments are errors rather
than silent overrides.

Three fingerprints serve different purposes:

- `source.sha256` detects changes to the input file.
- `processed.pixel_sha256` detects any change in final dimensions, layout,
  transparency, or final per-pixel RGB values.
- `processed.palette_sha256` detects changes to the canonical color/count
  table and remains useful in diagnostics when the layout alone changed.

The processed pixel fingerprint is authoritative for application. Matching
only the same colors and counts is insufficient because a different layout
would create different geometry.

## Manifest Schema Direction

The implemented version 1 format is JSON and fails closed on unsupported
`schema_version` or `mode` values. Its current top-level groups are `source`,
`processing`, `model`, `processed_image`, and `sections`. Generate a manifest
with the CLI to obtain the authoritative editable shape; validation rejects
missing, duplicate, stale, or structurally incompatible content.

The example below documents the richer target metadata vocabulary. Fields such
as raw-source palette tables, bounding boxes, catalog delta-E values, generator
timestamps, and nested processing groups are reserved for later compatible
schema work and are not currently emitted or accepted as substitutes for the
implemented required fields.

```json
{
  "schema": "pixel-to-3mf.palette-relief",
  "schema_version": 1,
  "generator": {
    "application": "pixel-to-3mf",
    "version": "1.0.0",
    "generated_at": "2026-10-08T18:30:00-04:00"
  },
  "source": {
    "filename": "pacman.png",
    "path": "E:\\art\\pacman.png",
    "sha256": "...",
    "width_px": 224,
    "height_px": 264,
    "mode": "RGBA",
    "visible_pixel_count": 38104,
    "color_count": 10,
    "palette_sha256": "...",
    "palette": [
      {
        "rgb": [0, 0, 0],
        "hex": "#000000",
        "pixel_count": 24500
      }
    ]
  },
  "processing": {
    "auto_crop": false,
    "padding": {
      "size_px": 0,
      "color_rgb": [255, 255, 255],
      "type": "circular"
    },
    "preprocess_filter": {
      "name": null,
      "size": 3
    },
    "quantization": {
      "enabled": true,
      "algorithm": "none",
      "requested_colors": 10,
      "iterate": false,
      "resolved_colors": 10
    },
    "denoise": {
      "minimum_blob_size_px": 0
    },
    "connectivity": 8,
    "trim_disconnected": false
  },
  "processed": {
    "width_px": 224,
    "height_px": 264,
    "visible_pixel_count": 38104,
    "final_color_count": 10,
    "pixel_sha256": "...",
    "palette_sha256": "..."
  },
  "backing": {
    "height_mm": 1.0,
    "selection_mode": "explicit",
    "requested_rgb": [0, 0, 0],
    "resolved_rgb": [0, 0, 0],
    "source_coordinate": null,
    "material": {
      "mode": "filament",
      "name": "Bambu Lab PLA Basic Black",
      "manufacturer": "Bambu Lab",
      "filament_type": "PLA",
      "finish": "Basic",
      "matched_rgb": [0, 0, 0],
      "hex": "#000000"
    }
  },
  "background": {
    "rgb": [0, 0, 0],
    "hex": "#000000",
    "pixel_count": 24500,
    "component_count": 1,
    "height_mm": 1.0
  },
  "height_contract": {
    "height_mode": "exact",
    "height_reference": "backing_top",
    "unit": "mm"
  },
  "material_contract": {
    "default_color_depth_mode": "top_cap",
    "default_interface_depth_mm": 1.0
  },
  "sections": [
    {
      "section_number": 1,
      "section_name": "image.section_01",
      "section_image": "image.section_01.png",
      "color": {
        "rgb": [255, 87, 87],
        "hex": "#FF5757"
      },
      "pixel_count": 4872,
      "pixel_fraction": 0.12786,
      "component_count": 18,
      "bounding_box_px": {
        "left": 4,
        "top": 6,
        "right": 219,
        "bottom": 258
      },
      "pre_quantization_colors": [
        {
          "rgb": [250, 80, 82],
          "hex": "#fa5052",
          "pixel_count": 3102
        },
        {
          "rgb": [255, 92, 90],
          "hex": "#ff5c5a",
          "pixel_count": 1770
        }
      ],
      "material": {
        "mode": "filament",
        "name": "Bambu Lab PLA Basic Red",
        "manufacturer": "Bambu Lab",
        "filament_type": "PLA",
        "finish": "Basic",
        "matched_rgb": [255, 52, 48],
        "hex": "#ff3430",
        "delta_e": 3.14
      },
      "height_mm": null,
      "color_depth_mode": "top_cap",
      "interface_depth_mm": 1.0
    }
  ]
}
```

### Original and pre-quantization color information

In the richer target schema, `source.palette` records the raw loaded image's visible RGB population before
crop, padding, filtering, or quantization. Each section's
`pre_quantization_colors` is already implemented and records the aligned color
population immediately before quantization. This distinction matters because padding and filters can
introduce colors that did not occur in the raw source.

The section contribution list is a cross-tabulation, not necessarily a
one-to-one mapping. With dithering or filtering, one earlier RGB may contribute
pixels to several final colors, and one final color may receive pixels from
several earlier colors. Pixel counts make the relationship explicit without
claiming a false single-color mapping. Generated padding pixels must be
identified as generated rather than falsely attributed to a raw source color.

### Filament information

Material information records the final mapping used by the requested color
mode. In filament mode it includes the matched catalog record and RGB. In hex,
CSS-color, or generated-name modes, non-applicable filament fields are `null`
or omitted according to the finalized typed schema.

Material metadata is informative during editing but is revalidated during
application. A catalog/filter change must not silently substitute a different
material while claiming full reproducibility.

## Field Ownership and Editability

Version 1 intentionally limits normal manual edits.

| Field group | User editable? | Rule |
| --- | --- | --- |
| `sections[].height_mm` | Yes | Required finite value greater than zero |
| `sections[].color_depth_mode` | Yes | Supported enum only |
| `sections[].interface_depth_mm` | Yes | Required positive value compatible with section height |
| Source and fingerprints | No | Regenerated from authoritative inputs |
| RGB, rank, counts, bounds, components | No | Derived from processed pixels |
| Backing/background resolution | No | Derived from generation command |
| Material matches | No initially | Future remapping feature |

Manual changes to derived fields are detected by validation. A future schema
may support explicit color or filament remapping without overloading version 1
height fields.

## Section Ordering and Identity

Sections are ordered by descending final pixel count. Ties are resolved by RGB
tuple order to make generation deterministic. `section_number` is the stable
position within that generated manifest, while `section_name` and
`section_image` combine the source stem with that zero-padded number. RGB
remains the authoritative geometry color key in schema version 1. Regenerating
after changing the processed palette may legitimately renumber sections.

The background RGB is omitted from `sections`, so an image with ten final
colors produces nine editable sections when exactly one color is selected as
background.

## Validation Contract

Validation has four stages.

### 1. Schema validation

Errors include:

- Unknown schema or unsupported version
- Missing required objects or fields
- Wrong JSON types
- Duplicate section IDs or RGB values
- Invalid RGB channels
- Unknown enum values
- Nonfinite, zero, or negative heights
- Missing editable height values
- Interface depths incompatible with total section height

### 2. Source and preprocessing validation

Errors include:

- Missing source image
- Source hash mismatch
- Preprocessing recipe cannot be replayed
- Processed pixel hash mismatch
- Processed palette hash mismatch
- Final image dimensions differ
- Background color is absent from final visible pixels
- Missing manifest section for a final non-background RGB
- Extra manifest section not present in final pixels
- Pixel or component counts differ

### 3. Material validation

Errors include:

- Backing material cannot be resolved
- Section material cannot be resolved under frozen filters
- Two manifest entries conflict over one final RGB
- Required backing-colored fill has no backing material assignment

Warnings may be used when a catalog record's descriptive metadata changed but
its stable identity and RGB remain valid. The implementation should introduce
a stable filament identifier if the color-tools API provides one.

### 4. Geometry validation

Validation constructs the planned meshes in memory and checks:

- Every requested material volume is nonempty
- No zero-area or repeated-index triangles
- No zero-thickness volume
- All triangle indices are valid
- Expected Z extents match the manifest
- Meshes are manifold where the selected geometry path promises manifoldness
- Component aggregation preserves every final model pixel
- Backing fill and color volume partition each section without gaps or overlap
  except shared boundary faces required by the multi-object export contract

Validation reports errors separately from printability warnings.

Suggested warnings include:

- A material depth below configured nozzle line width or known layer height
- Height differences likely to disappear after layer quantization
- Very small disconnected components
- Large numbers of disconnected components in one logical color object
- Use of partially transparent pixels, which currently become full geometry
- Optimized triangulation falling back to the per-pixel path

Successful validation prints the resolved palette, heights, material-depth
modes, total Z range, object count, component count, and final material count.

## Geometry and Object Model

### Initial object grouping

The initial implementation targets one logical 3MF object per final section
color, plus backing-colored objects needed by the material-depth rules. Meshes
for disconnected components of the same color are concatenated into one mesh
object without inventing visible geometry between them.

A 3MF mesh may contain disconnected components. This should produce one
object-level material assignment in slicers that honor the 3MF object model.
The behavior must be tested in Bambu Studio with many small islands such as the
white dots in the Ms. Pac-Man example.

### Micro-connectors

Micro-connectors are explicitly deferred from the first implementation. They
may be introduced only if target slicers split disconnected components despite
their shared 3MF object.

Before implementation, the existing connector solution from the user's other
projects must be reviewed. Any connector design must declare:

- Placement plane and routing strategy
- Width, height, and material
- Interaction with backing fill and differing section heights
- Manifold guarantees
- Slicer-resolution assumptions
- Whether connector removal is required or merely acceptable

The design must not depend on every slicer silently deleting geometry below an
unspecified threshold.

### Material partitioning

Every section is partitioned vertically according to its material-depth mode.
The color and backing-colored portions are separate material objects but share
the same XY footprint and an exact horizontal boundary.

All backing-colored portions should be aggregated where safely possible so the
slicer does not receive hundreds of redundant backing-material objects.
Likewise, every visible final RGB should normally appear once in the object
list even when it has many disconnected components.

## Interaction With Existing Modes

- Existing Two-Level Relief remains available through `--relief` with no
  behavioral change.
- Palette Relief is activated only with `--relief-manifest`.
- The two modes are mutually exclusive.
- Standard, optimized, and smoothed geometry paths must consume the same
  resolved section plan rather than independently interpreting the manifest.
- Solid-core behavior requires a separate compatibility decision before being
  enabled with Palette Relief; it must not be inferred from current
  Two-Level Relief shell behavior.
- `--no-backing-plate` is initially incompatible because Palette Relief's
  height and material contracts explicitly reference a physical backing top.
  Supporting it later requires a defined replacement reference plane.

## Separation of Concerns

The implementation should preserve these ownership boundaries:

- Image preprocessing owns final pixels and source-to-final color contribution
  analysis.
- Manifest generation owns serialization of the frozen recipe and derived
  palette facts.
- Manifest parsing owns schema and type validation, with no mesh imports.
- Relief planning owns conversion of a valid manifest into material/Z spans.
- Geometry builders own mesh construction from explicit XY footprints and Z
  spans; they do not read JSON.
- The 3MF writer owns object/material packaging, not height interpretation.
- The shared preview renderer consumes finalized colored meshes and does not
  interpret manifest semantics.
- CLI orchestration owns mutually exclusive actions and output requests.

A single typed intermediate `PaletteReliefPlan` should be the contract between
validated manifest data and geometry generation. This avoids duplicating height
and material logic across per-pixel, optimized, smoothed, rendering, and 3MF
paths.

## Compatibility and Migration

The new format does not replace `.info.json`, `.summary.txt`, or batch Markdown
summaries:

- `.manifest.json` is an editable Palette Relief recipe for one source image.
- `.section_NN.png` files are derived, full-canvas visual references for its
  editable color sections.
- `.info.json` is a generated description of an already-created 3MF.
- `.summary.txt` is a human-readable material/AMS report.
- `batch_summary_*.md` describes a batch conversion run.

The README currently describes intermediate preview generation as part of
`--preview`. Documentation and tests must be updated when independent
`--quantized` output is introduced. A compatibility policy must be selected:
either retain the old additional outputs under `--preview` for a deprecation
period or make the separation in a documented breaking release.

## Resolved Version 1 Decisions

1. The schema enum names are `top_cap` and `deep_color`.
2. `height_mm` must be strictly greater than `interface_depth_mm`; both material
   volumes must have positive height.
3. Manifest generation records the configured color/filament match when it is
   available, while exact processed RGB remains authoritative.
4. `--quantized` independently requests the quantization comparison.
   `--preview` temporarily retains its historical quantized and denoised
   comparisons for compatibility.
5. Palette Relief version 1 rejects solid-core, optimized, smoothed, and
   missing/zero physical backing configurations.
6. Disconnected same-color shells are aggregated into one 3MF mesh object.
   Micro-connectors remain deferred until slicer acceptance testing proves they
   are needed.
7. `--generate-relief-manifest` accepts an optional output path and defaults to
   `{image_stem}.manifest.json`. It also writes one full-canvas
   `{image_stem}.section_NN.png` reference for each non-background section.

The remaining external acceptance item is verifying how each supported slicer
presents disconnected shells contained in one 3MF mesh object.

## Testing Strategy

### Manifest tests

- Deterministic generation and ordering
- Stable section numbering, names, and image filenames
- Full-canvas section-image dimensions, orientation, background fill, and exact
  per-section pixels
- Ten final colors plus one background produces nine sections
- Exact raw, pre-quantization, and final color population counts
- Round-trip JSON parsing
- Unsupported schema/version rejection
- Missing, extra, duplicate, and modified sections
- Source, processed-pixel, and palette fingerprint mismatches
- NaN, infinity, zero, negative, and missing heights
- Invalid material-depth combinations

### Coordinate tests

- Top-left zero-based coordinate convention
- Transparent coordinate rejection
- Cropped-away coordinate rejection
- Quantized color reporting
- Explicit, automatic, and coordinate-selected backing modes
- Mutual exclusivity of backing selectors

### Geometry tests

- Exact Z extents for every section
- Background remains at configured color height
- Physical backing retains configured thickness and color
- `top_cap` volume partition
- `deep_color` volume partition
- Multiple disconnected components aggregate into one logical color object
- No missing pixels, duplicate material volume, or degenerate triangles
- Standard and optimized paths produce equivalent bounds and materials
- Final render visibly represents differing heights and material depths

### Output tests

- `--quantized` produces only the quantization comparison it owns
- `--preview` produces the filament-mapping comparison it owns
- Combined output flags generate all requested artifacts
- Summary, swatches, render, embedded thumbnails, and `.info.json` agree on
  final materials
- Bambu Studio acceptance test for disconnected components in one object

## Proposed Implementation Sequence

1. Approve this contract and finalize provisional enum names.
2. Add typed manifest models, canonical hashing, and JSON round-trip tests.
3. Add `--color-at` and backing coordinate resolution.
4. Add manifest generation after the authoritative preprocessing pipeline.
5. Add validation through schema, replay, material, and dry-run geometry stages.
6. Introduce the typed Palette Relief plan and Z/material partitioning.
7. Adapt standard geometry, then optimized and smoothed paths to that plan.
8. Aggregate disconnected same-color components into logical 3MF objects.
9. Integrate summary, swatches, preview, quantized comparison, render, and
   embedded thumbnail outputs.
10. Validate real models in Bambu Studio before considering connectors.
11. Document the CLI and remove any stale claims about output ownership.

Each stage should land with focused tests before the next stage begins. No
micro-connectors, arbitrary area grouping, color remapping, filament remapping,
or LayerForge process integration belong in the first implementation.

## Deferred Capabilities

- Calculated heights based on luminance, rank, or formulas
- Height references other than `backing_top`
- Intentional zero-height or omitted sections
- User-editable RGB/color remapping
- User-editable filament remapping
- Multiple independently controlled objects within one source image
- LayerForge orchestration
- Micro-connectors
- Automatic semantic foreground/background recognition
- Gradient or continuous heightmaps

These are expected directions, but schema version 1 must remain a small,
deterministic contract centered on explicit per-color heights.
