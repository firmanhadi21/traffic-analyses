#!/usr/bin/env python3
"""
Revision Analyses for Manuscript Revisions
Addresses reviewer concerns with additional statistical analyses.

Analyses included:
1. Spatial weight sensitivity (Moran's I with multiple weight specifications)
2. FDR-corrected LISA
3. Period-specific Moran's I
4. Spatial regression (Spatial Lag, Spatial Error, OLS multiple)
5. Getis-Ord Gi* formal results
6. Match quality distribution (HERE-OSMnx spatial join)
7. POI buffer sensitivity

Run on HPC where geopandas/pysal/osmnx are available.
"""

import pandas as pd
import numpy as np
import geopandas as gpd
import osmnx as ox
import networkx as nx
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from esda.moran import Moran, Moran_Local
from esda.getisord import G_Local
from libpysal.weights import KNN, DistanceBand
from statsmodels.stats.multitest import multipletests

# Try importing spreg for spatial regression
try:
    import spreg
    SPREG_AVAILABLE = True
except ImportError:
    SPREG_AVAILABLE = False
    print("WARNING: spreg not available. Spatial regression will be skipped.")
    print("Install with: pip install spreg")

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

CITIES = {
    'smg': {
        'name': 'Semarang',
        'folder': 'traffic_smg_output',
        'bbox': (110.227, -7.105, 110.528, -6.919),
        'osm_network': 'osm_network_semarang.gpkg',
    },
    'bdg': {
        'name': 'Bandung',
        'folder': 'traffic_bdg_output',
        'bbox': (107.4688, -7.0848, 107.8261, -6.8294),
        'osm_network': 'osm_network_bandung.gpkg',
    },
    'jkt': {
        'name': 'Jakarta',
        'folder': 'traffic_jkt_output',
        'bbox': (106.6036, -6.4096, 107.11, -6.0911),
        'osm_network': 'osm_network_jakarta.gpkg',
    },
}

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]


def load_traffic_data(city_code, period='evening_peak'):
    """Load traffic GeoPackage for a city and period."""
    filepath = f"{CITIES[city_code]['folder']}/{period}_{city_code}.gpkg"
    return gpd.read_file(filepath)


def get_centroids_gdf(gdf):
    """Return a copy of gdf with geometry replaced by centroids."""
    gdf_c = gdf.copy()
    gdf_c['geometry'] = gdf_c.geometry.centroid
    return gdf_c


# ---------------------------------------------------------------------------
# 1. Spatial Weight Sensitivity Analysis
# ---------------------------------------------------------------------------

def spatial_weight_sensitivity(all_city_data):
    """
    Compute Moran's I with multiple spatial weight specifications:
    KNN k=4, k=8, k=12 and distance-band 500m, 1000m.
    """
    print("\n" + "=" * 70)
    print("1. SPATIAL WEIGHT SENSITIVITY ANALYSIS")
    print("=" * 70)

    results = []

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']
        gdf = data['evening_peak']
        y = gdf['jam_factor_mean'].values
        gdf_c = get_centroids_gdf(gdf)

        # Project to local UTM for distance-based weights
        gdf_proj = gdf_c.to_crs(gdf_c.estimate_utm_crs())

        # KNN weights
        for k in [4, 8, 12]:
            print(f"  {city_name} KNN k={k}...")
            try:
                w = KNN.from_dataframe(gdf_c, k=k)
                w.transform = 'r'
                mi = Moran(y, w)
                results.append({
                    'city': city_name,
                    'weight_type': f'KNN_k{k}',
                    'morans_I': mi.I,
                    'z_score': mi.z_norm,
                    'p_value': mi.p_norm,
                    'n': len(y),
                })
            except Exception as e:
                print(f"    Error: {e}")

        # Distance-band weights (in meters using projected CRS)
        for dist in [500, 1000]:
            print(f"  {city_name} Distance band {dist}m...")
            try:
                w = DistanceBand.from_dataframe(gdf_proj, threshold=dist, binary=False)
                w.transform = 'r'
                mi = Moran(y, w)
                results.append({
                    'city': city_name,
                    'weight_type': f'Distance_{dist}m',
                    'morans_I': mi.I,
                    'z_score': mi.z_norm,
                    'p_value': mi.p_norm,
                    'n': len(y),
                })
            except Exception as e:
                print(f"    Error: {e}")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'morans_i_sensitivity.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    print(df.to_string(index=False))
    return df


