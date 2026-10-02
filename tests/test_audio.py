from dataclasses import replace
import wave

import numpy as np

from app.audio.loop_processing import make_seamless_loop
from app.audio.preprocessing import preprocess, write_preview_wav
from app.config import CONFIG


def test_audio_trims_resamples_normalizes_and_removes_dc():
    source_rate = 4_000
    duration = 31.0
    t = np.arange(int(source_rate * duration)) / source_rate
    stereo_mix = 0.25 + 0.5 * np.sin(2 * np.pi * 440 * t)
    cfg = replace(CONFIG, target_sample_rate=1_000, high_pass_hz=150, low_pass_hz=450)
    result = preprocess(stereo_mix, source_rate, duration, 30.0, cfg)
    assert result.trimmed
    assert result.samples.size == 30_000
    assert abs(float(np.mean(result.samples))) < 0.01
    assert np.max(np.abs(result.samples)) <= cfg.limiter_threshold + 1e-6
    assert np.isfinite(result.samples).all()


def test_loop_has_one_revolution_and_a_closed_seam():
    rate = 2_050
    x = np.linspace(-0.7, 0.4, rate * 2, dtype=np.float32)
    loop = make_seamless_loop(x, rate)
    assert loop.size == round(CONFIG.revolution_duration_sec * rate)
    assert np.isclose(loop[0], loop[-1])
    assert np.max(np.abs(loop)) <= CONFIG.limiter_threshold + 1e-6


def test_preview_is_browser_compatible_without_changing_duration(tmp_path):
    samples = np.sin(np.linspace(0, 2 * np.pi * 440, 2_050, endpoint=False)).astype(np.float32)
    path = tmp_path / "preview.wav"
    write_preview_wav(path, samples, 2_050)
    with wave.open(str(path), "rb") as preview:
        assert preview.getframerate() == 44_100
        assert preview.getnchannels() == 1
        assert preview.getsampwidth() == 2
        assert preview.getnframes() == 44_100
