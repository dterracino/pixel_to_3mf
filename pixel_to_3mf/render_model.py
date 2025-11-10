"""
3D model rendering module for visualizing generated meshes.

This module renders the 3D model meshes to PNG images using matplotlib's
3D plotting capabilities. It creates a visualization showing all colored
regions with their correct colors and a slight camera tilt for better viewing.

WHY: This allows users to preview their 3D model without needing to open
a slicer application, making it easier to verify the conversion results.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless operation

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path

from .mesh_generator import Mesh


def render_meshes_to_file(
    meshes: List[Tuple[Mesh, str]],
    region_colors: List[Tuple[int, int, int]],
    output_path: str,
    model_width_mm: float,
    model_height_mm: float,
    backing_color: Tuple[int, int, int] = (255, 255, 255)
) -> None:
    """
    Render 3D meshes to a PNG file with correct colors.
    
    Creates a 3D visualization of all the meshes (colored regions + backing plate)
    with a slightly tilted viewing angle for better visualization. Each region
    is rendered with its actual color from the source image.
    
    WHY: Users want to preview their 3D model without opening a slicer. This
    provides instant visual feedback on the conversion result.
    
    Args:
        meshes: List of (Mesh, name) tuples - all regions plus backing plate
        region_colors: List of RGB tuples for each colored region
        output_path: Path where the PNG should be saved
        model_width_mm: Width of the model in millimeters (for setting view bounds)
        model_height_mm: Height of the model in millimeters (for setting view bounds)
        backing_color: RGB color for the backing plate (default: white)
    
    Raises:
        IOError: If the output file cannot be written
    """
    # Create figure with good size for detail
    fig = plt.figure(figsize=(12, 12), dpi=150)
    ax = fig.add_subplot(111, projection='3d')
    
    # Track color index - we need to match colors to regions
    color_index = 0
    
    # Process each mesh
    for mesh, name in meshes:
        # Determine the color for this mesh
        if name == "backing_plate":
            # Backing plate uses backing color
            color = np.array(backing_color) / 255.0  # Normalize to 0-1
        else:
            # This is a colored region - use its color
            if color_index < len(region_colors):
                color = np.array(region_colors[color_index]) / 255.0  # Normalize to 0-1
                color_index += 1
            else:
                # Fallback to gray if we somehow run out of colors
                color = np.array([128, 128, 128]) / 255.0
        
        # Convert mesh triangles to 3D polygons
        # Each triangle is defined by 3 vertex indices
        vertices_array = np.array(mesh.vertices)
        
        # Create list of triangular faces for Poly3DCollection
        faces = []
        for tri in mesh.triangles:
            # tri is (v0_idx, v1_idx, v2_idx)
            # Get the actual 3D coordinates for each vertex
            face = [
                vertices_array[tri[0]],
                vertices_array[tri[1]],
                vertices_array[tri[2]]
            ]
            faces.append(face)
        
        # Create polygon collection with this color
        # Alpha slightly less than 1.0 to show depth better
        poly = Poly3DCollection(
            faces,
            alpha=0.9,
            facecolor=color,
            edgecolor='black',
            linewidths=0.1
        )
        ax.add_collection3d(poly)
    
    # Set view limits based on model dimensions
    # Add a small margin for better visualization
    margin = max(model_width_mm, model_height_mm) * 0.1
    ax.set_xlim([0 - margin, model_width_mm + margin])
    ax.set_ylim([0 - margin, model_height_mm + margin])
    
    # Z limit depends on the maximum Z coordinate in the meshes
    max_z = 0
    for mesh, _ in meshes:
        for vertex in mesh.vertices:
            max_z = max(max_z, vertex[2])
    ax.set_zlim([0, max_z + margin])
    
    # Set labels
    ax.set_xlabel('X (mm)', fontsize=10)
    ax.set_ylabel('Y (mm)', fontsize=10)
    ax.set_zlabel('Z (mm)', fontsize=10)
    
    # Set viewing angle - slight tilt to see the model better
    # Default view is too straight-on
    # elev=30 means 30 degrees above the horizontal plane
    # azim=-60 means rotated 60 degrees counter-clockwise from the Y-axis
    ax.view_init(elev=30, azim=-60)
    
    # Add title
    ax.set_title('3D Model Preview', fontsize=14, fontweight='bold')
    
    # Save to file
    plt.savefig(output_path, bbox_inches='tight', dpi=150)
    plt.close(fig)


def generate_render_path(output_path: str) -> str:
    """
    Generate the render file path from the 3MF output path.
    
    Follows the pattern: {output_name}_render.png
    
    Args:
        output_path: Path to the 3MF output file
        
    Returns:
        Path where the render PNG should be saved
        
    Example:
        >>> generate_render_path("output/model.3mf")
        'output/model_render.png'
    """
    output_file = Path(output_path)
    stem = output_file.stem  # filename without extension
    parent = output_file.parent
    
    return str(parent / f"{stem}_render.png")
