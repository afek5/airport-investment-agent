"""HTTP routes (SPEC §7). P0: /api/health and /api/chat (no guards yet; P1-C adds them)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

from app import snapshot
from app.agent import USAGE_LIMITS, agent

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    m = snapshot.manifest()
    return {
        "status": "ok",
        "snapshot": {
            "built_at": m.get("built_at"),
            "tables": {k: {"rows": v.get("rows"), "as_of": v.get("as_of"), "window": v.get("window")}
                       for k, v in m.get("tables", {}).items()},
        },
        "db": "not configured",
    }


@router.post("/chat")
async def chat(request: Request) -> Response:
    return await VercelAIAdapter.dispatch_request(request, agent=agent, sdk_version=7, usage_limits=USAGE_LIMITS)
