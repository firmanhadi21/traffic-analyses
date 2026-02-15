"""
Shared utility functions for the traffic congestion pipeline.

Covers timestamp extraction, geometry hashing, temporal grouping,
day-type filtering, and file-range selection.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pytz

from trafficpipeline.config import TIMEZONE

# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"(\d{8})_(\d{6})")


def extract_timestamp(filepath: str | Path) -> datetime:
    """Extract a timezone-aware timestamp from a traffic GeoPackage filename.

    Expected pattern: ``*_YYYYMMDD_HHMMSS.gpkg``

    Returns
    -------
    datetime
        Localized to :data:`trafficpipeline.config.TIMEZONE` (GMT+7).
    """
    filename = Path(filepath).name
    match = _TS_RE.search(filename)
    if not match:
        raise ValueError(f"Cannot extract timestamp from '{filename}'")
    dt = datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y%m%d_%H%M%S")
    return pytz.timezone(TIMEZONE).localize(dt)


# ---------------------------------------------------------------------------
# Geometry hashing
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"-?\d+\.\d+")


def geometry_hash(geometry, precision: int = 6) -> str:
    """Return an MD5 hex-digest of *geometry* with coordinates rounded.

    Works for any Shapely geometry type (Point, LineString,
    MultiLineString, etc.).
    """
    from shapely.wkt import loads

    if isinstance(geometry, str):
        geometry = loads(geometry)

    def _round(m: re.Match) -> str:
        return f"{float(m.group()):.{precision}f}"

    rounded = _NUM_RE.sub(_round, geometry.wkt)
    return hashlib.md5(rounded.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Day-type helpers
# ---------------------------------------------------------------------------


def is_weekday(ts: datetime) -> bool:
    """True if *ts* is Monday-Friday."""
    return ts.weekday() < 5


def is_weekend(ts: datetime) -> bool:
    """True if *ts* is Saturday or Sunday."""
    return ts.weekday() >= 5


def matches_day_type(ts: datetime, day_type: str) -> bool:
    """Check whether *ts* matches *day_type* (``'all'``, ``'weekday'``, or ``'weekend'``)."""
    if day_type == "all":
        return True
    if day_type == "weekday":
        return is_weekday(ts)
    if day_type == "weekend":
        return is_weekend(ts)
    raise ValueError(f"Unknown day_type: {day_type!r}")


# ---------------------------------------------------------------------------
# Temporal grouping
# ---------------------------------------------------------------------------


def temporal_group_key(ts: datetime, grouping: str) -> str:
    """Classify *ts* into a temporal group label.

    Parameters
    ----------
    grouping : str
        One of ``'daily'``, ``'weekly'``, ``'monthly'``,
        ``'quarterly'``, ``'yearly'``, ``'all'``.
    """
    if grouping == "daily":
        return ts.strftime("%Y-%m-%d")
    if grouping == "weekly":
        iso = ts.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if grouping == "monthly":
        return f"{ts.year}-{ts.month:02d}"
    if grouping == "quarterly":
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    if grouping == "yearly":
        return str(ts.year)
    if grouping == "all":
        return "all_time"
    raise ValueError(f"Unknown grouping: {grouping!r}")


# ---------------------------------------------------------------------------
# File filtering
# ---------------------------------------------------------------------------


def filter_files_by_date_range(
    file_list: list[str | Path],
    start_date: str,
    end_date: str,
) -> list[Path]:
    """Keep only files whose embedded timestamp falls in [*start_date*, *end_date*].

    Dates are strings in ``YYYY-MM-DD`` format.
    """
    tz = pytz.timezone(TIMEZONE)
    start = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
    end = tz.localize(
        datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    )
    result: list[Path] = []
    for fp in file_list:
        try:
            ts = extract_timestamp(fp)
        except ValueError:
            continue
        if start <= ts <= end:
            result.append(Path(fp))
    return result


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def composite_osm_id(osmid, u, v, key) -> str:
    """Create a composite string ID from OSM edge attributes."""
    return f"{osmid}_{u}_{v}_{key}"


def synthetic_id(index: int, start: int = 9_000_000_000) -> str:
    """Create a synthetic ID for an unmatched traffic segment."""
    return f"SYNTHETIC_{start + index}"
