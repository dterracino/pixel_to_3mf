"""
Generic 3MF file writer with pluggable application logic.

This module provides a reusable 3MF writer that handles all standard 3MF
file generation operations while allowing applications to customize object
naming, material assignment, positioning, and thumbnail generation through
callback functions.

The 3MF format is a ZIP archive containing XML files that describe 3D models,
their assembly, and metadata. This writer handles the boilerplate while you
focus on your application's specific needs.

Example usage:
    from pixel_to_3mf.threemf_core import (
        ThreeMFWriter, ThreeMFMesh,
        create_centering_transform
    )
    
    # Define your callbacks
    def my_naming(obj_id, mesh):
        return f"Part {obj_id}"
    
    def my_slots(obj_id, mesh):
        return 1  # Single material
    
    def my_transforms(obj_id, mesh, context):
        # Center on origin
        center_x, center_y = context  # Assume context is (width, height)
        return (center_x / 2.0, center_y / 2.0, 0.0)
    
    # Create writer with callbacks
    writer = ThreeMFWriter(
        naming_callback=my_naming,
        slot_callback=my_slots,
        transform_callback=my_transforms
    )
    
    # Prepare meshes
    meshes = [
        ThreeMFMesh(
            vertices=[(0,0,0), (1,0,0), (1,1,0)],
            triangles=[(0,1,2)],
            metadata={'color': 'red'}
        )
    ]
    
    # Write file
    result = writer.write("output.3mf", meshes, context=(10.0, 10.0))
"""

import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Tuple, Dict, Any, Optional, Callable
from dataclasses import dataclass
import uuid

from .constants import COORDINATE_PRECISION

# ============================================================================
# XML Namespaces (3MF Specification)
# ============================================================================

NS_3MF = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_PRODUCTION = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS_BAMBU = "http://schemas.bambulab.com/package/2021"

# ============================================================================
# Core Data Structures
# ============================================================================

@dataclass
class ThreeMFMesh:
    """
    Generic mesh representation for 3MF export.
    
    A mesh consists of vertices (3D points) and triangles (groups of 3 vertex indices).
    Additional application-specific data can be stored in the metadata dict.
    
    Attributes:
        vertices: List of (x, y, z) coordinates in millimeters
        triangles: List of (v1, v2, v3) vertex indices forming triangles
        metadata: Dictionary for application-specific data (colors, names, etc.)
    
    Example:
        mesh = ThreeMFMesh(
            vertices=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
            triangles=[(0, 1, 2), (0, 2, 3)],
            metadata={'color_name': 'Red', 'ams_slot': 2}
        )
    """
    vertices: List[Tuple[float, float, float]]
    triangles: List[Tuple[int, int, int]]
    metadata: Dict[str, Any]

@dataclass
class ThreeMFObject:
    """
    Represents a 3MF object with all its properties.
    
    This combines the mesh geometry with its placement and material assignment.
    The writer uses this to generate the complete 3MF structure.
    
    Attributes:
        object_id: Unique ID (1-indexed, typically 1, 2, 3, ...)
        name: Display name shown in slicer UI
        extruder_slot: Material slot number (1-N, or 0 for container objects)
        transform: (x, y, z) offset in millimeters
        mesh: The mesh geometry
    """
    object_id: int
    name: str
    extruder_slot: int
    transform: Tuple[float, float, float]
    mesh: ThreeMFMesh

# ============================================================================
# Callback Type Definitions
# ============================================================================

ObjectNamingCallback = Callable[[int, ThreeMFMesh], str]
"""
Callback to determine the display name for an object.

This function is called for each mesh to determine what name appears in the
slicer's object list. Common strategies include:
- Naming by color: "Red", "Blue", "Green"
- Naming by material: "PLA Basic", "PETG Matte"
- Naming by part: "Body", "Lid", "Handle"
- Sequential naming: "Part 1", "Part 2", "Part 3"

Args:
    object_id: The object's ID (1-indexed)
    mesh: The mesh being named (check metadata for color, material, etc.)

Returns:
    Display name string (e.g., "Red", "Part 1", "Body")

Example:
    def name_by_color(obj_id: int, mesh: ThreeMFMesh) -> str:
        return mesh.metadata.get('color_name', f'Object {obj_id}')
"""

