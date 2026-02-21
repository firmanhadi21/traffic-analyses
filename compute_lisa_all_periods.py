#!/usr/bin/env python3
"""
Compute LISA (Local Indicators of Spatial Association) for all cities and periods.

This script computes Moran_Local for each of the 24 GeoPackage files (3 cities × 8 periods)
and saves the results with LISA classifications for use in spatiotemporal analysis.

Output: lisa_results/{city}_{period}_lisa.gpkg with columns:
    - geometry
    - jam_factor_mean
    - lisa_I: Local Moran's I statistic
    - lisa_q: Quadrant (1=HH, 2=LH, 3=LL, 4=HL)
    - lisa_p: Pseudo p-value from permutation test
    - lisa_cluster: Classification label (HH, LL, HL, LH, NS)
"""

import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

try:
    from esda.moran import Moran_Local
    from libpysal.weights import KNN
    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    print("ERROR: PySAL not installed. Install with:")
    print("  pip install esda libpysal")
    sys.exit(1)


# Configuration
BASE_DIR = Path("/Users/macbook/Dropbox/GitHub/traffic-analyses")
INPUT_DIR = BASE_DIR / "zenodo_data"
OUTPUT_DIR = BASE_DIR / "lisa_results"

CITIES = {
    'jkt': {'name': 'Jakarta', 'dir': 'traffic_jkt_output'},
    'bdg': {'name': 'Bandung', 'dir': 'traffic_bdg_output'},
    'smg': {'name': 'Semarang', 'dir': 'traffic_smg_output'},
}

PERIODS = [
    'night',
    'morning_peak',
    'morning_offpeak',
    'lunch_hours',
    'afternoon_offpeak',
    'evening_peak',
    'evening_offpeak',
    'late_night',
]

# LISA parameters
K_NEIGHBORS = 8
PERMUTATIONS = 999
ALPHA = 0.05


def compute_lisa(gdf: gpd.GeoDataFrame, column: str = 'jam_factor_mean',
                 k: int = K_NEIGHBORS, permutations: int = PERMUTATIONS,
                 alpha: float = ALPHA) -> gpd.GeoDataFrame:
    """
    Compute LISA for a GeoDataFrame.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input data with geometry and jam_factor_mean column
    column : str
        Column to analyze
    k : int
        Number of nearest neighbors for spatial weights
    permutations : int
        Number of permutations for pseudo p-value
    alpha : float
        Significance level

    Returns
    -------
    GeoDataFrame with LISA results added
    """
    gdf = gdf.copy()
    y = gdf[column].values

    # Handle any NaN values
    if np.isnan(y).any():
        print(f"    Warning: {np.isnan(y).sum()} NaN values found, filling with mean")
        y = np.nan_to_num(y, nan=np.nanmean(y))

    # Create KNN weights from centroids
    gdf_centroids = gdf.copy()
    gdf_centroids['geometry'] = gdf_centroids.geometry.centroid

    # Build spatial weights
    w = KNN.from_dataframe(gdf_centroids, k=k)
    w.transform = 'r'  # Row-standardize

    # Compute Local Moran's I
    lisa = Moran_Local(y, w, permutations=permutations)

    # Quadrant labels: 1=HH, 2=LH, 3=LL, 4=HL
    quadrant_labels = {1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}

    # Add LISA results to GeoDataFrame
    gdf['lisa_I'] = lisa.Is
    gdf['lisa_q'] = lisa.q
    gdf['lisa_p'] = lisa.p_sim
    gdf['lisa_sig'] = lisa.p_sim < alpha

    # Create classification labels
    gdf['lisa_cluster'] = 'NS'  # Default: Not Significant
    for idx in range(len(gdf)):
        if gdf.iloc[idx]['lisa_sig']:
            q = int(gdf.iloc[idx]['lisa_q'])
            gdf.at[gdf.index[idx], 'lisa_cluster'] = quadrant_labels.get(q, 'NS')

    return gdf


