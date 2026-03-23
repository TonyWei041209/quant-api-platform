"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from libs.core.logging import setup_logging
from apps.api.routers import health, instruments, research, execution, backtest


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