SlotAssignmentCallback = Callable[[int, ThreeMFMesh], int]
"""
Callback to assign material/extruder slot numbers to objects.

Multi-material printers (like Bambu Lab AMS) need to know which material
slot to use for each object. This function determines the slot assignment.

Common strategies include:
- Single material: Always return 1
- AMS color grouping: Group by color name (1 = white backing, 2+ = colors)
- Multi-material: Assign slots based on material properties
- Custom mapping: Use metadata to determine slot

Args:
    object_id: The object's ID (1-indexed)
    mesh: The mesh being assigned (check metadata for color, material, etc.)

Returns:
    Slot number (1-16 for Bambu AMS, 1-N for other systems, 0 for containers)

Example:
    def single_material(obj_id: int, mesh: ThreeMFMesh) -> int:
        return 1  # Everything uses slot 1
    
    def ams_by_color(obj_id: int, mesh: ThreeMFMesh) -> int:
        return mesh.metadata.get('ams_slot', 1)
"""

TransformCalculationCallback = Callable[[int, ThreeMFMesh, Any], Tuple[float, float, float]]
"""
Callback to calculate object positioning (3D transform).

Determines where each object sits in 3D space. The transform is an (x, y, z)
offset in millimeters. Common strategies include:
- Centered on origin: Use calculate_model_center() utility
- Stacked vertically: Calculate z-offset based on object height
- Grid layout: Arrange objects in a grid pattern
- Custom placement: Use metadata to determine position

Args:
    object_id: The object's ID (1-indexed)
    mesh: The mesh being positioned
    context: Application-specific context (e.g., model dimensions, layout info)

Returns:
    (x, y, z) offset in millimeters

Example:
    def center_on_origin(obj_id: int, mesh: ThreeMFMesh, context: Any) -> Tuple[float, float, float]:
        bounds = context  # Assume context is (width, height)
        center_x = bounds[0] / 2.0
        center_y = bounds[1] / 2.0
        z_offset = mesh.metadata.get('z_offset', 0.0)
        return (center_x, center_y, z_offset)
"""

ThumbnailGenerationCallback = Callable[[str, Any], List[Tuple[str, bytes]]]
"""
Callback to generate thumbnail images for the 3MF file.

Slicers display thumbnails in their UI and on printer screens. This function
generates thumbnail images from your source data. Common strategies include:
- Render views: Top view, isometric view, etc.
- Screenshots: Use source images or renders
- Generated: Create thumbnails from mesh data
- None: Return empty list for no thumbnails

Args:
    output_path: Path where the 3MF will be saved (for naming/context)
    context: Application-specific context (source images, render data, etc.)

Returns:
    List of (zip_path, image_bytes) tuples
    - zip_path: Path inside the 3MF archive (e.g., "Metadata/top_1.png")
    - image_bytes: PNG image data as bytes

Example:
    def no_thumbnails(output_path: str, context: Any) -> List[Tuple[str, bytes]]:
        return []  # No thumbnails
    
    def single_thumbnail(output_path: str, context: Any) -> List[Tuple[str, bytes]]:
        img_data = generate_thumbnail(context)
        return [("Metadata/thumbnail.png", img_data)]
"""

ProgressCallback = Callable[[str, str], None]
"""
Callback for progress reporting during 3MF generation.

Applications can use this to display progress to users during export.
The callback receives a stage name and a message describing the current operation.

Args:
    stage: Stage name (e.g., "export", "assembly", "thumbnails")
    message: Progress message (e.g., "Generating 44 objects...")

Example:
    def show_progress(stage: str, message: str) -> None:
        print(f"[{stage}] {message}")
"""

# ============================================================================
# Core Utility Functions (Application-Independent)
# ============================================================================

def prettify_xml(elem: ET.Element) -> str:
    """
    Convert an XML element tree to a pretty-printed string.
    
    ElementTree's tostring() creates ugly one-line XML. This function
    makes it readable with proper indentation for debugging.
    
    WHY: Pretty-printed XML is much easier to debug when inspecting
    3MF files manually or troubleshooting slicer import issues.
    
    Args:
        elem: Root element of the XML tree
    
    Returns:
        Pretty-printed XML string with <?xml?> declaration
    """
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def format_float(value: float, precision: int = COORDINATE_PRECISION) -> str:
    """
    Format a float for XML with specified precision.
    
    Strips trailing zeros for cleaner output and smaller file sizes.
    Example: 1.50000 -> "1.5", 2.0 -> "2"
    
    WHY: 3MF files can get large with many coordinates. Stripping
    trailing zeros reduces file size without losing precision.
    
    Args:
        value: Float value to format
        precision: Number of decimal places (default from constants)
    
    Returns:
        Formatted string with trailing zeros removed
    """
    return f"{value:.{precision}f}".rstrip('0').rstrip('.')


