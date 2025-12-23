"""
Mesh post-processing and repair module.

This module provides robust mesh validation and repair operations to ensure
manifold, watertight geometry. It uses trimesh for reliable mesh operations
and provides verbose Rich output for transparency.

WHY: Mesh generation algorithms (polygon optimization, rectangle merging, etc.)
can produce non-manifold geometry due to edge cases. Rather than trying to
generate perfect geometry every time, we generate good-enough geometry and
FIX it in post-processing. This is more robust and handles unknown edge cases.

Key operations:
- Merge duplicate vertices
- Remove degenerate faces (zero area)
- Fix winding order and normals
- Fill holes (heal boundary edges)
- Detect and report non-manifold edges

Uses trimesh library for reliable mesh repair operations.
"""

from typing import List, Tuple, Dict, Optional, Callable, TYPE_CHECKING
import numpy as np
from trimesh import Trimesh
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .mesh_generator import Mesh

# Set up logging for this module
logger = logging.getLogger(__name__)


def scan_mesh_issues(tmesh: Trimesh, console: Optional[Console] = None) -> Dict[str, int]:
    """
    Scan mesh for common issues (Pass 1).
    
    Detects:
    - Duplicate vertices (within epsilon)
    - Degenerate faces (zero area)
    - Non-manifold edges (3+ triangles sharing edge)
    - Boundary edges (holes in mesh)
    - Unreferenced vertices
    
    Args:
        tmesh: Trimesh object to scan
        console: Optional Rich Console for pretty output
    
    Returns:
        Dict with issue counts
    """
    issues = {
        'duplicate_vertices': 0,
        'degenerate_faces': 0,
        'non_manifold_edges': 0,
        'boundary_edges': 0,
        'unreferenced_vertices': 0,
        'total': 0
    }
    
    # Count unreferenced vertices
    # These are vertices that no face references
    referenced = np.zeros(len(tmesh.vertices), dtype=bool)
    referenced[tmesh.faces.flatten()] = True
    issues['unreferenced_vertices'] = int((~referenced).sum())
    
    # Count degenerate faces (zero area)
    face_areas = tmesh.area_faces
    issues['degenerate_faces'] = int((face_areas == 0).sum())
    
    # Count non-manifold edges
    # Non-manifold edge = shared by 3+ triangles (or 1 = boundary)
    edge_count = tmesh.edges_unique_length
    issues['non_manifold_edges'] = int((edge_count > 2).sum())
    issues['boundary_edges'] = int((edge_count == 1).sum())
    
    # Estimate duplicate vertices by checking if merge_vertices would help
    # We can't directly count without running merge, so we estimate based on
    # whether vertices are within merge radius of each other
    # For now, we'll discover this during the fix phase
    
    issues['total'] = sum(v for k, v in issues.items() if k != 'total')
    
    if console:
        table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
        table.add_column("Issue Type", style="white")
        table.add_column("Count", justify="right", style="yellow")
        table.add_column("Status", justify="center")
        
        # Add rows with status indicators
        def status_icon(count):
            return "✅" if count == 0 else "⚠️ " if count < 10 else "❌"
        
        table.add_row(
            "Unreferenced Vertices",
            str(issues['unreferenced_vertices']),
            status_icon(issues['unreferenced_vertices'])
        )
        table.add_row(
            "Degenerate Faces",
            str(issues['degenerate_faces']),
            status_icon(issues['degenerate_faces'])
        )
        table.add_row(
            "Non-Manifold Edges",
            str(issues['non_manifold_edges']),
            status_icon(issues['non_manifold_edges'])
        )
        table.add_row(
            "Boundary Edges (Holes)",
            str(issues['boundary_edges']),
            status_icon(issues['boundary_edges'])
        )
        
        console.print(table)
    
    return issues


