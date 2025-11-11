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

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig

# ============================================================================
# Feature flag for optimized mesh generation
# ============================================================================
# When True, uses polygon merging + triangulation for significant reduction
# in vertex/triangle counts (50-90% typical). When False, uses original
# per-pixel mesh generation. Both produce manifold meshes with identical
# visual results.
USE_OPTIMIZED_MESH_GENERATION = False

# Try to import optimized functions
try:
    from .polygon_optimizer import (
        generate_region_mesh_optimized,
        generate_backing_plate_optimized
    )
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False


class Mesh:
    """
    A 3D mesh defined by vertices and triangles.
    
    This is the fundamental building block of 3D graphics! A mesh is just:
    - A list of 3D points (vertices)
    - A list of triangles (each triangle = 3 vertex indices)
    
    Example:
        vertices = [(0,0,0), (1,0,0), (0,1,0)]  # 3 points
        triangles = [(0, 1, 2)]  # 1 triangle using all 3 vertices
        
    The order matters for triangles! Counter-clockwise = outward-facing normal.
    This is important for slicers to know which side is "outside" the model.
    """
    
    def __init__(self, vertices: List[Tuple[float, float, float]], triangles: List[Tuple[int, int, int]]):
        """
        Initialize a mesh.
        
        Args:
            vertices: List of (x, y, z) coordinates in millimeters
            triangles: List of (v0, v1, v2) vertex indices (0-indexed)
        """
        self.vertices = vertices
        self.triangles = triangles
    
    def __repr__(self) -> str:
        return f"Mesh(vertices={len(self.vertices)}, triangles={len(self.triangles)})"


