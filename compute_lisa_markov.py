#!/usr/bin/env python3
"""
LISA Markov Analysis for Spatiotemporal Traffic Congestion Dynamics

This script performs space-time autocorrelation analysis using PySAL's giddy module.
It computes:
1. Classic Markov transition matrices for LISA categories
2. Spatial Markov analysis (transitions conditioned on spatial lag)
3. Chi-squared test for spatial heterogeneity in transitions
4. Steady-state distributions
5. Visualizations for FOSS4G paper

References:
- Rey, S.J. (2001) Spatial empirics for economic growth and convergence
- Anselin, L. (1995) Local Indicators of Spatial Association—LISA
"""

import os
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

try:
    from giddy.markov import Markov, Spatial_Markov
    from libpysal.weights import KNN
    GIDDY_AVAILABLE = True
except ImportError:
    GIDDY_AVAILABLE = False
    print("ERROR: giddy not installed. Install with:")
    print("  pip install giddy")
    sys.exit(1)

warnings.filterwarnings('ignore')

# Configuration
BASE_DIR = Path("/Users/macbook/Dropbox/GitHub/traffic-analyses")
LISA_DIR = BASE_DIR / "lisa_results"
OUTPUT_DIR = BASE_DIR / "markov_results"
FIGURES_DIR = BASE_DIR / "figures" / "markov"

CITIES = {
    'jkt': {'name': 'Jakarta', 'color': '#e41a1c'},
    'bdg': {'name': 'Bandung', 'color': '#377eb8'},
    'smg': {'name': 'Semarang', 'color': '#4daf4a'},
}

PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]

# LISA categories: encode as integers for Markov analysis
# 0=NS, 1=HH, 2=LL, 3=LH, 4=HL
LISA_ENCODING = {'NS': 0, 'HH': 1, 'LL': 2, 'LH': 3, 'HL': 4}
LISA_DECODING = {v: k for k, v in LISA_ENCODING.items()}
LISA_LABELS = ['NS', 'HH', 'LL', 'LH', 'HL']
LISA_COLORS = {'NS': '#eeeeee', 'HH': '#d7191c', 'LL': '#2c7bb6', 'LH': '#abd9e9', 'HL': '#fdae61'}

K_NEIGHBORS = 8


def load_lisa_timeseries(city_code: str) -> tuple:
    """
    Load LISA time series data for a city.

    Returns
    -------
    gdf : GeoDataFrame
        Combined LISA data
    y : ndarray
        LISA classifications as integer matrix (n_segments × n_periods)
    """
    filepath = LISA_DIR / f"{city_code}_combined_lisa.gpkg"

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    gdf = gpd.read_file(filepath)

    # Extract LISA columns and encode as integers
    lisa_cols = [f'lisa_{p}' for p in PERIODS]

    # Create integer-encoded matrix
    y = np.zeros((len(gdf), len(PERIODS)), dtype=int)
    for i, col in enumerate(lisa_cols):
        y[:, i] = gdf[col].map(LISA_ENCODING).values

    return gdf, y


def compute_classic_markov(y: np.ndarray, city_name: str) -> dict:
    """
    Compute classic (non-spatial) Markov transition matrix.

    Parameters
    ----------
    y : ndarray
        Integer-encoded LISA classifications (n × t)
    city_name : str
        City name for reporting

    Returns
    -------
    dict with Markov results
    """
    print(f"\n  Computing Classic Markov for {city_name}...")

    # giddy Markov expects classes starting from 1, but we use 0-4
    # It handles this automatically
    m = Markov(y)

    return {
        'transitions': m.transitions,  # Transition count matrix
        'p': m.p,                       # Transition probability matrix
        'steady_state': m.steady_state, # Steady-state distribution
        'classes': m.classes,           # Unique classes observed
    }


