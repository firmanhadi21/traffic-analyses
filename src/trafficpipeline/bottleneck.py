"""
Road-capacity bottleneck analysis via OSMnx.

Tests whether congestion occurs at capacity-constrained segments
using graph-based capacity-drop detection, local capacity gradients,
and aggregate low-vs-high capacity comparisons.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree

from trafficpipeline.config import (
    CITIES,
    DEFAULT_LANES,
    HERE_MONITORED_TYPES,
    ROAD_HIERARCHY,
)

import warnings
warnings.filterwarnings("ignore")

ox.settings.use_cache = True
ox.settings.log_console = False


# ---------------------------------------------------------------------------
# Road network helpers
# ---------------------------------------------------------------------------


def _get_lanes(x) -> float:
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
            return float(x.split(";")[0])
        except Exception:
            return np.nan
    return np.nan


def _road_score(highway) -> float:
    if isinstance(highway, list):
        highway = highway[0]
    return ROAD_HIERARCHY.get(highway, 1)


def _highway_str(highway) -> str:
    return highway[0] if isinstance(highway, list) else highway


def get_road_capacity(city_code: str):
    """Download road network and compute capacity attributes.

    Returns ``(edges_filtered, G_filtered)`` where edges are limited
    to HERE-comparable road types.
    """
    city = CITIES[city_code]
    G = ox.graph_from_bbox(bbox=city["bbox"], network_type="drive")
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

    edges["lane_count"] = edges["lanes"].apply(_get_lanes) if "lanes" in edges.columns else np.nan
    edges["road_score"] = edges["highway"].apply(_road_score)

    def _est(row):
        if not pd.isna(row["lane_count"]):
            return row["lane_count"]
        hw = row["highway"]
        if isinstance(hw, list):
            hw = hw[0]
        return DEFAULT_LANES.get(hw, 1)

    edges["estimated_lanes"] = edges.apply(_est, axis=1)
    edges["capacity_score"] = edges["estimated_lanes"] * edges["road_score"]

    edges["highway_str"] = edges["highway"].apply(_highway_str)
    filtered = edges[edges["highway_str"].isin(HERE_MONITORED_TYPES)].copy()

    fids = set(filtered.index)
    G_filt = G.edge_subgraph(
        [(u, v, k) for u, v, k in G.edges(keys=True) if (u, v, k) in fids]
    ).copy()

    return filtered, G_filt


# ---------------------------------------------------------------------------
# Capacity-drop detection
# ---------------------------------------------------------------------------


def detect_capacity_drops(G, edges, threshold: float = 0.2):
    """Find graph nodes where incoming capacity exceeds outgoing by >=*threshold*.

    Returns ``(drop_nodes, drop_magnitudes, drop_coords)``.
    """
    edge_cap = {idx: row["capacity_score"] for idx, row in edges.iterrows()}
    nodes_gdf = ox.graph_to_gdfs(G, nodes=True, edges=False)

    drop_nodes, drop_mags = [], []
    for node in G.nodes():
        in_caps = [edge_cap.get(e, np.nan) for e in G.in_edges(node, keys=True)]
        out_caps = [edge_cap.get(e, np.nan) for e in G.out_edges(node, keys=True)]
        in_caps = [c for c in in_caps if not np.isnan(c)]
        out_caps = [c for c in out_caps if not np.isnan(c)]
        if not in_caps or not out_caps:
            continue
        mx_in, mx_out = max(in_caps), max(out_caps)
        if mx_in > mx_out:
            mag = (mx_in - mx_out) / mx_in
            if mag >= threshold:
                drop_nodes.append(node)
                drop_mags.append(mag)

    if drop_nodes:
        coords = np.array([[p.x, p.y] for p in nodes_gdf.loc[drop_nodes].geometry])
    else:
        coords = np.empty((0, 2))
    return drop_nodes, drop_mags, coords


# ---------------------------------------------------------------------------
# Capacity-drop congestion test
# ---------------------------------------------------------------------------


def analyze_capacity_drop_congestion(matched, drop_coords, drop_magnitudes):
    """Test proximity to capacity drops and local capacity gradient."""
    results: dict = {}
    matched = matched.copy()

    traffic_coords = np.array([[p.x, p.y] for p in matched.geometry.centroid])

    # Part A: distance to nearest drop
    if len(drop_coords) > 0:
        dtree = cKDTree(drop_coords)
        dists, idxs = dtree.query(traffic_coords, k=1)
        matched["dist_to_cap_drop"] = dists
        matched["nearest_drop_magnitude"] = np.array(drop_magnitudes)[idxs]

        valid = matched[["dist_to_cap_drop", "jam_factor_mean"]].dropna()
        r, p = stats.pearsonr(valid.iloc[:, 0], valid.iloc[:, 1])
        rho, rho_p = stats.spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
        results.update(drop_dist_pearson_r=r, drop_dist_pearson_p=p,
                       drop_dist_spearman_r=rho, drop_dist_spearman_p=rho_p)

        matched["drop_proximity"] = pd.qcut(
            matched["dist_to_cap_drop"], q=3,
            labels=["Near", "Medium", "Far"], duplicates="drop",
        )
        near = matched[matched["drop_proximity"] == "Near"]["jam_factor_mean"].dropna()
        far = matched[matched["drop_proximity"] == "Far"]["jam_factor_mean"].dropna()
        if len(near) > 1 and len(far) > 1:
            t, tp = stats.ttest_ind(near, far)
            d = (near.mean() - far.mean()) / np.sqrt((near.std() ** 2 + far.std() ** 2) / 2)
        else:
            t = tp = d = np.nan
        results.update(near_drop_jf=near.mean(), far_drop_jf=far.mean(),
                       drop_prox_t_stat=t, drop_prox_p_value=tp,
                       drop_prox_effect_size=d, n_capacity_drops=len(drop_coords))
    else:
        results["n_capacity_drops"] = 0

    # Part B: local capacity gradient (K=10)
    K = 10
    tree = cKDTree(traffic_coords)
    _, knn_idx = tree.query(traffic_coords, k=K + 1)
    neighbor_cap = np.array(
        [matched.iloc[idx[1:]]["capacity_score"].mean() for idx in knn_idx]
    )
    matched["neighbor_cap_mean"] = neighbor_cap
    matched["capacity_drop_local"] = neighbor_cap - matched["capacity_score"].values
    thr = matched["capacity_drop_local"].quantile(0.75)
    matched["is_local_bottleneck"] = matched["capacity_drop_local"] >= thr

    bn = matched[matched["is_local_bottleneck"]]["jam_factor_mean"].dropna()
    non_bn = matched[~matched["is_local_bottleneck"]]["jam_factor_mean"].dropna()
    if len(bn) > 1 and len(non_bn) > 1:
        t_l, p_l = stats.ttest_ind(bn, non_bn)
        d_l = (bn.mean() - non_bn.mean()) / np.sqrt((bn.std() ** 2 + non_bn.std() ** 2) / 2)
    else:
        t_l = p_l = d_l = np.nan

    valid_l = matched[["capacity_drop_local", "jam_factor_mean"]].dropna()
    r_l, p_r_l = stats.pearsonr(valid_l.iloc[:, 0], valid_l.iloc[:, 1])
    rho_l, rho_p_l = stats.spearmanr(valid_l.iloc[:, 0], valid_l.iloc[:, 1])

    results.update(
        local_bn_jf=bn.mean(), local_non_bn_jf=non_bn.mean(),
        local_bn_t_stat=t_l, local_bn_p_value=p_l, local_bn_effect_size=d_l,
        local_drop_pearson_r=r_l, local_drop_pearson_p=p_r_l,
        local_drop_spearman_r=rho_l, local_drop_spearman_p=rho_p_l,
    )
    return matched, results


# ---------------------------------------------------------------------------
# Peak sensitivity
# ---------------------------------------------------------------------------


def compute_peak_sensitivity(city_code: str, base_dir: str | Path = ".") -> gpd.GeoDataFrame:
    """Load evening-peak and night data and compute sensitivity metrics."""
    folder = Path(base_dir) / CITIES[city_code]["traffic_output_dir"]
    peak = gpd.read_file(str(folder / f"evening_peak_{city_code}.gpkg"))
    night = gpd.read_file(str(folder / f"night_{city_code}.gpkg"))
    eps = 0.1
    peak["peak_sensitivity"] = (peak["jam_factor_mean"] - night["jam_factor_mean"]) / (night["jam_factor_mean"] + eps)
    peak["cv"] = peak["jam_factor_std"] / (peak["jam_factor_mean"] + eps)
    peak["peak_night_ratio"] = peak["jam_factor_mean"] / (night["jam_factor_mean"] + eps)
    return peak


# ---------------------------------------------------------------------------
# Spatial join
# ---------------------------------------------------------------------------


def spatial_join_traffic_roads(
    traffic_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    max_distance: float = 0.002,
) -> gpd.GeoDataFrame:
    """Join traffic segments to road edges by nearest-centroid."""
    road_coords = np.array([[p.x, p.y] for p in roads_gdf.geometry.centroid])
    traffic_coords = np.array([[p.x, p.y] for p in traffic_gdf.geometry.centroid])
    tree = cKDTree(road_coords)
    dists, idxs = tree.query(traffic_coords, k=1)
    valid = dists <= max_distance

    result = traffic_gdf.copy()
    for attr in ["lane_count", "road_score", "estimated_lanes", "capacity_score"]:
        result[attr] = np.nan
        result.loc[valid, attr] = roads_gdf.iloc[idxs[valid]][attr].values

    result["matched"] = valid
    result["match_distance"] = dists
    return result


# ---------------------------------------------------------------------------
# Full city analysis
# ---------------------------------------------------------------------------


def analyze_city(city_code: str, base_dir: str | Path = ".") -> tuple[gpd.GeoDataFrame, dict]:
    """Run the complete bottleneck analysis for one city.

    Returns ``(matched_gdf, results_dict)``.
    """
    city_name = CITIES[city_code]["name"]
    print(f"\n{'=' * 60}")
    print(f"Bottleneck Analysis: {city_name}")
    print(f"{'=' * 60}")

    roads, G = get_road_capacity(city_code)
    traffic = compute_peak_sensitivity(city_code, base_dir)
    traffic = spatial_join_traffic_roads(traffic, roads)
    matched = traffic[traffic["matched"]].copy()

    results: dict = {"city": city_name}

    # Low vs high capacity comparison
    med = matched["capacity_score"].median()
    low = matched[matched["capacity_score"] <= med]["jam_factor_mean"]
    high = matched[matched["capacity_score"] > med]["jam_factor_mean"]
    t, p = stats.ttest_ind(low.dropna(), high.dropna())
    d = (low.mean() - high.mean()) / np.sqrt((low.std() ** 2 + high.std() ** 2) / 2)
    results.update(low_cap_jf=low.mean(), high_cap_jf=high.mean(),
                   cap_diff_pct=(low.mean() - high.mean()) / high.mean() * 100,
                   cap_t_stat=t, cap_p_value=p, cap_effect_size=d)

    # Capacity-congestion correlation
    v = matched[["capacity_score", "jam_factor_mean"]].dropna()
    r, rp = stats.pearsonr(v.iloc[:, 0], v.iloc[:, 1])
    rho, rho_p = stats.spearmanr(v.iloc[:, 0], v.iloc[:, 1])
    results.update(cap_pearson_r=r, cap_pearson_p=rp, cap_spearman_r=rho, cap_spearman_p=rho_p)

    # Graph-based capacity drops
    drop_nodes, drop_mags, drop_coords = detect_capacity_drops(G, roads)
    matched, drop_res = analyze_capacity_drop_congestion(matched, drop_coords, drop_mags)
    results.update(drop_res)

    return matched, results


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_results(
    all_results: dict,
    figures_dir: str | Path = "figures",
    output_dir: str | Path = "analysis_results",
) -> None:
    """Generate bottleneck figures and save CSV summary."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    # --- Capacity comparison box-plot ---
    fig, axes = plt.subplots(1, len(all_results), figsize=(5 * len(all_results), 5))
    if len(all_results) == 1:
        axes = [axes]
    for idx, (code, (traffic, res)) in enumerate(all_results.items()):
        ax = axes[idx]
        med = traffic["capacity_score"].median()
        lo = traffic[traffic["capacity_score"] <= med]["jam_factor_mean"].dropna()
        hi = traffic[traffic["capacity_score"] > med]["jam_factor_mean"].dropna()
        bp = ax.boxplot([lo, hi], labels=["Low Capacity", "High Capacity"], patch_artist=True)
        for patch, c in zip(bp["boxes"], ["#e74c3c", "#27ae60"]):
            patch.set_facecolor(c)
            patch.set_alpha(0.7)
        p_val = res["cap_p_value"]
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        ax.set_title(f"{CITIES[code]['name']} (p={p_val:.4f} {sig})", fontweight="bold")
        ax.set_ylabel("Jam Factor" if idx == 0 else "")
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Congestion by Road Capacity (Evening Peak)", fontweight="bold")
    plt.tight_layout()
    plt.savefig(fig_dir / "bottleneck_capacity_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Save CSV
    rows = [r for _, (_, r) in all_results.items()]
    pd.DataFrame(rows).to_csv(out_dir / "bottleneck_analysis_results.csv", index=False)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def run_analysis(base_dir: str | Path = ".", figures_dir: str | Path = "figures") -> None:
    """Run bottleneck analysis for all cities."""
    all_results: dict = {}
    for code in CITIES:
        matched, res = analyze_city(code, base_dir)
        all_results[code] = (matched, res)
    plot_results(all_results, figures_dir)
    print("Bottleneck analysis complete.")


if __name__ == "__main__":
    run_analysis()
