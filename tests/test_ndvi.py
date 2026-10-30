"""Causality, provenance, station isolation and dataset integration checks."""
import csv
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ml.data.ndvi import Observation, FEATURE_COLUMNS, attach_ndvi, load_observations
from ml.data.build_ndvi import build_dataset

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/ndvi_us-ne2_landsat_2015_2024.csv"


def observation(day, value=0.5, site="A", image="scene", fraction=1):
    return Observation(site, date.fromisoformat(day), value, image,
                       datetime.fromisoformat(day + "T12:00:00+00:00"), fraction)


def test_backward_join_missing_same_day_gaps_and_future_invariance():
    rows = [{"date": d} for d in ["2022-12-01", "2022-12-31", "2023-01-01", "2023-07-01"]]
    obs = [observation("2022-12-31"), observation("2023-07-01", 0.8)]
    result = attach_ndvi(rows, obs, site_id="A")
    assert all(result[0][c] == "" for c in FEATURE_COLUMNS)
    assert [r["ndvi_age_days"] for r in result] == ["", "0", "1", "0"]
    assert result[2]["ndvi_last"] == "0.5"
    assert attach_ndvi(rows, obs + [observation("2024-01-01", 0.1)], site_id="A") == result
    assert attach_ndvi(rows[:3], obs[:1], site_id="A") == result[:3]
    assert "ndvi_last" not in rows[0]


def test_ties_order_site_isolation_and_empty_observations():
    obs = [observation("2020-01-01", 0.2, image="a", fraction=0.8),
           observation("2020-01-01", 0.4, image="b"),
           observation("2020-01-01", 0.6, image="c"),
           observation("2020-01-01", 0.9, site="B")]
    rows = [{"date": "2020-01-02", "site_id": s} for s in ["A", "B", "C"]]
    result = attach_ndvi(rows, obs)
    assert result == attach_ndvi(rows, list(reversed(obs)))
    assert [r["ndvi_last"] for r in result] == ["0.6", "0.9", ""]
    assert attach_ndvi(rows, [])[0]["ndvi_last"] == ""
    with pytest.raises(ValueError, match="conflicting"):
        attach_ndvi(rows, obs, site_id="A")