def fix_mesh_issues(
    tmesh: Trimesh,
    issues: Dict[str, int],
    console: Optional[Console] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, int]:
    """
    Fix detected mesh issues (Pass 2).
    
    Applies repairs in optimal order:
    1. Remove duplicate faces
    2. Remove degenerate faces
    3. Remove unreferenced vertices
    4. Merge duplicate vertices
    5. Fill holes
    6. Fix normals and winding order
    
    Args:
        tmesh: Trimesh object to repair (modified in-place)
        issues: Dict of detected issues from scan_mesh_issues
        console: Optional Rich Console for pretty output
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with counts of fixes applied
    """
    fixes = {
        'duplicate_faces_removed': 0,
        'degenerate_faces_removed': 0,
        'unreferenced_vertices_removed': 0,
        'vertices_merged': 0,
        'holes_filled': 0,
        'normals_fixed': False,
        'total_fixes': 0
    }
    
    def log_step(step: str):
        if console:
            console.print(f"  [cyan]→[/cyan] {step}")
        if progress_callback:
            progress_callback(step)
        logger.debug(step)
    
    # Track original counts
    original_vertices = len(tmesh.vertices)
    original_faces = len(tmesh.faces)
    
    # Fixing strategy: Use trimesh's built-in repair functions with aggressive settings
    # Process with validate=True does: remove NaN/Inf, merge vertices, 
    # remove degenerate faces, remove duplicate faces, fix winding
    
    if console:
        console.print("\n[bold cyan]Pass 2: Fixing Issues[/bold cyan]")
    
    # Step 1: Remove NaN/Inf values
    log_step("Removing NaN/Inf values...")
    tmesh.remove_infinite_values()
    if console:
        console.print(f"    [green]✓[/green] Removed NaN/Inf values")
    
    # Step 2: Merge duplicate vertices AGGRESSIVELY
    # Use digits_vertex to control tolerance - fewer digits = more aggressive
    # Default is ~5-6 digits, we'll use 3 to merge vertices within ~0.001 units
    log_step("Merging duplicate vertices (aggressive)...")
    before_vertices = len(tmesh.vertices)
    tmesh.merge_vertices(digits_vertex=3)
    after_vertices = len(tmesh.vertices)
    fixes['vertices_merged'] = before_vertices - after_vertices
    if fixes['vertices_merged'] > 0 and console:
        console.print(f"    [green]✓[/green] Merged {fixes['vertices_merged']} duplicate vertices (tolerance: 0.001)")
    
    # Step 3: Remove degenerate faces with strict threshold
    # Remove faces with OBB edge < 1e-8 (stricter than default zero-area check)
    log_step("Removing degenerate faces (strict)...")
    before_faces = len(tmesh.faces)
    nondegenerate_mask = tmesh.nondegenerate_faces(height=1e-8)
    tmesh.update_faces(nondegenerate_mask)
    after_faces = len(tmesh.faces)
    degenerate_removed = before_faces - after_faces
    fixes['degenerate_faces_removed'] = degenerate_removed
    if degenerate_removed > 0 and console:
        console.print(f"    [green]✓[/green] Removed {degenerate_removed} degenerate faces (threshold: 1e-8)")
    
    # Step 4: Remove duplicate faces
    log_step("Removing duplicate faces...")
    before_faces = len(tmesh.faces)
    unique_mask = tmesh.unique_faces()
    tmesh.update_faces(unique_mask)
    after_faces = len(tmesh.faces)
    duplicate_removed = before_faces - after_faces
    fixes['duplicate_faces_removed'] = duplicate_removed
    if duplicate_removed > 0 and console:
        console.print(f"    [green]✓[/green] Removed {duplicate_removed} duplicate faces")
    
    # Step 5: Fix winding consistency
    log_step("Fixing winding consistency...")
    try:
        from trimesh import repair
        repair.fix_winding(tmesh)
        if console:
            console.print(f"    [green]✓[/green] Fixed winding consistency")
    except Exception as e:
        if console:
            console.print(f"    [yellow]⚠[/yellow]  Could not fix winding: {e}")
        logger.warning(f"Could not fix winding: {e}")
    
    # Step 6: Remove unreferenced vertices
    log_step("Removing unreferenced vertices...")
    before_vertices = len(tmesh.vertices)
    tmesh.remove_unreferenced_vertices()
    after_vertices = len(tmesh.vertices)
    fixes['unreferenced_vertices_removed'] = before_vertices - after_vertices
    if fixes['unreferenced_vertices_removed'] > 0 and console:
        console.print(f"    [green]✓[/green] Removed {fixes['unreferenced_vertices_removed']} unreferenced vertices")
    
    # Step 5: Fill holes
    log_step("Filling holes...")
    before_watertight = tmesh.is_watertight
    tmesh.fill_holes()
    after_watertight = tmesh.is_watertight
    fixes['holes_filled'] = 1 if (not before_watertight and after_watertight) else 0
    if fixes['holes_filled'] > 0 and console:
        console.print(f"    [green]✓[/green] Filled holes (mesh is now watertight)")
    elif not after_watertight and console:
        console.print(f"    [yellow]⚠[/yellow]  Mesh still has holes after fill_holes()")
    
    # Step 6: Fix normals (ensure outward facing)
    log_step("Fixing normals...")
    tmesh.fix_normals()
    fixes['normals_fixed'] = True
    if console:
        console.print(f"    [green]✓[/green] Fixed normals (outward facing)")
    
    fixes['total_fixes'] = sum(v for k, v in fixes.items() 
                               if k != 'total_fixes' and isinstance(v, int))
    
    # Summary
    vertices_after = len(tmesh.vertices)
    faces_after = len(tmesh.faces)
    
    if console:
        console.print()
        summary = Table(show_header=False, box=None, padding=(0, 2))
        summary.add_column("Label", style="cyan")
        summary.add_column("Value", style="white")
        
        summary.add_row("Original:", f"{original_vertices:,} vertices, {original_faces:,} faces")
        summary.add_row("Final:", f"{vertices_after:,} vertices, {faces_after:,} faces")
        summary.add_row("Reduction:", 
                       f"{original_vertices - vertices_after:,} vertices, "
                       f"{original_faces - faces_after:,} faces")
        
        console.print(summary)
    
    return fixes


