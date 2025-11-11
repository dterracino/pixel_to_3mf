"""
Polygon-based mesh optimization using shapely and triangle.

This module provides optimized mesh generation by merging pixel squares
into polygons and triangulating them efficiently. This is a second processing
path alongside the original per-pixel mesh generation - both approaches
produce manifold meshes with identical visual results.

The optimization reduces vertex and triangle counts by 50-90% for typical
pixel art while maintaining all manifold properties.
"""

from collections import deque
from typing import List, Tuple, Set, Optional, Dict, TYPE_CHECKING, cast, Sequence
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.ops import unary_union
import triangle as tr
import logging

from .region_merger import Region
from .image_processor import PixelData

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig
    from .mesh_generator import Mesh

# Set up logging for this module
# Note: Level will be configured by the application (see cli.py)
logger = logging.getLogger(__name__)

# Module-level statistics for tracking optimization results
# Reset at the start of each conversion
_optimization_stats = {
    'total_regions': 0,
    'optimized_success': 0,
    'fallback_not_4_connected': 0,
    'fallback_invalid_polygon': 0,
    'fallback_triangulation_failed': 0,
    'fallback_other_error': 0
}


def reset_optimization_stats() -> None:
    """Reset optimization statistics for a new conversion."""
    global _optimization_stats
    _optimization_stats = {
        'total_regions': 0,
        'optimized_success': 0,
        'fallback_not_4_connected': 0,
        'fallback_invalid_polygon': 0,
        'fallback_triangulation_failed': 0,
        'fallback_other_error': 0
    }


def get_optimization_stats() -> Dict[str, int]:
    """Get current optimization statistics."""
    return _optimization_stats.copy()


def log_optimization_summary() -> None:
    """Log summary of optimization results."""
    total = _optimization_stats['total_regions']
    optimized = _optimization_stats['optimized_success']
    fallback_total = (
        _optimization_stats['fallback_not_4_connected'] +
        _optimization_stats['fallback_invalid_polygon'] +
        _optimization_stats['fallback_triangulation_failed'] +
        _optimization_stats['fallback_other_error']
    )
    
    if total == 0:
        return  # No regions processed
    
    logger.info("=" * 70)
    logger.info("OPTIMIZATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total regions processed: {total}")
    logger.info(f"Successfully optimized: {optimized} ({optimized*100//total}%)")
    logger.info(f"Fallback to original: {fallback_total} ({fallback_total*100//total}%)")
    
    if _optimization_stats['fallback_not_4_connected'] > 0:
        logger.info(f"  - Not 4-connected: {_optimization_stats['fallback_not_4_connected']}")
    if _optimization_stats['fallback_invalid_polygon'] > 0:
        logger.info(f"  - Invalid polygon: {_optimization_stats['fallback_invalid_polygon']}")
    if _optimization_stats['fallback_triangulation_failed'] > 0:
        logger.info(f"  - Triangulation failed: {_optimization_stats['fallback_triangulation_failed']}")
    if _optimization_stats['fallback_other_error'] > 0:
        logger.info(f"  - Other errors: {_optimization_stats['fallback_other_error']}")
    logger.info("=" * 70)



def _is_4_connected(pixels: Set[Tuple[int, int]]) -> bool:
    """
    Check if all pixels in the set are 4-connected (edge-sharing).
    
    This is critical for polygon optimization! Pixels that are only
    diagonally connected (8-connected but not 4-connected) will form
    separate polygon components when treated as squares, causing the
    optimization to fail.
    
    Uses BFS to traverse the pixel set using only 4-connectivity
    (up/down/left/right). If we can reach all pixels, they're all
    4-connected. If we can't, some are only diagonally connected.
    
    Args:
        pixels: Set of (x, y) pixel coordinates
    
    Returns:
        True if all pixels are reachable via 4-connected neighbors,
        False if some pixels are only diagonally connected
    """
    if not pixels:
        return True
    
    # Start BFS from arbitrary pixel
    visited: Set[Tuple[int, int]] = set()
    start = next(iter(pixels))
    # Using deque for O(1) popleft() instead of list.pop(0) which is O(n)
    queue: deque[Tuple[int, int]] = deque([start])
    visited.add(start)
    
    while queue:
        x, y = queue.popleft()
        
        # Check only 4-connected neighbors (edge-sharing)
        neighbors_4 = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        for nx, ny in neighbors_4:
            if (nx, ny) in pixels and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
    
    # If we visited all pixels, they're all 4-connected
    is_connected = len(visited) == len(pixels)
    
    if not is_connected:
        logger.debug(f"Pixel set is NOT 4-connected: visited {len(visited)}/{len(pixels)} pixels")
    
    return is_connected


