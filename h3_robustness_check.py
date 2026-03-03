#!/usr/bin/env python3
"""
H3 Hexagonal Aggregation — Robustness Check
============================================
Aggregates traffic congestion, POI density, and network centrality
into Uber H3 hexagonal bins at resolutions 8 and 9.

Addresses the scale-mismatch hypothesis: segment-level analysis may miss
neighbourhood-level spatial patterns that only emerge when variables are
measured at the same spatial grain.

Methodology:
  1. Assign each road segment centroid to an H3 hex cell
  2. Aggregate jam_factor_mean per hexagon (observation-weighted)
  3. Fetch POIs from OSM, count per hexagon
  4. Fetch OSM network, compute betweenness centrality, mean per hexagon
  5. Pearson + Spearman correlations at hex level
  6. Moran's I on hex-aggregated congestion
  7. Compare all results against existing segment-level findings

Resolutions:
  8  — ~461 m hex diameter, ~0.46 km² area  (neighbourhood scale)
  9  — ~174 m hex diameter, ~0.10 km² area  (block scale)
"""

import h3
import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
from shapely.geometry import Polygon
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

ox.settings.use_cache = True
ox.settings.log_console = False

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("analysis_results")
OUTPUT_DIR.mkdir(exist_ok=True)

FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# ── City config (same bbox convention as existing scripts) ───────────────────
CITIES = {
    'smg': {
        'name': 'Semarang',
        'bbox': (110.227, -7.105, 110.528, -6.919),
        'traffic_folder': 'traffic_smg_output',
        'color': '#2ecc71',
    },
    'bdg': {
        'name': 'Bandung',
        'bbox': (107.4688, -7.0848, 107.8261, -6.8294),
        'traffic_folder': 'traffic_bdg_output',
        'color': '#3498db',
    },
    'jkt': {
        'name': 'Jakarta',
        'bbox': (106.6036, -6.4096, 107.11, -6.0911),
        'traffic_folder': 'traffic_jkt_output',
        'color': '#e74c3c',
    },
}

PERIODS = [
    'morning_peak', 'evening_peak', 'lunch_hours',
    'morning_offpeak', 'afternoon_offpeak', 'evening_offpeak',
    'night', 'late_night',
]

H3_RESOLUTIONS = [8, 9]

H3_RES_INFO = {
    8: {'diameter_m': 461,  'area_km2': 0.46},
    9: {'diameter_m': 174,  'area_km2': 0.10},
}

# All POI tags used in the existing poi_congestion_analysis.py
POI_TAGS = {
    'shop': True,
    'office': True,
    'amenity': [
        'school', 'university', 'college', 'kindergarten',
        'hospital', 'clinic', 'doctors', 'pharmacy',
        'restaurant', 'cafe', 'fast_food', 'food_court',
        'bus_station', 'fuel',
    ],
    'public_transport': True,
}

# Segment-level benchmark results (from existing analyses) for comparison
SEGMENT_BENCHMARKS = {
    'poi_spearman_r':  {'Semarang': -0.007, 'Bandung': -0.013, 'Jakarta': -0.0005},
    'cent_spearman_r': {'Semarang': -0.011, 'Bandung':  0.012, 'Jakarta':  0.002},
    'morans_I':        {'Semarang': -0.0039,'Bandung':  0.0075,'Jakarta':  0.0026},
}


# ── H3 helpers ────────────────────────────────────────────────────────────────

def cell_to_polygon(cell: str) -> Polygon:
    """Convert an H3 cell ID to a Shapely Polygon (lng, lat order)."""
    boundary = h3.cell_to_boundary(cell)   # returns (lat, lng) tuples
    return Polygon([(lng, lat) for lat, lng in boundary])


def assign_h3_cells(gdf: gpd.GeoDataFrame, resolution: int) -> list:
    """Return a list of H3 cell IDs, one per row, based on centroid."""
    return [
        h3.latlng_to_cell(pt.y, pt.x, resolution)
        for pt in gdf.geometry.centroid
    ]


# ── Traffic aggregation ───────────────────────────────────────────────────────

def aggregate_traffic_to_h3(city_code: str, resolution: int):
    """
    Load all 8 time-period GeoPackages, assign segments to H3 cells,
    and return a GeoDataFrame with one row per hexagon containing the
    observation-weighted mean jam_factor across all periods.
    """
    city = CITIES[city_code]
    folder = city['traffic_folder']

    frames = []
    for period in PERIODS:
        path = Path(folder) / f"{period}_{city_code}.gpkg"
        if not path.exists():
            continue
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        gdf['h3_cell'] = assign_h3_cells(gdf, resolution)
        frames.append(gdf[['h3_cell', 'jam_factor_mean', 'jam_factor_count']])

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)

    def weighted_agg(df):
        weights = df['jam_factor_count']
        return pd.Series({
            'jam_factor_mean': np.average(df['jam_factor_mean'], weights=weights),
            'jam_factor_std':  df['jam_factor_mean'].std(),
            'n_segments':      len(df),
            'n_observations':  int(weights.sum()),
        })

    agg = combined.groupby('h3_cell').apply(weighted_agg).reset_index()
    agg['geometry'] = agg['h3_cell'].apply(cell_to_polygon)
    return gpd.GeoDataFrame(agg, geometry='geometry', crs='EPSG:4326')


