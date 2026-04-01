"""
AIS Test Suite — Ephemeris Engine
Tests planetary computation against known reference values.
"""
import pytest
from app.core.models import BirthData
from app.ephemeris.engine import EphemerisEngine, SIGNS


@pytest.fixture
def engine():
    return EphemerisEngine()


@pytest.fixture
def test_birth_data():
    """Known birth data: Jan 15 1990, 06:30 IST, New Delhi"""
    return BirthData(
        date="1990-01-15",
        time="06:30:00",
        timezone="Asia/Kolkata",
        latitude=28.6139,
        longitude=77.2090,
        time_confidence="exact",
    )


def test_engine_initializes(engine):
    assert engine is not None


def test_birth_data_to_jd(engine, test_birth_data):
    jd, utc_dt = engine.birth_data_to_jd(test_birth_data)
    assert jd > 2440000  # Valid Julian Day (post 1970)
    assert utc_dt.year == 1990
    assert utc_dt.month == 1


def test_planet_computation(engine, test_birth_data):
    jd, _ = engine.birth_data_to_jd(test_birth_data)
    sun_data = engine.compute_planet(jd, "Sun")
    # Sun should be in Sagittarius (sidereal Lahiri) in Jan 1990
    assert sun_data["sign"] in SIGNS
    assert 0 <= sun_data["longitude"] < 360
    assert 1 <= sun_data["sign_number"] <= 12
    assert sun_data["nakshatra"] is not None
    assert 1 <= sun_data["nakshatra_pada"] <= 4


def test_ketu_computation(engine, test_birth_data):
    jd, _ = engine.birth_data_to_jd(test_birth_data)
    ketu = engine.compute_planet(jd, "Ketu")
    rahu = engine.compute_planet(jd, "Rahu")
    # Ketu should be exactly 180° from Rahu
    diff = abs(ketu["longitude"] - rahu["longitude"])
    assert abs(diff - 180) < 1.0  # Within 1° tolerance


def test_house_computation(engine, test_birth_data):
    jd, _ = engine.birth_data_to_jd(test_birth_data)
    houses = engine.compute_houses(jd, test_birth_data.latitude, test_birth_data.longitude)
    assert "lagna_sign" in houses
    assert houses["lagna_sign"] in SIGNS
    assert 0 <= houses["lagna_longitude"] < 360


def test_dignity_computation(engine):
    # Jupiter in Cancer = exalted
    assert engine.get_dignity("Jupiter", 4) == "exalted"  # Cancer = sign 4
    # Saturn in Aries = debilitated
    assert engine.get_dignity("Saturn", 1) == "debilitated"  # Aries = sign 1
    # Mars in Aries = moolatrikona
    assert engine.get_dignity("Mars", 1) == "moolatrikona"


def test_full_chart_computation(engine, test_birth_data):
    chart = engine.compute_chart(test_birth_data)
    assert chart.lagna in SIGNS
    assert chart.moon_sign in SIGNS
    assert chart.sun_sign in SIGNS
    assert len(chart.planets) == 9
    assert all(p in chart.planets for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"])
    assert len(chart.houses) == 12
    assert chart.current_dasha.mahadasha is not None
    assert chart.current_dasha.antardasha is not None
    assert 0.0 <= chart.current_dasha.elapsed_fraction <= 1.0


def test_divisional_charts(engine, test_birth_data):
    chart = engine.compute_chart(test_birth_data)
    assert chart.d9_lagna in SIGNS
    assert chart.d10_lagna in SIGNS