# ---------------------------------------------------------------------------
# 2. FDR-Corrected LISA
# ---------------------------------------------------------------------------

def fdr_corrected_lisa(all_city_data):
    """
    Re-run LISA with Benjamini-Hochberg FDR correction.
    Report observed significant, expected by chance, FDR-corrected counts.
    """
    print("\n" + "=" * 70)
    print("2. FDR-CORRECTED LISA ANALYSIS")
    print("=" * 70)

    results = []

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']
        gdf = data['evening_peak']
        y = gdf['jam_factor_mean'].values
        gdf_c = get_centroids_gdf(gdf)
        n = len(y)

        print(f"  {city_name} (n={n})...")

        w = KNN.from_dataframe(gdf_c, k=8)
        w.transform = 'r'
        lisa = Moran_Local(y, w, permutations=999)

        p_values = lisa.p_sim
        quadrant_labels = {1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}

        # Original significance (alpha=0.05)
        sig_original = np.sum(p_values < 0.05)
        expected_by_chance = int(n * 0.05)

        # FDR correction (Benjamini-Hochberg)
        reject_fdr, pvals_corrected, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')
        sig_fdr = np.sum(reject_fdr)

        # Cluster counts after FDR correction
        cluster_counts_fdr = {'HH': 0, 'LL': 0, 'HL': 0, 'LH': 0, 'NS': 0}
        for i in range(n):
            if reject_fdr[i]:
                q = int(lisa.q[i])
                label = quadrant_labels.get(q, 'NS')
                cluster_counts_fdr[label] += 1
            else:
                cluster_counts_fdr['NS'] += 1

        results.append({
            'city': city_name,
            'n_segments': n,
            'sig_original_p05': int(sig_original),
            'expected_by_chance': expected_by_chance,
            'sig_fdr_corrected': int(sig_fdr),
            'HH_fdr': cluster_counts_fdr['HH'],
            'LL_fdr': cluster_counts_fdr['LL'],
            'HL_fdr': cluster_counts_fdr['HL'],
            'LH_fdr': cluster_counts_fdr['LH'],
            'NS_fdr': cluster_counts_fdr['NS'],
        })

        print(f"    Original significant (p<0.05): {sig_original}")
        print(f"    Expected by chance (5%):        {expected_by_chance}")
        print(f"    FDR-corrected significant:      {sig_fdr}")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'lisa_fdr_corrected.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    return df


# ---------------------------------------------------------------------------
# 3. Period-Specific Moran's I
# ---------------------------------------------------------------------------

def period_specific_morans_i(all_city_data):
    """
    Compute Moran's I separately for each of 8 temporal periods x 3 cities.
    """
    print("\n" + "=" * 70)
    print("3. PERIOD-SPECIFIC MORAN'S I")
    print("=" * 70)

    results = []

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']

        for period in TIME_PERIODS:
            print(f"  {city_name} - {period}...")
            gdf = data[period]
            y = gdf['jam_factor_mean'].values
            gdf_c = get_centroids_gdf(gdf)

            try:
                w = KNN.from_dataframe(gdf_c, k=8)
                w.transform = 'r'
                mi = Moran(y, w)
                results.append({
                    'city': city_name,
                    'period': period,
                    'morans_I': mi.I,
                    'z_score': mi.z_norm,
                    'p_value': mi.p_norm,
                    'n': len(y),
                })
            except Exception as e:
                print(f"    Error: {e}")
                results.append({
                    'city': city_name,
                    'period': period,
                    'morans_I': np.nan,
                    'z_score': np.nan,
                    'p_value': np.nan,
                    'n': len(y),
                })

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'morans_i_by_period.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    print(df.to_string(index=False))
    return df


# ---------------------------------------------------------------------------
# 4. Spatial Regression
# ---------------------------------------------------------------------------

