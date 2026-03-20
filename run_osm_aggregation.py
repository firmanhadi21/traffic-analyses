#!/usr/bin/env python3
"""
OSM-Based Traffic Data Aggregation (all cities)

Replaces the legacy FID-based aggregation with OSM-based segment matching.
Uses geometry hashing + spatial join fallback to assign stable OSM composite
IDs to every raw HERE segment across all snapshots.

The legacy pipeline used row-index-based 'fid' which is UNSTABLE across
snapshots (HERE API returns segments in different order each time). This
script fixes that by mapping each segment to a stable OSM road ID via
geometry hashing.

Outputs: {period}_{city}.gpkg  (same format as legacy, drop-in replacement)
Each file contains: osm_composite_id, jam_factor_mean/std/count/min/max, geometry

Usage:
    python run_osm_aggregation.py                    # all 3 cities
    python run_osm_aggregation.py --city jkt         # Jakarta only
    python run_osm_aggregation.py --city smg bdg     # Semarang + Bandung
"""

import argparse
import glob
import hashlib
import os
import sys
import time
from datetime import datetime

import geopandas as gpd
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Mapping dates correspond to when OSM reference networks were built
MAPPING_DATES = {
    'smg': '20260202',
    'bdg': '20260203',
    'jkt': '20260320',
}

CITIES = {
    'smg': {
        'name': 'Semarang',
        'raw_folder': 'traffic_data_smg',
        'output_folder': 'traffic_smg_output',
    },
    'bdg': {
        'name': 'Bandung',
        'raw_folder': 'traffic_data_bdg',
        'output_folder': 'traffic_bdg_output',
    },
    'jkt': {
        'name': 'Jakarta',
        'raw_folder': 'traffic_data_jkt',
        'output_folder': 'traffic_jkt_output',
    },
}

ALL_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night',
]

# Columns to aggregate
CANDIDATE_TRAFFIC_COLS = {
    'jam_factor': ['jam_factor', 'JF', 'jf'],
    'speed': ['speed', 'speed_uncapped', 'SU', 'SP'],
    'free_flow': ['free_flow', 'free_flow_speed', 'FF'],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_timestamp(filename):
    """Extract timestamp from filename: city_traffic_YYYYMMDD_HHMMSS.gpkg"""
    try:
        base = os.path.splitext(os.path.basename(filename))[0]
        parts = base.split('_')
        return datetime.strptime(f"{parts[2]}_{parts[3]}", "%Y%m%d_%H%M%S")
    except Exception:
        return None


def get_time_period(hour):
    """Classify hour into one of 8 time periods."""
    if 0 <= hour < 6:
        return 'night'
    elif hour < 9:
        return 'morning_peak'
    elif hour < 12:
        return 'morning_offpeak'
    elif hour < 14:
        return 'lunch_hours'
    elif hour < 16:
        return 'afternoon_offpeak'
    elif hour < 19:
        return 'evening_peak'
    elif hour < 22:
        return 'evening_offpeak'
    else:
        return 'late_night'


def format_duration(seconds):
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}min"
    else:
        return f"{seconds / 3600:.1f}h"


def detect_columns(gdf):
    """Auto-detect which traffic columns are present in the data."""
    found = {}
    for canonical, candidates in CANDIDATE_TRAFFIC_COLS.items():
        for c in candidates:
            if c in gdf.columns:
                found[canonical] = c
                break
    return found


def geom_wkb_hash(geom):
    """Compute MD5 hash of geometry WKB for fast lookup."""
    return hashlib.md5(geom.wkb).hexdigest()