def pixels_to_polygon(
    pixels: Set[Tuple[int, int]], 
    pixel_size_mm: float
) -> Polygon:
    """
    Convert set of pixels to shapely Polygon by unioning pixel squares.
    
    Takes a set of pixel coordinates and creates a merged polygon by
    treating each pixel as a square and using shapely's unary_union to
    merge them all together. This handles complex shapes including those
    with holes automatically.
    
    Args:
        pixels: Set of (x, y) pixel coordinates
        pixel_size_mm: Size of each pixel in millimeters
    
    Returns:
        shapely.geometry.Polygon representing the merged region
    
    Raises:
        ValueError: If the resulting polygon is invalid, if pixels set is empty,
                   or if the union produces multiple disconnected parts
    """
    logger.debug(f"Converting {len(pixels)} pixels to polygon (pixel_size={pixel_size_mm}mm)")
    
    if not pixels:
        raise ValueError("Cannot create polygon from empty pixel set")
    
    # Create a square box for each pixel
    pixel_squares = []
    for x, y in pixels:
        # Create a box from (x, y) to (x+1, y+1) scaled by pixel size
        square = box(
            x * pixel_size_mm,
            y * pixel_size_mm,
            (x + 1) * pixel_size_mm,
            (y + 1) * pixel_size_mm
        )
        pixel_squares.append(square)
    
    logger.debug(f"Created {len(pixel_squares)} pixel squares, performing union...")
    
    # Union all squares into a single polygon (or MultiPolygon)
    merged = unary_union(pixel_squares)
    
    logger.debug(f"Union result type: {type(merged).__name__}")
    
    # Handle MultiPolygon case - this indicates disconnected components
    if isinstance(merged, MultiPolygon):
        num_parts = len(merged.geoms)
        logger.warning(f"Got MultiPolygon with {num_parts} disconnected parts")
        
        # CRITICAL FIX: Do not discard parts! A MultiPolygon means the region
        # has disconnected components, which happens when flood-fill found pixels
        # that appear connected but create separate polygons after union.
        # This is a problematic geometry for optimization - fall back instead.
        raise ValueError(
            f"Region produced {num_parts} disconnected polygon parts. "
            f"This geometry is not suitable for optimization."
        )
    
    # At this point, merged must be a Polygon (not MultiPolygon)
    if not isinstance(merged, Polygon):
        raise ValueError(f"Expected Polygon but got {type(merged).__name__}")
    
    # Validate the polygon
    if not merged.is_valid:
        error_msg = merged.explain_validity() if hasattr(merged, 'explain_validity') else "unknown reason"  # type: ignore[attr-defined]
        raise ValueError(f"Invalid polygon created: {error_msg}")
    
    # Log polygon characteristics
    num_holes = len(list(merged.interiors))
    logger.debug(f"Polygon created: exterior={len(merged.exterior.coords)} vertices, "
                f"holes={num_holes}, area={merged.area:.2f}mm²")
    
    # Note: Additional validation of hole count happens in _validate_polygon_for_triangulation()
    # to keep validation logic centralized
    
    return merged


