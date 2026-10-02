from __future__ import annotations

import numpy as np
from scipy import signal


def generate_test_signal(kind: str, duration: float, sample_rate: int) -> np.ndarray:
    t = np.arange(max(1, int(duration * sample_rate)), dtype=np.float32) / sample_rate
    if kind == "sine440":
        return (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    if kind == "sine500":
        return (0.8 * np.sin(2 * np.pi * 500 * t)).astype(np.float32)
    if kind == "sweep":
        return (0.8 * signal.chirp(t, 180, max(duration, 1e-3), 950)).astype(np.float32)
    if kind == "silence":
        return np.zeros_like(t)
    if kind == "impulse":
        out = np.zeros_like(t)
        out[:: max(1, sample_rate // 5)] = 0.8
        return out
    raise ValueError("Unknown test signal.")

