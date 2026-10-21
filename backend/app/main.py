"""One container: FastAPI serves /api/* and the static Next.js export at / (SPEC §2)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.api import router  # noqa: E402

FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", ROOT / "frontend" / "out"))

app = FastAPI(title="Airport Investment Intelligence Agent")
app.include_router(router)

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