def write_scenes(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def scene(**updates):
    return {**dict(site_id="A", date="2020-01-02", acquired_at_utc="2020-01-02T02:00:00Z",
                   image_id="a", ndvi_mean="0.5", valid_fraction="1", min_valid_fraction="0.8",
                   is_usable="1"), **updates}


def test_adapter_quality_and_calendar(tmp_path):
    path = tmp_path / "scenes.csv"
    write_scenes(path, [scene(), scene(image_id="b", ndvi_mean="", is_usable="0", valid_fraction="0")])
    assert len(load_observations(path)) == 1
    assert load_observations(path, utc_offset_hours=-6)[0].day == date(2020, 1, 1)
    for update in [dict(ndvi_mean="nan"), dict(valid_fraction="0.2"),
                   dict(date="2020-01-03"), dict(ndvi_mean=""), dict(is_usable="2")]:
        write_scenes(path, [scene(**update)])
        with pytest.raises(ValueError):
            load_observations(path)
    write_scenes(path, [scene(), scene()])
    with pytest.raises(ValueError, match="duplicate"):
        load_observations(path)


def test_real_dataset_every_row_and_reproducibility(tmp_path):
    daily = ROOT / "data/processed/daily.csv"
    report = build_dataset(daily, RAW, tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert build_dataset(daily, RAW, tmp_path) == report
    assert first == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with daily.open() as handle:
        original = list(csv.DictReader(handle))
    with (tmp_path / "daily.csv").open() as handle:
        result = list(csv.DictReader(handle))
    assert len(result) == len(original)
    usable = load_observations(RAW, utc_offset_hours=-6)
    assert all(o.day == o.acquired_at.date() for o in usable)  # UTC and station dates agree here
    for old, new in zip(original, result):
        assert all(new[k] == v for k, v in old.items())
        candidates = [o for o in usable if o.day.isoformat() <= new["date"]]
        if not candidates:
            assert all(new[c] == "" for c in FEATURE_COLUMNS)
        else:
            latest = max(candidates, key=lambda o: (o.day, o.valid_fraction, o.acquired_at, o.image_id))
            assert new["snapshot_date"] == latest.day.isoformat() <= new["date"]
            assert new["ndvi_image_id"] == latest.image_id
            assert float(new["ndvi_last"]) == latest.value
            assert int(new["ndvi_age_days"]) == (date.fromisoformat(new["date"]) - latest.day).days
    with (tmp_path / "train.csv").open() as handle:
        train = list(csv.DictReader(handle))
    with (tmp_path / "test.csv").open() as handle:
        test = list(csv.DictReader(handle))
    assert train + test == result
    assert train[-1]["date"] < "2023-01-01" <= test[0]["date"]


def test_hourly_builder_cli(tmp_path):
    flux = tmp_path / "flux.csv"
    precip = tmp_path / "precip.csv"
    flux.write_text("TIMESTAMP_START,TIMESTAMP_END,LE_F_MDS,TA_F_MDS,RH,WS_F,NETRAD,PA_F\n"
                    "202001020000,202001030000,100,20,60,2,120,100\n")
    precip.write_text("TIMESTAMP_START,TIMESTAMP_END,P_PI_F_1_1_1\n"
                      "202001020000,202001030000,0\n")
    ndvi = tmp_path / "scenes.csv"
    write_scenes(ndvi, [scene(site_id="US-Ne2")])
    output = tmp_path / "out"
    subprocess.run([sys.executable, str(ROOT / "src/ml/data/build_daily.py"),
                    "--fluxnet-input", str(flux), "--precip-input", str(precip),
                    "--ndvi-input", str(ndvi), "--output-dir", str(output)], check=True)
    with (output / "daily.csv").open() as handle:
        row = next(csv.DictReader(handle))
    assert row["ndvi_age_days"] == "1"
    assert row["snapshot_date"] == "2020-01-01"


def test_long_gap_and_later_same_day_acquisition():
    early = observation("2020-01-01", 0.2)
    late = Observation("A", early.day, 0.7, "late", datetime(2020, 1, 1, 18, tzinfo=timezone.utc), 1)
    result = attach_ndvi([{"date": "2020-12-31"}], [late, early], site_id="A")[0]
    assert result["ndvi_age_days"] == "365"
    assert result["ndvi_image_id"] == "late"


def test_rejected_scene_does_not_replace_last(tmp_path):
    path = tmp_path / "scenes.csv"
    write_scenes(path, [scene(), scene(image_id="bad", date="2020-01-03",
                                      acquired_at_utc="2020-01-03T12:00:00Z",
                                      valid_fraction="0.1", is_usable="0")])
    row = attach_ndvi([{"date": "2020-01-04"}], load_observations(path), site_id="A")[0]
    assert row["snapshot_date"] == "2020-01-02"
    assert row["ndvi_age_days"] == "2"


def test_dataset_rejects_duplicate_dates_and_wrong_site(tmp_path):
    daily = tmp_path / "daily.csv"
    daily.write_text("date\n2020-01-01\n2020-01-01\n")
    with pytest.raises(ValueError, match="Duplicate"):
        build_dataset(daily, RAW, tmp_path / "out")
    daily.write_text("date\n2020-01-01\n")
    with pytest.raises(ValueError, match="No usable"):
        build_dataset(daily, RAW, tmp_path / "out", site_id="unknown")
    with pytest.raises(ValueError, match="differ"):
        build_dataset(daily, RAW, tmp_path)


@pytest.mark.parametrize("bad_date", ["2022-W52-7", "20230101", "2023-02-29"])
def test_noncanonical_dates_rejected_before_writing(tmp_path, bad_date):
    daily = tmp_path / "input.csv"
    daily.write_text(f"date\n{bad_date}\n")
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_dataset(daily, RAW, output)
    assert not output.exists()
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        attach_ndvi([{"date": bad_date}], [], site_id="A")


@pytest.mark.parametrize("name", ["daily.csv", "train.csv", "test.csv", "ndvi_build_report.json"])
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_ndvi_input_never_overwritten(tmp_path, name, alias):
    daily = tmp_path / "weather.csv"
    daily.write_text("date\n2020-01-01\n")
    output = tmp_path / "out"
    output.mkdir()
    target = output / name
    ndvi = target if alias == "direct" else tmp_path / "scenes.csv"
    ndvi.write_bytes(RAW.read_bytes())
    if alias == "symlink":
        target.symlink_to(ndvi)
    elif alias == "hardlink":
        target.hardlink_to(ndvi)
    before = ndvi.read_bytes()
    with pytest.raises(ValueError, match="conflicting paths"):
        build_dataset(daily, ndvi, output)
    assert ndvi.read_bytes() == before
    assert list(output.iterdir()) == [target]


def test_daily_input_alias_and_output_aliases_rejected(tmp_path):
    from ml.data.validation import validate_output_paths
    source = tmp_path / "source.csv"
    source.write_text("unchanged")
    alias = tmp_path / "alias.csv"
    alias.symlink_to(source)
    with pytest.raises(ValueError, match="conflicting paths"):
        validate_output_paths([source], [alias])
    with pytest.raises(ValueError, match="conflicting paths"):
        validate_output_paths([], [source, alias])
    assert source.read_text() == "unchanged"


@pytest.mark.parametrize("updates", [
    {"valid_fraction": float("nan")}, {"valid_fraction": 1.1},
    {"image_id": " "}, {"site_id": ""}, {"value": float("inf")},
    {"day": date(2020, 1, 2)}, {"acquired_at": datetime(2020, 1, 1, 12)},
])
def test_normalized_observation_contract(updates):
    values = dict(site_id="A", day=date(2020, 1, 1), value=0.5, image_id="a",
                  acquired_at=datetime(2020, 1, 1, 12, tzinfo=timezone.utc), valid_fraction=1)
    with pytest.raises(ValueError):
        Observation(**{**values, **updates})


def test_observation_calendar_offset_is_explicit():
    acquired = datetime(2020, 1, 2, 2, tzinfo=timezone.utc)
    obs = Observation("A", date(2020, 1, 1), 0.5, "a", acquired, 1, utc_offset_hours=-6)
    assert obs.day == date(2020, 1, 1)
    with pytest.raises(ValueError, match="calendar"):
        Observation("A", date(2020, 1, 1), 0.5, "a", acquired, 1)
