"""
Geostatistical analysis and visualisation of traffic patterns.

Provides spatial statistics, hotspot classification, a spatial-
autocorrelation proxy, and a full suite of publication-ready figures.
"""

from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from trafficpipeline.config import CITIES, TIME_PERIODS, TIME_PERIOD_LABELS

import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Traffic colour-map
# ---------------------------------------------------------------------------

def _traffic_cmap() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(
        "traffic",
        ["#27ae60", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#c0392b"],
    )


TRAFFIC_CMAP = _traffic_cmap()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_city_data(city_code: str, base_dir: str | Path = ".") -> dict[str, gpd.GeoDataFrame]:
    """Load all time-period GeoPackages for a single city."""
    folder = Path(base_dir) / CITIES[city_code]["traffic_output_dir"]
    data: dict[str, gpd.GeoDataFrame] = {}
    for period in TIME_PERIODS:
        fp = folder / f"{period}_{city_code}.gpkg"
        if fp.exists():
            data[period] = gpd.read_file(str(fp))
    return data


def load_all_cities(base_dir: str | Path = ".") -> dict[str, dict[str, gpd.GeoDataFrame]]:
    """Load data for every city."""
    return {code: load_city_data(code, base_dir) for code in CITIES}


# ---------------------------------------------------------------------------
# Spatial statistics
# ---------------------------------------------------------------------------


def spatial_statistics(gdf: gpd.GeoDataFrame, column: str = "jam_factor_mean") -> dict:
    """Compute descriptive spatial statistics for *column*."""
    v = gdf[column].dropna()
    return {
        "count": len(v),
        "mean": float(v.mean()),
        "std": float(v.std()),
        "min": float(v.min()),
        "max": float(v.max()),
        "median": float(v.median()),
        "q25": float(v.quantile(0.25)),
        "q75": float(v.quantile(0.75)),
        "iqr": float(v.quantile(0.75) - v.quantile(0.25)),
        "cv": float(v.std() / v.mean()) if v.mean() > 0 else 0.0,
        "skewness": float(v.skew()),
        "kurtosis": float(v.kurtosis()),
    }


def hotspot_classification(
    gdf: gpd.GeoDataFrame,
    column: str = "jam_factor_mean",
) -> tuple[pd.Series, pd.Series]:
    """Classify segments into congestion categories.

    Returns ``(class_counts, class_pct)``.
    """
    v = gdf[column].copy()
    conditions = [
        v <= 1.0,
        (v > 1.0) & (v <= 2.0),
        (v > 2.0) & (v <= 4.0),
        (v > 4.0) & (v <= 6.0),
        v > 6.0,
    ]
    labels = ["Free Flow", "Light Traffic", "Moderate", "Heavy", "Severe"]
    gdf = gdf.copy()
    gdf["congestion_class"] = np.select(conditions, labels, default="Unknown")
    counts = gdf["congestion_class"].value_counts()
    pct = (counts / len(gdf) * 100).round(2)
    return counts, pct


def spatial_autocorrelation_proxy(
    gdf: gpd.GeoDataFrame,
    column: str = "jam_factor_mean",
    k: int = 5,
) -> tuple[float, gpd.GeoDataFrame]:
    """Compute a KNN-based spatial clustering indicator.

    Returns ``(correlation, gdf_with_local_mean)``.
    """
    from scipy.spatial import cKDTree

    gdf = gdf.copy()
    centroids = gdf.geometry.centroid
    values = gdf[column].values.astype(float)
    coords = np.array([[p.x, p.y] for p in centroids])

    tree = cKDTree(coords)
    kk = min(k + 1, len(coords))
    _, indices = tree.query(coords, k=kk)

    local_means = np.array([values[idx[1:]].mean() for idx in indices])
    gdf["local_mean"] = local_means
    gdf["local_deviation"] = values - local_means

    corr = float(np.corrcoef(values, local_means)[0, 1])
    return corr, gdf


# ---------------------------------------------------------------------------
# Plotting functions
# ---------------------------------------------------------------------------


def plot_city_traffic_maps(
    city_code: str,
    data: dict[str, gpd.GeoDataFrame],
    figures_dir: str | Path = "figures",
) -> Path:
    """Create an 8-panel traffic-intensity map for one city."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)
    city_name = CITIES[city_code]["name"]

    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    axes_flat = axes.flatten()

    for idx, period in enumerate(TIME_PERIODS):
        ax = axes_flat[idx]
        data[period].plot(
            column="jam_factor_mean", cmap=TRAFFIC_CMAP,
            linewidth=0.5, ax=ax, vmin=0, vmax=4, legend=False,
        )
        ax.set_title(TIME_PERIOD_LABELS[period], fontsize=10, fontweight="bold")
        ax.set_axis_off()

    sm = plt.cm.ScalarMappable(cmap=TRAFFIC_CMAP, norm=plt.Normalize(0, 4))
    sm.set_array([])
    fig.colorbar(sm, ax=axes_flat, orientation="horizontal", fraction=0.02, pad=0.08).set_label(
        "Jam Factor (0 = Free Flow, 4+ = Congested)", fontsize=12
    )
    plt.suptitle(f"{city_name} — Traffic Patterns by Time Period", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    fp = fig_dir / f"{city_code}_traffic_maps.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return fp


def plot_temporal_pattern(
    all_city_data: dict,
    figures_dir: str | Path = "figures",
) -> Path:
    """Bar chart comparing mean jam factor across time periods for all cities."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(TIME_PERIODS))
    w = 0.25

    for i, (code, data) in enumerate(all_city_data.items()):
        means = [data[p]["jam_factor_mean"].mean() for p in TIME_PERIODS]
        stds = [data[p]["jam_factor_mean"].std() for p in TIME_PERIODS]
        ax.bar(x + i * w, means, w, label=CITIES[code]["name"],
               color=CITIES[code]["color"], yerr=stds, capsize=3, alpha=0.8)

    ax.set_xlabel("Time Period")
    ax.set_ylabel("Mean Jam Factor")
    ax.set_title("Traffic Congestion Patterns by Time Period", fontweight="bold")
    ax.set_xticks(x + w)
    ax.set_xticklabels(
        [TIME_PERIOD_LABELS[p].replace("\n", " ") for p in TIME_PERIODS],
        rotation=45, ha="right", fontsize=9,
    )
    ax.legend(title="City")
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, 3)
    plt.tight_layout()
    fp = fig_dir / "temporal_pattern_comparison.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return fp


