"""
3MF file writer module.

This is where we package everything up into the 3MF format! A 3MF file is
actually just a ZIP archive containing XML files and metadata. We generate:

1. 3D/Objects/object_1.model - The mesh library (all our geometry)
2. 3D/3dmodel.model - The main assembly file (references the meshes)
3. Metadata/model_settings.config - Object names (the color names!)
4. [Content_Types].xml - Required metadata about file types
5. _rels/.rels - Required relationships file

It's like making a little self-contained package that slicers can open! 📦
"""

import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Tuple, TYPE_CHECKING, Optional, Callable
from pathlib import Path
import uuid

from .mesh_generator import Mesh
from .constants import COORDINATE_PRECISION
from .color_tools import Palette, FilamentPalette, rgb_to_lab, rgb_to_hex

# Import for type checking only (avoids circular imports)
if TYPE_CHECKING:
    from .image_processor import PixelData
    from .config import ConversionConfig


# XML namespaces used in 3MF files
NS_3MF = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_PRODUCTION = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS_BAMBU = "http://schemas.bambulab.com/package/2021"


def prettify_xml(elem: ET.Element) -> str:
    """
    Convert an XML element tree to a pretty-printed string.
    
    ElementTree's tostring() creates ugly one-line XML. This function
    makes it readable with proper indentation. Much nicer for debugging!
    
    Args:
        elem: Root element of the XML tree
    
    Returns:
        Pretty-printed XML string
    """
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def format_float(value: float, precision: int = COORDINATE_PRECISION) -> str:
    """
    Format a float for XML with specified precision.
    
    This strips trailing zeros and ensures consistent formatting.
    Example: 1.50000 -> "1.5", 2.0 -> "2"
    
    Args:
        value: Float value to format
        precision: Number of decimal places
    
    Returns:
        Formatted string
    """
    return f"{value:.{precision}f}".rstrip('0').rstrip('.')


def generate_object_model_xml(meshes: List[Tuple[Mesh, str]]) -> str:
    """
    Generate the XML content for 3D/Objects/object_1.model.
    
    This file is like a warehouse - it contains ALL our mesh objects
    (colored regions + backing plate), each with a unique ID.
    
    Args:
        meshes: List of (Mesh, color_name) tuples
    
    Returns:
        XML string for the object model file
    """
    # Create root element with all necessary namespaces
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
    ET.SubElement(root, "metadata", name="BambuStudio:3mfVersion").text = "1"
    
    # Create resources container
    resources = ET.SubElement(root, "resources")
    
    # Add each mesh as an object
    for mesh_id, (mesh, color_name) in enumerate(meshes, start=1):
        # Generate a UUID for this object (required by some slicers)
        obj_uuid = str(uuid.uuid4())
        
        # Create object element
        obj = ET.SubElement(
            resources,
            "object",
            attrib={
                "id": str(mesh_id),
                f"p:UUID": obj_uuid,
                "type": "model"
            }
        )
        
        # Create mesh element
        mesh_elem = ET.SubElement(obj, "mesh")
        
        # Add vertices
        vertices_elem = ET.SubElement(mesh_elem, "vertices")
        for x, y, z in mesh.vertices:
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
        for v1, v2, v3 in mesh.triangles:
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


