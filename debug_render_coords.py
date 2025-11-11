#!/usr/bin/env python3
"""
Debug script to analyze 3D model coordinate transformations.

This script helps diagnose rendering issues by showing mesh coordinates
from multiple viewing angles and displaying coordinate transformation details.

Usage:
    python debug_render_coords.py <input_image> [--output <3mf_file>]
"""

import sys
import os
from pathlib import Path
import argparse

# Add pixel_to_3mf to path
sys.path.insert(0, str(Path(__file__).parent))

from pixel_to_3mf.image_processor import load_image
from pixel_to_3mf.region_merger import merge_regions
from pixel_to_3mf.mesh_generator import generate_region_mesh, generate_backing_plate
from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.pixel_to_3mf import _create_filtered_pixel_data


def analyze_mesh_coordinates(mesh, name):
    """
    Analyze and print coordinate statistics for a mesh.
    
    Args:
        mesh: Mesh object to analyze
        name: Name of the mesh for display
    """
    if not mesh.vertices:
        print(f"\n{name}: NO VERTICES")
        return
    
    # Find min/max coordinates
    min_x = min(v[0] for v in mesh.vertices)
    max_x = max(v[0] for v in mesh.vertices)
    min_y = min(v[1] for v in mesh.vertices)
    max_y = max(v[1] for v in mesh.vertices)
    min_z = min(v[2] for v in mesh.vertices)
    max_z = max(v[2] for v in mesh.vertices)
    
    print(f"\n{name}:")
    print(f"  Vertices: {len(mesh.vertices)}")
    print(f"  Triangles: {len(mesh.triangles)}")
    print(f"  X range: [{min_x:.3f}, {max_x:.3f}] (width: {max_x - min_x:.3f}mm)")
    print(f"  Y range: [{min_y:.3f}, {max_y:.3f}] (height: {max_y - min_y:.3f}mm)")
    print(f"  Z range: [{min_z:.3f}, {max_z:.3f}] (depth: {max_z - min_z:.3f}mm)")
    
    # Show some sample vertices
    print(f"  First 5 vertices:")
    for i, v in enumerate(mesh.vertices[:5]):
        print(f"    [{i}] ({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})")
    
    if len(mesh.vertices) > 5:
        print(f"  Last 5 vertices:")
        for i in range(max(0, len(mesh.vertices) - 5), len(mesh.vertices)):
            v = mesh.vertices[i]
            print(f"    [{i}] ({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})")


def print_coordinate_summary(meshes, region_colors, model_width_mm, model_height_mm, backing_color):
    """
    Print comprehensive coordinate summary for all meshes.
    
    Args:
        meshes: List of (Mesh, name) tuples
        region_colors: List of RGB colors for regions
        model_width_mm: Model width
        model_height_mm: Model height
        backing_color: RGB color for backing plate
    """
    print("\n" + "="*80)
    print("COORDINATE ANALYSIS")
    print("="*80)
    
    print(f"\nModel Dimensions: {model_width_mm:.3f}mm x {model_height_mm:.3f}mm")
    print(f"Total meshes: {len(meshes)}")
    
    # Track overall bounds
    overall_min_x = float('inf')
    overall_max_x = float('-inf')
    overall_min_y = float('inf')
    overall_max_y = float('-inf')
    overall_min_z = float('inf')
    overall_max_z = float('-inf')
    
    # Analyze each mesh
    color_index = 0
    for mesh, name in meshes:
        if mesh.vertices:
            min_x = min(v[0] for v in mesh.vertices)
            max_x = max(v[0] for v in mesh.vertices)
            min_y = min(v[1] for v in mesh.vertices)
            max_y = max(v[1] for v in mesh.vertices)
            min_z = min(v[2] for v in mesh.vertices)
            max_z = max(v[2] for v in mesh.vertices)
            
            overall_min_x = min(overall_min_x, min_x)
            overall_max_x = max(overall_max_x, max_x)
            overall_min_y = min(overall_min_y, min_y)
            overall_max_y = max(overall_max_y, max_y)
            overall_min_z = min(overall_min_z, min_z)
            overall_max_z = max(overall_max_z, max_z)
        
        # Determine color for this mesh
        if name == "backing_plate":
            color = backing_color
            color_str = f"RGB{backing_color}"
        else:
            if color_index < len(region_colors):
                color = region_colors[color_index]
                color_str = f"RGB{region_colors[color_index]}"
                color_index += 1
            else:
                color = (128, 128, 128)
                color_str = "RGB(128, 128, 128) [fallback]"
        
        analyze_mesh_coordinates(mesh, f"{name} - {color_str}")
    
    # Print overall bounds
    print("\n" + "-"*80)
    print("OVERALL BOUNDS (all meshes combined):")
    print(f"  X: [{overall_min_x:.3f}, {overall_max_x:.3f}]")
    print(f"  Y: [{overall_min_y:.3f}, {overall_max_y:.3f}]")
    print(f"  Z: [{overall_min_z:.3f}, {overall_max_z:.3f}]")
    print("-"*80)