def calculate_model_bounds(meshes: List[ThreeMFMesh]) -> Tuple[float, float, float, float, float, float]:
    """
    Calculate the bounding box of all meshes.
    
    WHY: Many applications need to know model dimensions for centering,
    scaling, or layout calculations. This utility provides that information
    by finding the min/max coordinates across all mesh vertices.
    
    Args:
        meshes: List of meshes to analyze
    
    Returns:
        (min_x, max_x, min_y, max_y, min_z, max_z) in millimeters
        Returns (0, 0, 0, 0, 0, 0) if meshes is empty
    
    Example:
        bounds = calculate_model_bounds(meshes)
        width = bounds[1] - bounds[0]  # max_x - min_x
        height = bounds[3] - bounds[2]  # max_y - min_y
        depth = bounds[5] - bounds[4]   # max_z - min_z
    """
    if not meshes:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    
    # Filter out meshes with no vertices
    valid_meshes = [mesh for mesh in meshes if mesh.vertices]
    if not valid_meshes:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    
    min_x = min(min(v[0] for v in mesh.vertices) for mesh in valid_meshes)
    max_x = max(max(v[0] for v in mesh.vertices) for mesh in valid_meshes)
    min_y = min(min(v[1] for v in mesh.vertices) for mesh in valid_meshes)
    max_y = max(max(v[1] for v in mesh.vertices) for mesh in valid_meshes)
    min_z = min(min(v[2] for v in mesh.vertices) for mesh in valid_meshes)
    max_z = max(max(v[2] for v in mesh.vertices) for mesh in valid_meshes)
    
    return (min_x, max_x, min_y, max_y, min_z, max_z)


def calculate_model_center(meshes: List[ThreeMFMesh]) -> Tuple[float, float]:
    """
    Calculate the XY center point of all meshes.
    
    WHY: Most applications want models centered on the build plate.
    This utility calculates the center point for centering transforms.
    
    The Z coordinate is not included because vertical positioning is
    typically application-specific (stacking, layer heights, etc.).
    
    Args:
        meshes: List of meshes to analyze
    
    Returns:
        (center_x, center_y) in millimeters
        Returns (0.0, 0.0) if meshes is empty
    
    Example:
        center_x, center_y = calculate_model_center(meshes)
        # Use these to create transforms that center the model
    """
    min_x, max_x, min_y, max_y, _, _ = calculate_model_bounds(meshes)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    return (center_x, center_y)


def create_centering_transform(
    meshes: List[ThreeMFMesh],
    z_offset: float = 0.0
) -> Tuple[float, float, float]:
    """
    Create a transform that centers meshes on the XY origin.
    
    WHY: Most applications want models centered on the build plate.
    This is the most common transform calculation, so we provide it
    as a standard utility. Applications can use this directly or
    as a starting point for custom transforms.
    
    Args:
        meshes: List of meshes to center
        z_offset: Optional Z-axis offset in millimeters (default: 0.0)
    
    Returns:
        (x, y, z) transform in millimeters that centers the model
    
    Example:
        # Simple centering at z=0
        transform = create_centering_transform(meshes)
        
        # Center with 2mm z-offset
        transform = create_centering_transform(meshes, z_offset=2.0)
    """
    center_x, center_y = calculate_model_center(meshes)
    return (center_x, center_y, z_offset)


def count_mesh_stats(meshes: List[ThreeMFMesh]) -> Tuple[int, int]:
    """
    Count total vertices and triangles across all meshes.
    
    WHY: Useful for reporting mesh complexity to users and validating
    mesh generation in tests. Larger models have more triangles.
    
    Args:
        meshes: List of meshes to analyze
    
    Returns:
        (total_vertices, total_triangles)
    
    Example:
        vertices, triangles = count_mesh_stats(meshes)
        print(f"Model has {vertices} vertices and {triangles} triangles")
    """
    total_vertices = sum(len(mesh.vertices) for mesh in meshes)
    total_triangles = sum(len(mesh.triangles) for mesh in meshes)
    return total_vertices, total_triangles


