from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "external_crosscheck.json"
REQUIRED_EXPECTED_KEYS = {
    "lagna",
    "moon_sign",
    "sun_sign",
    "moon_nakshatra",
    "moon_nakshatra_pada",
    "current_mahadasha",
}


def load_fixture() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def write_fixture(data: list[dict[str, Any]]) -> None:
    FIXTURE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def validate_entry(entry: dict[str, Any]) -> None:
    required_top = {"id", "source_tool", "input", "expected"}
    missing_top = sorted(required_top - set(entry.keys()))
    if missing_top:
        raise ValueError(f"Entry '{entry.get('id', '<unknown>')}' missing top-level keys: {missing_top}")

    missing_expected = sorted(REQUIRED_EXPECTED_KEYS - set(entry["expected"].keys()))
    if missing_expected:
        raise ValueError(f"Entry '{entry['id']}' missing expected keys: {missing_expected}")

    if not isinstance(entry["expected"]["moon_nakshatra_pada"], int):
        raise ValueError(f"Entry '{entry['id']}' has non-integer moon_nakshatra_pada.")


def merge_updates(existing: list[dict[str, Any]], updates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {item["id"]: item for item in existing}
    changed: list[str] = []

    for update in updates:
        validate_entry(update)
        update["manual_verified"] = True

        prior = by_id.get(update["id"])
        if prior is None:
            by_id[update["id"]] = update
            changed.append(f"added:{update['id']}")
            continue

        merged = {
            **prior,
            "source_tool": update["source_tool"],
            "input": update["input"],
            "expected": update["expected"],
            "manual_verified": True,
        }
        by_id[update["id"]] = merged
        changed.append(f"updated:{update['id']}")

    ordered_ids = [item["id"] for item in existing]
    for new_id in by_id:
        if new_id not in ordered_ids:
            ordered_ids.append(new_id)
    merged_list = [by_id[item_id] for item_id in ordered_ids]

    return merged_list, changed


def parse_updates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("Update file must be a JSON object or array.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge externally-verified chart values into external_crosscheck fixture."
    )
    parser.add_argument(
        "--updates-file",
        required=True,
        help="Path to JSON file containing one or more externally verified fixture entries.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing fixture file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    updates_file = Path(args.updates_file).resolve()
    if not updates_file.exists():
        raise FileNotFoundError(f"Updates file not found: {updates_file}")

    existing = load_fixture()
    updates = parse_updates(updates_file)
    merged, changed = merge_updates(existing, updates)

    print(f"Fixture path: {FIXTURE_PATH}")
    print(f"Detected {len(changed)} change(s): {', '.join(changed) if changed else 'none'}")

    if args.dry_run:
        print("Dry run enabled. No files were written.")
        return

    write_fixture(merged)
    print("Fixture updated successfully.")


if __name__ == "__main__":
    main()
