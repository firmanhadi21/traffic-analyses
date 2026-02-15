"""
Centralized configuration for the traffic congestion pipeline.

All city definitions, time periods, directory conventions, and shared
constants live here so that every other module imports from one place.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Base directories (resolved relative to the *working directory*, not the
# package install location, so that data paths work for end-users).
# Users can override DATA_DIR before importing analysis modules.
# ---------------------------------------------------------------------------
DATA_DIR = Path(".")

# ---------------------------------------------------------------------------
# City definitions
# ---------------------------------------------------------------------------
CITIES = {
    "smg": {
        "name": "Semarang",
        # OSMnx 2.0 bbox format: (west, south, east, north)
        "bbox": (110.227, -7.105, 110.528, -6.919),
        "bbox_dict": {
            "west": 110.227,
            "south": -7.105,
            "east": 110.528,
            "north": -6.919,
        },
        "traffic_data_dir": "traffic_data_smg",
        "traffic_output_dir": "traffic_smg_output",
        "filename_pattern": "semarang_traffic_*.gpkg",
        "expected_segments": 1076,
        "color": "#2ecc71",
    },
    "bdg": {
        "name": "Bandung",
        "bbox": (107.4688, -7.0848, 107.8261, -6.8294),
        "bbox_dict": {
            "west": 107.4688,
            "south": -7.0848,
            "east": 107.8261,
            "north": -6.8294,
        },
        "traffic_data_dir": "traffic_data_bdg",
        "traffic_output_dir": "traffic_bdg_output",
        "filename_pattern": "bandung_traffic_*.gpkg",
        "expected_segments": 3063,
        "color": "#3498db",
    },
    "jkt": {
        "name": "Jakarta",
        "bbox": (106.6036, -6.4096, 107.11, -6.0911),
        "bbox_dict": {
            "west": 106.6036,
            "south": -6.4096,
            "east": 107.11,
            "north": -6.0911,
        },
        "traffic_data_dir": "traffic_data_jkt",
        "traffic_output_dir": "traffic_jkt_output",
        "filename_pattern": "jakarta_traffic_*.gpkg",
        "expected_segments": 14609,
        "color": "#e74c3c",
    },
}

# ---------------------------------------------------------------------------
# Time periods  (8 disjoint bins covering 24 h)
# ---------------------------------------------------------------------------
TIME_PERIODS = [
    "night",
    "morning_peak",
    "morning_offpeak",
    "lunch_hours",
    "afternoon_offpeak",
    "evening_peak",
    "evening_offpeak",
    "late_night",
]

TIME_PERIOD_HOURS = {
    "night": (0, 6),
    "morning_peak": (6, 9),
    "morning_offpeak": (9, 12),
    "lunch_hours": (12, 14),
    "afternoon_offpeak": (14, 16),
    "evening_peak": (16, 19),
    "evening_offpeak": (19, 22),
    "late_night": (22, 24),
}

TIME_PERIOD_LABELS = {
    "night": "Night\n(00-06)",
    "morning_peak": "Morning\nPeak (06-09)",
    "morning_offpeak": "Morning\nOff-peak (09-12)",
    "lunch_hours": "Lunch\n(12-14)",
    "afternoon_offpeak": "Afternoon\nOff-peak (14-16)",
    "evening_peak": "Evening\nPeak (16-19)",
    "evening_offpeak": "Evening\nOff-peak (19-22)",
    "late_night": "Late Night\n(22-00)",
}

# ---------------------------------------------------------------------------
# Traffic metrics available in raw GeoPackage snapshots
# ---------------------------------------------------------------------------
TRAFFIC_METRICS = ["jam_factor", "speed", "free_flow"]

# ---------------------------------------------------------------------------
# Spatial / matching parameters
# ---------------------------------------------------------------------------
MATCHING_PARAMS = {
    "nearest_neighbor_threshold_m": 50,
    "synthetic_id_start": 9000000000,
    "geometry_precision": 6,
    "target_match_rate": 0.95,
    "max_mean_distance_m": 20,
}

OSM_PARAMS = {
    "network_type": "drive",
    "cache_days": 30,
}

# ---------------------------------------------------------------------------
# POI categories (used by poi module)
# ---------------------------------------------------------------------------
POI_CATEGORIES = {
    "commercial": {
        "tags": {"shop": True},
        "description": "Shops and retail",
    },
    "offices": {
        "tags": {"office": True},
        "description": "Offices and workplaces",
    },
    "education": {
        "tags": {"amenity": ["school", "university", "college", "kindergarten"]},
        "description": "Schools and educational facilities",
    },
    "healthcare": {
        "tags": {"amenity": ["hospital", "clinic", "doctors", "pharmacy"]},
        "description": "Healthcare facilities",
    },
    "food": {
        "tags": {"amenity": ["restaurant", "cafe", "fast_food", "food_court"]},
        "description": "Restaurants and food outlets",
    },
    "transport": {
        "tags": {"amenity": ["bus_station", "fuel"], "public_transport": True},
        "description": "Transport hubs",
    },
}

# ---------------------------------------------------------------------------
# Road hierarchy (used by bottleneck module)
# ---------------------------------------------------------------------------
ROAD_HIERARCHY = {
    "motorway": 6, "motorway_link": 5.5,
    "trunk": 5, "trunk_link": 4.5,
    "primary": 4, "primary_link": 3.5,
    "secondary": 3, "secondary_link": 2.5,
    "tertiary": 2, "tertiary_link": 1.5,
    "residential": 1, "living_street": 0.5,
    "unclassified": 1, "service": 0.5,
}

DEFAULT_LANES = {
    "motorway": 3, "motorway_link": 2,
    "trunk": 2, "trunk_link": 1,
    "primary": 2, "primary_link": 1,
    "secondary": 2, "secondary_link": 1,
    "tertiary": 1, "tertiary_link": 1,
    "residential": 1, "living_street": 1,
    "unclassified": 1, "service": 1,
}

HERE_MONITORED_TYPES = {
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
}

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------
CRS = "EPSG:4326"
TIMEZONE = "Asia/Bangkok"  # GMT+7; matches Indonesian WIB

# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_city(code: str) -> dict:
    """Return city dict or raise ``KeyError`` with a helpful message."""
    if code not in CITIES:
        valid = ", ".join(sorted(CITIES))
        raise KeyError(f"Unknown city code '{code}'. Choose from: {valid}")
    return CITIES[code]


def get_time_period(hour: int) -> str:
    """Map an hour (0-23) to its time-period name."""
    for name, (start, end) in TIME_PERIOD_HOURS.items():
        if start <= hour < end:
            return name
    raise ValueError(f"Hour {hour} does not fall in any time period")


def traffic_data_path(city_code: str) -> Path:
    """Absolute path to raw traffic snapshots for *city_code*."""
    return DATA_DIR / CITIES[city_code]["traffic_data_dir"]


def traffic_output_path(city_code: str) -> Path:
    """Absolute path to aggregated output for *city_code*."""
    return DATA_DIR / CITIES[city_code]["traffic_output_dir"]