def validate_triangle_winding(mesh: ThreeMFMesh) -> str:
    """
    Determine the predominant winding order of triangles in a mesh.
    
    Counter-clockwise (CCW) winding means normals point outward from the surface,
    which is the standard convention for 3D meshes.
    
    For a 3D mesh with multiple faces (top, bottom, sides), we look at the
    top surface triangles (those with highest Z coordinate) to determine winding,
    as those should all face upward (positive Z normal).
    
    WHY: Correct winding is critical for proper rendering and slicing.
    Slicers use normals to determine inside vs outside of the model.
    
    Args:
        mesh: The mesh to validate
    
    Returns:
        "CCW" if triangles use counter-clockwise winding (normals point out),
        "CW" if triangles use clockwise winding (normals point in),
        "MIXED" if winding is inconsistent,
        "UNKNOWN" if mesh is empty or all triangles are degenerate
    """
    # Check if mesh has triangles
    if not mesh.triangles:
        return "UNKNOWN"
    
    # Find the max Z coordinate to identify top surface triangles
    max_z = max(max(mesh.vertices[i][2] for i in tri) for tri in mesh.triangles)
    
    # Collect winding for top surface triangles (those with vertices near max_z)
    top_face_winding = []
    
    for tri in mesh.triangles:
        # Get vertices
        v0 = mesh.vertices[tri[0]]
        v1 = mesh.vertices[tri[1]]
        v2 = mesh.vertices[tri[2]]
        
        # Check if this is a top surface triangle (all vertices at max Z)
        if abs(v0[2] - max_z) < 1e-6 and abs(v1[2] - max_z) < 1e-6 and abs(v2[2] - max_z) < 1e-6:
            # Compute edge vectors
            edge1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            edge2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            
            # Cross product gives normal vector (right-hand rule)
            # For top surface, positive Z normal = CCW, negative Z normal = CW
            normal_z = edge1[0] * edge2[1] - edge1[1] * edge2[0]
            
            if abs(normal_z) > 1e-10:  # Not degenerate
                top_face_winding.append("CCW" if normal_z > 0 else "CW")
    
    if not top_face_winding:
        return "UNKNOWN"
    
    # Check consistency
    ccw_count = sum(1 for w in top_face_winding if w == "CCW")
    cw_count = sum(1 for w in top_face_winding if w == "CW")
    
    if ccw_count > 0 and cw_count == 0:
        return "CCW"
    elif cw_count > 0 and ccw_count == 0:
        return "CW"
    else:
        return "MIXED"


# ============================================================================
# XML Generation Functions (3MF Specification)
# ============================================================================

def _generate_object_model_xml(objects: List[ThreeMFObject]) -> str:
    """
    Generate the XML content for 3D/Objects/object_1.model.
    
    This is the "mesh library" file that contains all the actual geometry
    (vertices and triangles). The main model file references these objects.
    
    WHY: The 3MF spec separates geometry (this file) from assembly
    (main model file). This allows reusing the same geometry with
    different transforms.
    
    Args:
        objects: List of ThreeMFObject instances with meshes
    
    Returns:
        XML string for the object model file
    """
    root = ET.Element(
        "model",
        attrib={
            "unit": "millimeter",
            "xml:lang": "en-US",
            "xmlns": NS_3MF,
            f"xmlns:p": NS_PRODUCTION,
            "requiredextensions": "p"
        }
    )
    
    # Add resources section (contains all mesh objects)
    resources = ET.SubElement(root, "resources")
    
    # Add each mesh object
    for obj in objects:
        obj_uuid = str(uuid.uuid4())
        obj_elem = ET.SubElement(
            resources,
            "object",
            attrib={
                "id": str(obj.object_id),
                f"p:UUID": obj_uuid,
                "type": "model"
            }
        )
        
        # Create mesh element
        mesh_elem = ET.SubElement(obj_elem, "mesh")
        
        # Add vertices
        vertices_elem = ET.SubElement(mesh_elem, "vertices")
        for x, y, z in obj.mesh.vertices:
            ET.SubElement(
                vertices_elem,
                "vertex",
                attrib={
                    "x": format_float(x),
                    "y": format_float(y),
                    "z": format_float(z)
                }
            )
        
        # Add triangles
        triangles_elem = ET.SubElement(mesh_elem, "triangles")
        for v1, v2, v3 in obj.mesh.triangles:
            ET.SubElement(
                triangles_elem,
                "triangle",
                attrib={
                    "v1": str(v1),
                    "v2": str(v2),
                    "v3": str(v3)
                }
            )
    
    # Add empty build tag (required by spec even though this file isn't directly built)
    ET.SubElement(root, "build")
    
    return prettify_xml(root)


