#!/usr/bin/env python3
"""
Revision 2 analyses for TRIP major-revision response.

Addresses:
  R2.2  FFS-only and centrality-only mixed-model sub-specs (split ΔR²)
  R1.2  Closeness centrality results alongside betweenness
  R2.4  Mixed-model diagnostics: random-effects normality, residual Moran's I
  R1.4  Residual variance characterization (limited to what existing
        8-period panel supports; hour-of-day deferred since the panel is
        already aggregated to periods)

Reuses data-loading / OSM patterns from speed_spatial_analysis.py and
revision_analyses.py. Caches per-segment betweenness + closeness to CSV
so re-running is fast.

Outputs (all under analysis_results/):
  multilevel_subspecs.csv         per-city, all 5 model specs
  centrality_cache_<city>.csv     per-segment betweenness + closeness
  centrality_closeness_corr.csv   per-city closeness correlations
  re_residual_diagnostics.csv     residual Moran's I + RE summary
  figures/re_qq_<city>.png        random-effects Q-Q plots
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import statsmodels.formula.api as smf
from esda.moran import Moran
from libpysal.weights import KNN
from scipy import stats

warnings.filterwarnings("ignore")
ox.settings.use_cache = True
ox.settings.log_console = False

BASE = Path(__file__).resolve().parent
OUT = BASE / "analysis_results"
FIG = BASE / "figures"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

CITIES = {
    "smg": {
        "name": "Semarang",
        "folder": "traffic_smg_output",
        "bbox": (-7.105, 110.227, -6.919, 110.528),
    },
    "bdg": {
        "name": "Bandung",
        "folder": "traffic_bdg_output",
        "bbox": (-7.0848, 107.4688, -6.8294, 107.8261),
    },
    "jkt": {
        "name": "Jakarta",
        "folder": "traffic_jkt_output",
        "bbox": (-6.4096, 106.6036, -6.0911, 107.11),
    },
}

TIME_PERIODS = [
    "night", "morning_peak", "morning_offpeak", "lunch_hours",
    "afternoon_offpeak", "evening_peak", "evening_offpeak", "late_night",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_speed_gpkg(filepath: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(str(filepath))
    if "osm_composite_id" in gdf.columns:
        gdf["segment_id"] = gdf["osm_composite_id"]
    elif "fid" in gdf.columns:
        gdf["segment_id"] = gdf["fid"]
    else:
        gdf["segment_id"] = range(1, len(gdf) + 1)
    return gdf


def load_panel(city_code: str) -> pd.DataFrame:
    """Build long panel (segment x period) with speed + FFS."""
    folder = BASE / CITIES[city_code]["folder"]
    frames = []
    for period in TIME_PERIODS:
        fp = folder / f"{period}_{city_code}.gpkg"
        if not fp.exists():
            continue
        gdf = load_speed_gpkg(fp)
        df = pd.DataFrame({
            "segment_id": gdf["segment_id"].values,
            "time_period": period,
            "speed_mean": gdf.get("speed_mean", pd.Series([np.nan]*len(gdf))).values,
            "free_flow_mean": gdf.get("free_flow_mean", pd.Series([np.nan]*len(gdf))).values,
            "jam_factor_mean": gdf.get("jam_factor_mean", pd.Series([np.nan]*len(gdf))).values,
        })
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No GPKGs found for {city_code}")
    return pd.concat(frames, ignore_index=True)


def load_segment_geoms(city_code: str) -> gpd.GeoDataFrame:
    """Load evening-peak GPKG to get segment geometries (for centrality join)."""
    folder = BASE / CITIES[city_code]["folder"]
    fp = folder / f"evening_peak_{city_code}.gpkg"
    return load_speed_gpkg(fp)


# ---------------------------------------------------------------------------
# Centrality (betweenness + closeness)
# ---------------------------------------------------------------------------

def compute_centrality_cache(city_code: str, segments_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Compute betweenness + closeness per traffic segment.

    Edge betweenness via sampled approximation (k=500). Edge closeness is
    computed at the node level then averaged over edge endpoints.

    Caches to analysis_results/centrality_cache_<city>.csv.
    """
    cache_fp = OUT / f"centrality_cache_{city_code}.csv"
    if cache_fp.exists():
        print(f"  [cache] loading {cache_fp.name}")
        return pd.read_csv(cache_fp)

    cfg = CITIES[city_code]
    south, west, north, east = cfg["bbox"]
    print(f"  Downloading OSM drive network for {cfg['name']} (bbox={cfg['bbox']})...")
    G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive")
    print(f"    Nodes: {G.number_of_nodes():,}, Edges: {G.number_of_edges():,}")

    # Edge betweenness (sampled)
    k_sample = min(500, G.number_of_nodes())
    print(f"    Edge betweenness (k={k_sample} sampled sources)...")
    edge_bc = nx.edge_betweenness_centrality(G, k=k_sample, weight="length", normalized=True)
    nx.set_edge_attributes(G, edge_bc, "betweenness")

    # Node closeness — sampled for large graphs (exact O(V*E*logV) is infeasible for V>30k)
    print(f"    Node closeness centrality (sampled)...")
    G_u = ox.convert.to_undirected(G) if hasattr(ox, "convert") else G.to_undirected()
    n_nodes = G_u.number_of_nodes()
    if n_nodes <= 5000:
        node_cc = nx.closeness_centrality(G_u, distance="length")
    else:
        # Sample 500 source nodes; for each, run single-source Dijkstra.
        # Approximate closeness for each node uses distances to the sampled set.
        rng = np.random.default_rng(0)
        sample_nodes = rng.choice(list(G_u.nodes()), size=min(500, n_nodes), replace=False).tolist()
        # dist_to_sample[node] = list of distances from node to each sampled source
        dist_to_sample = {n: [] for n in G_u.nodes()}
        for i, src in enumerate(sample_nodes):
            if (i + 1) % 50 == 0:
                print(f"      closeness source {i+1}/{len(sample_nodes)}")
            lengths = nx.single_source_dijkstra_path_length(G_u, src, weight="length")
            for n, d in lengths.items():
                if d > 0:
                    dist_to_sample[n].append(d)
        node_cc = {}
        for n, dists in dist_to_sample.items():
            if dists:
                # Approx closeness = sample size / sum of distances, normalized to (sample-1)/total
                node_cc[n] = (len(dists) - 1) / sum(dists) if sum(dists) > 0 else 0.0
            else:
                node_cc[n] = 0.0

    # Build edge GDF
    edges = ox.graph_to_gdfs(G, nodes=False)
    edges = edges.reset_index()  # makes u, v, key columns
    edges["betweenness"] = edges.apply(
        lambda r: edge_bc.get((r["u"], r["v"], r.get("key", 0)), 0.0), axis=1,
    )
    # Edge closeness = mean of endpoint closeness
    edges["closeness"] = edges.apply(
        lambda r: 0.5 * (node_cc.get(r["u"], 0.0) + node_cc.get(r["v"], 0.0)), axis=1,
    )

    # Spatial join: nearest OSM edge centroid for each traffic segment centroid
    osm_c = edges[["geometry", "betweenness", "closeness"]].copy()
    if segments_gdf.crs != osm_c.crs:
        osm_c = osm_c.to_crs(segments_gdf.crs)
    osm_c["geometry"] = osm_c.geometry.centroid

    traffic_c = segments_gdf[["segment_id", "geometry"]].copy()
    traffic_c["geometry"] = traffic_c.geometry.centroid

    joined = gpd.sjoin_nearest(
        traffic_c, osm_c, how="left", distance_col="match_dist",
    )
    joined = joined[~joined["segment_id"].duplicated(keep="first")]

    # Filter very far matches (>200m in degrees, approx 0.002)
    far = joined["match_dist"] > 0.002
    joined.loc[far, ["betweenness", "closeness"]] = np.nan

    result = joined[["segment_id", "betweenness", "closeness", "match_dist"]].copy()
    result.to_csv(cache_fp, index=False)
    print(f"    Saved cache: {cache_fp.name} ({len(result)} segments)")
    return result