def generate_main_model_xml(
    num_objects: int, 
    mesh_transforms: List[Tuple[float, float, float]],
    build_plate_center: Tuple[float, float] = (128.0, 128.0)
) -> str:
    """
    Generate the XML content for 3D/3dmodel.model.
    
    This is the "assembly" file that references all the objects from
    object_1.model. It creates a "build" that instances each object.
    
    The container object ID should be num_objects (the count of all parts),
    NOT 0! This is critical for slicers to recognize the structure properly.
    
    Args:
        num_objects: Total number of mesh objects (1-indexed, so if you have
                    44 meshes, they're numbered 1 through 44)
        mesh_transforms: List of (x, y, z) translations for each mesh (relative to model center)
        build_plate_center: (x, y) coordinates for centering on build plate (default: 128, 128)
    
    Returns:
        XML string for the main model file
    """
    # The container object ID should be one more than the last mesh object
    # For example: if we have 44 mesh objects (IDs 1-44), the container is ID 45
    container_id = num_objects + 1
    
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
    
    # Create resources with a main assembly object
    resources = ET.SubElement(root, "resources")
    
    # Create a container object that references all the individual objects
    # This uses the container_id we calculated above
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
    
    # Reference each mesh object in the object_1.model file (IDs 1 through num_objects)
    # Each component gets its calculated transform (relative to model center)
    for obj_id in range(1, num_objects + 1):
        comp_uuid = str(uuid.uuid4())
        
        # Get the transform for this mesh (0-indexed in the list)
        tx, ty, tz = mesh_transforms[obj_id - 1]
        
        # Format: scale_x 0 0 0 scale_y 0 0 0 scale_z translate_x translate_y translate_z
        transform = f"1 0 0 0 1 0 0 0 1 {format_float(tx)} {format_float(ty)} {format_float(tz)}"
        
        ET.SubElement(
            components,
            "component",
            attrib={
                f"p:path": "/3D/Objects/object_1.model",
                "objectid": str(obj_id),
                f"p:UUID": comp_uuid,
                "transform": transform
            }
        )
    
    # Create build section (what actually gets printed)
    build_uuid = str(uuid.uuid4())
    build = ET.SubElement(root, "build", attrib={f"p:UUID": build_uuid})
    
    # Build transform to center on build plate
    # Format: scale_x 0 0 0 scale_y 0 0 0 scale_z translate_x translate_y translate_z
    # We use z=1 to lift it slightly off the bed (matching the working example)
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


def generate_model_settings_xml(object_names: List[Tuple[int, str]]) -> str:
    """
    Generate the XML content for Metadata/model_settings.config.
    
    This is where the magic happens for object naming! Each object ID
    gets mapped to its color name, which appears in the slicer UI.
    
    Args:
        object_names: List of (object_id, color_name) tuples
    
    Returns:
        XML string for the model settings file
    """
    root = ET.Element("config")
    
    # Get the container object ID (should be the highest object ID)
    container_id = max(obj_id for obj_id, _ in object_names)
    
    # Create a parent object entry - the container
    parent_obj = ET.SubElement(root, "object", id=str(container_id))
    ET.SubElement(parent_obj, "metadata", key="name", value="PixelArt3D")
    
    # Add each named object as a "part" of the parent (excluding the container itself)
    for obj_id, color_name in object_names:
        if obj_id != container_id:  # Don't add the container as a part of itself
            part = ET.SubElement(parent_obj, "part", id=str(obj_id), subtype="normal_part")
            ET.SubElement(part, "metadata", key="name", value=color_name)
    
    # Add the assemble section at the root level
    # This tells the slicer how to assemble/place the object
    assemble = ET.SubElement(root, "assemble")
    ET.SubElement(
        assemble,
        "assemble_item",
        attrib={
            "object_id": str(container_id),
            "instance_id": "0",
            # Identity transform: no scaling (1, 1, 1), no rotation, no translation
            "transform": "1 0 0 0 1 0 0 0 1 0 0 0",
            "offset": "0 0 0"
        }
    )
    
    # Don't add extra XML declaration - prettify_xml will add it
    return prettify_xml(root)


def generate_content_types_xml() -> str:
    """
    Generate [Content_Types].xml - required by 3MF spec.
    
    This file tells parsers what kind of files are in the archive.
    It's boilerplate but necessary!
    
    Returns:
        XML string for content types
    """
    root = ET.Element(
        "Types",
        xmlns="http://schemas.openxmlformats.org/package/2006/content-types"
    )
    
    # Define content types for our files
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
    
    # Don't add extra XML declaration - prettify_xml will add it
    return prettify_xml(root)


