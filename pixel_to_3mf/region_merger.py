"""
Region merging module using flood-fill algorithm.

This is where the magic happens! Instead of keeping every single pixel as
its own separate mesh, we group together all connected pixels of the same
color into "regions." This dramatically reduces polygon count and makes
the final model cleaner and easier to slice.

Think of it like the paint bucket tool in Photoshop - we're finding all
the connected areas of the same color! 🎨
"""

from collections import deque
from typing import Dict, List, Set, Tuple, TYPE_CHECKING
from .image_processor import PixelData

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .config import ConversionConfig


class Region:
    """
    A connected group of same-color pixels.
    
    This represents one "blob" of color that will become a single mesh object.
    For example, if you have a red heart shape, all those connected red pixels
    form one Region, even if it's a complex shape!
    """
    
    def __init__(self, color: Tuple[int, int, int], pixels: Set[Tuple[int, int]]):
        """
        Initialize a region.
        
        Args:
            color: RGB color tuple (r, g, b)
            pixels: Set of (x, y) coordinates that make up this region
        """
        self.color = color
        self.pixels = pixels
    
    def __repr__(self) -> str:
        return f"Region(color=RGB{self.color}, pixels={len(self.pixels)})"


def flood_fill(
    start_x: int,
    start_y: int,
    target_color: Tuple[int, int, int],
    pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]],
    visited: Set[Tuple[int, int]],
    connectivity: int = 8
) -> Set[Tuple[int, int]]:
    """
    Perform flood fill to find all connected pixels of the same color.
    
    This is a classic computer science algorithm! We start at one pixel and
    "flood" outward to all adjacent pixels of the same color, marking them
    as we go. We use 8-connectivity by default (includes diagonals) so pixels 
    touching at corners are merged into the same region.
    
    We use an iterative approach with a queue rather than recursion to avoid
    stack overflow on large regions. Python's recursion limit is only ~1000,
    but a region could easily have 10,000+ pixels!
    
    Args:
        start_x, start_y: Starting pixel coordinates
        target_color: RGB color we're looking for
        pixels: Dict of all non-transparent pixels (x,y) -> (r,g,b,a)
        visited: Set of already-processed pixels (we'll add to this)
        connectivity: 0 (no merge), 4 (edge-connected), or 8 (includes diagonals)
    
    Returns:
        Set of (x, y) coordinates in this connected region
    """
    # The region we're building
    region_pixels: Set[Tuple[int, int]] = set()
    
    # Queue of pixels to process (breadth-first search)
    # Using deque for O(1) popleft() instead of list.pop(0) which is O(n)
    queue: deque[Tuple[int, int]] = deque([(start_x, start_y)])
    
    # Mark starting pixel as visited
    visited.add((start_x, start_y))
    
    while queue:
        # Pop the first pixel from queue - O(1) with deque
        x, y = queue.popleft()
        
        # Add it to our region
        region_pixels.add((x, y))
        
        # Connectivity 0 means no merging - just return this single pixel
        if connectivity == 0:
            continue
        
        # Build neighbor list based on connectivity mode
        if connectivity == 8:
            # 8-connectivity: includes diagonals
            # This creates much fewer objects for diagonal patterns
            neighbors = [
                (x + 1, y),      # right
                (x - 1, y),      # left
                (x, y + 1),      # down
                (x, y - 1),      # up
                (x + 1, y + 1),  # diagonal: down-right
                (x - 1, y - 1),  # diagonal: up-left
                (x + 1, y - 1),  # diagonal: up-right
                (x - 1, y + 1),  # diagonal: down-left
            ]
        else:  # connectivity == 4
            # 4-connectivity: edge-connected only
            neighbors = [
                (x + 1, y),  # right
                (x - 1, y),  # left
                (x, y + 1),  # down
                (x, y - 1),  # up
            ]
        
        for nx, ny in neighbors:
            # Skip if already visited
            if (nx, ny) in visited:
                continue
            
            # Skip if this pixel doesn't exist or is transparent
            if (nx, ny) not in pixels:
                continue
            
            # Get the neighbor's color (first 3 values = RGB, ignore alpha)
            neighbor_rgba = pixels[(nx, ny)]
            neighbor_color = (neighbor_rgba[0], neighbor_rgba[1], neighbor_rgba[2])
            
            # Skip if it's a different color
            if neighbor_color != target_color:
                continue
            
            # This pixel matches! Add it to the queue and mark as visited
            queue.append((nx, ny))
            visited.add((nx, ny))
    
    return region_pixels


