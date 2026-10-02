from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.jobs import STORE
from app.api.routes import router
from app.config import PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = PROJECT_ROOT / "app" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    STORE.cleanup()
    yield


app = FastAPI(title="Record Forge", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}