# ── POI aggregation ───────────────────────────────────────────────────────────

def fetch_pois(city_code: str) -> gpd.GeoDataFrame:
    """Download POIs from OSM for a city (same tags as existing analysis)."""
    city = CITIES[city_code]
    try:
        pois = ox.features_from_bbox(bbox=city['bbox'], tags=POI_TAGS)
        pois = pois.copy()
        pois['geometry'] = pois.geometry.centroid
        pois = pois[pois.geometry.type == 'Point']
        if pois.crs is None:
            pois = pois.set_crs("EPSG:4326")
        return pois
    except Exception as e:
        print(f"    Warning — POI fetch failed: {e}")
        return gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs='EPSG:4326'))


def aggregate_pois_to_h3(pois: gpd.GeoDataFrame, resolution: int) -> pd.Series:
    """Count POIs per H3 cell. Returns Series indexed by cell ID."""
    if len(pois) == 0:
        return pd.Series(dtype=float)
    cells = [h3.latlng_to_cell(pt.y, pt.x, resolution) for pt in pois.geometry]
    return pd.Series(cells).value_counts().rename('poi_count')


# ── Centrality aggregation ────────────────────────────────────────────────────

def fetch_centrality(city_code: str):
    """
    Download the OSM drive network and compute edge betweenness centrality.
    Uses k-sample approximation for large networks (same as existing script).
    """
    city = CITIES[city_code]
    try:
        G = ox.graph_from_bbox(bbox=city['bbox'], network_type='drive', simplify=True)
        print(f"    Network: {len(G.nodes):,} nodes, {len(G.edges):,} edges")

        if len(G.nodes) > 5000:
            k = min(500, len(G.nodes))
            print(f"    Using k={k} sample for betweenness centrality...")
            edge_bc = nx.edge_betweenness_centrality(G, normalized=True, k=k)
        else:
            edge_bc = nx.edge_betweenness_centrality(G, normalized=True)

        nx.set_edge_attributes(G, edge_bc, 'betweenness')
        edges = ox.graph_to_gdfs(G, nodes=False)
        print(f"    Max betweenness: {edges['betweenness'].max():.6f}")
        return edges
    except Exception as e:
        print(f"    Warning — centrality failed: {e}")
        return None


def aggregate_centrality_to_h3(edges: gpd.GeoDataFrame, resolution: int) -> pd.Series:
    """Mean betweenness centrality per H3 cell. Returns Series indexed by cell ID."""
    if edges is None or len(edges) == 0:
        return pd.Series(dtype=float)
    gdf = edges.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf['h3_cell'] = assign_h3_cells(gdf, resolution)
    return gdf.groupby('h3_cell')['betweenness'].mean().rename('centrality_mean')


# ── Statistics ────────────────────────────────────────────────────────────────

def correlate(x: np.ndarray, y: np.ndarray) -> dict:
    """Pearson + Spearman on complete pairs."""
    mask = ~(np.isnan(x) | np.isnan(y))
    n = mask.sum()
    if n < 10:
        return dict(n=n, pearson_r=np.nan, pearson_p=np.nan,
                    spearman_r=np.nan, spearman_p=np.nan)
    xv, yv = x[mask], y[mask]
    pr, pp = stats.pearsonr(xv, yv)
    sr, sp = stats.spearmanr(xv, yv)
    return dict(n=int(n), pearson_r=pr, pearson_p=pp, spearman_r=sr, spearman_p=sp)


def compute_morans_i(hex_gdf: gpd.GeoDataFrame, value_col: str) -> dict:
    """Global Moran's I using Queen contiguity on hex polygons."""
    try:
        from libpysal.weights import Queen
        import esda
        w = Queen.from_dataframe(hex_gdf, silence_warnings=True)
        w.transform = 'r'
        moran = esda.Moran(hex_gdf[value_col], w)
        return dict(I=moran.I, p_sim=moran.p_sim, z_sim=moran.z_sim)
    except Exception as e:
        return dict(I=np.nan, p_sim=np.nan, z_sim=np.nan, error=str(e))


# ── Per-city pipeline ─────────────────────────────────────────────────────────