def split_diagonal_only_connections(region: Region) -> List[Region]:
    """
    Split a region into sub-regions where pixels are only connected via 4-connectivity.
    
    WHY: In 8-connectivity mode, pixels that touch diagonally are merged into one region.
    However, when generating 3D meshes, diagonal-only connections create non-manifold
    geometry (4 triangles meet at a single edge). To fix this, we need to detect
    sub-regions that are only connected diagonally and split them into separate regions.
    
    The algorithm:
    1. Use 4-connectivity flood-fill to find truly connected sub-regions
    2. Each sub-region becomes a separate Region object
    3. This ensures meshes for each region will be manifold
    
    Example:
        Region with pixels: {(0,0), (1,1), (2,2)}  (diagonal staircase)
        Result: 3 separate regions, one per pixel
        
        Region with pixels: {(0,0), (1,0), (0,1), (1,1)}  (2x2 square)
        Result: 1 region (all pixels are edge-connected)
    
    Args:
        region: The region to potentially split
    
    Returns:
        List of Region objects. If region is fully edge-connected, returns [region].
        If region has diagonal-only connections, returns multiple Region objects.
    """
    # Convert to a fake pixel dict for flood_fill (flood_fill expects this format)
    # We just need (x,y) -> (r,g,b,a) but we can use dummy alpha since flood_fill
    # only checks RGB
    fake_pixels = {(x, y): (*region.color, 255) for x, y in region.pixels}
    
    sub_regions: List[Region] = []
    visited: Set[Tuple[int, int]] = set()
    
    # Use 4-connectivity to find truly connected sub-regions
    for x, y in region.pixels:
        if (x, y) in visited:
            continue
        
        # Flood fill with 4-connectivity (edge-only connections)
        sub_region_pixels = flood_fill(
            x, y, 
            region.color, 
            fake_pixels, 
            visited, 
            connectivity=4  # Force 4-connectivity to detect diagonal-only connections
        )
        
        # Create a new region for this sub-region
        sub_regions.append(Region(color=region.color, pixels=sub_region_pixels))
    
    return sub_regions


def merge_regions(pixel_data: PixelData, config: 'ConversionConfig') -> List[Region]:
    """
    Group all pixels into connected regions by color.
    
    This is the main function you'll call! It scans through all non-transparent
    pixels and uses flood-fill to group them into regions. Each region becomes
    one mesh object in the final 3MF file.
    
    The algorithm:
    1. Keep a set of "visited" pixels (starts empty)
    2. For each unvisited pixel:
       a. Start a flood-fill from that pixel
       b. Get all connected pixels of the same color
       c. Create a Region and mark all those pixels as visited
    3. Return the list of regions
    
    Example: If you have a red heart shape and a blue star shape, you'll get
    exactly 2 regions - one for the heart, one for the star. Even if the heart
    has a complex outline with hundreds of pixels, it's still just ONE region!
    
    Note: Diagonal-only connections are handled during mesh generation to ensure
    manifold geometry. At the region level, we keep same-color pixels together
    even if only diagonally connected.
    
    Args:
        pixel_data: Processed pixel data from image_processor
        config: ConversionConfig object with connectivity setting
    
    Returns:
        List of Region objects, one per connected same-color area
    """
    regions: List[Region] = []
    visited: Set[Tuple[int, int]] = set()
    
    # Scan through all non-transparent pixels
    for (x, y), rgba in pixel_data.pixels.items():
        # Skip if we've already processed this pixel
        if (x, y) in visited:
            continue
        
        # Extract RGB color (ignore alpha - we know alpha > 0 since it's in pixels dict)
        color = (rgba[0], rgba[1], rgba[2])
        
        # Flood fill to get all connected pixels of this color
        region_pixels = flood_fill(x, y, color, pixel_data.pixels, visited, connectivity=config.connectivity)
        
        # Create a region for this blob
        regions.append(Region(color=color, pixels=region_pixels))
    
    return regions


