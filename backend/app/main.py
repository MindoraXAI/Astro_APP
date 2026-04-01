"""
AIS FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import requests

from app.api import chart, predict
from app.core.config import settings
from app.rag.weaviate_client import init_weaviate_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AIS starting up...")
    logger.info(f"  Environment : {settings.APP_ENV}")
    logger.info(f"  LLM         : {settings.active_llm_model} via {settings.active_llm_provider}")
    logger.info(f"  Embeddings  : {settings.NVIDIA_EMBED_MODEL} via NVIDIA NIM")
    logger.info(f"  Ayanamsa    : {'Lahiri (sidereal)' if settings.DEFAULT_AYANAMSA == 1 else settings.DEFAULT_AYANAMSA}")
    logger.info(f"  House Sys   : {'Whole Sign' if settings.DEFAULT_HOUSE_SYSTEM == 'W' else settings.DEFAULT_HOUSE_SYSTEM}")

    try:
        ready_url = f"{settings.WEAVIATE_URL.rstrip('/')}/v1/.well-known/ready"
        if requests.get(ready_url, timeout=1.5).ok:
            await init_weaviate_schema()
            logger.info("Weaviate schema ready")
        else:
            logger.warning("Weaviate readiness check failed, skipping schema init")
    except Exception as exc:
        logger.warning(f"Weaviate not reachable at startup, using local retrieval fallback: {exc}")

    yield

    logger.info("AIS shutting down...")


app = FastAPI(
    title="Astro Intelligence System (AIS)",
    description=(
        "A hybrid astrology platform combining Swiss Ephemeris precision, "
        "classical Vedic rule engines, retrieval, and optional LLM synthesis."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chart.router, prefix="/api/chart", tags=["Chart Computation"])
app.include_router(predict.router, prefix="/api/predict", tags=["Prediction"])

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "system": "Astro Intelligence System",
        "version": "2.0.0",
        "llm": settings.active_llm_model,
        "llm_provider": settings.active_llm_provider,
        "llm_synthesis_enabled": settings.ENABLE_LLM_SYNTHESIS,
        "embeddings": settings.NVIDIA_EMBED_MODEL,
        "frontend": "/app",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Astro Intelligence System API",
        "docs": "/docs",
        "health": "/health",
        "frontend": "/app",
    }