# ---------------------------------------------------------------------------
# Mixed-model sub-specifications (R2.2)
# ---------------------------------------------------------------------------

def fit_subspecs(panel: pd.DataFrame, cent_df: pd.DataFrame, city_name: str) -> dict:
    """Fit 5 nested mixed models and return ΔR² for each spatial predictor.

    Models (all REML, random intercept on segment_id):
      M0 null    : speed ~ 1
      M1 temporal: speed ~ C(time_period)
      M2 +FFS    : speed ~ C(time_period) + free_flow_mean
      M3 +cent   : speed ~ C(time_period) + betweenness
      M4 full    : speed ~ C(time_period) + betweenness + free_flow_mean
    """
    df = panel.merge(cent_df[["segment_id", "betweenness", "closeness"]], on="segment_id", how="left")
    needed = ["speed_mean", "time_period", "betweenness", "free_flow_mean", "segment_id"]
    df = df.dropna(subset=needed).copy()

    print(f"  [{city_name}] {len(df):,} obs, {df['segment_id'].nunique():,} segments")

    # M0 Null
    m0 = smf.mixedlm("speed_mean ~ 1", df, groups=df["segment_id"]).fit(reml=True)
    var_b0 = float(m0.cov_re.iloc[0, 0])
    var_w0 = float(m0.scale)
    icc = var_b0 / (var_b0 + var_w0)

    # M1 Temporal
    m1 = smf.mixedlm("speed_mean ~ C(time_period)", df, groups=df["segment_id"]).fit(reml=True)
    var_b1 = float(m1.cov_re.iloc[0, 0])
    var_w1 = float(m1.scale)
    r2_temp = 1.0 - var_w1 / var_w0

    # M2 +FFS only
    m2 = smf.mixedlm("speed_mean ~ C(time_period) + free_flow_mean", df,
                     groups=df["segment_id"]).fit(reml=True)
    var_b2 = float(m2.cov_re.iloc[0, 0])
    dR2_ffs = 1.0 - var_b2 / var_b1

    # M3 +centrality only
    m3 = smf.mixedlm("speed_mean ~ C(time_period) + betweenness", df,
                     groups=df["segment_id"]).fit(reml=True)
    var_b3 = float(m3.cov_re.iloc[0, 0])
    dR2_cent = 1.0 - var_b3 / var_b1

    # M4 Full
    m4 = smf.mixedlm("speed_mean ~ C(time_period) + betweenness + free_flow_mean", df,
                     groups=df["segment_id"]).fit(reml=True)
    var_b4 = float(m4.cov_re.iloc[0, 0])
    dR2_full = 1.0 - var_b4 / var_b1

    fe = m4.fe_params
    pv = m4.pvalues

    res = {
        "city": city_name,
        "n_obs": len(df),
        "n_segments": int(df["segment_id"].nunique()),
        "icc": round(icc, 4),
        "var_between_null": round(var_b0, 3),
        "var_within_null": round(var_w0, 3),
        "var_between_temporal": round(var_b1, 3),
        "var_within_temporal": round(var_w1, 3),
        "r2_temporal": round(r2_temp, 4),
        "var_between_ffs_only": round(var_b2, 3),
        "dR2_ffs_only": round(dR2_ffs, 4),
        "var_between_cent_only": round(var_b3, 3),
        "dR2_cent_only": round(dR2_cent, 4),
        "var_between_full": round(var_b4, 3),
        "dR2_full": round(dR2_full, 4),
        "beta_betweenness_full": round(float(fe.get("betweenness", np.nan)), 4),
        "p_betweenness_full": float(pv.get("betweenness", np.nan)),
        "beta_free_flow_full": round(float(fe.get("free_flow_mean", np.nan)), 4),
        "p_free_flow_full": float(pv.get("free_flow_mean", np.nan)),
    }
    return res, m1  # return m1 (temporal) for diagnostics


