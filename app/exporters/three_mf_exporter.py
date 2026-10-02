from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import trimesh


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def _write_model(stream, mesh: trimesh.Trimesh) -> None:
    def emit(text: str) -> None:
        stream.write(text.encode("utf-8"))

    emit('<?xml version="1.0" encoding="UTF-8"?>\n')
    emit('<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n')
    emit('<metadata name="Title">Record Forge 7-inch playable record</metadata>\n<resources><object id="1" type="model"><mesh><vertices>\n')
    vertices = np.asarray(mesh.vertices)
    for start in range(0, len(vertices), 4096):
        chunk = vertices[start : start + 4096]
        emit("".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>\n' for x, y, z in chunk))
    emit("</vertices><triangles>\n")
    faces = np.asarray(mesh.faces)
    for start in range(0, len(faces), 4096):
        chunk = faces[start : start + 4096]
        emit("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in chunk))
    emit('</triangles></mesh></object></resources><build><item objectid="1"/></build></model>')


def export_3mf(mesh: trimesh.Trimesh, path: Path) -> None:
    # A minimal OPC package avoids a platform-specific lib3mf binary while using
    # only the published 3MF Core elements needed for one millimetre-scale mesh.
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        with archive.open("3D/3dmodel.model", "w") as model:
            _write_model(model, mesh)
    validate_3mf(path)


def validate_3mf(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError("3MF is not a valid ZIP package.")
    with zipfile.ZipFile(path) as archive:
        required = {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"}
        if not required.issubset(archive.namelist()):
            raise ValueError("3MF package is missing required parts.")
        head = archive.read("3D/3dmodel.model")[:1000]
        if b'unit="millimeter"' not in head or b"<vertices>" not in head:
            raise ValueError("3MF model metadata is invalid.")

