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
    top_vertex_map: dict[Tuple[int, int, str], int] = {}
    
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
            key = (cx, cy, label)
            if key not in top_vertex_map:
                # Create new vertex at (cx * ps, cy * ps, layer_height)
                top_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, layer_height))
            corner_indices.append(top_vertex_map[key])
        
        # Create 2 triangles for the top face
        # Triangle 1: bl -> br -> tl
        # Triangle 2: br -> tr -> tl
        bl, br, tl, tr = corner_indices
        triangles.append((bl, br, tl))
        triangles.append((br, tr, tl))
    
    # ========================================================================
    # Pass 3: Generate bottom face (z = 0)
    # ========================================================================
    # Same as top face, but at z=0 and with reversed winding (for correct normals)
    
    bottom_vertex_map: dict[Tuple[int, int, str], int] = {}
    
    for x, y in region.pixels:
        corners = [
            (x, y, "bl"),
            (x+1, y, "br"),
            (x, y+1, "tl"),
            (x+1, y+1, "tr"),
        ]
        
        corner_indices = []
        for cx, cy, label in corners:
            key = (cx, cy, label)
            if key not in bottom_vertex_map:
                bottom_vertex_map[key] = len(vertices)
                vertices.append((cx * ps, cy * ps, 0.0))
            corner_indices.append(bottom_vertex_map[key])
        
        # Bottom face triangles (reversed winding!)
        bl, br, tl, tr = corner_indices
        triangles.append((bl, tl, br))  # Note: tl and br swapped vs top face
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
            # We need 4 vertices: bottom-left, bottom-right, top-left, top-right
            
            # Bottom edge vertices (z=0)
            bl_bottom = (x1 * ps, y1 * ps, 0.0)
            br_bottom = (x2 * ps, y2 * ps, 0.0)
            
            # Top edge vertices (z=layer_height)
            tl_top = (x1 * ps, y1 * ps, layer_height)
            tr_top = (x2 * ps, y2 * ps, layer_height)
            
            # Add these 4 vertices
            idx_bl = len(vertices)
            vertices.append(bl_bottom)
            idx_br = len(vertices)
            vertices.append(br_bottom)
            idx_tl = len(vertices)
            vertices.append(tl_top)
            idx_tr = len(vertices)
            vertices.append(tr_top)
            
            # Create 2 triangles for the wall (outward-facing normals)
            # Triangle 1: bl -> tl -> br
            # Triangle 2: br -> tl -> tr
            triangles.append((idx_bl, idx_tl, idx_br))
            triangles.append((idx_br, idx_tl, idx_tr))
    
    return Mesh(vertices=vertices, triangles=triangles)


def generate_backing_plate(
    pixel_data: PixelData,
    base_height: float = BASE_LAYER_HEIGHT_MM
) -> Mesh:
    """
    Generate the solid backing plate that goes under everything.
    
    This is much simpler than the region meshes! We just create a rectangular
    slab that spans the entire image bounds. It goes from z=-base_height to z=0,
    so it sits underneath all the colored regions.
    
    Args:
        pixel_data: Pixel data (for dimensions)
        base_height: Thickness of the backing plate (default: BASE_LAYER_HEIGHT_MM)
    
    Returns:
        A Mesh object for the backing plate
    """
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    
    # The backing plate spans the full image dimensions
    width_mm = pixel_data.model_width_mm
    height_mm = pixel_data.model_height_mm
    
    # 8 vertices for a rectangular box:
    # Bottom face (z = -base_height)
    v0 = (0.0, 0.0, -base_height)
    v1 = (width_mm, 0.0, -base_height)
    v2 = (width_mm, height_mm, -base_height)
    v3 = (0.0, height_mm, -base_height)
    
    # Top face (z = 0)
    v4 = (0.0, 0.0, 0.0)
    v5 = (width_mm, 0.0, 0.0)
    v6 = (width_mm, height_mm, 0.0)
    v7 = (0.0, height_mm, 0.0)
    
    vertices = [v0, v1, v2, v3, v4, v5, v6, v7]
    
    # Now create triangles for all 6 faces of the box
    # Each face is 2 triangles (quad split into triangles)
    
    # Bottom face (z = -base_height) - normal pointing down
    triangles.append((0, 2, 1))
    triangles.append((0, 3, 2))
    
    # Top face (z = 0) - normal pointing up
    triangles.append((4, 5, 6))
    triangles.append((4, 6, 7))
    
    # Side faces (4 walls)
    # Front (y = 0)
    triangles.append((0, 1, 5))
    triangles.append((0, 5, 4))
    
    # Right (x = width_mm)
    triangles.append((1, 2, 6))
    triangles.append((1, 6, 5))
    
    # Back (y = height_mm)
    triangles.append((2, 3, 7))
    triangles.append((2, 7, 6))
    
    # Left (x = 0)
    triangles.append((3, 0, 4))
    triangles.append((3, 4, 7))
    
    return Mesh(vertices=vertices, triangles=triangles)
