"""
Core Mesh data structure for 3D geometry.

A mesh is the universal 3D representation: a list of 3D points (vertices)
and a list of triangles (each triangle = 3 indices into the vertex list).
This is used by STL, OBJ, 3MF and essentially every 3D format because it's
simple, compact, and GPU-friendly.

Triangle winding convention: counter-clockwise = outward-facing normal.
Slicers use the normal direction to determine which side is "outside" the
model, so all triangles must follow this convention consistently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(repr=False)
class Mesh:
    """
    A 3D mesh defined by vertices and triangles.

    Vertices are 3D points in millimetres. Triangles reference vertices by
    0-based index. Counter-clockwise winding (when viewed from outside) gives
    an outward-facing normal, which slicers require to know what is "inside"
    vs "outside" the model.

    Example:
        vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]  # 3 corners
        triangles = [(0, 1, 2)]                         # 1 triangle
    """

    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]

    def __repr__(self) -> str:
        return f"Mesh(vertices={len(self.vertices)}, triangles={len(self.triangles)})"
