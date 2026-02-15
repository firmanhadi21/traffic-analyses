#!/usr/bin/env python3
"""
Speed-Based Traffic Data Aggregation (all cities)

Memory-efficient re-aggregation that includes speed and free_flow columns
alongside jam_factor. Uses streaming statistics (Welford's algorithm) so
it never loads all data into RAM at once — safe for Jakarta's 206M rows.

Outputs: {period}_{city}_speed.gpkg  (e.g. evening_peak_jkt_speed.gpkg)
These are distinct from the jam-factor-only files ({period}_{city}.gpkg).

Segment matching uses geometry hashing (MD5 of WKB) for order-independent
fid assignment, consistent with the existing jam-factor aggregation.

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
        'output_folder': 'traffic_smg_speed_output',
    },
    'bdg': {
        'name': 'Bandung',
        'raw_folder': 'traffic_data_bdg',
        'output_folder': 'traffic_bdg_speed_output',
    },
    'jkt': {
        'name': 'Jakarta',
        'raw_folder': 'traffic_data_jkt',
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


def make_geom_id(geom):
    """Create a stable hash from geometry WKB for order-independent matching."""
    return hashlib.md5(geom.wkb).hexdigest()


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
        Vectorized batch update — much faster than row-by-row.
        fid_arr: array of fid values
        values_dict: {canonical_col: array of values}
        """
        pidx = self.period_to_idx.get(period)
        if pidx is None:
            return

        # Map fids to indices
        fid_indices = np.array([self.fid_to_idx.get(int(f), -1) for f in fid_arr])

        for cidx, canonical in enumerate(self.columns):
            raw_col = col_mapping.get(canonical)
            if raw_col not in values_dict:
                continue

            vals = values_dict[raw_col]

            # Process valid entries only
            valid = (fid_indices >= 0) & ~np.isnan(vals)
            valid_fids = fid_indices[valid]
            valid_vals = vals[valid]

            for fidx, val in zip(valid_fids, valid_vals):
                self.count[fidx, pidx, cidx] += 1
                n = self.count[fidx, pidx, cidx]
                delta = val - self.mean[fidx, pidx, cidx]
                self.mean[fidx, pidx, cidx] += delta / n
                delta2 = val - self.mean[fidx, pidx, cidx]
                self.m2[fidx, pidx, cidx] += delta * delta2
                if val < self.vmin[fidx, pidx, cidx]:
                    self.vmin[fidx, pidx, cidx] = val
                if val > self.vmax[fidx, pidx, cidx]:
                    self.vmax[fidx, pidx, cidx] = val

    def get_stats_df(self, period):
        """Return a DataFrame with stats for a given period."""
        pidx = self.period_to_idx[period]
        rows = []
        for fidx, fid in enumerate(self.fids):
            row = {'fid': fid}
            for cidx, canonical in enumerate(self.columns):
                n = self.count[fidx, pidx, cidx]
                if n == 0:
                    row[f'{canonical}_mean'] = np.nan
                    row[f'{canonical}_std'] = np.nan
                    row[f'{canonical}_count'] = 0
                    row[f'{canonical}_min'] = np.nan
                    row[f'{canonical}_max'] = np.nan
                else:
                    row[f'{canonical}_mean'] = round(self.mean[fidx, pidx, cidx], 4)
                    if n > 1:
                        row[f'{canonical}_std'] = round(
                            np.sqrt(self.m2[fidx, pidx, cidx] / (n - 1)), 4
                        )
                    else:
                        row[f'{canonical}_std'] = 0.0
                    row[f'{canonical}_count'] = int(n)
                    row[f'{canonical}_min'] = round(self.vmin[fidx, pidx, cidx], 4)
                    row[f'{canonical}_max'] = round(self.vmax[fidx, pidx, cidx], 4)
            rows.append(row)
        return pd.DataFrame(rows)


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

    # ---- Step 1: Build geometry reference + detect columns ----
    ref_gdf = gpd.read_file(gpkg_files[0])
    ref_gdf['geom_id'] = ref_gdf.geometry.apply(make_geom_id)
    if 'fid' not in ref_gdf.columns:
        ref_gdf['fid'] = range(1, len(ref_gdf) + 1)

    geom_to_fid = dict(zip(ref_gdf['geom_id'], ref_gdf['fid']))
    ref_geom = ref_gdf[['fid', 'geometry']].copy()
    print(f"  Segments: {len(ref_geom)}")

    col_mapping = detect_columns(ref_gdf)
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
        if (i + 1) % 500 == 0:
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

        # Match segments via geometry hash
        gdf['geom_id'] = gdf.geometry.apply(make_geom_id)
        gdf['fid'] = gdf['geom_id'].map(geom_to_fid)
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
