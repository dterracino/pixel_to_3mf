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




def _generate_region_mesh_original(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Original per-pixel mesh generation implementation.
    
    This is the fallback implementation that always works reliably.
    It generates meshes by creating geometry for each pixel individually.
    
    CRITICAL: For pixels that only touch diagonally (not edge-connected),
    we must NOT share vertices at the corners to avoid non-manifold geometry.
    Each pixel gets its own set of vertices to ensure manifold properties.
    
    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        config: ConversionConfig object with layer height and other parameters
    
    Returns:
        A Mesh object ready for export to 3MF
    """
    # Check which pixels in this region are edge-connected vs diagonal-only
    edge_connected_pixels = set()
    for x, y in region.pixels:
        # Check 4 edge neighbors
        edge_neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        for nx, ny in edge_neighbors:
            if (nx, ny) in region.pixels:
                # This pixel has at least one edge-connected neighbor in the region
                edge_connected_pixels.add((x, y))
                break
    
    # Diagonal-only pixels: pixels in region but not edge-connected to any other pixel in region
    diagonal_only_pixels = region.pixels - edge_connected_pixels
    
    # Original per-pixel mesh generation
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    
    ps = pixel_data.pixel_size_mm
    
    # We'll build this in multiple passes:
    # Pass 1: Find perimeter pixels (for walls)
    # Pass 2: Generate top face triangles
    # Pass 3: Generate bottom face triangles
    # Pass 4: Generate wall triangles
    
    # ========================================================================
    # Pass 1: Find perimeter pixels
    # ========================================================================
    # A pixel is on the perimeter if it has at least one neighbor (up/down/left/right)
    # that is NOT in this region
    
    perimeter_pixels: Set[Tuple[int, int]] = set()
    
    for x, y in region.pixels:
        # Check all 4 neighbors
        neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        
        # If any neighbor is NOT in the region, this pixel is on the perimeter
        for nx, ny in neighbors:
            if (nx, ny) not in region.pixels:
                perimeter_pixels.add((x, y))
                break
    
    # ========================================================================
    # Pass 2: Generate top face (z = config.color_height_mm)
    # ========================================================================
    # For each pixel, create 2 triangles to form a square

    # Map from (x, y) pixel coords to vertex index for top face
    # For diagonal-only pixels, uses 4-tuple keys: ((x,y), cx, cy, "top")
    # Dict[tuple, int] because keys are either (cx, cy) or ((x,y), cx, cy, label)
    top_vertex_map: Dict[tuple, int] = {}

    for x, y in region.pixels:
        # Each pixel square has 4 corners
        # We label them: "bl" (bottom-left), "br", "tl", "tr"
        # In pixel coordinates:
        #   - bottom-left  = (x, y)
        #   - bottom-right = (x+1, y)
        #   - top-left     = (x, y+1)
        #   - top-right    = (x+1, y+1)

        corners = [
            (x, y, "bl"),       # bottom-left
            (x+1, y, "br"),     # bottom-right
            (x, y+1, "tl"),     # top-left
            (x+1, y+1, "tr"),   # top-right
        ]

        # Create vertices for each corner
        corner_indices = []
        for cx, cy, label in corners:
            key = (cx, cy)
            
            # CRITICAL FIX: For diagonal-only pixels, create unique vertices
            # to prevent non-manifold geometry. Edge-connected pixels share vertices.
            if (x, y) in diagonal_only_pixels:
                # This pixel only touches others diagonally - create unique vertices
                # Use tuple with pixel coords to ensure uniqueness
                unique_key = ((x, y), cx, cy, "top")
                if unique_key not in top_vertex_map:
                    top_vertex_map[unique_key] = len(vertices)
                    vertices.append((cx * ps, cy * ps, config.color_height_mm))
                corner_indices.append(top_vertex_map[unique_key])
            else:
                # Edge-connected pixel - share vertices with neighbors
                if key not in top_vertex_map:
                    top_vertex_map[key] = len(vertices)
                    vertices.append((cx * ps, cy * ps, config.color_height_mm))
                corner_indices.append(top_vertex_map[key])
        
        # Create 2 triangles for the top face
        # Counter-clockwise winding when viewed from above (looking down at +Z)
        bl, br, tl, tr = corner_indices
        triangles.append((bl, br, tl))
        triangles.append((br, tr, tl))
    
    # ========================================================================
    # Pass 3: Generate bottom face (z = 0)
    # ========================================================================
    # Same as top face, but at z=0 and with reversed winding (for correct normals)
    # For diagonal-only pixels, uses 4-tuple keys: ((x,y), cx, cy, "bottom")
    # Dict[tuple, int] because keys are either (cx, cy) or ((x,y), cx, cy, label)
    bottom_vertex_map: Dict[tuple, int] = {}
    
    for x, y in region.pixels:
        corners = [
            (x, y, "bl"),
            (x+1, y, "br"),
            (x, y+1, "tl"),
            (x+1, y+1, "tr"),
        ]
        
        corner_indices = []
        for cx, cy, label in corners:
            key = (cx, cy)
            
            # CRITICAL FIX: For diagonal-only pixels, create unique vertices
            if (x, y) in diagonal_only_pixels:
                # This pixel only touches others diagonally - create unique vertices
                unique_key = ((x, y), cx, cy, "bottom")
                if unique_key not in bottom_vertex_map:
                    bottom_vertex_map[unique_key] = len(vertices)
                    vertices.append((cx * ps, cy * ps, config.color_layer_z_bottom))
                corner_indices.append(bottom_vertex_map[unique_key])
            else:
                # Edge-connected pixel - share vertices with neighbors
                if key not in bottom_vertex_map:
                    bottom_vertex_map[key] = len(vertices)
                    vertices.append((cx * ps, cy * ps, config.color_layer_z_bottom))
                corner_indices.append(bottom_vertex_map[key])
        
        # Bottom face triangles (CCW when viewed from below, looking up at -Z)
        bl, br, tl, tr = corner_indices
        triangles.append((bl, tl, br))
        triangles.append((br, tl, tr))
    
    # ========================================================================
    # Pass 4: Generate walls for perimeter pixels
    # ========================================================================
    # For each perimeter pixel, check which edges are exposed and create wall quads
    
    for x, y in perimeter_pixels:
        # Check each of the 4 edges
        edges = [
            ((x, y), (x+1, y), "bottom"),   # Bottom edge (y stays same)
            ((x+1, y), (x+1, y+1), "right"), # Right edge (x stays same)
            ((x+1, y+1), (x, y+1), "top"),   # Top edge (y stays same)
            ((x, y+1), (x, y), "left"),      # Left edge (x stays same)
        ]
        
        for (x1, y1), (x2, y2), edge_name in edges:
            # Check if the neighbor beyond this edge is in the region
            # If not, we need a wall here!
            
            # Calculate which neighbor pixel this edge faces
            if edge_name == "bottom":
                neighbor = (x, y - 1)
            elif edge_name == "right":
                neighbor = (x + 1, y)
            elif edge_name == "top":
                neighbor = (x, y + 1)
            else:  # left
                neighbor = (x - 1, y)
            
            # If neighbor is in the region, skip this edge (it's internal)
            if neighbor in region.pixels:
                continue
            
            # Create a wall quad (2 triangles) between bottom and top
            # CRITICAL FIX: Reuse existing vertices instead of creating duplicates!
            
            # For diagonal-only pixels, vertices are stored with unique keys
            # For edge-connected pixels, vertices use simple (cx, cy) keys
            if (x, y) in diagonal_only_pixels:
                # Diagonal-only pixel - use unique keys
                bl_key = ((x, y), x1, y1, "bottom")
                br_key = ((x, y), x2, y2, "bottom")
                tl_key = ((x, y), x1, y1, "top")
                tr_key = ((x, y), x2, y2, "top")
            else:
                # Edge-connected pixel - use simple keys
                bl_key = (x1, y1)
                br_key = (x2, y2)
                tl_key = (x1, y1)
                tr_key = (x2, y2)
            
            # Get vertex indices (should always be found since we created faces for this pixel)
            assert bl_key in bottom_vertex_map, f"Could not find bottom vertex for wall at {bl_key}"
            assert br_key in bottom_vertex_map, f"Could not find bottom vertex for wall at {br_key}"
            assert tl_key in top_vertex_map, f"Could not find top vertex for wall at {tl_key}"
            assert tr_key in top_vertex_map, f"Could not find top vertex for wall at {tr_key}"
            
            idx_bl = bottom_vertex_map[bl_key]
            idx_br = bottom_vertex_map[br_key]
            idx_tl = top_vertex_map[tl_key]
            idx_tr = top_vertex_map[tr_key]
            
            # Create 2 triangles for the wall (REVERSED winding for outward-facing normals)
            # The issue was that our walls were inside-out!
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
