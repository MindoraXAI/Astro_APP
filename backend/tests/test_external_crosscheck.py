import json
from pathlib import Path

from app.core.models import BirthData
from app.ephemeris.engine import EphemerisEngine


def test_external_crosscheck_multiple_real_charts():
    fixture_path = Path(__file__).parent / "fixtures" / "external_crosscheck.json"
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(fixtures) >= 3

    engine = EphemerisEngine()
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

        assert chart.lagna == expected["lagna"], f"{fixture['id']} lagna mismatch vs {fixture['source_tool']}"
        assert chart.moon_sign == expected["moon_sign"], f"{fixture['id']} moon mismatch vs {fixture['source_tool']}"
        assert chart.sun_sign == expected["sun_sign"], f"{fixture['id']} sun mismatch vs {fixture['source_tool']}"
        assert chart.planets["Moon"].nakshatra == expected["moon_nakshatra"], (
            f"{fixture['id']} moon nakshatra mismatch vs {fixture['source_tool']}"
        )
        assert chart.planets["Moon"].nakshatra_pada == expected["moon_nakshatra_pada"], (
            f"{fixture['id']} moon pada mismatch vs {fixture['source_tool']}"
        )
        assert chart.current_dasha.mahadasha == expected["current_mahadasha"], (
            f"{fixture['id']} mahadasha mismatch vs {fixture['source_tool']}"
        )
