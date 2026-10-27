from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import build_analysis
from .elexon import ElexonAPIError, get_month_payloads

app = FastAPI(
    title="UK Wind Forecast Monitor API",
    description="Compare historical Elexon national wind forecasts with FUELHH actual generation.",
    version="1.0.0",
)

allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wind-forecast-monitor"}


@app.get("/analysis", tags=["analysis"])
@app.get("/api/analysis", tags=["analysis"])
def analysis(
    month: str = Query(default="2026-01", pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    horizon_hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    # The hiring assignment explicitly narrows the product to January 2026.
    if month != "2026-01":
        raise HTTPException(status_code=400, detail="This pilot is scoped to January 2026, as required by the challenge brief.")
    try:
        actual_payload, forecast_payload = get_month_payloads(month, max_horizon_hours=168)
        return build_analysis(actual_payload, forecast_payload, month=month, horizon_hours=horizon_hours)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ElexonAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # fail visibly; do not silently substitute fabricated numbers
        raise HTTPException(status_code=500, detail=f"Unexpected analysis failure: {type(exc).__name__}: {exc}") from exc


# In Docker/local production, the frontend build is served by FastAPI. On Vercel,
# deploy frontend/ and backend/ as separate projects and configure VITE_API_BASE_URL.
_project_root = Path(__file__).resolve().parents[2]
_static_dir = Path(os.getenv("FRONTEND_DIST_DIR", str(_project_root / "frontend" / "dist")))
if _static_dir.exists() and (_static_dir / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets") if (_static_dir / "assets").exists() else None

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        candidate = (_static_dir / full_path).resolve()
        try:
            candidate.relative_to(_static_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
