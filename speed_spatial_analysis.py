#!/usr/bin/env python3
"""
Speed-Based Spatial Analysis (B2 + B3)

Loads existing B1 output (speed-aggregated GeoPackages) and runs:
  B2 — Centrality correlations on speed metrics (not just jam factor)
  B3 — Multilevel mixed-effects model for variance decomposition

Generates LaTeX tables for manuscript integration.

Usage:
    python speed_spatial_analysis.py                  # all 3 cities
    python speed_spatial_analysis.py --city smg       # Semarang only
    python speed_spatial_analysis.py --city smg bdg   # Semarang + Bandung
"""

import argparse
import os
import sys
import time
import warnings

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from scipy.stats import pearsonr, spearmanr
import statsmodels.formula.api as smf

warnings.filterwarnings('ignore')

# ============================================================
# Configuration
# ============================================================
CITIES = {
    'smg': {
        'name': 'Semarang',
        'output_folder': 'traffic_smg_output',
        'bbox': (-7.105, 110.227, -6.919, 110.528),  # south, west, north, east
    },
    'bdg': {
        'name': 'Bandung',
        'output_folder': 'traffic_bdg_output',
        'bbox': (-7.0848, 107.4688, -6.8294, 107.8261),
    },
    'jkt': {
        'name': 'Jakarta',
        'output_folder': 'traffic_jkt_output',
        'bbox': (-6.4096, 106.6036, -6.0911, 107.11),
    },
}

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night',
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = BASE_DIR  # CSVs and LaTeX go to project root


def load_speed_gpkg(filepath):
    """Load a speed GeoPackage, ensuring a segment_id column exists."""
    gdf = gpd.read_file(filepath)
    # Prefer osm_composite_id (OSM-based pipeline), fall back to fid (legacy)
    if 'osm_composite_id' in gdf.columns:
        gdf['segment_id'] = gdf['osm_composite_id']
    elif 'fid' in gdf.columns:
        gdf['segment_id'] = gdf['fid']
    else:
        gdf['segment_id'] = range(1, len(gdf) + 1)
    return gdf


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}min"
    else:
        return f"{seconds / 3600:.1f}h"


