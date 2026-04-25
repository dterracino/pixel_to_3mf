from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Callable

import numpy as np


@dataclass(repr=False)
class Mesh:
    """
    A 3D mesh defined by vertices and triangles.

    Vertices are 3D points in millimetres. Triangles reference vertices by
    0-based index. Counter-clockwise winding (when viewed from outside) gives
    an outward-facing normal, which slicers require to know what is "inside"
    vs "outside" the model.
    """

    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]

    # Tolerances (mm / mm²)
    vertex_merge_epsilon: float = 1e-6
    degenerate_area_epsilon: float = 1e-10
    edge_merge_epsilon: float = 1e-6  # reserved for future geometric edge logic

    # -------------------------------------------------------------------------
    # basic representation
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Mesh(vertices={len(self.vertices)}, triangles={len(self.triangles)})"

    # -------------------------------------------------------------------------
    # internal helpers
    # -------------------------------------------------------------------------

    @property
    def _V(self) -> np.ndarray:
        """Vertices as (N, 3) float64 array."""
        return np.asarray(self.vertices, dtype=np.float64)

    @property
    def _F(self) -> np.ndarray:
        """Triangles as (M, 3) int64 array."""
        return np.asarray(self.triangles, dtype=np.int64)

    def _set_from_arrays(self, V: np.ndarray, F: np.ndarray) -> None:
        self.vertices = [tuple(map(float, v)) for v in V.tolist()]
        self.triangles = [tuple(map(int, f)) for f in F.tolist()]

    def _compute_face_normals(
        self,
        F: np.ndarray | None = None,
        V: np.ndarray | None = None,
    ) -> np.ndarray:
        if V is None:
            V = self._V
        if F is None:
            F = self._F
        v0 = V[F[:, 0]]
        v1 = V[F[:, 1]]
        v2 = V[F[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(n, axis=1)
        norms[norms == 0.0] = 1.0
        return n / norms[:, None]

    def _compute_edge_map(self, F: np.ndarray | None = None) -> Dict[Tuple[int, int], List[int]]:
        if F is None:
            F = self._F
        edge_map: Dict[Tuple[int, int], List[int]] = {}
        for fi, (a, b, c) in enumerate(F):
            edges = [(a, b), (b, c), (c, a)]
            for u, v in edges:
                e = (u, v) if u < v else (v, u)
                edge_map.setdefault(e, []).append(fi)
        return edge_map

    def _compute_face_adjacency(self, F: np.ndarray | None = None) -> Dict[int, List[int]]:
        if F is None:
            F = self._F
        edge_map = self._compute_edge_map(F)
        adj: Dict[int, List[int]] = {i: [] for i in range(len(F))}
        for faces in edge_map.values():
            if len(faces) >= 2:
                for i in range(len(faces)):
                    for j in range(i + 1, len(faces)):
                        a, b = faces[i], faces[j]
                        adj[a].append(b)
                        adj[b].append(a)
        return adj

    def _connected_face_components(self, F: np.ndarray | None = None) -> List[List[int]]:
        if F is None:
            F = self._F
        adj = self._compute_face_adjacency(F)
        visited = set()
        components: List[List[int]] = []
        for f in range(len(F)):
            if f in visited:
                continue
            stack = [f]
            comp: List[int] = []
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                comp.append(cur)
                for nb in adj[cur]:
                    if nb not in visited:
                        stack.append(nb)
            components.append(comp)
        return components

    # -------------------------------------------------------------------------
    # check helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _make_result(ok: bool, errors: List[str], details: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": ok, "errors": errors, "details": details}

    # -------------------------------------------------------------------------
    # checks
    # -------------------------------------------------------------------------

    def check_non_manifold_edges(self) -> Dict[str, Any]:
        """
        Edges with more than 2 incident faces are topologically non-manifold.
        """
        F = self._F
        edge_map = self._compute_edge_map(F)
        non_manifold_edges = {e: faces for e, faces in edge_map.items() if len(faces) > 2}
        errors: List[str] = []
        if non_manifold_edges:
            errors.append(f"{len(non_manifold_edges)} non-manifold edges (edges with >2 incident faces)")
        return self._make_result(
            ok=not non_manifold_edges,
            errors=errors,
            details={"non_manifold_edges": non_manifold_edges},
        )

    def check_boundary_edges(self) -> Dict[str, Any]:
        """
        Edges with exactly 1 incident face are boundary edges; a watertight
        mesh has zero boundary edges.
        """
        F = self._F
        edge_map = self._compute_edge_map(F)
        boundary_edges = [e for e, faces in edge_map.items() if len(faces) == 1]
        errors: List[str] = []
        if boundary_edges:
            errors.append(f"{len(boundary_edges)} boundary edges (mesh is not watertight)")
        return self._make_result(
            ok=not boundary_edges,
            errors=errors,
            details={"boundary_edges": boundary_edges},
        )

    def check_degenerate_faces(self) -> Dict[str, Any]:
        """
        Faces with area below degenerate_area_epsilon are considered degenerate.
        Duplicate faces (same 3 vertices) are also reported.
        """
        V = self._V
        F = self._F
        v0 = V[F[:, 0]]
        v1 = V[F[:, 1]]
        v2 = V[F[:, 2]]
        areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
        zero_area_faces = np.where(areas < self.degenerate_area_epsilon)[0].tolist()

        sorted_F = np.sort(F, axis=1)
        _, idx, counts = np.unique(sorted_F, axis=0, return_index=True, return_counts=True)
        duplicate_faces: List[int] = []
        for i, c in zip(idx, counts):
            if c > 1:
                dup_indices = np.where((sorted_F == sorted_F[i]).all(axis=1))[0].tolist()
                duplicate_faces.extend(dup_indices[1:])
        duplicate_faces = sorted(set(duplicate_faces))

        errors: List[str] = []
        if zero_area_faces:
            errors.append(f"{len(zero_area_faces)} zero-area / degenerate faces")
        if duplicate_faces:
            errors.append(f"{len(duplicate_faces)} duplicate faces")

        return self._make_result(
            ok=not (zero_area_faces or duplicate_faces),
            errors=errors,
            details={
                "zero_area_faces": zero_area_faces,
                "duplicate_faces": duplicate_faces,
                "area_epsilon": self.degenerate_area_epsilon,
            },
        )

    def check_ccw_winding_consistency(self) -> Dict[str, Any]:
        """
        Check that across shared edges, faces are oriented consistently.
        This detects locally flipped triangles. It does NOT decide outward vs
        inward; that is handled by check_normals_outward().
        """
        F = self._F
        edge_to_faces: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for fi, (a, b, c) in enumerate(F):
            edges = [(a, b), (b, c), (c, a)]
            for (u, v) in edges:
                key = (u, v) if u < v else (v, u)
                sign = 1 if key == (u, v) else -1
                edge_to_faces.setdefault(key, []).append((fi, sign))

        inconsistent_pairs: List[Tuple[int, int]] = []
        for faces in edge_to_faces.values():
            if len(faces) == 2:
                (f0, s0), (f1, s1) = faces
                if s0 == s1:
                    inconsistent_pairs.append((f0, f1))

        errors: List[str] = []
        if inconsistent_pairs:
            errors.append(f"{len(inconsistent_pairs)} pairs of faces with inconsistent winding across shared edges")

        return self._make_result(
            ok=not inconsistent_pairs,
            errors=errors,
            details={"inconsistent_face_pairs": inconsistent_pairs},
        )

    def check_normals_outward(self) -> Dict[str, Any]:
        """
        For each connected shell, check whether normals mostly point outward.
        Outward is approximated by comparing face normals to the vector from
        shell centroid to face centroid.
        """
        V = self._V
        F = self._F
        normals = self._compute_face_normals(F, V)
        components = self._connected_face_components(F)

        shell_results: List[Dict[str, Any]] = []
        shells_with_inward_normals: List[int] = []

        for si, comp in enumerate(components):
            comp = np.asarray(comp, dtype=int)
            F_comp = F[comp]
            n_comp = normals[comp]

            shell_vertices = np.unique(F_comp.flatten())
            shell_centroid = V[shell_vertices].mean(axis=0)

            v0 = V[F_comp[:, 0]]
            v1 = V[F_comp[:, 1]]
            v2 = V[F_comp[:, 2]]
            face_centroids = (v0 + v1 + v2) / 3.0

            dirs = face_centroids - shell_centroid
            dots = np.einsum("ij,ij->i", n_comp, dirs)
            num_outward = int(np.sum(dots > 0))
            num_inward = int(np.sum(dots < 0))

            shell_ok = num_outward >= num_inward
            if not shell_ok:
                shells_with_inward_normals.append(si)

            shell_results.append(
                {
                    "shell_index": si,
                    "num_faces": int(len(comp)),
                    "num_outward": num_outward,
                    "num_inward": num_inward,
                    "normals_outward": shell_ok,
                }
            )

        errors: List[str] = []
        if shells_with_inward_normals:
            errors.append(f"{len(shells_with_inward_normals)} shells appear to have inward-pointing normals")

        return self._make_result(
            ok=not shells_with_inward_normals,
            errors=errors,
            details={
                "shells": shell_results,
                "shells_with_inward_normals": shells_with_inward_normals,
            },
        )

    def check_duplicate_vertices(self) -> Dict[str, Any]:
        """
        Detect groups of vertices that are closer than vertex_merge_epsilon.
        """
        V = self._V
        eps = self.vertex_merge_epsilon
        q = np.round(V / eps).astype(np.int64)
        _, inv, counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)
        groups: Dict[int, List[int]] = {}
        for vid, gid in enumerate(inv):
            groups.setdefault(gid, []).append(vid)
        duplicate_sets = [g for g in groups.values() if len(g) > 1]

        errors: List[str] = []
        if duplicate_sets:
            errors.append(f"{len(duplicate_sets)} groups of duplicate / near-duplicate vertices")

        return self._make_result(
            ok=not duplicate_sets,
            errors=errors,
            details={"duplicate_vertex_groups": duplicate_sets, "epsilon": eps},
        )

    def check_disconnected_shells(self) -> Dict[str, Any]:
        components = self._connected_face_components()
        num_shells = len(components)
        errors: List[str] = []
        if num_shells > 1:
            errors.append(f"{num_shells} disconnected shells")
        return self._make_result(
            ok=True,  # allowed, but reported
            errors=errors,
            details={
                "num_shells": num_shells,
                "shell_sizes": [len(c) for c in components],
            },
        )

    def check_self_intersections(self) -> Dict[str, Any]:
        """
        Basic self-intersection check using AABB broad-phase and a conservative
        triangle-triangle plane test. This is O(n^2) and intended for moderate meshes.
        """
        V = self._V
        F = self._F

        v0 = V[F[:, 0]]
        v1 = V[F[:, 1]]
        v2 = V[F[:, 2]]
        mins = np.minimum(np.minimum(v0, v1), v2)
        maxs = np.maximum(np.maximum(v0, v1), v2)

        def aabb_overlap(i: int, j: int) -> bool:
            return np.all(maxs[i] >= mins[j]) and np.all(maxs[j] >= mins[i])

        def plane_normal(a, b, c):
            n = np.cross(b - a, c - a)
            n_norm = np.linalg.norm(n)
            if n_norm == 0:
                return n, 0.0
            n_unit = n / n_norm
            return n_unit, -np.dot(n_unit, a)

        def signed_dist(n, d, x):
            return np.dot(n, x) + d

        def tri_tri_intersect(p1, q1, r1, p2, q2, r2) -> bool:
            # plane of tri1
            n1, d1 = plane_normal(p1, q1, r1)
            if np.linalg.norm(n1) == 0:
                return False
            sd2 = np.array([signed_dist(n1, d1, p2), signed_dist(n1, d1, q2), signed_dist(n1, d1, r2)])
            if np.all(sd2 > 0) or np.all(sd2 < 0):
                return False

            # plane of tri2
            n2, d2 = plane_normal(p2, q2, r2)
            if np.linalg.norm(n2) == 0:
                return False
            sd1 = np.array([signed_dist(n2, d2, p1), signed_dist(n2, d2, q1), signed_dist(n2, d2, r1)])
            if np.all(sd1 > 0) or np.all(sd1 < 0):
                return False

            # conservative: if planes intersect and AABBs overlap, treat as intersecting
            return True

        intersecting_pairs: List[Tuple[int, int]] = []
        n = len(F)
        for i in range(n):
            for j in range(i + 1, n):
                if len(set(F[i]).intersection(F[j])) > 0:
                    continue
                if not aabb_overlap(i, j):
                    continue
                if tri_tri_intersect(v0[i], v1[i], v2[i], v0[j], v1[j], v2[j]):
                    intersecting_pairs.append((i, j))

        errors: List[str] = []
        if intersecting_pairs:
            errors.append(f"{len(intersecting_pairs)} pairs of self-intersecting faces")

        return self._make_result(
            ok=not intersecting_pairs,
            errors=errors,
            details={"intersecting_face_pairs": intersecting_pairs},
        )

    def check_duplicate_edges(self) -> Dict[str, Any]:
        """
        Report edges that are used in a topologically suspicious way.
        In this triangle-list representation, the main 'duplicate' edge
        pathology is edges with >2 incident faces (non-manifold edges).
        """
        F = self._F
        edge_map = self._compute_edge_map(F)
        duplicate_edges = {e: faces for e, faces in edge_map.items() if len(faces) > 2}
        errors: List[str] = []
        if duplicate_edges:
            errors.append(
                f"{len(duplicate_edges)} edges are shared by more than 2 faces "
                "(duplicate / non-manifold edge usage)"
            )
        return self._make_result(
            ok=not duplicate_edges,
            errors=errors,
            details={"duplicate_edges": duplicate_edges},
        )

    # -------------------------------------------------------------------------
    # repairs (mutating)
    # -------------------------------------------------------------------------

    def repair_duplicate_vertices(self) -> Dict[str, Any]:
        """
        Merge vertices that are closer than vertex_merge_epsilon, then remove
        any faces that collapse to zero area as a result.
        """
        V = self._V
        F = self._F
        eps = self.vertex_merge_epsilon

        q = np.round(V / eps).astype(np.int64)
        _, inv, counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)

        old_to_new = inv
        new_V = V[np.arange(len(np.unique(inv)))]

        new_F = old_to_new[F]

        v0 = new_V[new_F[:, 0]]
        v1 = new_V[new_F[:, 1]]
        v2 = new_V[new_F[:, 2]]
        areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
        keep = areas > self.degenerate_area_epsilon
        removed_faces = np.where(~keep)[0].tolist()
        new_F = new_F[keep]

        merged_groups = int(np.sum(counts > 1))
        self._set_from_arrays(new_V, new_F)

        return self._make_result(
            ok=True,
            errors=[],
            details={
                "epsilon": eps,
                "merged_vertex_groups": merged_groups,
                "removed_faces_due_to_collapse": removed_faces,
            },
        )

    def repair_degenerate_faces(self) -> Dict[str, Any]:
        """
        Remove zero-area faces and exact duplicate faces.
        """
        V = self._V
        F = self._F

        v0 = V[F[:, 0]]
        v1 = V[F[:, 1]]
        v2 = V[F[:, 2]]
        areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
        zero_area_faces = np.where(areas < self.degenerate_area_epsilon)[0]

        sorted_F = np.sort(F, axis=1)
        _, idx, counts = np.unique(sorted_F, axis=0, return_index=True, return_counts=True)
        duplicate_faces: List[int] = []
        for i, c in zip(idx, counts):
            if c > 1:
                dup_indices = np.where((sorted_F == sorted_F[i]).all(axis=1))[0].tolist()
                duplicate_faces.extend(dup_indices[1:])
        duplicate_faces = np.array(sorted(set(duplicate_faces)), dtype=int)

        if len(zero_area_faces) or len(duplicate_faces):
            to_remove = np.unique(np.concatenate([zero_area_faces, duplicate_faces]))
        else:
            to_remove = np.array([], dtype=int)

        keep_mask = np.ones(len(F), dtype=bool)
        keep_mask[to_remove] = False
        new_F = F[keep_mask]

        self._set_from_arrays(V, new_F)

        return self._make_result(
            ok=True,
            errors=[],
            details={
                "removed_zero_area_faces": zero_area_faces.tolist(),
                "removed_duplicate_faces": duplicate_faces.tolist(),
            },
        )

    def repair_ccw_winding(self) -> Dict[str, Any]:
        """
        Fix local winding inconsistencies across shared edges by flipping
        faces where necessary. Does not enforce outward vs inward.
        """
        F = self._F.copy()
        edge_to_faces: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for fi, (a, b, c) in enumerate(F):
            edges = [(a, b), (b, c), (c, a)]
            for (u, v) in edges:
                key = (u, v) if u < v else (v, u)
                sign = 1 if key == (u, v) else -1
                edge_to_faces.setdefault(key, []).append((fi, sign))

        flipped_faces: List[int] = []
        for faces in edge_to_faces.values():
            if len(faces) == 2:
                (f0, s0), (f1, s1) = faces
                if s0 == s1:
                    F[f1] = F[f1][[0, 2, 1]]
                    flipped_faces.append(f1)

        self._set_from_arrays(self._V, F)

        return self._make_result(
            ok=True,
            errors=[],
            details={"flipped_faces": sorted(set(flipped_faces))},
        )

    def repair_normals_outward(self) -> Dict[str, Any]:
        """
        For each connected shell, if most faces appear inward (based on
        centroid test), flip all faces in that shell.
        """
        V = self._V
        F = self._F
        normals = self._compute_face_normals(F, V)
        components = self._connected_face_components(F)

        flipped_shells: List[int] = []

        for si, comp in enumerate(components):
            comp = np.asarray(comp, dtype=int)
            F_comp = F[comp]
            n_comp = normals[comp]

            shell_vertices = np.unique(F_comp.flatten())
            shell_centroid = V[shell_vertices].mean(axis=0)

            v0 = V[F_comp[:, 0]]
            v1 = V[F_comp[:, 1]]
            v2 = V[F_comp[:, 2]]
            face_centroids = (v0 + v1 + v2) / 3.0

            dirs = face_centroids - shell_centroid
            dots = np.einsum("ij,ij->i", n_comp, dirs)
            num_outward = np.sum(dots > 0)
            num_inward = np.sum(dots < 0)

            if num_inward > num_outward:
                F[comp] = F[comp][:, [0, 2, 1]]
                flipped_shells.append(si)

        self._set_from_arrays(V, F)

        return self._make_result(
            ok=True,
            errors=[],
            details={"flipped_shells": flipped_shells},
        )

    def repair_boundary_edges(self) -> Dict[str, Any]:
        """
        Simple hole-filling: for each boundary loop, create a fan from the
        loop centroid. This is heuristic and assumes small, roughly planar holes.
        """
        V = self._V
        F = self._F
        edge_map = self._compute_edge_map(F)

        boundary_edges = [e for e, faces in edge_map.items() if len(faces) == 1]
        if not boundary_edges:
            return self._make_result(
                ok=True,
                errors=[],
                details={"filled_holes": 0, "new_faces": []},
            )

        adj: Dict[int, List[int]] = {}
        for u, v in boundary_edges:
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)

        loops: List[List[int]] = []
        visited = set()
        for start in adj.keys():
            if start in visited:
                continue
            loop = [start]
            visited.add(start)
            cur = start
            prev = None
            while True:
                neighbors = adj[cur]
                nxt = None
                for nb in neighbors:
                    if nb == prev:
                        continue
                    if nb not in visited or (nb == start and len(loop) > 2):
                        nxt = nb
                        break
                if nxt is None:
                    break
                if nxt == start:
                    break
                loop.append(nxt)
                visited.add(nxt)
                prev, cur = cur, nxt
            if len(loop) >= 3:
                loops.append(loop)

        new_faces: List[Tuple[int, int, int]] = []
        for loop in loops:
            loop_vertices = V[np.array(loop)]
            centroid = loop_vertices.mean(axis=0)
            centroid_index = len(V)
            V = np.vstack([V, centroid])
            for i in range(len(loop)):
                a = loop[i]
                b = loop[(i + 1) % len(loop)]
                new_faces.append((centroid_index, a, b))

        if new_faces:
            F = np.vstack([F, np.asarray(new_faces, dtype=np.int64)])
            self._set_from_arrays(V, F)

        return self._make_result(
            ok=True,
            errors=[],
            details={"filled_holes": len(loops), "new_faces": new_faces},
        )

    def repair_non_manifold_edges(self) -> Dict[str, Any]:
        """
        Report non-manifold edges. No automatic repair is performed.

        Destructive Repair: Non‑Manifold Edges
        --------------------------------------

        A "non‑manifold edge" is an edge with 3 or more incident faces. This is a
        topological error that prevents the mesh from representing a valid solid.

        This repair is DESTRUCTIVE and should not be part of `repair_all()`.

        Correct deterministic behavior:
            - For each non‑manifold edge:
                - Keep the first two faces that share the edge
                - Remove all additional faces that reference the edge

        Rationale:
            - Non‑manifold edges are a superset of duplicate edges.
            - Removing extra faces is the only deterministic, predictable fix.
            - Splitting the mesh or duplicating vertices is possible but introduces
            subjective topology decisions and is not universally correct.
            - Slicers require manifold geometry; removing invalid faces is the safest
            way to restore manifoldness.

        Notes:
            - This may create holes or disconnected shells.
            - The user may choose to run hole‑filling or shell‑merging afterward.
            - This operation should only run when explicitly requested by the user.
        """
        check = self.check_non_manifold_edges()
        return self._make_result(
            ok=check["ok"],
            errors=check["errors"],
            details=check["details"],
        )

    def repair_self_intersections(self) -> Dict[str, Any]:
        """
        Report self-intersections. No automatic repair is performed.

        Destructive Repair: Self‑Intersecting Faces
        -------------------------------------------

        A self‑intersection occurs when two triangles intersect in 3D space without
        sharing an edge or vertex. This produces invalid geometry that slicers cannot
        interpret reliably.

        This repair is DESTRUCTIVE and should not be part of `repair_all()`.

        Correct deterministic behavior:
            - Identify all pairs of intersecting faces
            - Remove all faces that participate in any intersection

        Rationale:
            - There is no universally correct way to "fix" an intersection by
            modifying geometry; cutting or splitting faces introduces ambiguity.
            - Removing intersecting faces is deterministic, safe, and consistent with
            how professional tools (Netfabb, Meshmixer) handle "remove self‑intersecting faces".
            - This ensures the mesh becomes non‑self‑intersecting, even if it exposes
            holes that the user may later fill.

        Notes:
            - This may create holes or disconnected shells.
            - This operation should only run when explicitly requested by the user.
            - After removal, the user may choose to run hole‑filling or other repairs.
        """
        check = self.check_self_intersections()
        return self._make_result(
            ok=check["ok"],
            errors=check["errors"],
            details=check["details"],
        )

    def repair_duplicate_edges(self) -> Dict[str, Any]:
        """
        Report duplicate / non-manifold edge usage. No automatic repair is
        performed. This is intentionally NOT part of repair_all().

        Destructive Repair: Duplicate Edges
        -----------------------------------

        A "duplicate edge" is an edge shared by more than two faces. This is always
        topologically invalid for a manifold mesh and typically arises from geometry
        generation algorithms that accidentally emit overlapping polygons.

        This repair is DESTRUCTIVE and should not be part of `repair_all()`.

        Correct deterministic behavior:
            - For each edge with >2 incident faces:
                - Keep the first two faces (the minimum needed for a manifold surface)
                - Remove all additional faces that reference this edge

        Rationale:
            - Removing extra faces is the only deterministic, slicer‑friendly fix.
            - Attempting to split or duplicate geometry introduces ambiguity and
            unpredictable topology changes.
            - This matches the behavior of professional tools (Netfabb, Meshmixer)
            when configured for "remove overlapping faces".

        Notes:
            - This operation may create new boundary edges.
            - This operation may expose holes that the user can later fill manually.
            - This operation should only run when explicitly requested by the user.
        """
        check = self.check_duplicate_edges()
        return self._make_result(
            ok=check["ok"],
            errors=check["errors"],
            details=check["details"],
        )

    # -------------------------------------------------------------------------
    # master validation / repair
    # -------------------------------------------------------------------------

    def validate_for_printing(self) -> Dict[str, Any]:
        """
        Run all checks relevant to 3D printing / slicer semantics and
        return a structured report. This does not mutate the mesh.
        """
        results = {
            "non_manifold_edges": self.check_non_manifold_edges(),
            "boundary_edges": self.check_boundary_edges(),
            "degenerate_faces": self.check_degenerate_faces(),
            "self_intersections": self.check_self_intersections(),
            "ccw_winding_consistency": self.check_ccw_winding_consistency(),
            "normals_outward": self.check_normals_outward(),
            "duplicate_vertices": self.check_duplicate_vertices(),
            "disconnected_shells": self.check_disconnected_shells(),
            "duplicate_edges": self.check_duplicate_edges(),
        }

        overall_ok = all(r["ok"] for r in results.values())
        return {
            "overall_ok": overall_ok,
            "checks": results,
        }

    def repair_all(self) -> Dict[str, Any]:
        """
        Run a deterministic sequence of safe, non-destructive repairs aimed at
        making the mesh slicer-friendly. This intentionally does NOT auto-repair
        duplicate edges, non-manifold edges, or self-intersections.
        """
        reports: Dict[str, Any] = {}

        # Safe repairs only:
        reports["duplicate_vertices"] = self.repair_duplicate_vertices()
        reports["degenerate_faces"] = self.repair_degenerate_faces()
        reports["boundary_edges"] = self.repair_boundary_edges()
        reports["ccw_winding_consistency"] = self.repair_ccw_winding()
        reports["normals_outward"] = self.repair_normals_outward()

        # Final validation snapshot after safe repairs
        final_validation = self.validate_for_printing()

        return {
            "steps": reports,
            "final_validation": final_validation,
        }

    def repair_selected(self, repairs: List[Callable[[], Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Run exactly the repair functions provided in `repairs`, in order.

        Example:
            mesh.repair_selected([
                mesh.repair_duplicate_vertices,
                mesh.repair_degenerate_faces,
                mesh.repair_duplicate_edges,   # destructive/manual
            ])

        Each repair function must be a zero-argument callable that returns
        a structured report (the same format as all repair_* methods).
        """
        reports: Dict[str, Any] = {}

        for func in repairs:
            name = func.__name__
            try:
                reports[name] = func()
            except Exception as e:
                reports[name] = {
                    "ok": False,
                    "errors": [f"Exception during repair: {e}"],
                    "details": {},
                }

        return reports
