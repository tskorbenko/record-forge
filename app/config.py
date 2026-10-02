from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecordConfig:
    """All tunable physical and signal parameters, expressed in mm/seconds/Hz.

    The defaults target a 7-inch, 45 RPM FDM test record and are deliberately
    conservative. Calibration should only require changing this object.
    """

    record_diameter_mm: float = 177.8
    center_hole_mm: float = 7.24
    outer_groove_radius_mm: float = 87.1
    inner_groove_radius_mm: float = 66.0
    record_thickness_mm: float = 2.0
    rpm: float = 45.0
    groove_pitch_mm: float = 0.82
    groove_width_mm: float = 0.36
    groove_depth_mm: float = 0.22
    groove_amplitude_mm: float = 0.075
    bevel_mm: float = 0.35
    nozzle_diameter_mm: float = 0.2
    source_sample_rate: int = 44_100
    target_sample_rate: int = 2_050
    max_duration_sec: float = 30.0
    high_pass_hz: float = 200.0
    low_pass_hz: float = 950.0
    limiter_threshold: float = 0.92
    max_vertical_step_mm: float = 0.035
    lead_in_revolutions: float = 1.0
    run_out_revolutions: float = 0.75
    angular_segments: int = 1_368
    groove_radial_step_mm: float = 0.12
    label_radial_rings: int = 18
    edge_radial_rings: int = 8
    loop_spacing_mm: float = 2.3
    max_upload_bytes: int = 50 * 1024 * 1024
    job_ttl_hours: int = 6

    @property
    def radius_mm(self) -> float:
        return self.record_diameter_mm / 2.0

    @property
    def hole_radius_mm(self) -> float:
        return self.center_hole_mm / 2.0

    @property
    def revolutions_per_second(self) -> float:
        return self.rpm / 60.0

    @property
    def revolution_duration_sec(self) -> float:
        return 60.0 / self.rpm

    def public_dict(self) -> dict:
        return asdict(self)


CONFIG = RecordConfig()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = PROJECT_ROOT / "temp"

