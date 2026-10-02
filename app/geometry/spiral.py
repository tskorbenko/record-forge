from __future__ import annotations

import numpy as np


def angle_for_time(time_sec: np.ndarray | float, rpm: float) -> np.ndarray | float:
    """θ(t) = 2π × RPM/60 × t."""
    return 2.0 * np.pi * (rpm / 60.0) * time_sec


def radius_for_angle(theta: np.ndarray | float, start_radius_mm: float, pitch_mm: float) -> np.ndarray | float:
    """Archimedean inward spiral: r(θ) = r_start - pitch × θ/(2π)."""
    return start_radius_mm - pitch_mm * theta / (2.0 * np.pi)


def revolutions_for_duration(duration_sec: float, rpm: float) -> float:
    return duration_sec * rpm / 60.0


def final_radius(duration_sec: float, start_radius_mm: float, pitch_mm: float, rpm: float) -> float:
    return start_radius_mm - pitch_mm * revolutions_for_duration(duration_sec, rpm)

