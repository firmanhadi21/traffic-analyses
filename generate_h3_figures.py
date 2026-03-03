#!/usr/bin/env python3
"""
H3 Robustness Check — Figure Generation
=========================================
Produces three publication figures for the H3 robustness check section.

Figure 1: h3_congestion_maps.png
    3-panel choropleth of hex-level jam_factor_mean at resolution 8,
    one panel per city. Shows spatial pattern of congestion at
    neighbourhood scale.

Figure 2: h3_morans_scale.png
    Grouped bar chart comparing Global Moran's I at three spatial scales:
    road segment, H3 resolution 9 (~174 m), H3 resolution 8 (~461 m).
    Asterisks mark statistically significant values (p < 0.05).
    Key result: Jakarta's autocorrelation emerges only at hex scale.

Figure 3: h3_correlation_panels.png
    2 × 3 grid of scatter plots: POI count (top row) and network
    centrality (bottom row) vs hex-level jam factor, one column per city.
    Regression line, Pearson r, and Spearman rho annotated per panel.
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.patches as mpatches
from scipy import stats
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path("analysis_results")
FIGURES_DIR  = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# ── City config ───────────────────────────────────────────────────────────────
CITIES = {
    'smg': {'name': 'Semarang', 'color': '#2ecc71'},
    'bdg': {'name': 'Bandung',  'color': '#3498db'},
    'jkt': {'name': 'Jakarta',  'color': '#e74c3c'},
}
CITY_ORDER = ['smg', 'bdg', 'jkt']

# Segment-level Moran's I benchmarks from existing analysis
SEGMENT_MORANS = {
    'Semarang': {'I': -0.0039, 'p': 0.837},
    'Bandung':  {'I':  0.0075, 'p': 0.353},
    'Jakarta':  {'I':  0.0026, 'p': 0.492},
}

# Matplotlib style
plt.rcParams.update({
    'font.family':       'sans-serif',
    'font.size':         10,
    'axes.titlesize':    11,
    'axes.labelsize':    10,
    'xtick.labelsize':   9,
    'ytick.labelsize':   9,
    'legend.fontsize':   9,
    'figure.dpi':        150,
    'savefig.dpi':       300,
    'savefig.bbox':      'tight',
    'savefig.facecolor': 'white',
})


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: H3 Congestion Choropleth Maps (resolution 8, all cities)
# ─────────────────────────────────────────────────────────────────────────────

def figure1_congestion_maps():
    print("  Generating Figure 1: H3 congestion maps (OSM basemap)...")
    import contextily as ctx

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))

    # Load all GDFs and reproject to Web Mercator for contextily
    all_vals = []
    gdfs = {}
    for code in CITY_ORDER:
        gdf = gpd.read_file(RESULTS_DIR / f"h3_r8_{code}.gpkg")
        gdf = gdf.to_crs("EPSG:3857")
        gdfs[code] = gdf
        all_vals.extend(gdf['jam_factor_mean'].dropna().tolist())

    # Shared colormap — semi-transparent hexagons over basemap
    vmin, vmax = np.percentile(all_vals, 2), np.percentile(all_vals, 98)
    cmap = plt.cm.RdYlGn_r
    norm = Normalize(vmin=vmin, vmax=vmax)

    for ax, code in zip(axes, CITY_ORDER):
        gdf  = gdfs[code]
        city = CITIES[code]

        # H3 hex overlay: filled with alpha, thin white edge
        gdf.plot(
            column='jam_factor_mean',
            cmap=cmap,
            norm=norm,
            ax=ax,
            alpha=0.55,           # transparent so basemap shows through
            edgecolor='white',
            linewidth=0.2,
            missing_kwds={'color': '#cccccc', 'alpha': 0.3},
            zorder=2,
        )

        # OSM basemap
        ctx.add_basemap(
            ax,
            crs="EPSG:3857",
            source=ctx.providers.OpenStreetMap.Mapnik,
            zoom='auto',
            attribution_size=6,
            zorder=1,
        )

        ax.set_title(city['name'], fontweight='bold', pad=6)
        ax.set_axis_off()

        # Hexagon count annotation
        ax.text(
            0.02, 0.02,
            f"n = {len(gdf):,} hexagons\n(~461 m diameter)",
            transform=ax.transAxes,
            fontsize=8,
            va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85),
            zorder=3,
        )

    # Shared colorbar
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, orientation='vertical',
                        fraction=0.015, pad=0.01, shrink=0.85)
    cbar.set_label('Jam Factor (mean, observation-weighted)', labelpad=8)
    cbar.ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))

    fig.suptitle(
        'Neighbourhood-Scale Congestion Distribution — H3 Resolution 8 (~461 m)',
        fontsize=12, fontweight='bold', y=1.01,
    )

    out = FIGURES_DIR / 'h3_congestion_maps.png'
    fig.savefig(out)
    plt.close(fig)
    print(f"    Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Moran's I Scale Comparison
# ─────────────────────────────────────────────────────────────────────────────

def figure2_morans_scale():
    print("  Generating Figure 2: Moran's I scale comparison...")

    # Load H3 results
    df = pd.read_csv(RESULTS_DIR / 'h3_robustness_results.csv')

    fig, ax = plt.subplots(figsize=(8, 5))

    city_names  = ['Semarang', 'Bandung', 'Jakarta']
    n_cities    = len(city_names)
    scales      = ['Segment\n(road level)', 'H3 Res 9\n(~174 m)', 'H3 Res 8\n(~461 m)']
    bar_width   = 0.22
    x           = np.arange(n_cities)

    colors = ['#95a5a6', '#85c1e9', '#2e86c1']  # light → dark for segment → res9 → res8

    # Collect Moran's I values and p-values for each scale
    seg_I   = [SEGMENT_MORANS[c]['I'] for c in city_names]
    seg_p   = [SEGMENT_MORANS[c]['p'] for c in city_names]

    res9_I, res9_p = [], []
    res8_I, res8_p = [], []
    for city in city_names:
        r9 = df[(df['city'] == city) & (df['resolution'] == 9)].iloc[0]
        r8 = df[(df['city'] == city) & (df['resolution'] == 8)].iloc[0]
        res9_I.append(r9['morans_I']); res9_p.append(r9['morans_p'])
        res8_I.append(r8['morans_I']); res8_p.append(r8['morans_p'])

    all_scales = [
        (seg_I,  seg_p,  colors[0], scales[0], -bar_width),
        (res9_I, res9_p, colors[1], scales[1],  0),
        (res8_I, res8_p, colors[2], scales[2],  bar_width),
    ]

    for I_vals, p_vals, color, label, offset in all_scales:
        bars = ax.bar(
            x + offset, I_vals,
            width=bar_width,
            color=color,
            edgecolor='white',
            linewidth=0.6,
            label=label,
            zorder=3,
        )
        # Significance markers
        for i, (bar, p) in enumerate(zip(bars, p_vals)):
            if p < 0.05:
                ht = bar.get_height()
                ypos = ht + 0.001 if ht >= 0 else ht - 0.003
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    ypos,
                    '*',
                    ha='center', va='bottom' if ht >= 0 else 'top',
                    fontsize=13, color='#c0392b', fontweight='bold',
                )

    # Zero line
    ax.axhline(0, color='black', linewidth=0.8, zorder=2)

    # Significance threshold annotation box
    ax.text(
        0.98, 0.97,
        '* p < 0.05',
        transform=ax.transAxes,
        ha='right', va='top', fontsize=9,
        color='#c0392b',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdfefe',
                  edgecolor='#c0392b', alpha=0.9),
    )

    ax.set_xticks(x)
    ax.set_xticklabels(city_names)
    ax.set_ylabel("Global Moran's I")
    ax.set_title(
        "Global Moran's I by Spatial Scale\n"
        "Segment level vs. H3 Hexagonal Aggregation",
        fontweight='bold',
    )
    ax.legend(title='Spatial unit', loc='upper left', framealpha=0.9)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.3f'))
    ax.grid(axis='y', alpha=0.3, zorder=1)
    ax.set_ylim(
        min(min(seg_I), min(res9_I), min(res8_I)) - 0.015,
        max(max(seg_I), max(res9_I), max(res8_I)) + 0.020,
    )

    out = FIGURES_DIR / 'h3_morans_scale.png'
    fig.savefig(out)
    plt.close(fig)
    print(f"    Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Correlation Scatter Panels (POI & Centrality vs JF, Res 8)
# ─────────────────────────────────────────────────────────────────────────────

def figure3_correlation_panels():
    print("  Generating Figure 3: H3 correlation scatter panels...")

    fig, axes = plt.subplots(
        2, 3,
        figsize=(14, 8),
        sharex='col',
    )

    row_labels = ['POI Density\n(count per hexagon)', 'Network Centrality\n(mean betweenness)']
    x_cols     = ['poi_count', 'centrality_mean']

    for col, code in enumerate(CITY_ORDER):
        city = CITIES[code]
        color = city['color']
        gdf  = gpd.read_file(RESULTS_DIR / f"h3_r8_{code}.gpkg")

        jf = gdf['jam_factor_mean'].values

        for row, (x_col, row_label) in enumerate(zip(x_cols, row_labels)):
            ax  = axes[row, col]
            x   = gdf[x_col].values
            mask = ~(np.isnan(x) | np.isnan(jf))
            xv, yv = x[mask], jf[mask]

            ax.scatter(xv, yv, alpha=0.35, s=12, color=color,
                       edgecolors='none', rasterized=True)

            # Regression line
            if len(xv) > 5:
                slope, intercept, r, p, _ = stats.linregress(xv, yv)
                rho, rho_p = stats.spearmanr(xv, yv)
                x_line = np.linspace(xv.min(), xv.max(), 200)
                ax.plot(x_line, slope * x_line + intercept,
                        color='#2c3e50', linewidth=1.5, linestyle='--', zorder=5)

                # Stats annotation
                sig_r   = '*' if p     < 0.05 else ''
                sig_rho = '*' if rho_p < 0.05 else ''
                ax.text(
                    0.97, 0.97,
                    f"r = {r:+.3f}{sig_r}\nρ = {rho:+.3f}{sig_rho}\nn = {mask.sum():,}",
                    transform=ax.transAxes,
                    ha='right', va='top', fontsize=8.5,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85),
                )
            else:
                ax.text(0.5, 0.5, 'Insufficient data',
                        transform=ax.transAxes, ha='center', va='center',
                        color='grey', fontsize=9)

            # Labels
            if row == 0:
                ax.set_title(city['name'], fontweight='bold', pad=6)
            if col == 0:
                ax.set_ylabel(row_label, fontsize=9)
            if row == 1:
                ax.set_xlabel('Predictor value', fontsize=9)

            ax.grid(True, alpha=0.25, linewidth=0.5)
            ax.tick_params(labelsize=8)

    fig.suptitle(
        'H3 Hex-Level Correlations — Resolution 8 (~461 m)\n'
        'POI Density and Network Centrality vs. Mean Jam Factor',
        fontsize=11, fontweight='bold', y=1.01,
    )

    # Legend for significance
    fig.text(
        0.99, 0.01,
        '* p < 0.05',
        ha='right', va='bottom', fontsize=8.5, color='#2c3e50',
        style='italic',
    )

    plt.tight_layout()
    out = FIGURES_DIR / 'h3_correlation_panels.png'
    fig.savefig(out)
    plt.close(fig)
    print(f"    Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4: Segment vs Hex correlation comparison (summary bar chart)
# ─────────────────────────────────────────────────────────────────────────────

def figure4_correlation_comparison():
    print("  Generating Figure 4: Segment vs. hex correlation comparison...")

    # Segment-level Spearman rho benchmarks
    seg_poi  = {'Semarang': -0.007, 'Bandung': -0.013, 'Jakarta': -0.0005}
    seg_cent = {'Semarang': -0.011, 'Bandung':  0.012, 'Jakarta':  0.002}

    df = pd.read_csv(RESULTS_DIR / 'h3_robustness_results.csv')
    city_names = ['Semarang', 'Bandung', 'Jakarta']

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    bar_width = 0.25
    x = np.arange(len(city_names))

    panel_data = [
        # (ax, title, seg_dict, res8_col, res9_col)
        (axes[0], 'POI Density',      seg_poi,  'poi_spearman_r',  'poi_spearman_p'),
        (axes[1], 'Network Centrality', seg_cent, 'cent_spearman_r', 'cent_spearman_p'),
    ]

    colors_scale = {
        'Segment\n(road level)': '#bdc3c7',
        'H3 Res 9\n(~174 m)':    '#85c1e9',
        'H3 Res 8\n(~461 m)':    '#2e86c1',
    }

    for ax, title, seg_dict, rho_col, p_col in panel_data:
        seg_vals = [seg_dict[c] for c in city_names]

        res8 = df[df['resolution'] == 8].set_index('city')
        res9 = df[df['resolution'] == 9].set_index('city')
        res8_rho = [res8.loc[c, rho_col] for c in city_names]
        res9_rho = [res9.loc[c, rho_col] for c in city_names]
        res8_p   = [res8.loc[c, p_col]   for c in city_names]
        res9_p   = [res9.loc[c, p_col]   for c in city_names]

        scale_data = [
            (seg_vals,  [1.0]*3,  colors_scale['Segment\n(road level)'],  'Segment\n(road level)',  -bar_width),
            (res9_rho,  res9_p,   colors_scale['H3 Res 9\n(~174 m)'],     'H3 Res 9\n(~174 m)',    0),
            (res8_rho,  res8_p,   colors_scale['H3 Res 8\n(~461 m)'],     'H3 Res 8\n(~461 m)',    bar_width),
        ]

        for rho_vals, p_vals, color, label, offset in scale_data:
            bars = ax.bar(
                x + offset, rho_vals,
                width=bar_width,
                color=color,
                edgecolor='white',
                linewidth=0.5,
                label=label,
                zorder=3,
            )
            # Mark significant bars (not applicable at segment level since p not stored)
            for bar, p in zip(bars, p_vals):
                if p < 0.05:
                    ht = bar.get_height()
                    ypos = ht + 0.001 if ht >= 0 else ht - 0.003
                    ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                            '*', ha='center', fontsize=13,
                            color='#c0392b', fontweight='bold',
                            va='bottom' if ht >= 0 else 'top')

        ax.axhline(0, color='black', linewidth=0.8, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(city_names)
        ax.set_title(title, fontweight='bold', pad=6)
        ax.set_ylabel("Spearman ρ" if ax == axes[0] else "")
        ax.grid(axis='y', alpha=0.3, zorder=1)
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.3f'))

        # Practical significance band
        ax.axhspan(-0.1, 0.1, alpha=0.06, color='grey', zorder=0, label='|ρ| < 0.1\n(negligible)')

    axes[0].legend(loc='upper right', fontsize=8.5, framealpha=0.9,
                   title='Spatial unit')
    axes[1].legend(loc='upper right', fontsize=8.5, framealpha=0.9)

    fig.suptitle(
        'Spearman ρ: Segment Level vs. H3 Hexagonal Aggregation\n'
        'Null result persists across all spatial scales (* p < 0.05)',
        fontsize=11, fontweight='bold',
    )

    plt.tight_layout()
    out = FIGURES_DIR / 'h3_correlation_comparison.png'
    fig.savefig(out)
    plt.close(fig)
    print(f"    Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("H3 FIGURE GENERATION")
    print("=" * 60)

    figure1_congestion_maps()
    figure2_morans_scale()
    figure3_correlation_panels()
    figure4_correlation_comparison()

    print("\nAll figures saved to:", FIGURES_DIR)
    print("=" * 60)
    print("Files produced:")
    for f in ['h3_congestion_maps.png', 'h3_morans_scale.png',
              'h3_correlation_panels.png', 'h3_correlation_comparison.png']:
        path = FIGURES_DIR / f
        size = path.stat().st_size / 1024 if path.exists() else 0
        print(f"  {f}  ({size:.0f} KB)")


if __name__ == "__main__":
    main()
