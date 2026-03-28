"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from libs.core.logging import setup_logging
from apps.api.routers import health, instruments, research, execution, backtest, dq
from apps.api.routers import watchlist, presets, notes, daily, broker, portfolio, ai
from apps.api.auth import verify_firebase_token


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-react" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="Quant API Platform",
    description="API-first quantitative stock analysis and research platform",
    version="1.7.0",
    lifespan=lifespan,
)

# CORS — allow Firebase Hosting and local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://secret-medium-491502-n8.web.app",
        "https://secret-medium-491502-n8.firebaseapp.com",
        "http://localhost:3002",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Detect if running behind Firebase/proxy that sends /api/* paths
_raw_prefix = os.getenv("API_PREFIX", "")
API_PREFIX = _raw_prefix if _raw_prefix.startswith("/") else ""


def _pfx(sub: str) -> str:
    """Build route prefix: /api/instruments or /instruments."""
    return f"{API_PREFIX}{sub}" if API_PREFIX else sub


# Auth dependency for protected routes
from fastapi import Depends
_auth = [Depends(verify_firebase_token)]

# Register all routers — /health is public, everything else requires auth
if API_PREFIX:
    app.include_router(health.router, prefix=API_PREFIX)
else:
    app.include_router(health.router)
app.include_router(instruments.router, prefix=_pfx("/instruments"), tags=["instruments"], dependencies=_auth)
app.include_router(research.router, prefix=_pfx("/research"), tags=["research"], dependencies=_auth)
app.include_router(execution.router, prefix=_pfx("/execution"), tags=["execution"], dependencies=_auth)
app.include_router(backtest.router, prefix=_pfx("/backtest"), tags=["backtest"], dependencies=_auth)
app.include_router(dq.router, prefix=_pfx("/dq"), tags=["dq"], dependencies=_auth)
app.include_router(watchlist.router, prefix=_pfx("/watchlist"), tags=["watchlist"], dependencies=_auth)
app.include_router(presets.router, prefix=_pfx("/presets"), tags=["presets"], dependencies=_auth)
app.include_router(notes.router, prefix=_pfx("/notes"), tags=["notes"], dependencies=_auth)
app.include_router(daily.router, prefix=_pfx("/daily"), tags=["daily"], dependencies=_auth)
app.include_router(broker.router, prefix=_pfx("/broker"), tags=["broker"], dependencies=_auth)
app.include_router(portfolio.router, prefix=_pfx("/portfolio"), tags=["portfolio"], dependencies=_auth)
app.include_router(ai.router, prefix=_pfx("/ai"), tags=["ai"], dependencies=_auth)

# Serve frontend static files
if FRONTEND_DIR.exists():
    # Mount /assets for Vite build output (JS/CSS bundles)
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Mount root static files (favicon, icons, etc.)
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    # Serve favicon.svg directly
    @app.get("/favicon.svg", include_in_schema=False)
    async def serve_favicon():
        fav = FRONTEND_DIR / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav), media_type="image/svg+xml")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
