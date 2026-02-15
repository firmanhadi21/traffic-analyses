"""
Temporal vs spatial predictor comparison (synthesis).

Computes temporal eta-squared, loads POI and centrality R-squared,
and produces comparison bar-charts and radar plots.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from trafficpipeline.config import CITIES, TIME_PERIODS

import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_temporal_data(base_dir: str | Path = ".") -> dict[str, dict[str, np.ndarray]]:
    """Load jam-factor arrays for every city and period."""
    base = Path(base_dir)
    data: dict[str, dict[str, np.ndarray]] = {}
    for code, info in CITIES.items():
        folder = base / info["traffic_output_dir"]
        city: dict[str, np.ndarray] = {}
        for period in TIME_PERIODS:
            fp = folder / f"{period}_{code}.gpkg"
            if fp.exists():
                gdf = gpd.read_file(str(fp))
                city[period] = gdf["jam_factor_mean"].values
        data[code] = city
    return data


# ---------------------------------------------------------------------------
# Temporal effect size
# ---------------------------------------------------------------------------


def compute_temporal_effect(all_data: dict) -> dict[str, dict]:
    """Compute eta-squared (one-way ANOVA) for time-of-day variation."""
    results: dict[str, dict] = {}
    for code, city_data in all_data.items():
        groups = [city_data[p] for p in TIME_PERIODS if p in city_data]
        f_stat, p_val = stats.f_oneway(*groups)
        all_vals = np.concatenate(groups)
        grand = all_vals.mean()
        ss_total = ((all_vals - grand) ** 2).sum()
        ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
        eta2 = ss_between / ss_total
        results[code] = {
            "f_statistic": float(f_stat),
            "p_value": float(p_val),
            "eta_squared": float(eta2),
            "variance_explained_pct": float(eta2 * 100),
        }
    return results


# ---------------------------------------------------------------------------
# Spatial correlation loaders
# ---------------------------------------------------------------------------


def load_correlation_results(
    output_dir: str | Path = "analysis_results",
) -> tuple[dict[str, float], dict[str, float]]:
    """Load POI and centrality R-squared from CSV files."""
    out = Path(output_dir)
    name_to_code = {"Semarang": "smg", "Bandung": "bdg", "Jakarta": "jkt"}

    poi_corr: dict[str, float] = {}
    fp = out / "poi_congestion_correlations.csv"
    if fp.exists():
        df = pd.read_csv(fp)
        for _, row in df.iterrows():
            code = name_to_code.get(row["city"])
            if code:
                poi_corr[code] = row.get("total_spearman_r", 0) ** 2

    cent_corr: dict[str, float] = {}
    fp = out / "centrality_correlations.csv"
    if fp.exists():
        df = pd.read_csv(fp)
        for _, row in df.iterrows():
            code = name_to_code.get(row["city"])
            if code:
                cent_corr[code] = row.get("spearman_r", 0) ** 2

    return poi_corr, cent_corr


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_effect_size_comparison(
    temporal: dict,
    poi_corr: dict,
    cent_corr: dict,
    figures_dir: str | Path = "figures",
) -> Path:
    """Bar chart comparing variance explained by each predictor."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    cities = list(CITIES.keys())
    names = [CITIES[c]["name"] for c in cities]
    x = np.arange(len(cities))
    w = 0.25

    t_vals = [temporal[c]["variance_explained_pct"] for c in cities]
    p_vals = [poi_corr.get(c, 0) * 100 for c in cities]
    c_vals = [cent_corr.get(c, 0) * 100 for c in cities]

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.bar(x - w, t_vals, w, label="Time Period (eta sq)", color="#e74c3c", alpha=0.8)
    ax.bar(x, p_vals, w, label="POI Density (R sq)", color="#3498db", alpha=0.8)
    ax.bar(x + w, c_vals, w, label="Centrality (R sq)", color="#2ecc71", alpha=0.8)

    for bars in [ax.containers[0], ax.containers[1], ax.containers[2]]:
        for bar in bars:
            h = bar.get_height()
            if h > 0.1:
                ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.1f}%",
                        ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Variance Explained (%)")
    ax.set_title("Congestion Predictors: Temporal vs Spatial", fontweight="bold")
    ax.legend(loc="upper right")
    ax.set_ylim(0, max(t_vals) * 1.2)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    fp = fig_dir / "temporal_vs_spatial_effect_size.png"
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
    """Run temporal-vs-spatial synthesis."""
    data = load_temporal_data(base_dir)
    temporal = compute_temporal_effect(data)

    for code, eff in temporal.items():
        print(f"  {CITIES[code]['name']}: eta^2={eff['eta_squared']:.4f} "
              f"({eff['variance_explained_pct']:.1f}%)")

    poi_corr, cent_corr = load_correlation_results(output_dir)
    plot_effect_size_comparison(temporal, poi_corr, cent_corr, figures_dir)
    print("Synthesis complete.")


if __name__ == "__main__":
    run_analysis()
