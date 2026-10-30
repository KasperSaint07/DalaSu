"""Rebuild the DAL-30 dataset from daily weather/ET and immutable scene exports."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

if __package__:
    from .validation import parse_calendar_date, validate_output_paths
    from .ndvi import FEATURE_COLUMNS, attach_ndvi, load_observations
    from .build_daily import START_DATE, END_DATE, TRAIN_END, TEST_START
else:
    from validation import parse_calendar_date, validate_output_paths
    from ndvi import FEATURE_COLUMNS, attach_ndvi, load_observations
    from build_daily import START_DATE, END_DATE, TRAIN_END, TEST_START


def build_dataset(daily_input, ndvi_input, output_dir, site_id="US-Ne2", utc_offset_hours=-6):
    daily_input, ndvi_input, output_dir = map(Path, (daily_input, ndvi_input, output_dir))
    validate_output_paths(
        [daily_input, ndvi_input],
        [output_dir / name for name in ("daily.csv", "train.csv", "test.csv", "ndvi_build_report.json")],
    )
    with daily_input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    if "date" not in columns or not rows:
        raise ValueError("Daily input must contain dates and at least one row")
    for row in rows:
        parse_calendar_date(row["date"])
    if any(not START_DATE <= row["date"] <= END_DATE for row in rows):
        raise ValueError("Daily dates outside configured split period")
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError("Duplicate daily dates in single-site dataset")
    observations = load_observations(ndvi_input, utc_offset_hours=utc_offset_hours)
    if not any(obs.site_id == site_id for obs in observations):
        raise ValueError(f"No usable NDVI observations for {site_id}")
    joined = attach_ndvi(sorted(rows, key=lambda row: row["date"]), observations, site_id=site_id)
    columns = [c for c in columns if c not in FEATURE_COLUMNS] + FEATURE_COLUMNS
    splits = {"daily": joined, "train": [r for r in joined if r["date"] <= TRAIN_END],
              "test": [r for r in joined if r["date"] >= TEST_START]}
    if splits["train"] + splits["test"] != joined:
        raise ValueError("Temporal split must cover every daily row exactly once")
    ages = [int(r["ndvi_age_days"]) for r in joined if r["snapshot_date"]]
    report = {"policy_version": "DAL-30-v1", "site_id": site_id,
              "utc_offset_hours": utc_offset_hours,
              "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (daily_input, ndvi_input)},
              "rows": {name: len(values) for name, values in splits.items()},
              "missing_ndvi_rows": len(joined) - len(ages),
              "first_usable_snapshot": min(o.day for o in observations if o.site_id == site_id).isoformat(),
              "max_age_days": max(ages, default=None)}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, values in splits.items():
        with (output_dir / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(values)
    (output_dir / "ndvi_build_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-input", type=Path, default=Path("data/processed/daily.csv"))
    parser.add_argument("--ndvi-input", type=Path, default=Path("data/raw/ndvi_us-ne2_landsat_2015_2024.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ndvi"))
    parser.add_argument("--site-id", default="US-Ne2")
    parser.add_argument("--utc-offset-hours", type=float, default=-6,
                        help="Fixed station standard-time offset; US-Ne2: UTC-6, no DST")
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.daily_input, args.ndvi_input, args.output_dir,
                                   args.site_id, args.utc_offset_hours), indent=2))


if __name__ == "__main__":
    main()
