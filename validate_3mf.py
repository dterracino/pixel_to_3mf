"""
Quick validation script to check for non-manifold edges in a 3MF file.
"""
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
import sys

def count_non_manifold_edges(threemf_path):
    """Count non-manifold and boundary edges in a 3MF file."""
    
    with zipfile.ZipFile(threemf_path, 'r') as zf:
        # Find all .model files
        model_files = [name for name in zf.namelist() if name.endswith('.model')]
        
        print(f"\nAnalyzing: {threemf_path}")
        print(f"Found {len(model_files)} model file(s): {model_files}\n")
        
        total_boundary = 0
        total_non_manifold = 0
        
        for model_file in model_files:
            print(f"=== {model_file} ===")
            
            with zf.open(model_file) as f:
                tree = ET.parse(f)
                root = tree.getroot()
            
            # Handle namespace
            ns = {'': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
            meshes = root.findall('.//mesh', ns)
            
            if not meshes:
                print("  No meshes found")
                continue
            
            print(f"  {len(meshes)} mesh(es) found\n")
            
            for mesh_idx, mesh in enumerate(meshes, 1):
                # Count edges
                edge_count = defaultdict(int)
                
                triangles = mesh.findall('.//triangle', ns)
                for tri in triangles:
                    v1 = int(tri.get('v1'))
                    v2 = int(tri.get('v2'))
                    v3 = int(tri.get('v3'))
                    
                    # Add all 3 edges (normalized so (a,b) == (b,a))
                    edges = [
                        (min(v1, v2), max(v1, v2)),
                        (min(v2, v3), max(v2, v3)),
                        (min(v3, v1), max(v3, v1))
                    ]
                    
                    for edge in edges:
                        edge_count[edge] += 1
                
                # Count boundary and non-manifold
                boundary = sum(1 for count in edge_count.values() if count == 1)
                non_manifold = sum(1 for count in edge_count.values() if count > 2)
                
                total_boundary += boundary
                total_non_manifold += non_manifold
                
                if boundary > 0 or non_manifold > 0:
                    print(f"  Mesh #{mesh_idx}:")
                    if boundary > 0:
                        print(f"    ❌ Boundary edges: {boundary}")
                    if non_manifold > 0:
                        print(f"    ❌ Non-manifold edges: {non_manifold}")
                else:
                    print(f"  Mesh #{mesh_idx}: ✅ Manifold (0 boundary, 0 non-manifold)")
        
        print(f"\n{'='*60}")
        print(f"TOTAL: {total_boundary} boundary edges, {total_non_manifold} non-manifold edges")
        
        if total_boundary == 0 and total_non_manifold == 0:
            print("✅ ALL MESHES ARE MANIFOLD!")
        else:
            print("❌ NON-MANIFOLD GEOMETRY DETECTED")
        print(f"{'='*60}\n")
        
        return total_boundary, total_non_manifold

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_3mf.py <file.3mf>")
        sys.exit(1)
    
    count_non_manifold_edges(sys.argv[1])
