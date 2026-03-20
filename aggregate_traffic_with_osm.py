"""
Aggregate traffic data using OSM-based segment matching.
Flexible, parameter-driven aggregation with CLI interface.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm

from config import (
    CITIES, TRAFFIC_METRICS, TEMPORAL_GROUPINGS, DAY_TYPES, CRS,
    get_mapping_path, get_osm_reference_path, get_aggregated_output_path
)
from utils import (
    extract_timestamp_from_filename,
    create_geometry_hash,
    parse_time_period,
    in_time_period,
    get_temporal_group,
    filter_files_by_date_range,
    matches_day_type
)


class IncrementalAggregator:
    """
    Memory-efficient incremental aggregator for traffic data.

    Maintains running statistics (sum, sum_sq, count, min, max) grouped by
    OSM segment and temporal period.
    """

    def __init__(self):
        """Initialize empty aggregator."""
        self.data = defaultdict(lambda: {
            'sum': 0.0,
            'sum_sq': 0.0,
            'count': 0,
            'min': float('inf'),
            'max': float('-inf')
        })

    def update(self, osm_id, temporal_group, values):
        """
        Update statistics for a segment-time group.

        Args:
            osm_id: OSM composite ID
            temporal_group: Temporal group identifier (e.g., "2025-W01")
            values: Array of metric values
        """
        key = (osm_id, temporal_group)
        stats = self.data[key]

        values = np.array(values)
        valid_values = values[~np.isnan(values)]

        if len(valid_values) == 0:
            return

        stats['sum'] += valid_values.sum()
        stats['sum_sq'] += (valid_values ** 2).sum()
        stats['count'] += len(valid_values)
        stats['min'] = min(stats['min'], valid_values.min())
        stats['max'] = max(stats['max'], valid_values.max())

    def to_dataframe(self, metric_name):
        """
        Convert aggregated data to DataFrame.

        Args:
            metric_name: Name of the traffic metric

        Returns:
            DataFrame with columns: osm_composite_id, temporal_group,
            {metric}_mean, {metric}_std, {metric}_count, {metric}_min, {metric}_max
        """
        rows = []
        for (osm_id, temporal_group), stats in self.data.items():
            if stats['count'] == 0:
                continue

            mean = stats['sum'] / stats['count']
            # Calculate std using sum of squares formula
            variance = (stats['sum_sq'] / stats['count']) - (mean ** 2)
            std = np.sqrt(max(0, variance))  # Avoid negative due to rounding

            rows.append({
                'osm_composite_id': osm_id,
                'temporal_group': temporal_group,
                f'{metric_name}_mean': mean,
                f'{metric_name}_std': std,
                f'{metric_name}_count': stats['count'],
                f'{metric_name}_min': stats['min'],
                f'{metric_name}_max': stats['max']
            })

        return pd.DataFrame(rows)


def load_mapping_table(city_code, date_str):
    """
    Load HERE to OSM mapping table.

    Args:
        city_code: City code
        date_str: Reference date string (YYYYMMDD)

    Returns:
        Dictionary mapping geometry hash to OSM composite ID
    """
    mapping_path = get_mapping_path(city_code, date_str)

    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Mapping file not found: {mapping_path}\n"
            f"Run create_here_osm_mapping.py first"
        )

    print(f"Loading mapping table: {mapping_path.name}")
    mapping_df = pd.read_csv(mapping_path)
    print(f"  Mappings: {len(mapping_df)}")

    # Create hash → OSM ID lookup dictionary
    mapping_dict = dict(zip(
        mapping_df['here_geometry_hash'],
        mapping_df['osm_composite_id']
    ))

    return mapping_dict


def aggregate_traffic_data(city_code, metric, time_period_str, temporal_grouping,
                            start_date, end_date, mapping_date, day_type='all'):
    """
    Aggregate traffic data with OSM-based matching.

    Args:
        city_code: City code ('smg', 'bdg', 'jkt')
        metric: Traffic metric to aggregate ('jam_factor', 'speed', 'free_flow')
        time_period_str: Time period string (e.g., "morning_peak:6-9")
        temporal_grouping: Temporal grouping ('daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all')
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        mapping_date: Reference date for mapping (YYYYMMDD)
        day_type: Day type filter ('all', 'weekday', 'weekend')

    Returns:
        Path to output GeoPackage file
    """
    if city_code not in CITIES:
        raise ValueError(f"Unknown city code: {city_code}")
    if metric not in TRAFFIC_METRICS:
        raise ValueError(f"Unknown metric: {metric}")
    if temporal_grouping not in TEMPORAL_GROUPINGS:
        raise ValueError(f"Unknown temporal grouping: {temporal_grouping}")
    if day_type not in DAY_TYPES:
        raise ValueError(f"Unknown day type: {day_type}")

    city_config = CITIES[city_code]

    print(f"\n{'='*60}")
    print(f"Aggregating traffic data for {city_config['name']}")
    print(f"{'='*60}")
    print(f"Metric: {metric}")
    print(f"Time period: {time_period_str}")
    print(f"Temporal grouping: {temporal_grouping}")
    print(f"Day type: {day_type}")
    print(f"Date range: {start_date} to {end_date}")

    # Parse time period
    period_name, start_hour, end_hour = parse_time_period(time_period_str)
    print(f"  Hour range: {start_hour}:00 - {end_hour}:00")

    # Load mapping table
    mapping_dict = load_mapping_table(city_code, mapping_date)

    # Find all traffic files in date range
    traffic_dir = city_config['traffic_data_dir']
    all_files = sorted(traffic_dir.glob(city_config['filename_pattern']))
    filtered_files = filter_files_by_date_range(all_files, start_date, end_date)

    print(f"\nFiles to process: {len(filtered_files)} (out of {len(all_files)} total)")

    if len(filtered_files) == 0:
        raise ValueError(f"No files found in date range {start_date} to {end_date}")

    # Initialize aggregator
    aggregator = IncrementalAggregator()

    # Process files incrementally
    print(f"\nProcessing files...")
    files_processed = 0
    files_skipped_time = 0
    files_failed = 0

    for filepath in tqdm(filtered_files, desc="Aggregating", unit="file"):
        try:
            # Extract timestamp
            timestamp = extract_timestamp_from_filename(filepath)

            # Check if within time period
            if not in_time_period(timestamp, start_hour, end_hour):
                files_skipped_time += 1
                continue

            # Check if matches day type (weekday/weekend filter)
            if not matches_day_type(timestamp, day_type):
                files_skipped_time += 1
                continue

            # Get temporal group
            temporal_group = get_temporal_group(timestamp, temporal_grouping)

            # Read GeoPackage
            gdf = gpd.read_file(filepath)

            # Check if metric exists
            if metric not in gdf.columns:
                print(f"  Warning: {metric} not found in {filepath.name}, skipping")
                files_failed += 1
                continue

            # Create geometry hashes and map to OSM IDs
            gdf['here_geometry_hash'] = gdf['geometry'].apply(create_geometry_hash)
            gdf['osm_composite_id'] = gdf['here_geometry_hash'].map(mapping_dict)

            # Drop segments without mapping (shouldn't happen)
            unmapped = gdf['osm_composite_id'].isna().sum()
            if unmapped > 0:
                print(f"  Warning: {unmapped} unmapped segments in {filepath.name}")
                gdf = gdf.dropna(subset=['osm_composite_id'])

            # Update aggregator for each segment
            for osm_id in gdf['osm_composite_id'].unique():
                segment_data = gdf[gdf['osm_composite_id'] == osm_id]
                values = segment_data[metric].values
                aggregator.update(osm_id, temporal_group, values)

            files_processed += 1

        except Exception as e:
            print(f"  Error processing {filepath.name}: {e}")
            files_failed += 1
            continue

    print(f"\nProcessing summary:")
    print(f"  Successfully processed: {files_processed}")
    print(f"  Skipped (time filter): {files_skipped_time}")
    print(f"  Failed: {files_failed}")

    if files_processed == 0:
        raise ValueError("No files were successfully processed")

    # Convert to DataFrame
    print(f"\nConverting to DataFrame...")
    result_df = aggregator.to_dataframe(metric)
    print(f"  Rows: {len(result_df)}")
    print(f"  Unique segments: {result_df['osm_composite_id'].nunique()}")
    print(f"  Temporal groups: {result_df['temporal_group'].nunique()}")

    # Load OSM reference geometry
    osm_ref_path = get_osm_reference_path(city_code, mapping_date)
    if not osm_ref_path.exists():
        raise FileNotFoundError(f"OSM reference not found: {osm_ref_path}")

    print(f"\nLoading OSM reference geometry...")
    osm_gdf = gpd.read_file(osm_ref_path)
    print(f"  OSM segments: {len(osm_gdf)}")

    # Join with geometry
    print(f"\nJoining with OSM geometry...")
    result_gdf = result_df.merge(
        osm_gdf[['osm_composite_id', 'geometry']],
        on='osm_composite_id',
        how='left'
    )

    # Convert to GeoDataFrame
    result_gdf = gpd.GeoDataFrame(result_gdf, geometry='geometry', crs=osm_gdf.crs)

    # Check for missing geometries
    missing_geom = result_gdf['geometry'].isna().sum()
    if missing_geom > 0:
        print(f"  Warning: {missing_geom} rows without geometry (likely synthetic IDs)")

    # Save to file
    output_path = get_aggregated_output_path(
        city_code, period_name, temporal_grouping, metric,
        start_date.replace('-', ''), end_date.replace('-', ''),
        day_type
    )

    print(f"\nSaving to {output_path}...")
    result_gdf.to_file(output_path, driver='GPKG')
    print(f"  Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Print summary statistics
    print(f"\n{'='*60}")
    print("Aggregation complete!")
    print(f"{'='*60}")
    print(f"Output file: {output_path}")
    print(f"\nData summary:")
    print(f"  Total rows: {len(result_gdf)}")
    print(f"  Unique segments: {result_gdf['osm_composite_id'].nunique()}")
    print(f"  Temporal groups: {result_gdf['temporal_group'].nunique()}")
    print(f"\nMetric statistics ({metric}_mean):")
    print(f"  Mean: {result_gdf[f'{metric}_mean'].mean():.2f}")
    print(f"  Std: {result_gdf[f'{metric}_mean'].std():.2f}")
    print(f"  Min: {result_gdf[f'{metric}_mean'].min():.2f}")
    print(f"  Max: {result_gdf[f'{metric}_mean'].max():.2f}")

    return output_path


def main():
    """Command-line interface for traffic aggregation."""
    parser = argparse.ArgumentParser(
        description='Aggregate traffic data with OSM-based segment matching',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Weekly morning peak jam factor for a year
  python aggregate_traffic_with_osm.py \\
    --city smg \\
    --metric jam_factor \\
    --time-period "morning_peak:6-9" \\
    --temporal-grouping weekly \\
    --start-date 2025-01-01 \\
    --end-date 2025-12-31 \\
    --mapping-date 20260202

  # Monthly evening peak speed
  python aggregate_traffic_with_osm.py \\
    --city jkt \\
    --metric speed \\
    --time-period "evening_peak:16-19" \\
    --temporal-grouping monthly \\
    --start-date 2025-01-01 \\
    --end-date 2025-12-31 \\
    --mapping-date 20260202

  # Daily all-day traffic for a week
  python aggregate_traffic_with_osm.py \\
    --city bdg \\
    --metric jam_factor \\
    --time-period "allday:0-24" \\
    --temporal-grouping daily \\
    --start-date 2025-08-17 \\
    --end-date 2025-08-23 \\
    --mapping-date 20260202

  # Overall quarterly statistics
  python aggregate_traffic_with_osm.py \\
    --city smg \\
    --metric free_flow \\
    --time-period "allday:0-24" \\
    --temporal-grouping all \\
    --start-date 2025-01-01 \\
    --end-date 2025-03-31 \\
    --mapping-date 20260202
        """
    )

    parser.add_argument(
        '--city',
        required=True,
        choices=list(CITIES.keys()),
        help='City code (smg, bdg, jkt)'
    )
    parser.add_argument(
        '--metric',
        required=True,
        choices=TRAFFIC_METRICS,
        help='Traffic metric to aggregate'
    )
    parser.add_argument(
        '--time-period',
        required=True,
        help='Time period in format "name:start_hour-end_hour" (e.g., "morning_peak:6-9")'
    )
    parser.add_argument(
        '--temporal-grouping',
        required=True,
        choices=TEMPORAL_GROUPINGS,
        help='Temporal grouping for aggregation'
    )
    parser.add_argument(
        '--start-date',
        required=True,
        help='Start date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--end-date',
        required=True,
        help='End date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--mapping-date',
        required=True,
        help='Reference date for OSM mapping in YYYYMMDD format'
    )
    parser.add_argument(
        '--day-type',
        default='all',
        choices=DAY_TYPES,
        help='Day type filter: all (default), weekday (Mon-Fri), or weekend (Sat-Sun)'
    )

    args = parser.parse_args()

    # Validate date formats
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
        datetime.strptime(args.mapping_date, '%Y%m%d')
    except ValueError as e:
        print(f"Error: Invalid date format. {e}", file=sys.stderr)
        sys.exit(1)

    # Validate time period format
    try:
        parse_time_period(args.time_period)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Run aggregation
    try:
        aggregate_traffic_data(
            args.city,
            args.metric,
            args.time_period,
            args.temporal_grouping,
            args.start_date,
            args.end_date,
            args.mapping_date,
            args.day_type
        )
    except Exception as e:
        print(f"\nError during aggregation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