# ---------------------------------------------------------------------------
# OSM mapping loader
# ---------------------------------------------------------------------------
def load_osm_mapping(city_code, mapping_date):
    """
    Load the HERE-to-OSM mapping table and OSM reference geometry.

    Returns:
        osm_ref_gdf: GeoDataFrame with osm_composite_id + geometry
        mapping_dict: dict of here_geometry_hash -> osm_composite_id
    """
    from utils import create_geometry_hash

    mapping_path = f"osm_reference/{city_code}_here_to_osm_mapping_{mapping_date}.csv"
    osm_ref_path = f"osm_reference/{city_code}_osm_reference_{mapping_date}.gpkg"

    if not os.path.exists(mapping_path):
        raise FileNotFoundError(
            f"OSM mapping not found: {mapping_path}\n"
            f"Run: python osm_network_builder.py --city {city_code} --date {mapping_date}\n"
            f"Then: python create_here_osm_mapping.py --city {city_code} --date {mapping_date}"
        )
    if not os.path.exists(osm_ref_path):
        raise FileNotFoundError(f"OSM reference not found: {osm_ref_path}")

    print(f"  Loading OSM mapping: {mapping_path}")
    mapping_df = pd.read_csv(mapping_path)
    mapping_dict = dict(zip(
        mapping_df['here_geometry_hash'],
        mapping_df['osm_composite_id']
    ))
    print(f"    WKT-hash mappings: {len(mapping_dict)}")

    print(f"  Loading OSM reference: {osm_ref_path}")
    osm_ref_gdf = gpd.read_file(osm_ref_path)
    print(f"    OSM segments: {len(osm_ref_gdf)}")

    return osm_ref_gdf, mapping_dict, create_geometry_hash


def build_wkb_to_osm_cache(raw_gdf, osm_ref_gdf, wkt_hash_mapping, create_geometry_hash_fn):
    """
    Build WKB-hash -> osm_composite_id cache from a raw snapshot.

    Two-step lookup:
    1. Compute WKT-based hash (same as mapping table), look up osm_composite_id
    2. Store result keyed by WKB hash for fast O(1) lookup in subsequent files

    For geometries not in the mapping table, fall back to sjoin_nearest
    against the OSM reference network.
    """
    cache = {}

    # Step 1: Use WKT hash mapping for known geometries
    wkt_hashes = raw_gdf.geometry.apply(create_geometry_hash_fn)
    wkb_hashes = raw_gdf.geometry.apply(geom_wkb_hash)
    osm_ids = wkt_hashes.map(wkt_hash_mapping)

    matched_mask = osm_ids.notna()
    for wkb_h, osm_id in zip(wkb_hashes[matched_mask], osm_ids[matched_mask]):
        cache[wkb_h] = osm_id

    # Step 2: Spatial join fallback for unmatched
    unmatched = raw_gdf[~matched_mask]
    if len(unmatched) > 0:
        print(f"    Spatial join fallback for {len(unmatched)} unmatched segments...")
        osm_for_join = osm_ref_gdf[['osm_composite_id', 'geometry']].copy()
        if unmatched.crs and osm_for_join.crs and unmatched.crs != osm_for_join.crs:
            unmatched = unmatched.to_crs(osm_for_join.crs)

        joined = gpd.sjoin_nearest(
            unmatched[['geometry']].copy(),
            osm_for_join,
            how='left',
            max_distance=0.001,  # ~111m at equator
        )
        joined = joined[~joined.index.duplicated(keep='first')]
        valid = joined['osm_composite_id'].notna()

        unmatched_wkb = unmatched.geometry.apply(geom_wkb_hash)
        for idx in joined[valid].index:
            wkb_h = unmatched_wkb.loc[idx]
            cache[wkb_h] = joined.loc[idx, 'osm_composite_id']

        n_resolved = valid.sum()
        n_still_unmatched = (~valid).sum()
        if n_still_unmatched > 0:
            print(f"    Resolved {n_resolved}, still unmatched: {n_still_unmatched}")

    return cache


