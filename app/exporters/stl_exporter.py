from __future__ import annotations

from pathlib import Path

import trimesh


def export_binary_stl(mesh: trimesh.Trimesh, path: Path) -> None:
    data = mesh.export(file_type="stl")
    path.write_bytes(data)
    if path.stat().st_size < 84 or (path.stat().st_size - 84) % 50 != 0:
        raise ValueError("Binary STL validation failed.")