def _validate_polygon_for_triangulation(poly: Polygon) -> Tuple[bool, str]:
    """
    Validate polygon geometry before passing to triangle library.
    
    This helps prevent segmentation faults by detecting problematic
    configurations before they reach the C library.
    
    Args:
        poly: Polygon to validate
        
    Returns:
        (bool, str): (is_valid, error_message)
                     If valid: (True, "")
                     If invalid: (False, "reason for failure")
    """
    # Check basic validity
    if not poly.is_valid:
        return (False, f"Invalid polygon: {poly.explain_validity()}")  # type: ignore[attr-defined]
    
    # Check for degenerate cases
    if poly.area <= 0:
        return (False, f"Polygon has zero or negative area: {poly.area}")
    
    # Check exterior ring
    exterior_coords = list(poly.exterior.coords[:-1])
    if len(exterior_coords) < 3:
        return (False, f"Polygon exterior has fewer than 3 vertices: {len(exterior_coords)}")
    
    # Check for too many vertices (complex geometries more likely to segfault)
    if len(exterior_coords) > 100:
        return (False, f"Polygon exterior has too many vertices ({len(exterior_coords)}). This geometry is not suitable for optimization.")
    
    # Check for collinear points in exterior (can cause triangulation issues)
    # Simple heuristic: if all points have very similar coordinates, it might be degenerate
    if len(exterior_coords) > 2:
        xs = [c[0] for c in exterior_coords]
        ys = [c[1] for c in exterior_coords]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        
        # If polygon is essentially a line (very thin), it's problematic
        if x_range < 1e-6 or y_range < 1e-6:
            return (False, f"Polygon is degenerate (too thin): x_range={x_range}, y_range={y_range}")
    
    # Check holes
    num_holes = len(list(poly.interiors))
    for i, interior in enumerate(poly.interiors):
        hole_coords = list(interior.coords[:-1])
        if len(hole_coords) < 3:
            return (False, f"Hole {i} has fewer than 3 vertices: {len(hole_coords)}")
        # Check hole complexity
        if len(hole_coords) > 50:
            return (False, f"Hole {i} has too many vertices ({len(hole_coords)}). This geometry is not suitable for optimization.")
    
    # Stricter check: if the polygon has holes AND complex exterior, reject it
    # Empirical observation: polygons with holes and > 20 exterior vertices often segfault
    if num_holes > 0 and len(exterior_coords) > 20:
        return (False, f"Polygon has {num_holes} holes and complex exterior ({len(exterior_coords)} vertices). This geometry is not suitable for optimization.")
    
    # Additional check: if the polygon has many holes, it might be problematic
    if num_holes > 5:
        logger.warning(f"Polygon has {num_holes} holes, which may cause triangulation issues")
        return (False, f"Polygon has too many holes ({num_holes}). This geometry is not suitable for optimization.")
    
    logger.debug(f"Polygon validation passed: exterior={len(exterior_coords)} vertices, "
                f"holes={num_holes}")
    
    # All checks passed!
    return (True, "")


