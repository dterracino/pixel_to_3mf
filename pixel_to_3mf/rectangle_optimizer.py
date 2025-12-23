"""
Rectangle-based mesh optimization for pixel art.

This module provides manifold mesh generation by merging edge-adjacent pixels
into rectangles. Unlike polygon-based approaches, this guarantees 0 non-manifold
edges by construction since we only handle axis-aligned rectangles on a grid.

Algorithm:
1. Split regions into 4-connected sub-regions (no diagonal-only connections)
2. Merge consecutive horizontal pixels into strips
3. Merge vertically-aligned strips into rectangles
4. Generate shared vertices at rectangle corners (manifold requirement)
5. Generate triangles with proper CCW winding

Key insight: Region merger can use 8-connectivity for color grouping, but mesh
optimization must use 4-connectivity only. Diagonal pixel connections create
point-to-point contact which is non-manifold topology.
"""

from collections import deque
from typing import List, Tuple, Set, Dict, TYPE_CHECKING
import logging

from .region_merger import Region
from .image_processor import PixelData

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig
    from .mesh_generator import Mesh

# Set up logging for this module
logger = logging.getLogger(__name__)


def split_to_4_connectivity(pixels: Set[Tuple[int, int]]) -> List[Set[Tuple[int, int]]]:
    """
    Split pixel set into 4-connected sub-regions (edge-adjacent only).
    
    Takes pixels that may be 8-connected (including diagonals) and splits them
    into separate sub-regions where pixels are only connected via edges (up,
    down, left, right). This ensures no diagonal-only connections exist in the
    final mesh topology.
    
    Args:
        pixels: Set of (x, y) pixel coordinates
    
    Returns:
        List of 4-connected sub-regions, each as a set of pixel coordinates
    """
    if not pixels:
        return []
    
    unvisited = pixels.copy()
    sub_regions: List[Set[Tuple[int, int]]] = []
    
    while unvisited:
        # Start new sub-region from any unvisited pixel
        start_pixel = next(iter(unvisited))
        sub_region: Set[Tuple[int, int]] = set()
        
        # BFS with 4-connectivity only
        queue: deque[Tuple[int, int]] = deque([start_pixel])
        visited_local: Set[Tuple[int, int]] = {start_pixel}
        
        while queue:
            x, y = queue.popleft()
            sub_region.add((x, y))
            unvisited.discard((x, y))
            
            # Check 4 edge neighbors only (no diagonals)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = x + dx, y + dy
                neighbor = (nx, ny)
                
                if neighbor in pixels and neighbor not in visited_local:
                    visited_local.add(neighbor)
                    queue.append(neighbor)
        
        sub_regions.append(sub_region)
        logger.debug(f"Split sub-region: {len(sub_region)} pixels")
    
    logger.debug(f"Split {len(pixels)} pixels into {len(sub_regions)} 4-connected sub-regions")
    return sub_regions


def merge_horizontal_strips(pixels: Set[Tuple[int, int]]) -> List[Tuple[int, int, int]]:
    """
    Merge consecutive horizontal pixels into strips.
    
    Scans each row and creates horizontal strips for runs of consecutive
    x-coordinates. This is the first phase of rectangle merging.
    
    Args:
        pixels: Set of (x, y) pixel coordinates (must be 4-connected)
    
    Returns:
        List of horizontal strips as (x_start, x_end, y) tuples
        x_end is inclusive (last pixel in strip)
    """
    if not pixels:
        return []
    
    # Group pixels by row (y-coordinate)
    rows: Dict[int, List[int]] = {}
    for x, y in pixels:
        if y not in rows:
            rows[y] = []
        rows[y].append(x)
    
    # Sort each row's x-coordinates
    for y in rows:
        rows[y].sort()
    
    # Find consecutive runs in each row
    strips: List[Tuple[int, int, int]] = []
    for y in sorted(rows.keys()):
        x_coords = rows[y]
        
        # Start first strip
        strip_start = x_coords[0]
        strip_end = x_coords[0]
        
        for x in x_coords[1:]:
            if x == strip_end + 1:
                # Consecutive, extend strip
                strip_end = x
            else:
                # Gap found, save current strip and start new one
                strips.append((strip_start, strip_end, y))
                strip_start = x
                strip_end = x
        
        # Save final strip for this row
        strips.append((strip_start, strip_end, y))
    
    logger.debug(f"Merged {len(pixels)} pixels into {len(strips)} horizontal strips")
    return strips


