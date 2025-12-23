"""Quick script to check mesh validity of a 3MF file."""

import trimesh
import sys

if len(sys.argv) < 2:
    print("Usage: python check_mesh_validity.py <path_to_3mf>")
    sys.exit(1)

path = sys.argv[1]
print(f"Loading: {path}")

# Load the 3MF file
scene = trimesh.load(path)

if isinstance(scene, trimesh.Scene):
    meshes = list(scene.geometry.values())
    print(f"Found {len(meshes)} meshes in scene\n")
else:
    meshes = [scene]
    print("Single mesh\n")

total_non_manifold = 0
total_boundary = 0

for i, mesh in enumerate(meshes):
    print(f"=== Mesh {i+1} ===")
    print(f"  Vertices: {len(mesh.vertices):,}")
    print(f"  Faces: {len(mesh.faces):,}")
    print(f"  Watertight: {mesh.is_watertight}")
    print(f"  Volume: {mesh.is_volume}")
    
    # Count non-manifold edges
    edges = mesh.edges_unique
    edge_adj_count = mesh.edges_unique_length
    
    # Non-manifold edges: shared by != 2 faces
    non_manifold_mask = edge_adj_count != 2
    non_manifold_count = non_manifold_mask.sum()
    
    # Boundary edges: shared by exactly 1 face
    boundary_mask = edge_adj_count == 1
    boundary_count = boundary_mask.sum()
    
    print(f"  Non-manifold edges: {non_manifold_count}")
    print(f"  Boundary edges: {boundary_count}")
    print()
    
    total_non_manifold += non_manifold_count
    total_boundary += boundary_count

print(f"=== TOTALS ===")
print(f"Non-manifold edges: {total_non_manifold}")
print(f"Boundary edges: {total_boundary}")

if total_non_manifold == 0 and total_boundary == 0:
    print("\n✅ PERFECT! All meshes are manifold and watertight!")
elif total_non_manifold == 0:
    print(f"\n⚠ Manifold but has {total_boundary} boundary edges (holes)")
else:
    print(f"\n❌ HAS ISSUES: {total_non_manifold} non-manifold edges")