def generate_rels_xml() -> str:
    """
    Generate _rels/.rels - required relationships file.
    
    This tells the parser where to find the main 3D model file.
    More boilerplate, but hey, that's XML for you! 🤷
    
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
    
    # Don't add extra XML declaration - prettify_xml will add it
    return prettify_xml(root)


def generate_3dmodel_rels_xml() -> str:
    """
    Generate 3D/_rels/3dmodel.model.rels - relationships for the main model.
    
    This is almost identical to the root .rels file, but it links the main model
    to the object library. Both files use the same structure, just different targets.
    
    CRITICAL: Without this file, the slicer can't find the mesh geometry in object_1.model!
    
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
    
    # Don't add extra XML declaration - prettify_xml will add it
    return prettify_xml(root)


def get_color_name(rgb: Tuple[int, int, int], config: 'ConversionConfig') -> str:
    """
    Get the name for an RGB color based on the configured naming mode.
    
    Supports three modes:
    - "color": Find nearest CSS color name using Delta E 2000
    - "filament": Find nearest filament based on maker/type/finish filters
    - "hex": Use hex color code as the name
    
    Args:
        rgb: RGB tuple (0-255 for each channel)
        config: ConversionConfig with color_naming_mode and filament filters
    
    Returns:
        Color name string (e.g., "red", "Bambu PLA Basic Red", "#FF5733")
    """
    if config.color_naming_mode == "hex":
        # Hex mode: just return the hex code
        return rgb_to_hex(rgb)
    
    elif config.color_naming_mode == "filament":
        # Filament mode: search for nearest filament based on filters
        palette = FilamentPalette.load_default()
        
        try:
            nearest_filament, distance = palette.nearest_filament(
                target_rgb=rgb,
                metric="de2000",
                maker=config.filament_maker,
                type_name=config.filament_type,
                finish=config.filament_finish
            )
            # Return the full filament description: Maker + Type + Finish + Color
            # Example: "Bambu Lab PLA Basic Black"
            return f"{nearest_filament.maker} {nearest_filament.type} {nearest_filament.finish} {nearest_filament.color}"
        except ValueError as e:
            # If no filaments match the filters, fall back to hex
            return rgb_to_hex(rgb)
    
    else:  # "color" mode (default)
        # CSS color mode: find nearest named color
        palette = Palette.load_default()
        
        # Convert RGB to LAB color space for accurate comparison
        lab = rgb_to_lab(rgb)
        
        # Find nearest color using Delta E 2000
        nearest_color, distance = palette.nearest_color(lab, space="lab", metric="de2000")
        
        return nearest_color.name