def run_city(city_code: str) -> list:
    city_name = CITIES[city_code]['name']
    print(f"\n{'='*60}")
    print(f"  {city_name}")
    print(f"{'='*60}")

    print("  Fetching POIs from OSM...")
    pois = fetch_pois(city_code)
    print(f"    {len(pois):,} POIs found")

    print("  Computing network centrality...")
    edges = fetch_centrality(city_code)

    city_results = []

    for res in H3_RESOLUTIONS:
        info = H3_RES_INFO[res]
        print(f"\n  ── Resolution {res}  (~{info['diameter_m']} m diameter, "
              f"~{info['area_km2']} km² area) ──")

        # 1. Aggregate traffic
        print("    Aggregating traffic segments to H3...")
        hex_gdf = aggregate_traffic_to_h3(city_code, res)
        if hex_gdf is None:
            print("    No traffic data found — skipping")
            continue
        n_hex = len(hex_gdf)
        print(f"    {n_hex} hexagons with traffic data")

        # 2. POI count per hex
        poi_counts = aggregate_pois_to_h3(pois, res)
        hex_gdf['poi_count'] = hex_gdf['h3_cell'].map(poi_counts).fillna(0)

        # 3. Mean centrality per hex
        cent_means = aggregate_centrality_to_h3(edges, res)
        hex_gdf['centrality_mean'] = hex_gdf['h3_cell'].map(cent_means)

        # 4. Correlations
        jf = hex_gdf['jam_factor_mean'].values
        poi_corr  = correlate(jf, hex_gdf['poi_count'].values)
        cent_corr = correlate(jf, hex_gdf['centrality_mean'].values)

        print(f"    POI density  — r={poi_corr['pearson_r']:+.4f}  "
              f"ρ={poi_corr['spearman_r']:+.4f}  p={poi_corr['spearman_p']:.4f}  "
              f"(n={poi_corr['n']})")
        print(f"    Centrality   — r={cent_corr['pearson_r']:+.4f}  "
              f"ρ={cent_corr['spearman_r']:+.4f}  p={cent_corr['spearman_p']:.4f}  "
              f"(n={cent_corr['n']})")

        # 5. Moran's I on hex-level congestion
        print("    Computing Moran's I on hex congestion...")
        moran = compute_morans_i(hex_gdf, 'jam_factor_mean')
        sig = "**" if moran['p_sim'] < 0.05 else ""
        print(f"    Moran's I = {moran['I']:+.4f}  p = {moran['p_sim']:.4f} {sig}")

        # 6. Save hex GeoPackage
        out_path = OUTPUT_DIR / f"h3_r{res}_{city_code}.gpkg"
        hex_gdf.to_file(out_path, driver='GPKG')
        print(f"    Saved: {out_path}")

        city_results.append({
            'city':           city_name,
            'city_code':      city_code,
            'resolution':     res,
            'diameter_m':     info['diameter_m'],
            'n_hexagons':     n_hex,
            # POI
            'poi_n':          poi_corr['n'],
            'poi_pearson_r':  poi_corr['pearson_r'],
            'poi_pearson_p':  poi_corr['pearson_p'],
            'poi_spearman_r': poi_corr['spearman_r'],
            'poi_spearman_p': poi_corr['spearman_p'],
            # Centrality
            'cent_n':         cent_corr['n'],
            'cent_pearson_r': cent_corr['pearson_r'],
            'cent_pearson_p': cent_corr['pearson_p'],
            'cent_spearman_r':cent_corr['spearman_r'],
            'cent_spearman_p':cent_corr['spearman_p'],
            # Moran
            'morans_I':       moran['I'],
            'morans_p':       moran['p_sim'],
        })

    return city_results


# ── Summary & interpretation ──────────────────────────────────────────────────

