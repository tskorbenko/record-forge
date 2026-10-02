from dataclasses import replace

import numpy as np

from app.config import CONFIG
from app.geometry.mesh import build_record


def small_config():
    return replace(CONFIG, angular_segments=192, groove_radial_step_mm=0.5, label_radial_rings=8, edge_radial_rings=4)


def test_mesh_is_watertight_finite_and_correct_size():
    cfg = small_config()
    audio = np.sin(np.linspace(0, 20 * np.pi, 400)).astype(np.float32) * 0.5
    result = build_record([audio], 2_050, "normal", cfg)
    assert result.mesh.is_watertight
    assert np.isfinite(result.mesh.vertices).all()
    assert np.allclose(result.mesh.extents[:2], [177.8, 177.8], atol=0.25)
    assert 0 < result.mesh.extents[2] <= cfg.record_thickness_mm + 0.05


def test_loop_mesh_supports_four_independent_grooves():
    cfg = small_config()
    loop = np.zeros(round(cfg.revolution_duration_sec * 500), dtype=np.float32)
    result = build_record([loop] * 4, 500, "loop", cfg)
    assert len(result.debug["loop_radii_mm"]) == 4
    assert result.mesh.is_watertight

