# External Cross-check Updater CLI

Use this script to merge manually verified values from AstroSage or Jagannatha Hora into:

- `tests/fixtures/external_crosscheck.json`

## Command

```powershell
python scripts/update_external_crosscheck.py --updates-file "scripts/external-crosscheck-update.example.json" --dry-run
python scripts/update_external_crosscheck.py --updates-file "scripts/external-crosscheck-update.example.json"
```

## Expected update JSON shape

Each entry needs:

- `id`
- `source_tool`
- `input` with date/time/timezone/latitude/longitude
- `expected` with:
  - `lagna`
  - `moon_sign`
  - `sun_sign`
  - `moon_nakshatra`
  - `moon_nakshatra_pada` (integer)
  - `current_mahadasha`

The script automatically sets `manual_verified: true` for merged entries.
