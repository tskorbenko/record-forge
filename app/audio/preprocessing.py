from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

from app.config import CONFIG, RecordConfig


@dataclass(frozen=True)
class ProcessedAudio:
    samples: np.ndarray
    sample_rate: int
    original_duration_sec: float
    used_duration_sec: float
    trimmed: bool


def preprocess(samples: np.ndarray, input_rate: int, original_duration: float, max_duration: float, config: RecordConfig = CONFIG) -> ProcessedAudio:
    if samples.size == 0 or input_rate <= 0:
        raise ValueError("No audio samples were decoded.")
    max_count = max(1, int(round(max_duration * input_rate)))
    x = np.asarray(samples[:max_count], dtype=np.float64)
    x = np.nan_to_num(x, copy=False)
    x -= np.mean(x)

    # A 4th-order SOS band-pass removes bass excursions and ultrasonic geometry.
    nyquist = input_rate / 2.0
    low = max(1.0, min(config.high_pass_hz, nyquist * 0.8))
    high = max(low + 1.0, min(config.low_pass_hz, nyquist * 0.95))
    sos = signal.butter(4, [low, high], btype="bandpass", fs=input_rate, output="sos")
    if x.size > 32:
        x = signal.sosfiltfilt(sos, x)
    else:
        x = signal.sosfilt(sos, x)

    # Soft compression followed by a hard safety limiter is deterministic.
    x = np.tanh(x * 1.6)
    peak = float(np.max(np.abs(x)))
    if peak > 1e-9:
        x = x / peak * config.limiter_threshold
    target_count = max(1, int(round(x.size * config.target_sample_rate / input_rate)))
    x = signal.resample_poly(x, config.target_sample_rate, input_rate)
    x = x[:target_count]
    x = np.clip(np.nan_to_num(x), -config.limiter_threshold, config.limiter_threshold).astype(np.float32)
    used = x.size / config.target_sample_rate
    return ProcessedAudio(x, config.target_sample_rate, original_duration, used, original_duration > max_duration + 1e-3)


def slope_limit(samples: np.ndarray, max_step: float) -> np.ndarray:
    out = np.asarray(samples, dtype=np.float32).copy()
    if out.size < 2:
        return out
    for i in range(1, out.size):
        out[i] = np.clip(out[i], out[i - 1] - max_step, out[i - 1] + max_step)
    return out


def write_preview_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    # The groove samples stay at the physically useful rate (2050 Hz by
    # default). A browser preview needs a conventional PCM rate. Polyphase
    # upsampling changes only the delivery format, not the encoded signal.
    preview_rate = CONFIG.source_sample_rate
    if sample_rate != preview_rate:
        playback = signal.resample_poly(samples, preview_rate, sample_rate)
    else:
        playback = np.asarray(samples)
    pcm = (np.clip(np.nan_to_num(playback), -1, 1) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(preview_rate)
        wav.writeframes(pcm.tobytes())
