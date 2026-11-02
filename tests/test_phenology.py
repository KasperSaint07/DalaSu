"""No leakage, explicit evidence status, boundaries, coverage and determinism."""
import copy
import csv
import json
from datetime import date, datetime, timezone

import pytest

from ml.data.ndvi import Observation, load_observations
from ml.data.build_phenology import (
    DEFAULT_METADATA, DEFAULT_NDVI, DEFAULT_TEST, build, classify_proxy, compress_intervals,
    fit_thresholds, load_intervals, make_labels, read_csv, select_snapshots, validate_labels,
)


@pytest.fixture
def policy():
    return json.loads((DEFAULT_METADATA / "policy.json").read_text())


def observation(day, value, site="US-Ne2", image="scene"):
    return Observation(site, date.fromisoformat(day), value, image + day,
                       datetime.fromisoformat(day + "T18:00:00+00:00"), 1, -6)


def test_training_only_and_same_day_deduplication(policy):
    observations = [observation("2022-01-01", .1), observation("2022-06-01", .9),
                    observation("2024-06-01", .5), observation("2022-06-01", -.5, site="other")]
    # Lower-coverage duplicate must not inflate the training quantiles/sample count.
    observations.append(Observation("US-Ne2", date(2022, 6, 1), -.5, "duplicate",
                                    datetime(2022, 6, 1, 18, tzinfo=timezone.utc), .9, -6))
    fit = fit_thresholds(select_snapshots(observations, policy), policy)
    assert fit["n_training_snapshots"] == 2
    assert fit["low_ndvi"] == pytest.approx(.3)
    assert fit["high_ndvi"] == pytest.approx(.7)
    observations[-3] = observation("2024-06-01", -1)
    assert fit_thresholds(select_snapshots(observations, policy), policy) == fit


def test_future_training_cutoff_and_constant_training_rejected(policy):
    policy["train_end"] = "2023-01-01"
    with pytest.raises(ValueError, match="before 2023"):
        fit_thresholds([], policy)
    policy["train_end"] = "2022-12-31"
    with pytest.raises(ValueError, match="Degenerate"):
        fit_thresholds([{"date": "2022-01-01", "ndvi_last": "0.2"},
                        {"date": "2022-06-01", "ndvi_last": "0.2"}], policy)


@pytest.mark.parametrize("value,age,previous,gap,expected", [
    (.2, 0, None, 0, "proxy_low_vegetation"),
    (.8, 0, None, 0, "proxy_high_vegetation"),
    (.9, 32, None, 0, "proxy_high_vegetation"),
    (.9, 33, None, 0, "unknown"),
    (.5, 0, .3, 16, "proxy_greenup"),
    (.5, 0, .7, 16, "proxy_decline"),
    (.5, 0, .3, 33, "unknown"),
    (.5, 0, .5, 16, "unknown"),
    (.5, 0, None, 0, "unknown"),
])
def test_proxy_boundaries(policy, value, age, previous, gap, expected):
    from datetime import timedelta
    snapshot = date(2023, 6, 20)
    row = dict(snapshot_date=snapshot.isoformat(), ndvi_last=str(value), ndvi_age_days=str(age))
    prev = None if previous is None else dict(date=(snapshot-timedelta(days=gap)).isoformat(), ndvi_last=str(previous))
    stage, _, _ = classify_proxy(row, prev, {"low_ndvi": .2, "high_ndvi": .8}, policy)
    assert stage == expected