def compute_spatial_markov(y: np.ndarray, w, city_name: str) -> dict:
    """
    Compute Spatial Markov (transitions conditioned on spatial lag).

    Tests whether transition probabilities depend on neighbors' states.

    Parameters
    ----------
    y : ndarray
        Integer-encoded LISA classifications (n × t)
    w : libpysal weights
        Spatial weights matrix
    city_name : str
        City name for reporting

    Returns
    -------
    dict with Spatial Markov results
    """
    print(f"  Computing Spatial Markov for {city_name}...")

    # Spatial Markov with discrete lag classes
    sm = Spatial_Markov(y, w, fixed=True, k=5)  # k=5 lag classes

    return {
        'P': sm.P,                    # Transition matrices by lag class
        'S': sm.S,                    # Steady states by lag class
        'T': sm.T,                    # Transition counts by lag class
        'chi2': sm.chi2,              # Chi-squared test statistic
        'chi2_pvalue': sm.chi2_pvalue if hasattr(sm, 'chi2_pvalue') else None,
        'dof': sm.chi2_dof if hasattr(sm, 'chi2_dof') else None,
        'summary': None,  # sm.summary() has a bug with regime names
    }


def compute_persistence_metrics(y: np.ndarray) -> dict:
    """
    Compute persistence metrics for each LISA category.

    Returns
    -------
    dict with persistence statistics
    """
    n_segments, n_periods = y.shape

    metrics = {}

    for cat_code, cat_name in LISA_DECODING.items():
        # For each segment, count how many periods it's in this category
        cat_counts = np.sum(y == cat_code, axis=1)

        # Segments ever in this category
        ever_in_cat = np.sum(cat_counts > 0)

        # Segments always in this category
        always_in_cat = np.sum(cat_counts == n_periods)

        # Average periods in this category (for segments ever in it)
        if ever_in_cat > 0:
            avg_periods = np.mean(cat_counts[cat_counts > 0])
        else:
            avg_periods = 0

        metrics[cat_name] = {
            'ever': ever_in_cat,
            'always': always_in_cat,
            'avg_periods': avg_periods,
            'ever_pct': ever_in_cat / n_segments * 100,
            'always_pct': always_in_cat / n_segments * 100,
        }

    return metrics


def plot_transition_matrix(p: np.ndarray, city_name: str, output_path: Path):
    """Plot transition probability matrix as heatmap."""

    fig, ax = plt.subplots(figsize=(8, 6))

    # Create heatmap
    im = ax.imshow(p, cmap='YlOrRd', vmin=0, vmax=1)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Transition Probability', fontsize=11)

    # Set ticks and labels
    ax.set_xticks(range(len(LISA_LABELS)))
    ax.set_yticks(range(len(LISA_LABELS)))
    ax.set_xticklabels(LISA_LABELS, fontsize=11)
    ax.set_yticklabels(LISA_LABELS, fontsize=11)

    # Add text annotations
    for i in range(len(LISA_LABELS)):
        for j in range(len(LISA_LABELS)):
            value = p[i, j]
            color = 'white' if value > 0.5 else 'black'
            ax.text(j, i, f'{value:.2f}', ha='center', va='center',
                   color=color, fontsize=10, fontweight='bold')

    ax.set_xlabel('To State (t+1)', fontsize=12)
    ax.set_ylabel('From State (t)', fontsize=12)
    ax.set_title(f'{city_name}: LISA Transition Probabilities\n(Between Adjacent Time Periods)',
                fontsize=13, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"    Saved: {output_path.name}")


def plot_steady_state_comparison(results: dict, output_path: Path):
    """Plot steady-state distributions for all cities."""

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(LISA_LABELS))
    width = 0.25

    for i, (city_code, city_info) in enumerate(CITIES.items()):
        if city_code in results:
            ss = results[city_code]['classic']['steady_state']
            bars = ax.bar(x + i*width, ss, width, label=city_info['name'],
                         color=city_info['color'], alpha=0.8)

            # Add value labels
            for bar, val in zip(bars, ss):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                       f'{val:.1%}', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('LISA Category', fontsize=12)
    ax.set_ylabel('Steady-State Probability', fontsize=12)
    ax.set_title('Long-Run Equilibrium Distribution of LISA Categories\n(Derived from Markov Transition Matrices)',
                fontsize=13, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(LISA_LABELS, fontsize=11)
    ax.legend(title='City', fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_path.name}")


def plot_persistence_analysis(results: dict, output_path: Path):
    """Plot persistence analysis showing chronic vs episodic hotspots."""

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    for ax, (city_code, city_info) in zip(axes, CITIES.items()):
        if city_code not in results:
            continue

        metrics = results[city_code]['persistence']

        categories = ['HH', 'LL', 'HL', 'LH']
        ever_pcts = [metrics[c]['ever_pct'] for c in categories]
        always_pcts = [metrics[c]['always_pct'] for c in categories]

        x = np.arange(len(categories))
        width = 0.35

        bars1 = ax.bar(x - width/2, ever_pcts, width, label='Ever in category',
                      color='steelblue', alpha=0.7)
        bars2 = ax.bar(x + width/2, always_pcts, width, label='Always in category',
                      color='darkred', alpha=0.7)

        ax.set_xlabel('LISA Category', fontsize=11)
        ax.set_ylabel('% of Segments', fontsize=11)
        ax.set_title(f'{city_info["name"]}', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=10)
        ax.legend(fontsize=9)
        ax.set_ylim(0, max(ever_pcts) * 1.3)
        ax.grid(axis='y', alpha=0.3)

        # Add value labels
        for bar in bars1:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                   f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=8)
        for bar in bars2:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                   f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=8)

    fig.suptitle('Temporal Persistence of LISA Clusters: Chronic vs Episodic Patterns\n(Across 8 Daily Time Periods)',
                fontsize=13, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_path.name}")