def triangulate_polygon_2d(poly: Polygon) -> Tuple[List[Tuple[float, float]], List[Tuple[int, int, int]]]:
    """
    Triangulate 2D polygon using constrained Delaunay triangulation.
    
    Uses the triangle library to create a quality triangulation of the polygon.
    Properly handles holes (interior rings) in the polygon.
    
    CRITICAL: Triangle library requires:
    - CCW (counter-clockwise) winding for exterior
    - CW (clockwise) winding for holes
    - Hole points must be inside the hole region (but not on boundary)
    
    Shapely's unary_union may produce polygons with either winding orientation,
    so we check and fix as needed.
    
    Args:
        poly: shapely.geometry.Polygon to triangulate
    
    Returns:
        Tuple of (vertices, triangles) where:
        - vertices: List of (x, y) coordinates
        - triangles: List of (v0, v1, v2) vertex index triples (CCW winding)
    
    Raises:
        RuntimeError: If triangulation fails
        ValueError: If polygon has problematic characteristics
    """
    import numpy as np
    
    logger.debug(f"Starting triangulation of polygon with {len(poly.exterior.coords)-1} exterior vertices")
    
    # Validate polygon before attempting triangulation
    is_valid, error_msg = _validate_polygon_for_triangulation(poly)
    if not is_valid:
        logger.error(f"Polygon validation failed: {error_msg}")
        raise ValueError(error_msg)
    
    def is_ccw(coords):
        """Check if coordinates are counter-clockwise using shoelace formula."""
        area = 0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        return area > 0
    
    # Extract exterior coordinates (remove duplicate last point)
    exterior_coords = list(poly.exterior.coords[:-1])
    
    # Triangle library REQUIRES CCW winding for exterior
    was_reversed = False
    if not is_ccw(exterior_coords):
        exterior_coords = list(reversed(exterior_coords))
        was_reversed = True
    
    logger.debug(f"Exterior winding: {'CCW' if not was_reversed else 'CW->CCW (reversed)'}")
    
    # Convert to numpy arrays for triangle library (more reliable)
    all_vertices = np.array(exterior_coords, dtype=np.float64)
    exterior_segments = np.array(
        [[i, (i + 1) % len(exterior_coords)] for i in range(len(exterior_coords))],
        dtype=np.int32
    )
    
    # Handle holes if present
    hole_points_list = []
    all_segments = [exterior_segments]
    
    for hole_idx, interior in enumerate(poly.interiors):
        logger.debug(f"Processing hole {hole_idx+1}/{len(list(poly.interiors))}")
        hole_coords = list(interior.coords[:-1])
        
        # Triangle library REQUIRES CW winding for holes (opposite of exterior)
        if is_ccw(hole_coords):
            hole_coords = list(reversed(hole_coords))
        
        # Add hole vertices
        hole_vertices = np.array(hole_coords, dtype=np.float64)
        offset = len(all_vertices)
        all_vertices = np.vstack([all_vertices, hole_vertices])
        
        # Add hole segments
        hole_segments = np.array(
            [[offset + i, offset + (i + 1) % len(hole_coords)] for i in range(len(hole_coords))],
            dtype=np.int32
        )
        all_segments.append(hole_segments)
        
        # Calculate hole point - must be inside the hole area
        # IMPROVED: Use representative_point() which is guaranteed to be inside
        # the geometry, falling back to centroid if needed
        from shapely.geometry import LinearRing
        hole_ring = LinearRing(hole_coords)
        hole_poly = Polygon(hole_ring)
        
        # Use representative_point for better reliability
        hole_point = hole_poly.representative_point()
        hole_center_x, hole_center_y = hole_point.x, hole_point.y
        
        # Validate that the point is actually inside
        if not hole_poly.contains(hole_point):
            # Fallback: use simple centroid
            logger.warning(f"representative_point not inside hole {hole_idx+1}, using centroid")
            hole_center_x = sum(p[0] for p in hole_coords) / len(hole_coords)
            hole_center_y = sum(p[1] for p in hole_coords) / len(hole_coords)
        
        hole_points_list.append([hole_center_x, hole_center_y])
        
        logger.debug(f"Hole {hole_idx+1} center: ({hole_center_x:.2f}, {hole_center_y:.2f})")
    
    # Combine all segments
    all_segments_combined = np.vstack(all_segments)
    
    logger.debug(f"Prepared triangulation input: {len(all_vertices)} vertices, "
                f"{len(all_segments_combined)} segments, {len(hole_points_list)} holes")
    
    # Prepare input for triangle library
    triangle_input = {
        'vertices': all_vertices,
        'segments': all_segments_combined
    }
    
    # Add hole points if we have holes
    if hole_points_list:
        triangle_input['holes'] = np.array(hole_points_list, dtype=np.float64)
    
    # Triangulate with basic PSLG
    # 'p' = Planar Straight Line Graph (respects boundary edges and holes)
    # 'Q' = Quiet mode (suppress output)
    # 'Y' = Prohibit Steiner points on boundaries (more reliable with holes)
    
    logger.debug("Calling triangle library for triangulation...")
    try:
        logger.debug("Attempting triangulation with 'pQY' flags...")
        result = tr.triangulate(triangle_input, 'pQY')
        logger.debug("Triangulation with 'pQY' succeeded")
    except Exception as e:
        logger.warning(f"Triangulation with 'pQY' failed: {e}, trying 'pQ'...")
        # If triangulation with holes fails, try without the Y flag
        try:
            result = tr.triangulate(triangle_input, 'pQ')
            logger.debug("Triangulation with 'pQ' succeeded")
        except Exception as e2:
            logger.error(f"Both triangulation attempts failed: primary={e}, fallback={e2}")
            raise RuntimeError(f"Triangulation failed: {e}, retry also failed: {e2}")
    
    # Extract results
    vertices_2d = [tuple(v) for v in result['vertices']]
    triangles_2d = [tuple(t) for t in result['triangles']]
    
    logger.debug(f"Triangulation complete: {len(vertices_2d)} vertices, {len(triangles_2d)} triangles")
    
    return vertices_2d, triangles_2d


