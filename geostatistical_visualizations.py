#!/usr/bin/env python3
"""
Advanced Geostatistical Visualizations for Traffic Congestion Study

Generates:
1. Moran scatterplot (spatial lag vs. value)
2. Hotspot significance maps (p-value overlay)
3. Getis-Ord Gi* hotspot analysis
4. Spatial correlogram (Moran's I by distance bands)
"""

import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import contextily as ctx
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


def add_basemap(ax, gdf, zoom='auto', alpha=0.4):
    """Add OSM basemap to a matplotlib axes with geodata in EPSG:4326."""
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    try:
        ctx.add_basemap(
            ax, crs=gdf.crs,
            source=ctx.providers.CartoDB.Positron,
            zoom=zoom, alpha=alpha,
        )
    except Exception:
        pass  # Silently skip if tiles unavailable

# Import spatial statistics
try:
    from esda.moran import Moran, Moran_Local
    from esda.getisord import G_Local
    from libpysal.weights import KNN, DistanceBand
    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    print("ERROR: PySAL required. Install with: pip install esda libpysal")
    exit(1)

# Output directories
FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# City configurations
CITIES = {
    'smg': {'name': 'Semarang', 'folder': 'traffic_smg_output', 'color': '#2ecc71'},
    'bdg': {'name': 'Bandung', 'folder': 'traffic_bdg_output', 'color': '#3498db'},
    'jkt': {'name': 'Jakarta', 'folder': 'traffic_jkt_output', 'color': '#e74c3c'}
}


def load_traffic_data(city_code, period='evening_peak'):
    """Load traffic data for a city"""
    filepath = f"{CITIES[city_code]['folder']}/{period}_{city_code}.gpkg"
    gdf = gpd.read_file(filepath)
    # Create centroid geometry for spatial weights
    gdf['centroid'] = gdf.geometry.centroid
    return gdf


def create_spatial_weights(gdf, method='knn', k=8):
    """Create spatial weights matrix from centroids"""
    # Use centroids for weights calculation
    gdf_points = gdf.copy()
    gdf_points['geometry'] = gdf_points['centroid']

    if method == 'knn':
        w = KNN.from_dataframe(gdf_points, k=k)
    else:
        # Distance band - use median nearest neighbor distance
        from libpysal.weights import DistanceBand
        coords = np.array([[p.x, p.y] for p in gdf_points.geometry])
        from scipy.spatial import distance
        dists = distance.cdist(coords, coords)
        np.fill_diagonal(dists, np.inf)
        median_nn = np.median(np.min(dists, axis=1))
        w = DistanceBand.from_dataframe(gdf_points, threshold=median_nn * 1.5)

    w.transform = 'r'
    return w


def plot_moran_scatterplot(gdf, w, column='jam_factor_mean', city_code='smg'):
    """
    Create Moran scatterplot showing spatial lag vs. original values
    Quadrants: HH (upper right), LL (lower left), LH (upper left), HL (lower right)
    """
    city_name = CITIES[city_code]['name']
    y = gdf[column].values

    # Standardize values
    y_std = (y - y.mean()) / y.std()

    # Compute spatial lag
    y_lag = np.array([np.mean(y_std[list(w.neighbors[i])]) for i in range(len(y_std))])

    # Compute Moran's I
    mi = Moran(y, w)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 10))

    # Scatter plot with quadrant colors
    colors = []
    for i in range(len(y_std)):
        if y_std[i] >= 0 and y_lag[i] >= 0:
            colors.append('#d7191c')  # HH - red
        elif y_std[i] < 0 and y_lag[i] < 0:
            colors.append('#2c7bb6')  # LL - blue
        elif y_std[i] >= 0 and y_lag[i] < 0:
            colors.append('#fdae61')  # HL - orange
        else:
            colors.append('#abd9e9')  # LH - light blue

    ax.scatter(y_std, y_lag, c=colors, alpha=0.6, s=20, edgecolors='white', linewidth=0.5)

    # Add regression line (slope = Moran's I)
    ax.axhline(0, color='black', linewidth=0.5)
    ax.axvline(0, color='black', linewidth=0.5)

    # Regression line
    x_line = np.linspace(y_std.min(), y_std.max(), 100)
    y_line = mi.I * x_line
    ax.plot(x_line, y_line, 'r-', linewidth=2, label=f"Moran's I = {mi.I:.4f}")

    # Labels and title
    ax.set_xlabel('Standardized Jam Factor', fontsize=12)
    ax.set_ylabel('Spatial Lag of Jam Factor', fontsize=12)
    ax.set_title(f"{city_name} - Moran Scatterplot\n(I = {mi.I:.4f}, p = {mi.p_sim:.4f})",
                 fontsize=14, fontweight='bold')

    # Legend
    legend_elements = [
        mpatches.Patch(color='#d7191c', label='HH (High-High)'),
        mpatches.Patch(color='#2c7bb6', label='LL (Low-Low)'),
        mpatches.Patch(color='#fdae61', label='HL (High-Low)'),
        mpatches.Patch(color='#abd9e9', label='LH (Low-High)')
    ]
    ax.legend(handles=legend_elements, loc='upper left')

    ax.set_xlim(-4, 4)
    ax.set_ylim(-4, 4)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    filepath = FIGURES_DIR / f'{city_code}_moran_scatterplot.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")

    return mi


