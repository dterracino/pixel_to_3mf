"""
Mesh generation module for creating 3D geometry from 2D regions.

This is where we go from flat pixel art to actual 3D meshes! We take
regions (connected blobs of pixels) and extrude them upward into solid
geometry. We also create the backing plate that goes underneath everything.

The geometry is stored as vertices (3D points) and triangles (3 vertex
indices each). This is the universal format for 3D meshes - STL, OBJ,
3MF all use this approach! 🎲
"""

from typing import List, Tuple, Set
from .region_merger import Region
from .image_processor import PixelData
from .constants import COLOR_LAYER_HEIGHT_MM, BASE_LAYER_HEIGHT_MM


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


def generate_region_mesh(
    region: Region,
    pixel_data: PixelData,
    layer_height: float = COLOR_LAYER_HEIGHT_MM
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
    
    Args:
        region: The region to extrude
        pixel_data: Pixel scaling info
        layer_height: How high to extrude (default: COLOR_LAYER_HEIGHT_MM)
    
    Returns:
        A Mesh object ready for export to 3MF
    """
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
    # Pass 2: Generate top face (z = layer_height)
    # ========================================================================
    # For each pixel, create 2 triangles to form a square
    
    # Map from (x, y) pixel coords to vertex index for top face
    top_vertex_map: dict[Tuple[int, int], int] = {}
    
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
                # Create new vertex at (cx * ps, cy * ps, layer_height)
                top_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, layer_height))
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
    
    bottom_vertex_map: dict[Tuple[int, int], int] = {}
    
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
            
            # Now that our keys are just (x, y) coordinates, lookup is simple!
            # For bottom vertices (z=0)
            bl_key = (x1, y1)
            br_key = (x2, y2)
            
            # For top vertices (z=layer_height)
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


def generate_backing_plate(
    pixel_data: PixelData,
    base_height: float = BASE_LAYER_HEIGHT_MM
) -> Mesh:
    """
    Generate the backing plate that goes under everything.
    
    The backing plate should match the EXACT footprint of the non-transparent pixels,
    with holes where transparent pixels are. It goes from z=-base_height to z=0.
    
    Args:
        pixel_data: Pixel data (includes which pixels are non-transparent)
        base_height: Thickness of the backing plate (default: BASE_LAYER_HEIGHT_MM)
    
    Returns:
        A Mesh object for the backing plate
    """
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    
    ps = pixel_data.pixel_size_mm
    
    # Similar to region generation, but simpler - we create a slab for each pixel
    # Top face (z = 0) and bottom face (z = -base_height)
    
    top_vertex_map: dict[Tuple[int, int], int] = {}
    bottom_vertex_map: dict[Tuple[int, int], int] = {}
    
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
        
        # Bottom face vertices (z = -base_height)
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
                vertices.append((cx * ps, cy * ps, -base_height))
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