def plot_congestion_distribution(
    all_city_data: dict,
    figures_dir: str | Path = "figures",
) -> Path:
    """Histogram of jam-factor distributions per city."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    for idx, (code, data) in enumerate(all_city_data.items()):
        ax = axes[idx]
        vals = []
        for p in TIME_PERIODS:
            vals.extend(data[p]["jam_factor_mean"].dropna().tolist())
        ax.hist(vals, bins=50, color=CITIES[code]["color"], alpha=0.7, edgecolor="white")
        ax.axvline(np.mean(vals), color="red", ls="--", label=f"Mean: {np.mean(vals):.2f}")
        ax.axvline(np.median(vals), color="blue", ls="--", label=f"Median: {np.median(vals):.2f}")
        ax.set_xlabel("Jam Factor")
        ax.set_ylabel("Frequency")
        ax.set_title(CITIES[code]["name"], fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    plt.suptitle("Distribution of Traffic Congestion (All Time Periods)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fp = fig_dir / "congestion_distribution.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return fp


def plot_congestion_hotspots(
    city_code: str,
    data: dict[str, gpd.GeoDataFrame],
    period: str = "evening_peak",
    figures_dir: str | Path = "figures",
) -> Path:
    """Side-by-side intensity + hotspot classification map."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)
    city_name = CITIES[city_code]["name"]
    gdf = data[period].copy()

    fig, axes = plt.subplots(1, 2, figsize=(12, 10))

    gdf.plot(column="jam_factor_mean", cmap=TRAFFIC_CMAP, linewidth=0.8,
             ax=axes[0], vmin=0, vmax=4, legend=True,
             legend_kwds={"label": "Jam Factor", "shrink": 0.8})
    axes[0].set_title(f"{city_name} — Intensity ({TIME_PERIOD_LABELS[period]})", fontweight="bold")
    axes[0].set_axis_off()

    gdf["hotspot"] = "Normal"
    gdf.loc[gdf["jam_factor_mean"] > gdf["jam_factor_mean"].quantile(0.9), "hotspot"] = "Hotspot (Top 10%)"
    gdf.loc[gdf["jam_factor_mean"] < gdf["jam_factor_mean"].quantile(0.1), "hotspot"] = "Coldspot (Bottom 10%)"

    color_map = {"Normal": "#95a5a6", "Hotspot (Top 10%)": "#e74c3c", "Coldspot (Bottom 10%)": "#27ae60"}
    for label, color in color_map.items():
        sub = gdf[gdf["hotspot"] == label]
        if len(sub):
            sub.plot(ax=axes[1], color=color, linewidth=0.8, label=label)
    axes[1].legend(loc="lower right")
    axes[1].set_title(f"{city_name} — Hotspots", fontweight="bold")
    axes[1].set_axis_off()

    plt.tight_layout()
    fp = fig_dir / f"{city_code}_hotspots_{period}.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return fp