def _generate_main_model_xml(
    objects: List[ThreeMFObject],
    container_id: int,
    container_name: str,
    build_plate_center: Tuple[float, float],
    model_title: str | None
) -> str:
    """
    Generate the XML content for 3D/3dmodel.model.
    
    This is the "assembly" file that references all the objects from
    object_1.model and positions them in 3D space. It creates a container
    object that groups all parts together.
    
    WHY: The assembly file allows positioning multiple mesh objects
    independently while treating them as a single model in the slicer.
    
    Args:
        objects: List of ThreeMFObject instances with transforms
        container_id: ID for the container object (typically num_objects + 1)
        container_name: Name for the container object
        build_plate_center: (x, y) coordinates for centering on build plate
        model_title: Optional title metadata for the model
    
    Returns:
        XML string for the main model file
    """
    root = ET.Element(
        "model",
        attrib={
            "unit": "millimeter",
            "xml:lang": "en-US",
            "xmlns": NS_3MF,
            f"xmlns:BambuStudio": NS_BAMBU,
            f"xmlns:p": NS_PRODUCTION,
            "requiredextensions": "p"
        }
    )
    
    # Add metadata
    ET.SubElement(root, "metadata", name="Application").text = "PixelTo3MF"
    ET.SubElement(root, "metadata", name="BambuStudio:3mfVersion").text = "1"
    ET.SubElement(root, "metadata", name="Thumbnail_Middle").text = "/Metadata/plate_1.png"
    ET.SubElement(root, "metadata", name="Thumbnail_Small").text = "/Metadata/plate_1_small.png"
    
    # Use provided title or default
    title = model_title if model_title else container_name
    ET.SubElement(root, "metadata", name="Title").text = title
    
    # Create resources with container object
    resources = ET.SubElement(root, "resources")
    
    container_uuid = str(uuid.uuid4())
    container_obj = ET.SubElement(
        resources,
        "object",
        attrib={
            "id": str(container_id),
            f"p:UUID": container_uuid,
            "type": "model"
        }
    )
    
    components = ET.SubElement(container_obj, "components")
    
    # Reference each mesh object with its transform
    for obj in objects:
        comp_uuid = str(uuid.uuid4())
        
        tx, ty, tz = obj.transform
        transform = f"1 0 0 0 1 0 0 0 1 {format_float(tx)} {format_float(ty)} {format_float(tz)}"
        
        ET.SubElement(
            components,
            "component",
            attrib={
                f"p:path": "/3D/Objects/object_1.model",
                "objectid": str(obj.object_id),
                f"p:UUID": comp_uuid,
                "transform": transform
            }
        )
    
    # Create build section
    build_uuid = str(uuid.uuid4())
    build = ET.SubElement(root, "build", attrib={f"p:UUID": build_uuid})
    
    # Build transform to center on build plate
    build_transform = f"1 0 0 0 1 0 0 0 1 {build_plate_center[0]} {build_plate_center[1]} 1"
    
    item_uuid = str(uuid.uuid4())
    ET.SubElement(
        build,
        "item",
        attrib={
            "objectid": str(container_id),
            f"p:UUID": item_uuid,
            "transform": build_transform,
            "printable": "1"
        }
    )
    
    return prettify_xml(root)