def process_all_files():
    """Process all 24 GeoPackage files and compute LISA."""

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    results_summary = []
    total_files = len(CITIES) * len(PERIODS)
    processed = 0

    print("=" * 60)
    print("LISA Computation for All Cities and Periods")
    print("=" * 60)
    print(f"Cities: {list(CITIES.keys())}")
    print(f"Periods: {len(PERIODS)}")
    print(f"Total files to process: {total_files}")
    print(f"Parameters: k={K_NEIGHBORS}, permutations={PERMUTATIONS}, alpha={ALPHA}")
    print("=" * 60)

    start_time = time.time()

    for city_code, city_info in CITIES.items():
        city_name = city_info['name']
        city_dir = INPUT_DIR / city_info['dir']

        print(f"\n{'='*40}")
        print(f"Processing {city_name}")
        print(f"{'='*40}")

        for period in PERIODS:
            processed += 1

            # Input file
            input_file = city_dir / f"{period}_{city_code}.gpkg"

            if not input_file.exists():
                print(f"  [{processed}/{total_files}] SKIP: {input_file.name} not found")
                continue

            print(f"  [{processed}/{total_files}] Processing {period}...", end=" ", flush=True)

            try:
                # Load data
                gdf = gpd.read_file(input_file)
                n_segments = len(gdf)

                # Compute LISA
                t0 = time.time()
                gdf_lisa = compute_lisa(gdf)
                elapsed = time.time() - t0

                # Count clusters
                cluster_counts = gdf_lisa['lisa_cluster'].value_counts().to_dict()

                # Save output
                output_file = OUTPUT_DIR / f"{city_code}_{period}_lisa.gpkg"

                # Select columns to save
                cols_to_save = ['geometry', 'jam_factor_mean', 'lisa_I', 'lisa_q', 'lisa_p', 'lisa_cluster']
                gdf_lisa[cols_to_save].to_file(output_file, driver='GPKG')

                print(f"done ({elapsed:.1f}s) - HH:{cluster_counts.get('HH', 0)}, "
                      f"LL:{cluster_counts.get('LL', 0)}, "
                      f"HL:{cluster_counts.get('HL', 0)}, "
                      f"LH:{cluster_counts.get('LH', 0)}, "
                      f"NS:{cluster_counts.get('NS', 0)}")

                # Store summary
                results_summary.append({
                    'city': city_code,
                    'city_name': city_name,
                    'period': period,
                    'n_segments': n_segments,
                    'HH': cluster_counts.get('HH', 0),
                    'LL': cluster_counts.get('LL', 0),
                    'HL': cluster_counts.get('HL', 0),
                    'LH': cluster_counts.get('LH', 0),
                    'NS': cluster_counts.get('NS', 0),
                    'sig_total': n_segments - cluster_counts.get('NS', 0),
                    'sig_pct': (n_segments - cluster_counts.get('NS', 0)) / n_segments * 100,
                })

            except Exception as e:
                print(f"ERROR: {e}")
                continue

    total_time = time.time() - start_time

    # Save summary CSV
    if results_summary:
        summary_df = pd.DataFrame(results_summary)
        summary_file = OUTPUT_DIR / "lisa_summary_all_periods.csv"
        summary_df.to_csv(summary_file, index=False)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total processing time: {total_time:.1f} seconds")
        print(f"Files processed: {len(results_summary)}/{total_files}")
        print(f"\nResults saved to: {OUTPUT_DIR}")
        print(f"Summary CSV: {summary_file}")

        # Print summary table
        print("\n" + "-" * 80)
        print(f"{'City':<10} {'Period':<20} {'Segments':>10} {'HH':>6} {'LL':>6} {'HL':>6} {'LH':>6} {'Sig%':>8}")
        print("-" * 80)
        for r in results_summary:
            print(f"{r['city']:<10} {r['period']:<20} {r['n_segments']:>10} "
                  f"{r['HH']:>6} {r['LL']:>6} {r['HL']:>6} {r['LH']:>6} {r['sig_pct']:>7.1f}%")
        print("-" * 80)


def create_combined_dataset():
    """
    Create a combined dataset with LISA classifications across all periods.
    Useful for LISA Markov analysis.
    """
    print("\n" + "=" * 60)
    print("Creating Combined Dataset for Markov Analysis")
    print("=" * 60)

    for city_code, city_info in CITIES.items():
        city_name = city_info['name']
        print(f"\nProcessing {city_name}...")

        # Load first period to get geometry
        first_file = OUTPUT_DIR / f"{city_code}_{PERIODS[0]}_lisa.gpkg"
        if not first_file.exists():
            print(f"  Skipping - LISA files not found")
            continue

        base_gdf = gpd.read_file(first_file)[['geometry', 'jam_factor_mean']]
        base_gdf = base_gdf.rename(columns={'jam_factor_mean': f'jf_{PERIODS[0]}'})

        # Add LISA cluster for first period
        lisa_gdf = gpd.read_file(first_file)
        base_gdf[f'lisa_{PERIODS[0]}'] = lisa_gdf['lisa_cluster']

        # Load remaining periods
        for period in PERIODS[1:]:
            period_file = OUTPUT_DIR / f"{city_code}_{period}_lisa.gpkg"
            if period_file.exists():
                gdf = gpd.read_file(period_file)
                base_gdf[f'jf_{period}'] = gdf['jam_factor_mean']
                base_gdf[f'lisa_{period}'] = gdf['lisa_cluster']

        # Save combined file
        output_file = OUTPUT_DIR / f"{city_code}_combined_lisa.gpkg"
        base_gdf.to_file(output_file, driver='GPKG')
        print(f"  Saved: {output_file.name}")
        print(f"  Columns: {list(base_gdf.columns)}")

        # Also save as CSV for easier inspection (without geometry)
        csv_file = OUTPUT_DIR / f"{city_code}_lisa_timeseries.csv"
        lisa_cols = [c for c in base_gdf.columns if c.startswith('lisa_')]
        base_gdf[lisa_cols].to_csv(csv_file, index=True)
        print(f"  CSV: {csv_file.name}")


if __name__ == "__main__":
    # Step 1: Compute LISA for all files
    process_all_files()

    # Step 2: Create combined dataset for Markov analysis
    create_combined_dataset()

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print("\nNext steps for FOSS4G paper:")
    print("1. Use lisa_results/*_combined_lisa.gpkg for LISA Markov analysis")
    print("2. Install giddy: pip install giddy")
    print("3. Run spatiotemporal analysis with giddy.markov")
