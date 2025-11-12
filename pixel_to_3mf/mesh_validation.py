"""
Mesh validation module using trimesh for comprehensive quality checks.

This module provides validation and repair functions for 3D meshes,
abstracting the backend library (currently trimesh) to allow for
potential future backend swaps while maintaining a consistent API.

The validation functions help ensure meshes are:
- Watertight (no holes or gaps)
- Manifold (every edge shared by exactly 2 faces)
- Properly wound (consistent CCW normal direction)
- Free of degenerate geometry
"""

from typing import List, Tuple, Dict, Optional, Any
import logging

# Set up logging for this module
logger = logging.getLogger(__name__)

# Try to import trimesh - it's an optional dependency
try:
    import trimesh
    import trimesh.repair
    import numpy as np
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False
    trimesh = None
    np = None

# Import our mesh type
from .mesh_generator import Mesh


class ValidationResult:
    """
    Result of mesh validation containing issues found and statistics.
    
    This encapsulates validation results in a way that's independent
    of the backend validation library used.
    """
    
    def __init__(self):
        """Initialize an empty validation result."""
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict[str, Any] = {}
    
    def add_error(self, message: str) -> None:
        """Add a critical error that makes the mesh invalid."""
        self.is_valid = False
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add a non-critical warning about mesh quality."""
        self.warnings.append(message)
    
    def add_stat(self, key: str, value: Any) -> None:
        """Add a statistic about the mesh."""
        self.stats[key] = value
    
    def __repr__(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return f"ValidationResult({status}, errors={len(self.errors)}, warnings={len(self.warnings)})"


def is_trimesh_available() -> bool:
    """
    Check if trimesh is available for enhanced validation.
    
    Returns:
        True if trimesh is installed and available
    """
    return TRIMESH_AVAILABLE


def validate_mesh(mesh: Mesh, mesh_name: str = "mesh") -> ValidationResult:
    """
    Validate a mesh for 3D printing readiness.
    
    Performs comprehensive validation checks including:
    - Watertightness (no holes or boundaries)
    - Winding consistency (CCW normals)
    - Volume validity
    - Topological correctness (Euler number)
    - Degenerate face detection
    - Duplicate detection
    
    Args:
        mesh: Mesh object to validate
        mesh_name: Name for error messages (e.g., "Region 1", "Backing plate")
    
    Returns:
        ValidationResult with detailed findings
    """
    result = ValidationResult()
    
    if not TRIMESH_AVAILABLE:
        # Fallback: Basic validation without trimesh
        result.add_warning("Trimesh not available - using basic validation only")
        _validate_basic(mesh, mesh_name, result)
        return result
    
    # Convert to trimesh format
    try:
        tmesh = trimesh.Trimesh(
            vertices=mesh.vertices,
            faces=mesh.triangles,
            process=False  # Don't auto-repair, we want to detect issues
        )
    except Exception as e:
        result.add_error(f"{mesh_name}: Failed to create trimesh object: {e}")
        return result
    
    # Add basic statistics
    result.add_stat("vertices", len(tmesh.vertices))
    result.add_stat("triangles", len(tmesh.faces))
    
    # Critical check: Watertightness
    if not tmesh.is_watertight:
        result.add_error(f"{mesh_name} is not watertight (has holes or open boundaries)")
        
        # Try to provide more details about the problem
        edges = tmesh.edges_unique
        edge_adjacency = tmesh.face_adjacency
        boundary_edges = len(edges) - len(edge_adjacency)
        if boundary_edges > 0:
            result.add_stat("boundary_edges", boundary_edges)
            result.add_error(f"  Found {boundary_edges} boundary edges (edges with only 1 adjacent face)")
    else:
        result.add_stat("watertight", True)
    
    # Critical check: Winding consistency
    if not tmesh.is_winding_consistent:
        result.add_error(f"{mesh_name} has inconsistent triangle winding")
        result.add_error("  Some triangles are wound clockwise, others counter-clockwise")
    else:
        result.add_stat("winding_consistent", True)
    
    # Important check: Valid volume
    if not tmesh.is_volume:
        result.add_error(f"{mesh_name} does not enclose a valid volume")
    else:
        result.add_stat("is_volume", True)
        result.add_stat("volume_mm3", float(tmesh.volume))
        
        # Check for negative volume (inside-out mesh)
        if tmesh.volume < 0:
            result.add_error(f"{mesh_name} has negative volume (mesh is inside-out)")
    
    # Topological check: Euler number
    euler = tmesh.euler_number
    result.add_stat("euler_number", euler)
    if euler != 2:
        # For a closed manifold surface, Euler = 2
        # If not 2, there may be topological holes (genus > 0)
        genus = 1 - (euler / 2)
        result.add_warning(f"{mesh_name} has unusual topology (euler={euler}, genus={genus})")
    
    # Quality check: Degenerate faces
    if hasattr(tmesh, 'area_faces'):
        degenerate_threshold = 1e-10
        degenerate_count = (tmesh.area_faces < degenerate_threshold).sum()
        if degenerate_count > 0:
            result.add_warning(f"{mesh_name} has {degenerate_count} degenerate (zero-area) triangles")
            result.add_stat("degenerate_faces", int(degenerate_count))
    
    # Quality check: Face angles
    if hasattr(tmesh, 'face_angles'):
        angles_deg = np.degrees(tmesh.face_angles)
        min_angle = float(angles_deg.min())
        max_angle = float(angles_deg.max())
        result.add_stat("min_angle_deg", min_angle)
        result.add_stat("max_angle_deg", max_angle)
        
        # Warn about very acute or obtuse angles (sliver triangles)
        if min_angle < 5.0:
            result.add_warning(f"{mesh_name} has very acute triangles (min angle: {min_angle:.1f}°)")
        if max_angle > 175.0:
            result.add_warning(f"{mesh_name} has very obtuse triangles (max angle: {max_angle:.1f}°)")
    
    # Physical properties
    if hasattr(tmesh, 'area'):
        result.add_stat("surface_area_mm2", float(tmesh.area))
    
    if hasattr(tmesh, 'bounds'):
        bounds = tmesh.bounds
        extents = tmesh.extents
        result.add_stat("bounds_min", [float(x) for x in bounds[0]])
        result.add_stat("bounds_max", [float(x) for x in bounds[1]])
        result.add_stat("extents", [float(x) for x in extents])
    
    return result


def _validate_basic(mesh: Mesh, mesh_name: str, result: ValidationResult) -> None:
    """
    Basic validation without trimesh (fallback).
    
    Performs minimal validation using just the vertex and triangle data.
    This is much less comprehensive than the trimesh-based validation.
    
    Args:
        mesh: Mesh to validate
        mesh_name: Name for error messages
        result: ValidationResult to populate
    """
    # Basic checks
    result.add_stat("vertices", len(mesh.vertices))
    result.add_stat("triangles", len(mesh.triangles))
    
    if len(mesh.vertices) == 0:
        result.add_error(f"{mesh_name} has no vertices")
        return
    
    if len(mesh.triangles) == 0:
        result.add_error(f"{mesh_name} has no triangles")
        return
    
    # Check for degenerate triangles (vertices at same position)
    degenerate_count = 0
    for tri in mesh.triangles:
        v0, v1, v2 = mesh.vertices[tri[0]], mesh.vertices[tri[1]], mesh.vertices[tri[2]]
        if v0 == v1 or v1 == v2 or v2 == v0:
            degenerate_count += 1
    
    if degenerate_count > 0:
        result.add_warning(f"{mesh_name} has {degenerate_count} degenerate triangles")
    
    # Check vertex indices are in range
    max_index = len(mesh.vertices) - 1
    for i, tri in enumerate(mesh.triangles):
        for j, idx in enumerate(tri):
            if idx < 0 or idx > max_index:
                result.add_error(f"{mesh_name} triangle {i} has out-of-range vertex index {idx}")


def attempt_repair(mesh: Mesh, mesh_name: str = "mesh") -> Tuple[Mesh, List[str]]:
    """
    Attempt to automatically repair common mesh issues.
    
    Tries to fix:
    - Holes (fill_holes)
    - Inconsistent winding (fix_normals)
    - Degenerate faces
    - Duplicate vertices
    - Unreferenced vertices
    
    Args:
        mesh: Mesh to repair
        mesh_name: Name for logging
    
    Returns:
        Tuple of (repaired_mesh, list_of_fixes_applied)
    """
    fixes_applied = []
    
    if not TRIMESH_AVAILABLE:
        logger.warning(f"Cannot repair {mesh_name}: trimesh not available")
        return mesh, ["Trimesh not available for repair"]
    
    # Convert to trimesh
    try:
        tmesh = trimesh.Trimesh(
            vertices=mesh.vertices,
            faces=mesh.triangles,
            process=False
        )
    except Exception as e:
        logger.error(f"Failed to convert {mesh_name} to trimesh: {e}")
        return mesh, [f"Conversion failed: {e}"]
    
    # Try to fill holes
    if not tmesh.is_watertight:
        try:
            filled = tmesh.fill_holes()
            if filled:
                fixes_applied.append("Filled holes")
                logger.info(f"{mesh_name}: Filled holes successfully")
        except Exception as e:
            logger.warning(f"{mesh_name}: fill_holes failed: {e}")
    
    # Fix winding consistency
    if not tmesh.is_winding_consistent:
        try:
            tmesh.fix_normals()
            fixes_applied.append("Fixed normals/winding")
            logger.info(f"{mesh_name}: Fixed winding consistency")
        except Exception as e:
            logger.warning(f"{mesh_name}: fix_normals failed: {e}")
    
    # Remove degenerate faces
    try:
        before = len(tmesh.faces)
        tmesh.remove_degenerate_faces()
        after = len(tmesh.faces)
        if before > after:
            fixes_applied.append(f"Removed {before - after} degenerate triangles")
            logger.info(f"{mesh_name}: Removed {before - after} degenerate faces")
    except Exception as e:
        logger.warning(f"{mesh_name}: remove_degenerate_faces failed: {e}")
    
    # Merge duplicate vertices
    try:
        before = len(tmesh.vertices)
        tmesh.merge_vertices()
        after = len(tmesh.vertices)
        if before > after:
            fixes_applied.append(f"Merged {before - after} duplicate vertices")
            logger.info(f"{mesh_name}: Merged {before - after} duplicate vertices")
    except Exception as e:
        logger.warning(f"{mesh_name}: merge_vertices failed: {e}")
    
    # Remove unreferenced vertices
    try:
        before = len(tmesh.vertices)
        tmesh.remove_unreferenced_vertices()
        after = len(tmesh.vertices)
        if before > after:
            fixes_applied.append(f"Removed {before - after} unreferenced vertices")
            logger.info(f"{mesh_name}: Removed {before - after} unreferenced vertices")
    except Exception as e:
        logger.warning(f"{mesh_name}: remove_unreferenced_vertices failed: {e}")
    
    # Convert back to our Mesh format
    repaired_mesh = Mesh(
        vertices=[tuple(v) for v in tmesh.vertices.tolist()],
        triangles=[tuple(f) for f in tmesh.faces.tolist()]
    )
    
    return repaired_mesh, fixes_applied


def get_mesh_report(mesh: Mesh, mesh_name: str = "mesh") -> str:
    """
    Generate a detailed mesh quality report.
    
    Creates a human-readable report with:
    - Basic statistics (vertices, triangles)
    - Validation status (watertight, winding, volume)
    - Physical properties (volume, surface area, dimensions)
    - Quality metrics (triangle angles)
    
    Args:
        mesh: Mesh to analyze
        mesh_name: Name for the report
    
    Returns:
        Formatted report string
    """
    result = validate_mesh(mesh, mesh_name)
    
    lines = []
    lines.append(f"=== Mesh Quality Report: {mesh_name} ===")
    lines.append("")
    
    # Basic stats
    lines.append("Basic Statistics:")
    lines.append(f"  Vertices: {result.stats.get('vertices', 'N/A'):,}")
    lines.append(f"  Triangles: {result.stats.get('triangles', 'N/A'):,}")
    lines.append("")
    
    # Validation status
    lines.append("Validation Status:")
    if result.is_valid:
        lines.append("  ✅ VALID - Mesh passed all critical checks")
    else:
        lines.append("  ❌ INVALID - Mesh has critical issues")
    
    lines.append(f"  Watertight: {'✅ Yes' if result.stats.get('watertight') else '❌ No'}")
    lines.append(f"  Winding Consistent: {'✅ Yes' if result.stats.get('winding_consistent') else '❌ No'}")
    lines.append(f"  Valid Volume: {'✅ Yes' if result.stats.get('is_volume') else '❌ No'}")
    
    if 'euler_number' in result.stats:
        lines.append(f"  Euler Number: {result.stats['euler_number']}")
    lines.append("")
    
    # Physical properties (if available)
    if 'volume_mm3' in result.stats or 'surface_area_mm2' in result.stats:
        lines.append("Physical Properties:")
        if 'volume_mm3' in result.stats:
            lines.append(f"  Volume: {result.stats['volume_mm3']:.2f} mm³")
        if 'surface_area_mm2' in result.stats:
            lines.append(f"  Surface Area: {result.stats['surface_area_mm2']:.2f} mm²")
        if 'extents' in result.stats:
            ext = result.stats['extents']
            lines.append(f"  Dimensions: {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm")
        lines.append("")
    
    # Quality metrics (if available)
    if 'min_angle_deg' in result.stats:
        lines.append("Triangle Quality:")
        lines.append(f"  Angle Range: {result.stats['min_angle_deg']:.1f}° to {result.stats['max_angle_deg']:.1f}°")
        if 'degenerate_faces' in result.stats:
            lines.append(f"  Degenerate Triangles: {result.stats['degenerate_faces']}")
        lines.append("")
    
    # Errors
    if result.errors:
        lines.append("Errors:")
        for error in result.errors:
            lines.append(f"  ❌ {error}")
        lines.append("")
    
    # Warnings
    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  ⚠️ {warning}")
        lines.append("")
    
    return "\n".join(lines)


def validate_optimization_quality(
    original_mesh: Mesh,
    optimized_mesh: Mesh,
    tolerance: float = 0.01
) -> ValidationResult:
    """
    Validate that optimization didn't break the mesh.
    
    Compares the original and optimized meshes to ensure:
    - Watertightness is preserved
    - Volume is approximately the same (within tolerance)
    - Topology is preserved (same Euler number)
    - Winding consistency is maintained
    
    Args:
        original_mesh: Original unoptimized mesh
        optimized_mesh: Optimized mesh to validate
        tolerance: Maximum acceptable volume change ratio (default 1%)
    
    Returns:
        ValidationResult with comparison findings
    """
    result = ValidationResult()
    
    if not TRIMESH_AVAILABLE:
        result.add_warning("Trimesh not available - cannot validate optimization")
        return result
    
    # Validate both meshes
    orig_result = validate_mesh(original_mesh, "Original")
    opt_result = validate_mesh(optimized_mesh, "Optimized")
    
    # Check that optimization didn't break watertightness
    if orig_result.stats.get('watertight') and not opt_result.stats.get('watertight'):
        result.add_error("Optimization broke watertightness!")
    
    # Check that optimization didn't break winding consistency
    if orig_result.stats.get('winding_consistent') and not opt_result.stats.get('winding_consistent'):
        result.add_error("Optimization broke winding consistency!")
    
    # Check volume preservation
    if 'volume_mm3' in orig_result.stats and 'volume_mm3' in opt_result.stats:
        orig_vol = orig_result.stats['volume_mm3']
        opt_vol = opt_result.stats['volume_mm3']
        
        if orig_vol != 0:
            vol_diff = abs(orig_vol - opt_vol)
            vol_ratio = vol_diff / abs(orig_vol)
            
            result.add_stat("volume_change_ratio", vol_ratio)
            result.add_stat("volume_change_mm3", vol_diff)
            
            if vol_ratio > tolerance:
                result.add_error(f"Volume changed by {vol_ratio*100:.1f}% (exceeds {tolerance*100:.1f}% tolerance)")
        else:
            result.add_warning("Original volume is zero, cannot compare")
    
    # Check topology preservation
    if 'euler_number' in orig_result.stats and 'euler_number' in opt_result.stats:
        if orig_result.stats['euler_number'] != opt_result.stats['euler_number']:
            result.add_error("Optimization changed topology (Euler number changed)!")
    
    # Calculate reduction statistics
    orig_tri = orig_result.stats.get('triangles', 0)
    opt_tri = opt_result.stats.get('triangles', 0)
    if orig_tri > 0:
        reduction = orig_tri - opt_tri
        reduction_pct = (reduction / orig_tri) * 100
        result.add_stat("triangle_reduction", reduction)
        result.add_stat("triangle_reduction_pct", reduction_pct)
    
    orig_vert = orig_result.stats.get('vertices', 0)
    opt_vert = opt_result.stats.get('vertices', 0)
    if orig_vert > 0:
        reduction = orig_vert - opt_vert
        reduction_pct = (reduction / orig_vert) * 100
        result.add_stat("vertex_reduction", reduction)
        result.add_stat("vertex_reduction_pct", reduction_pct)
    
    return result
