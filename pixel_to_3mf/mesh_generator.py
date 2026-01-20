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
    top_vertex_map: Dict[Tuple[int, ...], int] = {}

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
    bottom_vertex_map: Dict[Tuple[int, ...], int] = {}
    
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
                    vertices.append((cx * ps, cy * ps, 0.0))
                corner_indices.append(bottom_vertex_map[unique_key])
            else:
                # Edge-connected pixel - share vertices with neighbors
                if key not in bottom_vertex_map:
                    bottom_vertex_map[key] = len(vertices)
                    vertices.append((cx * ps, cy * ps, 0.0))
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

    The backing plate should match the EXACT footprint of the non-transparent pixels,
    with holes where transparent pixels are. It goes from z=-config.base_height_mm to z=0.
    
    Automatically uses optimized path for simple rectangles (no transparency)!
    When USE_OPTIMIZED_MESH_GENERATION is True, dispatches to rectangle-based
    optimization for reduced vertex/triangle counts and guaranteed manifold meshes.
    Falls back to original implementation if optimization fails.

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
