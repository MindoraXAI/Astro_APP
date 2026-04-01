"""
AIS Chart API Routes
POST /api/chart/compute — compute full ChartState from birth data
GET  /api/chart/transits — current planetary positions
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.models import BirthData, ChartState, LocationResolutionResponse
from app.ephemeris.engine import get_engine
from app.services.location import resolve_birth_data, resolve_location_query

router = APIRouter()


@router.post("/compute", response_model=ChartState, summary="Compute Full Natal Chart")
async def compute_chart(birth_data: BirthData):
    """
    Compute a complete Vedic natal chart from birth data.

    Returns ChartState with:
    - All 9 planetary positions (sidereal, Lahiri ayanamsa)
    - Lagna, Moon sign, Sun sign
    - House placements (Whole Sign)
    - Nakshatra and Pada for each planet
    - Dignity and Shadbala strength scores
    - Vimshottari Dasha sequence
    - D9/D10 divisional chart lagnas
    - Current transit effects
    """
    try:
        engine = get_engine()
        chart = engine.compute_chart(resolve_birth_data(birth_data))
        return chart
    except Exception as e:
        logger.error(f"Chart computation error: {e}")
        raise HTTPException(status_code=500, detail=f"Chart computation failed: {str(e)}")


@router.post("/yogas", summary="Detect Yogas Only")
async def detect_yogas(birth_data: BirthData):
    """
    Compute chart and run yoga detection without full ALM synthesis.
    Useful for quick yoga analysis.
    """
    from app.symbolic.yoga_engine import get_yoga_engine
    try:
        engine = get_engine()
        chart = engine.compute_chart(resolve_birth_data(birth_data))
        yoga_engine = get_yoga_engine()
        yogas = yoga_engine.detect_yogas(chart)
        return {
            "lagna": chart.lagna,
            "moon_sign": chart.moon_sign,
            "total_yogas": len(yogas),
            "active_yogas": [y.model_dump() for y in yogas],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve-location", response_model=LocationResolutionResponse, summary="Resolve Birth Place")
async def resolve_location(place: str):
    try:
        return resolve_location_query(place)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
