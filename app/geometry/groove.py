from __future__ import annotations

import numpy as np

from app.config import CONFIG, RecordConfig
from app.geometry.spiral import angle_for_time, radius_for_angle


def normal_surface_z(radii: np.ndarray, angles: np.ndarray, audio: np.ndarray, sample_rate: int, config: RecordConfig = CONFIG) -> tuple[np.ndarray, dict]:
    """Evaluate a printable V-like spiral depression on a polar surface grid.

    For every polar vertex we choose the nearest turn of the Archimedean
    centerline. Its signed radial distance controls the groove cross-section;
    time on that centerline selects the waveform sample that modulates depth.
    """
    rr = radii[:, None]
    phi = angles[None, :]
    lead_angle = 2.0 * np.pi * config.lead_in_revolutions
    audio_duration = audio.size / sample_rate
    audio_angle = float(angle_for_time(audio_duration, config.rpm))
    run_angle = 2.0 * np.pi * config.run_out_revolutions
    end_angle = lead_angle + audio_angle + run_angle

    # θ = φ + 2πn. Choose n whose spiral radius is nearest this grid radius.
    turns = np.rint((config.outer_groove_radius_mm - rr) / config.groove_pitch_mm - phi / (2.0 * np.pi))
    theta = phi + 2.0 * np.pi * turns
    center_r = radius_for_angle(theta, config.outer_groove_radius_mm, config.groove_pitch_mm)
    distance = np.abs(rr - center_r)
    profile = np.clip(1.0 - distance / (config.groove_width_mm / 2.0), 0.0, 1.0) ** 1.4
    valid = (theta >= 0.0) & (theta <= end_angle)
    profile *= valid

    time = (theta - lead_angle) / (2.0 * np.pi * config.revolutions_per_second)
    sample_pos = np.clip(time * sample_rate, 0.0, max(0, audio.size - 1))
    waveform = np.interp(sample_pos, np.arange(audio.size), audio) if audio.size else np.zeros_like(theta)
    waveform *= (time >= 0.0) & (time < audio_duration)
    depth = np.clip(config.groove_depth_mm + config.groove_amplitude_mm * waveform, 0.06, config.record_thickness_mm * 0.45)
    z = config.record_thickness_mm - profile * depth

    # Add a silent locked circle at the endpoint; min() unions depressions.
    lock_radius = float(radius_for_angle(end_angle, config.outer_groove_radius_mm, config.groove_pitch_mm))
    lock_profile = np.clip(1.0 - np.abs(rr - lock_radius) / (config.groove_width_mm / 2.0), 0.0, 1.0) ** 1.4
    z = np.minimum(z, config.record_thickness_mm - lock_profile * config.groove_depth_mm)
    return z.astype(np.float32), {
        "audio_revolutions": audio_duration * config.revolutions_per_second,
        "total_revolutions": end_angle / (2.0 * np.pi),
        "final_radius_mm": lock_radius,
    }


def loop_surface_z(radii: np.ndarray, angles: np.ndarray, loops: list[np.ndarray], config: RecordConfig = CONFIG) -> tuple[np.ndarray, dict]:
    rr = radii[:, None]
    z = np.full((radii.size, angles.size), config.record_thickness_mm, dtype=np.float32)
    loop_radii: list[float] = []
    for index, audio in enumerate(loops):
        radius = config.outer_groove_radius_mm - 2.0 - index * config.loop_spacing_mm
        loop_radii.append(radius)
        pos = angles / (2.0 * np.pi) * audio.size
        waveform = np.interp(pos, np.arange(audio.size), audio, period=audio.size)
        profile = np.clip(1.0 - np.abs(rr - radius) / (config.groove_width_mm / 2.0), 0.0, 1.0) ** 1.4
        depth = np.clip(config.groove_depth_mm + config.groove_amplitude_mm * waveform[None, :], 0.06, config.record_thickness_mm * 0.45)
        z = np.minimum(z, config.record_thickness_mm - profile * depth)
    return z, {"loop_radii_mm": loop_radii, "loop_duration_sec": config.revolution_duration_sec}

