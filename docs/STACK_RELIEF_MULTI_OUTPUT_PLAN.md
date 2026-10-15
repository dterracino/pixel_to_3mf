# Stack Relief Multi-Output Plan

## Status

Planning draft for the next Stack Relief phase. This document records the
agreed behavioral contracts and the remaining design choices. It does not
change the current manifest schema, editor, geometry generation, or export
behavior.

Implementation should not begin until the unresolved decisions in this
document have been reviewed.

## Purpose

The Stack Relief editor defines several independently extruded selections
against one processed source image. Some selections may need to print as
separate pieces for later physical assembly. The current converter produces
one 3MF from one processed image, so the manifest needs an additional concept
that partitions stacks into coordinated 3MF outputs without losing their
shared spatial relationship.

The reference workflow is an Ms. Pac-Man image:

- The maze and dots remain attached to a full backing plate.
- Ghosts are peeled into a separate 3MF so they can be printed independently.
- The backing plate remains solid underneath the original ghost locations.
- The detached ghost geometry retains its intended internal X/Y/Z alignment.
- Each 3MF remains one slicer assembly containing separately colorable mesh
  objects.

This feature is output partitioning, not automatic part packing and not a new
geometry-authoring system.

## Terminology

- **Stack**: A saved pixel selection plus its total stack height and top-color
  height. The remaining depth is filled with the configured background color.
- **Output**: A named collection of stacks written to one 3MF file.
- **Backing output**: The one output that receives the full physical backing
  plate. It is absent when backing is disabled.
- **Detached output**: Any output that does not receive the backing plate.
- **Mesh object**: One geometry object produced by the existing mesh-building
  and material-grouping rules. A mesh object may contain disconnected closed
  shells.
- **Component**: A 3MF component reference to one mesh object.
- **Assembly container**: The single 3MF object that references all components
  belonging to an output.
- **Build item**: The top-level printable item in the 3MF `<build>` section.
- **Assembly view**: A preview of every output restored to its intended
  position relative to the source image and backing plate.
- **Output view**: A preview of exactly one generated 3MF.

## Confirmed Contracts

### Stack ownership

- Every saved stack belongs to exactly one output.
- An output may contain any number of stacks and any number of disconnected
  physical pieces.
- A stack is not duplicated across outputs in the initial implementation.
- Moving a stack changes only which 3MF receives its above-backing geometry.
  It does not alter the stack's selection or height recipe.

### Backing ownership

- At most one output receives a physical backing plate.
- When backing is enabled, `backing_output_id` identifies that output.
- When backing is disabled, `backing_output_id` is null.
- The backing output always receives the complete original processed-image
  backing footprint.
- Moving stacks to detached outputs must not remove, recess, or cut holes in
  the backing plate beneath their original positions.
- Detached outputs do not receive partial, cropped, or stack-shaped backing
  plates.

For a 2 mm backing and a ghost stack containing 2 mm of background fill plus
1 mm of visible color, the logical assembled cross-section is:

```text
z = 5 mm  +-----------------------+
          | ghost color, 1 mm     |  detached stack
z = 4 mm  +-----------------------+
          | background fill, 2 mm|  detached stack
z = 2 mm  +-----------------------+
          | backing plate, 2 mm   |  backing output
z = 0 mm  +-----------------------+
```

The base 3MF contains the full backing through this location but no ghost
geometry above it. The ghost 3MF contains the complete 3 mm ghost stack.

### Spatial positioning

- Stack geometry continues to use one shared source-image coordinate system.
- Relative X/Y/Z placement among objects in an output must never change.
- An output may receive one common translation to place the assembly near the
  print-bed origin.
- That translation applies to the output assembly as a whole, not separately
  to its child objects.
- Automatic nesting, rotation, or packing is out of scope.
- An assembly preview restores outputs to their source-relative positions and
  displays detached stacks on the backing top.

### 3MF packaging

Every generated 3MF must preserve the existing container pattern:

```text
3MF output
└── one build item
    └── one assembly container
        ├── component: mesh object 1
        ├── component: mesh object 2
        └── component: mesh object N
```

- Color/material geometry remains in individual mesh objects according to the
  existing geometry aggregation rules.
- All mesh objects are referenced as components of one assembly container.
- The `<build>` section contains exactly one item referencing that container.
- Child objects must not become independent top-level build items. Slicers can
  otherwise auto-drop them to the bed and destroy their intended Z placement.
- Geometry must not be collapsed into one indiscriminate mesh because color
  objects need to remain independently assignable in the slicer.
- This phase does not introduce micro-connectors or change connectivity rules.

## Proposed Manifest Shape