def plot_lisa_significance_map(gdf, w, column='jam_factor_mean', city_code='smg', alpha=0.05):
    """
    Create LISA significance map with p-value overlay
    Shows which clusters are statistically significant
    """
    city_name = CITIES[city_code]['name']
    y = gdf[column].values

    # Compute Local Moran's I
    lisa = Moran_Local(y, w, permutations=999)

    gdf = gdf.copy()
    gdf['lisa_I'] = lisa.Is
    gdf['lisa_p'] = lisa.p_sim
    gdf['lisa_q'] = lisa.q

    # Create significance categories
    def get_sig_category(p, q):
        if p >= alpha:
            return 'Not Significant'
        elif q == 1:
            return 'HH (p<0.05)'
        elif q == 3:
            return 'LL (p<0.05)'
        elif q == 4:
            return 'HL (p<0.05)'
        elif q == 2:
            return 'LH (p<0.05)'
        else:
            return 'Not Significant'

    gdf['sig_cluster'] = [get_sig_category(p, q) for p, q in zip(lisa.p_sim, lisa.q)]

    # Create figure with two panels
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # Left: Cluster map
    ax1 = axes[0]
    colors_map = {
        'HH (p<0.05)': '#d7191c',
        'LL (p<0.05)': '#2c7bb6',
        'HL (p<0.05)': '#fdae61',
        'LH (p<0.05)': '#abd9e9',
        'Not Significant': '#eeeeee'
    }

    for cluster_type in ['Not Significant', 'LH (p<0.05)', 'HL (p<0.05)', 'LL (p<0.05)', 'HH (p<0.05)']:
        subset = gdf[gdf['sig_cluster'] == cluster_type]
        if len(subset) > 0:
            subset.plot(ax=ax1, color=colors_map[cluster_type], linewidth=0.5)

    add_basemap(ax1, gdf)
    ax1.set_title(f'{city_name} - LISA Cluster Map\n(α = {alpha})', fontsize=12, fontweight='bold')
    ax1.set_axis_off()

    # Legend
    legend_elements = [mpatches.Patch(color=c, label=l) for l, c in colors_map.items()]
    ax1.legend(handles=legend_elements, loc='lower right', fontsize=9)

    # Right: P-value map
    ax2 = axes[1]

    # Custom colormap for p-values (reversed - low p = hot)
    cmap = plt.cm.RdYlGn_r
    norm = BoundaryNorm([0, 0.01, 0.05, 0.1, 0.5, 1.0], cmap.N)

    gdf.plot(column='lisa_p', ax=ax2, cmap=cmap, norm=norm, linewidth=0.5,
             legend=True, legend_kwds={'label': 'p-value', 'shrink': 0.7})

    add_basemap(ax2, gdf)
    ax2.set_title(f'{city_name} - LISA Significance (p-values)', fontsize=12, fontweight='bold')
    ax2.set_axis_off()

    plt.tight_layout()
    filepath = FIGURES_DIR / f'{city_code}_lisa_significance.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")

    # Count significant clusters
    sig_counts = gdf['sig_cluster'].value_counts()
    return sig_counts