def print_summary(df: pd.DataFrame):
    print("\n" + "=" * 80)
    print("H3 ROBUSTNESS CHECK — SUMMARY")
    print("=" * 80)

    for res in H3_RESOLUTIONS:
        info = H3_RES_INFO[res]
        subset = df[df['resolution'] == res]
        print(f"\nResolution {res}  (~{info['diameter_m']} m hex diameter):")
        hdr = (f"  {'City':<12} {'Hexes':>6}  "
               f"{'POI r':>7} {'POI ρ':>7} {'POI p':>7}  "
               f"{'Cent r':>7} {'Cent ρ':>7} {'Cent p':>7}  "
               f"{'Moran I':>8} {'p':>6}")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for _, row in subset.iterrows():
            poi_sig  = "*" if row['poi_spearman_p']  < 0.05 else " "
            cent_sig = "*" if row['cent_spearman_p'] < 0.05 else " "
            mor_sig  = "*" if row['morans_p']         < 0.05 else " "
            print(f"  {row['city']:<12} {int(row['n_hexagons']):>6}  "
                  f"{row['poi_pearson_r']:>+7.4f} {row['poi_spearman_r']:>+7.4f} "
                  f"{row['poi_spearman_p']:>6.4f}{poi_sig}  "
                  f"{row['cent_pearson_r']:>+7.4f} {row['cent_spearman_r']:>+7.4f} "
                  f"{row['cent_spearman_p']:>6.4f}{cent_sig}  "
                  f"{row['morans_I']:>+8.4f} {row['morans_p']:>5.4f}{mor_sig}")

    print("\n  (* p < 0.05)")

    # Segment-level benchmark
    print("\n" + "-" * 80)
    print("Segment-level baseline (existing analysis):")
    print(f"  POI ρ:      Semarang={SEGMENT_BENCHMARKS['poi_spearman_r']['Semarang']:+.4f}  "
          f"Bandung={SEGMENT_BENCHMARKS['poi_spearman_r']['Bandung']:+.4f}  "
          f"Jakarta={SEGMENT_BENCHMARKS['poi_spearman_r']['Jakarta']:+.4f}  (all p > 0.6)")
    print(f"  Cent ρ:     Semarang={SEGMENT_BENCHMARKS['cent_spearman_r']['Semarang']:+.4f}  "
          f"Bandung={SEGMENT_BENCHMARKS['cent_spearman_r']['Bandung']:+.4f}  "
          f"Jakarta={SEGMENT_BENCHMARKS['cent_spearman_r']['Jakarta']:+.4f}  (all p > 0.44)")
    print(f"  Moran's I:  Semarang={SEGMENT_BENCHMARKS['morans_I']['Semarang']:+.4f}  "
          f"Bandung={SEGMENT_BENCHMARKS['morans_I']['Bandung']:+.4f}  "
          f"Jakarta={SEGMENT_BENCHMARKS['morans_I']['Jakarta']:+.4f}  (all p > 0.35)")

    # Interpretation
    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    sig_poi  = df[df['poi_spearman_p']  < 0.05]
    sig_cent = df[df['cent_spearman_p'] < 0.05]
    sig_mor  = df[df['morans_p']         < 0.05]

    # POI
    if len(sig_poi) == 0:
        print("\n  POI density:")
        print("    Null result PERSISTS at both hex resolutions.")
        print("    Scale mismatch was NOT the cause of the null finding.")
        print("    Congestion is genuinely unrelated to activity centre density.")
    else:
        print(f"\n  POI density:")
        print(f"    Significant in {len(sig_poi)}/{len(df)} resolution × city combinations.")
        for _, r in sig_poi.iterrows():
            print(f"    → {r['city']} (res {int(r['resolution'])}): "
                  f"ρ={r['poi_spearman_r']:+.4f}, p={r['poi_spearman_p']:.4f}")
        print("    Scale mismatch WAS a contributing factor.")
        print("    Recommend reporting hex-level result alongside segment-level.")

    # Centrality
    if len(sig_cent) == 0:
        print("\n  Network centrality:")
        print("    Null result PERSISTS at both hex resolutions.")
    else:
        print(f"\n  Network centrality:")
        print(f"    Significant in {len(sig_cent)}/{len(df)} resolution × city combinations.")
        for _, r in sig_cent.iterrows():
            print(f"    → {r['city']} (res {int(r['resolution'])}): "
                  f"ρ={r['cent_spearman_r']:+.4f}, p={r['cent_spearman_p']:.4f}")

    # Moran's I
    if len(sig_mor) == 0:
        print("\n  Moran's I (hex-level):")
        print("    No spatial autocorrelation at hex level.")
        print("    Congestion is spatially random regardless of aggregation scale.")
        print("    Temporal dominance finding is robust.")
    else:
        print(f"\n  Moran's I (hex-level):")
        print(f"    Spatial clustering EMERGES at hex level in {len(sig_mor)}/{len(df)} cases.")
        for _, r in sig_mor.iterrows():
            print(f"    → {r['city']} (res {int(r['resolution'])}): "
                  f"I={r['morans_I']:+.4f}, p={r['morans_p']:.4f}")
        print("    H3 aggregation reduces within-hex noise, revealing spatial structure.")
        print("    Recommend including hex-level Moran's I in robustness section.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H3 HEXAGONAL AGGREGATION — ROBUSTNESS CHECK")
    print("Resolutions: 8 (~461 m) and 9 (~174 m)")
    print("Variables:   POI density, network centrality, Moran's I")
    print("Cities:      Semarang, Bandung, Jakarta")
    print("=" * 70)

    all_results = []
    for city_code in CITIES:
        all_results.extend(run_city(city_code))

    df = pd.DataFrame(all_results)

    print_summary(df)

    out_path = OUTPUT_DIR / 'h3_robustness_results.csv'
    df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