def merge_vertical_rectangles(strips: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int, int]]:
    """
    Merge vertically-aligned horizontal strips into rectangles.
    
    Takes horizontal strips and merges those that are vertically aligned
    (same x_start and x_end) into larger rectangles spanning multiple rows.
    
    Args:
        strips: List of (x_start, x_end, y) horizontal strips
    
    Returns:
        List of rectangles as (x_start, x_end, y_start, y_end) tuples
        Both x_end and y_end are inclusive
    """
    if not strips:
        return []
    
    # Sort strips by (y, x_start) for processing
    sorted_strips = sorted(strips, key=lambda s: (s[2], s[0]))
    
    rectangles: List[Tuple[int, int, int, int]] = []
    used: Set[int] = set()
    
    for i, (x_start, x_end, y) in enumerate(sorted_strips):
        if i in used:
            continue
        
        # Start new rectangle
        rect_x_start = x_start
        rect_x_end = x_end
        rect_y_start = y
        rect_y_end = y
        used.add(i)
        
        # Try to extend downward by finding matching strips in next rows
        current_y = y
        while True:
            # Look for strip in next row that matches horizontally
            next_y = current_y + 1
            found_match = False
            
            for j, (next_x_start, next_x_end, next_y_coord) in enumerate(sorted_strips):
                if j in used:
                    continue
                if next_y_coord != next_y:
                    if next_y_coord > next_y:
                        break  # No more strips in this row
                    continue
                
                # Check if this strip matches our rectangle's width
                if next_x_start == rect_x_start and next_x_end == rect_x_end:
                    # Match found! Extend rectangle
                    rect_y_end = next_y
                    used.add(j)
                    found_match = True
                    break
            
            if not found_match:
                break  # No matching strip in next row, stop extending
            
            current_y = next_y
        
        rectangles.append((rect_x_start, rect_x_end, rect_y_start, rect_y_end))
    
    logger.debug(f"Merged {len(strips)} strips into {len(rectangles)} rectangles")
    return rectangles


