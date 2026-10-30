"""Validated scene adapter and site-isolated, backward-only daily NDVI join."""
from __future__ import annotations

import csv
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if __package__:
    from .validation import parse_calendar_date
else:
    from validation import parse_calendar_date

FEATURE_COLUMNS = ["ndvi_last", "ndvi_age_days", "snapshot_date", "ndvi_image_id"]


@dataclass(frozen=True)
class Observation:
    site_id: str
    day: date
    value: float
    image_id: str
    acquired_at: datetime
    valid_fraction: float
    utc_offset_hours: float = 0

    def __post_init__(self):
        if not isinstance(self.site_id, str) or not self.site_id.strip():
            raise ValueError("Observation requires a nonempty site_id")
        if not isinstance(self.image_id, str) or not self.image_id.strip():
            raise ValueError("Observation requires a nonempty image_id")
        if not math.isfinite(self.value) or not -1 <= self.value <= 1:
            raise ValueError("Invalid observation NDVI")
        if not math.isfinite(self.valid_fraction) or not 0 <= self.valid_fraction <= 1:
            raise ValueError("Invalid observation coverage")
        if not isinstance(self.acquired_at, datetime) or self.acquired_at.utcoffset() is None:
            raise ValueError("Observation acquisition must be timezone-aware")
        calendar = timezone(timedelta(hours=self.utc_offset_hours))
        if type(self.day) is not date or self.day != self.acquired_at.astimezone(calendar).date():
            raise ValueError("Observation day disagrees with acquisition in its calendar")


def load_observations(path: Path, *, utc_offset_hours: float = 0) -> list[Observation]:
    """Adapt DAL-29 CSV; fixed offset supports station standard-time calendars."""
    calendar = timezone(timedelta(hours=utc_offset_hours))
    required = {"site_id", "date", "acquired_at_utc", "image_id", "ndvi_mean",
                "valid_fraction", "min_valid_fraction", "is_usable"}
    observations = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if required - set(reader.fieldnames or []):
            raise ValueError(f"Missing NDVI columns: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            identity = (row["site_id"], row["image_id"])
            if not all(identity) or identity in seen:
                raise ValueError(f"Empty or duplicate scene identity: {identity}")
            seen.add(identity)
            acquired = datetime.fromisoformat(row["acquired_at_utc"].replace("Z", "+00:00"))
            if acquired.tzinfo is None or acquired.utcoffset() != timedelta(0):
                raise ValueError("acquired_at_utc must have UTC timezone")
            if acquired.date() != parse_calendar_date(row["date"]):
                raise ValueError("Scene date disagrees with UTC acquisition timestamp")
            fraction, threshold = float(row["valid_fraction"]), float(row["min_valid_fraction"])
            if not (0 <= fraction <= 1 and 0 <= threshold <= 1):
                raise ValueError("Invalid coverage fraction or threshold")
            value = float(row["ndvi_mean"]) if row["ndvi_mean"] else None
            if value is not None and (not math.isfinite(value) or not -1 <= value <= 1):
                raise ValueError("Invalid NDVI value")
            if row["is_usable"] not in {"0", "1"}:
                raise ValueError("is_usable must be 0 or 1")
            if row["is_usable"] == "1":
                if value is None or fraction < threshold:
                    raise ValueError("Usable scene lacks valid NDVI or sufficient coverage")
                observations.append(Observation(row["site_id"], acquired.astimezone(calendar).date(),
                                                value, row["image_id"], acquired, fraction, utc_offset_hours))
    return observations


def attach_ndvi(rows: list[dict[str, str]], observations: list[Observation], *,
                site_id: str | None = None) -> list[dict[str, str]]:
    """Return new rows in input order. Each site has its own sorted observation index.

    For same-day scenes prefer coverage, then later acquisition, then greatest ID.
    No interpolation, expiry, imputation, or cross-site fallback is performed.
    """
    selected = {}
    for obs in observations:
        if not obs.site_id or not math.isfinite(obs.value) or not -1 <= obs.value <= 1:
            raise ValueError("Invalid normalized observation")
        key = (obs.site_id, obs.day)
        rank = lambda item: (item.valid_fraction, item.acquired_at, item.image_id)
        if key not in selected or rank(obs) > rank(selected[key]):
            selected[key] = obs
    by_site = {}
    for (site, day), obs in sorted(selected.items()):
        by_site.setdefault(site, []).append(obs)
    dates = {site: [obs.day for obs in values] for site, values in by_site.items()}
    output = []
    for row in rows:
        site = row.get("site_id") or site_id
        if not site or (site_id and row.get("site_id") and row["site_id"] != site_id):
            raise ValueError("Missing or conflicting daily site_id")
        day = parse_calendar_date(row["date"])
        index = bisect_right(dates.get(site, []), day) - 1
        features = dict.fromkeys(FEATURE_COLUMNS, "")
        if index >= 0:
            obs = by_site[site][index]
            features = {"ndvi_last": str(obs.value), "ndvi_age_days": str((day - obs.day).days),
                        "snapshot_date": obs.day.isoformat(), "ndvi_image_id": obs.image_id}
        output.append({**row, **features})
    return output
