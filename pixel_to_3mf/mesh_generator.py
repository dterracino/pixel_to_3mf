"""
Mesh generation module for creating 3D geometry from 2D regions.

This is where we go from flat pixel art to actual 3D meshes! We take
regions (connected blobs of pixels) and extrude them upward into solid
geometry. We also create the backing plate that goes underneath everything.

The geometry is stored as vertices (3D points) and triangles (3 vertex
indices each). This is the universal format for 3D meshes - STL, OBJ,
3MF all use this approach! 🎲
"""

from typing import List, Tuple, Set, Dict, TYPE_CHECKING
from .region_merger import Region
from .image_processor import PixelData
from .mesh import Mesh  # noqa: F401  (re-exported for backwards compatibility)

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig

# ============================================================================
# Feature flag for optimized mesh generation
# ============================================================================
# When True, uses rectangle merging for significant reduction in vertex/triangle
# counts (30-70% typical) with guaranteed manifold meshes (0 non-manifold edges).
# When False, uses original per-pixel mesh generation. Both produce manifold
# meshes with identical visual results.
USE_OPTIMIZED_MESH_GENERATION = False

# Try to import optimized functions
try:
    from .rectangle_optimizer import (
        optimize_region_rectangles as generate_region_mesh_optimized,
        generate_backing_plate_optimized
    )
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False




def _corner_key(
    x: int, y: int, cx: int, cy: int,
    region_pixels: Set[Tuple[int, int]]
) -> tuple:
    """
    Return the vertex map key for corner (cx, cy) of pixel (x, y).

    Normally adjacent pixels share corner vertices (key = (cx, cy)).  But at a
    "saddle" corner — where two region pixels are connected only diagonally and
    neither edge-adjacent pixel at that corner is in the region — sharing the
    vertex produces 4 wall triangles on the same vertical edge, which is
    non-manifold.  In that case we return a unique per-pixel key so each pixel
    owns its own copy of the corner vertex.

    Saddle condition (for a given corner of pixel (x, y)):
        diagonal_pixel  IN region_pixels
        AND edge_adj_1  NOT IN region_pixels
        AND edge_adj_2  NOT IN region_pixels

    This supersedes the old coarse "diagonal_only_pixels" check, which only
    caught pixels with *no* edge-connected neighbours at all and missed the
    common case where both pixels are edge-connected to the region via other
    paths but still meet only diagonally at a specific corner.
    """
    if cx == x and cy == y:            # bottom-left corner
        diagonal, adj1, adj2 = (x - 1, y - 1), (x - 1, y), (x, y - 1)
    elif cx == x + 1 and cy == y:      # bottom-right corner
        diagonal, adj1, adj2 = (x + 1, y - 1), (x + 1, y), (x, y - 1)
    elif cx == x and cy == y + 1:      # top-left corner
        diagonal, adj1, adj2 = (x - 1, y + 1), (x - 1, y), (x, y + 1)
    else:                              # top-right corner: (x+1, y+1)
        diagonal, adj1, adj2 = (x + 1, y + 1), (x + 1, y), (x, y + 1)

    if (diagonal in region_pixels
            and adj1 not in region_pixels
            and adj2 not in region_pixels):
        return (x, y, cx, cy)   # unique per-pixel key — saddle corner
    return (cx, cy)             # shared key — normal corner


