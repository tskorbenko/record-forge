from __future__ import annotations

import numpy as np

from app.config import CONFIG, RecordConfig


def make_seamless_loop(samples: np.ndarray, sample_rate: int, config: RecordConfig = CONFIG) -> np.ndarray:
    target = max(2, int(round(config.revolution_duration_sec * sample_rate)))
    x = np.asarray(samples[:target], dtype=np.float32)
    if x.size < target:
        x = np.pad(x, (0, target - x.size))
    fade = min(max(8, int(sample_rate * 0.025)), target // 5)
    if fade:
        weight = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        blended = x[-fade:] * (1.0 - weight) + x[:fade] * weight
        x[:fade] = blended
        x[-fade:] = blended
        seam = (x[0] + x[-1]) * 0.5
        x[0] = seam
        x[-1] = seam
    x -= float(np.mean(x))
    peak = float(np.max(np.abs(x)))
    if peak > 1e-9:
        x *= config.limiter_threshold / peak
    return x


def repeated_preview(loop: np.ndarray, repetitions: int = 4) -> np.ndarray:
    return np.tile(loop, max(1, repetitions))
