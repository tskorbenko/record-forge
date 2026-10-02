from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.jobs import STORE, process_job, process_test_job
from app.api.schemas import JobCreate, TestJobCreate
from app.config import CONFIG

router = APIRouter(prefix="/api")


def _job(job_id: str):
    try:
        return STORE.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "Job not found.") from exc


@router.post("/jobs", status_code=201)
def create_job(request: JobCreate) -> dict:
    return STORE.create(request.mode, request.loop_count).public()


@router.post("/jobs/{job_id}/audio")
async def upload_audio(job_id: str, file: UploadFile = File(...), slot: int = Query(0, ge=0, le=3)) -> dict:
    job = _job(job_id)
    if slot >= job.loop_count:
        raise HTTPException(400, "Audio slot is outside this job's loop count.")
    content_type = (file.content_type or "").lower()
    allowed_mime = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}
    if content_type not in allowed_mime:
        raise HTTPException(415, "Unsupported audio format. Use MP3 or WAV.")
    suffix = Path(file.filename or "audio").suffix.lower()
    destination = job.directory / f"source-{slot}{suffix if suffix in {'.mp3', '.wav'} else '.audio'}"
    size = 0
    with destination.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > CONFIG.max_upload_bytes:
                output.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(413, "The uploaded file is too large.")
            output.write(chunk)
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "The uploaded file is empty.")
    job.inputs[slot] = destination
    job.stage = "Audio uploaded"
    return job.public()


@router.post("/jobs/{job_id}/generate", status_code=202)
def generate(job_id: str, background: BackgroundTasks) -> dict:
    job = _job(job_id)
    if job.status == "processing":
        raise HTTPException(409, "This job is already processing.")
    if len(job.inputs) != job.loop_count:
        raise HTTPException(400, "Upload every required audio file first.")
    job.status = "processing"
    job.stage = "Uploading complete"
    background.add_task(process_job, job)
    return job.public()


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return _job(job_id).public()


def _download(job_id: str, filename: str, media_type: str) -> FileResponse:
    job = _job(job_id)
    path = job.directory / filename
    if job.status != "ready" or not path.exists():
        raise HTTPException(409, "The requested file is not ready.")
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/jobs/{job_id}/preview")
def preview(job_id: str) -> FileResponse:
    job = _job(job_id)
    path = job.directory / "preview.wav"
    if job.status != "ready" or not path.exists():
        raise HTTPException(409, "The preview is not ready.")
    return FileResponse(path, media_type="audio/wav", content_disposition_type="inline")


@router.get("/jobs/{job_id}/record.stl")
def stl(job_id: str) -> FileResponse:
    return _download(job_id, "record.stl", "model/stl")


@router.get("/jobs/{job_id}/record.3mf")
def three_mf(job_id: str) -> FileResponse:
    return _download(job_id, "record.3mf", "model/3mf")


@router.post("/debug/test-job", status_code=202)
def debug_test_job(request: TestJobCreate, background: BackgroundTasks) -> dict:
    job = STORE.create("normal", 1)
    background.add_task(process_test_job, job, request.signal, request.duration_sec)
    return job.public()


@router.get("/config")
def config() -> dict:
    return CONFIG.public_dict()