# ============================================================
# B2 — Centrality computation and correlation
# ============================================================
def compute_centrality(city_code, cfg):
    """Download OSM network, compute edge betweenness, spatial-join to traffic segments."""
    name = cfg['name']
    south, west, north, east = cfg['bbox']

    print(f"\n  Downloading OSM drive network for {name}...")
    for attempt in range(3):
        try:
            G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type='drive')
            break
        except Exception as e:
            if attempt < 2:
                print(f"  Download failed (attempt {attempt+1}/3), retrying in 10s: {e}")
                time.sleep(10)
            else:
                raise
    print(f"  Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    n_nodes = G.number_of_nodes()
    k = min(500, n_nodes) if n_nodes > 500 else None
    print(f"  Computing edge betweenness centrality (k={k})...")
    t0 = time.time()
    edge_bc = nx.edge_betweenness_centrality(G, k=k, weight='length', normalized=True)
    print(f"  Centrality computed in {format_duration(time.time() - t0)}")

    edges_gdf = ox.graph_to_gdfs(G, nodes=False)
    edges_gdf['betweenness'] = edges_gdf.index.map(lambda idx: edge_bc.get(idx, 0.0))
    edges_gdf = edges_gdf[['geometry', 'betweenness']].reset_index(drop=True)
    print(f"  Betweenness range: {edges_gdf['betweenness'].min():.6f} – "
          f"{edges_gdf['betweenness'].max():.6f}")

    # Load reference geometry from any period file
    out_folder = os.path.join(BASE_DIR, cfg['output_folder'])
    ref_file = os.path.join(out_folder, f'evening_peak_{city_code}.gpkg')
    if not os.path.exists(ref_file):
        # Fallback to any available period
        for p in TIME_PERIODS:
            ref_file = os.path.join(out_folder, f'{p}_{city_code}.gpkg')
            if os.path.exists(ref_file):
                break

    ref_gdf = load_speed_gpkg(ref_file)
    ref_centroids = ref_gdf[['segment_id', 'geometry']].copy()
    ref_centroids['geometry'] = ref_centroids.geometry.centroid

    osm_centroids = edges_gdf.copy()
    osm_centroids['geometry'] = osm_centroids.geometry.centroid

    print(f"  Spatial joining traffic segments to OSM edges...")
    joined = gpd.sjoin_nearest(
        ref_centroids[['segment_id', 'geometry']],
        osm_centroids[['geometry', 'betweenness']],
        how='left',
        max_distance=0.002,  # ~200m in degrees
    )
    centrality_df = joined.groupby('segment_id')['betweenness'].first().reset_index()
    matched = centrality_df['betweenness'].notna().sum()
    print(f"  Matched {matched}/{len(ref_gdf)} segments to OSM edges")

    return centrality_df


def run_centrality_correlations(city_code, cfg, centrality_df):
    """Correlate betweenness centrality with all traffic metrics."""
    name = cfg['name']
    out_folder = os.path.join(BASE_DIR, cfg['output_folder'])

    speed_file = os.path.join(out_folder, f'evening_peak_{city_code}.gpkg')
    if not os.path.exists(speed_file):
        print(f"  {name}: evening_peak speed file not found, skipping correlations")
        return []

    speed_gdf = load_speed_gpkg(speed_file)
    merged = speed_gdf.merge(centrality_df, on='segment_id', how='inner')
    merged = merged.dropna(subset=['betweenness'])

    print(f"\n  {name}: Centrality vs traffic metrics (evening peak, n={len(merged)})")

    metrics = {
        'jam_factor_mean': 'Jam factor',
        'speed_mean': 'Current speed (km/h)',
        'free_flow_mean': 'Free-flow speed (km/h)',
    }

    corr_rows = []
    for col, label in metrics.items():
        if col not in merged.columns:
            continue
        valid = merged[['betweenness', col]].dropna()
        if len(valid) < 10:
            continue

        r_p, p_p = pearsonr(valid['betweenness'], valid[col])
        r_s, p_s = spearmanr(valid['betweenness'], valid[col])
        r2 = r_p ** 2

        print(f"    {label}: r={r_p:.4f}, R²={r2:.6f}, "
              f"rho={r_s:.4f}, p={p_s:.2e}")

        corr_rows.append({
            'city': name, 'metric': col, 'metric_label': label,
            'pearson_r': round(r_p, 6), 'R_squared': round(r2, 6),
            'pearson_p': p_p, 'spearman_rho': round(r_s, 6),
            'spearman_p': p_s, 'n': len(valid),
        })

    # Speed reduction
    if 'speed_mean' in merged.columns and 'free_flow_mean' in merged.columns:
        merged['speed_reduction_mean'] = merged['free_flow_mean'] - merged['speed_mean']
        valid = merged[['betweenness', 'speed_reduction_mean']].dropna()
        if len(valid) >= 10:
            r_p, p_p = pearsonr(valid['betweenness'], valid['speed_reduction_mean'])
            r_s, p_s = spearmanr(valid['betweenness'], valid['speed_reduction_mean'])
            r2 = r_p ** 2
            print(f"    Speed reduction: r={r_p:.4f}, R²={r2:.6f}, "
                  f"rho={r_s:.4f}, p={p_s:.2e}")
            corr_rows.append({
                'city': name, 'metric': 'speed_reduction_mean',
                'metric_label': 'Speed reduction (km/h)',
                'pearson_r': round(r_p, 6), 'R_squared': round(r2, 6),
                'pearson_p': p_p, 'spearman_rho': round(r_s, 6),
                'spearman_p': p_s, 'n': len(valid),
            })

    return corr_rows


# ============================================================
# B3 — Multilevel model
# ============================================================
def run_multilevel_model(city_code, cfg, centrality_df):
    """Fit null, temporal, and full mixed-effects models."""
    name = cfg['name']
    out_folder = os.path.join(BASE_DIR, cfg['output_folder'])

    print(f"\n  {name}: Building multilevel dataset...")

    # Stack all 8 periods into long format
    frames = []
    for period in TIME_PERIODS:
        speed_file = os.path.join(out_folder, f'{period}_{city_code}.gpkg')
        if not os.path.exists(speed_file):
            continue
        gdf = load_speed_gpkg(speed_file)
        cols = ['segment_id']
        for metric in ['jam_factor_mean', 'speed_mean', 'free_flow_mean',
                        'jam_factor_count']:
            if metric in gdf.columns:
                cols.append(metric)
        df = pd.DataFrame(gdf[cols])
        df['time_period'] = period
        frames.append(df)

    if not frames:
        print(f"  No speed files found for {name}, skipping MLM")
        return None

    long_df = pd.concat(frames, ignore_index=True)
    long_df = long_df.merge(centrality_df, on='segment_id', how='left')

    if 'speed_mean' in long_df.columns and 'free_flow_mean' in long_df.columns:
        long_df['speed_reduction'] = long_df['free_flow_mean'] - long_df['speed_mean']

    model_cols = ['speed_mean', 'time_period', 'betweenness', 'free_flow_mean', 'segment_id']
    model_df = long_df.dropna(subset=[c for c in model_cols if c in long_df.columns])
    print(f"  Dataset: {len(model_df)} rows "
          f"({model_df['segment_id'].nunique()} segments x "
          f"{model_df['time_period'].nunique()} periods)")

    # ---- Model 1: Null ----
    print(f"  Fitting null model (random intercept only)...")
    null_model = smf.mixedlm(
        'speed_mean ~ 1', data=model_df, groups=model_df['segment_id']
    ).fit(reml=True)

    var_segment = null_model.cov_re.iloc[0, 0]
    var_residual = null_model.scale
    icc = var_segment / (var_segment + var_residual)

    print(f"  ICC = {icc:.4f} ({icc*100:.1f}%)")
    print(f"    Between-segment variance: {var_segment:.2f}")
    print(f"    Within-segment variance:  {var_residual:.2f}")

    # ---- Model 2: Temporal ----
    print(f"  Fitting temporal model...")
    temporal_model = smf.mixedlm(
        'speed_mean ~ C(time_period)', data=model_df, groups=model_df['segment_id']
    ).fit(reml=True)

    var_seg_t = temporal_model.cov_re.iloc[0, 0]
    var_res_t = temporal_model.scale
    r2_temporal = 1 - (var_res_t / var_residual)

    print(f"  Temporal pseudo-R²: {r2_temporal:.4f} ({r2_temporal*100:.1f}%)")

    # ---- Model 3: Full ----
    print(f"  Fitting full model (time + betweenness + free_flow)...")
    full_model = smf.mixedlm(
        'speed_mean ~ C(time_period) + betweenness + free_flow_mean',
        data=model_df, groups=model_df['segment_id']
    ).fit(reml=True)

    var_seg_f = full_model.cov_re.iloc[0, 0]
    var_res_f = full_model.scale
    r2_spatial_incr = 1 - (var_seg_f / var_seg_t) if var_seg_t > 0 else 0

    print(f"  Spatial incremental R²: {r2_spatial_incr:.4f} ({r2_spatial_incr*100:.2f}%)")

    # Fixed effect coefficients
    fe = full_model.fe_params
    pvals = full_model.pvalues
    print(f"  Fixed effects:")
    for param in ['betweenness', 'free_flow_mean']:
        if param in fe.index:
            coef = fe[param]
            p = pvals[param]
            sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'ns'
            print(f"    {param}: coef={coef:.4f}, p={p:.2e} {sig}")

    result = {
        'city': name,
        'n_obs': len(model_df),
        'n_segments': model_df['segment_id'].nunique(),
        'ICC_null': round(icc, 4),
        'ICC_pct': f'{icc*100:.1f}%',
        'var_between': round(var_segment, 2),
        'var_within': round(var_residual, 2),
        'R2_temporal': round(r2_temporal, 4),
        'R2_temporal_pct': f'{r2_temporal*100:.1f}%',
        'R2_spatial_incremental': round(r2_spatial_incr, 4),
        'R2_spatial_pct': f'{r2_spatial_incr*100:.2f}%',
        'var_segment_after_time': round(var_seg_t, 2),
        'var_segment_after_full': round(var_seg_f, 2),
        'beta_betweenness': round(fe.get('betweenness', np.nan), 4),
        'p_betweenness': pvals.get('betweenness', np.nan),
        'beta_free_flow': round(fe.get('free_flow_mean', np.nan), 4),
        'p_free_flow': pvals.get('free_flow_mean', np.nan),
    }

    # Save model summaries
    summary_file = os.path.join(out_folder, f'mlm_summary_{city_code}.txt')
    with open(summary_file, 'w') as f:
        f.write(f"Multilevel Model Results for {name}\n{'='*60}\n\n")
        f.write(f"Null Model (ICC):\n{null_model.summary()}\n\n")
        f.write(f"Temporal Model:\n{temporal_model.summary()}\n\n")
        f.write(f"Full Model:\n{full_model.summary()}\n")
    print(f"  Saved: {summary_file}")

    return result


# ============================================================
# LaTeX table generation
# ============================================================
def generate_latex_tables(all_anova, corr_df, mlm_df):
    """Generate LaTeX tables for manuscript."""
    city_names = {'smg': 'Semarang', 'bdg': 'Bandung', 'jkt': 'Jakarta'}
    lines = []

    # ---- Table 1: ANOVA comparison across metrics ----
    lines.append(r'% Table: Temporal ANOVA across metric types')
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'\centering')
    lines.append(r'\caption{Temporal variance explained ($\eta^2$) by metric type. '
                 r'Absolute speed metrics confirm temporal dominance is not an artifact '
                 r'of jam factor normalization.}')
    lines.append(r'\label{tab:speed_validation}')
    lines.append(r'\begin{tabular}{lcccc}')
    lines.append(r'\toprule')
    lines.append(r'City & Jam factor & Current speed & Speed reduction & Free-flow speed \\')
    lines.append(r'\midrule')

    for city_code in ['smg', 'bdg', 'jkt']:
        if city_code not in all_anova:
            continue
        name = city_names[city_code]
        vals = []
        for m in ['jam_factor', 'speed', 'speed_reduction', 'free_flow']:
            eta = all_anova[city_code].get(m)
            if eta is not None and not np.isnan(eta):
                vals.append(f'{eta*100:.1f}\\%')
            else:
                vals.append('N/A')
        lines.append(f'{name} & {" & ".join(vals)} \\\\')

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\end{table}')
    lines.append('')

    # ---- Table 2: Centrality correlations across metrics ----
    lines.append(r'% Table: Centrality-congestion correlations across metric types')
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'\centering')
    lines.append(r'\caption{Pearson $R^2$ between edge betweenness centrality and traffic metrics '
                 r'(evening peak). Null correlations persist across all metric types, '
                 r'confirming that the finding is not an artifact of jam factor normalization.}')
    lines.append(r'\label{tab:centrality_speed}')
    lines.append(r'\begin{tabular}{lcccc}')
    lines.append(r'\toprule')
    lines.append(r'City & Jam factor & Current speed & Speed reduction & Free-flow speed \\')
    lines.append(r'\midrule')

    for city in ['Semarang', 'Bandung', 'Jakarta']:
        city_corr = corr_df[corr_df['city'] == city]
        vals = []
        for label in ['Jam factor', 'Current speed (km/h)',
                       'Speed reduction (km/h)', 'Free-flow speed (km/h)']:
            match = city_corr[city_corr['metric_label'] == label]
            if len(match) > 0:
                vals.append(f'{match.iloc[0]["R_squared"]:.4f}')
            else:
                vals.append('N/A')
        lines.append(f'{city} & {" & ".join(vals)} \\\\')

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\end{table}')
    lines.append('')

    # ---- Table 3: Multilevel model results ----
    lines.append(r'% Table: Multilevel model variance decomposition')
    lines.append(r'\begin{table}[htbp]')
    lines.append(r'\centering')
    lines.append(r'\caption{Multilevel model variance decomposition. ICC represents the '
                 r'proportion of speed variance attributable to between-segment (spatial) '
                 r'differences. Temporal pseudo-$R^2$ is the within-segment variance '
                 r'reduction from time period; spatial incremental $\Delta R^2$ is the '
                 r'between-segment variance reduction from adding centrality and '
                 r'free-flow speed.}')
    lines.append(r'\label{tab:multilevel}')
    lines.append(r'\begin{tabular}{lccccc}')
    lines.append(r'\toprule')
    lines.append(r'City & Segments & ICC & Temporal $R^2$ & '
                 r'Spatial $\Delta R^2$ & $\beta_{\text{centrality}}$ \\')
    lines.append(r'\midrule')

    for _, row in mlm_df.iterrows():
        beta = row['beta_betweenness']
        p = row['p_betweenness']
        sig = ('$^{***}$' if p < 0.001 else '$^{**}$' if p < 0.01
               else '$^{*}$' if p < 0.05 else '')
        lines.append(
            f"{row['city']} & {row['n_segments']:,} & {row['ICC_pct']} & "
            f"{row['R2_temporal_pct']} & {row['R2_spatial_pct']} & "
            f"{beta:.4f}{sig} \\\\"
        )

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='Speed-based spatial analysis (B2 centrality + B3 multilevel model)'
    )
    parser.add_argument(
        '--city', nargs='+', choices=list(CITIES.keys()),
        help='Cities to process (default: all)'
    )
    args = parser.parse_args()

    cities_to_run = args.city if args.city else list(CITIES.keys())

    print("=" * 60)
    print("SPEED-BASED SPATIAL ANALYSIS (B2 + B3)")
    print(f"Cities: {', '.join(c.upper() for c in cities_to_run)}")
    print("=" * 60)

    t_start = time.time()

    # Load existing ANOVA results (from B1)
    all_anova = {}
    for city_code in cities_to_run:
        anova_file = os.path.join(
            BASE_DIR, CITIES[city_code]['output_folder'],
            f'anova_results_{city_code}.csv'
        )
        if os.path.exists(anova_file):
            df = pd.read_csv(anova_file)
            all_anova[city_code] = {
                row['metric']: row['eta_squared']
                for _, row in df.iterrows()
            }
            print(f"  Loaded ANOVA: {anova_file}")

    # B2 — Centrality
    print(f"\n{'='*60}")
    print("B2: CENTRALITY CORRELATIONS")
    print(f"{'='*60}")

    all_centrality = {}
    all_corr_rows = []

    for city_code in cities_to_run:
        cfg = CITIES[city_code]
        print(f"\n{'='*60}")
        print(f"{cfg['name']} ({city_code.upper()})")
        print(f"{'='*60}")

        centrality_df = compute_centrality(city_code, cfg)
        all_centrality[city_code] = centrality_df

        corr_rows = run_centrality_correlations(city_code, cfg, centrality_df)
        all_corr_rows.extend(corr_rows)

    corr_df = pd.DataFrame(all_corr_rows)
    corr_csv = os.path.join(OUTPUT_DIR, 'centrality_correlations_all_metrics.csv')
    corr_df.to_csv(corr_csv, index=False)
    print(f"\nSaved: {corr_csv}")

    # Print summary
    if len(corr_df) > 0:
        print(f"\n{'='*70}")
        print("SUMMARY: Centrality R² across metrics")
        print('='*70)
        pivot = corr_df.pivot(index='city', columns='metric_label', values='R_squared')
        print(pivot.to_string())

    # B3 — Multilevel model
    print(f"\n{'='*60}")
    print("B3: MULTILEVEL MODEL")
    print(f"{'='*60}")

    mlm_rows = []
    for city_code in cities_to_run:
        cfg = CITIES[city_code]
        centrality_df = all_centrality[city_code]
        result = run_multilevel_model(city_code, cfg, centrality_df)
        if result:
            mlm_rows.append(result)

    mlm_df = pd.DataFrame(mlm_rows)
    mlm_csv = os.path.join(OUTPUT_DIR, 'multilevel_model_results.csv')
    mlm_df.to_csv(mlm_csv, index=False)
    print(f"\nSaved: {mlm_csv}")

    # Print MLM summary
    if len(mlm_df) > 0:
        print(f"\n{'='*70}")
        print("MULTILEVEL MODEL SUMMARY")
        print('='*70)
        display_cols = ['city', 'n_segments', 'ICC_pct', 'R2_temporal_pct',
                        'R2_spatial_pct', 'beta_betweenness', 'p_betweenness']
        print(mlm_df[display_cols].to_string(index=False))

    # Generate LaTeX tables
    latex = generate_latex_tables(all_anova, corr_df, mlm_df)
    latex_file = os.path.join(OUTPUT_DIR, 'tables_for_manuscript.tex')
    with open(latex_file, 'w') as f:
        f.write(latex)
    print(f"\nSaved: {latex_file}")

    total = time.time() - t_start
    print(f"\nTotal time: {format_duration(total)}")
    print("Done!")


if __name__ == '__main__':
    main()