def validate_final_mesh(tmesh: Trimesh, console: Optional[Console] = None) -> bool:
    """
    Final validation check after repairs.
    
    Checks:
    - Is watertight (no holes)
    - Has no non-manifold edges
    - Has valid normals
    
    Args:
        tmesh: Trimesh object to validate
        console: Optional Rich Console for pretty output
    
    Returns:
        True if mesh is valid and manifold
    """
    is_watertight = tmesh.is_watertight
    edge_count = tmesh.edges_unique_length
    non_manifold = int((edge_count > 2).sum())
    boundary = int((edge_count == 1).sum())
    
    is_valid = is_watertight and non_manifold == 0 and boundary == 0
    
    if console:
        console.print("\n[bold cyan]Final Validation[/bold cyan]")
        
        validation_table = Table(show_header=False, box=None, padding=(0, 2))
        validation_table.add_column("Check", style="white")
        validation_table.add_column("Status", justify="center")
        
        validation_table.add_row(
            "Watertight (no holes)",
            "[green]✅ Yes[/green]" if is_watertight else "[red]❌ No[/red]"
        )
        validation_table.add_row(
            "Non-manifold edges",
            "[green]✅ None (0)[/green]" if non_manifold == 0 else f"[red]❌ {non_manifold} found[/red]"
        )
        validation_table.add_row(
            "Boundary edges",
            "[green]✅ None (0)[/green]" if boundary == 0 else f"[red]❌ {boundary} found[/red]"
        )
        
        console.print(validation_table)
        console.print()
        
        if is_valid:
            console.print("[bold green]✅ MESH IS MANIFOLD AND VALID[/bold green]")
        else:
            console.print("[bold yellow]⚠️  MESH STILL HAS ISSUES[/bold yellow]")
            console.print("[dim]Note: Some complex geometries may be difficult to fully repair.[/dim]")
    
    return is_valid


def validate_and_fix_mesh(
    mesh: 'Mesh',
    name: str = "mesh",
    verbose: bool = True,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Tuple['Mesh', Dict]:
    """
    Main entry point for mesh post-processing.
    
    Performs two-pass validation and repair:
    1. Scan for issues (detect problems)
    2. Fix issues (apply repairs)
    3. Final validation
    
    This is a defensive programming approach: don't try to generate perfect
    geometry, generate good-enough geometry and FIX it. Handles edge cases
    gracefully and provides transparency through verbose output.
    
    Args:
        mesh: Mesh object with vertices and triangles
        name: Name of mesh for logging/display
        verbose: If True, show detailed Rich output
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple of (fixed_mesh, diagnostics_dict)
        - fixed_mesh: Repaired Mesh object
        - diagnostics: Dict with issue/fix counts and validation results
    """
    from .mesh_generator import Mesh
    
    console = Console() if verbose else None
    
    if console:
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]🔧 Post-Processing: {name}[/bold cyan]",
            border_style="cyan"
        ))
        console.print()
    
    # Convert to trimesh format
    tmesh = Trimesh(
        vertices=np.array(mesh.vertices, dtype=np.float64),
        faces=np.array(mesh.triangles, dtype=np.int32)
    )
    
    if console:
        console.print(f"[cyan]Loaded:[/cyan] {len(tmesh.vertices):,} vertices, {len(tmesh.faces):,} faces")
        console.print()
    
    # PASS 1: SCAN
    if console:
        console.print("[bold cyan]Pass 1: Scanning for Issues[/bold cyan]")
    
    issues = scan_mesh_issues(tmesh, console)
    
    # PASS 2: FIX (if needed)
    if issues['total'] > 0:
        fixes = fix_mesh_issues(tmesh, issues, console, progress_callback)
    else:
        if console:
            console.print("\n[green]✅ No issues detected, mesh is already valid![/green]")
        fixes = {}
    
    # PASS 3: VALIDATE
    is_valid = validate_final_mesh(tmesh, console)
    
    # Convert back to our Mesh format
    fixed_mesh = Mesh(
        vertices=tmesh.vertices.tolist(),
        triangles=tmesh.faces.tolist()
    )
    
    diagnostics = {
        'issues': issues,
        'fixes': fixes,
        'is_valid': is_valid,
        'final_vertices': len(tmesh.vertices),
        'final_faces': len(tmesh.faces)
    }
    
    logger.info(
        f"Post-processed {name}: "
        f"{issues['total']} issues found, "
        f"{fixes.get('total_fixes', 0)} fixes applied, "
        f"{'VALID' if is_valid else 'STILL HAS ISSUES'}"
    )
    
    return fixed_mesh, diagnostics