def download_osm_network(city_code):
    """Download OSM network and compute betweenness centrality."""
    city = CITIES[city_code]
    print(f"  Downloading {city['name']} network...")
    G = ox.graph_from_bbox(bbox=city['bbox'], network_type='drive', simplify=True)
    print(f"    Nodes: {len(G.nodes):,}, Edges: {len(G.edges):,}")

    # Betweenness centrality (sampled for large networks)
    print(f"    Computing betweenness centrality...")
    k_sample = min(500, len(G.nodes))
    edge_bc = nx.edge_betweenness_centrality(G, normalized=True, k=k_sample, weight='length')
    nx.set_edge_attributes(G, edge_bc, 'betweenness')

    edges = ox.graph_to_gdfs(G, nodes=False)
    return G, edges


def _download_pois(city_code):
    """Download POIs for a city and return as GeoDataFrame of point geometries."""
    city = CITIES[city_code]
    bbox = city['bbox']
    tags = {
        'amenity': True, 'shop': True, 'office': True,
        'tourism': True, 'leisure': True, 'building': ['commercial', 'retail', 'office']
    }
    pois = ox.features_from_bbox(bbox=bbox, tags=tags)
    pois_pts = pois.copy()
    pois_pts['geometry'] = pois_pts.geometry.centroid
    return pois_pts[['geometry']]


def _get_walk_network(city_code):
    """Download walkable street network for network-distance POI analysis."""
    city = CITIES[city_code]
    G_walk = ox.graph_from_bbox(bbox=city['bbox'], network_type='walk', simplify=True)
    return G_walk


def compute_poi_density_network(gdf, city_code, G_walk, pois_pts, dist_m=400):
    """
    Compute POI density using network distance along road segments.

    For each traffic segment centroid, finds the nearest network node and
    creates a network-distance subgraph within dist_m. Then counts POIs
    whose nearest network node falls within that subgraph.

    Parameters
    ----------
    gdf : GeoDataFrame
        Traffic data with geometry.
    city_code : str
        City identifier.
    G_walk : networkx.MultiDiGraph
        Walking network graph from OSMnx.
    pois_pts : GeoDataFrame
        POI point geometries.
    dist_m : float
        Network distance threshold in meters.

    Returns
    -------
    np.ndarray
        POI count for each traffic segment.
    """
    city_name = CITIES[city_code]['name']
    print(f"    Computing network-distance POI density for {city_name} "
          f"(dist={dist_m}m)...")

    # Ensure CRS alignment
    gdf_wgs = gdf.to_crs(epsg=4326) if gdf.crs.to_epsg() != 4326 else gdf
    pois_wgs = pois_pts.to_crs(epsg=4326) if pois_pts.crs.to_epsg() != 4326 else pois_pts

    # Get traffic segment centroids
    traffic_centroids = gdf_wgs.geometry.centroid

    # Snap POIs to nearest network node (once per city+radius call)
    poi_coords = np.array([(p.y, p.x) for p in pois_wgs.geometry])
    poi_nodes = ox.nearest_nodes(G_walk, X=poi_coords[:, 1], Y=poi_coords[:, 0])

    # Snap traffic centroids to nearest network node
    traffic_coords_y = np.array([c.y for c in traffic_centroids])
    traffic_coords_x = np.array([c.x for c in traffic_centroids])
    traffic_nodes = ox.nearest_nodes(G_walk, X=traffic_coords_x, Y=traffic_coords_y)

    # Build a set of POI nodes for fast lookup
    poi_node_set = set(poi_nodes)
    # Count POIs per node (a node may have multiple POIs)
    from collections import Counter
    poi_node_counts = Counter(poi_nodes)

    poi_counts = np.zeros(len(gdf), dtype=int)

    for i, src_node in enumerate(traffic_nodes):
        try:
            # Get all nodes reachable within dist_m via network distance
            reachable = nx.single_source_dijkstra_path_length(
                G_walk, src_node, cutoff=dist_m, weight='length'
            )
            # Count POIs at reachable nodes
            count = sum(
                poi_node_counts[node]
                for node in reachable
                if node in poi_node_set
            )
            poi_counts[i] = count
        except nx.NetworkXError:
            poi_counts[i] = 0

        if (i + 1) % 500 == 0:
            print(f"      Processed {i+1}/{len(gdf)} segments...")

    print(f"      Done. Mean POI count: {poi_counts.mean():.1f}")
    return poi_counts


