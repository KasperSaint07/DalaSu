"""Evidence-aware crop labels and backward-only NDVI proxies, independent of ET.

Run from repository root: PYTHONPATH=src python -m ml.data.build_phenology
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from .ndvi import attach_ndvi, load_observations
from .validation import parse_calendar_date, validate_output_paths

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METADATA = ROOT / "data/metadata/phenology"
DEFAULT_NDVI = ROOT / "data/raw/ndvi_us-ne2_landsat_2015_2024.csv"
DEFAULT_TEST = ROOT / "data/processed/test.csv"
DEFAULT_OUTPUT = ROOT / "data/processed/phenology"
OBSERVED_STAGES = {"emergence", "vegetative", "reproductive", "maturation", "off_season"}
PROXY_STAGES = {"proxy_low_vegetation", "proxy_high_vegetation", "proxy_greenup", "proxy_decline"}
FIELDS = ["date", "crop", "crop_status", "crop_source", "stage", "source", "status",
          "actual_stage", "actual_source", "evidence_locator", "proxy_stage", "proxy_reason",
          "snapshot_date", "snapshot_image_id", "ndvi_last", "ndvi_age_days",
          "previous_snapshot_date", "previous_image_id", "ndvi_change", "policy_version"]


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_policy(policy):
    for key in ("train_start", "train_end", "label_start", "label_end"):
        parse_calendar_date(policy[key])
    if not (policy["train_start"] <= policy["train_end"] <= "2022-12-31" <
            policy["label_start"] <= policy["label_end"]):
        raise ValueError("Training must end before 2023 and precede label dates")
    if not (0 <= policy["low_quantile"] < policy["high_quantile"] <= 1):
        raise ValueError("Invalid quantiles")
    if policy["quantile_method"] != "linear":
        raise ValueError("Only linear quantiles are supported")
    for key in ("max_snapshot_age_days", "max_trend_gap_days"):
        if type(policy[key]) is not int or policy[key] < 1:
            raise ValueError("Age/gap limits must be positive integers")
    if not 0 < policy["trend_delta_ndvi"] <= 2:
        raise ValueError("Invalid NDVI trend deadband")


def select_snapshots(observations, policy):
    """Reuse DAL-30 quality/tie-breaking rules, one selected scene per site date."""
    days = sorted({o.day.isoformat() for o in observations if o.site_id == policy["site_id"]})
    if not days:
        raise ValueError("No usable site observations")
    return attach_ndvi([{"date": d} for d in days], observations, site_id=policy["site_id"])


def fit_thresholds(snapshots, policy):
    validate_policy(policy)
    training = [s for s in snapshots if policy["train_start"] <= s["date"] <= policy["train_end"]]
    if len(training) < 2:
        raise ValueError("Insufficient training NDVI snapshots")
    values = [float(s["ndvi_last"]) for s in training]
    low, high = np.quantile(values, [policy["low_quantile"], policy["high_quantile"]], method="linear")
    if not np.isfinite([low, high]).all() or low >= high:
        raise ValueError("Degenerate training thresholds")
    return {"low_ndvi": float(low), "high_ndvi": float(high), "n_training_snapshots": len(training),
            "first_training_snapshot": training[0]["date"], "last_training_snapshot": training[-1]["date"],
            "training_snapshots_sha256": digest(training), "policy_sha256": digest(policy)}


def load_intervals(path, sources, policy):
    """Require explicit day-level intervals and locatable evidence; never infer boundaries."""
    required = {"start_date", "end_date", "crop", "stage", "source_id", "evidence_locator", "status"}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != required:
            raise ValueError("Invalid observed interval columns")
        intervals = sorted(list(reader), key=lambda r: r["start_date"])
    last_end = None
    for row in intervals:
        start, end = parse_calendar_date(row["start_date"]), parse_calendar_date(row["end_date"])
        if start > end or not policy["label_start"] <= row["start_date"] <= row["end_date"] <= policy["label_end"]:
            raise ValueError("Observed interval outside label window or reversed")
        if last_end is not None and start <= last_end:
            raise ValueError("Overlapping observed intervals")
        last_end = end
        if row["stage"] not in OBSERVED_STAGES or row["status"] != "observed":
            raise ValueError("Invalid observed stage/status")
        if not row["crop"].strip() or not row["evidence_locator"].strip():
            raise ValueError("Observed intervals require crop and evidence locator")
        if row["source_id"] not in sources or sources[row["source_id"]]["kind"] != "field_record":
            raise ValueError("Observed intervals require a registered field_record source")
    return intervals


def classify_proxy(row, previous, thresholds, policy):
    """No future scene, annual peak lookup, interpolation, ET or crop-date guessing."""
    if not row["snapshot_date"]:
        return "unknown", "no_snapshot", ""
    if int(row["ndvi_age_days"]) > policy["max_snapshot_age_days"]:
        return "unknown", "stale_snapshot", ""
    value = float(row["ndvi_last"])
    change = value - float(previous["ndvi_last"]) if previous else None
    delta = "" if change is None else str(change)
    if value <= thresholds["low_ndvi"]:
        return "proxy_low_vegetation", "low_training_quantile", delta
    if value >= thresholds["high_ndvi"]:
        return "proxy_high_vegetation", "high_training_quantile", delta
    if previous is None:
        return "unknown", "no_previous_snapshot", delta
    gap = (parse_calendar_date(row["snapshot_date"]) - parse_calendar_date(previous["date"])).days
    if not 0 < gap <= policy["max_trend_gap_days"]:
        return "unknown", "trend_gap_too_large", delta
    if change > policy["trend_delta_ndvi"]:
        return "proxy_greenup", "positive_ndvi_change", delta
    if change < -policy["trend_delta_ndvi"]:
        return "proxy_decline", "negative_ndvi_change", delta
    return "unknown", "ambiguous_midrange", delta


def make_labels(dates, observations, policy, thresholds, contexts, intervals):
    snapshots = select_snapshots(observations, policy)
    previous = {r["date"]: snapshots[i-1] if i else None for i, r in enumerate(snapshots)}
    joined = attach_ndvi([{"date": d} for d in dates], observations, site_id=policy["site_id"])
    rows = []
    for row in joined:
        context = contexts.get(row["date"][:4])
        if context is None:
            raise ValueError("Missing annual crop context")
        prev = previous.get(row["snapshot_date"])
        proxy, reason, delta = classify_proxy(row, prev, thresholds, policy)
        actual = next((r for r in intervals if r["start_date"] <= row["date"] <= r["end_date"]), None)
        rows.append(dict(date=row["date"], crop=actual["crop"] if actual else context["crop"],
                         crop_status="observed" if actual else context["crop_status"],
                         crop_source=actual["source_id"] if actual else context["crop_source"],
                         stage=actual["stage"] if actual else proxy,
                         source=actual["source_id"] if actual else ("landsat_dal29" if proxy != "unknown" else "evidence_audit"),
                         status="observed" if actual else ("approximate" if proxy != "unknown" else "unknown"),
                         actual_stage=actual["stage"] if actual else "unknown",
                         actual_source=actual["source_id"] if actual else "evidence_audit",
                         evidence_locator=actual["evidence_locator"] if actual else "docs/14-phenology-labels.md",
                         proxy_stage=proxy, proxy_reason=reason, snapshot_date=row["snapshot_date"],
                         snapshot_image_id=row["ndvi_image_id"], ndvi_last=row["ndvi_last"], ndvi_age_days=row["ndvi_age_days"],
                         previous_snapshot_date=prev["date"] if prev else "", previous_image_id=prev["ndvi_image_id"] if prev else "",
                         ndvi_change=delta, policy_version=policy["version"]))
    validate_labels(rows, dates)
    return rows


def validate_labels(rows, expected_dates):
    if [r["date"] for r in rows] != list(expected_dates) or len(set(expected_dates)) != len(expected_dates):
        raise ValueError("Labels must cover each requested date exactly once in order")
    for row in rows:
        day = parse_calendar_date(row["date"])
        if row["snapshot_date"]:
            snapshot = parse_calendar_date(row["snapshot_date"])
            if snapshot > day or (day - snapshot).days != int(row["ndvi_age_days"]):
                raise ValueError("Future or inconsistent NDVI snapshot")
            if row["previous_snapshot_date"] and row["previous_snapshot_date"] >= row["snapshot_date"]:
                raise ValueError("Previous NDVI snapshot must be strictly earlier")
        expected_status = "observed" if row["stage"] in OBSERVED_STAGES else "approximate" if row["stage"] in PROXY_STAGES else "unknown"
        if row["status"] != expected_status or (expected_status == "unknown" and row["stage"] != "unknown"):
            raise ValueError("Inconsistent stage/status")
        if row["status"] == "observed" and (row["actual_stage"] != row["stage"] or
                                            row["actual_source"] != row["source"]):
            raise ValueError("Inconsistent observed evidence")
        if row["status"] != "observed" and row["stage"] != row["proxy_stage"]:
            raise ValueError("Final non-observed stage must equal proxy stage")
        if row["status"] != "observed" and row["actual_stage"] != "unknown":
            raise ValueError("Proxy must not masquerade as actual stage")


def compress_intervals(rows):
    intervals = []
    keys = ["crop", "crop_status", "crop_source", "stage", "status", "source", "actual_stage",
            "actual_source", "evidence_locator", "proxy_stage", "proxy_reason"]
    for row in rows:
        same = intervals and all(intervals[-1][k] == row[k] for k in keys)
        adjacent = intervals and parse_calendar_date(intervals[-1]["end_date"]) + timedelta(days=1) == parse_calendar_date(row["date"])
        if same and adjacent:
            intervals[-1]["end_date"] = row["date"]
            intervals[-1]["calendar_days"] += 1
        else:
            intervals.append(dict(start_date=row["date"], end_date=row["date"], calendar_days=1,
                                  **{k: row[k] for k in keys}))
    return intervals


def coverage(rows):
    result = {}
    for year in sorted({r["date"][:4] for r in rows}):
        subset = [r for r in rows if r["date"].startswith(year)]
        count = lambda key: {v: sum(r[key] == v for r in subset) for v in sorted({r[key] for r in subset})}
        result[year] = {"n": len(subset), "status": count("status"), "stage": count("stage"),
                        "proxy_reason": count("proxy_reason"),
                        "actual_stage_unknown": sum(r["actual_stage"] == "unknown" for r in subset)}
    return result


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(metadata_dir=DEFAULT_METADATA, ndvi_input=DEFAULT_NDVI, test_input=DEFAULT_TEST, output_dir=DEFAULT_OUTPUT):
    metadata_dir, ndvi_input, test_input, output_dir = map(Path, (metadata_dir, ndvi_input, test_input, output_dir))
    inputs = [metadata_dir / name for name in ("policy.json", "sources.json", "crop_context.csv", "observed_intervals.csv")]
    inputs += [ndvi_input, test_input]
    names = ["daily_labels.csv", "test_labels.csv", "label_intervals.csv", "fitted_policy.json", "coverage.json", "coverage.md"]
    validate_output_paths(inputs, [output_dir / n for n in names])
    policy = json.loads(inputs[0].read_text())
    validate_policy(policy)
    sources = {r["id"]: r for r in json.loads(inputs[1].read_text())["sources"]}
    contexts_list = read_csv(inputs[2])
    contexts = {r["year"]: r for r in contexts_list}
    if len(contexts) != len(contexts_list) or any(r["crop_source"] not in sources for r in contexts_list):
        raise ValueError("Duplicate crop years or unknown crop source")
    intervals = load_intervals(inputs[3], sources, policy)
    observations = load_observations(ndvi_input, utc_offset_hours=policy["utc_offset_hours"])
    thresholds = fit_thresholds(select_snapshots(observations, policy), policy)
    # Read dates only; ET and prediction columns never enter the labelling rules.
    test_dates = [r["date"] for r in read_csv(test_input)]
    if len(test_dates) != 561 or test_dates != sorted(set(test_dates)):
        raise ValueError("Expected 561 unique sorted canonical test dates")
    first, last = map(parse_calendar_date, (policy["label_start"], policy["label_end"]))
    dates = [(first + timedelta(days=i)).isoformat() for i in range((last-first).days+1)]
    if not set(test_dates) <= set(dates):
        raise ValueError("Test dates outside label window")
    rows = make_labels(dates, observations, policy, thresholds, contexts, intervals)
    lookup = {r["date"]: r for r in rows}
    test = [lookup[d] for d in test_dates]
    validate_labels(test, test_dates)
    compressed = compress_intervals(rows)
    summary = {"policy_version": policy["version"], "calendar_days": len(rows), "test_days": len(test),
               "calendar_days_without_et_test_observation": len(rows)-len(test),
               "calendar_coverage": coverage(rows), "test_coverage": coverage(test),
               "observed_interval_count": len(intervals), "label_interval_count": len(compressed),
               "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
               "labelling_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "numpy_version": np.__version__,
               "actual_stage_analysis_ready": all(r["actual_stage"] != "unknown" for r in test)}
    lines = ["# Phenology label coverage — US-Ne2", "",
             "Actual agronomic stages and NDVI proxies are separate. An approximate label is not field validation.", "",
             f"Calendar coverage: {len(rows)} days. Canonical test coverage: {len(test)} dates. "
             f"The other {len(rows)-len(test)} calendar days have no retained ET test observation; no ET is filled.", "",
             "| Year | Test dates | Observed stages | NDVI proxies | Unknown final labels | Unknown actual stages |",
             "|---|---:|---:|---:|---:|---:|"]
    for year, c in summary["test_coverage"].items():
        lines.append(f'| {year} | {c["n"]} | {c["status"].get("observed",0)} | {c["status"].get("approximate",0)} | '
                     f'{c["status"].get("unknown",0)} | {c["actual_stage_unknown"]} |')
    lines += ["", "## Label counts on test dates", "", "| Year | Label | Count |", "|---|---|---:|"]
    for year, c in summary["test_coverage"].items():
        for stage, n in c["stage"].items():
            lines.append(f"| {year} | {stage} | {n} |")
    lines += ["", "## Missing or ambiguous proxy evidence", "", "| Year | Reason | Count |", "|---|---|---:|"]
    for year, c in summary["test_coverage"].items():
        for reason, n in c["proxy_reason"].items():
            lines.append(f"| {year} | {reason} | {n} |")
    lines += ["", "## Frozen rule fit", "", f'- Low threshold: {thresholds["low_ndvi"]:.8f}; high: {thresholds["high_ndvi"]:.8f}.',
              f'- Training: {thresholds["n_training_snapshots"]} unique selected snapshots, '
              f'{thresholds["first_training_snapshot"]} through {thresholds["last_training_snapshot"]}.',
              "- No test ET, model predictions or errors are used; no stage-error comparison is performed here.",
              "- Source audit and rule definitions: [method](../../../docs/14-phenology-labels.md).",
              "- Unknown runs and all non-overlapping calendar intervals: label_intervals.csv.",
              f'- Full actual-stage coverage: {summary["actual_stage_analysis_ready"]}. '
              "Do not claim actual-stage analysis is complete when evidence is missing.", ""]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / names[0], rows, FIELDS)
    write_csv(output_dir / names[1], test, FIELDS)
    write_csv(output_dir / names[2], compressed, list(compressed[0]))
    (output_dir / names[3]).write_text(json.dumps({"policy": policy, "fit": thresholds}, indent=2) + "\n")
    (output_dir / names[4]).write_text(json.dumps(summary, indent=2) + "\n")
    (output_dir / names[5]).write_text("\n".join(lines), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--ndvi-input", type=Path, default=DEFAULT_NDVI)
    parser.add_argument("--test-input", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.metadata_dir, args.ndvi_input, args.test_input, args.output_dir)
    print(json.dumps({k: result[k] for k in ("calendar_days", "test_days", "test_coverage", "actual_stage_analysis_ready")}, indent=2))


if __name__ == "__main__":
    main()
