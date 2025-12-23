import numpy as np
import pymesh

# Documentation is at the Pymesh site
# https://pymesh.readthedocs.io/en/latest/api_local_mesh_cleanup.html

def create_and_repair_mesh(vertices, faces):
    """
    Create a PyMesh mesh from vertices and faces, run checks, and repair it.
    """
    # Step 1: Create mesh from raw data
    mesh = pymesh.form_mesh(vertices, faces)
    print("=== Initial Mesh Info ===")
    print(f"Vertices:\n{mesh.vertices}")
    print(f"Faces:\n{mesh.faces}")
    print(f"Num vertices: {mesh.num_vertices}")
    print(f"Num faces: {mesh.num_faces}")
    print(f"Bounding box: min={mesh.bbox[0]}, max={mesh.bbox[1]}")
    print()

    # Step 2: Run mesh checks
    print("=== Mesh Checks ===")
    print(f"Is manifold: {pymesh.is_manifold(mesh)}")
    print(f"Is watertight: {pymesh.is_watertight(mesh)}")
    print(f"Has self-intersection: {pymesh.has_self_intersection(mesh)}")
    print()

    # Step 3: Repair process
    print("=== Repair Steps ===")
    mesh, info = pymesh.remove_duplicated_vertices(mesh, tol=1e-12)
    print(f"Removed duplicated vertices: {info['num_removed']}")

    mesh, info = pymesh.remove_duplicated_faces(mesh)
    print(f"Removed duplicated faces: {info['num_removed']}")

    mesh, info = pymesh.remove_degenerated_triangles(mesh)
    print(f"Removed degenerated triangles: {info['num_removed']}")

    mesh, info = pymesh.remove_isolated_vertices(mesh)
    print(f"Removed isolated vertices: {info['num_removed']}")

    mesh, info = pymesh.resolve_self_intersection(mesh)
    print(f"Resolved self-intersections: {info['num_resolved']}")

    mesh, info = pymesh.split_long_edges(mesh, 1.0)  # Example threshold
    print(f"Split long edges: {info['num_edges_split']}")

    mesh, info = pymesh.collapse_short_edges(mesh, 1e-6)
    print(f"Collapsed short edges: {info['num_edges_collapsed']}")

    mesh, info = pymesh.remove_obtuse_triangles(mesh, 150.0)
    print(f"Removed obtuse triangles: {info['num_removed']}")

    print()

    # Step 4: Final checks
    print("=== Final Mesh Info ===")
    print(f"Num vertices: {mesh.num_vertices}")
    print(f"Num faces: {mesh.num_faces}")
    print(f"Is manifold: {pymesh.is_manifold(mesh)}")
    print(f"Is watertight: {pymesh.is_watertight(mesh)}")
    print(f"Has self-intersection: {pymesh.has_self_intersection(mesh)}")
    print(f"Bounding box: min={mesh.bbox[0]}, max={mesh.bbox[1]}")

    return mesh

if __name__ == "__main__":
    # Example: a simple tetrahedron with one bad duplicate vertex
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, 0.0]  # duplicate of first vertex
    ])

    faces = np.array([
        [0, 1, 2],
        [0, 1, 3],
        [0, 2, 3],
        [1, 2, 3]
    ])

    repaired_mesh = create_and_repair_mesh(vertices, faces)

    # After repairs are done
    final_vertices = repaired_mesh.vertices  # NumPy array of shape (N, 3)
    final_faces = repaired_mesh.faces        # NumPy array of shape (M, 3)

    print("=== Final Mesh Data ===")
    print("Vertices array shape:", final_vertices.shape)
    print("Faces array shape:", final_faces.shape)

    # Example: iterate through vertices
    for i, v in enumerate(final_vertices):
        print(f"Vertex {i}: {v}")

    # Example: iterate through faces
    for i, f in enumerate(final_faces):
        print(f"Face {i}: {f}")