def assign_osm_ids(gdf, wkb_cache, osm_ref_gdf):
    """
    Assign OSM composite IDs to a raw GeoDataFrame using WKB hash cache.
    Falls back to sjoin_nearest for any uncached geometries.
    """
    gdf = gdf.copy()
    wkb_hashes = gdf.geometry.apply(geom_wkb_hash)
    gdf['_wkb_hash'] = wkb_hashes
    gdf['osm_composite_id'] = wkb_hashes.map(wkb_cache)

    # Handle uncached via spatial join fallback
    uncached_mask = gdf['osm_composite_id'].isna()
    if uncached_mask.any():
        uncached = gdf.loc[uncached_mask]
        osm_for_join = osm_ref_gdf[['osm_composite_id', 'geometry']].copy()
        if uncached.crs and osm_for_join.crs and uncached.crs != osm_for_join.crs:
            uncached = uncached.to_crs(osm_for_join.crs)

        joined = gpd.sjoin_nearest(
            uncached[['geometry', '_wkb_hash']].copy(),
            osm_for_join,
            how='left',
            max_distance=0.001,
        )
        joined = joined[~joined.index.duplicated(keep='first')]
        valid = joined['osm_composite_id'].notna()

        # Update cache and dataframe
        for idx in joined[valid].index:
            wkb_h = joined.loc[idx, '_wkb_hash']
            osm_id = joined.loc[idx, 'osm_composite_id']
            wkb_cache[wkb_h] = osm_id
            gdf.loc[idx, 'osm_composite_id'] = osm_id

    gdf = gdf.drop(columns=['_wkb_hash'])
    return gdf


