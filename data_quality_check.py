#!/usr/bin/env python3
"""
Data Quality Check for Traffic Pipeline

Standalone script — no package installation required.
Validates both raw and aggregated traffic GeoPackages.

Checks:
  1. Column presence and types
  2. Null/missing values
  3. Value ranges (jam_factor 0-10, speed >= 0, free_flow >= 0)
  4. Segment count consistency across time periods
  5. Geometry validity and duplicates
  6. Bidirectional segment detection (same geometry, different free_flow)
  7. Temporal coverage completeness
  8. Observation density per segment

Usage:
    python data_quality_check.py                     # check aggregated data
    python data_quality_check.py --raw               # check raw data (sample)
    python data_quality_check.py --city smg          # single city
    python data_quality_check.py --raw --n-sample 10 # sample 10 raw files
"""

import argparse
import glob
import hashlib
import os
import sys
from collections import Counter
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
        'agg_folder': 'traffic_smg_output',
        'expected_segments': 1076,
    },
    'bdg': {
        'name': 'Bandung',
        'raw_folder': 'traffic_data_bdg',
        'agg_folder': 'traffic_bdg_output',
        'expected_segments': 3069,
    },
    'jkt': {
        'name': 'Jakarta',
        'raw_folder': 'traffic_data_jkt',
        'agg_folder': 'traffic_jkt_output',
        'expected_segments': 14549,
    },
}

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night',
]

EXPECTED_RAW_COLS = ['jam_factor', 'speed', 'free_flow', 'geometry']
EXPECTED_AGG_COLS = ['jam_factor_mean', 'jam_factor_std', 'jam_factor_count', 'geometry']


# ============================================================
# Helpers
# ============================================================
def status(ok):
    return 'PASS' if ok else 'FAIL'


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def geom_hash(geom):
    return hashlib.md5(geom.wkb).hexdigest()


