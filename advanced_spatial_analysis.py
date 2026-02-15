#!/usr/bin/env python3
"""
Advanced Spatial Analysis for Traffic Congestion Study
Computes: Moran's I, LISA, Centrality-Congestion Correlations, ANOVA

This script fills in the missing analyses for the research paper.
"""

import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Try to import spatial statistics libraries
try:
    from esda.moran import Moran, Moran_Local
    from libpysal.weights import Queen, KNN
    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    print("WARNING: PySAL not installed. Install with: pip install esda libpysal")

# Output directory
OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# City configurations
CITIES = {
    'smg': {'name': 'Semarang', 'folder': 'traffic_smg_output', 'color': '#2ecc71',
            'osm_network': 'osm_network_semarang.gpkg'},
    'bdg': {'name': 'Bandung', 'folder': 'traffic_bdg_output', 'color': '#3498db',
            'osm_network': 'osm_network_bandung.gpkg'},
    'jkt': {'name': 'Jakarta', 'folder': 'traffic_jkt_output', 'color': '#e74c3c',
            'osm_network': 'osm_network_jakarta.gpkg'}
}

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]


def load_traffic_data(city_code, period='evening_peak'):
    """Load traffic data for a city and period"""
    filepath = f"{CITIES[city_code]['folder']}/{period}_{city_code}.gpkg"
    return gpd.read_file(filepath)


def compute_global_morans_i(gdf, column='jam_factor_mean', weight_type='knn', k=8):
    """
    Compute Global Moran's I statistic for spatial autocorrelation

    Parameters:
    -----------
    gdf : GeoDataFrame
        Traffic data with geometry
    column : str
        Column to analyze
    weight_type : str
        'queen' for polygon contiguity or 'knn' for k-nearest neighbors
    k : int
        Number of neighbors for KNN weights

    Returns:
    --------
    dict : Moran's I results
    """
    if not PYSAL_AVAILABLE:
        return None

    # Get values
    y = gdf[column].values

    # Create spatial weights
    # For line geometries, use KNN based on centroids
    gdf_temp = gdf.copy()
    gdf_temp['geometry'] = gdf_temp.geometry.centroid

    try:
        if weight_type == 'queen':
            # Queen contiguity (for polygons)
            w = Queen.from_dataframe(gdf_temp)
        else:
            # K-nearest neighbors (better for line/point data)
            w = KNN.from_dataframe(gdf_temp, k=k)

        # Row-standardize weights
        w.transform = 'r'

        # Compute Moran's I
        mi = Moran(y, w)

        return {
            'I': mi.I,
            'Expected_I': mi.EI,
            'Variance': mi.VI_norm,
            'z_score': mi.z_norm,
            'p_value': mi.p_norm,
            'n': len(y)
        }
    except Exception as e:
        print(f"  Error computing Moran's I: {e}")
        return None


def compute_lisa(gdf, column='jam_factor_mean', k=8, alpha=0.05):
    """
    Compute Local Indicators of Spatial Association (LISA)

    Returns GeoDataFrame with LISA classifications:
    - HH: High-High (hotspot)
    - LL: Low-Low (coldspot)
    - HL: High-Low (spatial outlier)
    - LH: Low-High (spatial outlier)
    - NS: Not significant
    """
    if not PYSAL_AVAILABLE:
        return gdf, None

    gdf = gdf.copy()
    y = gdf[column].values

    # Create KNN weights from centroids
    gdf_temp = gdf.copy()
    gdf_temp['geometry'] = gdf_temp.geometry.centroid

    try:
        w = KNN.from_dataframe(gdf_temp, k=k)
        w.transform = 'r'

        # Compute Local Moran's I
        lisa = Moran_Local(y, w, permutations=999)

        # Get quadrant classifications
        # q values: 1=HH, 2=LH, 3=LL, 4=HL
        quadrant_labels = {1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}

        gdf['lisa_I'] = lisa.Is
        gdf['lisa_q'] = lisa.q
        gdf['lisa_p'] = lisa.p_sim
        gdf['lisa_sig'] = lisa.p_sim < alpha

        # Create classification labels
        gdf['lisa_cluster'] = 'NS'  # Not significant
        for idx in range(len(gdf)):
            if gdf.iloc[idx]['lisa_sig']:
                q = int(gdf.iloc[idx]['lisa_q'])
                gdf.iloc[idx, gdf.columns.get_loc('lisa_cluster')] = quadrant_labels.get(q, 'NS')

        # Count clusters
        cluster_counts = gdf['lisa_cluster'].value_counts()

        return gdf, {
            'cluster_counts': cluster_counts.to_dict(),
            'significant_count': int(gdf['lisa_sig'].sum()),
            'total_count': len(gdf)
        }

    except Exception as e:
        print(f"  Error computing LISA: {e}")
        return gdf, None


