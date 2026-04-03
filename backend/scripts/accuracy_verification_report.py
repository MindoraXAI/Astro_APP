from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.models import BirthData
from app.ephemeris.engine import EphemerisEngine
from app.services.location import resolve_location_query

FIXTURE_DIR = ROOT / "tests" / "fixtures"
REPORT_PATH = ROOT / "reports" / "accuracy-verification-report.md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fixture_set(engine: EphemerisEngine, fixture_name: str) -> tuple[int, int, list[str]]:
    fixtures = load_json(FIXTURE_DIR / fixture_name)
    checks = 0
    passed = 0
    failures: list[str] = []

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
        observed = {
            "lagna": chart.lagna,
            "moon_sign": chart.moon_sign,
            "sun_sign": chart.sun_sign,
            "moon_nakshatra": chart.planets["Moon"].nakshatra,
            "moon_nakshatra_pada": chart.planets["Moon"].nakshatra_pada,
            "current_mahadasha": chart.current_dasha.mahadasha,
        }

        for key, expected_value in expected.items():
            if key not in observed:
                continue
            checks += 1
            if observed[key] == expected_value:
                passed += 1
            else:
                failures.append(
                    f"- {fixture['id']} ({fixture.get('source_tool', fixture_name)}): `{key}` expected `{expected_value}` got `{observed[key]}`"
                )

    return passed, checks, failures


def count_verified_external_fixtures() -> tuple[int, int]:
    fixtures = load_json(FIXTURE_DIR / "external_crosscheck.json")
    total = len(fixtures)
    verified = sum(1 for f in fixtures if f.get("manual_verified") is True)
    return verified, total


def time_sensitivity(engine: EphemerisEngine, birth: BirthData) -> dict[str, Any]:
    t0 = engine.compute_chart(birth)
    t_minus = birth.model_copy(update={"time": _shift_time(birth.time, -15)})
    t_plus = birth.model_copy(update={"time": _shift_time(birth.time, 15)})
    c_minus = engine.compute_chart(t_minus)
    c_plus = engine.compute_chart(t_plus)
    return {
        "baseline_time": birth.time,
        "minus_15": t_minus.time,
        "plus_15": t_plus.time,
        "moon_signs": [t0.moon_sign, c_minus.moon_sign, c_plus.moon_sign],
        "lagna_signs": [t0.lagna, c_minus.lagna, c_plus.lagna],
    }


def _shift_time(time_str: str, minutes: int) -> str:
    dt = datetime.strptime(f"2000-01-01 {time_str}", "%Y-%m-%d %H:%M:%S")
    shifted = dt + timedelta(minutes=minutes)
    return shifted.strftime("%H:%M:%S")


def run() -> None:
    engine = EphemerisEngine()
    generated_at = datetime.utcnow().isoformat()

    golden_passed, golden_checks, golden_failures = evaluate_fixture_set(engine, "golden_charts.json")
    external_passed, external_checks, external_failures = evaluate_fixture_set(engine, "external_crosscheck.json")
    verified_external, total_external = count_verified_external_fixtures()

    dst_cases: list[str] = []
    for date_str, time_str in [("2021-03-14", "02:30:00"), ("2021-11-07", "01:30:00")]:
        birth = BirthData(
            date=date_str,
            time=time_str,
            timezone="America/New_York",
            latitude=40.7128,
            longitude=-74.0060,
            time_confidence="exact",
        )
        chart = engine.compute_chart(birth)
        dst_cases.append(f"- {date_str} {time_str} America/New_York -> Lagna `{chart.lagna}`, Moon `{chart.moon_sign}`")

    sensitivity = time_sensitivity(
        engine,
        BirthData(
            date="1990-01-15",
            time="06:30:00",
            timezone="Asia/Kolkata",
            latitude=28.6139,
            longitude=77.2090,
            time_confidence="approximate",
        ),
    )

    ambiguous_queries = ["Springfield", "San Jose", "London"]
    geocode_lines: list[str] = []
    for query in ambiguous_queries:
        resolved = resolve_location_query(query)
        geocode_lines.append(
            f"- {query}: `{resolved.display_name}` | tz `{resolved.timezone}` | candidates `{resolved.candidates_count}` | confidence `{resolved.confidence}`"
        )

    golden_failures_block = "\n".join(golden_failures) if golden_failures else "- No mismatches."
    external_failures_block = "\n".join(external_failures) if external_failures else "- No mismatches."
    dst_block = "\n".join(dst_cases)
    geocode_block = "\n".join(geocode_lines)

    content = f"""# Accuracy Verification Report

Generated at: `{generated_at}` UTC

## 1) Golden Fixture Regression

- Checks passed: **{golden_passed}/{golden_checks}**

{golden_failures_block}

## 2) External Tool Cross-check

- Checks passed: **{external_passed}/{external_checks}**
- Fixture source file: `tests/fixtures/external_crosscheck.json`
- Manual external verification complete: **{verified_external}/{total_external}** fixtures

{external_failures_block}

## 3) Edge-case Validation

### Historical DST
{dst_block}

### Approximate Birth Time Sensitivity (+/-15 minutes)
- Baseline time: `{sensitivity["baseline_time"]}`
- Compared times: `{sensitivity["minus_15"]}`, `{sensitivity["baseline_time"]}`, `{sensitivity["plus_15"]}`
- Moon signs: `{sensitivity["moon_signs"]}`
- Lagna signs: `{sensitivity["lagna_signs"]}`

### Geocoding Ambiguity
{geocode_block}

## 4) Trust Summary

- Astronomical/rashi pipeline: validated against deterministic fixtures.
- External reference parity: automated via fixture-based comparison.
- Remaining production action: periodically refresh external fixtures from AstroSage/Jagannatha Hora exports.
"""

    REPORT_PATH.write_text(content, encoding="utf-8")
    print(str(REPORT_PATH))


if __name__ == "__main__":
    run()
