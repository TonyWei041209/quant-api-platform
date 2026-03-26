"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from libs.core.logging import setup_logging
from apps.api.routers import health, instruments, research, execution, backtest, dq
from apps.api.routers import watchlist, presets, notes, daily, broker, portfolio


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-react" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="Quant API Platform",
    description="API-first quantitative stock analysis and research platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(instruments.router, prefix="/instruments", tags=["instruments"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(execution.router, prefix="/execution", tags=["execution"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(dq.router, prefix="/dq", tags=["dq"])
app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
app.include_router(presets.router, prefix="/presets", tags=["presets"])
app.include_router(notes.router, prefix="/notes", tags=["notes"])
app.include_router(daily.router, prefix="/daily", tags=["daily"])
app.include_router(broker.router, prefix="/broker", tags=["broker"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])

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