def test_no_future_scene_and_observed_precedence(policy):
    contexts = {"2023": dict(crop="maize", crop_status="inferred_rotation", crop_source="rotation")}
    observations = [observation("2023-05-01", .1), observation("2023-05-04", .9)]
    dates = ["2023-05-02", "2023-05-03", "2023-05-04"]
    labels = make_labels(dates, observations, policy, {"low_ndvi": .2, "high_ndvi": .8}, contexts, [])
    assert [r["stage"] for r in labels] == ["proxy_low_vegetation", "proxy_low_vegetation", "proxy_high_vegetation"]
    assert all(r["actual_stage"] == "unknown" for r in labels)
    interval = dict(start_date="2023-05-03", end_date="2023-05-03", crop="maize", stage="emergence",
                    source_id="record", evidence_locator="file/version/row")
    observed = make_labels(dates, observations, policy, {"low_ndvi": .2, "high_ndvi": .8}, contexts, [interval])
    assert observed[1]["status"] == "observed"
    assert observed[1]["stage"] == observed[1]["actual_stage"] == "emergence"
    assert observed[1]["proxy_stage"] == "proxy_low_vegetation"
    assert observed[0] == labels[0] and observed[2] == labels[2]
    invalid = copy.deepcopy(labels)
    invalid[0]["actual_stage"] = "emergence"
    with pytest.raises(ValueError, match="masquerade"):
        validate_labels(invalid, dates)


@pytest.mark.parametrize("failure", ["overlap", "reversed", "source", "status", "locator", "precision"])
def test_bad_observed_intervals_rejected(tmp_path, policy, failure):
    row = dict(start_date="2023-05-01", end_date="2023-05-10", crop="maize", stage="vegetative",
               source_id="record", evidence_locator="file/version/row", status="observed")
    rows = [row]
    if failure == "overlap":
        rows.append({**row, "start_date": "2023-05-10", "end_date": "2023-05-15"})
    elif failure == "reversed":
        row["end_date"] = "2023-04-30"
    elif failure == "source":
        row["source_id"] = "rotation"
    elif failure == "status":
        row["status"] = "approximate"
    elif failure == "locator":
        row["evidence_locator"] = ""
    else:
        row["start_date"] = "2023-05"
    path = tmp_path / "observed.csv"
    with path.open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        load_intervals(path, {"record": {"kind": "field_record"}, "rotation": {"kind": "site_description"}}, policy)


def test_complete_reproducible_outputs_and_et_independence(tmp_path, policy):
    out = tmp_path / "out"
    result = build(output_dir=out)
    assert result["calendar_days"] == 731
    assert result["test_days"] == 561
    assert result["actual_stage_analysis_ready"] is False
    daily, test = read_csv(out / "daily_labels.csv"), read_csv(out / "test_labels.csv")
    assert len({r["date"] for r in daily}) == 731
    assert [r["date"] for r in test] == [r["date"] for r in read_csv(DEFAULT_TEST)]
    assert all(r["actual_stage"] == "unknown" and r["status"] != "observed" for r in test)
    assert any(r["date"] == "2024-02-29" for r in daily)
    intervals = compress_intervals(daily)
    assert sum(r["calendar_days"] for r in intervals) == 731
    assert all(a["end_date"] < b["start_date"] for a, b in zip(intervals, intervals[1:]))
    snapshots = {p.name: p.read_bytes() for p in out.iterdir()}
    build(output_dir=out)
    assert snapshots == {p.name: p.read_bytes() for p in out.iterdir()}
    # A date-only manifest gives identical labels: ET and model errors are unnecessary.
    dates_path = tmp_path / "date_only.csv"
    dates_path.write_text("date\n" + "\n".join(r["date"] for r in test) + "\n")
    build(test_input=dates_path, output_dir=tmp_path / "date_only")
    assert (tmp_path / "date_only/test_labels.csv").read_bytes() == snapshots["test_labels.csv"]
    # Snapshot provenance must agree with the already built DAL-30 dataset.
    ndvi_rows = read_csv(DEFAULT_TEST.parent / "ndvi/test.csv")
    assert [r["snapshot_date"] for r in test] == [r["snapshot_date"] for r in ndvi_rows]
    assert [r["snapshot_image_id"] for r in test] == [r["ndvi_image_id"] for r in ndvi_rows]


def test_output_collision_rejected(tmp_path):
    target = tmp_path / "test_labels.csv"
    target.write_text(DEFAULT_TEST.read_text())
    original = target.read_bytes()
    with pytest.raises(ValueError, match="must differ"):
        build(test_input=target, output_dir=tmp_path)
    assert target.read_bytes() == original