def ensure_ccw_winding_2d(
    vertices_2d: List[Tuple[float, float]],
    triangles_2d: List[Tuple[int, int, int]]
) -> List[Tuple[int, int, int]]:
    """
    Ensure all 2D triangles have counter-clockwise winding.
    
    Uses the signed area formula to detect winding direction.
    If a triangle has clockwise winding (negative area), its vertices
    are reversed to make it counter-clockwise.
    
    This is critical for ensuring consistent normals when extruding to 3D!
    Without consistent winding, wall triangles may have inverted normals
    leading to non-manifold edges.
    
    Args:
        vertices_2d: List of (x, y) vertex coordinates
        triangles_2d: List of (v0, v1, v2) vertex index triples
    
    Returns:
        List of triangles with CCW winding guaranteed
    """
    corrected_triangles = []
    reversed_count = 0
    
    for tri in triangles_2d:
        v0 = vertices_2d[tri[0]]
        v1 = vertices_2d[tri[1]]
        v2 = vertices_2d[tri[2]]
        
        # Calculate signed area using cross product
        # Positive area = CCW, Negative area = CW
        signed_area = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v1[1] - v0[1]) * (v2[0] - v0[0])
        
        if signed_area < 0:
            # Triangle is CW - reverse it to make CCW
            corrected_triangles.append((tri[0], tri[2], tri[1]))
            reversed_count += 1
        else:
            # Triangle is already CCW (or degenerate with zero area)
            corrected_triangles.append(tri)
    
    if reversed_count > 0:
        logger.info(f"Corrected {reversed_count} CW triangles to CCW for consistent winding")
    
    return corrected_triangles


def validate_mesh_manifold(mesh: 'Mesh') -> Tuple[bool, List[str]]:
    """
    Validate that a mesh is manifold.
    
    A manifold mesh has every edge shared by exactly 2 triangles.
    This function checks edge usage and reports any non-manifold edges.
    
    Args:
        mesh: Mesh object to validate
    
    Returns:
        Tuple of (is_manifold, list_of_errors)
    """
    from collections import defaultdict
    
    edge_usage = defaultdict(int)
    for tri in mesh.triangles:
        # Create edges as sorted tuples (undirected)
        edges = [
            tuple(sorted([tri[0], tri[1]])),
            tuple(sorted([tri[1], tri[2]])),
            tuple(sorted([tri[2], tri[0]]))
        ]
        for edge in edges:
            edge_usage[edge] += 1
    
    errors = []
    for edge, count in edge_usage.items():
        if count != 2:
            errors.append(f"Edge {edge} used by {count} triangles (should be 2)")
    
    return len(errors) == 0, errors