def plot_lisa_map(gdf, city_code, period='evening_peak'):
    """Plot LISA cluster map"""
    city_name = CITIES[city_code]['name']

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Left: Traffic intensity
    ax1 = axes[0]
    gdf.plot(column='jam_factor_mean', cmap='RdYlGn_r', linewidth=0.8, ax=ax1,
             legend=True, legend_kwds={'label': 'Jam Factor', 'shrink': 0.7})
    ax1.set_title(f'{city_name} - Traffic Intensity\n(Evening Peak)', fontsize=12, fontweight='bold')
    ax1.set_axis_off()

    # Right: LISA clusters
    ax2 = axes[1]

    # Define colors for each cluster type
    colors = {'HH': '#d7191c', 'LL': '#2c7bb6', 'HL': '#fdae61', 'LH': '#abd9e9', 'NS': '#eeeeee'}

    for cluster_type, color in colors.items():
        subset = gdf[gdf['lisa_cluster'] == cluster_type]
        if len(subset) > 0:
            subset.plot(ax=ax2, color=color, linewidth=0.8, label=f'{cluster_type} ({len(subset)})')

    ax2.set_title(f'{city_name} - LISA Clusters\n(p < 0.05)', fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right', title='Cluster Type')
    ax2.set_axis_off()

    plt.tight_layout()
    filepath = FIGURES_DIR / f'{city_code}_lisa_clusters.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def compute_centrality_correlations(city_code):
    """
    Compute correlations between network centrality and traffic congestion
    by spatially joining OSMnx edges with traffic segments
    """
    city_name = CITIES[city_code]['name']
    osm_file = CITIES[city_code]['osm_network']

    # Check if OSM network file exists
    if not Path(osm_file).exists():
        print(f"  OSM network file not found: {osm_file}")
        return None

    # Load OSM edges with centrality
    try:
        osm_edges = gpd.read_file(osm_file, layer='edges')
    except Exception as e:
        print(f"  Error loading OSM edges: {e}")
        return None

    # Load traffic data
    traffic = load_traffic_data(city_code, 'evening_peak')

    # Ensure same CRS
    if osm_edges.crs != traffic.crs:
        osm_edges = osm_edges.to_crs(traffic.crs)

    # Check if betweenness is in OSM data
    if 'betweenness' not in osm_edges.columns:
        print(f"  Computing betweenness centrality for {city_name}...")
        # We need to recompute - this would require loading the full graph
        # For now, skip if not precomputed
        print(f"  Betweenness not precomputed in {osm_file}")
        return None

    # Spatial join: find nearest OSM edge for each traffic segment
    # Use buffer-based approach for line-to-line matching
    traffic_centroids = traffic.copy()
    traffic_centroids['geometry'] = traffic_centroids.geometry.centroid

    osm_centroids = osm_edges.copy()
    osm_centroids['geometry'] = osm_centroids.geometry.centroid

    # Nearest join
    joined = gpd.sjoin_nearest(
        traffic_centroids[['geometry', 'jam_factor_mean']],
        osm_centroids[['geometry', 'betweenness']],
        how='left',
        distance_col='match_distance'
    )

    # Filter matches within reasonable distance (e.g., 100m)
    max_distance = 0.001  # roughly 100m in degrees
    joined = joined[joined['match_distance'] < max_distance]

    if len(joined) < 10:
        print(f"  Too few matches ({len(joined)}) for correlation")
        return None

    # Compute correlations
    jam_factor = joined['jam_factor_mean'].values
    betweenness = joined['betweenness'].values

    # Remove NaN values
    mask = ~(np.isnan(jam_factor) | np.isnan(betweenness))
    jam_factor = jam_factor[mask]
    betweenness = betweenness[mask]

    if len(jam_factor) < 10:
        print(f"  Too few valid values for correlation")
        return None

    pearson_r, pearson_p = stats.pearsonr(jam_factor, betweenness)
    spearman_r, spearman_p = stats.spearmanr(jam_factor, betweenness)

    return {
        'n_matched': len(jam_factor),
        'pearson_r': pearson_r,
        'pearson_p': pearson_p,
        'spearman_r': spearman_r,
        'spearman_p': spearman_p
    }


def run_anova_analysis(all_city_data):
    """
    Run one-way ANOVA and Tukey HSD tests for temporal period differences
    """
    results = {}

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']
        print(f"\n  {city_name}:")

        # Collect mean jam factors for each period
        period_means = {}
        period_values = []

        for period in TIME_PERIODS:
            values = data[period]['jam_factor_mean'].dropna().values
            period_means[period] = values
            period_values.append(values)

        # One-way ANOVA
        f_stat, p_value = stats.f_oneway(*period_values)
        print(f"    ANOVA: F={f_stat:.2f}, p={p_value:.2e}")

        # Tukey HSD (using scipy's implementation)
        # Combine all values with group labels
        all_values = []
        all_groups = []
        for i, period in enumerate(TIME_PERIODS):
            vals = period_means[period]
            all_values.extend(vals)
            all_groups.extend([i] * len(vals))

        # Perform Tukey HSD
        try:
            from scipy.stats import tukey_hsd
            tukey_result = tukey_hsd(*period_values)

            # Find significant pairs
            sig_pairs = []
            for i in range(len(TIME_PERIODS)):
                for j in range(i+1, len(TIME_PERIODS)):
                    p_adj = tukey_result.pvalue[i, j]
                    if p_adj < 0.05:
                        sig_pairs.append((TIME_PERIODS[i], TIME_PERIODS[j], p_adj))

            print(f"    Significant period pairs (p<0.05): {len(sig_pairs)}")

            results[city_code] = {
                'f_statistic': f_stat,
                'p_value': p_value,
                'significant_pairs': len(sig_pairs),
                'total_pairs': len(TIME_PERIODS) * (len(TIME_PERIODS) - 1) // 2
            }
        except ImportError:
            # Fallback if tukey_hsd not available
            print(f"    Tukey HSD requires scipy >= 1.8")
            results[city_code] = {
                'f_statistic': f_stat,
                'p_value': p_value,
                'significant_pairs': None,
                'total_pairs': None
            }

    return results


def generate_results_report(moran_results, lisa_results, corr_results, anova_results):
    """Generate a comprehensive results report"""
    report = []
    report.append("=" * 80)
    report.append("ADVANCED SPATIAL ANALYSIS RESULTS")
    report.append("=" * 80)
    report.append("")

    # Moran's I results
    report.append("1. GLOBAL MORAN'S I (Spatial Autocorrelation)")
    report.append("-" * 60)
    report.append(f"{'City':<12} {'Moran I':>10} {'Z-score':>10} {'p-value':>12} {'Interpretation'}")
    report.append("-" * 60)

    for city_code, result in moran_results.items():
        city_name = CITIES[city_code]['name']
        if result:
            interp = "Clustered" if result['I'] > 0 and result['p_value'] < 0.05 else "Random"
            report.append(f"{city_name:<12} {result['I']:>10.4f} {result['z_score']:>10.2f} "
                         f"{result['p_value']:>12.2e} {interp}")
        else:
            report.append(f"{city_name:<12} {'N/A':>10} {'N/A':>10} {'N/A':>12}")

    report.append("")

    # LISA results
    report.append("2. LISA CLUSTER ANALYSIS (Local Moran's I)")
    report.append("-" * 60)

    for city_code, result in lisa_results.items():
        city_name = CITIES[city_code]['name']
        if result:
            report.append(f"\n{city_name}:")
            report.append(f"  Total segments: {result['total_count']}")
            report.append(f"  Significant clusters (p<0.05): {result['significant_count']}")
            for cluster, count in result['cluster_counts'].items():
                report.append(f"    {cluster}: {count}")

    report.append("")

    # Centrality correlations
    report.append("3. CENTRALITY-CONGESTION CORRELATIONS")
    report.append("-" * 60)
    report.append(f"{'City':<12} {'n':>8} {'Pearson r':>12} {'p-value':>12} {'Spearman r':>12} {'p-value':>12}")
    report.append("-" * 72)

    for city_code, result in corr_results.items():
        city_name = CITIES[city_code]['name']
        if result:
            report.append(f"{city_name:<12} {result['n_matched']:>8} {result['pearson_r']:>12.4f} "
                         f"{result['pearson_p']:>12.4f} {result['spearman_r']:>12.4f} {result['spearman_p']:>12.4f}")
        else:
            report.append(f"{city_name:<12} {'N/A':>8} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>12}")

    report.append("")

    # ANOVA results
    report.append("4. ANOVA RESULTS (Temporal Period Differences)")
    report.append("-" * 60)
    report.append(f"{'City':<12} {'F-statistic':>12} {'p-value':>15} {'Sig. pairs':>12}")
    report.append("-" * 55)

    for city_code, result in anova_results.items():
        city_name = CITIES[city_code]['name']
        sig_pairs = result['significant_pairs'] if result['significant_pairs'] else 'N/A'
        report.append(f"{city_name:<12} {result['f_statistic']:>12.2f} {result['p_value']:>15.2e} "
                     f"{sig_pairs:>12}")

    report.append("")
    report.append("=" * 80)

    report_text = "\n".join(report)

    # Save report
    filepath = OUTPUT_DIR / 'advanced_analysis_results.txt'
    with open(filepath, 'w') as f:
        f.write(report_text)
    print(f"\nSaved: {filepath}")

    return report_text


def main():
    print("=" * 70)
    print("ADVANCED SPATIAL ANALYSIS")
    print("Computing: Moran's I, LISA, Centrality Correlations, ANOVA")
    print("=" * 70)

    if not PYSAL_AVAILABLE:
        print("\nERROR: PySAL libraries required. Install with:")
        print("  pip install esda libpysal")
        print("\nContinuing with available analyses...")

    # Load all data
    print("\n1. Loading traffic data...")
    all_city_data = {}
    for city_code in CITIES.keys():
        city_data = {}
        for period in TIME_PERIODS:
            city_data[period] = load_traffic_data(city_code, period)
        all_city_data[city_code] = city_data
        print(f"  Loaded {CITIES[city_code]['name']}")

    # Compute Global Moran's I
    print("\n2. Computing Global Moran's I...")
    moran_results = {}
    for city_code in CITIES.keys():
        print(f"  {CITIES[city_code]['name']}...")
        gdf = all_city_data[city_code]['evening_peak']
        result = compute_global_morans_i(gdf, 'jam_factor_mean', weight_type='knn', k=8)
        moran_results[city_code] = result
        if result:
            print(f"    Moran's I = {result['I']:.4f}, z = {result['z_score']:.2f}, p = {result['p_value']:.4f}")

    # Compute LISA
    print("\n3. Computing LISA clusters...")
    lisa_results = {}
    for city_code in CITIES.keys():
        print(f"  {CITIES[city_code]['name']}...")
        gdf = all_city_data[city_code]['evening_peak']
        gdf_lisa, result = compute_lisa(gdf, 'jam_factor_mean', k=8)
        lisa_results[city_code] = result
        if result:
            print(f"    Significant clusters: {result['significant_count']}/{result['total_count']}")
            # Update data and plot
            all_city_data[city_code]['evening_peak'] = gdf_lisa
            plot_lisa_map(gdf_lisa, city_code, 'evening_peak')

    # Compute centrality correlations
    print("\n4. Computing centrality-congestion correlations...")
    corr_results = {}
    for city_code in CITIES.keys():
        print(f"  {CITIES[city_code]['name']}...")
        result = compute_centrality_correlations(city_code)
        corr_results[city_code] = result
        if result:
            print(f"    Pearson r = {result['pearson_r']:.4f}, Spearman r = {result['spearman_r']:.4f}")

    # Run ANOVA
    print("\n5. Running ANOVA analysis...")
    anova_results = run_anova_analysis(all_city_data)

    # Generate report
    print("\n6. Generating results report...")
    report = generate_results_report(moran_results, lisa_results, corr_results, anova_results)
    print("\n" + report)

    # Save results as CSV for manuscript
    print("\n7. Saving results for manuscript...")

    # Moran's I table
    moran_df = pd.DataFrame([
        {
            'City': CITIES[code]['name'],
            'Moran_I': r['I'] if r else None,
            'Z_score': r['z_score'] if r else None,
            'p_value': r['p_value'] if r else None
        }
        for code, r in moran_results.items()
    ])
    moran_df.to_csv(OUTPUT_DIR / 'morans_i_results.csv', index=False)
    print(f"  Saved: {OUTPUT_DIR / 'morans_i_results.csv'}")

    # LISA summary table
    lisa_df = pd.DataFrame([
        {
            'City': CITIES[code]['name'],
            'HH_Hotspots': r['cluster_counts'].get('HH', 0) if r else None,
            'LL_Coldspots': r['cluster_counts'].get('LL', 0) if r else None,
            'HL_Outliers': r['cluster_counts'].get('HL', 0) if r else None,
            'LH_Outliers': r['cluster_counts'].get('LH', 0) if r else None,
            'Not_Significant': r['cluster_counts'].get('NS', 0) if r else None
        }
        for code, r in lisa_results.items()
    ])
    lisa_df.to_csv(OUTPUT_DIR / 'lisa_results.csv', index=False)
    print(f"  Saved: {OUTPUT_DIR / 'lisa_results.csv'}")

    # ANOVA table
    anova_df = pd.DataFrame([
        {
            'City': CITIES[code]['name'],
            'F_statistic': r['f_statistic'],
            'p_value': r['p_value'],
            'Significant_pairs': r['significant_pairs']
        }
        for code, r in anova_results.items()
    ])
    anova_df.to_csv(OUTPUT_DIR / 'anova_results.csv', index=False)
    print(f"  Saved: {OUTPUT_DIR / 'anova_results.csv'}")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE!")
    print(f"Results saved to: {OUTPUT_DIR.absolute()}")
    print(f"Figures saved to: {FIGURES_DIR.absolute()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
