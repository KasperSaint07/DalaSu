#!/usr/bin/env python3
"""Build daily US-Ne2 evapotranspiration data from FLUXNET and BASE HR files.

The downloaded source CSV is treated as immutable. Missing values encoded as
-9999 are converted to None in memory. Daily means and extrema require at least
MIN_COVERAGE, while quantities integrated over the day require complete daily
coverage so missing intervals are never treated as zero.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


START_DATE = "2015-01-01"
END_DATE = "2024-12-31"
TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"
MIN_COVERAGE = 0.80
MIN_INTEGRATED_COVERAGE = 1.0
EXPECTED_DAY_SECONDS = 86_400.0
LATENT_HEAT_J_KG = 2.45e6
PRECIP_COLUMN = "P_PI_F_1_1_1"

SOURCE_COLUMNS = {
    "le": "LE_F_MDS",
    "ta": "TA_F_MDS",
    "rh": "RH",
    "ws": "WS_F",
    "rn": "NETRAD",
    "pa": "PA_F",
}

OUTPUT_COLUMNS = [
    "date",
    "et_obs_mm",
    "tmax_c",
    "tmin_c",
    "rh_mean_pct",
    "ws_ms",
    "rn_mj_m2_day",
    "p_kpa",
    "precip_mm",
    "doy",
]


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M")


def parse_value(value: str) -> float | None:
    if value == "" or value == "-9999":
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def weighted_mean(samples: list[tuple[float, float]]) -> float:
    total_seconds = sum(seconds for _, seconds in samples)
    return sum(value * seconds for value, seconds in samples) / total_seconds


def format_number(value: float) -> str:
    return f"{value:.6f}"


def load_daily_precipitation(source: Path) -> tuple[dict[str, float], int]:
    """Aggregate PI-filled BASE precipitation from hourly intervals to days."""

    days: dict[str, dict[str, object]] = defaultdict(
        lambda: {"intervals": set(), "values": []}
    )

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        # AmeriFlux BASE CSVs start with comment lines such as Site and Version.
        data_lines = (line for line in handle if not line.startswith("#"))
        reader = csv.DictReader(data_lines)
        required = {"TIMESTAMP_START", "TIMESTAMP_END", PRECIP_COLUMN}
        missing_columns = sorted(required.difference(reader.fieldnames or []))
        if missing_columns:
            raise ValueError(
                f"Missing BASE precipitation columns: {', '.join(missing_columns)}"
            )

        for row in reader:
            start = parse_timestamp(row["TIMESTAMP_START"])
            end = parse_timestamp(row["TIMESTAMP_END"])
            date = start.date().isoformat()
            if not START_DATE <= date <= END_DATE:
                continue

            seconds = (end - start).total_seconds()
            if seconds <= 0 or seconds > EXPECTED_DAY_SECONDS:
                raise ValueError(
                    f"Invalid BASE interval "
                    f"{row['TIMESTAMP_START']}–{row['TIMESTAMP_END']}"
                )

            day = days[date]
            intervals = day["intervals"]
            assert isinstance(intervals, set)
            interval = (row["TIMESTAMP_START"], row["TIMESTAMP_END"])
            if interval in intervals:
                raise ValueError(
                    f"Duplicate BASE interval {interval[0]}–{interval[1]}"
                )
            intervals.add(interval)
            value = parse_value(row[PRECIP_COLUMN])
            if value is not None:
                values = day["values"]
                assert isinstance(values, list)
                values.append((value, seconds))

    precipitation: dict[str, float] = {}
    rejected = 0
    for date, day in days.items():
        values = day["values"]
        assert isinstance(values, list)
        valid_seconds = sum(seconds for _, seconds in values)
        coverage = valid_seconds / EXPECTED_DAY_SECONDS
        if not math.isclose(coverage, MIN_INTEGRATED_COVERAGE):
            rejected += 1
            continue

        # BASE P_PI_F is already millimetres per dataset interval. Do not
        # multiply by interval duration; simply sum the hourly amounts.
        precipitation[date] = sum(value for value, _ in values)

    return precipitation, rejected


def build_daily(
    source: Path, precip_source: Path
) -> tuple[list[dict[str, str]], dict[str, int]]:
    precipitation, rejected_precip = load_daily_precipitation(precip_source)
    days: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "intervals": set(),
            "values": {key: [] for key in SOURCE_COLUMNS},
        }
    )

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"TIMESTAMP_START", "TIMESTAMP_END", *SOURCE_COLUMNS.values()}
        missing_columns = sorted(required.difference(reader.fieldnames or []))
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        for row in reader:
            start = parse_timestamp(row["TIMESTAMP_START"])
            end = parse_timestamp(row["TIMESTAMP_END"])
            date = start.date().isoformat()
            if not START_DATE <= date <= END_DATE:
                continue

            seconds = (end - start).total_seconds()
            if seconds <= 0 or seconds > EXPECTED_DAY_SECONDS:
                raise ValueError(
                    f"Invalid interval {row['TIMESTAMP_START']}–{row['TIMESTAMP_END']}"
                )

            day = days[date]
            intervals = day["intervals"]
            assert isinstance(intervals, set)
            interval = (row["TIMESTAMP_START"], row["TIMESTAMP_END"])
            if interval in intervals:
                raise ValueError(f"Duplicate interval {interval[0]}–{interval[1]}")
            intervals.add(interval)
            values = day["values"]
            assert isinstance(values, dict)
            for key, column in SOURCE_COLUMNS.items():
                value = parse_value(row[column])
                if value is not None:
                    values[key].append((value, seconds))

    output: list[dict[str, str]] = []
    rejected = 0
    rejected_by_variable = {key: 0 for key in SOURCE_COLUMNS}

    for date in sorted(days):
        day = days[date]
        values = day["values"]
        assert isinstance(values, dict)

        failed = []
        for key in SOURCE_COLUMNS:
            valid_seconds = sum(seconds for _, seconds in values[key])
            coverage = valid_seconds / EXPECTED_DAY_SECONDS
            required_coverage = (
                MIN_INTEGRATED_COVERAGE if key in {"le", "rn"} else MIN_COVERAGE
            )
            coverage_is_valid = (
                math.isclose(coverage, required_coverage)
                if required_coverage == MIN_INTEGRATED_COVERAGE
                else coverage >= required_coverage
            )
            if not coverage_is_valid:
                failed.append(key)
                rejected_by_variable[key] += 1

        if date not in precipitation:
            failed.append("precip")

        if failed:
            rejected += 1
            continue

        le_energy = sum(value * seconds for value, seconds in values["le"])
        rn_energy = sum(value * seconds for value, seconds in values["rn"])
        date_value = datetime.strptime(date, "%Y-%m-%d").date()

        output.append(
            {
                "date": date,
                "et_obs_mm": format_number(le_energy / LATENT_HEAT_J_KG),
                "tmax_c": format_number(max(value for value, _ in values["ta"])),
                "tmin_c": format_number(min(value for value, _ in values["ta"])),
                "rh_mean_pct": format_number(weighted_mean(values["rh"])),
                "ws_ms": format_number(weighted_mean(values["ws"])),
                "rn_mj_m2_day": format_number(rn_energy / 1e6),
                "p_kpa": format_number(weighted_mean(values["pa"])),
                "precip_mm": format_number(precipitation[date]),
                "doy": str(date_value.timetuple().tm_yday),
            }
        )

    stats = {
        "candidate_days": len(days),
        "retained_days": len(output),
        "rejected_days": rejected,
        "rejected_precip": rejected_precip,
        **{f"rejected_{key}": count for key, count in rejected_by_variable.items()},
    }
    return output, stats


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fluxnet-input",
        "--input",
        dest="fluxnet_input",
        type=Path,
        required=True,
        help="AmeriFlux FLUXNET FLUXMET_HR CSV",
    )
    parser.add_argument(
        "--precip-input",
        type=Path,
        required=True,
        help="AmeriFlux BASE_HR CSV containing P_PI_F_1_1_1",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    rows, stats = build_daily(args.fluxnet_input, args.precip_input)
    train = [row for row in rows if START_DATE <= row["date"] <= TRAIN_END]
    test = [row for row in rows if TEST_START <= row["date"] <= END_DATE]

    if len(train) + len(test) != len(rows):
        raise RuntimeError("Temporal split does not cover every daily record")
    if train and test and train[-1]["date"] >= test[0]["date"]:
        raise RuntimeError("Train/test date ranges overlap")

    write_csv(args.output_dir / "daily.csv", rows)
    write_csv(args.output_dir / "train.csv", train)
    write_csv(args.output_dir / "test.csv", test)

    print(f"candidate_days={stats['candidate_days']}")
    print(f"retained_days={stats['retained_days']}")
    print(f"rejected_days={stats['rejected_days']}")
    print(f"train_rows={len(train)}")
    print(f"test_rows={len(test)}")
    for key in SOURCE_COLUMNS:
        print(f"rejected_for_{key}={stats[f'rejected_{key}']}")
    print(f"rejected_for_precip={stats['rejected_precip']}")


if __name__ == "__main__":
    main()