def extrude_polygon_to_mesh(
    poly: Polygon,
    triangles_2d: List[Tuple[int, int, int]],
    vertices_2d: List[Tuple[float, float]],
    z_bottom: float,
    z_top: float
) -> 'Mesh':
    """
    Extrude 2D triangulated polygon to 3D mesh with top, bottom, and wall faces.
    
    Creates a manifold 3D mesh by:
    1. Creating top face at z_top (CCW from above)
    2. Creating bottom face at z_bottom (CCW from below = reversed)
    3. Creating wall quads around perimeter and holes
    
    All vertices are shared properly to maintain manifold properties.
    
    CRITICAL: Ensures all input triangles have CCW winding before extrusion
    to prevent non-manifold edges from inconsistent normals.
    
    Args:
        poly: Original shapely polygon (for perimeter extraction)
        triangles_2d: List of triangle vertex indices from triangulation
        vertices_2d: List of (x, y) vertices from triangulation
        z_bottom: Z coordinate for bottom face
        z_top: Z coordinate for top face
    
    Returns:
        Mesh object with complete 3D geometry
    """
    # Import at runtime to avoid circular dependency
    from .mesh_generator import Mesh
    
    # CRITICAL FIX: Ensure all 2D triangles have consistent CCW winding
    # This prevents non-manifold issues from mixed winding orders
    triangles_2d = ensure_ccw_winding_2d(vertices_2d, triangles_2d)
    
    vertices_3d: List[Tuple[float, float, float]] = []
    triangles_3d: List[Tuple[int, int, int]] = []
    
    # ========================================================================
    # Step 1: Create top face vertices and triangles
    # ========================================================================
    top_vertex_map: Dict[int, int] = {}
    for i, (x, y) in enumerate(vertices_2d):
        vertices_3d.append((x, y, z_top))
        top_vertex_map[i] = len(vertices_3d) - 1
    
    # Add top face triangles (CCW winding from above)
    for tri in triangles_2d:
        t0, t1, t2 = tri
        triangles_3d.append((
            top_vertex_map[t0],
            top_vertex_map[t1],
            top_vertex_map[t2]
        ))
    
    # ========================================================================
    # Step 2: Create bottom face vertices and triangles
    # ========================================================================
    bottom_vertex_map: Dict[int, int] = {}
    for i, (x, y) in enumerate(vertices_2d):
        vertices_3d.append((x, y, z_bottom))
        bottom_vertex_map[i] = len(vertices_3d) - 1
    
    # Add bottom face triangles (reversed winding for CCW from below)
    for tri in triangles_2d:
        t0, t1, t2 = tri
        triangles_3d.append((
            bottom_vertex_map[t0],
            bottom_vertex_map[t2],  # Swap t1 and t2 for reversed winding
            bottom_vertex_map[t1]
        ))
    
    # ========================================================================
    # Step 3: Create walls around perimeter
    # ========================================================================
    # Build a map from 2D coordinates to vertex indices for quick lookup
    coord_to_idx: Dict[Tuple[float, float], int] = {}
    for i, (x, y) in enumerate(vertices_2d):
        # Round to avoid floating-point precision issues
        key = (round(x, 6), round(y, 6))
        coord_to_idx[key] = i
    
    # Process exterior perimeter
    # CRITICAL FIX: Ensure perimeter is CCW for correct wall winding
    # shapely's unary_union may produce CW or CCW, we need CCW for outward normals
    perimeter = list(poly.exterior.coords[:-1])
    
    # Check if perimeter is CCW using shoelace formula
    def is_ccw_perimeter(coords):
        area = 0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        return area > 0
    
    if not is_ccw_perimeter(perimeter):
        # Perimeter is CW, reverse it to CCW for correct wall normals
        perimeter = list(reversed(perimeter))
        logger.debug("Reversed CW perimeter to CCW for correct wall winding")
    
    _create_wall_quads(
        perimeter, coord_to_idx, top_vertex_map, bottom_vertex_map,
        triangles_3d, reverse_winding=False
    )
    
    # Process holes (interior rings) - walls with reversed winding
    # Holes should have CW winding (opposite of exterior) for inward normals
    for interior in poly.interiors:
        hole_perimeter = list(interior.coords[:-1])
        
        # Ensure hole perimeter is CW (opposite of exterior CCW)
        if is_ccw_perimeter(hole_perimeter):
            # Hole is CCW, reverse it to CW for correct inward normals
            hole_perimeter = list(reversed(hole_perimeter))
            logger.debug("Reversed CCW hole perimeter to CW for correct wall winding")
        
        _create_wall_quads(
            hole_perimeter, coord_to_idx, top_vertex_map, bottom_vertex_map,
            triangles_3d, reverse_winding=True
        )
    
    return Mesh(vertices=vertices_3d, triangles=triangles_3d)


