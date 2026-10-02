from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    mode: Literal["normal", "loop"] = "normal"
    loop_count: int = Field(default=1, ge=1, le=4)


class TestJobCreate(BaseModel):
    signal: Literal["sine440", "sine500", "sweep", "silence", "impulse"] = "sine440"
    duration_sec: float = Field(default=1.0, gt=0.05, le=5.0)