def _generate_region_mesh_original(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Original per-pixel mesh generation implementation.
    
    This is the fallback implementation that always works reliably.
    It generates meshes by creating geometry for each pixel individually.
    
    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        config: ConversionConfig object with layer height and other parameters
    
    Returns:
        A Mesh object ready for export to 3MF
    """
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
    top_vertex_map: Dict[Tuple[int, int], int] = {}

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

        # Create vertices for each corner (if not already created)
        corner_indices = []
        for cx, cy, label in corners:
            # KEY FIX: Use only coordinates for the key, not the label!
            # Adjacent pixels call the same corner different names (e.g. one pixel's "tr" is another's "tl")
            key = (cx, cy)
            if key not in top_vertex_map:
                # Create new vertex at (cx * ps, cy * ps, config.color_height_mm)
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
    
    bottom_vertex_map: Dict[Tuple[int, int], int] = {}
    
    for x, y in region.pixels:
        corners = [
            (x, y, "bl"),
            (x+1, y, "br"),
            (x, y+1, "tl"),
            (x+1, y+1, "tr"),
        ]
        
        corner_indices = []
        for cx, cy, label in corners:
            # KEY FIX: Use only coordinates, not label!
            key = (cx, cy)
            if key not in bottom_vertex_map:
                bottom_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, 0.0))
            corner_indices.append(bottom_vertex_map[key])
        
        # Bottom face triangles (CCW when viewed from below, looking up at -Z)
        bl, br, tl, tr = corner_indices
        triangles.append((bl, tl, br))
        triangles.append((br, tl, tr))
    
    # ========================================================================
    # Pre-Pass 4: Detect diagonal-only corners
    # ========================================================================
    # A corner is diagonal-only if pixels share it but are NOT edge-connected
    # These corners need separate wall vertices to maintain manifold property
    
    diagonal_corners: Set[Tuple[int, int]] = set()
    
    for px, py in region.pixels:
        # Check all 4 diagonal neighbors
        # For each diagonal, we also list the two edge pixels that would connect them
        diag_neighbors = [
            ((px + 1, py + 1), [(px + 1, py), (px, py + 1)]),  # top-right diagonal
            ((px - 1, py + 1), [(px - 1, py), (px, py + 1)]),  # top-left diagonal
            ((px + 1, py - 1), [(px + 1, py), (px, py - 1)]),  # bottom-right diagonal
            ((px - 1, py - 1), [(px - 1, py), (px, py - 1)]),  # bottom-left diagonal
        ]
        
        for (diag_x, diag_y), edge_pixels in diag_neighbors:
            # Check if diagonal pixel exists in region
            if (diag_x, diag_y) not in region.pixels:
                continue
            
            # Check if any edge-connecting pixel exists
            has_edge_connection = any(ep in region.pixels for ep in edge_pixels)
            
            # If diagonal exists but NO edge connection, mark shared corner
            if not has_edge_connection:
                # The shared corner is the point where the two pixels meet
                # For pixel (px, py) and diagonal neighbor (diag_x, diag_y):
                # - If diag is to the right (diag_x > px), corner x = px + 1
                # - If diag is to the left (diag_x < px), corner x = px
                # - If diag is above (diag_y > py), corner y = py + 1
                # - If diag is below (diag_y < py), corner y = py
                corner_x = px + 1 if diag_x > px else px
                corner_y = py + 1 if diag_y > py else py
                diagonal_corners.add((corner_x, corner_y))
    
    # Map from ((pixel_x, pixel_y), (corner_x, corner_y)) to vertex index
    # This allows different pixels to have separate vertices at diagonal corners
    diagonal_wall_vertices_top: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = {}
    diagonal_wall_vertices_bottom: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = {}
    
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
            # Handle diagonal corners specially to maintain manifold property
            
            # Helper function to get vertex index for a corner
            def get_wall_vertex(corner_x: int, corner_y: int, is_top: bool) -> int:
                corner_key = (corner_x, corner_y)
                
                # Check if this corner is shared only by diagonal pixels
                if corner_key in diagonal_corners:
                    # Create wall-specific vertex (keyed by pixel + corner)
                    # Different pixels get different vertices at diagonal corners
                    # Same pixel's different walls share the same vertex
                    wall_key = ((x, y), corner_key)
                    
                    if is_top:
                        if wall_key not in diagonal_wall_vertices_top:
                            diagonal_wall_vertices_top[wall_key] = len(vertices)
                            vertices.append((corner_x * ps, corner_y * ps, config.color_height_mm))
                        return diagonal_wall_vertices_top[wall_key]
                    else:
                        if wall_key not in diagonal_wall_vertices_bottom:
                            diagonal_wall_vertices_bottom[wall_key] = len(vertices)
                            vertices.append((corner_x * ps, corner_y * ps, 0.0))
                        return diagonal_wall_vertices_bottom[wall_key]
                else:
                    # Reuse existing face vertex (normal case for edge-connected pixels)
                    if is_top:
                        assert corner_key in top_vertex_map, f"Could not find top vertex at {corner_key}"
                        return top_vertex_map[corner_key]
                    else:
                        assert corner_key in bottom_vertex_map, f"Could not find bottom vertex at {corner_key}"
                        return bottom_vertex_map[corner_key]
            
            # Get vertex indices for the wall quad
            idx_bl = get_wall_vertex(x1, y1, is_top=False)
            idx_br = get_wall_vertex(x2, y2, is_top=False)
            idx_tl = get_wall_vertex(x1, y1, is_top=True)
            idx_tr = get_wall_vertex(x2, y2, is_top=True)
            
            # Create 2 triangles for the wall (CCW winding for outward-facing normals)
            triangles.append((idx_bl, idx_br, idx_tl))
            triangles.append((idx_br, idx_tr, idx_tl))
    
    return Mesh(vertices=vertices, triangles=triangles)


def _generate_backing_plate_original(
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Mesh:
    """
    Original per-pixel backing plate generation implementation.
    
    This is the fallback implementation that always works reliably.
    It generates the backing plate by creating geometry for each pixel individually.

    Args:
        pixel_data: Pixel data (includes which pixels are non-transparent)
        config: ConversionConfig object with base height and other parameters

    Returns:
        A Mesh object for the backing plate
    """
    # Original per-pixel mesh generation
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []

    ps = pixel_data.pixel_size_mm

    # Similar to region generation, but simpler - we create a slab for each pixel
    # Top face (z = 0) and bottom face (z = -config.base_height_mm)
    
    top_vertex_map: Dict[Tuple[int, int], int] = {}
    bottom_vertex_map: Dict[Tuple[int, int], int] = {}
    
    # Get all non-transparent pixel positions
    pixel_positions = set(pixel_data.pixels.keys())
    
    # Generate top and bottom faces
    for x, y in pixel_positions:
        # Top face vertices (z = 0)
        top_corners = [
            (x, y, "bl"),
            (x+1, y, "br"),
            (x, y+1, "tl"),
            (x+1, y+1, "tr"),
        ]
        
        top_indices = []
        for cx, cy, label in top_corners:
            # KEY FIX: Remove label from key!
            key = (cx, cy)
            if key not in top_vertex_map:
                top_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, 0.0))
            top_indices.append(top_vertex_map[key])
        
        # Top face triangles (facing up)
        bl, br, tl, tr = top_indices
        triangles.append((bl, br, tl))
        triangles.append((br, tr, tl))
        
        # Bottom face vertices (z = -config.base_height_mm)
        bottom_corners = [
            (x, y, "bl"),
            (x+1, y, "br"),
            (x, y+1, "tl"),
            (x+1, y+1, "tr"),
        ]

        bottom_indices = []
        for cx, cy, label in bottom_corners:
            # KEY FIX: Remove label from key!
            key = (cx, cy)
            if key not in bottom_vertex_map:
                bottom_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, -config.base_height_mm))
            bottom_indices.append(bottom_vertex_map[key])
        
        # Bottom face triangles (facing down - reversed winding)
        bl, br, tl, tr = bottom_indices
        triangles.append((bl, tl, br))
        triangles.append((br, tl, tr))
    
    # Generate perimeter walls (only where edges are exposed)
    for x, y in pixel_positions:
        # Check each of the 4 edges
        edges = [
            ((x, y), (x+1, y), (x, y-1), "bottom"),      # Bottom edge, neighbor below
            ((x+1, y), (x+1, y+1), (x+1, y), "right"),   # Right edge, neighbor right
            ((x+1, y+1), (x, y+1), (x, y+1), "top"),     # Top edge, neighbor above
            ((x, y+1), (x, y), (x-1, y), "left"),        # Left edge, neighbor left
        ]
        
        for (x1, y1), (x2, y2), neighbor, edge_name in edges:
            # If neighbor pixel exists, skip this edge (it's internal)
            if neighbor in pixel_positions:
                continue
            
            # Create wall quad
            # CRITICAL FIX: Reuse vertices from top/bottom maps to avoid duplicates!
            
            # Now that keys are just (x, y), lookup is simple!
            bl_key = (x1, y1)
            br_key = (x2, y2)
            tl_key = (x1, y1)
            tr_key = (x2, y2)
            
            # Get the vertex indices from our maps
            assert bl_key in bottom_vertex_map, f"Could not find bottom vertex for backing plate wall at {bl_key}"
            assert br_key in bottom_vertex_map, f"Could not find bottom vertex for backing plate wall at {br_key}"
            assert tl_key in top_vertex_map, f"Could not find top vertex for backing plate wall at {tl_key}"
            assert tr_key in top_vertex_map, f"Could not find top vertex for backing plate wall at {tr_key}"
            
            idx_bl = bottom_vertex_map[bl_key]
            idx_br = bottom_vertex_map[br_key]
            idx_tl = top_vertex_map[tl_key]
            idx_tr = top_vertex_map[tr_key]
            
            # Wall triangles (REVERSED winding for outward-facing normals)
            triangles.append((idx_bl, idx_br, idx_tl))
            triangles.append((idx_br, idx_tr, idx_tl))
    
    return Mesh(vertices=vertices, triangles=triangles)


def _is_simple_rectangle(pixel_data: PixelData) -> bool:
    """
    Check if all pixels form a complete rectangle (no transparency).
    
    This is perfect for full-frame images like screenshots or large pixel art.
    A simple rectangle allows us to use a much more efficient backing plate.
    
    Args:
        pixel_data: The pixel data to check
    
    Returns:
        True if the image is a complete rectangle with no transparent pixels
    """
    total_expected = pixel_data.width * pixel_data.height
    total_actual = len(pixel_data.pixels)
    return total_expected == total_actual


def _create_simple_rectangle_backing_plate(pixel_data: PixelData, base_height_mm: float) -> Mesh:
    """
    Create a simple rectangular backing plate - just 12 triangles!
    
    Perfect for images with no transparency or holes.
    Way more efficient than tracing complex outlines.
    
    Args:
        pixel_data: The pixel data (used for dimensions)
        base_height_mm: Height of the backing plate
    
    Returns:
        A Mesh object with 8 vertices and 12 triangles (rectangular prism)
    """
    width_mm = pixel_data.width * pixel_data.pixel_size_mm
    height_mm = pixel_data.height * pixel_data.pixel_size_mm
    
    # 8 vertices (rectangular prism)
    # Bottom 4 corners at z=-base_height_mm
    # Top 4 corners at z=0
    vertices = [
        (0, 0, -base_height_mm),              # 0: bottom-left-front
        (width_mm, 0, -base_height_mm),       # 1: bottom-right-front
        (width_mm, height_mm, -base_height_mm),  # 2: bottom-right-back
        (0, height_mm, -base_height_mm),      # 3: bottom-left-back
        (0, 0, 0),                            # 4: top-left-front
        (width_mm, 0, 0),                     # 5: top-right-front
        (width_mm, height_mm, 0),             # 6: top-right-back
        (0, height_mm, 0),                    # 7: top-left-back
    ]
    
    # 12 triangles (2 per face, 6 faces)
    # Use counter-clockwise winding for outward-facing normals
    triangles = [
        # Bottom face (z=-base_height_mm) - looking up from below
        (0, 2, 1), (0, 3, 2),
        # Top face (z=0) - looking down from above
        (4, 5, 6), (4, 6, 7),
        # Front face (y=0)
        (0, 1, 5), (0, 5, 4),
        # Back face (y=height_mm)
        (2, 3, 7), (2, 7, 6),
        # Left face (x=0)
        (0, 4, 7), (0, 7, 3),
        # Right face (x=width_mm)
        (1, 2, 6), (1, 6, 5),
    ]
    
    return Mesh(vertices=vertices, triangles=triangles)


def _create_complex_backing_plate(pixel_data: PixelData, config: 'ConversionConfig') -> Mesh:
    """
    Create backing plate using the current union approach.
    
    This is the existing implementation - handles sprites with holes,
    irregular shapes, etc.
    
    Args:
        pixel_data: The pixel data
        config: ConversionConfig object with base height and other parameters
    
    Returns:
        A Mesh object for the backing plate
    """
    # This is just the original implementation
    return _generate_backing_plate_original(pixel_data, config)


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
    
    When USE_OPTIMIZED_MESH_GENERATION is True, dispatches to polygon-based
    optimization for reduced vertex/triangle counts. Falls back to original
    implementation if optimization fails.

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

    The backing plate should match the EXACT footprint of the non-transparent pixels,
    with holes where transparent pixels are. It goes from z=-config.base_height_mm to z=0.
    
    Automatically uses optimized path for simple rectangles (no transparency)!
    When USE_OPTIMIZED_MESH_GENERATION is True, dispatches to polygon-based
    optimization for reduced vertex/triangle counts. Falls back to original
    implementation if optimization fails.

    Args:
        pixel_data: Pixel data (includes which pixels are non-transparent)
        config: ConversionConfig object with base height and other parameters

    Returns:
        A Mesh object for the backing plate
    """
    # Fast path: check if it's just a simple rectangle
    if _is_simple_rectangle(pixel_data):
        return _create_simple_rectangle_backing_plate(pixel_data, config.base_height_mm)
    
    # Complex path: use the current union approach for sprites with holes
    # Dispatch to optimized version if enabled and available
    if USE_OPTIMIZED_MESH_GENERATION and OPTIMIZATION_AVAILABLE:
        return generate_backing_plate_optimized(pixel_data, config)
    
    # Use original implementation
    return _generate_backing_plate_original(pixel_data, config)
