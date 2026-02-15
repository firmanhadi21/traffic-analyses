#!/usr/bin/env python3
"""
POI-Congestion Analysis

Tests hypothesis: Congestion clusters around activity centers (jobs, shopping, schools)

Methodology:
1. Download POI data from OpenStreetMap (amenities, shops, offices, schools)
2. Compute POI density within buffer of each traffic segment
3. Correlate POI density with jam factor
4. Compare with centrality correlation (expecting POI > centrality)
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# City configurations (OSMnx 2.0 format: west, south, east, north)
CITIES = {
    'smg': {
        'name': 'Semarang',
        'bbox': (110.227, -7.105, 110.528, -6.919),
        'traffic_folder': 'traffic_smg_output',
        'color': '#2ecc71'
    },
    'bdg': {
        'name': 'Bandung',
        'bbox': (107.4688, -7.0848, 107.8261, -6.8294),
        'traffic_folder': 'traffic_bdg_output',
        'color': '#3498db'
    },
    'jkt': {
        'name': 'Jakarta',
        'bbox': (106.6036, -6.4096, 107.11, -6.0911),
        'traffic_folder': 'traffic_jkt_output',
        'color': '#e74c3c'
    }
}

# POI categories to analyze
POI_CATEGORIES = {
    'commercial': {
        'tags': {'shop': True},
        'description': 'Shops and retail'
    },
    'offices': {
        'tags': {'office': True},
        'description': 'Offices and workplaces'
    },
    'education': {
        'tags': {'amenity': ['school', 'university', 'college', 'kindergarten']},
        'description': 'Schools and educational facilities'
    },
    'healthcare': {
        'tags': {'amenity': ['hospital', 'clinic', 'doctors', 'pharmacy']},
        'description': 'Healthcare facilities'
    },
    'food': {
        'tags': {'amenity': ['restaurant', 'cafe', 'fast_food', 'food_court']},
        'description': 'Restaurants and food outlets'
    },
    'transport': {
        'tags': {'amenity': ['bus_station', 'fuel'], 'public_transport': True},
        'description': 'Transport hubs'
    }
}


def download_pois(city_code, category_name, tags):
    """Download POIs from OpenStreetMap"""
    city = CITIES[city_code]

    try:
        pois = ox.features_from_bbox(bbox=city['bbox'], tags=tags)

        # Convert to points (centroids for polygons)
        if len(pois) > 0:
            pois = pois.copy()
            pois['geometry'] = pois.geometry.centroid
            pois = pois[pois.geometry.type == 'Point']

        return pois
    except Exception as e:
        print(f"    Warning: Could not download {category_name}: {e}")
        return gpd.GeoDataFrame()


def compute_poi_density(traffic_gdf, poi_gdf, buffer_distance=0.005):
    """
    Compute POI density around each traffic segment

    Parameters:
    -----------
    traffic_gdf : GeoDataFrame
        Traffic segments
    poi_gdf : GeoDataFrame
        POI points
    buffer_distance : float
        Buffer distance in degrees (~500m at equator for 0.005)

    Returns:
    --------
    array : POI count within buffer for each segment
    """
    if len(poi_gdf) == 0:
        return np.zeros(len(traffic_gdf))

    # Create buffer around each traffic segment centroid
    traffic_centroids = traffic_gdf.geometry.centroid

    # Count POIs within buffer of each segment
    poi_counts = []

    for centroid in traffic_centroids:
        buffer = centroid.buffer(buffer_distance)
        count = poi_gdf.geometry.within(buffer).sum()
        poi_counts.append(count)

    return np.array(poi_counts)


def analyze_city(city_code):
    """Analyze POI-congestion relationship for a city"""
    city = CITIES[city_code]
    city_name = city['name']

    print(f"\n{'='*50}")
    print(f"Analyzing {city_name}")
    print(f"{'='*50}")

    # Load traffic data
    print(f"\n  Loading traffic data...")
    traffic_path = f"{city['traffic_folder']}/evening_peak_{city_code}.gpkg"
    traffic = gpd.read_file(traffic_path)
    print(f"    Segments: {len(traffic)}")

    # Ensure CRS is set
    if traffic.crs is None:
        traffic = traffic.set_crs("EPSG:4326")

    # Download and analyze each POI category
    results = {
        'city': city_name,
        'n_segments': len(traffic)
    }

    all_poi_counts = np.zeros(len(traffic))
    category_results = []

    for cat_name, cat_info in POI_CATEGORIES.items():
        print(f"\n  Downloading {cat_name} POIs...")
        pois = download_pois(city_code, cat_name, cat_info['tags'])
        n_pois = len(pois)
        print(f"    Found: {n_pois} POIs")

        if n_pois > 0:
            # Ensure same CRS
            if pois.crs is None:
                pois = pois.set_crs("EPSG:4326")
            elif pois.crs != traffic.crs:
                pois = pois.to_crs(traffic.crs)

            # Compute density
            print(f"    Computing density...")
            poi_counts = compute_poi_density(traffic, pois, buffer_distance=0.003)  # ~300m
            all_poi_counts += poi_counts

            # Compute correlation with jam factor
            jam_factor = traffic['jam_factor_mean'].values

            # Remove NaN values
            mask = ~(np.isnan(jam_factor) | np.isnan(poi_counts))
            if mask.sum() > 10:
                r, p = stats.pearsonr(jam_factor[mask], poi_counts[mask])
                rho, rho_p = stats.spearmanr(jam_factor[mask], poi_counts[mask])

                category_results.append({
                    'category': cat_name,
                    'description': cat_info['description'],
                    'n_pois': n_pois,
                    'pearson_r': r,
                    'pearson_p': p,
                    'spearman_r': rho,
                    'spearman_p': rho_p
                })

                print(f"    Correlation: r={r:.4f} (p={p:.4f}), ρ={rho:.4f} (p={rho_p:.4f})")

    # Total POI density correlation
    print(f"\n  Computing total POI density correlation...")
    jam_factor = traffic['jam_factor_mean'].values
    mask = ~(np.isnan(jam_factor) | np.isnan(all_poi_counts))

    if mask.sum() > 10:
        r_total, p_total = stats.pearsonr(jam_factor[mask], all_poi_counts[mask])
        rho_total, rho_p_total = stats.spearmanr(jam_factor[mask], all_poi_counts[mask])

        results['total_pois'] = int(all_poi_counts.sum())
        results['total_pearson_r'] = r_total
        results['total_pearson_p'] = p_total
        results['total_spearman_r'] = rho_total
        results['total_spearman_p'] = rho_p_total

        print(f"    TOTAL: r={r_total:.4f} (p={p_total:.4f}), ρ={rho_total:.4f} (p={rho_p_total:.4f})")

    # Store POI counts in traffic data for visualization
    traffic['poi_density'] = all_poi_counts

    return results, category_results, traffic


def plot_poi_congestion_scatter(traffic, city_code):
    """Create scatter plot of POI density vs congestion"""
    city_name = CITIES[city_code]['name']
    color = CITIES[city_code]['color']

    fig, ax = plt.subplots(figsize=(10, 8))

    x = traffic['poi_density'].values
    y = traffic['jam_factor_mean'].values

    # Remove NaN
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    ax.scatter(x, y, alpha=0.4, s=20, color=color, edgecolors='white', linewidth=0.3)

    # Add regression line
    slope, intercept, r, p, se = stats.linregress(x, y)
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, 'r-', linewidth=2, label=f'r = {r:.4f} (p = {p:.4f})')

    ax.set_xlabel('POI Density (count within 300m)', fontsize=12)
    ax.set_ylabel('Jam Factor', fontsize=12)
    ax.set_title(f'{city_name}: POI Density vs Traffic Congestion', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    filepath = FIGURES_DIR / f'{city_code}_poi_congestion_scatter.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_poi_congestion_map(traffic, city_code):
    """Create side-by-side map of POI density and congestion"""
    city_name = CITIES[city_code]['name']

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Left: POI density
    ax1 = axes[0]
    traffic.plot(column='poi_density', cmap='YlOrRd', linewidth=0.8, ax=ax1,
                legend=True, legend_kwds={'label': 'POI Count', 'shrink': 0.7})
    ax1.set_title(f'{city_name} - POI Density', fontsize=12, fontweight='bold')
    ax1.set_axis_off()

    # Right: Congestion
    ax2 = axes[1]
    traffic.plot(column='jam_factor_mean', cmap='RdYlGn_r', linewidth=0.8, ax=ax2,
                legend=True, legend_kwds={'label': 'Jam Factor', 'shrink': 0.7})
    ax2.set_title(f'{city_name} - Traffic Congestion', fontsize=12, fontweight='bold')
    ax2.set_axis_off()

    plt.suptitle(f'{city_name}: POI Density vs Congestion Comparison', fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / f'{city_code}_poi_congestion_map.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_category_comparison(all_category_results):
    """Plot correlation comparison across POI categories"""
    fig, ax = plt.subplots(figsize=(14, 8))

    # Prepare data
    categories = list(POI_CATEGORIES.keys())
    x = np.arange(len(categories))
    width = 0.25

    for i, (city_code, cat_results) in enumerate(all_category_results.items()):
        city_name = CITIES[city_code]['name']
        color = CITIES[city_code]['color']

        # Get correlations for each category
        correlations = []
        for cat in categories:
            cat_data = next((c for c in cat_results if c['category'] == cat), None)
            if cat_data:
                correlations.append(cat_data['spearman_r'])
            else:
                correlations.append(0)

        ax.bar(x + i*width, correlations, width, label=city_name, color=color, alpha=0.8)

    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_xlabel('POI Category', fontsize=12)
    ax.set_ylabel('Spearman Correlation (ρ)', fontsize=12)
    ax.set_title('POI-Congestion Correlation by Category and City', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels([POI_CATEGORIES[c]['description'] for c in categories], rotation=45, ha='right')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    filepath = FIGURES_DIR / 'poi_category_comparison.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {filepath}")


def compare_with_centrality():
    """Compare POI correlation with centrality correlation"""
    # Load centrality results if available
    centrality_path = OUTPUT_DIR / 'centrality_correlations.csv'
    if centrality_path.exists():
        centrality_df = pd.read_csv(centrality_path)
        return centrality_df
    return None


def main():
    print("=" * 70)
    print("POI-CONGESTION ANALYSIS")
    print("Testing: Does congestion cluster around activity centers?")
    print("=" * 70)

    all_results = []
    all_category_results = {}

    for city_code in CITIES.keys():
        results, category_results, traffic = analyze_city(city_code)
        all_results.append(results)
        all_category_results[city_code] = category_results

        # Create visualizations
        print(f"\n  Creating visualizations...")
        plot_poi_congestion_scatter(traffic, city_code)
        plot_poi_congestion_map(traffic, city_code)

    # Category comparison plot
    print(f"\nCreating category comparison plot...")
    plot_category_comparison(all_category_results)

    # Save results
    results_df = pd.DataFrame(all_results)
    results_path = OUTPUT_DIR / 'poi_congestion_correlations.csv'
    results_df.to_csv(results_path, index=False)
    print(f"\nSaved: {results_path}")

    # Compare with centrality
    print("\n" + "=" * 70)
    print("COMPARISON: POI Density vs Network Centrality")
    print("=" * 70)

    centrality_df = compare_with_centrality()

    print(f"\n{'City':<12} {'POI Corr (ρ)':>15} {'Centrality Corr (ρ)':>20} {'Winner':>12}")
    print("-" * 65)

    for result in all_results:
        city = result['city']
        poi_r = result.get('total_spearman_r', 0)

        cent_r = 0
        if centrality_df is not None:
            cent_row = centrality_df[centrality_df['city'] == city]
            if len(cent_row) > 0:
                cent_r = cent_row['spearman_r'].values[0]

        winner = "POI" if abs(poi_r) > abs(cent_r) else "Centrality" if abs(cent_r) > abs(poi_r) else "Tie"
        print(f"{city:<12} {poi_r:>15.4f} {cent_r:>20.4f} {winner:>12}")

    # Summary
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    avg_poi_corr = np.mean([r.get('total_spearman_r', 0) for r in all_results])
    avg_cent_corr = 0
    if centrality_df is not None:
        avg_cent_corr = centrality_df['spearman_r'].mean()

    print(f"\nAverage POI-Congestion correlation:        ρ = {avg_poi_corr:.4f}")
    print(f"Average Centrality-Congestion correlation: ρ = {avg_cent_corr:.4f}")

    if abs(avg_poi_corr) > abs(avg_cent_corr):
        print("\n✓ POI density is a BETTER predictor of congestion than network centrality")
        print("  → Supports hypothesis: congestion clusters around activity centers")
    else:
        print("\n✗ Network centrality is a better predictor (or both are weak)")
        print("  → Does not support the activity center hypothesis")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
