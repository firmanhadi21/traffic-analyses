"""
Exploratory Data Analysis (EDA) and data-quality validation.

Checks for nulls, completeness, value ranges, temporal coverage,
and generates validation figures and a Markdown report.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import warnings

from trafficpipeline.config import CITIES, TIME_PERIODS

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_all_data(base_dir: str | Path = ".") -> dict[str, dict[str, gpd.GeoDataFrame]]:
    """Load aggregated GeoPackages for every city and time period.

    Parameters
    ----------
    base_dir : path-like
        Root directory containing ``traffic_*_output/`` folders.

    Returns
    -------
    dict
        ``{city_code: {period: GeoDataFrame}}``
    """
    base = Path(base_dir)
    data: dict[str, dict[str, gpd.GeoDataFrame]] = {}
    for code, info in CITIES.items():
        folder = base / info["traffic_output_dir"]
        city_data: dict[str, gpd.GeoDataFrame] = {}
        for period in TIME_PERIODS:
            fp = folder / f"{period}_{code}.gpkg"
            if fp.exists():
                city_data[period] = gpd.read_file(str(fp))
        data[code] = city_data
    return data


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------


def check_null_values(all_data: dict) -> list[dict]:
    """Check for null / missing values in key columns."""
    KEY_COLS = [
        "jam_factor_mean", "jam_factor_std",
        "jam_factor_min", "jam_factor_max",
        "jam_factor_count", "geometry",
    ]
    report: list[dict] = []
    for code, city_data in all_data.items():
        for period, gdf in city_data.items():
            nulls = {
                col: {"count": int(gdf[col].isna().sum()), "pct": gdf[col].isna().mean() * 100}
                for col in KEY_COLS if col in gdf.columns
            }
            has_nulls = any(v["count"] > 0 for v in nulls.values())
            report.append({
                "city": CITIES[code]["name"],
                "period": period,
                "total_rows": len(gdf),
                "has_nulls": has_nulls,
                "null_details": nulls,
            })
    return report


def check_completeness(all_data: dict) -> list[dict]:
    """Verify segment count consistency across time periods."""
    report: list[dict] = []
    for code, city_data in all_data.items():
        counts = [len(gdf) for gdf in city_data.values()]
        obs = [
            gdf["jam_factor_count"].sum()
            for gdf in city_data.values()
            if "jam_factor_count" in gdf.columns
        ]
        report.append({
            "city": CITIES[code]["name"],
            "segments": counts[0] if counts else 0,
            "is_consistent": len(set(counts)) == 1,
            "total_observations": int(sum(obs)),
        })
    return report


def check_value_ranges(all_data: dict) -> list[dict]:
    """Check that jam-factor means fall in [0, 10]."""
    report: list[dict] = []
    for code, city_data in all_data.items():
        means = pd.concat(
            [gdf["jam_factor_mean"].dropna() for gdf in city_data.values()]
        )
        oor = int(((means < 0) | (means > 10)).sum())
        report.append({
            "city": CITIES[code]["name"],
            "min_value": float(means.min()),
            "max_value": float(means.max()),
            "out_of_range": oor,
            "is_valid": oor == 0,
        })
    return report


# ---------------------------------------------------------------------------
# Visualisations
# ---------------------------------------------------------------------------


def create_visualizations(
    all_data: dict,
    output_dir: str | Path = "eda_output",
) -> None:
    """Generate EDA figures (coverage, completeness, distributions, nulls)."""
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    cities = list(CITIES.keys())
    names = [CITIES[c]["name"] for c in cities]
    colors = [CITIES[c]["color"] for c in cities]

    # ---- Coverage comparison ----
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    seg_counts = [len(all_data[c][TIME_PERIODS[0]]) for c in cities]
    bars = axes[0].bar(names, seg_counts, color=colors, edgecolor="black")
    axes[0].set_ylabel("Number of Segments")
    axes[0].set_title("(a) Road Segment Coverage")
    for b, n in zip(bars, seg_counts):
        axes[0].text(b.get_x() + b.get_width() / 2, b.get_height(), f"{n:,}",
                     ha="center", va="bottom", fontsize=10)

    obs_totals = []
    for c in cities:
        obs_totals.append(sum(
            all_data[c][p]["jam_factor_count"].sum()
            for p in TIME_PERIODS if "jam_factor_count" in all_data[c][p].columns
        ))
    bars = axes[1].bar(names, [o / 1e6 for o in obs_totals], color=colors, edgecolor="black")
    axes[1].set_ylabel("Total Observations (millions)")
    axes[1].set_title("(b) Data Volume")

    obs_per = [o / s for o, s in zip(obs_totals, seg_counts)]
    axes[2].bar(names, obs_per, color=colors, edgecolor="black")
    axes[2].set_ylabel("Observations per Segment")
    axes[2].set_title("(c) Data Density")
    axes[2].axhline(np.mean(obs_per), color="red", ls="--", label="Mean")
    axes[2].legend()

    plt.suptitle("Data Coverage Validation Across Cities", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out / "eda_coverage_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ---- Distribution validation ----
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for idx, code in enumerate(cities):
        vals = pd.concat([all_data[code][p]["jam_factor_mean"].dropna() for p in TIME_PERIODS])
        axes[idx].hist(vals, bins=50, color=CITIES[code]["color"], alpha=0.7, edgecolor="white")
        axes[idx].axvline(vals.mean(), color="red", ls="--", label=f"Mean: {vals.mean():.2f}")
        axes[idx].axvline(vals.median(), color="blue", ls="--", label=f"Median: {vals.median():.2f}")
        axes[idx].set_xlabel("Jam Factor")
        axes[idx].set_ylabel("Frequency")
        axes[idx].set_title(f"{CITIES[code]['name']} (n={len(vals):,})")
        axes[idx].legend(fontsize=8)
        axes[idx].set_xlim(0, 10)

    plt.suptitle("Jam Factor Distribution Validation", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out / "eda_distribution_validation.png", dpi=150, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    all_data: dict,
    output_dir: str | Path = "eda_output",
    *,
    verbose: bool = True,
) -> str:
    """Run all validations and write an EDA report.

    Returns the report as a Markdown string.
    """
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    null_rpt = check_null_values(all_data)
    comp_rpt = check_completeness(all_data)
    range_rpt = check_value_ranges(all_data)

    all_ok = (
        all(not r["has_nulls"] for r in null_rpt)
        and all(r["is_consistent"] for r in comp_rpt)
        and all(r["is_valid"] for r in range_rpt)
    )

    lines = [
        "# Exploratory Data Analysis Report",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "## Executive Summary",
        "",
        "**DATA VALIDATION: PASSED**" if all_ok else "**DATA VALIDATION: ISSUES FOUND**",
        "",
        "## Null Value Check",
        "",
        "PASS" if all(not r["has_nulls"] for r in null_rpt) else "WARNING: nulls detected",
        "",
        "## Data Completeness",
        "",
        "| City | Segments | Consistent | Total Observations |",
        "|------|----------|------------|-------------------|",
    ]
    for r in comp_rpt:
        lines.append(
            f"| {r['city']} | {r['segments']:,} | {'Yes' if r['is_consistent'] else 'No'} "
            f"| {r['total_observations']:,} |"
        )
    lines += [
        "",
        "## Value Range Validation",
        "",
        "| City | Min JF | Max JF | Valid |",
        "|------|--------|--------|-------|",
    ]
    for r in range_rpt:
        lines.append(
            f"| {r['city']} | {r['min_value']:.3f} | {r['max_value']:.3f} "
            f"| {'Yes' if r['is_valid'] else 'No'} |"
        )

    md = "\n".join(lines)
    (out / "eda_report.md").write_text(md)

    if verbose:
        print(md)

    create_visualizations(all_data, output_dir=out)
    return md


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run EDA from the command line."""
    print("=" * 70)
    print("EXPLORATORY DATA ANALYSIS")
    print("=" * 70)

    data = load_all_data()
    generate_report(data)

    print("\nEDA complete.")


if __name__ == "__main__":
    main()