def plot_getis_ord_gi(gdf, w, column='jam_factor_mean', city_code='smg'):
    """
    Compute and plot Getis-Ord Gi* hotspot analysis
    Alternative to LISA - focuses on clustering of high/low values
    """
    city_name = CITIES[city_code]['name']
    y = gdf[column].values

    # Compute Gi*
    gi = G_Local(y, w, star=True, permutations=999)

    gdf = gdf.copy()
    gdf['gi_z'] = gi.Zs
    gdf['gi_p'] = gi.p_sim

    # Classify hotspots/coldspots based on z-scores and p-values
    def classify_gi(z, p, alpha=0.05):
        if p >= alpha:
            return 'Not Significant'
        elif z > 2.58:
            return 'Hot Spot (99% CI)'
        elif z > 1.96:
            return 'Hot Spot (95% CI)'
        elif z > 1.65:
            return 'Hot Spot (90% CI)'
        elif z < -2.58:
            return 'Cold Spot (99% CI)'
        elif z < -1.96:
            return 'Cold Spot (95% CI)'
        elif z < -1.65:
            return 'Cold Spot (90% CI)'
        else:
            return 'Not Significant'

    gdf['gi_class'] = [classify_gi(z, p) for z, p in zip(gi.Zs, gi.p_sim)]

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # Left: Classification map
    ax1 = axes[0]
    colors_map = {
        'Hot Spot (99% CI)': '#d7191c',
        'Hot Spot (95% CI)': '#fdae61',
        'Hot Spot (90% CI)': '#fee08b',
        'Not Significant': '#eeeeee',
        'Cold Spot (90% CI)': '#d9ef8b',
        'Cold Spot (95% CI)': '#a6d96a',
        'Cold Spot (99% CI)': '#1a9641'
    }

    # Plot in order (not significant first, then by significance)
    plot_order = ['Not Significant', 'Cold Spot (90% CI)', 'Cold Spot (95% CI)', 'Cold Spot (99% CI)',
                  'Hot Spot (90% CI)', 'Hot Spot (95% CI)', 'Hot Spot (99% CI)']

    for gi_class in plot_order:
        subset = gdf[gdf['gi_class'] == gi_class]
        if len(subset) > 0:
            subset.plot(ax=ax1, color=colors_map[gi_class], linewidth=0.5)

    add_basemap(ax1, gdf)
    ax1.set_title(f'{city_name} - Getis-Ord Gi* Hotspot Analysis', fontsize=12, fontweight='bold')
    ax1.set_axis_off()

    # Legend (only for classes that exist)
    existing_classes = gdf['gi_class'].unique()
    legend_elements = [mpatches.Patch(color=colors_map[c], label=c)
                       for c in plot_order if c in existing_classes]
    ax1.legend(handles=legend_elements, loc='lower right', fontsize=8)

    # Right: Z-score map
    ax2 = axes[1]

    # Diverging colormap for z-scores
    vmax = max(abs(gdf['gi_z'].min()), abs(gdf['gi_z'].max()))
    gdf.plot(column='gi_z', ax=ax2, cmap='RdBu_r', vmin=-vmax, vmax=vmax,
             linewidth=0.5, legend=True, legend_kwds={'label': 'Gi* Z-score', 'shrink': 0.7})

    add_basemap(ax2, gdf)
    ax2.set_title(f'{city_name} - Gi* Z-scores', fontsize=12, fontweight='bold')
    ax2.set_axis_off()

    plt.tight_layout()
    filepath = FIGURES_DIR / f'{city_code}_getis_ord_gi.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")

    # Return summary
    class_counts = gdf['gi_class'].value_counts()
    return class_counts