def _create_wall_quads(
    perimeter: Sequence[Tuple[float, ...]],
    coord_to_idx: Dict[Tuple[float, float], int],
    top_vertex_map: Dict[int, int],
    bottom_vertex_map: Dict[int, int],
    triangles_3d: List[Tuple[int, int, int]],
    reverse_winding: bool
) -> None:
    """
    Helper to create wall quads around a perimeter.
    
    This is extracted to avoid code duplication between exterior and hole walls.
    
    Args:
        perimeter: List of (x, y) coordinates forming the perimeter
        coord_to_idx: Map from rounded coordinates to vertex indices
        top_vertex_map: Map from 2D vertex index to 3D top vertex index
        bottom_vertex_map: Map from 2D vertex index to 3D bottom vertex index
        triangles_3d: List to append wall triangles to (modified in place)
        reverse_winding: If True, reverse triangle winding (for holes)
    """
    for i in range(len(perimeter)):
        p1 = perimeter[i]
        p2 = perimeter[(i + 1) % len(perimeter)]
        
        # Find vertex indices by rounding coordinates
        k1 = (round(p1[0], 6), round(p1[1], 6))
        k2 = (round(p2[0], 6), round(p2[1], 6))
        
        if k1 not in coord_to_idx or k2 not in coord_to_idx:
            # Shouldn't happen, but defensive programming
            continue
        
        idx1 = coord_to_idx[k1]
        idx2 = coord_to_idx[k2]
        
        # Get 3D vertex indices for wall quad
        bl = bottom_vertex_map[idx1]  # bottom-left
        br = bottom_vertex_map[idx2]  # bottom-right
        tl = top_vertex_map[idx1]     # top-left
        tr = top_vertex_map[idx2]     # top-right
        
        # Create two triangles forming the wall quad
        if reverse_winding:
            # Reversed winding for holes (normals point inward)
            triangles_3d.append((bl, tl, br))
            triangles_3d.append((br, tl, tr))
        else:
            # Normal winding for exterior (normals point outward)
            triangles_3d.append((bl, br, tl))
            triangles_3d.append((tl, br, tr))


