"""
Analyze what's wrong with polygon optimizer meshes.

NOTE: This script requires trimesh to be installed:
    pip install trimesh

This is a debug/analysis script, not part of the main conversion pipeline.
"""
from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.image_processor import load_and_process_image
from pixel_to_3mf.region_merger import merge_regions_by_color
from pixel_to_3mf.mesh_generator import generate_region_mesh
from pixel_to_3mf.polygon_optimizer import optimize_region_mesh
# from pixel_to_3mf.mesh_validation import validate_mesh  # REMOVED - mesh_validation.py deleted
import sys

# Load castlevania
config = ConversionConfig(
    max_size_mm=200,
    connectivity=8,
    optimize_mesh=True
)

print("Loading castlevania.png...")
pixel_data = load_and_process_image("samples/input/large/castlevania.png", config)

print(f"Image: {pixel_data.width}x{pixel_data.height} pixels")
print(f"Model: {pixel_data.model_width_mm:.1f}x{pixel_data.model_height_mm:.1f}mm")

# Merge regions
print("\nMerging regions...")
regions = merge_regions_by_color(
    pixel_data.pixels,
    pixel_data.width,
    pixel_data.height,
    config.connectivity,
    trim_disconnected=False
)

print(f"Found {len(regions)} regions")

# Test first few regions with optimization
print("\n" + "="*70)
print("COMPARING ORIGINAL vs OPTIMIZED MESHES")
print("="*70)

for i, region in enumerate(regions[:5]):  # Test first 5 regions
    bounds, pixel_coords, rgb = region
    
    print(f"\n=== Region {i+1}: {len(pixel_coords)} pixels, color RGB{rgb} ===")
    
    # Generate original mesh
    original_mesh = generate_region_mesh(
        pixel_coords,
        bounds,
        pixel_data.pixel_size_mm,
        config.color_height_mm
    )
    
    # # Validate original (DISABLED - mesh_validation.py removed)
    # original_result = validate_mesh(original_mesh, f"region_{i+1}_original")
    print(f"\nORIGINAL MESH:")
    print(f"  Vertices: {len(original_mesh.vertices)}")
    print(f"  Triangles: {len(original_mesh.triangles)}")
    # print(f"  Valid: {original_result.is_valid}")
    # if not original_result.is_valid or original_result.warnings:
    #     print(f"  Errors: {len(original_result.errors)}")
    #     for err in original_result.errors[:3]:
    #         print(f"    - {err}")
    #     print(f"  Warnings: {len(original_result.warnings)}")
    #     for warn in original_result.warnings[:3]:
    #         print(f"    - {warn}")
    
    # Generate optimized mesh
    try:
        optimized_mesh = optimize_region_mesh(
            pixel_coords,
            bounds,
            pixel_data.pixel_size_mm,
            config.color_height_mm
        )
        
        # # Validate optimized (DISABLED - mesh_validation.py removed)
        # optimized_result = validate_mesh(optimized_mesh, f"region_{i+1}_optimized")
        print(f"\nOPTIMIZED MESH:")
        print(f"  Vertices: {len(optimized_mesh.vertices)}")
        print(f"  Triangles: {len(optimized_mesh.triangles)}")
        print(f"  Reduction: {100 * (1 - len(optimized_mesh.vertices) / len(original_mesh.vertices)):.1f}%")
        # print(f"  Valid: {optimized_result.is_valid}")
        # if not optimized_result.is_valid or optimized_result.warnings:
        #     print(f"  Errors: {len(optimized_result.errors)}")
        #     for err in optimized_result.errors:
        #         print(f"    - {err}")
        #     print(f"  Warnings: {len(optimized_result.warnings)}")
        #     for warn in optimized_result.warnings:
        #         print(f"    - {warn}")
        
        # Check for non-manifold edges specifically
        import trimesh
        import numpy as np
        tmesh = trimesh.Trimesh(
            vertices=optimized_mesh.vertices,
            faces=optimized_mesh.triangles,
            process=False
        )
        
        # Manual edge count
        edge_face_count = {}
        for face_idx, face in enumerate(optimized_mesh.triangles):
            edges = [
                tuple(sorted([face[0], face[1]])),
                tuple(sorted([face[1], face[2]])),
                tuple(sorted([face[2], face[0]])),
            ]
            for edge in edges:
                edge_face_count[edge] = edge_face_count.get(edge, 0) + 1
        
        edges_with_1_face = sum(1 for count in edge_face_count.values() if count == 1)
        edges_with_2_faces = sum(1 for count in edge_face_count.values() if count == 2)
        edges_with_3plus = sum(1 for count in edge_face_count.values() if count > 2)
        
        print(f"\nEDGE ANALYSIS:")
        print(f"  Boundary edges (1 face): {edges_with_1_face}")
        print(f"  Manifold edges (2 faces): {edges_with_2_faces}")
        print(f"  Non-manifold edges (3+ faces): {edges_with_3plus}")
        
        if edges_with_3plus > 0:
            print(f"\n  NON-MANIFOLD EDGE DETAILS:")
            for edge, count in edge_face_count.items():
                if count > 2:
                    v1_idx, v2_idx = edge
                    v1 = optimized_mesh.vertices[v1_idx]
                    v2 = optimized_mesh.vertices[v2_idx]
                    print(f"    Edge {v1_idx}-{v2_idx}: {count} faces")
                    print(f"      V{v1_idx}: ({v1[0]:.3f}, {v1[1]:.3f}, {v1[2]:.3f})")
                    print(f"      V{v2_idx}: ({v2[0]:.3f}, {v2[1]:.3f}, {v2[2]:.3f})")
        
    except Exception as e:
        print(f"\nOPTIMIZED MESH FAILED: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*70)
print("Analysis complete!")