def plot_spatial_correlogram(gdf, column='jam_factor_mean', city_code='smg', n_bands=10):
    """
    Create spatial correlogram showing Moran's I at different distance bands
    Reveals how spatial autocorrelation decays with distance
    """
    city_name = CITIES[city_code]['name']
    y = gdf[column].values

    # Get centroid coordinates
    coords = np.array([[p.x, p.y] for p in gdf['centroid']])

    # Calculate pairwise distances
    from scipy.spatial import distance
    dists = distance.cdist(coords, coords)

    # Determine distance bands
    max_dist = np.percentile(dists[dists > 0], 50)  # Use median distance as max
    band_edges = np.linspace(0, max_dist, n_bands + 1)
    band_centers = (band_edges[:-1] + band_edges[1:]) / 2

    # Convert to approximate km (at equator, 1 degree ≈ 111 km)
    band_centers_km = band_centers * 111

    # Compute Moran's I for each distance band
    morans_i = []
    morans_p = []

    print(f"  Computing correlogram for {city_name}...")
    for i in range(len(band_edges) - 1):
        try:
            # Create distance band weights
            w = DistanceBand.from_array(coords, threshold=band_edges[i+1],
                                        lower_bound=band_edges[i], binary=True)
            if w.n > 0 and w.max_neighbors > 0:
                w.transform = 'r'
                mi = Moran(y, w, permutations=99)
                morans_i.append(mi.I)
                morans_p.append(mi.p_sim)
            else:
                morans_i.append(np.nan)
                morans_p.append(np.nan)
        except Exception as e:
            morans_i.append(np.nan)
            morans_p.append(np.nan)

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot Moran's I values
    valid_mask = ~np.isnan(morans_i)
    ax.plot(band_centers_km[valid_mask], np.array(morans_i)[valid_mask],
            'o-', color=CITIES[city_code]['color'], linewidth=2, markersize=8)

    # Mark significant values
    sig_mask = np.array(morans_p) < 0.05
    combined_mask = valid_mask & sig_mask
    ax.scatter(band_centers_km[combined_mask], np.array(morans_i)[combined_mask],
               s=100, facecolors='none', edgecolors='red', linewidth=2,
               label='Significant (p<0.05)', zorder=5)

    # Reference line at 0
    ax.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)

    # Labels
    ax.set_xlabel('Distance Band (km)', fontsize=12)
    ax.set_ylabel("Moran's I", fontsize=12)
    ax.set_title(f"{city_name} - Spatial Correlogram\n(Moran's I by Distance)",
                 fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    filepath = FIGURES_DIR / f'{city_code}_correlogram.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")

    return pd.DataFrame({
        'distance_km': band_centers_km,
        'morans_i': morans_i,
        'p_value': morans_p
    })


def create_combined_summary_figure(city_code='smg'):
    """Create a combined 2x2 summary figure with all analyses"""
    # This assumes individual figures have been created
    # We'll create a summary combining key visualizations
    pass


def main():
    print("=" * 70)
    print("ADVANCED GEOSTATISTICAL VISUALIZATIONS")
    print("=" * 70)

    all_results = {}

    for city_code in CITIES.keys():
        city_name = CITIES[city_code]['name']
        print(f"\n{'='*50}")
        print(f"Processing {city_name}...")
        print(f"{'='*50}")

        # Load data
        print(f"\n  Loading traffic data...")
        gdf = load_traffic_data(city_code, 'evening_peak')
        print(f"  Loaded {len(gdf)} segments")

        # Create spatial weights
        print(f"  Creating spatial weights (KNN, k=8)...")
        w = create_spatial_weights(gdf, method='knn', k=8)

        # 1. Moran Scatterplot
        print(f"\n  1. Generating Moran scatterplot...")
        mi = plot_moran_scatterplot(gdf, w, 'jam_factor_mean', city_code)

        # 2. LISA Significance Map
        print(f"  2. Generating LISA significance map...")
        lisa_counts = plot_lisa_significance_map(gdf, w, 'jam_factor_mean', city_code)

        # 3. Getis-Ord Gi*
        print(f"  3. Generating Getis-Ord Gi* analysis...")
        gi_counts = plot_getis_ord_gi(gdf, w, 'jam_factor_mean', city_code)

        # 4. Spatial Correlogram
        print(f"  4. Generating spatial correlogram...")
        correlogram = plot_spatial_correlogram(gdf, 'jam_factor_mean', city_code, n_bands=10)

        all_results[city_code] = {
            'morans_i': mi.I,
            'morans_p': mi.p_sim,
            'lisa_counts': lisa_counts,
            'gi_counts': gi_counts,
            'correlogram': correlogram
        }

    # Save summary results
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for city_code, results in all_results.items():
        city_name = CITIES[city_code]['name']
        print(f"\n{city_name}:")
        print(f"  Global Moran's I: {results['morans_i']:.4f} (p = {results['morans_p']:.4f})")
        print(f"  Gi* Hotspots (95%+): {results['gi_counts'].get('Hot Spot (99% CI)', 0) + results['gi_counts'].get('Hot Spot (95% CI)', 0)}")
        print(f"  Gi* Coldspots (95%+): {results['gi_counts'].get('Cold Spot (99% CI)', 0) + results['gi_counts'].get('Cold Spot (95% CI)', 0)}")

    print("\n" + "=" * 70)
    print("FIGURES GENERATED")
    print("=" * 70)
    print(f"\nAll figures saved to: {FIGURES_DIR.absolute()}")
    print("\nNew figures:")
    print("  - *_moran_scatterplot.png   : Moran scatterplot with quadrants")
    print("  - *_lisa_significance.png   : LISA clusters with p-values")
    print("  - *_getis_ord_gi.png        : Getis-Ord Gi* hotspot analysis")
    print("  - *_correlogram.png         : Spatial correlogram")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