def generate_region_mesh_optimized(
    region: Region,
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> 'Mesh':
    """
    Optimized mesh generation using polygon merging and triangulation.
    
    This is a drop-in replacement for generate_region_mesh() in mesh_generator.py.
    It produces the same manifold meshes but with significantly fewer vertices
    and triangles (typically 50-90% reduction for pixel art).
    
    Pipeline:
    1. Convert region pixels to shapely Polygon (union of pixel squares)
    2. Validate polygon (must be valid, non-self-intersecting)
    3. Triangulate using triangle library with quality constraints
    4. Extrude to 3D mesh (top face, bottom face, walls)
    5. Fallback to original implementation on any error
    
    Args:
        region: Region object with pixels to mesh
        pixel_data: PixelData with scaling information
        config: ConversionConfig with layer heights and other parameters
    
    Returns:
        Mesh object with optimized geometry
    
    Note:
        Falls back to original implementation instead of raising exceptions.
        This ensures robustness even if edge cases occur.
    """
    logger.info(f"Starting optimized mesh generation for region with {len(region.pixels)} pixels, "
               f"color=RGB{region.color}")
    
    # Track this region
    global _optimization_stats
    _optimization_stats['total_regions'] += 1
    
    try:
        # Step 0: Check if pixels are 4-connected (edge-sharing)
        # If pixels are only diagonally connected (8-connected but not 4-connected),
        # they will form disconnected polygon components, making optimization impossible
        logger.debug("Step 0: Checking pixel connectivity...")
        if not _is_4_connected(region.pixels):
            logger.debug(
                f"Region has pixels that are only diagonally connected. "
                f"Falling back to original implementation."
            )
            # Track fallback reason
            _optimization_stats['fallback_not_4_connected'] += 1
            # Don't warn here - this is an expected condition for 8-connected regions
            # The user chose 8-connectivity for region merging, which is fine
            from .mesh_generator import _generate_region_mesh_original
            return _generate_region_mesh_original(region, pixel_data, config)
        
        # Step 1: Convert pixels to polygon
        logger.debug("Step 1: Converting pixels to polygon...")
        poly = pixels_to_polygon(region.pixels, pixel_data.pixel_size_mm)
        logger.debug(f"Polygon created successfully")
        
        # Step 1.5: Validate polygon (no longer raises exception!)
        is_valid, error_msg = _validate_polygon_for_triangulation(poly)
        
        if not is_valid:
            # Clean single warning, no traceback!
            logger.warning(
                f"Optimized mesh generation failed for region with {len(region.pixels)} pixels: {error_msg}"
            )
            # Track fallback reason
            _optimization_stats['fallback_invalid_polygon'] += 1
            # Note: warnings.warn() removed - it breaks rich console output
            # Import the original implementation to avoid circular dependency
            from .mesh_generator import _generate_region_mesh_original
            return _generate_region_mesh_original(region, pixel_data, config)
        
        # Step 2: Triangulate the polygon
        logger.debug("Step 2: Triangulating polygon...")
        vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
        logger.debug(f"Triangulation successful: {len(vertices_2d)} vertices, {len(triangles_2d)} triangles")
        
        # Step 3: Extrude to 3D mesh
        logger.debug("Step 3: Extruding to 3D mesh...")
        mesh = extrude_polygon_to_mesh(
            poly, 
            triangles_2d, 
            vertices_2d,
            z_bottom=0.0,
            z_top=config.color_height_mm
        )
        logger.debug(f"3D mesh created: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
        
        # Track successful optimization
        _optimization_stats['optimized_success'] += 1
        
        logger.info(f"Optimized mesh generation completed successfully for region")
        return mesh
        
    except Exception as e:
        # Only catch truly unexpected errors
        logger.warning(
            f"Unexpected error during optimization for region with {len(region.pixels)} pixels, "
            f"falling back to original implementation. Error: {e}",
            exc_info=True
        )
        # Track fallback reason
        _optimization_stats['fallback_other_error'] += 1
        # Note: warnings.warn() removed - it breaks rich console output
        
        # Import the original implementation to avoid circular dependency
        from .mesh_generator import _generate_region_mesh_original
        return _generate_region_mesh_original(region, pixel_data, config)


def generate_backing_plate_optimized(
    pixel_data: PixelData,
    config: 'ConversionConfig'
) -> 'Mesh':
    """
    Optimized backing plate generation using polygon approach.
    
    This is a drop-in replacement for generate_backing_plate() in mesh_generator.py.
    Creates the backing plate by merging all non-transparent pixels into a single
    polygon (with holes) and triangulating it.
    
    Args:
        pixel_data: PixelData with all pixel information
        config: ConversionConfig with base height parameter
    
    Returns:
        Mesh object for the backing plate
    
    Note:
        Falls back to original implementation on any error.
    """
    try:
        # Collect all non-transparent pixel coordinates
        all_pixels = set(pixel_data.pixels.keys())
        
        if not all_pixels:
            # No pixels means empty backing plate (shouldn't happen, but defensive)
            from .mesh_generator import Mesh
            return Mesh(vertices=[], triangles=[])
        
        # Step 0: Check if pixels are 4-connected
        # Backing plates can have disconnected parts (sprites with gaps),
        # but if the entire set isn't 4-connected, skip optimization
        if not _is_4_connected(all_pixels):
            logger.debug("Backing plate pixels are not 4-connected, falling back to original")
            from .mesh_generator import _generate_backing_plate_original
            return _generate_backing_plate_original(pixel_data, config)
        
        # Step 1: Convert all pixels to polygon
        poly = pixels_to_polygon(all_pixels, pixel_data.pixel_size_mm)
        
        # Step 1.5: Validate polygon (returns result instead of raising)
        is_valid, error_msg = _validate_polygon_for_triangulation(poly)
        
        if not is_valid:
            logger.warning(f"Optimized backing plate generation failed, falling back to original: {error_msg}")
            # Note: warnings.warn() removed - it breaks rich console output
            # Import the original implementation to avoid circular dependency
            from .mesh_generator import _generate_backing_plate_original
            return _generate_backing_plate_original(pixel_data, config)
        
        # Step 2: Triangulate the polygon
        vertices_2d, triangles_2d = triangulate_polygon_2d(poly)
        
        # Step 3: Extrude to 3D mesh (backing plate goes from -base_height to 0)
        mesh = extrude_polygon_to_mesh(
            poly,
            triangles_2d,
            vertices_2d,
            z_bottom=-config.base_height_mm,
            z_top=0.0
        )
        
        return mesh
        
    except Exception as e:
        # Only catch truly unexpected errors
        logger.warning(f"Unexpected error during backing plate optimization, falling back to original: {e}")
        # Note: warnings.warn() removed - it breaks rich console output
        
        # Import the original implementation to avoid circular dependency
        from .mesh_generator import _generate_backing_plate_original
        return _generate_backing_plate_original(pixel_data, config)