def create_multi_view_renders(meshes, region_colors, output_base_path, model_width_mm, model_height_mm, backing_color):
    """
    Create renders from multiple viewing angles to help diagnose issues.
    
    Args:
        meshes: List of (Mesh, name) tuples
        region_colors: List of RGB colors for regions
        output_base_path: Base path for output files
        model_width_mm: Model width
        model_height_mm: Model height
        backing_color: RGB color for backing plate
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np
    
    # Define viewing angles: (elevation, azimuth, description)
    views = [
        (90, 0, "top_view"),        # Looking straight down from above
        (-90, 0, "bottom_view"),    # Looking straight up from below
        (0, 0, "front_view"),       # Looking from front (along Y axis)
        (0, 90, "right_view"),      # Looking from right (along X axis)
        (0, -90, "left_view"),      # Looking from left
        (30, -60, "default_view"),  # Default 3D view (current implementation)
        (45, -45, "isometric_view"), # Isometric-style view
    ]
    
    output_dir = Path(output_base_path).parent
    output_stem = Path(output_base_path).stem
    
    print("\n" + "="*80)
    print("GENERATING MULTI-VIEW RENDERS")
    print("="*80)
    
    # Create figure and axes ONCE - reuse for all views
    fig = plt.figure(figsize=(12, 12), dpi=96)
    ax = fig.add_subplot(111, projection='3d')
    
    # Track color index
    color_index = 0
    
    # Separate backing plate from regions to control render order
    # WHY: Backing plate must be rendered FIRST (added to axes first) so that
    # colored regions are always rendered on top. Matplotlib's 3D painter's
    # algorithm can fail with certain viewing angles if backing plate is added last.
    backing_plate_mesh = None
    region_meshes = []
    
    for mesh, name in meshes:
        if name == "backing_plate":
            backing_plate_mesh = (mesh, name)
        else:
            region_meshes.append((mesh, name))
    
    # Process backing plate FIRST if it exists
    meshes_ordered = []
    if backing_plate_mesh:
        meshes_ordered.append(backing_plate_mesh)
    meshes_ordered.extend(region_meshes)
    
    # Add all meshes to the plot ONCE
    # WHY: We only need to create the geometry once, then just change the viewing angle
    # for each output image. This is much more efficient than recreating the entire
    # plot for each view.
    # 
    # CRITICAL: We add backing plate FIRST, then colored regions. Combined with a
    # significant Z-offset on the backing plate, this ensures it renders behind the
    # colored regions from all viewing angles.
    for mesh, name in meshes_ordered:
        # Determine color and transparency
        if name == "backing_plate":
            color = np.array(backing_color) / 255.0
            # Use lower alpha for backing plate so regions show through if needed
            alpha = 0.6
        else:
            if color_index < len(region_colors):
                color = np.array(region_colors[color_index]) / 255.0
                color_index += 1
            else:
                color = np.array([128, 128, 128]) / 255.0
            alpha = 1.0  # Full opacity for colored regions
        
        # Convert mesh to polygons
        vertices_array = np.array(mesh.vertices)
        
        # Apply Z-offset to backing plate to ensure it renders behind colored regions
        # WHY: Color layers are typically 1mm thick, so we offset by 1mm to completely
        # separate the backing plate from the colored regions with no overlap. This
        # ensures Matplotlib's painter's algorithm can correctly determine depth order
        # from all viewing angles (the 0.1mm offset wasn't enough when layers overlapped).
        if name == "backing_plate":
            vertices_array = vertices_array.copy()  # Don't modify original
            vertices_array[:, 2] -= 1.0  # Shift Z coordinate down by 1mm for complete separation
        
        faces = []
        for tri in mesh.triangles:
            face = [
                vertices_array[tri[0]],
                vertices_array[tri[1]],
                vertices_array[tri[2]]
            ]
            faces.append(face)
        
        # Create polygon collection
        # WHY: Matplotlib's painter's algorithm struggles with depth sorting at certain
        # angles. We rely on: (1) Adding backing plate first, (2) Large Z-offset (1mm),
        # (3) Lower alpha on backing plate. This combination ensures colored regions
        # always appear on top regardless of viewing angle.
        poly = Poly3DCollection(
            faces,
            alpha=alpha,
            facecolor=color,
            edgecolor='black',
            linewidths=0.1
        )
        ax.add_collection3d(poly)
    
    # Set view limits (only need to do this once)
    margin = max(model_width_mm, model_height_mm) * 0.1
    ax.set_xlim([0 - margin, model_width_mm + margin])
    ax.set_ylim([0 - margin, model_height_mm + margin])
    
    # Calculate Z limits from actual mesh data
    min_z = 0
    max_z = 0
    for mesh, _ in meshes:
        for vertex in mesh.vertices:
            min_z = min(min_z, vertex[2])
            max_z = max(max_z, vertex[2])
    ax.set_zlim([min_z - margin, max_z + margin])
    
    # Set labels (only need to do this once)
    ax.set_xlabel('X (mm)', fontsize=10)
    ax.set_ylabel('Y (mm)', fontsize=10)
    ax.set_zlabel('Z (mm)', fontsize=10)
    
    # Now loop through views and just change the camera angle + save
    for elev, azim, view_name in views:
        print(f"\nCreating {view_name} (elev={elev}, azim={azim})...")
        
        # Update view angle (this is fast - just rotates the camera)
        ax.view_init(elev=elev, azim=azim)
        
        # Update title for this view
        title = f'3D Model Preview - {view_name.replace("_", " ").title()}\n'
        title += f'(elevation={elev}°, azimuth={azim}°)'
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # Save this view
        output_path = output_dir / f"{output_stem}_{view_name}.png"
        plt.savefig(output_path, bbox_inches='tight', dpi=96)
        
        print(f"  Saved: {output_path}")
    
    # Close the figure after all views are saved
    plt.close(fig)
    
    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description="Debug script to analyze 3D model coordinate transformations"
    )
    parser.add_argument("input", help="Input image file")
    parser.add_argument("--output", "-o", help="Output base path (default: same directory as input file)")
    parser.add_argument("--max-size", type=float, default=200.0, help="Maximum model dimension in mm")
    parser.add_argument("--color-height", type=float, default=1.0, help="Color layer height in mm")
    parser.add_argument("--base-height", type=float, default=1.0, help="Base layer height in mm")
    
    args = parser.parse_args()
    
    # Default output path - same directory as input file with _debug suffix
    if args.output:
        output_base = args.output
    else:
        input_path = Path(args.input)
        output_base = str(input_path.parent / f"{input_path.stem}_debug")
    
    print("="*80)
    print("DEBUG: 3D MODEL COORDINATE ANALYSIS")
    print("="*80)
    print(f"Input: {args.input}")
    print(f"Output base: {output_base}")
    print(f"Max size: {args.max_size}mm")
    print(f"Color height: {args.color_height}mm")
    print(f"Base height: {args.base_height}mm")
    
    # Create config
    config = ConversionConfig(
        max_size_mm=args.max_size,
        color_height_mm=args.color_height,
        base_height_mm=args.base_height,
        backing_color=(255, 255, 255)
    )
    
    # Load image
    print("\n" + "-"*80)
    print("Loading image...")
    pixel_data = load_image(args.input, config)
    print(f"Image: {pixel_data.width}x{pixel_data.height} pixels")
    print(f"Pixel size: {pixel_data.pixel_size_mm:.3f}mm")
    print(f"Model dimensions: {pixel_data.width * pixel_data.pixel_size_mm:.3f}mm x {pixel_data.height * pixel_data.pixel_size_mm:.3f}mm")
    
    # Merge regions
    print("\n" + "-"*80)
    print("Merging regions...")
    regions = merge_regions(pixel_data, config)
    region_colors = [region.color for region in regions]
    print(f"Found {len(regions)} regions with {len(set(region_colors))} unique colors")
    
    # Generate meshes
    print("\n" + "-"*80)
    print("Generating meshes...")
    meshes = []
    
    for i, region in enumerate(regions):
        mesh = generate_region_mesh(region, pixel_data, config)
        meshes.append((mesh, f"region_{i+1}"))
    
    # Generate backing plate
    filtered_pixel_data = _create_filtered_pixel_data(regions, pixel_data)
    backing_mesh = generate_backing_plate(filtered_pixel_data, config)
    meshes.append((backing_mesh, "backing_plate"))
    
    print(f"Generated {len(meshes)} meshes total")
    
    # Calculate model dimensions
    model_width_mm = pixel_data.width * pixel_data.pixel_size_mm
    model_height_mm = pixel_data.height * pixel_data.pixel_size_mm
    
    # Print coordinate analysis
    print_coordinate_summary(
        meshes,
        region_colors,
        model_width_mm,
        model_height_mm,
        config.backing_color
    )
    
    # Create multi-view renders
    create_multi_view_renders(
        meshes,
        region_colors,
        output_base,
        model_width_mm,
        model_height_mm,
        config.backing_color
    )
    
    print("\n" + "="*80)
    print("DEBUG ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
