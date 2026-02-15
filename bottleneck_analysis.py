#!/usr/bin/env python3
"""
Bottleneck Analysis

Proves that congestion occurs at capacity-constrained segments,
not necessarily at high-POI activity centers.

Key insight: Bottlenecks are where road capacity is insufficient
to handle peak-period demand. These are characterized by:
1. Low lane count / narrow roads
2. High peak-to-offpeak ratio (sensitive to demand surges)
3. High temporal variance (congested at peak, free at night)
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
from scipy.spatial import cKDTree
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


def get_road_capacity_attributes(city_code):
    """
    Download road network and extract capacity-related attributes.

    Capacity proxies:
    - lanes: number of lanes
    - highway: road type (motorway > trunk > primary > secondary > tertiary > residential)
    - maxspeed: speed limit (higher = more capacity typically)
    """
    city = CITIES[city_code]
    print(f"  Downloading road network for {city['name']}...")

    # Download drivable network
    G = ox.graph_from_bbox(bbox=city['bbox'], network_type='drive')

    # Convert to GeoDataFrame
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

    # Extract capacity-related attributes
    def get_lanes(x):
        """Extract lane count, handling various formats"""
        if isinstance(x, list):
            try:
                return float(x[0])
            except (ValueError, IndexError):
                return np.nan
        try:
            if pd.isna(x):
                return np.nan
        except (ValueError, TypeError):
            return np.nan
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            try:
                return float(x.split(';')[0])  # Take first value if multiple
            except:
                return np.nan
        return np.nan

    edges['lane_count'] = edges['lanes'].apply(get_lanes) if 'lanes' in edges.columns else np.nan

    # Road hierarchy score (higher = more capacity)
    road_hierarchy = {
        'motorway': 6, 'motorway_link': 5.5,
        'trunk': 5, 'trunk_link': 4.5,
        'primary': 4, 'primary_link': 3.5,
        'secondary': 3, 'secondary_link': 2.5,
        'tertiary': 2, 'tertiary_link': 1.5,
        'residential': 1, 'living_street': 0.5,
        'unclassified': 1, 'service': 0.5
    }

    def get_road_score(highway):
        if isinstance(highway, list):
            highway = highway[0]
        return road_hierarchy.get(highway, 1)

    edges['road_score'] = edges['highway'].apply(get_road_score)

    # Capacity proxy: combination of lanes and road type
    # If lanes unknown, estimate from road type
    default_lanes = {
        'motorway': 3, 'motorway_link': 2,
        'trunk': 2, 'trunk_link': 1,
        'primary': 2, 'primary_link': 1,
        'secondary': 2, 'secondary_link': 1,
        'tertiary': 1, 'tertiary_link': 1,
        'residential': 1, 'living_street': 1,
        'unclassified': 1, 'service': 1
    }

    def estimate_lanes(row):
        if not pd.isna(row['lane_count']):
            return row['lane_count']
        highway = row['highway']
        if isinstance(highway, list):
            highway = highway[0]
        return default_lanes.get(highway, 1)

    edges['estimated_lanes'] = edges.apply(estimate_lanes, axis=1)

    # Capacity score = lanes * road_score
    edges['capacity_score'] = edges['estimated_lanes'] * edges['road_score']

    print(f"    Road segments (all): {len(edges)}")

    # Filter to road types that HERE Traffic typically monitors
    # HERE covers motorways, trunks, primaries, secondaries, and their links.
    # It rarely covers tertiary, residential, service, or living streets.
    here_monitored_types = {
        'motorway', 'motorway_link',
        'trunk', 'trunk_link',
        'primary', 'primary_link',
        'secondary', 'secondary_link',
        'tertiary', 'tertiary_link',
    }

    def get_highway_str(highway):
        if isinstance(highway, list):
            return highway[0]
        return highway

    edges['highway_str'] = edges['highway'].apply(get_highway_str)
    edges_filtered = edges[edges['highway_str'].isin(here_monitored_types)].copy()

    # Also create a filtered subgraph for capacity drop detection
    filtered_edge_ids = set(edges_filtered.index)
    G_filtered = G.edge_subgraph(
        [(u, v, k) for u, v, k in G.edges(keys=True) if (u, v, k) in filtered_edge_ids]
    ).copy()

    print(f"    Road segments (HERE-comparable): {len(edges_filtered)} ({len(edges_filtered)/len(edges)*100:.1f}%)")
    print(f"    Filtered out: {len(edges) - len(edges_filtered)} residential/service/unclassified segments")
    print(f"    Lane count coverage: {edges_filtered['lane_count'].notna().mean()*100:.1f}%")

    return edges_filtered, G_filtered


def detect_capacity_drops(G, edges):
    """
    Detect locations where road capacity drops along the network using graph topology.

    A capacity drop node is where the max incoming edge capacity exceeds
    the max outgoing edge capacity — a "funnel" point where traffic gets squeezed.

    Returns:
        drop_nodes: list of node IDs with capacity drops
        drop_magnitudes: magnitude of drop at each node (fraction of incoming capacity lost)
        drop_coords: (N, 2) array of lon/lat coordinates for drop nodes
    """
    # Map edge capacity scores
    edge_cap = {}
    for idx, row in edges.iterrows():
        edge_cap[idx] = row['capacity_score']

    nodes_gdf = ox.graph_to_gdfs(G, nodes=True, edges=False)

    drop_nodes = []
    drop_magnitudes = []

    for node in G.nodes():
        in_edges = list(G.in_edges(node, keys=True))
        out_edges = list(G.out_edges(node, keys=True))

        if not in_edges or not out_edges:
            continue

        in_caps = [edge_cap.get(e, np.nan) for e in in_edges]
        out_caps = [edge_cap.get(e, np.nan) for e in out_edges]

        in_caps = [c for c in in_caps if not np.isnan(c)]
        out_caps = [c for c in out_caps if not np.isnan(c)]

        if not in_caps or not out_caps:
            continue

        max_in = max(in_caps)
        max_out = max(out_caps)

        # Capacity drop: high incoming capacity flowing into lower outgoing
        if max_in > max_out:
            drop_magnitude = (max_in - max_out) / max_in
            if drop_magnitude >= 0.2:  # At least 20% capacity reduction
                drop_nodes.append(node)
                drop_magnitudes.append(drop_magnitude)

    if drop_nodes:
        drop_points = nodes_gdf.loc[drop_nodes]
        drop_coords = np.array([[p.x, p.y] for p in drop_points.geometry])
    else:
        drop_coords = np.array([]).reshape(0, 2)

    return drop_nodes, drop_magnitudes, drop_coords


def analyze_capacity_drop_congestion(matched, drop_coords, drop_magnitudes):
    """
    Test bottleneck hypothesis: does proximity to capacity drop points
    predict higher congestion?

    Also tests local capacity gradient: segments with lower capacity
    than their spatial neighbors (local bottlenecks) should be more congested.
    """
    results = {}

    # ── Part A: Distance to nearest capacity drop ──
    if len(drop_coords) > 0:
        traffic_centroids = matched.geometry.centroid
        traffic_coords = np.array([[p.x, p.y] for p in traffic_centroids])

        drop_tree = cKDTree(drop_coords)
        distances, indices = drop_tree.query(traffic_coords, k=1)

        matched = matched.copy()
        matched['dist_to_cap_drop'] = distances
        matched['nearest_drop_magnitude'] = np.array(drop_magnitudes)[indices]

        # Correlation: distance to capacity drop vs congestion
        valid = matched[['dist_to_cap_drop', 'jam_factor_mean']].dropna()
        r_dist, p_dist = stats.pearsonr(valid['dist_to_cap_drop'], valid['jam_factor_mean'])
        rho_dist, rho_p_dist = stats.spearmanr(valid['dist_to_cap_drop'], valid['jam_factor_mean'])

        results['drop_dist_pearson_r'] = r_dist
        results['drop_dist_pearson_p'] = p_dist
        results['drop_dist_spearman_r'] = rho_dist
        results['drop_dist_spearman_p'] = rho_p_dist

        # Bin by distance tertiles
        matched['drop_proximity'] = pd.qcut(
            matched['dist_to_cap_drop'], q=3,
            labels=['Near', 'Medium', 'Far'], duplicates='drop'
        )

        proximity_stats = matched.groupby('drop_proximity')['jam_factor_mean'].agg(['mean', 'count'])

        # t-test: near vs far from capacity drops
        near = matched[matched['drop_proximity'] == 'Near']['jam_factor_mean'].dropna()
        far = matched[matched['drop_proximity'] == 'Far']['jam_factor_mean'].dropna()

        if len(near) > 1 and len(far) > 1:
            t_prox, p_prox = stats.ttest_ind(near, far)
            d_prox = (near.mean() - far.mean()) / np.sqrt((near.std()**2 + far.std()**2) / 2)
        else:
            t_prox, p_prox, d_prox = np.nan, np.nan, np.nan

        results['near_drop_jf'] = near.mean() if len(near) > 0 else np.nan
        results['far_drop_jf'] = far.mean() if len(far) > 0 else np.nan
        results['drop_prox_t_stat'] = t_prox
        results['drop_prox_p_value'] = p_prox
        results['drop_prox_effect_size'] = d_prox
        results['n_capacity_drops'] = len(drop_coords)

        print(f"\n    Capacity drop analysis (graph-based):")
        print(f"      Capacity drop nodes detected: {len(drop_coords)} (≥20% reduction)")
        print(f"\n      Distance to nearest capacity drop vs congestion:")
        print(f"        Pearson r: {r_dist:.4f} (p={p_dist:.4f})")
        print(f"        Spearman ρ: {rho_dist:.4f} (p={rho_p_dist:.4f})")
        print(f"\n      Congestion by proximity to capacity drops:")
        for label, row in proximity_stats.iterrows():
            print(f"        {label}: JF = {row['mean']:.3f} (n={int(row['count'])})")
        print(f"      Near vs Far: t={t_prox:.2f}, p={p_prox:.4f}, Cohen's d={d_prox:.3f}")

    else:
        print(f"\n    Capacity drop analysis: No capacity drops detected")
        results['n_capacity_drops'] = 0

    # ── Part B: Local capacity gradient (neighborhood analysis) ──
    traffic_centroids = matched.geometry.centroid
    traffic_coords = np.array([[p.x, p.y] for p in traffic_centroids])

    tree = cKDTree(traffic_coords)
    K = 10
    distances_knn, indices_knn = tree.query(traffic_coords, k=K + 1)

    # Mean capacity of K nearest neighbors (excluding self)
    neighbor_caps = np.array([
        matched.iloc[idx[1:]]['capacity_score'].mean()
        for idx in indices_knn
    ])

    matched['neighbor_cap_mean'] = neighbor_caps
    matched['capacity_drop_local'] = neighbor_caps - matched['capacity_score'].values
    # Positive = this segment has LESS capacity than its neighbors (local bottleneck)
    matched['relative_cap_drop'] = matched['capacity_drop_local'] / (neighbor_caps + 0.1)

    # Identify local bottleneck zones (top 25% of local capacity drop)
    threshold = matched['capacity_drop_local'].quantile(0.75)
    matched['is_local_bottleneck'] = matched['capacity_drop_local'] >= threshold

    bn = matched[matched['is_local_bottleneck']]['jam_factor_mean'].dropna()
    non_bn = matched[~matched['is_local_bottleneck']]['jam_factor_mean'].dropna()

    if len(bn) > 1 and len(non_bn) > 1:
        t_local, p_local = stats.ttest_ind(bn, non_bn)
        d_local = (bn.mean() - non_bn.mean()) / np.sqrt((bn.std()**2 + non_bn.std()**2) / 2)
    else:
        t_local, p_local, d_local = np.nan, np.nan, np.nan

    # Correlation: local capacity drop vs congestion
    valid_local = matched[['capacity_drop_local', 'jam_factor_mean']].dropna()
    r_local, p_r_local = stats.pearsonr(valid_local['capacity_drop_local'], valid_local['jam_factor_mean'])
    rho_local, rho_p_local = stats.spearmanr(valid_local['capacity_drop_local'], valid_local['jam_factor_mean'])

    results['local_bn_jf'] = bn.mean()
    results['local_non_bn_jf'] = non_bn.mean()
    results['local_bn_t_stat'] = t_local
    results['local_bn_p_value'] = p_local
    results['local_bn_effect_size'] = d_local
    results['local_drop_pearson_r'] = r_local
    results['local_drop_pearson_p'] = p_r_local
    results['local_drop_spearman_r'] = rho_local
    results['local_drop_spearman_p'] = rho_p_local

    print(f"\n    Local capacity gradient analysis (K={K} neighbors):")
    print(f"      Local bottleneck segments (capacity < neighbors): {matched['is_local_bottleneck'].sum()} / {len(matched)}")
    print(f"        Bottleneck zones: JF = {bn.mean():.3f} (n={len(bn)})")
    print(f"        Non-bottleneck:   JF = {non_bn.mean():.3f} (n={len(non_bn)})")
    diff_pct = (bn.mean() - non_bn.mean()) / non_bn.mean() * 100
    print(f"        Difference: {diff_pct:+.1f}%")
    print(f"        t-statistic: {t_local:.2f}, p-value: {p_local:.4f}")
    print(f"        Effect size (Cohen's d): {d_local:.3f}")
    print(f"\n      Local capacity drop vs congestion correlation:")
    print(f"        Pearson r: {r_local:.4f} (p={p_r_local:.4f})")
    print(f"        Spearman ρ: {rho_local:.4f} (p={rho_p_local:.4f})")

    return matched, results


def compute_peak_sensitivity(city_code):
    """
    Compute how sensitive each segment is to peak-hour demand.

    Peak sensitivity = (evening_peak_JF - night_JF) / night_JF

    High sensitivity indicates capacity constraint -
    the road handles off-peak fine but fails during peak.
    """
    city = CITIES[city_code]

    # Load evening peak and night data
    peak_path = f"{city['traffic_folder']}/evening_peak_{city_code}.gpkg"
    night_path = f"{city['traffic_folder']}/night_{city_code}.gpkg"

    peak = gpd.read_file(peak_path)
    night = gpd.read_file(night_path)

    # Compute peak sensitivity
    # Add small epsilon to avoid division by zero
    epsilon = 0.1
    peak['peak_sensitivity'] = (peak['jam_factor_mean'] - night['jam_factor_mean']) / (night['jam_factor_mean'] + epsilon)

    # Also compute coefficient of variation as bottleneck indicator
    peak['cv'] = peak['jam_factor_std'] / (peak['jam_factor_mean'] + epsilon)

    # Peak-to-night ratio
    peak['peak_night_ratio'] = peak['jam_factor_mean'] / (night['jam_factor_mean'] + epsilon)

    return peak


def spatial_join_traffic_roads(traffic_gdf, roads_gdf, max_distance=0.002):
    """
    Join traffic segments to road network edges based on proximity.
    """
    # Get centroids
    traffic_centroids = traffic_gdf.geometry.centroid
    road_centroids = roads_gdf.geometry.centroid

    # Build KD-tree for road centroids
    road_coords = np.array([[p.x, p.y] for p in road_centroids])
    traffic_coords = np.array([[p.x, p.y] for p in traffic_centroids])

    tree = cKDTree(road_coords)

    # Find nearest road for each traffic segment
    distances, indices = tree.query(traffic_coords, k=1)

    # Filter by max distance
    valid_mask = distances <= max_distance

    # Create result DataFrame
    result = traffic_gdf.copy()

    # Add road attributes
    road_attrs = ['lane_count', 'road_score', 'estimated_lanes', 'capacity_score']
    for attr in road_attrs:
        result[attr] = np.nan
        result.loc[valid_mask, attr] = roads_gdf.iloc[indices[valid_mask]][attr].values

    result['matched'] = valid_mask
    result['match_distance'] = distances

    print(f"    Matched: {valid_mask.sum()} / {len(traffic_gdf)} ({valid_mask.mean()*100:.1f}%)")
    if valid_mask.any():
        matched_dists = distances[valid_mask]
        print(f"    Match distance (matched): median={np.median(matched_dists):.5f}°, "
              f"mean={np.mean(matched_dists):.5f}°, max={np.max(matched_dists):.5f}°")

    return result


def analyze_bottlenecks(city_code):
    """
    Main analysis: prove bottlenecks (capacity constraints) cause congestion.
    """
    city = CITIES[city_code]
    city_name = city['name']

    print(f"\n{'='*60}")
    print(f"Bottleneck Analysis: {city_name}")
    print(f"{'='*60}")

    # Step 1: Get road capacity attributes
    roads, G = get_road_capacity_attributes(city_code)

    # Step 2: Compute peak sensitivity
    print(f"  Computing peak sensitivity...")
    traffic = compute_peak_sensitivity(city_code)

    # Step 3: Spatial join
    print(f"  Matching traffic segments to road network...")
    traffic = spatial_join_traffic_roads(traffic, roads)

    # Filter to matched segments
    matched = traffic[traffic['matched']].copy()
    print(f"    Using {len(matched)} matched segments for analysis")

    # Step 4: Analyze relationship between capacity and congestion
    print(f"\n  Analyzing capacity-congestion relationships...")

    results = {'city': city_name}

    # 4a. Low capacity roads vs high capacity roads
    median_capacity = matched['capacity_score'].median()
    low_cap = matched[matched['capacity_score'] <= median_capacity]['jam_factor_mean']
    high_cap = matched[matched['capacity_score'] > median_capacity]['jam_factor_mean']

    t_stat, p_value = stats.ttest_ind(low_cap.dropna(), high_cap.dropna())
    effect_size = (low_cap.mean() - high_cap.mean()) / np.sqrt(
        (low_cap.std()**2 + high_cap.std()**2) / 2
    )

    print(f"\n    Capacity comparison:")
    print(f"      Low capacity roads:  JF = {low_cap.mean():.3f} (n={len(low_cap)})")
    print(f"      High capacity roads: JF = {high_cap.mean():.3f} (n={len(high_cap)})")
    print(f"      Difference: {((low_cap.mean() - high_cap.mean()) / high_cap.mean() * 100):+.1f}%")
    print(f"      t-statistic: {t_stat:.2f}, p-value: {p_value:.4f}")
    print(f"      Effect size (Cohen's d): {effect_size:.3f}")

    results['low_cap_jf'] = low_cap.mean()
    results['high_cap_jf'] = high_cap.mean()
    results['cap_diff_pct'] = (low_cap.mean() - high_cap.mean()) / high_cap.mean() * 100
    results['cap_t_stat'] = t_stat
    results['cap_p_value'] = p_value
    results['cap_effect_size'] = effect_size

    # 4b. Correlation: capacity score vs jam factor
    valid = matched[['capacity_score', 'jam_factor_mean']].dropna()
    r, p = stats.pearsonr(valid['capacity_score'], valid['jam_factor_mean'])
    rho, rho_p = stats.spearmanr(valid['capacity_score'], valid['jam_factor_mean'])

    print(f"\n    Capacity-Congestion correlation:")
    print(f"      Pearson r: {r:.4f} (p={p:.4f})")
    print(f"      Spearman ρ: {rho:.4f} (p={rho_p:.4f})")

    results['cap_pearson_r'] = r
    results['cap_pearson_p'] = p
    results['cap_spearman_r'] = rho
    results['cap_spearman_p'] = rho_p

    # 4c. Peak sensitivity analysis
    # High peak sensitivity = bottleneck (can't handle peak demand)
    print(f"\n    Peak sensitivity analysis:")

    median_sensitivity = matched['peak_sensitivity'].median()
    high_sens = matched[matched['peak_sensitivity'] > median_sensitivity]
    low_sens = matched[matched['peak_sensitivity'] <= median_sensitivity]

    # Do high-sensitivity segments have lower capacity?
    t_sens, p_sens = stats.ttest_ind(
        high_sens['capacity_score'].dropna(),
        low_sens['capacity_score'].dropna()
    )

    print(f"      High sensitivity segments: capacity = {high_sens['capacity_score'].mean():.2f}")
    print(f"      Low sensitivity segments:  capacity = {low_sens['capacity_score'].mean():.2f}")
    print(f"      Difference: {((high_sens['capacity_score'].mean() - low_sens['capacity_score'].mean()) / low_sens['capacity_score'].mean() * 100):+.1f}%")
    print(f"      t-statistic: {t_sens:.2f}, p-value: {p_sens:.4f}")

    results['high_sens_cap'] = high_sens['capacity_score'].mean()
    results['low_sens_cap'] = low_sens['capacity_score'].mean()
    results['sens_t_stat'] = t_sens
    results['sens_p_value'] = p_sens

    # 4d. Road type breakdown
    print(f"\n    Congestion by road type:")
    road_type_stats = matched.groupby('road_score')['jam_factor_mean'].agg(['mean', 'count'])
    road_type_stats = road_type_stats.sort_index(ascending=False)

    road_names = {
        6: 'Motorway', 5.5: 'Motorway Link',
        5: 'Trunk', 4.5: 'Trunk Link',
        4: 'Primary', 3.5: 'Primary Link',
        3: 'Secondary', 2.5: 'Secondary Link',
        2: 'Tertiary', 1.5: 'Tertiary Link',
        1: 'Residential', 0.5: 'Living Street/Service'
    }
    for score, row in road_type_stats.iterrows():
        name = road_names.get(score, f'Score {score}')
        print(f"      {name}: JF = {row['mean']:.3f} (n={int(row['count'])})")

    # 4e. Spatial capacity drop analysis (graph-based + local gradient)
    print(f"\n  Analyzing spatial capacity drops...")
    drop_nodes, drop_magnitudes, drop_coords = detect_capacity_drops(G, roads)
    matched, drop_results = analyze_capacity_drop_congestion(matched, drop_coords, drop_magnitudes)
    results.update(drop_results)

    return matched, results


def plot_bottleneck_analysis(all_results):
    """Create visualization of bottleneck findings"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for idx, (city_code, (traffic, stats_result)) in enumerate(all_results.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Box plot: Low capacity vs High capacity
        median_cap = traffic['capacity_score'].median()
        low_cap = traffic[traffic['capacity_score'] <= median_cap]['jam_factor_mean'].dropna()
        high_cap = traffic[traffic['capacity_score'] > median_cap]['jam_factor_mean'].dropna()

        bp = ax.boxplot([low_cap, high_cap], labels=['Low Capacity\n(Bottleneck)', 'High Capacity'],
                       patch_artist=True)

        colors = ['#e74c3c', '#27ae60']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Jam Factor' if idx == 0 else '')
        ax.set_xlabel('Road Capacity')

        p_val = stats_result['cap_p_value']
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        ax.set_title(f'{city_name}\n(p = {p_val:.4f} {sig})', fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

        # Add percentage difference annotation
        diff = stats_result['cap_diff_pct']
        ax.annotate(f"+{diff:.1f}%\nhigher",
                   xy=(0.5, 0.95), xycoords='axes fraction',
                   ha='center', va='top', fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

    plt.suptitle('Congestion by Road Capacity: Bottlenecks vs High-Capacity Roads\n(Evening Peak)',
                fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / 'bottleneck_capacity_comparison.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\nSaved: {filepath}")


def plot_capacity_correlation(all_results):
    """Scatter plot: capacity score vs jam factor"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for idx, (city_code, (traffic, stats_result)) in enumerate(all_results.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']
        color = CITIES[city_code]['color']

        valid = traffic[['capacity_score', 'jam_factor_mean']].dropna()

        ax.scatter(valid['capacity_score'], valid['jam_factor_mean'],
                  alpha=0.3, s=10, color=color)

        # Add regression line
        slope, intercept, r, p, se = stats.linregress(
            valid['capacity_score'], valid['jam_factor_mean']
        )
        x_line = np.linspace(valid['capacity_score'].min(), valid['capacity_score'].max(), 100)
        y_line = slope * x_line + intercept
        ax.plot(x_line, y_line, 'r-', linewidth=2, label=f'r = {r:.3f}')

        ax.set_xlabel('Road Capacity Score')
        ax.set_ylabel('Jam Factor' if idx == 0 else '')
        ax.set_title(f'{city_name}', fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)

    plt.suptitle('Road Capacity vs Congestion: Lower Capacity = More Congestion',
                fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / 'capacity_congestion_scatter.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {filepath}")


def plot_capacity_drop_analysis(all_results):
    """Visualize capacity drop analysis: proximity to drops and local gradient"""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    for idx, (city_code, (traffic, stats_result)) in enumerate(all_results.items()):
        city_name = CITIES[city_code]['name']
        color = CITIES[city_code]['color']

        # Top row: Distance to capacity drop vs congestion
        ax = axes[0, idx]
        if 'dist_to_cap_drop' in traffic.columns:
            valid = traffic[['dist_to_cap_drop', 'jam_factor_mean']].dropna()
            ax.scatter(valid['dist_to_cap_drop'], valid['jam_factor_mean'],
                      alpha=0.3, s=10, color=color)
            # Regression line
            slope, intercept, r, p, se = stats.linregress(
                valid['dist_to_cap_drop'], valid['jam_factor_mean']
            )
            x_line = np.linspace(valid['dist_to_cap_drop'].min(), valid['dist_to_cap_drop'].max(), 100)
            ax.plot(x_line, slope * x_line + intercept, 'r-', linewidth=2, label=f'r = {r:.3f}')
            ax.set_xlabel('Distance to Nearest Capacity Drop')
            ax.set_ylabel('Jam Factor' if idx == 0 else '')
            ax.set_title(f'{city_name}\n(n_drops={stats_result.get("n_capacity_drops", 0)})', fontweight='bold')
            ax.legend()
        else:
            ax.text(0.5, 0.5, 'No capacity\ndrops detected', ha='center', va='center',
                   transform=ax.transAxes)
            ax.set_title(f'{city_name}', fontweight='bold')
        ax.grid(alpha=0.3)

        # Bottom row: Local bottleneck vs non-bottleneck box plot
        ax = axes[1, idx]
        if 'is_local_bottleneck' in traffic.columns:
            bn = traffic[traffic['is_local_bottleneck']]['jam_factor_mean'].dropna()
            non_bn = traffic[~traffic['is_local_bottleneck']]['jam_factor_mean'].dropna()

            bp = ax.boxplot([bn, non_bn],
                           labels=['Local\nBottleneck', 'Non-\nBottleneck'],
                           patch_artist=True)
            colors_bp = ['#e74c3c', '#27ae60']
            for patch, c in zip(bp['boxes'], colors_bp):
                patch.set_facecolor(c)
                patch.set_alpha(0.7)

            p_val = stats_result.get('local_bn_p_value', 1)
            sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
            d = stats_result.get('local_bn_effect_size', 0)
            ax.set_title(f'p={p_val:.4f} {sig}, d={d:.3f}', fontsize=10)
        ax.set_ylabel('Jam Factor' if idx == 0 else '')
        ax.grid(axis='y', alpha=0.3)

    axes[0, 1].set_title(axes[0, 1].get_title(), fontweight='bold')
    fig.suptitle('Spatial Capacity Drop Analysis:\nProximity to Capacity Transitions & Local Bottlenecks',
                fontsize=14, fontweight='bold')
    plt.tight_layout()

    filepath = FIGURES_DIR / 'capacity_drop_spatial_analysis.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {filepath}")


def main():
    print("=" * 70)
    print("BOTTLENECK ANALYSIS")
    print("=" * 70)
    print("\nProving: Congestion occurs at capacity-constrained segments (bottlenecks)")
    print("         NOT necessarily at high-POI activity centers")

    all_results = {}

    for city_code in CITIES.keys():
        traffic, stats_result = analyze_bottlenecks(city_code)
        all_results[city_code] = (traffic, stats_result)

    # Create visualizations
    print("\n" + "=" * 70)
    print("Creating visualizations...")
    plot_bottleneck_analysis(all_results)
    plot_capacity_correlation(all_results)
    plot_capacity_drop_analysis(all_results)

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY: Bottleneck Effect on Congestion")
    print("=" * 70)

    print(f"\n{'City':<12} {'Low Cap JF':<12} {'High Cap JF':<12} {'Difference':<12} {'p-value':<10} {'Effect'}")
    print("-" * 70)

    for city_code, (_, stats_result) in all_results.items():
        city = stats_result['city']
        low = stats_result['low_cap_jf']
        high = stats_result['high_cap_jf']
        diff = stats_result['cap_diff_pct']
        p = stats_result['cap_p_value']
        d = stats_result['cap_effect_size']

        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        print(f"{city:<12} {low:<12.3f} {high:<12.3f} {diff:>+10.1f}% {p:<10.4f} d={d:.2f} {sig}")

    print("\n" + "-" * 70)
    print("Significance: *** p<0.001, ** p<0.01, * p<0.05")

    # Spatial capacity drop summary
    print("\n" + "=" * 70)
    print("SUMMARY: Spatial Capacity Drop Analysis")
    print("=" * 70)

    print(f"\n{'City':<12} {'Cap Drops':<11} {'Near JF':<10} {'Far JF':<10} {'p-value':<10} {'Local BN d':<10}")
    print("-" * 70)

    for city_code, (_, stats_result) in all_results.items():
        city = stats_result['city']
        n_drops = stats_result.get('n_capacity_drops', 0)
        near_jf = stats_result.get('near_drop_jf', np.nan)
        far_jf = stats_result.get('far_drop_jf', np.nan)
        p_drop = stats_result.get('drop_prox_p_value', np.nan)
        d_local = stats_result.get('local_bn_effect_size', np.nan)

        sig = "***" if p_drop < 0.001 else "**" if p_drop < 0.01 else "*" if p_drop < 0.05 else "" if not np.isnan(p_drop) else ""
        print(f"{city:<12} {n_drops:<11} {near_jf:<10.3f} {far_jf:<10.3f} {p_drop:<10.4f} d={d_local:.3f} {sig}")

    print("\n" + "-" * 70)

    # Compare with POI effect
    print("\n" + "=" * 70)
    print("COMPARISON: Bottleneck Effect vs POI Effect")
    print("=" * 70)
    print(f"\n{'City':<12} {'Bottleneck Δ':<15} {'POI Zone Δ':<15} {'Winner'}")
    print("-" * 50)

    # POI effect from activity_zone_results.csv
    poi_effects = {
        'Jakarta': 0.1,
        'Bandung': 0.1,
        'Semarang': -0.2
    }

    for city_code, (_, stats_result) in all_results.items():
        city = stats_result['city']
        bottleneck_diff = stats_result['cap_diff_pct']
        poi_diff = poi_effects.get(city, 0)

        winner = "BOTTLENECK" if abs(bottleneck_diff) > abs(poi_diff) else "POI" if abs(poi_diff) > abs(bottleneck_diff) else "Tie"
        print(f"{city:<12} {bottleneck_diff:>+13.1f}% {poi_diff:>+13.1f}% {winner:>12}")

    # Save results
    results_df = pd.DataFrame([r[1] for r in all_results.values()])
    results_path = OUTPUT_DIR / 'bottleneck_analysis_results.csv'
    results_df.to_csv(results_path, index=False)
    print(f"\nSaved: {results_path}")

    # Key interpretation
    print("\n" + "=" * 70)
    print("KEY INTERPRETATION")
    print("=" * 70)
    print("""
    BOTTLENECK vs ACTIVITY CENTER:

    1. AGGREGATE CAPACITY analysis (low vs high capacity roads)
       - Tests whether low-capacity roads are more congested overall

    2. SPATIAL CAPACITY DROPS (graph-based)
       - Detects nodes where incoming capacity > outgoing capacity
       - Tests whether proximity to capacity transitions predicts congestion
       - Stronger test of bottleneck hypothesis (localized flow constraints)

    3. LOCAL CAPACITY GRADIENT (neighborhood analysis)
       - Identifies segments with less capacity than spatial neighbors
       - These are local bottlenecks embedded in higher-capacity surroundings
       - Most direct test: relative capacity deficit → congestion?

    4. ACTIVITY CENTERS (POI density) — from prior analysis
       - High-POI areas have same congestion as low-POI areas
       - Effect size is near zero

    5. INTERPRETATION:
       - If spatial capacity drops show significant effects → bottleneck hypothesis supported
       - If no capacity metric predicts congestion → congestion is demand-driven (temporal)
       - Compare effect sizes across all approaches for final conclusion
    """)

    print("=" * 70)
    print("DONE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