def plot_diagonal_dominance(results: dict, output_path: Path):
    """Plot diagonal values (persistence probabilities) for each category."""

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(LISA_LABELS))
    width = 0.25

    for i, (city_code, city_info) in enumerate(CITIES.items()):
        if city_code in results:
            p = results[city_code]['classic']['p']
            diag = np.diag(p)
            bars = ax.bar(x + i*width, diag, width, label=city_info['name'],
                         color=city_info['color'], alpha=0.8)

    # Add reference line at 0.2 (random expectation for 5 categories)
    ax.axhline(y=0.2, color='gray', linestyle='--', linewidth=1, label='Random (1/5)')

    ax.set_xlabel('LISA Category', fontsize=12)
    ax.set_ylabel('P(Stay in Same Category)', fontsize=12)
    ax.set_title('Diagonal Dominance: Probability of Remaining in Same LISA Category\n(Higher = More Persistent Clusters)',
                fontsize=13, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(LISA_LABELS, fontsize=11)
    ax.legend(title='City', fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_path.name}")


def plot_spatial_contagion_test(results: dict, output_path: Path):
    """Plot spatial contagion test results (HH transition by neighbor context)."""

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    for ax, (city_code, city_info) in zip(axes, CITIES.items()):
        if city_code not in results or 'spatial' not in results[city_code]:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            continue

        sm_results = results[city_code]['spatial']
        P = sm_results['P']  # Transition matrices by lag class

        # Extract P(NS → HH) for different spatial lag classes
        # This shows: are segments near hotspots more likely to become hotspots?
        if P is not None and len(P) > 0:
            # P[k] is transition matrix for lag class k
            # We want P(from=NS=0, to=HH=1) for each lag class
            ns_to_hh = []
            lag_labels = []

            for k in range(len(P)):
                if P[k].shape[0] > 1 and P[k].shape[1] > 1:
                    # NS=0, HH=1
                    prob = P[k][0, 1] if P[k].shape[0] > 0 and P[k].shape[1] > 1 else 0
                    ns_to_hh.append(prob)
                    lag_labels.append(f'Lag {k+1}')

            if ns_to_hh:
                colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(ns_to_hh)))
                bars = ax.bar(range(len(ns_to_hh)), ns_to_hh, color=colors)
                ax.set_xticks(range(len(ns_to_hh)))
                ax.set_xticklabels(lag_labels, fontsize=9)
                ax.set_ylabel('P(NS → HH)', fontsize=11)

                # Add chi-squared result
                chi2 = sm_results.get('chi2', 'N/A')
                pval = sm_results.get('chi2_pvalue', 'N/A')
                if isinstance(chi2, (int, float)) and isinstance(pval, (int, float)):
                    sig = '***' if pval < 0.001 else '**' if pval < 0.01 else '*' if pval < 0.05 else ''
                    ax.text(0.95, 0.95, f'χ² = {chi2:.1f}{sig}\np = {pval:.4f}',
                           transform=ax.transAxes, ha='right', va='top', fontsize=9,
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        ax.set_title(f'{city_info["name"]}', fontsize=12, fontweight='bold')
        ax.set_xlabel('Spatial Lag Class\n(Low → High neighbor congestion)', fontsize=10)
        ax.grid(axis='y', alpha=0.3)

    fig.suptitle('Spatial Contagion Test: Does Neighbor Context Affect Hotspot Formation?\n'
                'P(NS → HH) by Spatial Lag Class',
                fontsize=13, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_path.name}")


def generate_report(results: dict, output_path: Path):
    """Generate text report with all results."""

    lines = []
    lines.append("=" * 70)
    lines.append("LISA MARKOV ANALYSIS REPORT")
    lines.append("Spatiotemporal Dynamics of Traffic Congestion Hotspots")
    lines.append("=" * 70)
    lines.append("")

    for city_code, city_info in CITIES.items():
        if city_code not in results:
            continue

        city_name = city_info['name']
        r = results[city_code]

        lines.append(f"\n{'='*50}")
        lines.append(f"{city_name.upper()}")
        lines.append(f"{'='*50}")

        # Classic Markov
        lines.append("\n1. CLASSIC MARKOV TRANSITIONS")
        lines.append("-" * 40)

        p = r['classic']['p']
        lines.append("\nTransition Probability Matrix:")
        lines.append(f"{'From/To':<8}" + "".join([f"{l:>8}" for l in LISA_LABELS]))
        for i, label in enumerate(LISA_LABELS):
            row = f"{label:<8}" + "".join([f"{p[i,j]:>8.3f}" for j in range(len(LISA_LABELS))])
            lines.append(row)

        # Steady state
        ss = r['classic']['steady_state']
        lines.append("\nSteady-State Distribution:")
        for i, label in enumerate(LISA_LABELS):
            lines.append(f"  {label}: {ss[i]:.1%}")

        # Diagonal dominance
        lines.append("\nDiagonal Dominance (Persistence Probability):")
        for i, label in enumerate(LISA_LABELS):
            lines.append(f"  P({label} → {label}): {p[i,i]:.1%}")

        # Persistence metrics
        lines.append("\n2. PERSISTENCE ANALYSIS")
        lines.append("-" * 40)

        metrics = r['persistence']
        lines.append(f"\n{'Category':<10} {'Ever (%)':<12} {'Always (%)':<12} {'Avg Periods':<12}")
        for cat in ['HH', 'LL', 'HL', 'LH', 'NS']:
            m = metrics[cat]
            lines.append(f"{cat:<10} {m['ever_pct']:<12.1f} {m['always_pct']:<12.1f} {m['avg_periods']:<12.1f}")

        # Spatial Markov
        if 'spatial' in r and r['spatial'].get('chi2') is not None:
            lines.append("\n3. SPATIAL MARKOV (Contagion Test)")
            lines.append("-" * 40)

            sm = r['spatial']
            chi2 = sm['chi2']
            pval = sm.get('chi2_pvalue', 'N/A')

            lines.append(f"\nChi-squared test for spatial homogeneity:")
            lines.append(f"  H0: Transition probabilities do not depend on neighbors' states")

            # Helper to extract scalar from nested sequences
            def get_scalar(val):
                while hasattr(val, '__getitem__') and not isinstance(val, (str, np.ndarray)):
                    try:
                        val = val[0]
                    except (IndexError, KeyError):
                        break
                if isinstance(val, np.ndarray):
                    val = val.flat[0] if val.size > 0 else 0.0
                return float(val) if val is not None else 0.0

            chi2_val = get_scalar(chi2)
            lines.append(f"  χ² = {chi2_val:.2f}")
            pval_val = get_scalar(pval) if pval is not None else None
            if isinstance(pval_val, (int, float)) and not np.isnan(pval_val):
                lines.append(f"  p-value = {pval_val:.6f}")
                if pval_val < 0.001:
                    lines.append("  Result: REJECT H0 (p < 0.001) - Strong evidence for spatial contagion")
                elif pval_val < 0.05:
                    lines.append("  Result: REJECT H0 (p < 0.05) - Evidence for spatial contagion")
                else:
                    lines.append("  Result: FAIL TO REJECT H0 - No significant spatial contagion")

    lines.append("\n" + "=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Saved: {output_path.name}")

    # Also print to console
    print('\n'.join(lines))


def save_results_csv(results: dict, output_dir: Path):
    """Save key results to CSV files."""

    # Transition matrices
    for city_code in CITIES:
        if city_code not in results:
            continue

        p = results[city_code]['classic']['p']
        df = pd.DataFrame(p, index=LISA_LABELS, columns=LISA_LABELS)
        df.to_csv(output_dir / f"{city_code}_transition_matrix.csv")

    # Summary statistics
    summary_rows = []
    for city_code, city_info in CITIES.items():
        if city_code not in results:
            continue

        r = results[city_code]
        p = r['classic']['p']
        ss = r['classic']['steady_state']

        row = {
            'city': city_code,
            'city_name': city_info['name'],
            'p_HH_HH': p[1, 1],  # P(HH → HH)
            'p_NS_HH': p[0, 1],  # P(NS → HH)
            'p_HH_NS': p[1, 0],  # P(HH → NS)
            'ss_NS': ss[0],
            'ss_HH': ss[1],
            'ss_LL': ss[2],
            'ss_LH': ss[3],
            'ss_HL': ss[4],
        }

        if 'spatial' in r and r['spatial'].get('chi2') is not None:
            row['spatial_chi2'] = r['spatial']['chi2']
            row['spatial_pvalue'] = r['spatial'].get('chi2_pvalue', None)

        summary_rows.append(row)

    pd.DataFrame(summary_rows).to_csv(output_dir / "markov_summary.csv", index=False)
    print(f"  Saved: markov_summary.csv")


def main():
    """Main function to run all analyses."""

    print("=" * 60)
    print("LISA MARKOV ANALYSIS")
    print("Spatiotemporal Dynamics of Traffic Congestion")
    print("=" * 60)

    # Create output directories
    OUTPUT_DIR.mkdir(exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    for city_code, city_info in CITIES.items():
        city_name = city_info['name']
        print(f"\n{'='*50}")
        print(f"Processing {city_name}")
        print(f"{'='*50}")

        try:
            # Load data
            gdf, y = load_lisa_timeseries(city_code)
            print(f"  Loaded {len(gdf)} segments × {y.shape[1]} periods")

            # Create spatial weights
            gdf_centroids = gdf.copy()
            gdf_centroids['geometry'] = gdf_centroids.geometry.centroid
            w = KNN.from_dataframe(gdf_centroids, k=K_NEIGHBORS)
            w.transform = 'r'

            # Compute analyses
            classic_results = compute_classic_markov(y, city_name)
            spatial_results = compute_spatial_markov(y, w, city_name)
            persistence = compute_persistence_metrics(y)

            results[city_code] = {
                'classic': classic_results,
                'spatial': spatial_results,
                'persistence': persistence,
                'n_segments': len(gdf),
                'n_periods': y.shape[1],
            }

            # Plot transition matrix
            plot_transition_matrix(
                classic_results['p'],
                city_name,
                FIGURES_DIR / f"{city_code}_transition_matrix.png"
            )

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Generate comparative plots
    print(f"\n{'='*50}")
    print("Generating Comparative Figures")
    print(f"{'='*50}")

    plot_steady_state_comparison(results, FIGURES_DIR / "steady_state_comparison.png")
    plot_persistence_analysis(results, FIGURES_DIR / "persistence_analysis.png")
    plot_diagonal_dominance(results, FIGURES_DIR / "diagonal_dominance.png")
    plot_spatial_contagion_test(results, FIGURES_DIR / "spatial_contagion_test.png")

    # Save results
    print(f"\n{'='*50}")
    print("Saving Results")
    print(f"{'='*50}")

    save_results_csv(results, OUTPUT_DIR)
    generate_report(results, OUTPUT_DIR / "markov_analysis_report.txt")

    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE!")
    print(f"{'='*60}")
    print(f"\nResults saved to: {OUTPUT_DIR}")
    print(f"Figures saved to: {FIGURES_DIR}")
    print("\nKey files for FOSS4G paper:")
    print("  - figures/markov/steady_state_comparison.png")
    print("  - figures/markov/diagonal_dominance.png")
    print("  - figures/markov/spatial_contagion_test.png")
    print("  - markov_results/markov_analysis_report.txt")


if __name__ == "__main__":
    main()
