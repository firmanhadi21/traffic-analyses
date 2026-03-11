"""
H3 hexagonal aggregation for MAUP robustness testing.

Aggregates segment-level traffic data to Uber H3 hexagons at multiple
resolutions, then re-runs Global Moran's I to test whether null spatial
autocorrelation results persist at neighbourhood scales.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from trafficpipeline.config import CITIES, TIME_PERIODS

import warnings
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# H3 aggregation
# ---------------------------------------------------------------------------


def h3_aggregate(
    gdf: gpd.GeoDataFrame,
    resolution: int = 8,
    column: str = "jam_factor_mean",
) -> gpd.GeoDataFrame:
    """Aggregate segment values to H3 hexagons at *resolution*.

    Requires the ``h3`` package (``pip install h3``).

    Returns a GeoDataFrame indexed by H3 cell with columns:
    ``h3_index``, ``mean``, ``median``, ``std``, ``count``, ``geometry``.
    """
    import h3
    from shapely.geometry import Polygon

    gdf = gdf.copy()
    centroids = gdf.geometry.centroid
    gdf["h3_index"] = [
        h3.latlng_to_cell(lat, lng, resolution)
        for lat, lng in zip(centroids.y, centroids.x)
    ]

    agg = gdf.groupby("h3_index")[column].agg(["mean", "median", "std", "count"])
    agg = agg.reset_index()

    # Build hexagon geometries
    polys = []
    for idx in agg["h3_index"]:
        boundary = h3.cell_to_boundary(idx)
        # h3 returns (lat, lng) tuples; convert to (lng, lat)
        coords = [(lng, lat) for lat, lng in boundary]
        coords.append(coords[0])  # close polygon
        polys.append(Polygon(coords))

    result = gpd.GeoDataFrame(agg, geometry=polys, crs="EPSG:4326")
    return result


# ---------------------------------------------------------------------------
# Moran's I on H3 grid
# ---------------------------------------------------------------------------


def h3_moran(
    h3_gdf: gpd.GeoDataFrame,
    column: str = "mean",
    k: int = 6,
    permutations: int = 999,
) -> dict:
    """Compute Global Moran's I on H3-aggregated data.

    Returns dict with ``morans_i``, ``z_score``, ``p_value``,
    ``n_hexagons``.
    """
    from esda import Moran
    from libpysal.weights import KNN

    if len(h3_gdf) < k + 1:
        return {
            "morans_i": np.nan,
            "z_score": np.nan,
            "p_value": np.nan,
            "n_hexagons": len(h3_gdf),
        }

    w = KNN.from_dataframe(h3_gdf, k=k)
    w.transform = "r"

    mi = Moran(h3_gdf[column].values, w, permutations=permutations)
    return {
        "morans_i": float(mi.I),
        "z_score": float(mi.z_sim),
        "p_value": float(mi.p_sim),
        "n_hexagons": len(h3_gdf),
    }


# ---------------------------------------------------------------------------
# Multi-resolution sweep
# ---------------------------------------------------------------------------


def resolution_sweep(
    gdf: gpd.GeoDataFrame,
    column: str = "jam_factor_mean",
    resolutions: list[int] | None = None,
) -> pd.DataFrame:
    """Run Moran's I at multiple H3 resolutions.

    Returns DataFrame with columns: resolution, n_hexagons, morans_i,
    z_score, p_value, significant.
    """
    if resolutions is None:
        resolutions = [6, 7, 8, 9]

    rows: list[dict] = []
    for res in resolutions:
        h3_gdf = h3_aggregate(gdf, resolution=res, column=column)
        if len(h3_gdf) < 10:
            continue
        mi = h3_moran(h3_gdf)
        rows.append({
            "resolution": res,
            **mi,
            "significant": mi["p_value"] < 0.05 if not np.isnan(mi["p_value"]) else False,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_resolution_sweep(
    all_sweeps: dict[str, pd.DataFrame],
    figures_dir: str | Path = "figures",
) -> Path:
    """Line plot of Moran's I across resolutions per city."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Panel 1: Moran's I
    ax = axes[0]
    for code, df in all_sweeps.items():
        ax.plot(df["resolution"], df["morans_i"], "o-",
                color=CITIES[code]["color"], label=CITIES[code]["name"],
                linewidth=2, markersize=8)
    ax.axhline(y=0, ls="--", color="gray", alpha=0.5)
    ax.set_xlabel("H3 Resolution")
    ax.set_ylabel("Moran's I")
    ax.set_title("Spatial Autocorrelation by Scale", fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)

    # Panel 2: p-values
    ax = axes[1]
    for code, df in all_sweeps.items():
        ax.plot(df["resolution"], df["p_value"], "s-",
                color=CITIES[code]["color"], label=CITIES[code]["name"],
                linewidth=2, markersize=8)
    ax.axhline(y=0.05, ls="--", color="red", alpha=0.5, label="p = 0.05")
    ax.set_xlabel("H3 Resolution")
    ax.set_ylabel("p-value")
    ax.set_title("Significance by Scale", fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    fp = fig_dir / "h3_resolution_sweep.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


def plot_h3_map(
    h3_gdf: gpd.GeoDataFrame,
    city_name: str,
    resolution: int,
    figures_dir: str | Path = "figures",
) -> Path:
    """Choropleth map of H3-aggregated congestion."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 10))
    h3_gdf.plot(column="mean", cmap="YlOrRd", linewidth=0.5, edgecolor="gray",
                ax=ax, legend=True,
                legend_kwds={"label": "Mean Jam Factor", "shrink": 0.7})
    ax.set_title(f"{city_name} — H3 Resolution {resolution}", fontweight="bold")
    ax.set_axis_off()
    plt.tight_layout()

    safe = city_name.lower().replace(" ", "_")
    fp = fig_dir / f"h3_map_{safe}_res{resolution}.png"
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
    period: str = "evening_peak",
    resolutions: list[int] | None = None,
) -> None:
    """Run H3 hexagonal robustness analysis for all cities."""
    if resolutions is None:
        resolutions = [6, 7, 8, 9]

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    base = Path(base_dir)

    all_sweeps: dict[str, pd.DataFrame] = {}
    all_rows: list[dict] = []

    for code, info in CITIES.items():
        name = info["name"]
        fp = base / info["traffic_output_dir"] / f"{period}_{code}.gpkg"
        if not fp.exists():
            print(f"  Skipping {name}: {fp} not found")
            continue

        print(f"\n{name}")
        print(f"  Loading {period} data …")
        gdf = gpd.read_file(str(fp))

        print(f"  Running resolution sweep ({resolutions}) …")
        sweep = resolution_sweep(gdf, resolutions=resolutions)
        all_sweeps[code] = sweep

        for _, row in sweep.iterrows():
            sig_str = "SIGNIFICANT" if row["significant"] else "not significant"
            print(f"    res={int(row['resolution'])}  "
                  f"n={int(row['n_hexagons'])}  "
                  f"I={row['morans_i']:.4f}  "
                  f"p={row['p_value']:.3f}  ({sig_str})")
            all_rows.append({"city": name, **row.to_dict()})

        # Map at resolution 8
        if 8 in resolutions:
            h3_gdf = h3_aggregate(gdf, resolution=8)
            plot_h3_map(h3_gdf, name, 8, figures_dir)

    if all_sweeps:
        plot_resolution_sweep(all_sweeps, figures_dir)

    pd.DataFrame(all_rows).to_csv(
        out_dir / "h3_robustness_results.csv", index=False
    )
    print("\nH3 robustness analysis complete.")