def get_region_bounds(region: Region) -> Tuple[int, int, int, int]:
    """
    Get the bounding box of a region in pixel coordinates.
    
    This is useful for debugging or optimization. Returns the min/max x/y
    coordinates of all pixels in the region.
    
    Args:
        region: The region to analyze
    
    Returns:
        Tuple of (min_x, max_x, min_y, max_y)
    """
    if not region.pixels:
        return (0, 0, 0, 0)
    
    xs = [x for x, y in region.pixels]
    ys = [y for x, y in region.pixels]
    
    return (min(xs), max(xs), min(ys), max(ys))


def is_pixel_disconnected(
    x: int,
    y: int,
    all_pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]]
) -> bool:
    """
    Check if a pixel is disconnected (only connects via corners/diagonals).
    
    A pixel is considered disconnected if it has NO edge-connected neighbors
    (up/down/left/right) of ANY color. These pixels only touch other pixels
    at corners, making them unreliable for 3D printing.
    
    The key insight: a pixel should only be trimmed if it has no edge-connected
    neighbors AT ALL, regardless of color. If a pixel has edge-connected neighbors
    (even of different colors), it should be kept because it has a solid connection
    in the 3D mesh.
    
    Example:
        BBBBBBX
        BBBBXXR  <-- This R is NOT disconnected if surrounded by B pixels
        BBBBXXX      (has edge-connected neighbors, even if different color)
    
    Args:
        x, y: Pixel coordinates to check
        all_pixels: Dict of all non-transparent pixels (x,y) -> (r,g,b,a) from entire image
    
    Returns:
        True if pixel is disconnected (no edge neighbors of any color), False otherwise
    """
    # Check all 4 edge-connected neighbors (not diagonals)
    edge_neighbors = [
        (x + 1, y),  # right
        (x - 1, y),  # left
        (x, y + 1),  # down
        (x, y - 1),  # up
    ]
    
    # If any edge neighbor exists (any color), pixel is NOT disconnected
    for nx, ny in edge_neighbors:
        if (nx, ny) in all_pixels:
            return False
    
    # No edge neighbors found - pixel is disconnected (only corner connections or isolated)
    return True


def trim_disconnected_pixels(
    regions: List[Region],
    all_pixels: Dict[Tuple[int, int], Tuple[int, int, int, int]]
) -> List[Region]:
    """
    Remove disconnected pixels from regions.
    
    Disconnected pixels are those that have NO edge-connected neighbors of ANY color.
    These are problematic for 3D printing because:
    1. The physical connection is too weak to print reliably
    2. In the 3D mesh, they only share a vertex with neighbors, not an edge
    
    This function iteratively removes disconnected pixels until none remain.
    We use iteration because removing one disconnected pixel might expose
    another pixel that becomes disconnected.
    
    The key change: We check against ALL pixels in the image (any color), not just
    pixels in the same region. A pixel is only trimmed if it has no edge-connected
    neighbors at all, regardless of color.
    
    Example:
        Before:  BBBBBXX       After:   BBBBBXX
                 BBBBRXX  -->          BBBBRXX
                 BBBBXXX               BBBBXXX
                 
        The R pixel is NOT removed even though it's a different color, because
        it has edge-connected neighbors (the B pixels).
    
    Args:
        regions: List of Region objects to process
        all_pixels: Dict of all non-transparent pixels (x,y) -> (r,g,b,a) from entire image
    
    Returns:
        List of Region objects with disconnected pixels removed.
        Empty regions (if all pixels were disconnected) are filtered out.
    """
    trimmed_regions: List[Region] = []
    
    for region in regions:
        # Keep removing disconnected pixels until none remain
        region_pixels = set(region.pixels)
        
        while True:
            # Find all disconnected pixels in current region
            # Check against ALL pixels in image, not just this region
            disconnected = {
                (x, y) for x, y in region_pixels
                if is_pixel_disconnected(x, y, all_pixels)
            }
            
            # If no disconnected pixels found, we're done
            if not disconnected:
                break
            
            # Remove disconnected pixels from this region
            region_pixels -= disconnected
            
            # Also remove them from all_pixels so they don't provide
            # edge connections for other pixels in subsequent iterations
            for pixel in disconnected:
                if pixel in all_pixels:
                    all_pixels = {k: v for k, v in all_pixels.items() if k != pixel}
        
        # Only keep regions that still have pixels
        if region_pixels:
            trimmed_regions.append(Region(color=region.color, pixels=region_pixels))
    
    return trimmed_regions