def spatial_regression_analysis(all_city_data):
    """
    Fit Spatial Lag, Spatial Error, and OLS multiple regression models.
    Predictors: centrality, POI density, temporal dummies, capacity score.
    """
    print("\n" + "=" * 70)
    print("4. SPATIAL REGRESSION ANALYSIS")
    print("=" * 70)

    if not SPREG_AVAILABLE:
        print("  SKIPPED: spreg not available.")
        return None

    results = []

    for city_code in CITIES.keys():
        city_name = CITIES[city_code]['name']
        print(f"\n  Processing {city_name}...")

        gdf = all_city_data[city_code]['evening_peak']
        y = gdf['jam_factor_mean'].values.reshape(-1, 1)
        gdf_c = get_centroids_gdf(gdf)

        # Spatial weights
        w = KNN.from_dataframe(gdf_c, k=8)
        w.transform = 'r'

        # Download network for centrality
        try:
            _, osm_edges = download_osm_network(city_code)
        except Exception as e:
            print(f"    Error downloading network: {e}")
            continue

        # Spatial join to get betweenness
        osm_c = osm_edges.copy()
        if gdf.crs != osm_c.crs:
            osm_c = osm_c.to_crs(gdf.crs)
        osm_c['geometry'] = osm_c.geometry.centroid

        traffic_c = gdf_c[['geometry']].copy()
        joined = gpd.sjoin_nearest(
            traffic_c, osm_c[['geometry', 'betweenness']],
            how='left', distance_col='match_dist'
        )
        joined = joined[~joined.index.duplicated(keep='first')]
	# Filter by 200m threshold
        max_dist = 0.002
        joined.loc[joined['match_dist'] > max_dist, 'betweenness'] = np.nan

        # Build predictor matrix
        betweenness = joined['betweenness'].values
        # Fill NaN with median
        med_bc = np.nanmedian(betweenness)
        betweenness = np.where(np.isnan(betweenness), med_bc, betweenness)

        # POI density at 400m network distance
        try:
            G_walk = _get_walk_network(city_code)
            pois_pts = _download_pois(city_code)
            poi_density = compute_poi_density_network(gdf, city_code, G_walk, pois_pts, dist_m=400)
        except Exception as e:
            print(f"    Error computing POI density: {e}")
            poi_density = np.zeros(len(gdf))

        X = np.column_stack([betweenness, poi_density])
        var_names = ['betweenness', 'poi_density_400m']

        # --- OLS ---
        print(f"    Fitting OLS...")
        try:
            ols = spreg.OLS(y, X, w=w, name_y='jam_factor', name_x=var_names)
            ols_r2 = ols.r2
            ols_betas = ols.betas.flatten()
            ols_pvals = [ols.t_stat[i][1] for i in range(len(ols.t_stat))]
        except Exception as e:
            print(f"    OLS error: {e}")
            ols_r2 = np.nan
            ols_betas = [np.nan] * (len(var_names) + 1)
            ols_pvals = [np.nan] * (len(var_names) + 1)

        # --- Spatial Lag Model ---
        print(f"    Fitting Spatial Lag model...")
        try:
            slag = spreg.GM_Lag(y, X, w=w, name_y='jam_factor', name_x=var_names)
            slag_r2 = slag.pr2
            slag_rho = slag.betas[-1][0]
            slag_betas = slag.betas.flatten()
            slag_pvals = [slag.z_stat[i][1] for i in range(len(slag.z_stat))]
        except Exception as e:
            print(f"    Spatial Lag error: {e}")
            slag_r2 = np.nan
            slag_rho = np.nan
            slag_betas = [np.nan] * (len(var_names) + 2)
            slag_pvals = [np.nan] * (len(var_names) + 2)

        # --- Spatial Error Model ---
        print(f"    Fitting Spatial Error model...")
        try:
            serr = spreg.GM_Error(y, X, w=w, name_y='jam_factor', name_x=var_names)
            serr_r2 = serr.pr2
            serr_lambda = serr.betas[-1][0]
            serr_betas = serr.betas.flatten()
            serr_pvals = [serr.z_stat[i][1] for i in range(len(serr.z_stat))]
        except Exception as e:
            print(f"    Spatial Error error: {e}")
            serr_r2 = np.nan
            serr_lambda = np.nan
            serr_betas = [np.nan] * (len(var_names) + 2)
            serr_pvals = [np.nan] * (len(var_names) + 2)

        results.append({
            'city': city_name,
            'n': len(y),
            # OLS results
            'ols_r2': ols_r2,
            'ols_beta_const': ols_betas[0] if len(ols_betas) > 0 else np.nan,
            'ols_beta_betweenness': ols_betas[1] if len(ols_betas) > 1 else np.nan,
            'ols_beta_poi': ols_betas[2] if len(ols_betas) > 2 else np.nan,
            'ols_p_betweenness': ols_pvals[1] if len(ols_pvals) > 1 else np.nan,
            'ols_p_poi': ols_pvals[2] if len(ols_pvals) > 2 else np.nan,
            # Spatial Lag results
            'slag_r2': slag_r2,
            'slag_rho': slag_rho,
            'slag_beta_betweenness': slag_betas[1] if len(slag_betas) > 1 else np.nan,
            'slag_beta_poi': slag_betas[2] if len(slag_betas) > 2 else np.nan,
            'slag_p_betweenness': slag_pvals[1] if len(slag_pvals) > 1 else np.nan,
            'slag_p_poi': slag_pvals[2] if len(slag_pvals) > 2 else np.nan,
            # Spatial Error results
            'serr_r2': serr_r2,
            'serr_lambda': serr_lambda,
            'serr_beta_betweenness': serr_betas[1] if len(serr_betas) > 1 else np.nan,
            'serr_beta_poi': serr_betas[2] if len(serr_betas) > 2 else np.nan,
            'serr_p_betweenness': serr_pvals[1] if len(serr_pvals) > 1 else np.nan,
            'serr_p_poi': serr_pvals[2] if len(serr_pvals) > 2 else np.nan,
        })

        print(f"    OLS R²={ols_r2:.4f}, Lag R²={slag_r2:.4f}, Error R²={serr_r2:.4f}")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'spatial_regression_results.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    return df


