from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import imageio_ffmpeg
from scipy.io import wavfile

from app.config import CONFIG, RecordConfig


class AudioDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class AudioInfo:
    duration_sec: float
    sample_rate: int
    channels: int
    codec: str


def ffmpeg_executable() -> str:
    """Prefer the system binary; fall back to imageio-ffmpeg's pinned build."""
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def _probe_with_ffmpeg(path: Path) -> AudioInfo:
    command = [ffmpeg_executable(), "-hide_banner", "-i", str(path), "-t", "0.001", "-f", "null", "-"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    output = result.stderr
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    audio_match = re.search(r"Audio:\s*([^,]+),\s*(\d+)\s*Hz,\s*([^,\r\n]+)", output)
    if not duration_match or not audio_match:
        raise AudioDecodeError("The file could not be decoded as readable audio.")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    layout = audio_match.group(3).lower()
    channels = 1 if "mono" in layout else 2 if "stereo" in layout else 6 if "5.1" in layout else 1
    return AudioInfo(duration, int(audio_match.group(2)), channels, audio_match.group(1).strip())


def probe_audio(path: Path, config: RecordConfig = CONFIG) -> AudioInfo:
    if not path.exists() or path.stat().st_size == 0:
        raise AudioDecodeError("The uploaded file is empty.")
    if path.stat().st_size > config.max_upload_bytes:
        raise AudioDecodeError("The uploaded file is too large.")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return _probe_with_ffmpeg(path)
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels,codec_type",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        stream = next(s for s in data.get("streams", []) if s.get("codec_type") == "audio")
        duration = float(data["format"]["duration"])
        if not np.isfinite(duration) or duration <= 0:
            raise ValueError
        return AudioInfo(duration, int(stream["sample_rate"]), int(stream["channels"]), stream["codec_name"])
    except (subprocess.SubprocessError, KeyError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        raise AudioDecodeError("The file could not be decoded as readable audio.") from exc


def decode_to_mono(path: Path, output_wav: Path, max_duration: float, config: RecordConfig = CONFIG) -> tuple[np.ndarray, int, AudioInfo]:
    info = probe_audio(path, config)
    command = [
        ffmpeg_executable(), "-y", "-v", "error", "-i", str(path), "-t", f"{max_duration:.6f}",
        "-ac", "1", "-ar", str(config.source_sample_rate), "-c:a", "pcm_s16le", str(output_wav),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=60)
    except subprocess.SubprocessError as exc:
        raise AudioDecodeError("The file could not be decoded.") from exc
    rate, pcm = wavfile.read(output_wav)
    samples = pcm.astype(np.float32) / 32768.0
    return samples, int(rate), info