# ---------------------------------------------------------------------------
# Diagnostics (R2.4)
# ---------------------------------------------------------------------------

def re_diagnostics(panel: pd.DataFrame, cent_df: pd.DataFrame, m1, city_code: str,
                   city_name: str, segments_gdf: gpd.GeoDataFrame) -> dict:
    """Random-effects normality (Q-Q + Shapiro), residual Moran's I.

    m1 is the temporal model (random intercept absorbs between-segment).
    """
    # BLUPs (random effects) by segment
    re_dict = m1.random_effects  # dict: segment_id -> Series with 'Group' col
    blups = pd.Series({sid: float(arr.iloc[0]) for sid, arr in re_dict.items()})

    # Q-Q plot
    fig, ax = plt.subplots(figsize=(6, 6))
    (osm_q, sm_q), (slope, intercept, r) = stats.probplot(blups.values, dist="norm")
    ax.scatter(osm_q, sm_q, s=8, alpha=0.5, color="#3498db")
    qmin, qmax = osm_q.min(), osm_q.max()
    ax.plot([qmin, qmax], [slope * qmin + intercept, slope * qmax + intercept],
            color="#e74c3c", lw=1.5)
    ax.set_xlabel("Theoretical quantiles")
    ax.set_ylabel("Sample quantiles (BLUPs)")
    ax.set_title(f"{city_name}: Q-Q plot of segment random intercepts\n"
                 f"r = {r:.3f}, n = {len(blups):,}")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    qq_fp = FIG / f"re_qq_{city_code}.png"
    plt.savefig(qq_fp, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    Saved Q-Q: {qq_fp.name}")

    # Shapiro-Wilk on a sample (max 5000 to avoid power saturation)
    sample = blups.sample(min(5000, len(blups)), random_state=0).values
    sw_W, sw_p = stats.shapiro(sample)

    # Residual Moran's I: aggregate residuals to segment level, KNN k=8 on centroids
    # Use the evening-peak segments_gdf for spatial weights.
    df = panel.merge(cent_df[["segment_id", "betweenness"]], on="segment_id", how="left")
    needed = ["speed_mean", "time_period", "betweenness", "free_flow_mean", "segment_id"]
    df = df.dropna(subset=needed)
    df["pred"] = m1.predict(df)
    df["resid"] = df["speed_mean"] - df["pred"]
    seg_resid = df.groupby("segment_id")["resid"].mean()

    geom = segments_gdf[["segment_id", "geometry"]].copy()
    geom["geometry"] = geom.geometry.centroid
    geom = geom.merge(seg_resid.rename("resid"), on="segment_id", how="inner")
    geom = geom.dropna(subset=["resid"]).reset_index(drop=True)

    if len(geom) < 50:
        moran_I, moran_p = np.nan, np.nan
    else:
        w = KNN.from_dataframe(geom, k=8)
        w.transform = "r"
        mi = Moran(geom["resid"].values, w)
        moran_I = float(mi.I)
        moran_p = float(mi.p_norm)

    return {
        "city": city_name,
        "n_segments_blups": int(len(blups)),
        "blups_mean": round(float(blups.mean()), 4),
        "blups_sd": round(float(blups.std()), 4),
        "qq_r": round(float(r), 4),
        "shapiro_W": round(float(sw_W), 4),
        "shapiro_p": float(sw_p),
        "residual_moransI": round(moran_I, 4) if moran_I == moran_I else np.nan,
        "residual_morans_p": moran_p,
        "qq_plot": str(qq_fp.name),
    }


# ---------------------------------------------------------------------------
# Closeness correlations (R1.2 / A4)
# ---------------------------------------------------------------------------

def closeness_corr(panel: pd.DataFrame, cent_df: pd.DataFrame, city_name: str) -> list[dict]:
    """Pearson & Spearman between closeness and each traffic metric (evening peak)."""
    ev = panel[panel["time_period"] == "evening_peak"].merge(
        cent_df[["segment_id", "closeness"]], on="segment_id", how="left",
    ).dropna(subset=["closeness"])

    rows = []
    metric_map = {
        "jam_factor_mean": "Jam factor",
        "speed_mean": "Current speed (km/h)",
        "free_flow_mean": "Free-flow speed (km/h)",
    }
    if "speed_mean" in ev.columns and "free_flow_mean" in ev.columns:
        ev = ev.copy()
        ev["speed_reduction"] = ev["free_flow_mean"] - ev["speed_mean"]
        metric_map["speed_reduction"] = "Speed reduction (km/h)"

    for col, label in metric_map.items():
        v = ev[["closeness", col]].dropna()
        if len(v) < 50:
            continue
        rp, pp = stats.pearsonr(v["closeness"], v[col])
        rs, ps = stats.spearmanr(v["closeness"], v[col])
        rows.append({
            "city": city_name, "metric": col, "metric_label": label,
            "n": len(v),
            "pearson_r": round(rp, 4), "pearson_p": float(pp),
            "spearman_rho": round(rs, 4), "spearman_p": float(ps),
            "R_squared": round(rp ** 2, 6),
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(cities_to_run: list[str] | None = None):
    cities = cities_to_run or list(CITIES.keys())
    print("=" * 70)
    print("REVISION 2 ANALYSES (TRIP major revision)")
    print(f"Cities: {[CITIES[c]['name'] for c in cities]}")
    print("=" * 70)

    multilevel_rows: list[dict] = []
    diag_rows: list[dict] = []
    closeness_rows: list[dict] = []

    for code in cities:
        cfg = CITIES[code]
        print(f"\n[{cfg['name']}]")
        panel = load_panel(code)
        segments_gdf = load_segment_geoms(code)
        cent_df = compute_centrality_cache(code, segments_gdf)

        print(f"  Fitting 5 mixed-model specifications...")
        res, m1 = fit_subspecs(panel, cent_df, cfg["name"])
        multilevel_rows.append(res)
        print(f"    ICC={res['icc']:.1%}  TempR2={res['r2_temporal']:.1%}  "
              f"dR2_FFS={res['dR2_ffs_only']:.1%}  "
              f"dR2_cent={res['dR2_cent_only']:.1%}  "
              f"dR2_full={res['dR2_full']:.1%}")

        print(f"  Random-effects diagnostics...")
        diag = re_diagnostics(panel, cent_df, m1, code, cfg["name"], segments_gdf)
        diag_rows.append(diag)
        print(f"    QQ r={diag['qq_r']}  Shapiro p={diag['shapiro_p']:.3g}  "
              f"Resid Moran's I={diag['residual_moransI']}  (p={diag['residual_morans_p']})")

        print(f"  Closeness centrality correlations...")
        closeness_rows.extend(closeness_corr(panel, cent_df, cfg["name"]))

    # Save outputs
    pd.DataFrame(multilevel_rows).to_csv(OUT / "multilevel_subspecs.csv", index=False)
    pd.DataFrame(diag_rows).to_csv(OUT / "re_residual_diagnostics.csv", index=False)
    pd.DataFrame(closeness_rows).to_csv(OUT / "centrality_closeness_corr.csv", index=False)

    print("\n" + "=" * 70)
    print("DONE. Outputs:")
    for f in ["multilevel_subspecs.csv", "re_residual_diagnostics.csv",
              "centrality_closeness_corr.csv"]:
        print(f"  {OUT/f}")
    print("=" * 70)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        bad = [a for a in args if a not in CITIES]
        if bad:
            print(f"Unknown city codes: {bad}. Valid: {list(CITIES)}", file=sys.stderr)
            sys.exit(2)
        main(args)
    else:
        main()
