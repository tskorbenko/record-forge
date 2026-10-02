# Record Forge

Record Forge is a working local MVP that converts a short MP3 or WAV file into a physically printable, approximately playable 7-inch record:

`audio → mono/band-limit/resample → time-mapped groove → watertight mesh → 3MF/STL`

It also includes an experimental infinite-loop mode with one to four independent closed circular grooves. Each loop repeats once per 45 RPM revolution (1.333333 seconds).

> **Experimental:** this project produces calibration-grade FDM record geometry, not guaranteed hi-fi audio. Inspect every file in a slicer before printing and protect your turntable/stylus when testing.

## What works

- MP3 and WAV upload with MIME, size, readability, duration, channel, and codec validation
- automatic trimming to 30 seconds in Normal mode
- automatic trimming to one 45 RPM revolution in Loop mode
- mono decode, DC removal, 200–950 Hz band-pass filtering, soft limiting, normalization, and 2050 Hz resampling
- processed WAV preview upsampled to browser-friendly 44.1 kHz PCM; groove geometry remains at 2050 Hz
- one continuous Archimedean spiral with geometric lead-in, run-out, and locked ending groove
- one to four independently playable circular loop grooves with a short seam crossfade
- watertight annular solid with a real center hole, bottom, outer wall, hole wall, and modulated top surface
- compressed millimeter-unit 3MF and binary STL export
- job status polling, staged progress, understandable errors, and six-hour temporary-job cleanup
- configurable developer test signals and debug metadata
- responsive, keyboard-accessible frontend

## Architecture

```text
app/
  main.py                    FastAPI entry point and static frontend
  config.py                  every physical and signal calibration value
  audio/
    decoder.py               ffprobe validation and FFmpeg decode
    preprocessing.py         deterministic filtering/resampling/preview
    loop_processing.py       one-revolution trim and seam crossfade
  geometry/
    spiral.py                time, angle, revolution, and radius equations
    groove.py                spiral/circular groove height evaluation
    mesh.py                  indexed watertight polar mesh and validation
    test_signals.py          sine, sweep, silence, and impulse sources
  exporters/
    stl_exporter.py          binary STL
    three_mf_exporter.py     compressed 3MF Core OPC package
  api/
    jobs.py                  temporary job lifecycle and processing pipeline
    routes.py                upload, generate, status, preview, downloads
    schemas.py               API request validation
  static/                    HTML, CSS, vanilla JavaScript
tests/                       audio, math, geometry, and export tests
temp/                        expiring job files; never committed
```

The frontend is deliberately thin. Processing is kept outside the API layer so a task queue can replace the current FastAPI background task later.

## Requirements

- Python 3.12+
- FFmpeg and ffprobe on `PATH` are recommended; the Python install includes a bundled FFmpeg fallback for decoding when system binaries are unavailable
- enough memory for roughly 275,000 vertices and 550,000 triangles at the default mesh resolution

Major dependencies are all free/open source: FastAPI (MIT), NumPy (BSD), SciPy (BSD), trimesh (MIT), imageio-ffmpeg (BSD), Uvicorn (BSD), and python-multipart (Apache-2.0).

### Install FFmpeg

Windows with winget:

```powershell
winget install Gyan.FFmpeg
```

macOS with Homebrew:

```bash
brew install ffmpeg
```

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Confirm both tools are available:

```bash
ffmpeg -version
ffprobe -version
```

## Run locally

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is at <http://127.0.0.1:8000/docs>.

The `examples/` directory includes a generated 440 Hz preview plus full-resolution STL and 3MF files for quick slicer inspection.

## Run with Docker

```bash
docker compose up --build
```

Then open <http://127.0.0.1:8000>.

## Use the application

1. Keep **Normal record** selected or choose **Infinite loop** and a groove count.
2. Drop an MP3/WAV into every visible slot.
3. Select **Generate record**.
4. Listen to the processed preview.
5. Download the 3MF (preferred) or STL.
6. Inspect dimensions, orientation, and toolpaths in your slicer before printing.

The generated object should import at about `177.8 × 177.8 × 2.0 mm`. STL is unitless by design, so the coordinates are emitted in the conventional millimeter scale. 3MF declares millimeters explicitly.

## Physical model

All calibration lives in `app/config.py` as `RecordConfig`; no physical magic numbers are spread through the algorithms.

For speed `R` RPM:

```text
revolutions_per_second = R / 60
theta(t) = 2π × (R / 60) × t
r(theta) = r_start - groove_pitch × theta / (2π)
```

At 45 RPM, one revolution takes 1.333333 seconds. A 30-second clip occupies 22.5 revolutions. Each top-surface mesh point finds the nearest turn of the Archimedean centerline. Its radial distance from the centerline creates a printable V-like cross-section; its time on the centerline selects the band-limited sample that changes groove depth.

The top is a nonuniform polar grid: coarse over the label and edge, fine across the groove region. It joins an annular bottom, outer cylinder, and inward-facing spindle-hole cylinder with shared periodic boundaries. This yields one closed, watertight solid without boolean operations or self-intersecting swept tubes.

### Default calibration values

| Parameter | Default | Meaning |
|---|---:|---|
| Record diameter | 177.8 mm | standard 7-inch form |
| Center hole | 7.24 mm | nominal spindle opening |
| Thickness | 2.0 mm | solid base thickness |
| Groove region | 87.1–66.0 mm radius | available audio area |
| Groove pitch | 0.82 mm/revolution | avoids adjacent-groove overlap |
| Groove width | 0.36 mm | printable depression width |
| Groove depth | 0.22 mm | unmodulated depth |
| Signal amplitude | 0.075 mm | maximum depth modulation scale |
| Angular samples | 1368/revolution | mesh resolution, distinct from audio rate |
| Audio sample rate | 2050 Hz | physical XY-resolution reference |
| Band-pass | 200–950 Hz | suppresses unprintable excursions |

At the outer groove, `2π × 87 mm / 0.2 mm ≈ 2735` theoretical XY samples per revolution, or about 2050 samples/second at 45 RPM. The audio representation uses that rate. The present mesh uses a somewhat lighter angular grid and interpolates the processed waveform, keeping output near a few hundred thousand triangles.

## Printing starting point

- 0.2 mm nozzle
- fine layer height (start around 0.08 mm if the printer/material supports it)
- slow external/perimeter speeds
- rigid, level bed and well-calibrated extrusion
- print flat with the groove face upward
- disable aggressive mesh simplification in the slicer

These are starting assumptions, not validated guarantees. The Creality Ender-3 V3 KE or a similar FDM printer is the initial target class.

## API

```text
POST /api/jobs                         create normal/loop job
POST /api/jobs/{id}/audio?slot=0       upload MP3/WAV
POST /api/jobs/{id}/generate           start background processing
GET  /api/jobs/{id}                    status and debug result
GET  /api/jobs/{id}/preview            processed WAV
GET  /api/jobs/{id}/record.3mf         3MF download
GET  /api/jobs/{id}/record.stl         STL download
POST /api/debug/test-job               generate a developer test record
GET  /api/config                       inspect active defaults
```

Developer test request:

```bash
curl -X POST http://127.0.0.1:8000/api/debug/test-job \
  -H "Content-Type: application/json" \
  -d '{"signal":"sine440","duration_sec":1.0}'
```

Available signals: `sine440`, `sine500`, `sweep`, `silence`, `impulse`.

## Tests

```bash
pytest -q
```

The suite covers 30-second trimming, resampling, normalization, one-revolution loops, loop seam closure, 45 RPM math, spiral pitch, finite/watertight geometry, dimensions, binary STL, compressed 3MF, and multi-loop construction.

## Temporary files and privacy

Each job uses `temp/{uuid}/` for the source, decoded audio, preview, and models. Files are not permanent application data. On application startup, job directories older than six hours are deleted. For a continuously running production service, replace startup cleanup with a scheduled worker.

## Known experimental assumptions

- Vertical depth modulation is used; commercial records normally use lateral/stereo groove systems and standardized equalization.
- The groove cross-section is printer-oriented rather than standardized for a particular stylus profile.
- No RIAA pre-emphasis/de-emphasis is applied.
- The top surface angular mesh is lower resolution than the processed signal and interpolates it.
- 3MF export intentionally implements the small, standards-defined Core subset for one mesh instead of adding a platform-specific lib3mf binary dependency.
- Actual playback depends heavily on nozzle geometry, layer adhesion, material, slicer behavior, turntable tracking force, and stylus shape.
- Physical tests are still required to calibrate pitch, width, depth, amplitude, filtering, and mesh sampling.

Change values in `RecordConfig`, not the geometry equations, during calibration. Future record sizes, speeds, nozzle sizes, labels, text, and track layouts can build on the same explicit time-to-angle model.