def write_3mf(
    output_path: str,
    meshes: List[Tuple[Mesh, str]],
    region_colors: List[Tuple[int, int, int]],
    pixel_data: 'PixelData',  # We need this to calculate positions
    config: 'ConversionConfig',
    progress_callback: Optional[Callable[[str, str], None]] = None
) -> Optional[str]:
    """
    Write all meshes to a 3MF file.

    This is the main export function! It takes all our generated meshes,
    figures out color names, and packages everything into a proper 3MF file.

    The 3MF structure:
    - [Content_Types].xml (required metadata)
    - _rels/.rels (required relationships)
    - 3D/3dmodel.model (main assembly)
    - 3D/Objects/object_1.model (all the mesh geometry)
    - Metadata/model_settings.config (object names/colors)

    Args:
        output_path: Path where to write the .3mf file
        meshes: List of (Mesh, name) tuples (regions + optional backing plate)
        region_colors: List of RGB colors for each region (for naming)
        pixel_data: PixelData object with model dimensions
        config: ConversionConfig object with conversion parameters
        progress_callback: Optional function to call with progress updates
    
    Returns:
        Path to summary file if generated, None otherwise
    """
    # Helper to send progress updates
    def _progress(message: str):
        if progress_callback:
            progress_callback("export", message)

    # Determine if we have a backing plate (check if config.base_height_mm > 0)
    has_backing_plate = config.base_height_mm > 0
    
    # Generate color names for regions
    # If we have a backing plate, the last mesh is the backing plate, so we skip it
    # Otherwise, all meshes are regions
    num_regions = len(region_colors)

    _progress(f"Assigning names to {num_regions} color regions...")

    # Calculate the center of our model for positioning
    # The model spans from (0, 0) to (model_width, model_height)
    model_center_x = pixel_data.model_width_mm / 2.0
    model_center_y = pixel_data.model_height_mm / 2.0

    # Create a list of (mesh_index, rgb, color_name) for sorting
    # mesh_index is 0-based index into the meshes list
    region_data = []
    for i, rgb in enumerate(region_colors):
        color_name = get_color_name(rgb, config)
        region_data.append((i, rgb, color_name))
    
    # Sort alphabetically by color name for easier slicer workflow
    region_data.sort(key=lambda x: x[2])  # Sort by color_name
    
    # Now create the object_names and mesh_transforms in sorted order
    # Objects are numbered 1, 2, 3, ... N (the meshes)
    # Then we need the container object at N+1
    object_names: List[Tuple[int, str]] = []
    
    # Also track mesh positions (transforms relative to model center)
    mesh_transforms: List[Tuple[float, float, float]] = []
    
    for obj_id, (mesh_idx, rgb, color_name) in enumerate(region_data, start=1):
        object_names.append((obj_id, color_name))
        # Colored regions are at z=0 (on top of backing plate)
        # Fix: Use POSITIVE offsets - we were backwards!
        mesh_transforms.append((model_center_x, model_center_y, 0.0))
    
    # Add the backing plate if it exists (last mesh object)
    if has_backing_plate:
        backing_plate_id = len(meshes)
        object_names.append((backing_plate_id, "Backing"))
        # Backing plate mesh is already at correct z coords (-base_height to 0)
        # Transform should be z=0, not z=-base_height (that would double the offset!)
        mesh_transforms.append((model_center_x, model_center_y, 0.0))
    
    # Add the container object (one more than the last mesh)
    container_id = len(meshes) + 1
    object_names.append((container_id, "PixelArt3D"))
    
    # Reorder meshes to match the sorted color order
    sorted_meshes = [meshes[mesh_idx] for mesh_idx, _, _ in region_data]
    if has_backing_plate:
        sorted_meshes.append(meshes[-1])  # Add backing plate at the end

    _progress("Generating 3MF XML structure...")

    # Generate XML content for all files
    object_model_xml = generate_object_model_xml(sorted_meshes)
    main_model_xml = generate_main_model_xml(len(sorted_meshes), mesh_transforms)
    settings_xml = generate_model_settings_xml(object_names)
    content_types_xml = generate_content_types_xml()
    rels_xml = generate_rels_xml()
    model_rels_xml = generate_3dmodel_rels_xml()

    _progress(f"Writing {len(sorted_meshes)} objects to 3MF archive...")

    # Create the 3MF file (which is just a ZIP with specific structure)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write all the XML files
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("3D/3dmodel.model", main_model_xml)
        zf.writestr("3D/_rels/3dmodel.model.rels", model_rels_xml)  # Fixed filename!
        zf.writestr("3D/Objects/object_1.model", object_model_xml)
        zf.writestr("Metadata/model_settings.config", settings_xml)
    
    # Report completion through progress callback
    _progress(f"✨ 3MF file written to: {output_path}")
    if has_backing_plate:
        _progress(f"{len(region_colors)} colored regions + 1 backing plate")
    else:
        _progress(f"{len(region_colors)} colored regions (no backing plate)")
    _progress(f"Total objects: {len(meshes)}")
    
    # Generate summary file if requested
    summary_path = None
    if config.generate_summary:
        from .summary_writer import write_summary_file
        
        _progress("Generating summary file...")
        
        # Extract RGB colors and names from region_data (already sorted)
        summary_colors = [rgb for _, rgb, _ in region_data]
        summary_names = [color_name for _, _, color_name in region_data]
        
        summary_path = write_summary_file(output_path, summary_colors, summary_names, config)
        _progress(f"📄 Summary written to: {summary_path}")
    
    return summary_path