# ---------------------------------------------------------------------------
# 5. Getis-Ord Gi* Formal Results
# ---------------------------------------------------------------------------

def getis_ord_formal(all_city_data):
    """
    Compute Gi* statistics and tabulate hot/cold spot counts.
    Compare with LISA findings.
    """
    print("\n" + "=" * 70)
    print("5. GETIS-ORD Gi* FORMAL RESULTS")
    print("=" * 70)

    results = []

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']
        gdf = data['evening_peak']
        y = gdf['jam_factor_mean'].values
        gdf_c = get_centroids_gdf(gdf)
        n = len(y)

        print(f"  {city_name} (n={n})...")

        w = KNN.from_dataframe(gdf_c, k=8)
        w.transform = 'B'  # Binary weights for Gi*

        gi = G_Local(y, w, star=True, permutations=999)

        z_scores = gi.Zs
        p_values = gi.p_sim

        # Classify hot/cold spots (alpha=0.05)
        hot_spots = np.sum((z_scores > 0) & (p_values < 0.05))
        cold_spots = np.sum((z_scores < 0) & (p_values < 0.05))
        not_sig = n - hot_spots - cold_spots

        # Confidence levels
        hot_99 = np.sum((z_scores > 0) & (p_values < 0.01))
        hot_95 = np.sum((z_scores > 0) & (p_values < 0.05) & (p_values >= 0.01))
        cold_99 = np.sum((z_scores < 0) & (p_values < 0.01))
        cold_95 = np.sum((z_scores < 0) & (p_values < 0.05) & (p_values >= 0.01))

        results.append({
            'city': city_name,
            'n_segments': n,
            'hot_spots_p05': int(hot_spots),
            'hot_spots_p01': int(hot_99),
            'hot_spots_p05_only': int(hot_95),
            'cold_spots_p05': int(cold_spots),
            'cold_spots_p01': int(cold_99),
            'cold_spots_p05_only': int(cold_95),
            'not_significant': int(not_sig),
            'pct_significant': round((hot_spots + cold_spots) / n * 100, 1),
        })

        print(f"    Hot spots (p<0.05): {hot_spots} ({hot_spots/n*100:.1f}%)")
        print(f"    Cold spots (p<0.05): {cold_spots} ({cold_spots/n*100:.1f}%)")
        print(f"    Not significant: {not_sig} ({not_sig/n*100:.1f}%)")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'getis_ord_results.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    return df