def _generate_model_settings_xml(objects: List[ThreeMFObject], container_id: int, container_name: str) -> str:
    """
    Generate the XML content for Metadata/model_settings.config.
    
    This is where object names and material slot assignments are stored.
    Each object gets mapped to its display name and extruder slot, which
    appears in the slicer UI.
    
    WHY: Slicers use this file to populate the object list and material
    assignments. Without it, all objects would be unnamed and use slot 1.
    
    Args:
        objects: List of ThreeMFObject instances with names and slots
        container_id: ID of the container object
        container_name: Name for the container object
    
    Returns:
        XML string for the model settings file
    """
    root = ET.Element("config")
    
    # Create parent object entry (the container)
    parent_obj = ET.SubElement(root, "object", id=str(container_id))
    ET.SubElement(parent_obj, "metadata", key="name", value=container_name)
    
    # Add each object as a "part" of the parent
    for obj in objects:
        part = ET.SubElement(parent_obj, "part", id=str(obj.object_id), subtype="normal_part")
        ET.SubElement(part, "metadata", key="name", value=obj.name)
        
        # Add extruder metadata only if slot != 1 (slot 1 is default)
        if obj.extruder_slot != 1:
            ET.SubElement(part, "metadata", key="extruder", value=str(obj.extruder_slot))
    
    # Add assemble section
    assemble = ET.SubElement(root, "assemble")
    ET.SubElement(
        assemble,
        "assemble_item",
        attrib={
            "object_id": str(container_id),
            "instance_id": "0",
            "transform": "1 0 0 0 1 0 0 0 1 0 0 0",
            "offset": "0 0 0"
        }
    )
    
    return prettify_xml(root)


def _generate_content_types_xml() -> str:
    """
    Generate [Content_Types].xml - required by 3MF spec.
    
    This file tells parsers what kind of files are in the archive.
    It's boilerplate but necessary for spec compliance!
    
    Returns:
        XML string for content types
    """
    root = ET.Element(
        "Types",
        xmlns="http://schemas.openxmlformats.org/package/2006/content-types"
    )
    
    ET.SubElement(
        root,
        "Default",
        attrib={
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml"
        }
    )
    
    ET.SubElement(
        root,
        "Default",
        attrib={
            "Extension": "model",
            "ContentType": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"
        }
    )
    
    ET.SubElement(
        root,
        "Default",
        attrib={
            "Extension": "png",
            "ContentType": "image/png"
        }
    )
    
    ET.SubElement(
        root,
        "Default",
        attrib={
            "Extension": "gcode",
            "ContentType": "text/x.gcode"
        }
    )
    
    return prettify_xml(root)


def _generate_rels_xml() -> str:
    """
    Generate _rels/.rels - required relationships file.
    
    This tells the parser where to find the main 3D model file.
    
    Returns:
        XML string for relationships
    """
    root = ET.Element(
        "Relationships",
        xmlns="http://schemas.openxmlformats.org/package/2006/relationships"
    )
    
    ET.SubElement(
        root,
        "Relationship",
        attrib={
            "Target": "/3D/3dmodel.model",
            "Id": "rel-1",
            "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
        }
    )
    
    return prettify_xml(root)


def _generate_3dmodel_rels_xml() -> str:
    """
    Generate 3D/_rels/3dmodel.model.rels - relationships for the main model.
    
    This links the main model to the object library. Without this file,
    the slicer can't find the mesh geometry in object_1.model!
    
    Returns:
        XML string for 3dmodel relationships
    """
    root = ET.Element(
        "Relationships",
        xmlns="http://schemas.openxmlformats.org/package/2006/relationships"
    )
    
    ET.SubElement(
        root,
        "Relationship",
        attrib={
            "Target": "/3D/Objects/object_1.model",
            "Id": "rel-1",
            "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
        }
    )
    
    return prettify_xml(root)


# ============================================================================
# ThreeMFWriter Class
# ============================================================================

