#!/usr/bin/env python3
"""
Compute Network Centrality - Traffic Congestion Correlations
Downloads OSM networks, computes betweenness centrality, and correlates with traffic data
"""

import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

# City configurations with bounding boxes
CITIES = {
    'smg': {
        'name': 'Semarang',
        'bbox': (-6.919, -7.105, 110.528, 110.227),  # north, south, east, west
        'traffic_folder': 'traffic_smg_output'
    },
    'bdg': {
        'name': 'Bandung',
        'bbox': (-6.8294, -7.0848, 107.8261, 107.4688),
        'traffic_folder': 'traffic_bdg_output'
    },
    'jkt': {
        'name': 'Jakarta',
        'bbox': (-6.0911, -6.4096, 107.11, 106.6036),
        'traffic_folder': 'traffic_jkt_output'
    }
}


def download_network_with_centrality(city_code):
    """Download OSM network and compute betweenness centrality"""
    city = CITIES[city_code]
    print(f"\n  Downloading {city['name']} network...")

    try:
        G = ox.graph_from_bbox(bbox=city['bbox'], network_type='drive', simplify=True)
        print(f"    Nodes: {len(G.nodes):,}, Edges: {len(G.edges):,}")

        # Compute edge betweenness centrality (can be slow for large networks)
        print(f"    Computing betweenness centrality...")

        # For large networks, use sampling
        if len(G.nodes) > 5000:
            # Sample nodes for faster computation
            k = min(500, len(G.nodes))
            print(f"    Using {k} sample nodes for large network...")
            edge_bc = nx.edge_betweenness_centrality(G, normalized=True, k=k)
        else:
            edge_bc = nx.edge_betweenness_centrality(G, normalized=True)

        nx.set_edge_attributes(G, edge_bc, 'betweenness')

        # Convert to GeoDataFrame
        edges = ox.graph_to_gdfs(G, nodes=False)
        print(f"    Done. Max betweenness: {edges['betweenness'].max():.6f}")

        return edges

    except Exception as e:
        print(f"    Error: {e}")
        return None


def compute_correlation(city_code, osm_edges):
    """Compute correlation between betweenness centrality and jam factor"""
    city = CITIES[city_code]

    # Load traffic data
    traffic_path = f"{city['traffic_folder']}/evening_peak_{city_code}.gpkg"
    traffic = gpd.read_file(traffic_path)
    print(f"    Traffic segments: {len(traffic)}")

    # Ensure same CRS
    if osm_edges.crs != traffic.crs:
        osm_edges = osm_edges.to_crs(traffic.crs)

    # Create centroid-based spatial join
    traffic_centroids = traffic.copy()
    traffic_centroids['geometry'] = traffic_centroids.geometry.centroid

    osm_centroids = osm_edges.copy()
    osm_centroids['osm_geom'] = osm_edges.geometry  # Keep original geometry
    osm_centroids['geometry'] = osm_centroids.geometry.centroid

    # Nearest join with distance
    print(f"    Performing spatial join...")
    joined = gpd.sjoin_nearest(
        traffic_centroids[['geometry', 'jam_factor_mean', 'fid']],
        osm_centroids[['geometry', 'betweenness']],
        how='left',
        distance_col='match_dist'
    )

    # Filter by distance (approximately 200m in degrees at equator)
    # At ~7 degrees south, 1 degree ≈ 111km, so 0.002 ≈ 220m
    max_dist = 0.002
    matched = joined[joined['match_dist'] < max_dist].copy()
    print(f"    Matched segments: {len(matched)} ({len(matched)/len(traffic)*100:.1f}%)")

    if len(matched) < 50:
        print(f"    Too few matches for reliable correlation")
        return None

    # Remove NaN values
    valid = matched.dropna(subset=['jam_factor_mean', 'betweenness'])

    if len(valid) < 50:
        print(f"    Too few valid values after removing NaN")
        return None

    jam = valid['jam_factor_mean'].values
    bc = valid['betweenness'].values

    # Compute correlations
    pearson_r, pearson_p = stats.pearsonr(jam, bc)
    spearman_r, spearman_p = stats.spearmanr(jam, bc)

    print(f"    Pearson r = {pearson_r:.4f} (p = {pearson_p:.4f})")
    print(f"    Spearman ρ = {spearman_r:.4f} (p = {spearman_p:.4f})")

    return {
        'city': city['name'],
        'n_matched': len(valid),
        'match_rate': len(matched) / len(traffic) * 100,
        'pearson_r': pearson_r,
        'pearson_p': pearson_p,
        'spearman_r': spearman_r,
        'spearman_p': spearman_p
    }


def main():
    print("=" * 70)
    print("CENTRALITY-CONGESTION CORRELATION ANALYSIS")
    print("=" * 70)

    results = []

    for city_code in CITIES.keys():
        city_name = CITIES[city_code]['name']
        print(f"\n{'='*50}")
        print(f"Processing {city_name}...")
        print(f"{'='*50}")

        # Download network with centrality
        osm_edges = download_network_with_centrality(city_code)

        if osm_edges is None:
            print(f"  Skipping {city_name} due to network download error")
            continue

        # Compute correlation
        result = compute_correlation(city_code, osm_edges)

        if result:
            results.append(result)

    # Generate summary table
    if results:
        print("\n" + "=" * 70)
        print("SUMMARY: Centrality-Congestion Correlations")
        print("=" * 70)
        print(f"{'City':<12} {'n':>8} {'Match%':>8} {'Pearson r':>10} {'p-value':>10} {'Spearman ρ':>10} {'p-value':>10}")
        print("-" * 70)

        for r in results:
            print(f"{r['city']:<12} {r['n_matched']:>8} {r['match_rate']:>7.1f}% "
                  f"{r['pearson_r']:>10.4f} {r['pearson_p']:>10.4f} "
                  f"{r['spearman_r']:>10.4f} {r['spearman_p']:>10.4f}")

        # Save to CSV
        df = pd.DataFrame(results)
        csv_path = OUTPUT_DIR / 'centrality_correlations.csv'
        df.to_csv(csv_path, index=False)
        print(f"\nSaved: {csv_path}")

        # Interpretation
        print("\n" + "-" * 70)
        print("INTERPRETATION:")
        for r in results:
            sig = "significant" if r['pearson_p'] < 0.05 else "not significant"
            direction = "positive" if r['pearson_r'] > 0 else "negative"
            strength = "weak" if abs(r['pearson_r']) < 0.3 else "moderate" if abs(r['pearson_r']) < 0.5 else "strong"
            print(f"  {r['city']}: {strength} {direction} correlation ({sig}, r={r['pearson_r']:.3f})")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