def _generate_region_mesh_original(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Original per-pixel mesh generation implementation.

    Generates a manifold mesh by extruding each pixel upward and stitching
    the top face, bottom face, and perimeter walls together.

    Corner vertices are shared between adjacent pixels by default.  The one
    exception is "saddle" corners — where two region pixels meet only
    diagonally (no edge-adjacent pixel in the region bridges them) — where
    sharing a vertex would cause four wall triangles to share a single
    vertical edge, which is non-manifold.  _corner_key() detects this and
    returns a unique per-pixel key for those corners.

    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        config: ConversionConfig object with layer height and other parameters

    Returns:
        A Mesh object ready for export to 3MF
    """
    region_pixels = region.pixels
    ps = pixel_data.pixel_size_mm

    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []

    # ========================================================================
    # Pass 1: Find perimeter pixels (needed for wall generation)
    # ========================================================================
    perimeter_pixels: Set[Tuple[int, int]] = set()
    for x, y in region_pixels:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in region_pixels:
                perimeter_pixels.add((x, y))
                break

    # ========================================================================
    # Pass 2: Generate top face  (z = config.color_height_mm)
    # ========================================================================
    top_vertex_map: Dict[tuple, int] = {}

    for x, y in region_pixels:
        corner_indices = []
        for cx, cy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
            key = _corner_key(x, y, cx, cy, region_pixels)
            if key not in top_vertex_map:
                top_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, config.color_height_mm))
            corner_indices.append(top_vertex_map[key])

        bl, br, tl, tr = corner_indices
        triangles.append((bl, br, tl))
        triangles.append((br, tr, tl))

    # ========================================================================
    # Pass 3: Generate bottom face  (z = config.color_layer_z_bottom)
    # ========================================================================
    bottom_vertex_map: Dict[tuple, int] = {}

    for x, y in region_pixels:
        corner_indices = []
        for cx, cy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
            key = _corner_key(x, y, cx, cy, region_pixels)
            if key not in bottom_vertex_map:
                bottom_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, config.color_layer_z_bottom))
            corner_indices.append(bottom_vertex_map[key])

        bl, br, tl, tr = corner_indices
        triangles.append((bl, tl, br))
        triangles.append((br, tl, tr))

    # ========================================================================
    # Pass 4: Generate walls for perimeter pixels
    # ========================================================================
    for x, y in perimeter_pixels:
        edges = [
            ((x,     y),     (x + 1, y),     "bottom"),
            ((x + 1, y),     (x + 1, y + 1), "right"),
            ((x + 1, y + 1), (x,     y + 1), "top"),
            ((x,     y + 1), (x,     y),     "left"),
        ]

        for (x1, y1), (x2, y2), edge_name in edges:
            if edge_name == "bottom":
                neighbor = (x,     y - 1)
            elif edge_name == "right":
                neighbor = (x + 1, y)
            elif edge_name == "top":
                neighbor = (x,     y + 1)
            else:
                neighbor = (x - 1, y)

            if neighbor in region_pixels:
                continue

            # Look up the two corner vertices that bound this wall edge.
            # _corner_key() returns the same key that was used during the
            # face-generation passes above, so these lookups always succeed.
            c1_key = _corner_key(x, y, x1, y1, region_pixels)
            c2_key = _corner_key(x, y, x2, y2, region_pixels)

            idx_bl = bottom_vertex_map[c1_key]
            idx_br = bottom_vertex_map[c2_key]
            idx_tl = top_vertex_map[c1_key]
            idx_tr = top_vertex_map[c2_key]

            triangles.append((idx_bl, idx_br, idx_tl))
            triangles.append((idx_br, idx_tr, idx_tl))

    return Mesh(vertices=vertices, triangles=triangles)


def _is_simple_rectangle(pixel_data: PixelData) -> bool:
    """
    Check if all pixels form a complete rectangle (no transparency).

    A simple rectangle allows a much more efficient slab mesh (8 vertices, 12 triangles)
    instead of per-pixel geometry tracing.
    """
    return pixel_data.width * pixel_data.height == len(pixel_data.pixels)


def _generate_slab_mesh(pixel_data: PixelData, z_bottom: float, z_top: float) -> Mesh:
    """
    Generate a solid slab between two arbitrary Z coordinates.

    This is the single implementation used by both generate_backing_plate and
    generate_solid_core. It matches the full non-transparent pixel footprint of
    the model — identical shape logic, different Z range.

    Fast path: if the image has no transparency (simple rectangle), produces
    a minimal 8-vertex / 12-triangle box.  Otherwise traces per-pixel geometry
    for sprites with holes or irregular outlines.

    Args:
        pixel_data: Model footprint — only non-transparent pixels are included
        z_bottom: Z coordinate of the bottom face
        z_top: Z coordinate of the top face

    Returns:
        A manifold Mesh object ready for 3MF export
    """
    # ------------------------------------------------------------------ fast path
    if _is_simple_rectangle(pixel_data):
        w = pixel_data.width * pixel_data.pixel_size_mm
        h = pixel_data.height * pixel_data.pixel_size_mm
        vertices: List[Tuple[float, float, float]] = [
            (0, 0, z_bottom), (w, 0, z_bottom), (w, h, z_bottom), (0, h, z_bottom),
            (0, 0, z_top),    (w, 0, z_top),    (w, h, z_top),    (0, h, z_top),
        ]
        triangles: List[Tuple[int, int, int]] = [
            (0, 2, 1), (0, 3, 2),          # bottom face
            (4, 5, 6), (4, 6, 7),          # top face
            (0, 1, 5), (0, 5, 4),          # front
            (2, 3, 7), (2, 7, 6),          # back
            (0, 4, 7), (0, 7, 3),          # left
            (1, 2, 6), (1, 6, 5),          # right
        ]
        return Mesh(vertices=vertices, triangles=triangles)

    # ----------------------------------------------------------------- slow path
    ps = pixel_data.pixel_size_mm
    pixel_positions = set(pixel_data.pixels.keys())

    verts: List[Tuple[float, float, float]] = []
    tris: List[Tuple[int, int, int]] = []
    top_map: Dict[Tuple[int, int], int] = {}
    bot_map: Dict[Tuple[int, int], int] = {}

    for x, y in pixel_positions:
        for (cx, cy), is_top in [
            *[((x + dx, y + dy), True)  for dx, dy in ((0,0),(1,0),(0,1),(1,1))],
            *[((x + dx, y + dy), False) for dx, dy in ((0,0),(1,0),(0,1),(1,1))],
        ]:
            key = (cx, cy)
            m = top_map if is_top else bot_map
            if key not in m:
                m[key] = len(verts)
                verts.append((cx * ps, cy * ps, z_top if is_top else z_bottom))

        bl_t = top_map[(x,   y)]
        br_t = top_map[(x+1, y)]
        tl_t = top_map[(x,   y+1)]
        tr_t = top_map[(x+1, y+1)]
        bl_b = bot_map[(x,   y)]
        br_b = bot_map[(x+1, y)]
        tl_b = bot_map[(x,   y+1)]
        tr_b = bot_map[(x+1, y+1)]

        tris.append((bl_t, br_t, tl_t)); tris.append((br_t, tr_t, tl_t))  # top face
        tris.append((bl_b, tl_b, br_b)); tris.append((br_b, tl_b, tr_b))  # bottom face

    for x, y in pixel_positions:
        for (x1, y1), (x2, y2), neighbor in [
            ((x,   y),   (x+1, y),   (x,   y-1)),   # south edge
            ((x+1, y),   (x+1, y+1), (x+1, y)),     # east edge
            ((x+1, y+1), (x,   y+1), (x,   y+1)),   # north edge
            ((x,   y+1), (x,   y),   (x-1, y)),     # west edge
        ]:
            if neighbor in pixel_positions:
                continue
            assert (x1, y1) in bot_map
            assert (x2, y2) in bot_map
            assert (x1, y1) in top_map
            assert (x2, y2) in top_map
            tris.append((bot_map[(x1,y1)], bot_map[(x2,y2)], top_map[(x1,y1)]))
            tris.append((bot_map[(x2,y2)], top_map[(x2,y2)], top_map[(x1,y1)]))

    return Mesh(vertices=verts, triangles=tris)


# Public API functions with dispatch logic
def generate_region_mesh(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Generate a 3D mesh for a colored region by extruding pixels upward.

    This is where the magic happens! We take a flat region (set of (x,y) pixels)
    and turn it into a 3D object by:
    1. Creating the top face (at z = layer_height)
    2. Creating the bottom face (at z = 0)
    3. Creating walls around the perimeter

    The tricky part is the perimeter detection - we need to find which pixels
    are on the edge (have at least one neighbor that's NOT in the region).
    
    When USE_OPTIMIZED_MESH_GENERATION is True, dispatches to rectangle-based
    optimization for reduced vertex/triangle counts and guaranteed manifold meshes.
    Falls back to original implementation if optimization fails.

    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        config: ConversionConfig object with layer height and other parameters

    Returns:
        A Mesh object ready for export to 3MF
    """
    # Dispatch to optimized version if enabled and available
    if USE_OPTIMIZED_MESH_GENERATION and OPTIMIZATION_AVAILABLE:
        return generate_region_mesh_optimized(region, pixel_data, config)
    
    # Use original implementation
    return _generate_region_mesh_original(region, pixel_data, config)


def generate_backing_plate(
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Generate the backing plate that goes under everything.

    The backing plate matches the exact non-transparent pixel footprint
    and spans z = [-config.base_height_mm, 0].

    For optimized mesh generation, delegates to generate_backing_plate_optimized
    from rectangle_optimizer when USE_OPTIMIZED_MESH_GENERATION is set.

    Args:
        pixel_data: Pixel data (includes which pixels are non-transparent)
        config: ConversionConfig object with base height and other parameters

    Returns:
        A Mesh object for the backing plate
    """
    if USE_OPTIMIZED_MESH_GENERATION and OPTIMIZATION_AVAILABLE:
        return generate_backing_plate_optimized(pixel_data, config)
    return _generate_slab_mesh(pixel_data, -config.base_height_mm, 0.0)


def generate_solid_core(
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Generate the solid core slab sandwiched between the two colour shells.

    The core shares the same full-model footprint as the backing plate but is
    centred on z=0: it spans [config.core_z_bottom, config.core_z_top].  A
    single filament fills the bulk of the model depth, reducing filament-swap
    time dramatically on multi-colour prints.

    Reuses _generate_slab_mesh — the same geometry logic as the backing plate,
    just at different Z coordinates.

    Only valid when config.has_solid_core is True.

    Args:
        pixel_data: Pixel data for the full model footprint
        config: ConversionConfig with solid_core=True and core_height_mm set

    Returns:
        A Mesh object for the solid core slab
    """
    return _generate_slab_mesh(pixel_data, config.core_z_bottom, config.core_z_top)



def generate_region_mesh_shell(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig',
    z_bottom: float,
    z_top: float,
) -> Mesh:
    """
    Generate a region mesh between two explicit Z coordinates.

    Used when solid_core is enabled to create each colour region as two
    thin shells — one below the core and one above — rather than a single
    full-height extrusion.

    The logic is identical to _generate_region_mesh_original but with
    parameterised z_bottom / z_top instead of reading from config.

    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        config: ConversionConfig (used for pixel_size via pixel_data, not heights)
        z_bottom: Z coordinate of the bottom face
        z_top: Z coordinate of the top face

    Returns:
        A Mesh object ready for export
    """
    edge_connected_pixels = set()
    for x, y in region.pixels:
        for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
            if (nx, ny) in region.pixels:
                edge_connected_pixels.add((x, y))
                break

    diagonal_only_pixels = region.pixels - edge_connected_pixels

    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    ps = pixel_data.pixel_size_mm

    perimeter_pixels: Set[Tuple[int, int]] = set()
    for x, y in region.pixels:
        for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
            if (nx, ny) not in region.pixels:
                perimeter_pixels.add((x, y))
                break

    top_vertex_map: Dict[tuple, int] = {}
    for x, y in region.pixels:
        corners = [(x, y, "bl"), (x+1, y, "br"), (x, y+1, "tl"), (x+1, y+1, "tr")]
        corner_indices = []
        for cx, cy, label in corners:
            if (x, y) in diagonal_only_pixels:
                key: tuple = ((x, y), cx, cy, "top")
            else:
                key = (cx, cy)
            if key not in top_vertex_map:
                top_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, z_top))
            corner_indices.append(top_vertex_map[key])
        bl, br, tl, tr = corner_indices
        triangles.append((bl, br, tl))
        triangles.append((br, tr, tl))

    bottom_vertex_map: Dict[tuple, int] = {}
    for x, y in region.pixels:
        corners = [(x, y, "bl"), (x+1, y, "br"), (x, y+1, "tl"), (x+1, y+1, "tr")]
        corner_indices = []
        for cx, cy, label in corners:
            if (x, y) in diagonal_only_pixels:
                key = ((x, y), cx, cy, "bottom")
            else:
                key = (cx, cy)
            if key not in bottom_vertex_map:
                bottom_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, z_bottom))
            corner_indices.append(bottom_vertex_map[key])
        bl, br, tl, tr = corner_indices
        triangles.append((bl, tl, br))
        triangles.append((br, tl, tr))

    for x, y in perimeter_pixels:
        edges = [
            ((x, y), (x+1, y), "bottom"),
            ((x+1, y), (x+1, y+1), "right"),
            ((x+1, y+1), (x, y+1), "top"),
            ((x, y+1), (x, y), "left"),
        ]
        for (x1, y1), (x2, y2), edge_name in edges:
            if edge_name == "bottom":
                neighbor = (x, y - 1)
            elif edge_name == "right":
                neighbor = (x + 1, y)
            elif edge_name == "top":
                neighbor = (x, y + 1)
            else:
                neighbor = (x - 1, y)
            if neighbor in region.pixels:
                continue
            if (x, y) in diagonal_only_pixels:
                bl_key: tuple = ((x, y), x1, y1, "bottom")
                br_key: tuple = ((x, y), x2, y2, "bottom")
                tl_key: tuple = ((x, y), x1, y1, "top")
                tr_key: tuple = ((x, y), x2, y2, "top")
            else:
                bl_key = (x1, y1)
                br_key = (x2, y2)
                tl_key = (x1, y1)
                tr_key = (x2, y2)
            idx_bl = bottom_vertex_map[bl_key]
            idx_br = bottom_vertex_map[br_key]
            idx_tl = top_vertex_map[tl_key]
            idx_tr = top_vertex_map[tr_key]
            triangles.append((idx_bl, idx_br, idx_tl))
            triangles.append((idx_br, idx_tr, idx_tl))

    return Mesh(vertices=vertices, triangles=triangles)


