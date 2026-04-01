"""
AIS Test Suite — FastAPI Integration Tests
Tests: /health, /api/chart/compute, /api/chart/yogas
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.models import BirthData


@pytest.fixture
def test_birth():
    return {
        "date": "1990-01-15",
        "time": "06:30:00",
        "timezone": "Asia/Kolkata",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "time_confidence": "approximate"
    }


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "llm" in data


@pytest.mark.asyncio
async def test_chart_compute(test_birth):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chart/compute", json=test_birth)
    assert resp.status_code == 200
    data = resp.json()
    assert "lagna" in data
    assert "planets" in data
    assert "houses" in data
    assert "current_dasha" in data
    assert len(data["planets"]) == 9
    assert len(data["houses"]) == 12
    # Verify planet structure
    sun = data["planets"]["Sun"]
    assert "sign" in sun
    assert "house" in sun
    assert "dignity" in sun
    assert 0.0 <= sun["shadbala_strength"] <= 1.0


@pytest.mark.asyncio
async def test_chart_yogas(test_birth):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chart/yogas", json=test_birth)
    assert resp.status_code == 200
    data = resp.json()
    assert "lagna" in data
    assert "active_yogas" in data
    assert isinstance(data["active_yogas"], list)


@pytest.mark.asyncio
async def test_invalid_birth_data():
    invalid = {"date": "2090-13-45", "time": "25:99:00", "timezone": "Invalid/Zone",
               "latitude": 999, "longitude": 999}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chart/compute", json=invalid)
    assert resp.status_code in (422, 500)  # Validation or computation error