class ThreeMFWriter:
    """
    Generic 3MF file writer with pluggable application logic.
    
    This class handles all standard 3MF file generation:
    - XML file generation (all required 3MF spec files)
    - ZIP archive structure
    - Mesh formatting and validation
    - Namespace and relationship management
    
    Application-specific logic (naming, slots, transforms, thumbnails)
    is injected via callback functions for maximum flexibility.
    
    Example:
        writer = ThreeMFWriter(
            naming_callback=lambda id, mesh: f"Part {id}",
            slot_callback=lambda id, mesh: 1,
            transform_callback=lambda id, mesh, ctx: (0, 0, 0)
        )
        
        meshes = [ThreeMFMesh(...), ThreeMFMesh(...)]
        result = writer.write("output.3mf", meshes)
    """
    
    def __init__(
        self,
        naming_callback: ObjectNamingCallback,
        slot_callback: SlotAssignmentCallback,
        transform_callback: TransformCalculationCallback,
        thumbnail_callback: Optional[ThumbnailGenerationCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        container_name: str = "Assembly",
        build_plate_center: Tuple[float, float] = (128.0, 128.0),
        model_title: str | None = None
    ):
        """
        Initialize the 3MF writer with application-specific callbacks.
        
        Args:
            naming_callback: Function that returns object name given (id, mesh)
            slot_callback: Function that returns extruder slot given (id, mesh)
            transform_callback: Function that returns (x,y,z) transform given (id, mesh, context)
            thumbnail_callback: Optional function that generates thumbnail images
            progress_callback: Optional progress reporting function
            container_name: Name for the container object (default: "Assembly")
            build_plate_center: (x, y) build plate center (default: 128, 128)
            model_title: Optional title metadata (uses container_name if None)
        """
        self.naming_callback = naming_callback
        self.slot_callback = slot_callback
        self.transform_callback = transform_callback
        self.thumbnail_callback = thumbnail_callback
        self.progress_callback = progress_callback
        self.container_name = container_name
        self.build_plate_center = build_plate_center
        self.model_title = model_title
    
    def _progress(self, message: str) -> None:
        """Send progress update if callback is configured."""
        if self.progress_callback:
            self.progress_callback("export", message)
    
    def write(
        self,
        output_path: str,
        meshes: List[ThreeMFMesh],
        context: Any = None
    ) -> Dict[str, Any]:
        """
        Write meshes to a 3MF file.
        
        This is the main entry point for 3MF generation. It converts meshes
        to objects using the configured callbacks, generates all required
        XML files, and packages everything into a ZIP archive.
        
        Args:
            output_path: Where to save the .3mf file
            meshes: List of meshes to export
            context: Optional context object passed to callbacks
        
        Returns:
            Dictionary with export statistics:
            - 'num_objects': Number of mesh objects exported
            - 'num_vertices': Total vertex count
            - 'num_triangles': Total triangle count
            - 'container_id': ID of the container object
            - 'objects': List of ThreeMFObject instances created
        
        Raises:
            ValueError: If meshes list is empty
        """
        if not meshes:
            raise ValueError("Cannot write 3MF file: meshes list is empty")
        
        self._progress(f"Preparing {len(meshes)} objects for export...")
        
        # Create ThreeMFObject instances using callbacks
        objects = []
        for obj_id, mesh in enumerate(meshes, start=1):
            name = self.naming_callback(obj_id, mesh)
            slot = self.slot_callback(obj_id, mesh)
            transform = self.transform_callback(obj_id, mesh, context)
            
            obj = ThreeMFObject(
                object_id=obj_id,
                name=name,
                extruder_slot=slot,
                transform=transform,
                mesh=mesh
            )
            objects.append(obj)
        
        # Container ID is one more than the last mesh object
        container_id = len(meshes) + 1
        
        self._progress("Generating 3MF XML structure...")
        
        # Generate all XML files
        object_model_xml = _generate_object_model_xml(objects)
        main_model_xml = _generate_main_model_xml(
            objects,
            container_id,
            self.container_name,
            self.build_plate_center,
            self.model_title
        )
        settings_xml = _generate_model_settings_xml(objects, container_id, self.container_name)
        content_types_xml = _generate_content_types_xml()
        rels_xml = _generate_rels_xml()
        model_rels_xml = _generate_3dmodel_rels_xml()
        
        self._progress(f"Writing {len(objects)} objects to 3MF archive...")
        
        # Create the 3MF file (ZIP archive)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Write all required XML files
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("3D/3dmodel.model", main_model_xml)
            zf.writestr("3D/_rels/3dmodel.model.rels", model_rels_xml)
            zf.writestr("3D/Objects/object_1.model", object_model_xml)
            zf.writestr("Metadata/model_settings.config", settings_xml)
            
            # Generate and add thumbnails if callback provided
            if self.thumbnail_callback:
                self._progress("Generating thumbnails...")
                thumbnails = self.thumbnail_callback(output_path, context)
                for zip_path, image_data in thumbnails:
                    zf.writestr(zip_path, image_data)
                self._progress(f"✅ Added {len(thumbnails)} thumbnails")
        
        # Calculate statistics
        num_vertices, num_triangles = count_mesh_stats(meshes)
        
        self._progress(f"✨ 3MF file written to: {output_path}")
        self._progress(f"Total objects: {len(objects)}")
        self._progress(f"Vertices: {num_vertices}, Triangles: {num_triangles}")
        
        return {
            'num_objects': len(objects),
            'num_vertices': num_vertices,
            'num_triangles': num_triangles,
            'container_id': container_id,
            'objects': objects
        }
