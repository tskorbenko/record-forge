from dataclasses import replace
import zipfile

import numpy as np

from app.config import CONFIG
from app.exporters.stl_exporter import export_binary_stl
from app.exporters.three_mf_exporter import export_3mf
from app.geometry.mesh import build_record


def test_binary_stl_and_3mf_exports(tmp_path):
    cfg = replace(CONFIG, angular_segments=128, groove_radial_step_mm=0.8, label_radial_rings=6, edge_radial_rings=3)
    mesh = build_record([np.zeros(200, dtype=np.float32)], 2_050, "normal", cfg).mesh
    stl = tmp_path / "record.stl"
    three_mf = tmp_path / "record.3mf"
    export_binary_stl(mesh, stl)
    export_3mf(mesh, three_mf)
    assert stl.read_bytes()[80:84] == len(mesh.faces).to_bytes(4, "little")
    assert zipfile.is_zipfile(three_mf)
    with zipfile.ZipFile(three_mf) as package:
        model = package.read("3D/3dmodel.model")
        assert b'unit="millimeter"' in model
        assert model.count(b"<triangle ") == len(mesh.faces)