# ---------------------------------------------------------------------------
# 6. Match Quality Distribution
# ---------------------------------------------------------------------------

def match_quality_analysis(all_city_data):
    """
    Analyze centroid-to-centroid match distances for HERE <-> OSMnx spatial join.
    Report percentage within 50m, 100m, 150m, 200m.
    """
    print("\n" + "=" * 70)
    print("6. MATCH QUALITY DISTRIBUTION")
    print("=" * 70)

    results = []

    for city_code in CITIES.keys():
        city_name = CITIES[city_code]['name']
        print(f"\n  Processing {city_name}...")

        gdf = all_city_data[city_code]['evening_peak']

        # Download OSM network
        try:
            _, osm_edges = download_osm_network(city_code)
        except Exception as e:
            print(f"    Error: {e}")
            continue

        if gdf.crs != osm_edges.crs:
            osm_edges = osm_edges.to_crs(gdf.crs)

        traffic_c = get_centroids_gdf(gdf)[['geometry']].copy()
        osm_c = osm_edges.copy()
        osm_c['geometry'] = osm_c.geometry.centroid

        joined = gpd.sjoin_nearest(
            traffic_c, osm_c[['geometry']],
            how='left', distance_col='match_dist_deg'
        )

        # Convert degrees to approximate meters (at ~7S latitude)
        # 1 degree latitude ~ 111,000m, 1 degree longitude ~ 110,000m * cos(7) ~ 109,100m
        # Average ~ 110,000m
        match_dist_m = joined['match_dist_deg'].values * 110000

        n_total = len(match_dist_m)
        within_50 = np.sum(match_dist_m <= 50)
        within_100 = np.sum(match_dist_m <= 100)
        within_150 = np.sum(match_dist_m <= 150)
        within_200 = np.sum(match_dist_m <= 200)

        results.append({
            'city': city_name,
            'n_segments': n_total,
            'mean_dist_m': round(np.mean(match_dist_m), 1),
            'median_dist_m': round(np.median(match_dist_m), 1),
            'p25_dist_m': round(np.percentile(match_dist_m, 25), 1),
            'p75_dist_m': round(np.percentile(match_dist_m, 75), 1),
            'pct_within_50m': round(within_50 / n_total * 100, 1),
            'pct_within_100m': round(within_100 / n_total * 100, 1),
            'pct_within_150m': round(within_150 / n_total * 100, 1),
            'pct_within_200m': round(within_200 / n_total * 100, 1),
        })

        print(f"    Mean distance: {np.mean(match_dist_m):.1f}m")
        print(f"    Within 50m: {within_50/n_total*100:.1f}%")
        print(f"    Within 100m: {within_100/n_total*100:.1f}%")
        print(f"    Within 200m: {within_200/n_total*100:.1f}%")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'match_quality.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    return df


# ---------------------------------------------------------------------------
# 7. POI Buffer Sensitivity
# ---------------------------------------------------------------------------