def plot_boxplot_comparison(
    all_city_data: dict,
    figures_dir: str | Path = "figures",
) -> Path:
    """Boxplot of jam factor by city and time period."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(16, 6))
    box_data, positions, colors = [], [], []
    pos = 0
    for period in TIME_PERIODS:
        for code in CITIES:
            box_data.append(all_city_data[code][period]["jam_factor_mean"].dropna().values)
            positions.append(pos)
            colors.append(CITIES[code]["color"])
            pos += 1
        pos += 0.5

    bp = ax.boxplot(box_data, positions=positions, widths=0.6, patch_artist=True, showfliers=False)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    period_pos = [i * 3.5 + 1 for i in range(len(TIME_PERIODS))]
    ax.set_xticks(period_pos)
    ax.set_xticklabels(
        [TIME_PERIOD_LABELS[p].replace("\n", " ") for p in TIME_PERIODS],
        rotation=45, ha="right", fontsize=9,
    )
    legend_patches = [mpatches.Patch(color=CITIES[c]["color"], label=CITIES[c]["name"], alpha=0.7) for c in CITIES]
    ax.legend(handles=legend_patches, loc="upper right")
    ax.set_ylabel("Jam Factor")
    ax.set_title("Traffic Congestion Distribution by City and Time Period", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    fp = fig_dir / "boxplot_comparison.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return fp


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def generate_statistics_report(
    all_city_data: dict,
    figures_dir: str | Path = "figures",
) -> str:
    """Create and save a plain-text statistics report."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    lines: list[str] = [
        "=" * 80,
        "GEOSTATISTICAL ANALYSIS REPORT — TRAFFIC PATTERNS",
        "=" * 80,
        "",
    ]

    for code, data in all_city_data.items():
        name = CITIES[code]["name"]
        lines += [f"\n{'=' * 40}", name.upper(), "=" * 40]
        all_means = []
        for p in TIME_PERIODS:
            all_means.extend(data[p]["jam_factor_mean"].dropna().tolist())
        lines.append(f"\nOverall: mean={np.mean(all_means):.4f}, std={np.std(all_means):.4f}")
        lines.append(f"\n{'Period':<20} {'Mean':>8} {'Std':>8} {'CV':>8}")
        lines.append("-" * 48)
        for period in TIME_PERIODS:
            s = spatial_statistics(data[period])
            lines.append(f"{period:<20} {s['mean']:>8.3f} {s['std']:>8.3f} {s['cv']:>8.3f}")

        counts, pct = hotspot_classification(data["evening_peak"])
        lines.append("\nEvening-peak classification:")
        for cat in ["Free Flow", "Light Traffic", "Moderate", "Heavy", "Severe"]:
            if cat in counts.index:
                lines.append(f"  {cat}: {counts[cat]} ({pct[cat]:.1f}%)")

        corr, _ = spatial_autocorrelation_proxy(data["evening_peak"])
        lines.append(f"\nSpatial clustering indicator: {corr:.4f}")

    report = "\n".join(lines)
    (fig_dir / "statistics_report.txt").write_text(report)
    return report


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def run_analysis(base_dir: str | Path = ".", figures_dir: str | Path = "figures") -> None:
    """Run the full geostatistical analysis pipeline."""
    print("Loading data …")
    all_data = load_all_cities(base_dir)

    print("Creating traffic maps …")
    for code in CITIES:
        plot_city_traffic_maps(code, all_data[code], figures_dir)

    print("Creating comparative figures …")
    plot_temporal_pattern(all_data, figures_dir)
    plot_congestion_distribution(all_data, figures_dir)
    plot_boxplot_comparison(all_data, figures_dir)

    print("Creating hotspot maps …")
    for code in CITIES:
        plot_congestion_hotspots(code, all_data[code], figures_dir=figures_dir)

    print("Generating statistics report …")
    generate_statistics_report(all_data, figures_dir)
    print("Done.")


if __name__ == "__main__":
    run_analysis()
