"""
LISA Markov and Spatial Markov analysis of congestion dynamics.

Computes LISA categories per segment per time period using PySAL (esda),
then fits classic Markov and Spatial Markov transition models via giddy
to quantify hotspot persistence and spatial contagion.
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
# LISA computation
# ---------------------------------------------------------------------------


def compute_lisa(
    gdf: gpd.GeoDataFrame,
    column: str = "jam_factor_mean",
    k: int = 8,
    permutations: int = 999,
    significance: float = 0.05,
) -> gpd.GeoDataFrame:
    """Compute Local Moran's I and assign LISA categories.

    Requires ``libpysal`` and ``esda`` (install with
    ``pip install traffic-congestion-pipeline[pysal]``).

    Returns *gdf* with added columns: ``lisa_i``, ``lisa_p``,
    ``lisa_q``, ``lisa_cat``.
    """
    from esda import Moran_Local
    from libpysal.weights import KNN

    gdf = gdf.copy()
    w = KNN.from_dataframe(gdf, k=k)
    w.transform = "r"

    lisa = Moran_Local(gdf[column].values, w, permutations=permutations)

    gdf["lisa_i"] = lisa.Is
    gdf["lisa_p"] = lisa.p_sim
    gdf["lisa_q"] = lisa.q

    # Quadrant labels: 1=HH, 2=LH, 3=LL, 4=HL
    quad_labels = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    gdf["lisa_cat"] = "NS"
    sig = gdf["lisa_p"] < significance
    gdf.loc[sig, "lisa_cat"] = gdf.loc[sig, "lisa_q"].map(quad_labels)

    return gdf


def compute_global_moran(
    gdf: gpd.GeoDataFrame,
    column: str = "jam_factor_mean",
    k: int = 8,
    permutations: int = 999,
) -> dict:
    """Compute Global Moran's I.

    Returns dict with ``morans_i``, ``z_score``, ``p_value``.
    """
    from esda import Moran
    from libpysal.weights import KNN

    w = KNN.from_dataframe(gdf, k=k)
    w.transform = "r"

    mi = Moran(gdf[column].values, w, permutations=permutations)
    return {
        "morans_i": float(mi.I),
        "z_score": float(mi.z_sim),
        "p_value": float(mi.p_sim),
    }


# ---------------------------------------------------------------------------
# LISA matrix construction
# ---------------------------------------------------------------------------

LISA_STATES = ["NS", "HH", "LL", "LH", "HL"]
LISA_CODE = {s: i for i, s in enumerate(LISA_STATES)}


def build_lisa_matrix(
    city_code: str,
    base_dir: str | Path = ".",
    column: str = "jam_factor_mean",
    k: int = 8,
) -> tuple[np.ndarray, list[gpd.GeoDataFrame]]:
    """Build (n_segments × n_periods) integer matrix of LISA codes.

    Returns ``(y, gdfs)`` where y[i, t] ∈ {0..4} encodes LISA_STATES.
    """
    base = Path(base_dir)
    folder = base / CITIES[city_code]["traffic_output_dir"]
    gdfs: list[gpd.GeoDataFrame] = []

    for period in TIME_PERIODS:
        fp = folder / f"{period}_{city_code}.gpkg"
        if not fp.exists():
            continue
        gdf = gpd.read_file(str(fp))
        gdf = compute_lisa(gdf, column=column, k=k)
        gdfs.append(gdf)

    n_seg = len(gdfs[0])
    n_per = len(gdfs)
    y = np.zeros((n_seg, n_per), dtype=int)
    for t, gdf in enumerate(gdfs):
        y[:, t] = gdf["lisa_cat"].map(LISA_CODE).values

    return y, gdfs


# ---------------------------------------------------------------------------
# Markov analysis
# ---------------------------------------------------------------------------


def classic_markov(y: np.ndarray) -> dict:
    """Fit a classic (non-spatial) Markov chain.

    Returns dict with ``transition_matrix``, ``steady_state``,
    and ``persistence`` (diagonal probabilities).
    """
    from giddy.markov import Markov

    m = Markov(y)
    p = m.p
    ss = m.steady_state

    return {
        "transition_matrix": p,
        "steady_state": ss,
        "persistence": {LISA_STATES[i]: float(p[i, i]) for i in range(len(LISA_STATES))},
    }


def spatial_markov(
    y: np.ndarray,
    gdf: gpd.GeoDataFrame,
    k: int = 8,
    permutations: int = 999,
) -> dict:
    """Fit a Spatial Markov model conditioned on neighbor states.

    Returns dict with ``chi2``, ``p_value``, ``dof``,
    ``significant`` (bool).
    """
    from giddy.markov import Spatial_Markov
    from libpysal.weights import KNN

    w = KNN.from_dataframe(gdf, k=k)
    w.transform = "r"

    sm = Spatial_Markov(y, w, permutations=permutations)

    chi2_val = float(sm.chi2.max()) if hasattr(sm.chi2, "max") else float(sm.chi2)
    p_val = float(sm.chi2.min()) if hasattr(sm, "shtest") else np.nan

    # Use the summary homogeneity test
    if hasattr(sm, "shtest"):
        tests = sm.shtest
        # shtest returns list of (chi2, p, dof) tuples per lag class
        max_chi2 = max(t[0] for t in tests)
        min_p = min(t[1] for t in tests)
        dof = tests[0][2] if tests else 0
        return {
            "chi2": float(max_chi2),
            "p_value": float(min_p),
            "dof": int(dof),
            "significant": float(min_p) < 0.05,
        }

    return {
        "chi2": chi2_val,
        "p_value": p_val,
        "dof": 0,
        "significant": False,
    }


# ---------------------------------------------------------------------------
# Persistence metrics
# ---------------------------------------------------------------------------


def persistence_statistics(y: np.ndarray) -> dict:
    """Compute segment-level persistence metrics.

    Returns dict mapping LISA states to {ever_pct, always_pct, avg_periods}.
    """
    n_seg, n_per = y.shape
    stats: dict[str, dict] = {}

    for code_idx, state in enumerate(LISA_STATES):
        mask = y == code_idx
        ever = mask.any(axis=1).sum()
        always = mask.all(axis=1).sum()
        avg = mask.sum(axis=1).mean()
        stats[state] = {
            "ever_pct": float(ever / n_seg * 100),
            "always_pct": float(always / n_seg * 100),
            "avg_periods": float(avg),
        }

    return stats


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def plot_transition_matrix(
    p: np.ndarray,
    city_name: str,
    figures_dir: str | Path = "figures",
) -> Path:
    """Heatmap of transition probability matrix."""
    fig_dir = Path(figures_dir) / "markov"
    fig_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(p, cmap="YlOrRd", vmin=0, vmax=1)
    ax.set_xticks(range(len(LISA_STATES)))
    ax.set_yticks(range(len(LISA_STATES)))
    ax.set_xticklabels(LISA_STATES)
    ax.set_yticklabels(LISA_STATES)
    ax.set_xlabel("To")
    ax.set_ylabel("From")
    ax.set_title(f"{city_name} — Transition Matrix", fontweight="bold")

    for i in range(len(LISA_STATES)):
        for j in range(len(LISA_STATES)):
            val = p[i, j]
            color = "white" if val > 0.5 else "black"
            ax.text(j, i, f"{val:.1%}", ha="center", va="center",
                    color=color, fontsize=10)

    fig.colorbar(im, ax=ax, shrink=0.8, label="Probability")
    plt.tight_layout()

    safe = city_name.lower().replace(" ", "_")
    fp = fig_dir / f"{safe}_transition_matrix.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


def plot_persistence_comparison(
    all_persistence: dict[str, dict],
    figures_dir: str | Path = "figures",
) -> Path:
    """Bar chart comparing persistence (diagonal) across cities."""
    fig_dir = Path(figures_dir) / "markov"
    fig_dir.mkdir(parents=True, exist_ok=True)

    states_to_plot = ["HH", "LL", "NS"]
    cities = list(all_persistence.keys())
    names = [CITIES[c]["name"] for c in cities]
    x = np.arange(len(cities))
    w = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = {"HH": "#e74c3c", "LL": "#3498db", "NS": "#95a5a6"}

    for i, state in enumerate(states_to_plot):
        vals = [all_persistence[c][state] * 100 for c in cities]
        bars = ax.bar(x + i * w, vals, w, label=f"P({state}→{state})",
                      color=colors[state], alpha=0.85)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                    f"{h:.1f}%", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x + w)
    ax.set_xticklabels(names)
    ax.set_ylabel("Persistence Probability (%)")
    ax.set_title("Hotspot Persistence Comparison", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    fp = fig_dir / "persistence_comparison.png"
    plt.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close()
    return fp


def plot_contagion_results(
    contagion: dict[str, dict],
    figures_dir: str | Path = "figures",
) -> Path:
    """Bar chart of spatial contagion chi² with significance markers."""
    fig_dir = Path(figures_dir) / "markov"
    fig_dir.mkdir(parents=True, exist_ok=True)

    cities = list(contagion.keys())
    names = [CITIES[c]["name"] for c in cities]
    chi2_vals = [contagion[c]["chi2"] for c in cities]
    p_vals = [contagion[c]["p_value"] for c in cities]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(names, chi2_vals, color=[CITIES[c]["color"] for c in cities],
                  alpha=0.85)

    for bar, pv in zip(bars, p_vals):
        h = bar.get_height()
        sig = "***" if pv < 0.001 else "**" if pv < 0.01 else "*" if pv < 0.05 else "ns"
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1,
                f"p={pv:.3f} {sig}", ha="center", va="bottom", fontsize=10)

    ax.set_ylabel("Chi-squared statistic")
    ax.set_title("Spatial Contagion Test", fontweight="bold")
    ax.axhline(y=3.84, ls="--", color="gray", alpha=0.5, label="χ² critical (p=0.05)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    fp = fig_dir / "spatial_contagion_test.png"
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
    """Run LISA Markov and Spatial Markov analysis for all cities."""
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    all_classic: dict[str, dict] = {}
    all_contagion: dict[str, dict] = {}
    all_persistence_diag: dict[str, dict] = {}
    summary_rows: list[dict] = []

    for code in CITIES:
        name = CITIES[code]["name"]
        print(f"\n{'=' * 50}")
        print(f"LISA Markov Analysis: {name}")
        print(f"{'=' * 50}")

        # Build LISA matrix
        print("  Computing LISA across time periods …")
        y, gdfs = build_lisa_matrix(code, base_dir)

        # Global Moran's I (evening peak)
        ep_idx = TIME_PERIODS.index("evening_peak")
        if ep_idx < len(gdfs):
            mi = compute_global_moran(gdfs[ep_idx])
            print(f"  Global Moran's I = {mi['morans_i']:.4f} "
                  f"(z={mi['z_score']:.2f}, p={mi['p_value']:.3f})")

        # Classic Markov
        print("  Fitting classic Markov chain …")
        cm = classic_markov(y)
        all_classic[code] = cm
        all_persistence_diag[code] = cm["persistence"]
        plot_transition_matrix(cm["transition_matrix"], name, figures_dir)

        diag = cm["persistence"]
        print(f"    P(HH→HH)={diag['HH']:.1%}  "
              f"P(LL→LL)={diag['LL']:.1%}  "
              f"P(NS→NS)={diag['NS']:.1%}")

        # Persistence statistics
        ps = persistence_statistics(y)
        print(f"    HH ever: {ps['HH']['ever_pct']:.1f}%  "
              f"always: {ps['HH']['always_pct']:.1f}%  "
              f"avg: {ps['HH']['avg_periods']:.1f} periods")

        # Spatial Markov
        print("  Fitting Spatial Markov model …")
        sm = spatial_markov(y, gdfs[0])
        all_contagion[code] = sm
        sig_str = "SIGNIFICANT" if sm["significant"] else "not significant"
        print(f"    χ²={sm['chi2']:.2f}  p={sm['p_value']:.3f}  ({sig_str})")

        summary_rows.append({
            "city": name,
            "n_segments": y.shape[0],
            "P_HH_HH": diag["HH"],
            "P_LL_LL": diag["LL"],
            "P_NS_NS": diag["NS"],
            "contagion_chi2": sm["chi2"],
            "contagion_p": sm["p_value"],
            "contagion_significant": sm["significant"],
            "morans_i": mi["morans_i"] if ep_idx < len(gdfs) else np.nan,
            "morans_p": mi["p_value"] if ep_idx < len(gdfs) else np.nan,
        })

    # Comparative figures
    plot_persistence_comparison(all_persistence_diag, figures_dir)
    plot_contagion_results(all_contagion, figures_dir)

    # Save summary CSV
    pd.DataFrame(summary_rows).to_csv(
        out_dir / "markov_analysis_results.csv", index=False
    )
    print("\nMarkov analysis complete.")