def poi_network_distance_sensitivity(all_city_data):
    """
    Test POI density-congestion correlation at multiple network-distance radii:
    200m (short walk), 400m (~5 min walk), 800m (~10 min walk), 1200m (~15 min walk).

    Uses actual walking network distance along road segments rather than
    Euclidean buffers, providing a more realistic measure of pedestrian
    accessibility to activity centers.
    """
    print("\n" + "=" * 70)
    print("7. POI NETWORK-DISTANCE SENSITIVITY ANALYSIS")
    print("=" * 70)

    network_radii = [200, 400, 800, 1200]
    results = []

    for city_code in CITIES.keys():
        city_name = CITIES[city_code]['name']
        gdf = all_city_data[city_code]['evening_peak']
        jam = gdf['jam_factor_mean'].values

        # Download walk network and POIs once per city
        print(f"\n  {city_name}: downloading walk network and POIs...")
        try:
            G_walk = _get_walk_network(city_code)
            pois_pts = _download_pois(city_code)
        except Exception as e:
            print(f"    Error downloading network/POIs: {e}")
            continue

        for radius in network_radii:
            print(f"  {city_name} network distance={radius}m...")

            poi_counts = compute_poi_density_network(
                gdf, city_code, G_walk, pois_pts, dist_m=radius
            )

            # Correlations
            valid = ~(np.isnan(jam) | np.isnan(poi_counts.astype(float)))
            if valid.sum() < 50:
                print(f"    Too few valid values")
                continue

            pearson_r, pearson_p = stats.pearsonr(jam[valid], poi_counts[valid])
            spearman_r, spearman_p = stats.spearmanr(jam[valid], poi_counts[valid])

            results.append({
                'city': city_name,
                'network_distance_m': radius,
                'distance_type': 'network (walk)',
                'n': int(valid.sum()),
                'mean_poi_count': round(np.mean(poi_counts[valid]), 2),
                'pearson_r': round(pearson_r, 4),
                'pearson_p': round(pearson_p, 4),
                'spearman_r': round(spearman_r, 4),
                'spearman_p': round(spearman_p, 4),
                'r_squared': round(pearson_r ** 2, 6),
            })

            print(f"    Pearson r={pearson_r:.4f} (p={pearson_p:.4f}), "
                  f"Spearman r={spearman_r:.4f} (p={spearman_p:.4f})")

    df = pd.DataFrame(results)
    outpath = OUTPUT_DIR / 'poi_network_distance_sensitivity.csv'
    df.to_csv(outpath, index=False)
    print(f"\n  Saved: {outpath}")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("REVISION ANALYSES")
    print("Addressing reviewer concerns with additional statistical analyses")
    print("=" * 70)

    # Load all traffic data
    print("\nLoading traffic data for all cities and periods...")
    all_city_data = {}
    for city_code in CITIES.keys():
        city_data = {}
        for period in TIME_PERIODS:
            city_data[period] = load_traffic_data(city_code, period)
        all_city_data[city_code] = city_data
        n = len(city_data['evening_peak'])
        print(f"  {CITIES[city_code]['name']}: {n} segments")

    # Run analyses
    print("\n" + "#" * 70)
    print("# Running all revision analyses...")
    print("#" * 70)

    # 1. Spatial weight sensitivity (no network download needed)
    sw_results = spatial_weight_sensitivity(all_city_data)

    # 2. FDR-corrected LISA (no network download needed)
    fdr_results = fdr_corrected_lisa(all_city_data)

    # 3. Period-specific Moran's I (no network download needed)
    period_results = period_specific_morans_i(all_city_data)

    # 4. Spatial regression (needs network download)
    reg_results = spatial_regression_analysis(all_city_data)

    # 5. Getis-Ord Gi* (no network download needed)
    gi_results = getis_ord_formal(all_city_data)

    # 6. Match quality (needs network download)
    mq_results = match_quality_analysis(all_city_data)

    # 7. POI network-distance sensitivity (needs walk network + POI download)
    poi_results = poi_network_distance_sensitivity(all_city_data)

    # Summary
    print("\n" + "=" * 70)
    print("ALL REVISION ANALYSES COMPLETE")
    print("=" * 70)
    print(f"\nOutput files in {OUTPUT_DIR.absolute()}:")
    for f in sorted(OUTPUT_DIR.glob('*.csv')):
        print(f"  {f.name}")

    print("\nThese results should be used to update the manuscript tables.")
    print("See the plan in paper/comments.md for guidance on where to insert results.")


if __name__ == "__main__":
    main()
