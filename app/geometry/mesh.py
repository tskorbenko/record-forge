from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from app.config import CONFIG, RecordConfig
from app.geometry.groove import loop_surface_z, normal_surface_z


@dataclass(frozen=True)
class MeshResult:
    mesh: trimesh.Trimesh
    debug: dict


def radial_grid(config: RecordConfig = CONFIG) -> np.ndarray:
    inner_land = np.linspace(config.hole_radius_mm, config.inner_groove_radius_mm, config.label_radial_rings, endpoint=False)
    groove = np.arange(config.inner_groove_radius_mm, config.outer_groove_radius_mm + config.groove_radial_step_mm, config.groove_radial_step_mm)
    outer_land = np.linspace(config.outer_groove_radius_mm + config.groove_radial_step_mm, config.radius_mm, config.edge_radial_rings)
    return np.unique(np.concatenate([inner_land, groove, outer_land])).astype(np.float32)


def _surface_mesh(radii: np.ndarray, angles: np.ndarray, top_z: np.ndarray, config: RecordConfig) -> trimesh.Trimesh:
    nr, na = top_z.shape
    rr = np.repeat(radii[:, None], na, axis=1)
    aa = np.repeat(angles[None, :], nr, axis=0)
    top = np.column_stack([(rr * np.cos(aa)).ravel(), (rr * np.sin(aa)).ravel(), top_z.ravel()]).astype(np.float32)

    # The flat bottom only needs matching inner/outer boundary rings.
    bottom_inner = np.column_stack([radii[0] * np.cos(angles), radii[0] * np.sin(angles), np.zeros(na)])
    bottom_outer = np.column_stack([radii[-1] * np.cos(angles), radii[-1] * np.sin(angles), np.zeros(na)])
    vertices = np.vstack([top, bottom_inner, bottom_outer]).astype(np.float32)
    bi = nr * na
    bo = bi + na
    faces: list[tuple[int, int, int]] = []

    # Top surface, counter-clockwise when viewed from above.
    for ring in range(nr - 1):
        a = ring * na
        b = (ring + 1) * na
        for j in range(na):
            k = (j + 1) % na
            faces.append((a + j, b + j, b + k))
            faces.append((a + j, b + k, a + k))

    top_inner = 0
    top_outer = (nr - 1) * na
    for j in range(na):
        k = (j + 1) % na
        # Bottom annulus faces point downward.
        faces.append((bi + j, bo + k, bo + j))
        faces.append((bi + j, bi + k, bo + k))
        # Outer cylinder.
        faces.append((top_outer + j, bo + j, bo + k))
        faces.append((top_outer + j, bo + k, top_outer + k))
        # Hole cylinder points inward into the opening.
        faces.append((top_inner + j, bi + k, bi + j))
        faces.append((top_inner + j, top_inner + k, bi + k))
    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces, dtype=np.int32), process=True, validate=True)


def build_record(audio_tracks: list[np.ndarray], sample_rate: int, mode: str = "normal", config: RecordConfig = CONFIG) -> MeshResult:
    if not audio_tracks or any(track.size == 0 for track in audio_tracks):
        raise ValueError("At least one non-empty audio track is required.")
    radii = radial_grid(config)
    angles = np.linspace(0.0, 2.0 * np.pi, config.angular_segments, endpoint=False, dtype=np.float32)
    if mode == "normal":
        top_z, physical = normal_surface_z(radii, angles, audio_tracks[0], sample_rate, config)
    elif mode == "loop":
        top_z, physical = loop_surface_z(radii, angles, audio_tracks, config)
    else:
        raise ValueError("Unsupported record mode.")
    mesh = _surface_mesh(radii, angles, top_z, config)
    bounds = mesh.bounds
    debug = {
        **physical,
        "vertices": int(len(mesh.vertices)),
        "triangles": int(len(mesh.faces)),
        "mesh_dimensions_mm": [round(float(v), 4) for v in (bounds[1] - bounds[0])],
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "groove_pitch_mm": config.groove_pitch_mm,
        "outer_radius_mm": config.outer_groove_radius_mm,
    }
    validate_mesh(mesh, config)
    return MeshResult(mesh, debug)


def validate_mesh(mesh: trimesh.Trimesh, config: RecordConfig = CONFIG) -> None:
    if mesh.is_empty or len(mesh.faces) == 0:
        raise ValueError("Generated mesh is empty.")
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Generated mesh contains non-finite coordinates.")
    dimensions = mesh.bounds[1] - mesh.bounds[0]
    if not np.isclose(dimensions[0], config.record_diameter_mm, atol=0.25) or not np.isclose(dimensions[1], config.record_diameter_mm, atol=0.25):
        raise ValueError("Generated record diameter is outside tolerance.")
    if dimensions[2] <= 0 or dimensions[2] > config.record_thickness_mm + 0.05:
        raise ValueError("Generated record thickness is outside tolerance.")
    if not mesh.is_watertight:
        raise ValueError("Generated mesh is not watertight.")

