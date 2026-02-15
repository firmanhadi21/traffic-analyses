"""
POI-congestion density analysis.

Downloads Points of Interest from OpenStreetMap via OSMnx,
computes POI density around traffic segments, and correlates
density with jam factor.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
from scipy import stats

from trafficpipeline.config import CITIES, POI_CATEGORIES

import warnings
warnings.filterwarnings("ignore")

ox.settings.use_cache = True
ox.settings.log_console = False


# ---------------------------------------------------------------------------
# POI helpers
# ---------------------------------------------------------------------------


def download_pois(
    city_code: str,
    category_name: str,
    tags: dict,
) -> gpd.GeoDataFrame:
    """Download POIs from OSM for *city_code* matching *tags*."""
    city = CITIES[city_code]
    try:
        pois = ox.features_from_bbox(bbox=city["bbox"], tags=tags)
        if len(pois) > 0:
            pois = pois.copy()
            pois["geometry"] = pois.geometry.centroid
            pois = pois[pois.geometry.type == "Point"]
        return pois
    except Exception:
        return gpd.GeoDataFrame()


def compute_poi_density(
    traffic_gdf: gpd.GeoDataFrame,
    poi_gdf: gpd.GeoDataFrame,
    buffer_distance: float = 0.005,
) -> np.ndarray:
    """Count POIs within *buffer_distance* (degrees) of each traffic centroid."""
    if len(poi_gdf) == 0:
        return np.zeros(len(traffic_gdf))
    centroids = traffic_gdf.geometry.centroid
    counts = []
    for c in centroids:
        counts.append(int(poi_gdf.geometry.within(c.buffer(buffer_distance)).sum()))
    return np.array(counts)


# ---------------------------------------------------------------------------
# City-level analysis
# ---------------------------------------------------------------------------


def analyze_city(
    city_code: str,
    base_dir: str | Path = ".",
    buffer_distance: float = 0.003,
) -> tuple[dict, list[dict], gpd.GeoDataFrame]:
    """Run POI-congestion analysis for one city.

    Returns ``(summary_results, category_results, traffic_gdf)``.
    """
    city = CITIES[city_code]
    city_name = city["name"]
    print(f"\nAnalyzing {city_name} …")

    folder = Path(base_dir) / city["traffic_output_dir"]
    traffic = gpd.read_file(str(folder / f"evening_peak_{city_code}.gpkg"))
    if traffic.crs is None:
        traffic = traffic.set_crs("EPSG:4326")

    results: dict = {"city": city_name, "n_segments": len(traffic)}
    all_poi_counts = np.zeros(len(traffic))
    cat_results: list[dict] = []

    for cat_name, cat_info in POI_CATEGORIES.items():
        pois = download_pois(city_code, cat_name, cat_info["tags"])
        n_pois = len(pois)
        if n_pois == 0:
            continue

        if pois.crs is None:
            pois = pois.set_crs("EPSG:4326")
        elif pois.crs != traffic.crs:
            pois = pois.to_crs(traffic.crs)

        counts = compute_poi_density(traffic, pois, buffer_distance)
        all_poi_counts += counts

        jf = traffic["jam_factor_mean"].values
        mask = ~(np.isnan(jf) | np.isnan(counts))
        if mask.sum() > 10:
            r, p = stats.pearsonr(jf[mask], counts[mask])
            rho, rho_p = stats.spearmanr(jf[mask], counts[mask])
            cat_results.append({
                "category": cat_name,
                "description": cat_info["description"],
                "n_pois": n_pois,
                "pearson_r": r, "pearson_p": p,
                "spearman_r": rho, "spearman_p": rho_p,
            })

    # Total density correlation
    jf = traffic["jam_factor_mean"].values
    mask = ~(np.isnan(jf) | np.isnan(all_poi_counts))
    if mask.sum() > 10:
        r_t, p_t = stats.pearsonr(jf[mask], all_poi_counts[mask])
        rho_t, rho_p_t = stats.spearmanr(jf[mask], all_poi_counts[mask])
        results.update(total_pois=int(all_poi_counts.sum()),
                       total_pearson_r=r_t, total_pearson_p=p_t,
                       total_spearman_r=rho_t, total_spearman_p=rho_p_t)

    traffic["poi_density"] = all_poi_counts
    return results, cat_results, traffic


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_scatter(traffic: gpd.GeoDataFrame, city_code: str, figures_dir: str | Path = "figures") -> Path:
    """Scatter plot: POI density vs jam factor."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)
    city = CITIES[city_code]

    fig, ax = plt.subplots(figsize=(10, 8))
    x, y = traffic["poi_density"].values, traffic["jam_factor_mean"].values
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    ax.scatter(x, y, alpha=0.4, s=20, color=city["color"], edgecolors="white", linewidth=0.3)

    slope, intercept, r, p, _ = stats.linregress(x, y)
    xl = np.linspace(x.min(), x.max(), 100)
    ax.plot(xl, slope * xl + intercept, "r-", lw=2, label=f"r={r:.4f} (p={p:.4f})")

    ax.set_xlabel("POI Density (count within 300 m)")
    ax.set_ylabel("Jam Factor")
    ax.set_title(f"{city['name']}: POI Density vs Congestion", fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    fp = fig_dir / f"{city_code}_poi_congestion_scatter.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


def plot_category_comparison(
    all_cat_results: dict[str, list[dict]],
    figures_dir: str | Path = "figures",
) -> Path:
    """Bar chart of per-category Spearman correlations."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    categories = list(POI_CATEGORIES.keys())
    x = np.arange(len(categories))
    w = 0.25

    fig, ax = plt.subplots(figsize=(14, 8))
    for i, (code, cats) in enumerate(all_cat_results.items()):
        vals = []
        for cat in categories:
            row = next((c for c in cats if c["category"] == cat), None)
            vals.append(row["spearman_r"] if row else 0)
        ax.bar(x + i * w, vals, w, label=CITIES[code]["name"], color=CITIES[code]["color"], alpha=0.8)

    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("POI Category")
    ax.set_ylabel("Spearman Correlation")
    ax.set_title("POI-Congestion Correlation by Category", fontweight="bold")
    ax.set_xticks(x + w)
    ax.set_xticklabels([POI_CATEGORIES[c]["description"] for c in categories], rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    fp = fig_dir / "poi_category_comparison.png"
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
    """Run POI analysis for all cities."""
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    all_results, all_cats = [], {}
    for code in CITIES:
        res, cats, traffic = analyze_city(code, base_dir)
        all_results.append(res)
        all_cats[code] = cats
        plot_scatter(traffic, code, figures_dir)

    plot_category_comparison(all_cats, figures_dir)
    pd.DataFrame(all_results).to_csv(out / "poi_congestion_correlations.csv", index=False)
    print("POI analysis complete.")


if __name__ == "__main__":
    run_analysis()