# ---------------------------------------------------------------------------
# Streaming statistics (Welford's algorithm, keyed by OSM ID)
# ---------------------------------------------------------------------------
class StreamingStats:
    """
    Memory-efficient per-segment, per-period statistics accumulator.
    Uses Welford's online algorithm for numerically stable mean/std.
    Keyed by osm_composite_id instead of fid.
    """

    def __init__(self, osm_ids, periods, columns):
        self.osm_ids = sorted(osm_ids)
        self.id_to_idx = {oid: i for i, oid in enumerate(self.osm_ids)}
        self.periods = sorted(periods)
        self.period_to_idx = {p: i for i, p in enumerate(self.periods)}
        self.columns = columns
        n_ids = len(self.osm_ids)
        n_periods = len(self.periods)
        n_cols = len(self.columns)

        self.count = np.zeros((n_ids, n_periods, n_cols), dtype=np.int64)
        self.mean = np.zeros((n_ids, n_periods, n_cols), dtype=np.float64)
        self.m2 = np.zeros((n_ids, n_periods, n_cols), dtype=np.float64)
        self.vmin = np.full((n_ids, n_periods, n_cols), np.inf, dtype=np.float64)
        self.vmax = np.full((n_ids, n_periods, n_cols), -np.inf, dtype=np.float64)

    def add_osm_id(self, osm_id):
        """Dynamically add a new OSM ID to the accumulator."""
        if osm_id in self.id_to_idx:
            return
        idx = len(self.osm_ids)
        self.osm_ids.append(osm_id)
        self.id_to_idx[osm_id] = idx
        n_periods = len(self.periods)
        n_cols = len(self.columns)
        self.count = np.concatenate([self.count, np.zeros((1, n_periods, n_cols), dtype=np.int64)])
        self.mean = np.concatenate([self.mean, np.zeros((1, n_periods, n_cols), dtype=np.float64)])
        self.m2 = np.concatenate([self.m2, np.zeros((1, n_periods, n_cols), dtype=np.float64)])
        self.vmin = np.concatenate([self.vmin, np.full((1, n_periods, n_cols), np.inf, dtype=np.float64)])
        self.vmax = np.concatenate([self.vmax, np.full((1, n_periods, n_cols), -np.inf, dtype=np.float64)])

    def update_batch_vectorized(self, osm_id_arr, values_dict, period, col_mapping):
        """Vectorized batch update using Welford's algorithm."""
        pidx = self.period_to_idx.get(period)
        if pidx is None:
            return

        # Map OSM IDs to indices
        id_indices = np.array([self.id_to_idx.get(oid, -1) for oid in osm_id_arr])

        for cidx, canonical in enumerate(self.columns):
            raw_col = col_mapping.get(canonical)
            if raw_col not in values_dict:
                continue

            vals = values_dict[raw_col]
            valid = (id_indices >= 0) & ~np.isnan(vals)
            if not valid.any():
                continue

            valid_ids = id_indices[valid]
            valid_vals = vals[valid]

            for fidx in np.unique(valid_ids):
                mask = valid_ids == fidx
                batch_vals = valid_vals[mask]

                for val in batch_vals:
                    self.count[fidx, pidx, cidx] += 1
                    n = self.count[fidx, pidx, cidx]
                    delta = val - self.mean[fidx, pidx, cidx]
                    self.mean[fidx, pidx, cidx] += delta / n
                    delta2 = val - self.mean[fidx, pidx, cidx]
                    self.m2[fidx, pidx, cidx] += delta * delta2

                batch_min = batch_vals.min()
                batch_max = batch_vals.max()
                if batch_min < self.vmin[fidx, pidx, cidx]:
                    self.vmin[fidx, pidx, cidx] = batch_min
                if batch_max > self.vmax[fidx, pidx, cidx]:
                    self.vmax[fidx, pidx, cidx] = batch_max

    def get_stats_df(self, period):
        """Return DataFrame with stats for a given period."""
        pidx = self.period_to_idx[period]
        result = {'osm_composite_id': self.osm_ids}

        for cidx, canonical in enumerate(self.columns):
            counts = self.count[:, pidx, cidx]
            means = self.mean[:, pidx, cidx]
            m2s = self.m2[:, pidx, cidx]
            mins = self.vmin[:, pidx, cidx]
            maxs = self.vmax[:, pidx, cidx]

            has_data = counts > 0
            has_variance = counts > 1

            mean_out = np.where(has_data, np.round(means, 4), np.nan)
            std_out = np.where(
                has_variance,
                np.round(np.sqrt(np.where(has_variance, m2s / (counts - 1), 0)), 4),
                np.where(has_data, 0.0, np.nan),
            )
            min_out = np.where(has_data, np.round(mins, 4), np.nan)
            max_out = np.where(has_data, np.round(maxs, 4), np.nan)

            result[f'{canonical}_mean'] = mean_out
            result[f'{canonical}_std'] = std_out
            result[f'{canonical}_count'] = counts.astype(int)
            result[f'{canonical}_min'] = min_out
            result[f'{canonical}_max'] = max_out

        return pd.DataFrame(result)


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------
def aggregate_city(city_code, config):
    """Aggregate one city with OSM-based segment matching."""
    raw_folder = config['raw_folder']
    output_folder = config['output_folder']
    name = config['name']
    mapping_date = MAPPING_DATES[city_code]

    os.makedirs(output_folder, exist_ok=True)

    gpkg_files = sorted(glob.glob(os.path.join(raw_folder, '*.gpkg')))
    if not gpkg_files:
        print(f"  No files found in {raw_folder}")
        return

    print(f"\n{'=' * 60}")
    print(f"{name} ({city_code.upper()}): {len(gpkg_files)} files")
    print(f"{'=' * 60}")

    t0 = time.time()

    # ---- Step 1: Load OSM mapping and reference geometry ----
    print(f"\n  Loading OSM mapping and reference...")
    osm_ref_gdf, wkt_hash_mapping, create_geometry_hash_fn = load_osm_mapping(
        city_code, mapping_date
    )

    # ---- Step 2: Build WKB hash cache from first raw file ----
    print(f"\n  Building geometry hash cache from first snapshot...")
    first_raw = gpd.read_file(gpkg_files[0])
    wkb_cache = build_wkb_to_osm_cache(
        first_raw, osm_ref_gdf, wkt_hash_mapping, create_geometry_hash_fn
    )
    print(f"    Cache initialized: {len(wkb_cache)} WKB→OSM mappings")

    # Detect traffic columns
    col_mapping = detect_columns(first_raw)
    print(f"  Detected columns: {col_mapping}")
    if not col_mapping:
        print("  ERROR: No traffic columns found!")
        return

    canonical_cols = list(col_mapping.keys())

    # Collect all known OSM IDs from reference
    all_osm_ids = set(osm_ref_gdf['osm_composite_id'].dropna().unique())
    all_osm_ids.update(wkb_cache.values())

    # ---- Step 3: Initialize streaming stats ----
    stats = StreamingStats(list(all_osm_ids), ALL_PERIODS, canonical_cols)

    # ---- Step 4: Stream through all files ----
    skipped = 0
    files_ok = 0
    min_ts, max_ts = None, None

    for i, f in enumerate(gpkg_files):
        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(gpkg_files) - i - 1) / rate
            print(f"  [{i+1}/{len(gpkg_files)}] "
                  f"{rate:.1f} files/s — ETA: {format_duration(eta)}")

        try:
            gdf = gpd.read_file(f)
        except Exception:
            skipped += 1
            continue

        ts = extract_timestamp(f)
        if ts is None:
            skipped += 1
            continue

        if min_ts is None or ts < min_ts:
            min_ts = ts
        if max_ts is None or ts > max_ts:
            max_ts = ts

        period = get_time_period(ts.hour)

        # Assign OSM IDs via cache + spatial join fallback
        gdf = assign_osm_ids(gdf, wkb_cache, osm_ref_gdf)
        gdf = gdf.dropna(subset=['osm_composite_id'])
        if len(gdf) == 0:
            skipped += 1
            continue

        # Add any new OSM IDs to stats accumulator
        for oid in gdf['osm_composite_id'].unique():
            if oid not in stats.id_to_idx:
                stats.add_osm_id(oid)

        # Build value arrays
        osm_id_arr = gdf['osm_composite_id'].values
        values_dict = {}
        for canonical, raw_col in col_mapping.items():
            if raw_col in gdf.columns:
                values_dict[raw_col] = gdf[raw_col].values.astype(float)

        # Update streaming stats
        stats.update_batch_vectorized(osm_id_arr, values_dict, period, col_mapping)

        files_ok += 1

    elapsed = time.time() - t0
    print(f"\n  Processed {files_ok} files in {format_duration(elapsed)} "
          f"({skipped} skipped)")
    if min_ts and max_ts:
        print(f"  Date range: {min_ts} -> {max_ts}")
    print(f"  WKB cache size: {len(wkb_cache)} mappings")

    # ---- Step 5: Save per-period GeoPackages ----
    print(f"\n  Saving aggregated GeoPackages...")
    osm_geom_lookup = osm_ref_gdf.set_index('osm_composite_id')[['geometry']]

    for period in ALL_PERIODS:
        stats_df = stats.get_stats_df(period)

        # Filter to segments with data
        count_cols = [c for c in stats_df.columns if c.endswith('_count')]
        if count_cols:
            has_data = stats_df[count_cols[0]] > 0
            stats_df_filtered = stats_df[has_data].copy()
        else:
            stats_df_filtered = stats_df.copy()

        if len(stats_df_filtered) == 0:
            continue

        # Join with OSM geometry
        period_gdf = stats_df_filtered.merge(
            osm_geom_lookup, left_on='osm_composite_id', right_index=True, how='left'
        )
        period_gdf = gpd.GeoDataFrame(period_gdf, geometry='geometry', crs=osm_ref_gdf.crs)

        # Drop rows without geometry (rare synthetic IDs not in OSM ref)
        period_gdf = period_gdf.dropna(subset=['geometry'])

        out_file = os.path.join(output_folder, f'{period}_{city_code}.gpkg')
        period_gdf.to_file(out_file, driver='GPKG')

        total_obs = stats_df_filtered[count_cols[0]].sum() if count_cols else 0
        print(f"    {out_file}  ({len(period_gdf)} segments, {total_obs:,} obs)")

    total_time = time.time() - t0
    print(f"\n  {name} complete in {format_duration(total_time)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='OSM-based traffic data aggregation (replaces legacy FID-based)'
    )
    parser.add_argument(
        '--city', nargs='+', choices=list(CITIES.keys()),
        help='Cities to process (default: all). E.g. --city smg bdg jkt'
    )
    args = parser.parse_args()

    cities_to_run = args.city if args.city else list(CITIES.keys())

    print("=" * 60)
    print("OSM-BASED TRAFFIC AGGREGATION")
    print("(Replaces legacy FID-based aggregation)")
    print(f"Cities: {', '.join(c.upper() for c in cities_to_run)}")
    print("=" * 60)

    t_start = time.time()

    for city_code in cities_to_run:
        try:
            aggregate_city(city_code, CITIES[city_code])
        except Exception as e:
            print(f"\nERROR processing {city_code}: {e}")
            import traceback
            traceback.print_exc()
            continue

    total = time.time() - t_start
    print(f"\nTotal time: {format_duration(total)}")
    print("Done!")


if __name__ == '__main__':
    main()