The initial schema proposal adds a top-level `outputs` collection and an
optional `backing_output_id`:

```json
{
  "schema_version": 3,
  "mode": "stack_relief",
  "model": {
    "units": "mm",
    "background_color": [0, 0, 0],
    "backing_color": [0, 0, 0],
    "backing_height_mm": 2.0
  },
  "backing_output_id": "output_base",
  "outputs": [
    {
      "output_id": "output_base",
      "output_name": "Main board",
      "file_name": "ms-pac-man-base.3mf",
      "stack_ids": ["stack_maze", "stack_border", "stack_dots"]
    },
    {
      "output_id": "output_ghosts",
      "output_name": "Ghost pieces",
      "file_name": "ms-pac-man-ghosts.3mf",
      "stack_ids": ["stack_red_ghost", "stack_pink_ghost"]
    }
  ],
  "stacks": [
    "existing stack definitions omitted from this example"
  ]
}
```

`outputs`, `backing_output_id`, and the version number remain proposed until
implementation review. In particular, the file-name field may be narrowed to
a safe file stem so manifests cannot write outside the selected destination.

### Backward compatibility

An older Stack Relief manifest without `outputs` should load as one implicit
output containing every stack. If backing is enabled, that implicit output is
the backing output. Saving from the updated editor may upgrade the manifest to
the new explicit schema version.

The legacy single-output command-line workflow must continue to produce the
same geometry and 3MF assembly structure.

## Geometry Compilation

Multi-output compilation should filter the validated stack plan rather than
reimplement stack geometry:

1. Validate the complete manifest and exclusive stack ownership.
2. Compile each stack's background-fill and source-color material spans using
   the existing Stack Relief plan.
3. Partition those spans by output membership.
4. Add the complete backing mesh only to the designated backing output.
5. Build material/color mesh objects with the existing production mesh path.
6. Package each output's mesh objects into one 3MF assembly container.

The production geometry used for the 3MF, standalone render, and embedded
thumbnails must remain the same authoritative finalized mesh set.

No detached-output code may derive the backing footprint from that output's
stack pixels. The backing footprint belongs to the processed source and is
independent of output assignment.

## Editor Workflow

The editor should always contain at least one output. New manifests begin with
a default output that owns all newly created stacks and, when enabled, the
backing plate.

The proposed UI includes:

- An **Outputs** list with New, Rename, and Delete commands.
- A visible indication of the backing output.
- A command to make the selected output the backing output.
- An output assignment control for the selected stack.
- Stack-list filtering or highlighting by selected output.
- Counts showing stacks assigned to each output.
- **Preview Complete Assembly** and **Preview Selected Output** commands.

Deleting a non-empty output should not silently delete its stacks. The safest
initial behavior is to block deletion until its stacks have been reassigned.
Deleting the backing output should likewise require selecting another backing
output or explicitly disabling backing.

Creating, renaming, deleting, or reassigning outputs marks the manifest dirty.
The existing create/resume and source-fingerprint protections remain in force.

## Preview Contract

### Complete assembly preview

- Shows the full backing plate once, when enabled.
- Shows every stack at its source-relative X/Y position.
- Places all stack geometry relative to the backing top.
- Uses distinct output visibility controls so fit and assembly relationships
  can be inspected.
- Does not apply print-bed packing.

### Selected output preview

- Shows exactly the finalized meshes intended for that output's 3MF.
- Includes the backing only for the backing output.
- Applies the same common output transform used by export, or an equivalent
  camera framing that preserves all relative coordinates.
- Uses the shared interactive renderer and production mesh path.

## Artifact Naming and Scope

Each output necessarily receives its own 3MF and geometry-derived render and
embedded thumbnails. Summary, swatch, preview, quantization, and metadata
scope needs an explicit decision because not every artifact naturally belongs
to an output:

| Artifact | Proposed scope | Status |
| --- | --- | --- |
| `.3mf` | One per output | Confirmed |
| Embedded thumbnails | One set per output 3MF | Confirmed |
| `_render.png` | One per output; optional complete-assembly render | Proposed |
| `.summary.txt` | One per output | Proposed |
| `_swatches.png` | One per output | Proposed |
| `_quantized.png` | Once per source/manifest | Proposed |
| `_preview.png` | Undecided: source-level or output-level filament comparison | Open |
| `.info.json` | One per output, with manifest/output identity | Proposed |

Explicit output names must be unique after case folding and filename
normalization. Derived artifacts should use the resolved output stem to avoid
collisions.

## Material and AMS Assignment

The assembled result normally needs consistent real-world colors across
several files. A promising policy is:

