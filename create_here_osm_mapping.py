"""
Create HERE to OSM mapping table.
Uses one HERE snapshot as geometry template and performs spatial matching to OSM.
"""

import sys
import argparse
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd

from config import (
    CITIES, CRS,
    get_osm_reference_path, get_mapping_path,
    get_diagnostics_path, get_unmatched_segments_path
)
from utils import create_geometry_hash
from spatial_matcher import match_here_to_osm


def load_here_snapshot(city_code):
    """
    Load one HERE snapshot as geometry template.

    Args:
        city_code: City code ('smg', 'bdg', 'jkt')

    Returns:
        GeoDataFrame of HERE segments
    """
    city_config = CITIES[city_code]
    traffic_dir = city_config['traffic_data_dir']

    # Find all traffic files
    pattern = city_config['filename_pattern']
    files = sorted(traffic_dir.glob(pattern))

    if len(files) == 0:
        raise FileNotFoundError(f"No traffic files found in {traffic_dir}")

    # Use the most recent file as template
    template_file = files[-1]
    print(f"Loading HERE snapshot from: {template_file.name}")

    gdf = gpd.read_file(template_file)

    print(f"  Loaded {len(gdf)} segments")
    print(f"  CRS: {gdf.crs}")

    # Ensure correct CRS
    if gdf.crs != CRS:
        print(f"  Reprojecting to {CRS}...")
        gdf = gdf.to_crs(CRS)

    return gdf


def create_mapping(city_code, date_str, osm_reference_path=None, force_refresh=False):
    """
    Create HERE to OSM mapping table.

    Args:
        city_code: City code ('smg', 'bdg', 'jkt')
        date_str: Date string for file naming (YYYYMMDD)
        osm_reference_path: Optional path to OSM reference (default: auto-detect)
        force_refresh: Force recreation even if mapping exists

    Returns:
        Path to created mapping CSV file
    """
    if city_code not in CITIES:
        raise ValueError(f"Unknown city code: {city_code}")

    city_config = CITIES[city_code]
    mapping_path = get_mapping_path(city_code, date_str)

    # Check if mapping already exists
    if mapping_path.exists() and not force_refresh:
        print(f"Mapping already exists: {mapping_path}")
        print("Use --force-refresh to recreate")
        return mapping_path

    print(f"\n{'='*60}")
    print(f"Creating HERE→OSM mapping for {city_config['name']}")
    print(f"{'='*60}")

    # Load OSM reference network
    if osm_reference_path is None:
        osm_reference_path = get_osm_reference_path(city_code, date_str)

    if not osm_reference_path.exists():
        raise FileNotFoundError(
            f"OSM reference not found: {osm_reference_path}\n"
            f"Run osm_network_builder.py first"
        )

    print(f"\nLoading OSM reference: {osm_reference_path.name}")
    osm_gdf = gpd.read_file(osm_reference_path)
    print(f"  OSM segments: {len(osm_gdf)}")

    # Load HERE snapshot
    print(f"\nLoading HERE snapshot...")
    here_gdf = load_here_snapshot(city_code)

    # Perform spatial matching
    print(f"\nPerforming spatial matching...")
    matched_gdf, diagnostics = match_here_to_osm(here_gdf, osm_gdf, verbose=True)

    # Create geometry hashes for matched segments
    print(f"\nCreating geometry hashes...")
    matched_gdf['here_geometry_hash'] = matched_gdf['geometry'].apply(create_geometry_hash)

    # Create mapping table: hash → OSM ID
    mapping_df = matched_gdf[['here_geometry_hash', 'osm_composite_id', 'match_method', 'distance_m']].copy()

    # Remove duplicates (shouldn't happen, but just in case)
    n_before = len(mapping_df)
    mapping_df = mapping_df.drop_duplicates(subset=['here_geometry_hash'])
    n_after = len(mapping_df)

    if n_before != n_after:
        print(f"  Warning: Removed {n_before - n_after} duplicate hashes")

    # Save mapping table
    print(f"\nSaving mapping table to {mapping_path}...")
    mapping_df.to_csv(mapping_path, index=False)
    print(f"  Rows: {len(mapping_df)}")
    print(f"  Size: {mapping_path.stat().st_size / 1024:.1f} KB")

    # Save diagnostics
    diagnostics_path = get_diagnostics_path(city_code, date_str)
    print(f"\nSaving diagnostics to {diagnostics_path}...")

    diagnostics['city_code'] = city_code
    diagnostics['city_name'] = city_config['name']
    diagnostics['date_str'] = date_str
    diagnostics['osm_reference_path'] = str(osm_reference_path)
    diagnostics['mapping_path'] = str(mapping_path)

    with open(diagnostics_path, 'w') as f:
        json.dump(diagnostics, f, indent=2)

    # Save unmatched segments (synthetic IDs) for review
    unmatched = matched_gdf[matched_gdf['match_method'] == 'synthetic'].copy()
    if len(unmatched) > 0:
        unmatched_path = get_unmatched_segments_path(city_code, date_str)
        print(f"\nSaving {len(unmatched)} unmatched segments to {unmatched_path}...")
        unmatched.to_file(unmatched_path, driver='GPKG')

    # Print summary
    print(f"\n{'='*60}")
    print("Mapping creation complete!")
    print(f"{'='*60}")
    print(f"Mapping file: {mapping_path}")
    print(f"Diagnostics: {diagnostics_path}")
    if len(unmatched) > 0:
        print(f"Unmatched segments: {unmatched_path}")
    print(f"\nKey statistics:")
    print(f"  Total segments: {diagnostics['total_segments']}")
    print(f"  OSM matched: {diagnostics['intersection_matched'] + diagnostics['nearest_neighbor_matched']} "
          f"({diagnostics['overall_osm_match_rate']:.1%})")
    print(f"  Synthetic IDs: {diagnostics['synthetic_ids']} ({diagnostics['synthetic_rate']:.1%})")

    return mapping_path


