"""
OSM Network Builder using OSMnx.
Downloads road networks for cities and saves as GeoPackage reference files.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import geopandas as gpd
import osmnx as ox

from config import CITIES, OSM_PARAMS, CRS, get_osm_reference_path
from utils import create_osm_composite_id


def download_osm_network(city_code, date_str, force_refresh=False):
    """
    Download OSM road network for a city.

    Args:
        city_code: City code ('smg', 'bdg', 'jkt')
        date_str: Date string for file naming (YYYYMMDD)
        force_refresh: Force re-download even if cached file exists

    Returns:
        Path to saved GeoPackage file
    """
    if city_code not in CITIES:
        raise ValueError(f"Unknown city code: {city_code}. Valid codes: {list(CITIES.keys())}")

    city_config = CITIES[city_code]
    output_path = get_osm_reference_path(city_code, date_str)

    # Check if cached file exists and is recent
    if output_path.exists() and not force_refresh:
        file_age = datetime.now() - datetime.fromtimestamp(output_path.stat().st_mtime)
        if file_age < timedelta(days=OSM_PARAMS['cache_days']):
            print(f"Using cached OSM network from {output_path}")
            print(f"  File age: {file_age.days} days (cache valid for {OSM_PARAMS['cache_days']} days)")
            return output_path

    print(f"Downloading OSM network for {city_config['name']}...")
    print(f"  Bounding box: {city_config['bbox']}")
    print(f"  Network type: {OSM_PARAMS['network_type']}")

    # Download network from OSM
    try:
        # OSMnx 2.0+ uses bbox as tuple: (west, south, east, north)
        bbox = (
            city_config['bbox']['west'],
            city_config['bbox']['south'],
            city_config['bbox']['east'],
            city_config['bbox']['north']
        )
        G = ox.graph_from_bbox(
            bbox,
            network_type=OSM_PARAMS['network_type'],
            simplify=True,
            retain_all=False,
            truncate_by_edge=True
        )
    except Exception as e:
        print(f"Error downloading OSM network: {e}", file=sys.stderr)
        raise

    print(f"  Downloaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Convert to GeoDataFrame
    print("Converting to GeoDataFrame...")
    gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

    # Create composite OSM ID
    print("Creating composite IDs...")
    gdf_edges['osm_composite_id'] = gdf_edges.apply(
        lambda row: create_osm_composite_id(
            row.get('osmid', row.name[2]),  # osmid might be in columns or index
            row.name[0],  # u
            row.name[1],  # v
            row.name[2]   # key
        ),
        axis=1
    )

    # Reset index to make u, v, key regular columns
    gdf_edges = gdf_edges.reset_index()

    # Select and reorder columns
    columns_to_keep = [
        'osm_composite_id',
        'osmid',
        'u',
        'v',
        'key',
        'highway',
        'name',
        'length',
        'geometry'
    ]

    # Only keep columns that exist
    available_columns = [col for col in columns_to_keep if col in gdf_edges.columns]
    gdf_edges = gdf_edges[available_columns]

    # Ensure correct CRS
    if gdf_edges.crs != CRS:
        print(f"Reprojecting from {gdf_edges.crs} to {CRS}...")
        gdf_edges = gdf_edges.to_crs(CRS)

    # Save to GeoPackage
    print(f"Saving to {output_path}...")
    gdf_edges.to_file(output_path, driver='GPKG', layer='osm_network')

    print(f"Successfully saved OSM network:")
    print(f"  Segments: {len(gdf_edges)}")
    print(f"  Path: {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    return output_path


def main():
    """Command-line interface for OSM network builder."""
    parser = argparse.ArgumentParser(
        description='Download OSM road networks for traffic analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download network for Semarang
  python osm_network_builder.py --city smg --date 20260202

  # Force refresh cached network
  python osm_network_builder.py --city jkt --date 20260202 --force-refresh

  # Download networks for all cities
  python osm_network_builder.py --all --date 20260202
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
        help='Download networks for all cities'
    )
    parser.add_argument(
        '--date',
        required=True,
        help='Reference date for file naming (YYYYMMDD)'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force re-download even if cached file exists'
    )

    args = parser.parse_args()

    # Validate date format
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
        print(f"\n{'='*60}")
        print(f"Processing {city_code.upper()}")
        print(f"{'='*60}")
        try:
            download_osm_network(city_code, args.date, args.force_refresh)
            success_count += 1
        except Exception as e:
            print(f"Failed to process {city_code}: {e}", file=sys.stderr)
            continue

    print(f"\n{'='*60}")
    print(f"Completed: {success_count}/{len(cities_to_process)} cities")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
