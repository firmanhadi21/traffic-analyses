"""
Utility functions for traffic data processing.
Includes timestamp extraction, geometry hashing, and temporal grouping.
"""

import re
import hashlib
from datetime import datetime
from pathlib import Path
from shapely.geometry import shape
from shapely.wkt import loads
import pytz

from config import TIMEZONE


def extract_timestamp_from_filename(filepath):
    """
    Extract timestamp from traffic data filename.

    Filename format: {city}_traffic_YYYYMMDD_HHMMSS.gpkg
    Example: semarang_traffic_20250115_143022.gpkg

    Args:
        filepath: Path or string of the filename

    Returns:
        datetime object in Asia/Bangkok timezone (GMT+7)
    """
    filename = Path(filepath).name

    # Pattern: YYYYMMDD_HHMMSS
    pattern = r'(\d{8})_(\d{6})'
    match = re.search(pattern, filename)

    if not match:
        raise ValueError(f"Could not extract timestamp from filename: {filename}")

    date_str = match.group(1)  # YYYYMMDD
    time_str = match.group(2)  # HHMMSS

    # Parse datetime
    dt_str = f"{date_str}_{time_str}"
    dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S")

    # Localize to Indonesian timezone
    tz = pytz.timezone(TIMEZONE)
    dt_localized = tz.localize(dt)

    return dt_localized


def create_geometry_hash(geometry, precision=6):
    """
    Create MD5 hash of geometry for consistent matching.

    Rounds coordinates to specified precision before hashing to handle
    minor floating point differences. Works with all geometry types including
    MultiLineString, LineString, etc.

    Args:
        geometry: Shapely geometry object or WKT string
        precision: Number of decimal places (default 6 = ~11cm precision)

    Returns:
        MD5 hash string (32 characters)
    """
    # Convert to shapely geometry if needed
    if isinstance(geometry, str):
        geom = loads(geometry)
    else:
        geom = geometry

    # Use WKT with rounded coordinates for consistent hashing
    # This works for all geometry types (Point, LineString, MultiLineString, etc.)
    from shapely import wkt

    # Get WKT representation
    wkt_str = geom.wkt

    # Parse and round coordinates
    # For simplicity, round the WKT string numbers directly
    import re

    def round_number(match):
        """Round a number in WKT string to specified precision."""
        num = float(match.group(0))
        return f"{num:.{precision}f}"

    # Replace all numbers in WKT with rounded versions
    # Pattern matches floating point numbers
    rounded_wkt = re.sub(r'-?\d+\.\d+', round_number, wkt_str)

    # Generate hash
    return hashlib.md5(rounded_wkt.encode()).hexdigest()


def parse_time_period(period_str):
    """
    Parse time period string into components.

    Format: "name:start_hour-end_hour"
    Example: "morning_peak:6-9" -> ("morning_peak", 6, 9)

    Args:
        period_str: Time period string

    Returns:
        Tuple of (name, start_hour, end_hour)
    """
    try:
        name, hours = period_str.split(':')
        start, end = hours.split('-')
        start_hour = int(start)
        end_hour = int(end)

        if not (0 <= start_hour < 24 and 0 <= end_hour <= 24):
            raise ValueError("Hours must be between 0-24")
        if start_hour >= end_hour:
            raise ValueError("Start hour must be less than end hour")

        return name, start_hour, end_hour
    except Exception as e:
        raise ValueError(f"Invalid time period format '{period_str}'. "
                         f"Expected 'name:start-end' (e.g., 'morning_peak:6-9'). Error: {e}")


def in_time_period(timestamp, start_hour, end_hour):
    """
    Check if timestamp falls within specified time period.

    Args:
        timestamp: datetime object
        start_hour: Start hour (0-23)
        end_hour: End hour (1-24)

    Returns:
        Boolean
    """
    hour = timestamp.hour
    return start_hour <= hour < end_hour


def is_weekday(timestamp):
    """
    Check if timestamp is a weekday (Monday-Friday).

    Args:
        timestamp: datetime object

    Returns:
        Boolean
    """
    return timestamp.weekday() < 5  # 0=Monday, 4=Friday


def is_weekend(timestamp):
    """
    Check if timestamp is a weekend (Saturday-Sunday).

    Args:
        timestamp: datetime object

    Returns:
        Boolean
    """
    return timestamp.weekday() >= 5  # 5=Saturday, 6=Sunday


def matches_day_type(timestamp, day_type):
    """
    Check if timestamp matches the specified day type filter.

    Args:
        timestamp: datetime object
        day_type: One of 'all', 'weekday', 'weekend'

    Returns:
        Boolean
    """
    if day_type == 'all':
        return True
    elif day_type == 'weekday':
        return is_weekday(timestamp)
    elif day_type == 'weekend':
        return is_weekend(timestamp)
    else:
        raise ValueError(f"Unknown day type: {day_type}")


def get_temporal_group(timestamp, grouping):
    """
    Classify timestamp into temporal group.

    Args:
        timestamp: datetime object
        grouping: One of 'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all'

    Returns:
        String identifier for the temporal group
    """
    if grouping == 'daily':
        return timestamp.strftime('%Y-%m-%d')
    elif grouping == 'weekly':
        # ISO week format: YYYY-Www
        iso_cal = timestamp.isocalendar()
        return f"{iso_cal[0]}-W{iso_cal[1]:02d}"
    elif grouping == 'monthly':
        return f"{timestamp.year}-{timestamp.month:02d}"
    elif grouping == 'quarterly':
        quarter = (timestamp.month - 1) // 3 + 1
        return f"{timestamp.year}-Q{quarter}"
    elif grouping == 'yearly':
        return f"{timestamp.year}"
    elif grouping == 'all':
        return 'all_time'
    else:
        raise ValueError(f"Unknown temporal grouping: {grouping}")


def filter_files_by_date_range(file_list, start_date, end_date):
    """
    Filter file list by date range based on filename timestamps.

    Args:
        file_list: List of file paths
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)

    Returns:
        Filtered list of file paths
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # Localize to Indonesian timezone
    tz = pytz.timezone(TIMEZONE)
    start_dt = tz.localize(start_dt)
    end_dt = tz.localize(end_dt.replace(hour=23, minute=59, second=59))

    filtered = []
    for filepath in file_list:
        try:
            timestamp = extract_timestamp_from_filename(filepath)
            if start_dt <= timestamp <= end_dt:
                filtered.append(filepath)
        except ValueError:
            # Skip files that don't match expected pattern
            continue

    return filtered


def create_osm_composite_id(osmid, u, v, key):
    """
    Create composite OSM ID from edge attributes.

    Args:
        osmid: OSM way ID
        u: Start node ID
        v: End node ID
        key: Edge key (for parallel edges)

    Returns:
        Composite ID string
    """
    return f"{osmid}_{u}_{v}_{key}"


def create_synthetic_id(index, start_id=9000000000):
    """
    Create synthetic ID for unmatched segments.

    Args:
        index: Sequential index
        start_id: Starting ID value

    Returns:
        Synthetic ID string
    """
    return f"SYNTHETIC_{start_id + index}"