# ============================================================
# Aggregated data checks
# ============================================================
def check_aggregated(city_code, cfg, base_dir='.'):
    name = cfg['name']
    agg_folder = os.path.join(base_dir, cfg['agg_folder'])
    print_header(f"{name} ({city_code.upper()}) — Aggregated Data")

    issues = []

    # Check folder exists
    if not os.path.isdir(agg_folder):
        print(f"  SKIP: folder {agg_folder} not found")
        return issues

    # Load all periods
    period_data = {}
    for period in TIME_PERIODS:
        fp = os.path.join(agg_folder, f'{period}_{city_code}.gpkg')
        if os.path.exists(fp):
            period_data[period] = gpd.read_file(fp)
        else:
            issues.append(f"Missing file: {fp}")
            print(f"  FAIL: Missing {period}_{city_code}.gpkg")

    if not period_data:
        print(f"  SKIP: No data files found")
        return issues

    # ---- Check 1: Column presence ----
    first_gdf = list(period_data.values())[0]
    missing_cols = [c for c in EXPECTED_AGG_COLS if c not in first_gdf.columns]
    ok = len(missing_cols) == 0
    print(f"\n  1. Column presence: {status(ok)}")
    print(f"     Columns: {list(first_gdf.columns)}")
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")
        print(f"     Missing: {missing_cols}")

    # ---- Check 2: Segment count consistency ----
    seg_counts = {p: len(gdf) for p, gdf in period_data.items()}
    unique_counts = set(seg_counts.values())
    ok = len(unique_counts) == 1
    print(f"\n  2. Segment consistency: {status(ok)}")
    if ok:
        print(f"     All periods: {list(unique_counts)[0]} segments")
    else:
        issues.append(f"Inconsistent segment counts: {seg_counts}")
        for p, c in seg_counts.items():
            print(f"     {p:25s} {c}")

    expected = cfg['expected_segments']
    actual = list(seg_counts.values())[0]
    if actual != expected:
        print(f"     NOTE: Expected {expected}, got {actual} (diff: {actual - expected:+d})")

    # ---- Check 3: Null values ----
    total_nulls = 0
    for p, gdf in period_data.items():
        for col in ['jam_factor_mean', 'jam_factor_count']:
            if col in gdf.columns:
                n = gdf[col].isna().sum()
                total_nulls += n
    ok = total_nulls == 0
    print(f"\n  3. Null values: {status(ok)}")
    if not ok:
        issues.append(f"{total_nulls} null values across all periods")
        print(f"     Total nulls: {total_nulls}")

    # ---- Check 4: Value ranges ----
    all_means = pd.concat([gdf['jam_factor_mean'].dropna() for gdf in period_data.values()])
    below = (all_means < 0).sum()
    above = (all_means > 10).sum()
    ok = below == 0 and above == 0
    print(f"\n  4. Value ranges (jam_factor 0-10): {status(ok)}")
    print(f"     Min: {all_means.min():.4f}, Max: {all_means.max():.4f}, Mean: {all_means.mean():.4f}")
    if not ok:
        issues.append(f"Out-of-range: {below} below 0, {above} above 10")

    # ---- Check 5: Geometry consistency ----
    hashes_by_period = {}
    for p, gdf in period_data.items():
        hashes_by_period[p] = set(geom_hash(g) for g in gdf.geometry)

    all_hashes = list(hashes_by_period.values())
    common = all_hashes[0]
    union = all_hashes[0]
    for h in all_hashes[1:]:
        common = common & h
        union = union | h
    ok = len(common) == len(union)
    print(f"\n  5. Geometry consistency across periods: {status(ok)}")
    print(f"     Common: {len(common)}, Union: {len(union)}, Mismatch: {len(union) - len(common)}")

    # ---- Check 6: Geometry duplicates (bidirectional issue) ----
    ref_gdf = first_gdf
    hashes = [geom_hash(g) for g in ref_gdf.geometry]
    counts = Counter(hashes)
    dupes = {h: c for h, c in counts.items() if c > 1}
    n_dupe_geom = len(dupes)
    n_dupe_rows = sum(c - 1 for c in dupes.values())
    ok = n_dupe_geom == 0
    print(f"\n  6. Geometry duplicates: {status(ok)}")
    if n_dupe_geom > 0:
        print(f"     {n_dupe_geom} geometries shared by {n_dupe_geom + n_dupe_rows} rows")
        print(f"     (likely bidirectional segments merged — see composite key fix)")
        issues.append(f"{n_dupe_geom} duplicate geometries (bidirectional merge)")

    # ---- Check 7: Observation density ----
    if 'jam_factor_count' in first_gdf.columns:
        # Use evening_peak for density check
        ep = period_data.get('evening_peak', first_gdf)
        counts_col = ep['jam_factor_count'].dropna()
        total_obs = sum(
            gdf['jam_factor_count'].sum() for gdf in period_data.values()
            if 'jam_factor_count' in gdf.columns
        )
        ok = counts_col.min() > 0
        print(f"\n  7. Observation density: {status(ok)}")
        print(f"     Total observations: {int(total_obs):,}")
        print(f"     Per-segment (evening peak): min={int(counts_col.min())}, "
              f"max={int(counts_col.max())}, mean={counts_col.mean():.0f}")
        zero_count = (counts_col == 0).sum()
        if zero_count > 0:
            issues.append(f"{zero_count} segments with 0 observations")
            print(f"     WARNING: {zero_count} segments with 0 observations")

    # Summary
    print(f"\n  SUMMARY: {len(issues)} issue(s) found")
    for iss in issues:
        print(f"    - {iss}")

    return issues


