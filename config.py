"""
Configuration file for traffic data aggregation system.
Contains city definitions, paths, and matching parameters.
"""

from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
OSM_REFERENCE_DIR = BASE_DIR / "osm_reference"
AGGREGATED_OUTPUT_DIR = BASE_DIR / "aggregated_output"

# Create directories if they don't exist
OSM_REFERENCE_DIR.mkdir(exist_ok=True)
AGGREGATED_OUTPUT_DIR.mkdir(exist_ok=True)

# City configurations
CITIES = {
    'smg': {
        'name': 'Semarang',
        'bbox': {
            'west': 110.227,
            'south': -7.105,
            'east': 110.528,
            'north': -6.919
        },
        'traffic_data_dir': BASE_DIR / 'traffic_data_smg',
        'filename_pattern': 'semarang_traffic_*.gpkg',
        'expected_segments': 1076
    },
    'bdg': {
        'name': 'Bandung',
        'bbox': {
            'west': 107.4688,
            'south': -7.0848,
            'east': 107.8261,
            'north': -6.8294
        },
        'traffic_data_dir': BASE_DIR / 'traffic_data_bdg',
        'filename_pattern': 'bandung_traffic_*.gpkg',
        'expected_segments': 3063
    },
    'jkt': {
        'name': 'Jakarta',
        'bbox': {
            'west': 106.6036,
            'south': -6.4096,
            'east': 107.11,
            'north': -6.0911
        },
        'traffic_data_dir': BASE_DIR / 'traffic_data_jkt',
        'filename_pattern': 'jakarta_traffic_*.gpkg',
        'expected_segments': 14609
    }
}

# Available traffic metrics
TRAFFIC_METRICS = ['jam_factor', 'speed', 'free_flow']

# Spatial matching parameters
MATCHING_PARAMS = {
    'nearest_neighbor_threshold_m': 50,  # Maximum distance for nearest neighbor fallback
    'synthetic_id_start': 9000000000,     # Starting ID for unmatched segments
    'geometry_precision': 6,              # Decimal places for coordinate rounding (~11cm)
    'target_match_rate': 0.95,            # Target >95% match rate
    'max_mean_distance_m': 20,            # Target mean NN distance <20m
}

# OSM network parameters
OSM_PARAMS = {
    'network_type': 'drive',              # All drivable roads
    'cache_days': 30,                     # Cache OSM networks for 30 days
}

# Temporal grouping options
TEMPORAL_GROUPINGS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all']

# Day type filtering options
DAY_TYPES = ['all', 'weekday', 'weekend']

# Coordinate Reference System
CRS = 'EPSG:4326'  # WGS84

# Timezone for Indonesian cities
TIMEZONE = 'Asia/Bangkok'  # GMT+7

def get_osm_reference_path(city_code, date_str):
    """Get path for OSM reference network file."""
    return OSM_REFERENCE_DIR / f"{city_code}_osm_reference_{date_str}.gpkg"

def get_mapping_path(city_code, date_str):
    """Get path for HERE to OSM mapping file."""
    return OSM_REFERENCE_DIR / f"{city_code}_here_to_osm_mapping_{date_str}.csv"

def get_diagnostics_path(city_code, date_str):
    """Get path for matching diagnostics file."""
    diagnostics_dir = AGGREGATED_OUTPUT_DIR / city_code / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    return diagnostics_dir / f"{city_code}_matching_diagnostics_{date_str}.json"

def get_unmatched_segments_path(city_code, date_str):
    """Get path for unmatched segments file."""
    diagnostics_dir = AGGREGATED_OUTPUT_DIR / city_code / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    return diagnostics_dir / f"{city_code}_unmatched_segments_{date_str}.gpkg"

def get_aggregated_output_path(city_code, time_period_name, temporal_grouping,
                                metric, start_date, end_date, day_type='all'):
    """Get path for aggregated output file."""
    output_dir = AGGREGATED_OUTPUT_DIR / city_code / "osm_based"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Include day_type in filename if not 'all'
    if day_type != 'all':
        filename = f"{city_code}_{time_period_name}_{temporal_grouping}_{day_type}_{metric}_{start_date}_{end_date}.gpkg"
    else:
        filename = f"{city_code}_{time_period_name}_{temporal_grouping}_{metric}_{start_date}_{end_date}.gpkg"
    return output_dir / filename