def check_mesh_manifold(mesh: Mesh) -> Dict[str, object]:
    """
    Check a mesh for manifold properties and CCW top-face winding.

    A manifold mesh has every edge shared by exactly 2 triangles — no open
    holes (boundary edges, count 1) and no impossible junctions
    (non-manifold edges, count 3+).  Slicers require manifold geometry to
    produce valid toolpaths.

    Also verifies that top-face triangles use CCW winding, which produces
    outward-facing (positive-Z) normals as required by the 3MF spec.

    Args:
        mesh: The Mesh to check.

    Returns:
        Dict with keys:
            boundary_edges:     int  — edges shared by exactly 1 triangle
            non_manifold_edges: int  — edges shared by 3+ triangles
            winding:            str  — "CCW", "CW", "MIXED", or "UNKNOWN"
            is_manifold:        bool — True iff both edge counts are 0
            is_ccw:             bool — True iff winding == "CCW"
            is_valid:           bool — True iff is_manifold and is_ccw
    """
    from collections import defaultdict

    edge_count: Dict[Tuple[int, int], int] = defaultdict(int)
    for v1, v2, v3 in mesh.triangles:
        edge_count[(min(v1, v2), max(v1, v2))] += 1
        edge_count[(min(v2, v3), max(v2, v3))] += 1
        edge_count[(min(v3, v1), max(v3, v1))] += 1

    boundary     = sum(1 for c in edge_count.values() if c == 1)
    non_manifold = sum(1 for c in edge_count.values() if c > 2)

    # Check top-face winding: all triangles at max-Z should have positive-Z
    # normals (CCW when viewed from above).
    winding = "UNKNOWN"
    if mesh.vertices and mesh.triangles:
        max_z = max(v[2] for v in mesh.vertices)
        normals_z: List[float] = []
        for v1i, v2i, v3i in mesh.triangles:
            p1, p2, p3 = mesh.vertices[v1i], mesh.vertices[v2i], mesh.vertices[v3i]
            if (abs(p1[2] - max_z) < 1e-6
                    and abs(p2[2] - max_z) < 1e-6
                    and abs(p3[2] - max_z) < 1e-6):
                # Z component of (p2-p1) × (p3-p1)
                nz = ((p2[0] - p1[0]) * (p3[1] - p1[1])
                      - (p2[1] - p1[1]) * (p3[0] - p1[0]))
                if abs(nz) > 1e-10:
                    normals_z.append(nz)
        if normals_z:
            ccw_n = sum(1 for n in normals_z if n > 0)
            cw_n  = len(normals_z) - ccw_n
            if ccw_n > 0 and cw_n == 0:
                winding = "CCW"
            elif cw_n > 0 and ccw_n == 0:
                winding = "CW"
            else:
                winding = "MIXED"

    return {
        'boundary_edges':      boundary,
        'non_manifold_edges':  non_manifold,
        'winding':             winding,
        'is_manifold':         boundary == 0 and non_manifold == 0,
        'is_ccw':              winding == "CCW",
        'is_valid':            boundary == 0 and non_manifold == 0 and winding == "CCW",
    }
