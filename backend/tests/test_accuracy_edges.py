from app.core.models import BirthData
from app.ephemeris.engine import EphemerisEngine
from app.services.location import resolve_location_query


def test_dst_transition_times_are_handled():
    engine = EphemerisEngine()

    # US DST spring-forward gap: 02:30 local is non-existent.
    non_existent = BirthData(
        date="2021-03-14",
        time="02:30:00",
        timezone="America/New_York",
        latitude=40.7128,
        longitude=-74.006,
        time_confidence="exact",
    )
    chart_gap = engine.compute_chart(non_existent)
    assert chart_gap.lagna is not None

    # US DST fall-back overlap: 01:30 local is ambiguous.
    ambiguous = BirthData(
        date="2021-11-07",
        time="01:30:00",
        timezone="America/New_York",
        latitude=40.7128,
        longitude=-74.006,
        time_confidence="exact",
    )
    chart_overlap = engine.compute_chart(ambiguous)
    assert chart_overlap.lagna is not None


def test_approximate_birth_time_sensitivity_window():
    engine = EphemerisEngine()
    baseline = BirthData(
        date="1990-01-15",
        time="06:30:00",
        timezone="Asia/Kolkata",
        latitude=28.6139,
        longitude=77.2090,
        time_confidence="approximate",
    )
    minus = baseline.model_copy(update={"time": "06:15:00"})
    plus = baseline.model_copy(update={"time": "06:45:00"})

    c0 = engine.compute_chart(baseline)
    c1 = engine.compute_chart(minus)
    c2 = engine.compute_chart(plus)

    # For approximate times, core signs should usually remain stable in a +/-15 minute window.
    assert c0.moon_sign == c1.moon_sign == c2.moon_sign
    assert c0.sun_sign == c1.sun_sign == c2.sun_sign


def test_location_geocoding_ambiguity_metadata():
    result = resolve_location_query("Springfield")
    assert result.timezone
    assert result.candidates_count is not None
    assert result.candidates_count >= 1
