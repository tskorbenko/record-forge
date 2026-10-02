from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from app.audio.decoder import decode_to_mono
from app.audio.loop_processing import make_seamless_loop, repeated_preview
from app.audio.preprocessing import preprocess, slope_limit, write_preview_wav
from app.config import CONFIG, TEMP_ROOT
from app.exporters.stl_exporter import export_binary_stl
from app.exporters.three_mf_exporter import export_3mf
from app.geometry.mesh import build_record
from app.geometry.test_signals import generate_test_signal

logger = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    mode: str
    loop_count: int
    directory: Path
    status: str = "waiting"
    stage: str = "Waiting for audio"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    inputs: dict[int, Path] = field(default_factory=dict)
    result: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "loop_count": self.loop_count,
            "status": self.status,
            "stage": self.stage,
            "error": self.error,
            "uploaded_slots": sorted(self.inputs),
            "result": self.result,
        }


class JobStore:
    def __init__(self) -> None:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    def create(self, mode: str, loop_count: int) -> Job:
        job_id = str(uuid.uuid4())
        directory = TEMP_ROOT / job_id
        directory.mkdir(parents=True)
        job = Job(job_id, mode, loop_count if mode == "loop" else 1, directory)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    def cleanup(self) -> None:
        cutoff = time.time() - CONFIG.job_ttl_hours * 3600
        for path in TEMP_ROOT.iterdir():
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file() and path.name != ".gitkeep" and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        with self._lock:
            self._jobs = {key: value for key, value in self._jobs.items() if value.created_at >= cutoff}


STORE = JobStore()


def _set(job: Job, stage: str, status: str = "processing") -> None:
    job.stage = stage
    job.status = status


def process_job(job: Job) -> None:
    started = time.perf_counter()
    try:
        tracks: list[np.ndarray] = []
        infos: list[dict] = []
        _set(job, "Preparing audio")
        max_duration = CONFIG.max_duration_sec if job.mode == "normal" else CONFIG.revolution_duration_sec
        for slot in range(job.loop_count):
            source = job.inputs.get(slot)
            if not source:
                raise ValueError(f"Audio slot {slot + 1} is missing.")
            decoded_path = job.directory / f"decoded-{slot}.wav"
            raw, rate, info = decode_to_mono(source, decoded_path, max_duration)
            _set(job, "Filtering audio")
            processed = preprocess(raw, rate, info.duration_sec, max_duration)
            signal = processed.samples
            if job.mode == "loop":
                signal = make_seamless_loop(signal, processed.sample_rate)
            signal = slope_limit(signal, CONFIG.max_vertical_step_mm / CONFIG.groove_amplitude_mm)
            tracks.append(signal)
            infos.append({
                "original_duration_sec": round(info.duration_sec, 3),
                "used_duration_sec": round(signal.size / processed.sample_rate, 3),
                "trimmed": info.duration_sec > max_duration + 1e-3,
                "input_sample_rate": info.sample_rate,
                "processed_sample_rate": processed.sample_rate,
                "samples": int(signal.size),
            })

        preview = tracks[0] if job.mode == "normal" else np.concatenate([repeated_preview(track, 4) for track in tracks])
        write_preview_wav(job.directory / "preview.wav", preview, CONFIG.target_sample_rate)
        _set(job, "Generating groove")
        built = build_record(tracks, CONFIG.target_sample_rate, job.mode)
        _set(job, "Building 3D model")
        stl_path = job.directory / "record.stl"
        mf_path = job.directory / "record.3mf"
        _set(job, "Exporting STL")
        export_binary_stl(built.mesh, stl_path)
        _set(job, "Exporting 3MF")
        export_3mf(built.mesh, mf_path)
        job.result = {
            "record": {"diameter_mm": CONFIG.record_diameter_mm, "rpm": CONFIG.rpm, "mono": True, "recommended_nozzle_mm": CONFIG.nozzle_diameter_mm},
            "audio": infos,
            "debug": {
                **built.debug,
                "stl_size_bytes": stl_path.stat().st_size,
                "three_mf_size_bytes": mf_path.stat().st_size,
                "processing_time_sec": round(time.perf_counter() - started, 3),
            },
        }
        (job.directory / "result.json").write_text(json.dumps(job.result, indent=2), encoding="utf-8")
        _set(job, "Ready", "ready")
    except Exception as exc:
        logger.exception("Record generation failed for job %s", job.id)
        job.error = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Record generation failed. Check the server log."
        _set(job, "Failed", "failed")


def process_test_job(job: Job, signal_name: str, duration: float) -> None:
    track = generate_test_signal(signal_name, duration, CONFIG.target_sample_rate)
    job.inputs[0] = job.directory / "generated-test-signal"
    started = time.perf_counter()
    try:
        write_preview_wav(job.directory / "preview.wav", track, CONFIG.target_sample_rate)
        _set(job, "Generating groove")
        built = build_record([track], CONFIG.target_sample_rate, "normal")
        _set(job, "Exporting STL")
        export_binary_stl(built.mesh, job.directory / "record.stl")
        _set(job, "Exporting 3MF")
        export_3mf(built.mesh, job.directory / "record.3mf")
        job.result = {"record": {"diameter_mm": CONFIG.record_diameter_mm, "rpm": CONFIG.rpm, "mono": True}, "audio": [{"test_signal": signal_name, "used_duration_sec": duration}], "debug": {**built.debug, "processing_time_sec": round(time.perf_counter() - started, 3)}}
        _set(job, "Ready", "ready")
    except Exception as exc:
        logger.exception("Test generation failed")
        job.error = str(exc)
        _set(job, "Failed", "failed")
