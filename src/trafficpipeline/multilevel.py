"""
Multilevel variance decomposition of traffic speed.

Fits nested mixed-effects models (null → temporal → full) using absolute
speed (km/h) to partition within-segment (temporal) and between-segment
(spatial) variance contributions.  Produces ICC, temporal R², spatial ΔR²,
and summary tables / figures.
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
# Data loading
# ---------------------------------------------------------------------------


def load_speed_panel(
    base_dir: str | Path = ".",
) -> dict[str, pd.DataFrame]:
    """Build a long-format panel (segment × period) with speed metrics.

    Returns a dict mapping city codes to DataFrames with columns:
    ``segment_id``, ``period``, ``speed_mean``, ``free_flow_mean``,
    ``jam_factor_mean``, ``speed_reduction``.
    """
    base = Path(base_dir)
    panels: dict[str, pd.DataFrame] = {}

    for code, info in CITIES.items():
        folder = base / info["traffic_output_dir"]
        rows: list[pd.DataFrame] = []
        for period in TIME_PERIODS:
            fp = folder / f"{period}_{code}.gpkg"
            if not fp.exists():
                continue
            gdf = gpd.read_file(str(fp))
            df = pd.DataFrame({
                "segment_id": range(len(gdf)),
                "period": period,
                "speed_mean": gdf["speed_mean"].values
                    if "speed_mean" in gdf.columns else np.nan,
                "free_flow_mean": gdf["free_flow_mean"].values
                    if "free_flow_mean" in gdf.columns else np.nan,
                "jam_factor_mean": gdf["jam_factor_mean"].values,
            })
            rows.append(df)
        if rows:
            panel = pd.concat(rows, ignore_index=True)
            panel["speed_reduction"] = panel["free_flow_mean"] - panel["speed_mean"]
            panels[code] = panel.dropna(subset=["speed_mean"])

    return panels


# ---------------------------------------------------------------------------
# Multilevel models
# ---------------------------------------------------------------------------


def fit_multilevel_models(
    panel: pd.DataFrame,
) -> dict:
    """Fit null → temporal → full mixed-effects models.

    Parameters
    ----------
    panel : DataFrame
        Long-format panel with ``segment_id``, ``period``, ``speed_mean``,
        ``free_flow_mean`` columns.

    Returns
    -------
    dict with keys: n_segments, icc, temporal_r2, spatial_delta_r2,
    beta_centrality, beta_centrality_p, null_var_segment, null_var_resid,
    temporal_var_resid, full_var_segment.
    """
    import statsmodels.formula.api as smf

    panel = panel.copy()
    panel["period_code"] = pd.Categorical(panel["period"]).codes

    # --- Null model: speed ~ 1 | segment_id ---
    null = smf.mixedlm(
        "speed_mean ~ 1",
        data=panel,
        groups=panel["segment_id"],
    ).fit(reml=True)

    var_segment = float(null.cov_re.iloc[0, 0])
    var_resid = float(null.scale)
    icc = var_segment / (var_segment + var_resid)

    # --- Temporal model: speed ~ C(period) | segment_id ---
    temporal = smf.mixedlm(
        "speed_mean ~ C(period)",
        data=panel,
        groups=panel["segment_id"],
    ).fit(reml=True)

    var_resid_temporal = float(temporal.scale)
    temporal_r2 = 1.0 - var_resid_temporal / var_resid

    # --- Full model: speed ~ C(period) + free_flow_mean | segment_id ---
    full = smf.mixedlm(
        "speed_mean ~ C(period) + free_flow_mean",
        data=panel,
        groups=panel["segment_id"],
    ).fit(reml=True)

    var_segment_full = float(full.cov_re.iloc[0, 0])
    var_segment_temporal = float(temporal.cov_re.iloc[0, 0])
    spatial_delta_r2 = 1.0 - var_segment_full / var_segment_temporal

    n_segments = panel["segment_id"].nunique()

    return {
        "n_segments": n_segments,
        "icc": icc,
        "temporal_r2": temporal_r2,
        "spatial_delta_r2": spatial_delta_r2,
        "null_var_segment": var_segment,
        "null_var_resid": var_resid,
        "temporal_var_resid": var_resid_temporal,
        "full_var_segment": var_segment_full,
    }


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_variance_decomposition(
    results: dict[str, dict],
    figures_dir: str | Path = "figures",
) -> Path:
    """Grouped bar chart of ICC, temporal R², and spatial ΔR²."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(exist_ok=True)

    cities = list(results.keys())
    names = [CITIES[c]["name"] for c in cities]
    x = np.arange(len(cities))
    w = 0.22

    icc_vals = [results[c]["icc"] * 100 for c in cities]
    temp_vals = [results[c]["temporal_r2"] * 100 for c in cities]
    spat_vals = [results[c]["spatial_delta_r2"] * 100 for c in cities]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_icc = ax.bar(x - w, icc_vals, w, label="ICC (between-segment %)",
                      color="#3498db", alpha=0.85)
    bars_tmp = ax.bar(x, temp_vals, w, label="Temporal R² (%)",
                      color="#e74c3c", alpha=0.85)
    bars_spt = ax.bar(x + w, spat_vals, w, label="Spatial ΔR² (%)",
                      color="#2ecc71", alpha=0.85)

    for bars in [bars_icc, bars_tmp, bars_spt]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                    f"{h:.1f}%", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Variance Explained (%)")
    ax.set_title("Multilevel Variance Decomposition (Absolute Speed)",
                 fontweight="bold")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    fp = fig_dir / "multilevel_variance_decomposition.png"
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
    """Run multilevel variance decomposition for all cities."""
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    print("Loading speed panel data …")
    panels = load_speed_panel(base_dir)

    results: dict[str, dict] = {}
    for code, panel in panels.items():
        name = CITIES[code]["name"]
        print(f"  Fitting multilevel models: {name} …")
        res = fit_multilevel_models(panel)
        results[code] = res
        print(f"    ICC={res['icc']:.1%}  Temporal R²={res['temporal_r2']:.1%}"
              f"  Spatial ΔR²={res['spatial_delta_r2']:.1%}")

    # Save CSV summary
    rows = []
    for code, res in results.items():
        row = {"city": CITIES[code]["name"], **res}
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_dir / "multilevel_results.csv", index=False)

    plot_variance_decomposition(results, figures_dir)
    print("Multilevel analysis complete.")
