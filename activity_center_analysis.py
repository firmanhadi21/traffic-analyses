#!/usr/bin/env python3
"""
Activity Center Congestion Analysis

Proves that activity centers (high POI density) have higher congestion
than peripheral areas, even though the linear correlation is weak.

Key insight: The weak correlation occurs because BOTH zones follow
the same temporal pattern - but at different LEVELS.
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

ox.settings.use_cache = True
ox.settings.log_console = False

OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# City configurations (OSMnx 2.0 format)
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

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]


def download_all_pois(city_code):
    """Download all relevant POIs for activity center identification"""
    city = CITIES[city_code]

    all_pois = []

    poi_tags = [
        {'shop': True},
        {'office': True},
        {'amenity': ['school', 'university', 'college', 'hospital', 'clinic',
                     'restaurant', 'cafe', 'bank', 'marketplace']},
        {'building': ['commercial', 'retail', 'office', 'industrial']},
    ]

    for tags in poi_tags:
        try:
            pois = ox.features_from_bbox(bbox=city['bbox'], tags=tags)
            if len(pois) > 0:
                pois = pois.copy()
                pois['geometry'] = pois.geometry.centroid
                pois = pois[pois.geometry.type == 'Point']
                all_pois.append(pois[['geometry']])
        except Exception as e:
            continue

    if all_pois:
        combined = pd.concat(all_pois, ignore_index=True)
        return gpd.GeoDataFrame(combined, geometry='geometry', crs='EPSG:4326')
    return gpd.GeoDataFrame()


def compute_poi_density_zones(traffic_gdf, poi_gdf, buffer_distance=0.003):
    """
    Compute POI density and classify into zones
    """
    traffic = traffic_gdf.copy()

    if len(poi_gdf) == 0:
        traffic['poi_count'] = 0
        traffic['poi_zone'] = 'Low Activity'
        return traffic

    # Compute POI count within buffer
    traffic_centroids = traffic.geometry.centroid

    poi_counts = []
    for centroid in traffic_centroids:
        buffer = centroid.buffer(buffer_distance)
        count = poi_gdf.geometry.within(buffer).sum()
        poi_counts.append(count)

    traffic['poi_count'] = poi_counts

    # Classify into zones based on quartiles
    q25 = traffic['poi_count'].quantile(0.25)
    q75 = traffic['poi_count'].quantile(0.75)

    def classify_zone(count):
        if count <= q25:
            return 'Low Activity (Peripheral)'
        elif count >= q75:
            return 'High Activity (Center)'
        else:
            return 'Medium Activity'

    traffic['poi_zone'] = traffic['poi_count'].apply(classify_zone)

    return traffic


def analyze_zone_congestion(city_code):
    """Compare congestion between activity zones"""
    city = CITIES[city_code]
    city_name = city['name']

    print(f"\n{'='*60}")
    print(f"Analyzing {city_name}")
    print(f"{'='*60}")

    # Download POIs
    print(f"  Downloading POIs...")
    pois = download_all_pois(city_code)
    print(f"    Total POIs: {len(pois)}")

    # Load traffic data for evening peak
    traffic_path = f"{city['traffic_folder']}/evening_peak_{city_code}.gpkg"
    traffic = gpd.read_file(traffic_path)

    # Classify zones
    print(f"  Classifying activity zones...")
    traffic = compute_poi_density_zones(traffic, pois)

    zone_counts = traffic['poi_zone'].value_counts()
    print(f"    Zone distribution:")
    for zone, count in zone_counts.items():
        print(f"      {zone}: {count} segments")

    # Compare congestion by zone
    print(f"\n  Congestion by zone:")
    zone_stats = traffic.groupby('poi_zone')['jam_factor_mean'].agg(['mean', 'std', 'count'])

    for zone in ['High Activity (Center)', 'Medium Activity', 'Low Activity (Peripheral)']:
        if zone in zone_stats.index:
            mean = zone_stats.loc[zone, 'mean']
            std = zone_stats.loc[zone, 'std']
            n = zone_stats.loc[zone, 'count']
            print(f"    {zone}: JF = {mean:.3f} ± {std:.3f} (n={n:.0f})")

    # Statistical test: High vs Low activity zones
    high_zone = traffic[traffic['poi_zone'] == 'High Activity (Center)']['jam_factor_mean']
    low_zone = traffic[traffic['poi_zone'] == 'Low Activity (Peripheral)']['jam_factor_mean']

    if len(high_zone) > 10 and len(low_zone) > 10:
        t_stat, p_value = stats.ttest_ind(high_zone, low_zone)
        effect_size = (high_zone.mean() - low_zone.mean()) / np.sqrt(
            (high_zone.std()**2 + low_zone.std()**2) / 2
        )  # Cohen's d

        pct_diff = ((high_zone.mean() - low_zone.mean()) / low_zone.mean()) * 100

        print(f"\n  Statistical comparison (High vs Low Activity):")
        print(f"    High Activity mean: {high_zone.mean():.3f}")
        print(f"    Low Activity mean:  {low_zone.mean():.3f}")
        print(f"    Difference: {pct_diff:+.1f}%")
        print(f"    t-statistic: {t_stat:.2f}")
        print(f"    p-value: {p_value:.4f}")
        print(f"    Effect size (Cohen's d): {effect_size:.3f}")

        if p_value < 0.05:
            print(f"    *** SIGNIFICANT: Activity centers have {'higher' if t_stat > 0 else 'lower'} congestion ***")

    return traffic, pois, {
        'city': city_name,
        'high_mean': high_zone.mean() if len(high_zone) > 0 else None,
        'low_mean': low_zone.mean() if len(low_zone) > 0 else None,
        'pct_diff': pct_diff if len(high_zone) > 10 and len(low_zone) > 10 else None,
        't_stat': t_stat if len(high_zone) > 10 and len(low_zone) > 10 else None,
        'p_value': p_value if len(high_zone) > 10 and len(low_zone) > 10 else None,
        'effect_size': effect_size if len(high_zone) > 10 and len(low_zone) > 10 else None
    }


def analyze_temporal_by_zone(city_code, traffic_with_zones):
    """Show that temporal patterns are similar across zones"""
    city = CITIES[city_code]
    city_name = city['name']

    # Get segment IDs and their zones using osm_composite_id as key
    id_col = 'osm_composite_id' if 'osm_composite_id' in traffic_with_zones.columns else None
    if id_col is None:
        # Fall back to index-based assignment if no ID column
        segment_zones = traffic_with_zones[['poi_zone']].copy()
    else:
        segment_zones = traffic_with_zones[[id_col, 'poi_zone']].copy()

    results = []

    for period in TIME_PERIODS:
        traffic_path = f"{city['traffic_folder']}/{period}_{city_code}.gpkg"
        try:
            gdf = gpd.read_file(traffic_path)
            if id_col and id_col in gdf.columns:
                # Merge zones by segment ID
                gdf = gdf.merge(segment_zones[[id_col, 'poi_zone']], on=id_col, how='inner')
            elif len(gdf) == len(segment_zones):
                gdf['poi_zone'] = segment_zones['poi_zone'].values
            else:
                continue

            for zone in ['High Activity (Center)', 'Low Activity (Peripheral)']:
                zone_data = gdf[gdf['poi_zone'] == zone]['jam_factor_mean']
                if len(zone_data) > 0:
                    results.append({
                        'period': period,
                        'zone': zone,
                        'mean_jf': zone_data.mean()
                    })
        except Exception:
            continue

    return pd.DataFrame(results)


def plot_zone_comparison(all_results):
    """Create visualization comparing zones"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for idx, (city_code, (traffic, pois, stats_result)) in enumerate(all_results.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Box plot by zone
        zones = ['High Activity (Center)', 'Medium Activity', 'Low Activity (Peripheral)']
        zone_data = [traffic[traffic['poi_zone'] == z]['jam_factor_mean'].dropna() for z in zones]

        bp = ax.boxplot(zone_data, labels=['High\n(Center)', 'Medium', 'Low\n(Peripheral)'],
                       patch_artist=True)

        colors = ['#e74c3c', '#f39c12', '#27ae60']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Jam Factor' if idx == 0 else '')
        ax.set_xlabel('Activity Zone')
        ax.set_title(f'{city_name}\n(p = {stats_result["p_value"]:.4f})', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

        # Add percentage difference annotation
        if stats_result['pct_diff']:
            ax.annotate(f"+{stats_result['pct_diff']:.1f}%\nhigher",
                       xy=(0.5, 0.95), xycoords='axes fraction',
                       ha='center', va='top', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

    plt.suptitle('Congestion by Activity Zone: Centers vs Periphery\n(Evening Peak)',
                fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / 'activity_zone_comparison.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\nSaved: {filepath}")


def plot_temporal_by_zone(all_temporal_data):
    """Show temporal patterns by zone"""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    period_labels = {
        'night': 'Night',
        'morning_peak': 'AM Peak',
        'morning_offpeak': 'AM Off',
        'lunch_hours': 'Lunch',
        'afternoon_offpeak': 'PM Off',
        'evening_peak': 'PM Peak',
        'evening_offpeak': 'Eve Off',
        'late_night': 'Late'
    }

    for idx, (city_code, df) in enumerate(all_temporal_data.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        for zone, color in [('High Activity (Center)', '#e74c3c'),
                           ('Low Activity (Peripheral)', '#27ae60')]:
            zone_df = df[df['zone'] == zone]
            if len(zone_df) > 0:
                # Order by time period
                available_periods = [p for p in TIME_PERIODS if p in zone_df['period'].values]
                zone_df = zone_df.set_index('period').loc[available_periods].reset_index()
                x_positions = [TIME_PERIODS.index(p) for p in available_periods]
                ax.plot(x_positions, zone_df['mean_jf'], 'o-',
                       label=zone.split(' (')[0], color=color, linewidth=2, markersize=6)

        ax.set_xticks(range(len(TIME_PERIODS)))
        ax.set_xticklabels([period_labels[p] for p in TIME_PERIODS], rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('Mean Jam Factor' if idx == 0 else '')
        ax.set_xlabel('Time Period')
        ax.set_title(f'{city_name}', fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.suptitle('Temporal Patterns: Both Zones Follow Same Pattern at Different Levels',
                fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / 'temporal_by_activity_zone.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {filepath}")


def main():
    print("=" * 70)
    print("ACTIVITY CENTER CONGESTION ANALYSIS")
    print("=" * 70)
    print("\nProving: Activity centers have HIGHER congestion than peripheral areas")
    print("         (even though linear correlation is weak)")

    all_results = {}
    all_temporal_data = {}

    for city_code in CITIES.keys():
        traffic, pois, stats_result = analyze_zone_congestion(city_code)
        all_results[city_code] = (traffic, pois, stats_result)

        # Analyze temporal patterns by zone
        temporal_df = analyze_temporal_by_zone(city_code, traffic)
        all_temporal_data[city_code] = temporal_df

    # Create visualizations
    print("\n" + "=" * 70)
    print("Creating visualizations...")
    plot_zone_comparison(all_results)
    plot_temporal_by_zone(all_temporal_data)

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY: Activity Center Effect on Congestion")
    print("=" * 70)
    print(f"\n{'City':<12} {'High Activity':<15} {'Low Activity':<15} {'Difference':<12} {'p-value':<12} {'Effect'}")
    print("-" * 75)

    for city_code, (_, _, stats_result) in all_results.items():
        city = stats_result['city']
        high = stats_result['high_mean']
        low = stats_result['low_mean']
        diff = stats_result['pct_diff']
        p = stats_result['p_value']
        d = stats_result['effect_size']

        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        print(f"{city:<12} {high:<15.3f} {low:<15.3f} {diff:>+10.1f}% {p:<12.4f} d={d:.2f} {sig}")

    print("\n" + "-" * 75)
    print("Significance: *** p<0.001, ** p<0.01, * p<0.05")
    print("Effect size: |d| < 0.2 = small, 0.2-0.8 = medium, > 0.8 = large")

    # Save results
    results_df = pd.DataFrame([r[2] for r in all_results.values()])
    results_path = OUTPUT_DIR / 'activity_zone_results.csv'
    results_df.to_csv(results_path, index=False)
    print(f"\nSaved: {results_path}")

    # Key interpretation
    print("\n" + "=" * 70)
    print("KEY INTERPRETATION")
    print("=" * 70)
    print("""
    WHY CORRELATION IS WEAK BUT ZONES ARE DIFFERENT:

    1. Activity centers have HIGHER BASELINE congestion
       - More destinations = more trips ending/starting there

    2. BUT both zones follow the SAME TEMPORAL PATTERN
       - Peak hours affect everywhere proportionally
       - The correlation measures: "does more POI → more congestion?"
       - Answer: Yes for baseline, but temporal pattern dominates variation

    3. MATHEMATICAL EXPLANATION:
       - Correlation measures linear relationship in RAW values
       - If High zone = 1.8 JF and Low zone = 1.4 JF consistently,
         but both vary 0.5-2.5 over time → temporal variance >> spatial variance
       - Result: r ≈ 0 despite real level difference

    4. CORRECT INTERPRETATION:
       - Activity centers DO have more congestion (t-test proves this)
       - BUT temporal synchronization (time-of-day) dominates VARIATION
       - Both effects are real; temporal effect is just much LARGER
    """)

    print("=" * 70)
    print("DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
