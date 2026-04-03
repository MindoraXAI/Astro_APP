import json
from pathlib import Path

from app.core.models import BirthData
from app.ephemeris.engine import EphemerisEngine


def _load_fixture(name: str):
    fixture_path = Path(__file__).parent / "fixtures" / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_golden_chart_fixtures_regression():
    engine = EphemerisEngine()
    fixtures = _load_fixture("golden_charts.json")
    assert len(fixtures) >= 3

    for fixture in fixtures:
        birth = BirthData(
            date=fixture["input"]["date"],
            time=fixture["input"]["time"],
            timezone=fixture["input"]["timezone"],
            latitude=fixture["input"]["latitude"],
            longitude=fixture["input"]["longitude"],
            time_confidence="exact",
        )
        chart = engine.compute_chart(birth)
        expected = fixture["expected"]

        assert chart.lagna == expected["lagna"], fixture["id"]
        assert chart.moon_sign == expected["moon_sign"], fixture["id"]
        assert chart.sun_sign == expected["sun_sign"], fixture["id"]
        assert chart.planets["Moon"].nakshatra == expected["moon_nakshatra"], fixture["id"]
        assert chart.planets["Moon"].nakshatra_pada == expected["moon_nakshatra_pada"], fixture["id"]
        assert chart.planets["Sun"].nakshatra == expected["sun_nakshatra"], fixture["id"]
        assert chart.current_dasha.mahadasha == expected["current_mahadasha"], fixture["id"]
        assert chart.current_dasha.antardasha == expected["current_antardasha"], fixture["id"]
        assert chart.houses[1].sign == expected["house_1_sign"], fixture["id"]
        assert chart.houses[7].sign == expected["house_7_sign"], fixture["id"]
