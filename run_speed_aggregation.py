#!/usr/bin/env python3
"""
Speed-Based Traffic Data Aggregation (all cities)

Memory-efficient re-aggregation that includes speed and free_flow columns
alongside jam_factor. Uses streaming statistics (Welford's algorithm) so
it never loads all data into RAM at once — safe for Jakarta's 206M rows.

Outputs: {period}_{city}_speed.gpkg  (e.g. evening_peak_jkt_speed.gpkg)
These are distinct from the jam-factor-only files ({period}_{city}.gpkg).

Segment matching uses spatial join (sjoin_nearest) against existing
aggregated GeoPackages to guarantee canonical fid consistency. The mapping
is cached by geometry WKB hash so the spatial join only runs for the first
file per city; subsequent files are instant hash lookups.

Usage:
    python run_speed_aggregation.py                    # all 3 cities
    python run_speed_aggregation.py --city jkt         # Jakarta only
    python run_speed_aggregation.py --city smg bdg     # Semarang + Bandung
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


# ============================================================
# Configuration
# ============================================================
CITIES = {
    'smg': {
        'name': 'Semarang',
        'raw_folder': 'traffic_data_smg',
        'ref_folder': 'traffic_smg_output',
        'output_folder': 'traffic_smg_speed_output',
    },
    'bdg': {
        'name': 'Bandung',
        'raw_folder': 'traffic_data_bdg',
        'ref_folder': 'traffic_bdg_output',
        'output_folder': 'traffic_bdg_speed_output',
    },
    'jkt': {
        'name': 'Jakarta',
        'raw_folder': 'traffic_data_jkt',
        'ref_folder': 'traffic_jkt_output',
        'output_folder': 'traffic_jkt_speed_output',
    },
}

# Columns to aggregate — will auto-detect from raw data
# Adjust if your HERE API data uses different column names
CANDIDATE_TRAFFIC_COLS = {
    'jam_factor': ['jam_factor', 'JF', 'jf'],
    'speed': ['speed', 'speed_uncapped', 'SU', 'SP'],
    'free_flow': ['free_flow', 'free_flow_speed', 'FF'],
}


# ============================================================
# Helper functions
# ============================================================
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


def build_geom_cache(raw_gdf, ref_gdf):
    """
    Build a geometry WKB-hash → canonical ref_fid mapping via spatial join.

    Uses geopandas.sjoin_nearest so each raw segment is matched to the
    closest reference segment by distance. The result is cached by
    MD5(WKB) so subsequent files skip the spatial join entirely.
    """
    ref_for_join = ref_gdf[['fid', 'geometry']].copy()
    ref_for_join = ref_for_join.rename(columns={'fid': 'ref_fid'})

    # Ensure matching CRS
    if raw_gdf.crs and ref_for_join.crs and raw_gdf.crs != ref_for_join.crs:
        raw_gdf = raw_gdf.to_crs(ref_for_join.crs)

    joined = gpd.sjoin_nearest(raw_gdf, ref_for_join, how='left')

    # Vectorized: compute hashes and build cache in bulk
    wkb_bytes = joined.geometry.apply(lambda g: g.wkb)
    hashes = wkb_bytes.apply(lambda b: hashlib.md5(b).hexdigest())
    ref_fids = joined['ref_fid']
    valid = ref_fids.notna()
    cache = dict(zip(hashes[valid], ref_fids[valid].astype(int)))
    return cache


def assign_ref_fids(gdf, geom_cache, ref_gdf):
    """
    Assign canonical reference fids to a raw GeoDataFrame.

    Looks up each segment's geometry hash in the cache (O(1) per segment).
    Any uncached geometries are resolved via sjoin_nearest and added to
    the cache for future files.
    """
    gdf = gdf.copy()
    # Vectorized hash computation
    hashes = gdf.geometry.apply(lambda g: hashlib.md5(g.wkb).hexdigest())
    gdf['_geom_hash'] = hashes
    gdf['fid'] = hashes.map(geom_cache)

    # Handle any uncached geometries via spatial join fallback
    uncached_mask = gdf['fid'].isna()
    if uncached_mask.any():
        uncached = gdf.loc[uncached_mask]
        ref_for_join = ref_gdf[['fid', 'geometry']].copy()
        ref_for_join = ref_for_join.rename(columns={'fid': 'ref_fid'})
        joined = gpd.sjoin_nearest(
            uncached[['geometry', '_geom_hash']].copy(),
            ref_for_join,
            how='left',
        )
        valid = joined['ref_fid'].notna()
        new_mappings = dict(zip(
            joined.loc[valid, '_geom_hash'],
            joined.loc[valid, 'ref_fid'].astype(int),
        ))
        geom_cache.update(new_mappings)
        # Re-map after updating cache
        gdf['fid'] = gdf['_geom_hash'].map(geom_cache)

    gdf = gdf.drop(columns=['_geom_hash'])
    return gdf


def detect_columns(gdf):
    """Auto-detect which traffic columns are present in the data."""
    found = {}
    for canonical, candidates in CANDIDATE_TRAFFIC_COLS.items():
        for c in candidates:
            if c in gdf.columns:
                found[canonical] = c
                break
    return found


def format_duration(seconds):
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}min"
    else:
        return f"{seconds / 3600:.1f}h"


# ============================================================
# Streaming statistics accumulator (Welford's algorithm)
# ============================================================
class StreamingStats:
    """
    Memory-efficient per-segment, per-period statistics accumulator.
    Uses Welford's online algorithm for numerically stable mean and std.
    Only stores O(segments × periods × columns) floats, not all raw data.
    """

    def __init__(self, fids, periods, columns):
        self.fids = sorted(fids)
        self.fid_to_idx = {fid: i for i, fid in enumerate(self.fids)}
        self.periods = sorted(periods)
        self.period_to_idx = {p: i for i, p in enumerate(self.periods)}
        self.columns = columns
        n_fids = len(self.fids)
        n_periods = len(self.periods)
        n_cols = len(self.columns)

        # Welford accumulators: shape (n_fids, n_periods, n_cols)
        self.count = np.zeros((n_fids, n_periods, n_cols), dtype=np.int64)
        self.mean = np.zeros((n_fids, n_periods, n_cols), dtype=np.float64)
        self.m2 = np.zeros((n_fids, n_periods, n_cols), dtype=np.float64)
        self.vmin = np.full((n_fids, n_periods, n_cols), np.inf, dtype=np.float64)
        self.vmax = np.full((n_fids, n_periods, n_cols), -np.inf, dtype=np.float64)

    def update_batch(self, df, period, col_mapping):
        """Update stats with a batch of data for a given time period."""
        pidx = self.period_to_idx.get(period)
        if pidx is None:
            return

        for cidx, canonical in enumerate(self.columns):
            raw_col = col_mapping.get(canonical)
            if raw_col is None or raw_col not in df.columns:
                continue

            for _, row in df.iterrows():
                fid = row.get('fid')
                val = row.get(raw_col)
                if fid is None or pd.isna(val):
                    continue

                fidx = self.fid_to_idx.get(int(fid))
                if fidx is None:
                    continue

                # Welford update
                self.count[fidx, pidx, cidx] += 1
                n = self.count[fidx, pidx, cidx]
                delta = val - self.mean[fidx, pidx, cidx]
                self.mean[fidx, pidx, cidx] += delta / n
                delta2 = val - self.mean[fidx, pidx, cidx]
                self.m2[fidx, pidx, cidx] += delta * delta2

                # Min/max
                if val < self.vmin[fidx, pidx, cidx]:
                    self.vmin[fidx, pidx, cidx] = val
                if val > self.vmax[fidx, pidx, cidx]:
                    self.vmax[fidx, pidx, cidx] = val

    def update_batch_vectorized(self, fid_arr, values_dict, period, col_mapping):
        """
        Fully vectorized batch update using NumPy array operations.
        fid_arr: array of fid values
        values_dict: {raw_col_name: array of values}
        """
        pidx = self.period_to_idx.get(period)
        if pidx is None:
            return

        # Map fids to indices — vectorized lookup
        fid_indices = np.array([self.fid_to_idx.get(int(f), -1) for f in fid_arr])

        for cidx, canonical in enumerate(self.columns):
            raw_col = col_mapping.get(canonical)
            if raw_col not in values_dict:
                continue

            vals = values_dict[raw_col]

            # Filter to valid entries
            valid = (fid_indices >= 0) & ~np.isnan(vals)
            if not valid.any():
                continue

            valid_fids = fid_indices[valid]
            valid_vals = vals[valid]

            # Group by unique fid index for efficient batch processing
            unique_fids = np.unique(valid_fids)

            for fidx in unique_fids:
                mask = valid_fids == fidx
                batch_vals = valid_vals[mask]

                # Batch Welford: process all values for this (fid, period, col)
                for val in batch_vals:
                    self.count[fidx, pidx, cidx] += 1
                    n = self.count[fidx, pidx, cidx]
                    delta = val - self.mean[fidx, pidx, cidx]
                    self.mean[fidx, pidx, cidx] += delta / n
                    delta2 = val - self.mean[fidx, pidx, cidx]
                    self.m2[fidx, pidx, cidx] += delta * delta2

                # Min/max via NumPy (vectorized)
                batch_min = batch_vals.min()
                batch_max = batch_vals.max()
                if batch_min < self.vmin[fidx, pidx, cidx]:
                    self.vmin[fidx, pidx, cidx] = batch_min
                if batch_max > self.vmax[fidx, pidx, cidx]:
                    self.vmax[fidx, pidx, cidx] = batch_max

    def get_stats_df(self, period):
        """Return a DataFrame with stats for a given period (vectorized)."""
        pidx = self.period_to_idx[period]
        result = {'fid': np.array(self.fids)}

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


# ============================================================
# Per-city ANOVA (streaming-compatible: uses per-period sums)
# ============================================================
class StreamingANOVA:
    """Accumulate per-period sums for one-pass ANOVA computation."""

    def __init__(self, periods, columns):
        self.periods = sorted(periods)
        self.columns = columns
        # Per period: count, sum, sum_of_squares
        self.count = {p: {c: 0 for c in columns} for p in periods}
        self.total = {p: {c: 0.0 for c in columns} for p in periods}
        self.total_sq = {p: {c: 0.0 for c in columns} for p in periods}

    def update(self, period, values_dict, col_mapping):
        """Update with a batch of values."""
        for canonical in self.columns:
            raw_col = col_mapping.get(canonical)
            if raw_col not in values_dict:
                continue
            vals = values_dict[raw_col]
            valid = vals[~np.isnan(vals)]
            n = len(valid)
            if n == 0:
                continue
            self.count[period][canonical] += n
            self.total[period][canonical] += valid.sum()
            self.total_sq[period][canonical] += (valid ** 2).sum()

    def compute(self):
        """Compute ANOVA F-stat and eta-squared for each column."""
        results = {}
        for canonical in self.columns:
            # Grand stats
            N = sum(self.count[p][canonical] for p in self.periods)
            if N == 0:
                results[canonical] = {'F': np.nan, 'eta_sq': np.nan, 'n': 0}
                continue
            grand_sum = sum(self.total[p][canonical] for p in self.periods)
            grand_mean = grand_sum / N
            ss_total = (
                sum(self.total_sq[p][canonical] for p in self.periods)
                - N * grand_mean ** 2
            )

            # Between-group SS
            k = 0
            ss_between = 0.0
            period_means = {}
            for p in self.periods:
                n_p = self.count[p][canonical]
                if n_p == 0:
                    continue
                k += 1
                p_mean = self.total[p][canonical] / n_p
                period_means[p] = round(p_mean, 2)
                ss_between += n_p * (p_mean - grand_mean) ** 2

            ss_within = ss_total - ss_between
            if k <= 1 or ss_within <= 0:
                results[canonical] = {'F': np.nan, 'eta_sq': np.nan, 'n': N}
                continue

            df_between = k - 1
            df_within = N - k
            F = (ss_between / df_between) / (ss_within / df_within)
            eta_sq = ss_between / ss_total if ss_total > 0 else 0

            results[canonical] = {
                'F': F,
                'eta_sq': eta_sq,
                'n': N,
                'period_means': period_means,
            }
        return results


# ============================================================
# Main aggregation
# ============================================================
def aggregate_city(city_code, config):
    """Aggregate one city with streaming stats."""
    raw_folder = config['raw_folder']
    output_folder = config['output_folder']
    name = config['name']

    os.makedirs(output_folder, exist_ok=True)

    gpkg_files = sorted(glob.glob(os.path.join(raw_folder, '*.gpkg')))
    if not gpkg_files:
        print(f"  No files found in {raw_folder}")
        return None

    print(f"\n{'=' * 60}")
    print(f"{name} ({city_code.upper()}): {len(gpkg_files)} files")
    print(f"{'=' * 60}")

    t0 = time.time()

    # ---- Step 1: Get reference geometry from FIRST RAW FILE ----
    # This matches the pattern in run_bandung_aggregation.py (line 103-109)
    print(f"  Extracting reference geometry from first file...")
    first_raw = gpd.read_file(gpkg_files[0])
    
    # Add 1-indexed fid if missing (matches line 77-79 in run_bandung_aggregation.py)
    if 'fid' not in first_raw.columns:
        first_raw['fid'] = range(1, len(first_raw) + 1)
    
    ref_geom = first_raw[['fid', 'geometry']].copy()
    print(f"  Reference: {os.path.basename(gpkg_files[0])} "
          f"({len(ref_geom)} segments)")
    
    # Pre-populate geometry → fid cache from reference geometry
    # (vectorized to avoid iterating)
    wkb_bytes = ref_geom.geometry.apply(lambda g: g.wkb)
    hashes = wkb_bytes.apply(lambda b: hashlib.md5(b).hexdigest())
    geom_cache = dict(zip(hashes, ref_geom['fid']))
    print(f"  Initialized cache: {len(geom_cache)} geometry→fid mappings")

    # Detect traffic columns from the first raw file
    col_mapping = detect_columns(first_raw)
    print(f"  Detected columns: {col_mapping}")
    if not col_mapping:
        print("  ERROR: No traffic columns found!")
        return None

    canonical_cols = list(col_mapping.keys())
    all_periods = [
        'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
        'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night',
    ]

    # ---- Step 2: Initialize streaming accumulators ----
    stats = StreamingStats(ref_geom['fid'].values, all_periods, canonical_cols)
    anova = StreamingANOVA(all_periods, canonical_cols)

    # Also track speed_reduction for ANOVA if both speed and free_flow exist
    has_reduction = 'speed' in col_mapping and 'free_flow' in col_mapping
    if has_reduction:
        anova_red = StreamingANOVA(all_periods, ['speed_reduction'])

    # ---- Step 3: Stream through all files ----
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

        # Match segments to canonical fids via spatial-join cache
        gdf = assign_ref_fids(gdf, geom_cache, ref_geom)
        gdf = gdf.dropna(subset=['fid'])
        if len(gdf) == 0:
            skipped += 1
            continue

        gdf['fid'] = gdf['fid'].astype(int)

        # Build value arrays for vectorized update
        fid_arr = gdf['fid'].values
        values_dict = {}
        for canonical, raw_col in col_mapping.items():
            if raw_col in gdf.columns:
                values_dict[raw_col] = gdf[raw_col].values.astype(float)

        # Update streaming stats
        stats.update_batch_vectorized(fid_arr, values_dict, period, col_mapping)

        # Update ANOVA accumulators
        anova.update(period, values_dict, col_mapping)

        # Speed reduction ANOVA
        if has_reduction:
            speed_raw = col_mapping['speed']
            ff_raw = col_mapping['free_flow']
            if speed_raw in values_dict and ff_raw in values_dict:
                reduction = values_dict[ff_raw] - values_dict[speed_raw]
                anova_red.update(period, {'speed_reduction': reduction},
                                {'speed_reduction': 'speed_reduction'})

        files_ok += 1

    elapsed = time.time() - t0
    print(f"\n  Processed {files_ok} files in {format_duration(elapsed)} "
          f"({skipped} skipped)")
    if min_ts and max_ts:
        print(f"  Date range: {min_ts} → {max_ts}")

    # ---- Step 4: Save per-period GeoPackages ----
    print(f"\n  Saving aggregated GeoPackages...")
    for period in all_periods:
        stats_df = stats.get_stats_df(period)
        # Check if any data exists for this period
        count_cols = [c for c in stats_df.columns if c.endswith('_count')]
        if count_cols and stats_df[count_cols[0]].sum() == 0:
            continue

        period_gdf = ref_geom.merge(stats_df, on='fid', how='left')
        out_file = os.path.join(output_folder, f'{period}_{city_code}_speed.gpkg')
        period_gdf.to_file(out_file, driver='GPKG')
        total_obs = stats_df[count_cols[0]].sum() if count_cols else 0
        print(f"    {out_file}  ({total_obs:,} obs)")

    # ---- Step 5: Print ANOVA results ----
    print(f"\n  --- ANOVA Results (time period → metric) ---")
    anova_results = anova.compute()
    for canonical, res in anova_results.items():
        if np.isnan(res.get('F', np.nan)):
            continue
        print(f"\n  {canonical}:")
        print(f"    F = {res['F']:,.0f}, η² = {res['eta_sq']:.4f} "
              f"({res['eta_sq']*100:.1f}%), n = {res['n']:,}")
        if 'period_means' in res:
            for p in sorted(res['period_means']):
                print(f"      {p}: {res['period_means'][p]}")

    if has_reduction:
        red_results = anova_red.compute()
        res = red_results.get('speed_reduction', {})
        if not np.isnan(res.get('F', np.nan)):
            print(f"\n  speed_reduction (free_flow − speed):")
            print(f"    F = {res['F']:,.0f}, η² = {res['eta_sq']:.4f} "
                  f"({res['eta_sq']*100:.1f}%), n = {res['n']:,}")
            if 'period_means' in res:
                for p in sorted(res['period_means']):
                    print(f"      {p}: {res['period_means'][p]}")

    # ---- Step 6: Save ANOVA CSV ----
    anova_rows = []
    for canonical, res in anova_results.items():
        anova_rows.append({
            'city': name,
            'metric': canonical,
            'F_stat': res.get('F'),
            'eta_squared': res.get('eta_sq'),
            'n': res.get('n'),
        })
    if has_reduction:
        res = red_results.get('speed_reduction', {})
        anova_rows.append({
            'city': name,
            'metric': 'speed_reduction',
            'F_stat': res.get('F'),
            'eta_squared': res.get('eta_sq'),
            'n': res.get('n'),
        })

    anova_df = pd.DataFrame(anova_rows)
    anova_csv = os.path.join(output_folder, f'anova_results_{city_code}.csv')
    anova_df.to_csv(anova_csv, index=False)
    print(f"\n  ANOVA saved: {anova_csv}")

    # ---- Step 7: Save detailed ANOVA output to text file ----
    anova_txt = os.path.join(output_folder, f'anova_detailed_{city_code}.txt')
    with open(anova_txt, 'w') as f:
        f.write(f"ANOVA Results for {name}\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"Total observations: {files_ok} files processed\n")
        if min_ts and max_ts:
            f.write(f"Date range: {min_ts} to {max_ts}\n")
        f.write(f"\n{'=' * 60}\n")
        f.write("Time Period → Metric Analysis\n")
        f.write(f"{'=' * 60}\n\n")
        
        for canonical, res in anova_results.items():
            if np.isnan(res.get('F', np.nan)):
                continue
            f.write(f"{canonical}:\n")
            f.write(f"  F-statistic = {res['F']:,.0f}\n")
            f.write(f"  η² (eta-squared) = {res['eta_sq']:.4f} ({res['eta_sq']*100:.1f}%)\n")
            f.write(f"  n = {res['n']:,} observations\n")
            if 'period_means' in res:
                f.write(f"  Period means:\n")
                for p in sorted(res['period_means']):
                    f.write(f"    {p}: {res['period_means'][p]}\n")
            f.write("\n")
        
        if has_reduction:
            res = red_results.get('speed_reduction', {})
            if not np.isnan(res.get('F', np.nan)):
                f.write("speed_reduction (free_flow − speed):\n")
                f.write(f"  F-statistic = {res['F']:,.0f}\n")
                f.write(f"  η² (eta-squared) = {res['eta_sq']:.4f} ({res['eta_sq']*100:.1f}%)\n")
                f.write(f"  n = {res['n']:,} observations\n")
                if 'period_means' in res:
                    f.write(f"  Period means:\n")
                    for p in sorted(res['period_means']):
                        f.write(f"    {p}: {res['period_means'][p]}\n")
    
    print(f"  ANOVA detailed output: {anova_txt}")

    total_time = time.time() - t0
    print(f"\n  {name} complete in {format_duration(total_time)}")

    return anova_results


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='Aggregate traffic data with speed columns (memory-efficient)'
    )
    parser.add_argument(
        '--city', nargs='+', choices=list(CITIES.keys()),
        help='Cities to process (default: all). E.g. --city smg bdg jkt'
    )
    args = parser.parse_args()

    cities_to_run = args.city if args.city else list(CITIES.keys())

    print("=" * 60)
    print("SPEED-BASED TRAFFIC AGGREGATION")
    print(f"Cities: {', '.join(c.upper() for c in cities_to_run)}")
    print("=" * 60)

    all_anova = {}
    t_start = time.time()

    for city_code in cities_to_run:
        result = aggregate_city(city_code, CITIES[city_code])
        if result:
            all_anova[city_code] = result

    # ---- Summary comparison table ----
    if all_anova:
        print("\n" + "=" * 70)
        print("SUMMARY: Temporal variance explained (η²) by metric")
        print("=" * 70)

        header = f"{'City':<12}"
        metrics = set()
        for res in all_anova.values():
            metrics.update(res.keys())
        metrics = sorted(metrics)

        for m in metrics:
            header += f"  {m:>16}"
        print(header)
        print("-" * len(header))

        for city_code, results in all_anova.items():
            row = f"{CITIES[city_code]['name']:<12}"
            for m in metrics:
                eta = results.get(m, {}).get('eta_sq')
                if eta is not None and not np.isnan(eta):
                    row += f"  {eta*100:>15.1f}%"
                else:
                    row += f"  {'N/A':>15}"
            print(row)

    total = time.time() - t_start
    print(f"\nTotal time: {format_duration(total)}")
    print("Done!")


if __name__ == '__main__':
    main()
