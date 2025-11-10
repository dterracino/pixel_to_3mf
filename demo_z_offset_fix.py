#!/usr/bin/env python3
"""
Quick comparison script to show backing plate Z-offset fix.

This demonstrates that the rendering offset prevents Z-fighting without
modifying the actual mesh geometry.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from pixel_to_3mf.mesh_generator import Mesh

def demonstrate_z_offset_fix():
    """Show how the Z-offset fix works for backing plate rendering."""
    
    print("="*80)
    print("BACKING PLATE Z-OFFSET FIX DEMONSTRATION")
    print("="*80)
    print()
    print("Problem: Backing plate top (Z=0) and region bottoms (Z=0) are coplanar,")
    print("causing Z-fighting artifacts in matplotlib rendering.")
    print()
    print("Solution: Apply -0.01mm offset to backing plate DURING RENDERING ONLY.")
    print()
    
    # Create a simple backing plate mesh
    backing_vertices = [
        (0.0, 0.0, -1.0),    # Bottom corners
        (10.0, 0.0, -1.0),
        (10.0, 10.0, -1.0),
        (0.0, 10.0, -1.0),
        (0.0, 0.0, 0.0),     # Top corners at Z=0 (shares plane with regions!)
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
    ]
    backing_mesh = Mesh(backing_vertices, [(0,1,2), (4,5,6)])
    
    # Create a colored region mesh
    region_vertices = [
        (2.0, 2.0, 0.0),     # Bottom corners at Z=0 (shares plane with backing!)
        (8.0, 2.0, 0.0),
        (8.0, 8.0, 0.0),
        (2.0, 8.0, 0.0),
        (2.0, 2.0, 1.0),     # Top corners at Z=1
        (8.0, 2.0, 1.0),
        (8.0, 8.0, 1.0),
        (2.0, 8.0, 1.0),
    ]
    region_mesh = Mesh(region_vertices, [(0,1,2), (4,5,6)])
    
    print("-"*80)
    print("BEFORE FIX (Original Mesh Coordinates)")
    print("-"*80)
    print()
    print("Backing Plate:")
    print(f"  Bottom vertices (Z): {backing_mesh.vertices[0][2]:.3f}mm")
    print(f"  Top vertices (Z):    {backing_mesh.vertices[4][2]:.3f}mm")
    print()
    print("Colored Region:")
    print(f"  Bottom vertices (Z): {region_mesh.vertices[0][2]:.3f}mm")
    print(f"  Top vertices (Z):    {region_mesh.vertices[4][2]:.3f}mm")
    print()
    print("⚠️  PROBLEM: Both top of backing and bottom of region are at Z=0!")
    print("    This causes Z-fighting where both surfaces compete to be visible.")
    print()
    
    # Apply the rendering offset (as done in render_model.py)
    backing_array = np.array(backing_mesh.vertices)
    backing_array_offset = backing_array.copy()
    backing_array_offset[:, 2] -= 0.01  # Apply -0.01mm offset
    
    print("-"*80)
    print("AFTER FIX (Rendering Coordinates with Offset)")
    print("-"*80)
    print()
    print("Backing Plate (with -0.01mm offset):")
    print(f"  Bottom vertices (Z): {backing_array_offset[0][2]:.3f}mm")
    print(f"  Top vertices (Z):    {backing_array_offset[4][2]:.3f}mm")
    print()
    print("Colored Region (unchanged):")
    print(f"  Bottom vertices (Z): {region_mesh.vertices[0][2]:.3f}mm")
    print(f"  Top vertices (Z):    {region_mesh.vertices[4][2]:.3f}mm")
    print()
    print("✅ FIXED: Now there's a 0.01mm gap preventing Z-fighting!")
    print("   The gap is too small to see (10 microns), but prevents the artifact.")
    print()
    
    print("-"*80)
    print("IMPORTANT NOTES")
    print("-"*80)
    print()
    print("1. The offset is ONLY applied during rendering (visualization)")
    print("2. The actual 3MF file geometry remains unchanged at Z=0")
    print("3. For 3D printing, the surfaces SHOULD be at Z=0 (proper connection)")
    print("4. The 0.01mm offset is invisible but prevents matplotlib Z-fighting")
    print()
    
    # Verify original mesh is unchanged
    print("-"*80)
    print("VERIFICATION: Original Mesh Data Unchanged")
    print("-"*80)
    print()
    print("Original backing plate top Z:", backing_mesh.vertices[4][2])
    print("✅ Original mesh data is preserved (still at Z=0 for proper 3D printing)")
    print()
    print("="*80)


if __name__ == "__main__":
    demonstrate_z_offset_fix()
