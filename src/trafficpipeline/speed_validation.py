"""
Speed-based validation of temporal dominance.

Runs one-way ANOVA across multiple speed metrics (jam factor, current
speed, speed reduction, free-flow speed) and computes centrality
correlations per metric type to confirm that temporal dominance is
not an artifact of jam factor normalization.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from trafficpipeline.config import CITIES, TIME_PERIODS, TIME_PERIOD_LABELS

import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

METRICS = ["jam_factor_mean", "speed_mean", "speed_reduction", "free_flow_mean"]
METRIC_LABELS = {
    "jam_factor_mean": "Jam factor",
    "speed_mean": "Current speed",
    "speed_reduction": "Speed reduction",
    "free_flow_mean": "Free-flow speed",
}


def load_metric_arrays(
    base_dir: str | Path = ".",
) -> dict[str, dict[str, dict[str, np.ndarray]]]:
    """Load per-city, per-period arrays for each speed metric.

    Returns nested dict: ``{city_code: {metric: {period: array}}}``.
    """
    base = Path(base_dir)
    data: dict[str, dict[str, dict[str, np.ndarray]]] = {}

    for code, info in CITIES.items():
        folder = base / info["traffic_output_dir"]
        city: dict[str, dict[str, np.ndarray]] = {m: {} for m in METRICS}

        for period in TIME_PERIODS:
            fp = folder / f"{period}_{code}.gpkg"
            if not fp.exists():
                continue
            gdf = gpd.read_file(str(fp))

            for m in METRICS:
                if m == "speed_reduction":
                    if "speed_mean" in gdf.columns and "free_flow_mean" in gdf.columns:
                        vals = (gdf["free_flow_mean"] - gdf["speed_mean"]).dropna().values
                    else:
                        continue
                elif m in gdf.columns:
                    vals = gdf[m].dropna().values
                else:
                    continue
                city[m][period] = vals

        data[code] = city
    return data


# ---------------------------------------------------------------------------
# ANOVA across metrics
# ---------------------------------------------------------------------------


def compute_eta_squared(
    groups: list[np.ndarray],
) -> dict:
    """One-way ANOVA returning F, p, and eta-squared."""
    f_stat, p_val = stats.f_oneway(*groups)
    all_vals = np.concatenate(groups)
    grand = all_vals.mean()
    ss_total = ((all_vals - grand) ** 2).sum()
    ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0
    return {
        "f_statistic": float(f_stat),
        "p_value": float(p_val),
        "eta_squared": float(eta2),
    }


def anova_all_metrics(
    data: dict[str, dict[str, dict[str, np.ndarray]]],
) -> pd.DataFrame:
    """Run ANOVA for each city × metric combination.

    Returns a DataFrame with columns: city, metric, f_statistic,
    p_value, eta_squared, eta_squared_pct.
    """
    rows: list[dict] = []
    for code, city_data in data.items():
        for metric in METRICS:
            groups = [city_data[metric][p]
                      for p in TIME_PERIODS
                      if p in city_data[metric]]
            if len(groups) < 2:
                continue
            res = compute_eta_squared(groups)
            rows.append({
                "city": CITIES[code]["name"],
                "city_code": code,
                "metric": METRIC_LABELS.get(metric, metric),
                "f_statistic": res["f_statistic"],
                "p_value": res["p_value"],
                "eta_squared": res["eta_squared"],
                "eta_squared_pct": res["eta_squared"] * 100,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Centrality correlations per metric
# ---------------------------------------------------------------------------


def centrality_correlations(
    base_dir: str | Path = ".",
    period: str = "evening_peak",
) -> pd.DataFrame:
    """Compute Pearson R² between betweenness centrality and each metric.

    Requires the bottleneck module's spatial join to have been run, or
    loads evening-peak GeoPackages and matches centrality via OSMnx.

    Returns DataFrame with columns: city, metric, r_squared, pearson_r,
    p_value.
    """
    import osmnx as ox
    from scipy.spatial import cKDTree

    from trafficpipeline.config import CITIES

    rows: list[dict] = []

    for code, info in CITIES.items():
        base = Path(base_dir)
        fp = base / info["traffic_output_dir"] / f"{period}_{code}.gpkg"
        if not fp.exists():
            continue
        gdf = gpd.read_file(str(fp))

        # Compute betweenness centrality from OSMnx
        try:
            G = ox.graph_from_bbox(bbox=info["bbox"], network_type="drive")
            bc = ox.edge_betweenness_centrality(G, weight="length")
            edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
            edges["betweenness"] = pd.Series(bc)
        except Exception:
            continue

        # Spatial join by nearest centroid
        edge_coords = np.array([[p.x, p.y] for p in edges.geometry.centroid])
        traffic_coords = np.array([[p.x, p.y] for p in gdf.geometry.centroid])
        tree = cKDTree(edge_coords)
        dists, idxs = tree.query(traffic_coords, k=1)
        valid = dists <= 0.002

        gdf = gdf.copy()
        gdf["betweenness"] = np.nan
        gdf.loc[valid, "betweenness"] = edges.iloc[idxs[valid]]["betweenness"].values

        matched = gdf.dropna(subset=["betweenness"])
        if len(matched) < 10:
            continue

        # Speed reduction
        if "speed_mean" in matched.columns and "free_flow_mean" in matched.columns:
            matched = matched.copy()
            matched["speed_reduction"] = matched["free_flow_mean"] - matched["speed_mean"]

        for metric in METRICS:
            col = metric
            if col not in matched.columns:
                continue
            v = matched[["betweenness", col]].dropna()
            if len(v) < 10:
                continue
            r, p_val = stats.pearsonr(v["betweenness"], v[col])
            rows.append({
                "city": CITIES[code]["name"],
                "city_code": code,
                "metric": METRIC_LABELS.get(metric, metric),
                "pearson_r": float(r),
                "r_squared": float(r ** 2),
                "p_value": float(p_val),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_eta_squared_comparison(
    df: pd.DataFrame,
    figures_dir: str | Path = "figures",
) -> Path:
    """Grouped bar chart of η² across metrics and cities."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    metrics_order = list(METRIC_LABELS.values())
    cities = df["city_code"].unique()
    x = np.arange(len(metrics_order))
    w = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, code in enumerate(cities):
        city_df = df[df["city_code"] == code]
        vals = []
        for m in metrics_order:
            row = city_df[city_df["metric"] == m]
            vals.append(row["eta_squared_pct"].values[0] if len(row) else 0)
        bars = ax.bar(x + i * w, vals, w, label=CITIES[code]["name"],
                      color=CITIES[code]["color"], alpha=0.85)
        for bar in bars:
            h = bar.get_height()
            if h > 0.01:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1,
                        f"{h:.1f}%", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x + w)
    ax.set_xticklabels(metrics_order, rotation=15)
    ax.set_ylabel("η² (%)")
    ax.set_title("Temporal Variance Explained by Metric Type", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    fp = fig_dir / "speed_validation_eta_squared.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


def plot_centrality_r2(
    df: pd.DataFrame,
    figures_dir: str | Path = "figures",
) -> Path:
    """Grouped bar chart of centrality R² per metric and city."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    if df.empty:
        return fig_dir / "centrality_r2_by_metric.png"

    metrics_order = list(METRIC_LABELS.values())
    cities = df["city_code"].unique()
    x = np.arange(len(metrics_order))
    w = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, code in enumerate(cities):
        city_df = df[df["city_code"] == code]
        vals = []
        for m in metrics_order:
            row = city_df[city_df["metric"] == m]
            vals.append(row["r_squared"].values[0] * 100 if len(row) else 0)
        ax.bar(x + i * w, vals, w, label=CITIES[code]["name"],
               color=CITIES[code]["color"], alpha=0.85)

    ax.set_xticks(x + w)
    ax.set_xticklabels(metrics_order, rotation=15)
    ax.set_ylabel("R²  (%)")
    ax.set_title("Centrality–Congestion Correlation by Metric Type",
                 fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    fp = fig_dir / "centrality_r2_by_metric.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def run_analysis(
    base_dir: str | Path = ".",
    figures_dir: str | Path = "figures",
    output_dir: str | Path = "analysis_results",
) -> None:
    """Run speed-based validation analysis."""
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    print("Loading metric arrays …")
    data = load_metric_arrays(base_dir)

    print("Running ANOVA across speed metrics …")
    eta_df = anova_all_metrics(data)
    eta_df.to_csv(out_dir / "speed_validation_anova.csv", index=False)
    print(eta_df[["city", "metric", "eta_squared_pct"]].to_string(index=False))

    plot_eta_squared_comparison(eta_df, figures_dir)

    print("\nComputing centrality correlations per metric …")
    cent_df = centrality_correlations(base_dir)
    if not cent_df.empty:
        cent_df.to_csv(out_dir / "centrality_by_metric.csv", index=False)
        print(cent_df[["city", "metric", "r_squared"]].to_string(index=False))
        plot_centrality_r2(cent_df, figures_dir)

    print("Speed validation complete.")
