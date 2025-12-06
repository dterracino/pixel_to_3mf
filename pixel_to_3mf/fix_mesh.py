import sys
import numpy as np
import trimesh
from trimesh import Trimesh

def detect_and_fix_mesh(file_path: str, output_path: str) -> None:
    try:
        # Load mesh explicitly as Trimesh
        mesh = trimesh.load_mesh(file_path)

        if not isinstance(mesh, Trimesh):
            print("❌ Error: Loaded object is not a Trimesh.")
            return

        if mesh.is_empty:
            print("❌ Error: Mesh is empty or could not be loaded.")
            return

        print(f"📂 Loaded mesh: {file_path}")
        print(f"   Vertices: {len(mesh.vertices)}, Faces: {len(mesh.faces)}")

        # --- Detect non-manifold edges ---
        non_manifold_edges = mesh.edges_unique[mesh.edges_unique_length != 2]
        if len(non_manifold_edges) > 0:
            print(f"⚠ Non-manifold edges detected: {len(non_manifold_edges)}")
        else:
            print("✅ No non-manifold edges detected.")

        if not mesh.is_watertight:
            print("⚠ Mesh is not watertight (possible holes or non-manifold vertices).")

        # --- Repair geometry ---
        # Note: This is the explicit path through the fixes, so we can see each step.
        # The other option is to call mesh.process(), which does many of these steps automatically.
        # That approach is more concise but less transparent; we can't log each step as easily.
        # But we can switch to that if desired for brevity.
        print("\n--- Repairing mesh ---")
        mesh.remove_duplicate_faces() # type: ignore[attr-defined]
        mesh.remove_degenerate_faces() # type: ignore[attr-defined]
        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()
        mesh.fill_holes()

        # As I said above, alternatively, we could use:
        mesh.process(validate=True)  # Additional processing and validation

        # --- Fix winding order & normals ---
        print("\n--- Fixing normals and winding order ---")
        mesh.rezero()  # Move mesh to origin
        mesh.remove_infinite_values()
        mesh.fix_normals()  # Ensures consistent winding and outward normals

        # Recompute vertex normals
        mesh.vertex_normals = mesh.vertex_normals  # Forces recomputation

        # --- Re-check manifold status ---
        non_manifold_edges_after = mesh.edges_unique[mesh.edges_unique_length != 2]
        if len(non_manifold_edges_after) == 0 and mesh.is_watertight:
            print("✅ Mesh repaired and normals fixed successfully.")
        else:
            print("⚠ Mesh still has issues after repair.")

        # Save repaired mesh
        mesh.export(output_path)
        print(f"💾 Repaired mesh saved to: {output_path}")

    except Exception as e:
        print(f"❌ Error processing mesh: {e}")

def fix_mesh_with_numpy(file_path: str, output_path: str) -> None:
    """
    Alternative mesh fixing using numpy for performance on large meshes.
    This function is a placeholder to indicate where such an implementation would go.
    Currently, it just calls the main detect_and_fix_mesh function.
    """
    mesh = trimesh.load_mesh(file_path)

    # Sort vertex indices in each face so duplicates match
    faces_sorted = np.sort(mesh.faces, axis=1)

    # Find unique faces
    _, unique_indices = np.unique(faces_sorted, axis=0, return_index=True)

    # Keep only unique faces
    mesh.update_faces(unique_indices)
    mesh.remove_unreferenced_vertices()

    mesh.export(output_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fix_mesh.py <input_mesh> <output_mesh>")
    else:
        detect_and_fix_mesh(sys.argv[1], sys.argv[2])