- Resolve color-to-filament matching once for the complete manifest.
- Reuse the resolved filament identity for the same RGB in every output.
- Allow numerical AMS slot assignments to be output-local because each 3MF
  may contain a different subset of materials.

This policy is not yet approved. It must be settled before summaries,
swatches, and output-specific previews are finalized.

## Validation Requirements

Static manifest validation must reject:

- Missing, empty, or duplicate output IDs.
- Empty or invalid output names.
- Duplicate or unsafe resolved filenames.
- References to unknown stack IDs.
- A stack assigned to no output.
- A stack assigned to more than one output.
- Empty outputs at final export time. Draft saves may warn instead.
- A `backing_output_id` that does not identify an output.
- A non-null backing output when backing is disabled, unless the schema
  deliberately treats it as dormant configuration.
- Enabled backing without a backing output.

Geometry validation must run independently for every output and report the
output name in each error. Complete-manifest validation must also verify that
the backing output contains the unchanged processed-image backing footprint.

## Test and Acceptance Plan

### Manifest tests

- Round-trip multiple outputs and stack assignments.
- Migrate a current single-output manifest to one implicit/default output.
- Reject missing, duplicate, and multiply assigned stacks.
- Preserve stack selections and height settings when reassigned.
- Preserve source and processed-image fingerprint validation.

### Geometry tests

- Moving a stack changes only its destination output.
- The backing mesh is byte-for-byte or geometrically equivalent before and
  after a stack is detached.
- Detached stack background fill and visible color retain their declared
  thicknesses.
- Output-wide translation preserves every pairwise component displacement.
- No detached output accidentally receives backing geometry.

### 3MF archive tests

For every generated output:

- The archive contains exactly one top-level `<build><item>`.
- That build item references the assembly container.
- The container has one component per finalized mesh object.
- Mesh/color objects remain present and independently named/assignable.
- Component transforms preserve their expected relative X/Y/Z placement.
- No child mesh object appears as an independent build item.
- Embedded thumbnails are derived from that output's finalized meshes.

### Workflow regression tests

- Current non-manifest conversion remains unchanged.
- Current single-output Stack Relief application remains unchanged.
- Create and resume preserve output assignments.
- Draft manifests may be saved with incomplete stack or output assignment,
  with clear warnings; final validation/export remains strict.
- `--summary`, `--swatches`, `--render`, and other selected artifacts use
  collision-free names for every output.

### Manual slicer acceptance

Automated XML checks are necessary but insufficient. At least one generated
multi-output fixture must be opened in the supported slicer and checked for:

- One assembly in the object list per 3MF.
- Separately colorable child objects.
- No child object auto-dropped independently to the bed.
- Correct relative Z placement between background-fill and visible-color
  objects.
- An intact backing beneath peeled-off stack locations in the base output.

The Ms. Pac-Man backing/ghost workflow should be the primary acceptance
fixture.

## Out of Scope for the Initial Phase

- Automatic part packing or nesting.
- Independent rotation of detached parts.
- Duplicate stacks appearing in several outputs.
- Multiple backing plates.
- Per-output backing footprints.
- Recesses, sockets, registration pins, snap fits, or glue clearances.
- Micro-connectors between disconnected shells.
- Changing current connectivity or material aggregation behavior.
- Slicer project configuration beyond the existing 3MF writer contract.

## Open Decisions

The following choices should be resolved before implementation:

1. Whether output filenames are stored as complete safe filenames or file
   stems from which `.3mf` and sidecars are derived.
2. How `--output some-name.3mf` interacts with several manifest outputs.
3. Whether draft manifests may contain temporarily unassigned stacks or empty
   outputs, and how the editor displays those states.
4. Whether material matching is global while AMS slot numbering is local to
   each output.
5. Whether `--render` produces only per-output renders or also one assembled
   overview.
6. Whether `--preview` is source-level, output-level, or both.
7. The exact common X/Y/Z transform used to place a detached assembly on the
   print bed without altering child transforms.
8. Whether the GUI needs output visibility toggles in the first implementation
   or can begin with selected-output and complete-assembly preview commands.

## Implementation Boundaries

Separation of concerns should remain explicit:

- `stack_manifest.py` owns schema, parsing, and validation.
- The Qt editor owns output authoring interactions, not geometry rules.
- `stack_plan.py` owns stack-to-material-span compilation.
- A new output-planning layer should partition compiled spans and define
  assembly-level transforms.
- Existing mesh builders own mesh generation.
- Existing 3MF writer code owns container/component/build packaging.
- The shared renderer consumes finalized colored meshes and does not decide
  output membership.

The implementation should extend these boundaries rather than teaching the
editor, renderer, or low-level 3MF writer about manifest-specific selection
semantics.
