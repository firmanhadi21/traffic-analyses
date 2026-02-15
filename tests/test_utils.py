"""Tests for trafficpipeline.utils."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytz

from trafficpipeline.utils import (
    extract_timestamp,
    geometry_hash,
    is_weekday,
    is_weekend,
    temporal_group_key,
)


def test_extract_timestamp_semarang():
    p = Path("semarang_traffic_20240315_143022.gpkg")
    ts = extract_timestamp(p)
    assert ts.year == 2024
    assert ts.month == 3
    assert ts.day == 15
    assert ts.hour == 14
    assert ts.minute == 30
    assert ts.second == 22
    assert ts.tzinfo is not None


def test_extract_timestamp_bandung():
    p = Path("bandung_traffic_20241201_080000.gpkg")
    ts = extract_timestamp(p)
    assert ts.month == 12
    assert ts.hour == 8


def test_extract_timestamp_invalid():
    import pytest
    with pytest.raises(ValueError):
        extract_timestamp(Path("random_file.gpkg"))


def test_geometry_hash_deterministic():
    # Use a mock WKT-like object
    class FakeGeom:
        def wkt(self):
            return "POINT (110.5 -7.0)"
        @property
        def wkt(self):
            return "POINT (110.5 -7.0)"

    g = FakeGeom()
    h1 = geometry_hash(g)
    h2 = geometry_hash(g)
    assert h1 == h2
    assert len(h1) == 32  # MD5 hex digest length


def test_is_weekday_weekend():
    tz = pytz.timezone("Asia/Bangkok")
    # 2024-03-18 is a Monday
    dt = datetime(2024, 3, 18, 12, 0, tzinfo=tz)
    assert is_weekday(dt) is True
    assert is_weekend(dt) is False
    # 2024-03-16 is a Saturday
    dt_sat = datetime(2024, 3, 16, 12, 0, tzinfo=tz)
    assert is_weekday(dt_sat) is False
    assert is_weekend(dt_sat) is True


def test_temporal_group_key_daily():
    tz = pytz.timezone("Asia/Bangkok")
    dt = datetime(2024, 3, 18, 12, 0, tzinfo=tz)
    assert temporal_group_key(dt, "daily") == "2024-03-18"


def test_temporal_group_key_monthly():
    tz = pytz.timezone("Asia/Bangkok")
    dt = datetime(2024, 3, 18, 12, 0, tzinfo=tz)
    assert temporal_group_key(dt, "monthly") == "2024-03"