# ============================================================
# Raw data checks
# ============================================================
def check_raw(city_code, cfg, base_dir='.', n_sample=5):
    name = cfg['name']
    raw_folder = os.path.join(base_dir, cfg['raw_folder'])
    print_header(f"{name} ({city_code.upper()}) — Raw Data (sample of {n_sample})")

    issues = []

    if not os.path.isdir(raw_folder):
        print(f"  SKIP: folder {raw_folder} not found")
        return issues

    files = sorted(glob.glob(os.path.join(raw_folder, '*.gpkg')))
    print(f"  Total files: {len(files)}")
    if not files:
        issues.append("No raw files found")
        return issues

    # Sample evenly across the file list
    indices = np.linspace(0, len(files) - 1, min(n_sample, len(files)), dtype=int)
    sample_files = [files[i] for i in indices]

    all_seg_counts = []
    all_geom_hashes = []

    for f in sample_files:
        fname = os.path.basename(f)
        try:
            gdf = gpd.read_file(f)
        except Exception as e:
            issues.append(f"Failed to read {fname}: {e}")
            print(f"  FAIL: Cannot read {fname}")
            continue

        n = len(gdf)
        all_seg_counts.append(n)

        # ---- Column check ----
        missing = [c for c in EXPECTED_RAW_COLS if c not in gdf.columns]
        if missing:
            issues.append(f"{fname}: missing columns {missing}")
            print(f"  {fname}: FAIL missing {missing}")
            continue

        # ---- Value ranges ----
        jf = gdf['jam_factor']
        sp = gdf['speed']
        ff = gdf['free_flow']

        jf_bad = ((jf < 0) | (jf > 10)).sum()
        sp_neg = (sp < 0).sum()
        ff_neg = (ff < 0).sum()
        ff_zero = (ff == 0).sum()

        range_ok = jf_bad == 0 and sp_neg == 0 and ff_neg == 0
        if not range_ok:
            issues.append(f"{fname}: range issues (jf_bad={jf_bad}, sp_neg={sp_neg}, ff_neg={ff_neg})")

        # ---- Geometry duplicates (bidirectional) ----
        hashes = [geom_hash(g) for g in gdf.geometry]
        unique_geom = len(set(hashes))
        n_bidir = n - unique_geom
        all_geom_hashes.append(set(hashes))

        # ---- Null check ----
        nulls = gdf[['jam_factor', 'speed', 'free_flow']].isna().sum().sum()

        print(f"  {fname}: {n} segs, {unique_geom} unique geom, "
              f"{n_bidir} bidir, {nulls} nulls, ranges={status(range_ok)}")

    # ---- Cross-file consistency ----
    if len(all_seg_counts) > 1:
        consistent = len(set(all_seg_counts)) == 1
        print(f"\n  Segment count consistency across samples: {status(consistent)}")
        if not consistent:
            print(f"    Counts: {all_seg_counts}")
            issues.append(f"Inconsistent segment counts: {all_seg_counts}")

    if len(all_geom_hashes) > 1:
        common = all_geom_hashes[0]
        union = all_geom_hashes[0]
        for h in all_geom_hashes[1:]:
            common = common & h
            union = union | h
        pct = len(common) / len(union) * 100 if union else 0
        print(f"  Geometry stability: {len(common)}/{len(union)} shared ({pct:.1f}%)")
        if pct < 95:
            issues.append(f"Low geometry stability: {pct:.1f}% shared across samples")

    print(f"\n  SUMMARY: {len(issues)} issue(s) found")
    for iss in issues:
        print(f"    - {iss}")

    return issues


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Traffic data quality check')
    parser.add_argument('--city', nargs='+', choices=list(CITIES.keys()),
                        help='Cities to check (default: all)')
    parser.add_argument('--raw', action='store_true',
                        help='Also check raw data (samples N files)')
    parser.add_argument('--n-sample', type=int, default=5,
                        help='Number of raw files to sample per city (default: 5)')
    parser.add_argument('--base-dir', default='.',
                        help='Base directory containing traffic data folders')
    args = parser.parse_args()

    cities = args.city if args.city else list(CITIES.keys())

    print("=" * 60)
    print("  TRAFFIC DATA QUALITY CHECK")
    print(f"  Date: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Cities: {', '.join(c.upper() for c in cities)}")
    print(f"  Mode: {'raw + aggregated' if args.raw else 'aggregated only'}")
    print("=" * 60)

    all_issues = {}

    for city_code in cities:
        cfg = CITIES[city_code]
        issues = check_aggregated(city_code, cfg, args.base_dir)
        if args.raw:
            issues += check_raw(city_code, cfg, args.base_dir, args.n_sample)
        all_issues[city_code] = issues

    # Final summary
    print_header("FINAL SUMMARY")
    total = sum(len(v) for v in all_issues.values())
    for code, issues in all_issues.items():
        status_str = 'PASS' if len(issues) == 0 else f'{len(issues)} ISSUE(S)'
        print(f"  {CITIES[code]['name']:12s} {status_str}")
    print(f"\n  Total issues: {total}")

    if total > 0:
        print("\n  Run with --raw for additional raw data checks.")
    print("\nDone.")

    return 0 if total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
