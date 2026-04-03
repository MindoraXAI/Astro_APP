# Accuracy Verification Report

Generated at: `2026-04-01T13:22:18.586952` UTC

## 1) Golden Fixture Regression

- Checks passed: **18/18**

- No mismatches.

## 2) External Tool Cross-check

- Checks passed: **18/18**
- Fixture source file: `tests/fixtures/external_crosscheck.json`
- Manual external verification complete: **0/3** fixtures

- No mismatches.

## 3) Edge-case Validation

### Historical DST
- 2021-03-14 02:30:00 America/New_York -> Lagna `Sagittarius`, Moon `Pisces`
- 2021-11-07 01:30:00 America/New_York -> Lagna `Leo`, Moon `Scorpio`

### Approximate Birth Time Sensitivity (+/-15 minutes)
- Baseline time: `06:30:00`
- Compared times: `06:15:00`, `06:30:00`, `06:45:00`
- Moon signs: `['Leo', 'Leo', 'Leo']`
- Lagna signs: `['Sagittarius', 'Sagittarius', 'Sagittarius']`

### Geocoding Ambiguity
- Springfield: `Springfield, Sangamon County, Illinois, United States` | tz `America/Chicago` | candidates `5` | confidence `0.6`
- San Jose: `San Jose, Santa Clara County, California, United States` | tz `America/Los_Angeles` | candidates `5` | confidence `0.6`
- London: `Greater London, England, United Kingdom` | tz `Europe/London` | candidates `3` | confidence `0.8`

## 4) Trust Summary

- Astronomical/rashi pipeline: validated against deterministic fixtures.
- External reference parity: automated via fixture-based comparison.
- Remaining production action: periodically refresh external fixtures from AstroSage/Jagannatha Hora exports.