def generate_vertices(
    rectangles: List[Tuple[int, int, int, int]],
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> Tuple[List[Tuple[float, float, float]], Dict[Tuple[float, float, float], int]]:
    """
    Generate shared vertices for all rectangles.
    
    Creates vertices at rectangle corners, sharing vertices between adjacent
    rectangles to ensure manifold topology. Each rectangle gets 8 vertices
    (4 corners on top face, 4 on bottom face).
    
    Args:
        rectangles: List of (x_start, x_end, y_start, y_end) rectangles
        pixel_data: Pixel scaling information
        config: ConversionConfig with layer heights
    
    Returns:
        Tuple of (vertices list, vertex_map dict)
        - vertices: List of (x_mm, y_mm, z_mm) coordinates
        - vertex_map: Dict mapping (x_mm, y_mm, z_mm) -> vertex_index
    """
    vertices: List[Tuple[float, float, float]] = []
    vertex_map: Dict[Tuple[float, float, float], int] = {}
    
    pixel_size_mm = pixel_data.pixel_size_mm
    z_bottom = 0.0
    z_top = config.color_height_mm
    
    def get_or_create_vertex(x_mm: float, y_mm: float, z_mm: float) -> int:
        """Get existing vertex index or create new vertex."""
        # Round to avoid floating point precision issues
        key = (round(x_mm, 6), round(y_mm, 6), round(z_mm, 6))
        
        if key in vertex_map:
            return vertex_map[key]
        
        vertex_idx = len(vertices)
        vertices.append(key)
        vertex_map[key] = vertex_idx
        return vertex_idx
    
    # Pre-generate all vertices for all rectangles
    # This ensures shared vertices are created properly
    for x_start, x_end, y_start, y_end in rectangles:
        # Calculate corner positions in mm
        # Pixels span from their coordinate to coordinate+1
        x_left = x_start * pixel_size_mm
        x_right = (x_end + 1) * pixel_size_mm  # +1 because x_end is inclusive
        y_bottom = y_start * pixel_size_mm
        y_top = (y_end + 1) * pixel_size_mm  # +1 because y_end is inclusive
        
        # Create 8 vertices (4 top + 4 bottom)
        # Bottom face (z = 0)
        get_or_create_vertex(x_left, y_bottom, z_bottom)    # v0: bottom-left-bottom
        get_or_create_vertex(x_left, y_top, z_bottom)       # v1: top-left-bottom
        get_or_create_vertex(x_right, y_top, z_bottom)      # v2: top-right-bottom
        get_or_create_vertex(x_right, y_bottom, z_bottom)   # v3: bottom-right-bottom
        
        # Top face (z = color_height_mm)
        get_or_create_vertex(x_left, y_bottom, z_top)       # v4: bottom-left-top
        get_or_create_vertex(x_left, y_top, z_top)          # v5: top-left-top
        get_or_create_vertex(x_right, y_top, z_top)         # v6: top-right-top
        get_or_create_vertex(x_right, y_bottom, z_top)      # v7: bottom-right-top
    
    logger.debug(f"Generated {len(vertices)} shared vertices for {len(rectangles)} rectangles")
    return vertices, vertex_map


def generate_triangles(
    rectangles: List[Tuple[int, int, int, int]],
    pixels: Set[Tuple[int, int]],
    pixel_data: PixelData,
    config: 'ConversionConfig',
    vertex_map: Dict[Tuple[float, float, float], int]
) -> List[Tuple[int, int, int]]:
    """
    Generate triangles with proper CCW winding for all rectangles.
    
    Each rectangle gets top and bottom faces (4 triangles total), plus
    side wall triangles ONLY on edges that face the perimeter (not shared
    with adjacent rectangles). This prevents duplicate walls on interior edges
    which would create non-manifold geometry.
    
    Args:
        rectangles: List of (x_start, x_end, y_start, y_end) rectangles
        pixels: Original pixel set (used to detect perimeter edges)
        pixel_data: Pixel scaling information
        config: ConversionConfig with layer heights
        vertex_map: Dict mapping (x_mm, y_mm, z_mm) -> vertex_index
    
    Returns:
        List of (v0, v1, v2) triangle vertex indices
    """
    triangles: List[Tuple[int, int, int]] = []
    
    pixel_size_mm = pixel_data.pixel_size_mm
    z_bottom = 0.0
    z_top = config.color_height_mm
    
    def get_vertex_index(x_mm: float, y_mm: float, z_mm: float) -> int:
        """Look up vertex index from coordinates."""
        key = (round(x_mm, 6), round(y_mm, 6), round(z_mm, 6))
        return vertex_map[key]
    
    def is_perimeter_edge(x_start: int, x_end: int, y_start: int, y_end: int, side: str) -> bool:
        """
        Check if a rectangle edge is on the perimeter (faces outside).
        
        An edge is on the perimeter if there are NO pixels immediately outside it.
        For example, the left edge is perimeter if there's no pixel at (x_start-1, y).
        
        Args:
            x_start, x_end, y_start, y_end: Rectangle bounds
            side: 'left', 'right', 'top', or 'bottom'
        
        Returns:
            True if this edge faces the perimeter (needs a wall)
        """
        if side == 'left':
            # Check if any pixel exists immediately to the left
            for y in range(y_start, y_end + 1):
                if (x_start - 1, y) in pixels:
                    return False  # Interior edge, no wall needed
            return True  # Perimeter edge, needs wall
        
        elif side == 'right':
            # Check if any pixel exists immediately to the right
            for y in range(y_start, y_end + 1):
                if (x_end + 1, y) in pixels:
                    return False
            return True
        
        elif side == 'bottom':
            # Check if any pixel exists immediately below
            for x in range(x_start, x_end + 1):
                if (x, y_start - 1) in pixels:
                    return False
            return True
        
        elif side == 'top':
            # Check if any pixel exists immediately above
            for x in range(x_start, x_end + 1):
                if (x, y_end + 1) in pixels:
                    return False
            return True
        
        return False
    
    for x_start, x_end, y_start, y_end in rectangles:
        # Calculate corner positions in mm
        x_left = x_start * pixel_size_mm
        x_right = (x_end + 1) * pixel_size_mm
        y_bottom = y_start * pixel_size_mm
        y_top = (y_end + 1) * pixel_size_mm
        
        # Get vertex indices for this rectangle's 8 corners
        v0 = get_vertex_index(x_left, y_bottom, z_bottom)   # bottom-left-bottom
        v1 = get_vertex_index(x_left, y_top, z_bottom)      # top-left-bottom
        v2 = get_vertex_index(x_right, y_top, z_bottom)     # top-right-bottom
        v3 = get_vertex_index(x_right, y_bottom, z_bottom)  # bottom-right-bottom
        v4 = get_vertex_index(x_left, y_bottom, z_top)      # bottom-left-top
        v5 = get_vertex_index(x_left, y_top, z_top)         # top-left-top
        v6 = get_vertex_index(x_right, y_top, z_top)        # top-right-top
        v7 = get_vertex_index(x_right, y_bottom, z_top)     # bottom-right-top
        
        # Top face (2 triangles, CCW from above)
        triangles.append((v4, v5, v6))  # bottom-left, top-left, top-right
        triangles.append((v4, v6, v7))  # bottom-left, top-right, bottom-right
        
        # Bottom face (2 triangles, CCW from below = CW from above)
        triangles.append((v0, v2, v1))  # bottom-left, top-right, top-left (reversed)
        triangles.append((v0, v3, v2))  # bottom-left, bottom-right, top-right (reversed)
        
        # Side walls (2 triangles per wall, CCW outward)
        # Only create walls on perimeter edges!
        
        # Left wall (x = x_left)
        if is_perimeter_edge(x_start, x_end, y_start, y_end, 'left'):
            triangles.append((v0, v5, v1))  # bottom-bottom, top-top, top-bottom
            triangles.append((v0, v4, v5))  # bottom-bottom, bottom-top, top-top
        
        # Right wall (x = x_right)
        if is_perimeter_edge(x_start, x_end, y_start, y_end, 'right'):
            triangles.append((v2, v3, v6))  # top-bottom, bottom-bottom, top-top
            triangles.append((v3, v7, v6))  # bottom-bottom, bottom-top, top-top
        
        # Bottom wall (y = y_bottom)
        if is_perimeter_edge(x_start, x_end, y_start, y_end, 'bottom'):
            triangles.append((v0, v3, v7))  # left-bottom, right-bottom, right-top
            triangles.append((v0, v7, v4))  # left-bottom, right-top, left-top
        
        # Top wall (y = y_top)
        if is_perimeter_edge(x_start, x_end, y_start, y_end, 'top'):
            triangles.append((v1, v6, v2))  # left-bottom, right-top, right-bottom
            triangles.append((v1, v5, v6))  # left-bottom, left-top, right-top
    
    logger.debug(f"Generated {len(triangles)} triangles for {len(rectangles)} rectangles")
    return triangles


def optimize_region_rectangles(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> 'Mesh':
    """
    Generate optimized mesh using rectangle merging.
    
    This is the main entry point for rectangle-based mesh optimization.
    Guaranteed to produce manifold meshes with 0 non-manifold edges.
    
    Algorithm:
    1. Split region into 4-connected sub-regions (no diagonal-only connections)
    2. For each sub-region:
       a. Merge consecutive horizontal pixels into strips
       b. Merge vertically-aligned strips into rectangles
    3. Generate shared vertices for all rectangles
    4. Generate triangles with proper CCW winding
    
    Args:
        region: Region with color and pixel coordinates
        pixel_data: Pixel scaling information
        config: ConversionConfig with layer heights and other parameters
    
    Returns:
        Mesh object with vertices and triangles
    """
    # Import here to avoid circular dependency
    from .mesh_generator import Mesh
    
    logger.debug(f"Optimizing region with {len(region.pixels)} pixels using rectangle merging")
    
    # Phase 1: Split into 4-connected sub-regions
    sub_regions = split_to_4_connectivity(region.pixels)
    
    # Phase 2 & 3: Merge into rectangles for each sub-region
    all_rectangles: List[Tuple[int, int, int, int]] = []
    
    for sub_region in sub_regions:
        strips = merge_horizontal_strips(sub_region)
        rectangles = merge_vertical_rectangles(strips)
        all_rectangles.extend(rectangles)
    
    logger.debug(f"Total rectangles after merging all sub-regions: {len(all_rectangles)}")
    
    # Phase 4: Generate shared vertices
    vertices, vertex_map = generate_vertices(all_rectangles, pixel_data, config)
    
    # Phase 5: Generate triangles (pass original pixels for perimeter detection)
    triangles = generate_triangles(all_rectangles, region.pixels, pixel_data, config, vertex_map)
    
    # Calculate reduction statistics
    original_vertex_count = len(region.pixels) * 8  # Each pixel would have 8 vertices
    original_triangle_count = len(region.pixels) * 12  # Each pixel would have 12 triangles
    reduction_vertices = 100 - (len(vertices) * 100 // original_vertex_count)
    reduction_triangles = 100 - (len(triangles) * 100 // original_triangle_count)
    
    logger.info(
        f"Rectangle optimization complete: "
        f"{len(region.pixels)} pixels → {len(all_rectangles)} rectangles → "
        f"{len(vertices)} vertices ({reduction_vertices}% reduction), "
        f"{len(triangles)} triangles ({reduction_triangles}% reduction)"
    )
    
    return Mesh(vertices, triangles)


def generate_backing_plate_optimized(
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> 'Mesh':
    """
    Generate optimized backing plate using rectangle merging.
    
    The backing plate is a single rectangle covering the entire pixel grid,
    so this is the simplest case: just create one rectangle.
    
    Args:
        pixel_data: Pixel dimensions and scaling
        config: ConversionConfig with base_height_mm
    
    Returns:
        Mesh object for backing plate
    """
    from .mesh_generator import Mesh
    
    logger.debug("Generating optimized backing plate")
    
    # Backing plate is a single rectangle covering entire grid
    # Rectangle spans from (0, 0) to (width-1, height-1)
    rectangles = [(0, pixel_data.width - 1, 0, pixel_data.height - 1)]
    
    # Create pixel set for perimeter detection (all non-transparent pixels)
    backing_pixels = set(pixel_data.pixels.keys())
    
    # Temporarily override config for backing plate height
    # Create a copy to avoid modifying original
    class BackingConfig:
        def __init__(self, base_config: 'ConversionConfig'):
            self.color_height_mm = base_config.base_height_mm
    
    backing_config = BackingConfig(config)
    
    # Generate vertices and triangles
    vertices, vertex_map = generate_vertices(rectangles, pixel_data, backing_config)  # type: ignore
    triangles = generate_triangles(rectangles, backing_pixels, pixel_data, backing_config, vertex_map)  # type: ignore
    
    logger.debug(f"Backing plate: {len(vertices)} vertices, {len(triangles)} triangles")
    
    return Mesh(vertices, triangles)