def main():
    """Command-line interface for mapping creation."""
    parser = argparse.ArgumentParser(
        description='Create HERE to OSM mapping table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create mapping for Semarang
  python create_here_osm_mapping.py --city smg --date 20260202

  # Force refresh existing mapping
  python create_here_osm_mapping.py --city smg --date 20260202 --force-refresh

  # Create mappings for all cities
  python create_here_osm_mapping.py --all --date 20260202

  # Use custom OSM reference
  python create_here_osm_mapping.py --city jkt --date 20260202 --osm-reference /path/to/custom.gpkg
        """
    )

    parser.add_argument(
        '--city',
        choices=list(CITIES.keys()),
        help='City code (smg, bdg, jkt)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Create mappings for all cities'
    )
    parser.add_argument(
        '--date',
        required=True,
        help='Reference date for file naming (YYYYMMDD)'
    )
    parser.add_argument(
        '--osm-reference',
        type=Path,
        help='Optional path to OSM reference file (default: auto-detect)'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force recreation even if mapping exists'
    )

    args = parser.parse_args()

    # Validate date format
    from datetime import datetime
    try:
        datetime.strptime(args.date, '%Y%m%d')
    except ValueError:
        print("Error: Date must be in YYYYMMDD format", file=sys.stderr)
        sys.exit(1)

    # Determine cities to process
    if args.all:
        cities_to_process = list(CITIES.keys())
    elif args.city:
        cities_to_process = [args.city]
    else:
        print("Error: Must specify either --city or --all", file=sys.stderr)
        sys.exit(1)

    # Process each city
    success_count = 0
    for city_code in cities_to_process:
        try:
            create_mapping(
                city_code,
                args.date,
                args.osm_reference,
                args.force_refresh
            )
            success_count += 1
        except Exception as e:
            print(f"\nFailed to create mapping for {city_code}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue

    print(f"\n{'='*60}")
    print(f"Completed: {success_count}/{len(cities_to_process)} cities")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
