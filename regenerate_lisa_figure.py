#!/usr/bin/env python3
"""
Regenerate figures/jkt_lisa_clusters.png from the saved canonical LISA
classification (lisa_results/jkt_evening_peak_lisa.gpkg) without recomputing
the permutation inference, so cluster counts stay identical to the published
run.

Changes vs the original advanced_spatial_analysis.plot_lisa_map render:
- CVD-safe 'plasma' colormap for the jam-factor panel (was RdYlGn_r,
  a red-green ramp unreadable under deuteranopia/protanopia).
- Scale bar and north arrow on both map panels.
"""

import math
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt

FIGURES_DIR = Path("figures")
LISA_GPKG = Path("lisa_results/jkt_evening_peak_lisa.gpkg")
CITY_NAME = "Jakarta"

# Same cluster palette as advanced_spatial_analysis.plot_lisa_map
CLUSTER_COLORS = {'HH': '#d7191c', 'LL': '#2c7bb6', 'HL': '#fdae61',
                  'LH': '#abd9e9', 'NS': '#cccccc'}


def add_scalebar_and_north(ax, gdf_3857, bar_km=5):
    """Draw a ground-distance scale bar (bottom-left) and north arrow
    (top-right) in EPSG:3857 axis units."""
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    # Web-Mercator units are metres / cos(lat); correct to ground metres.
    lat = gdf_3857.to_crs(4326).geometry.union_all().centroid.y
    bar_len = bar_km * 1000 / math.cos(math.radians(lat))
    x0 = xmin + 0.05 * (xmax - xmin)
    y0 = ymin + 0.05 * (ymax - ymin)
    ax.plot([x0, x0 + bar_len], [y0, y0], color='black', lw=3,
            solid_capstyle='butt', zorder=10)
    ax.text(x0 + bar_len / 2, y0 + 0.012 * (ymax - ymin), f'{bar_km} km',
            ha='center', va='bottom', fontsize=9, zorder=10)
    xn = xmin + 0.95 * (xmax - xmin)
    yn = ymin + 0.90 * (ymax - ymin)
    ax.annotate('N', xy=(xn, yn + 0.05 * (ymax - ymin)), xytext=(xn, yn),
                ha='center', va='center', fontsize=12, fontweight='bold',
                arrowprops=dict(arrowstyle='-|>', color='black', lw=1.5),
                zorder=10)


def main():
    gdf = gpd.read_file(LISA_GPKG).to_crs(3857)
    counts = gdf['lisa_cluster'].value_counts().to_dict()
    print(f"Loaded {len(gdf)} segments; cluster counts: {counts}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Left: traffic intensity (CVD-safe sequential colormap)
    ax1 = axes[0]
    gdf.plot(column='jam_factor_mean', cmap='plasma', linewidth=0.8, ax=ax1,
             legend=True, legend_kwds={'label': 'Jam Factor', 'shrink': 0.7},
             alpha=0.85)
    ctx.add_basemap(ax1, source=ctx.providers.CartoDB.Positron, alpha=0.4)
    ax1.set_title(f'{CITY_NAME} - Traffic Intensity\n(Evening Peak)',
                  fontsize=12, fontweight='bold')
    ax1.set_axis_off()
    add_scalebar_and_north(ax1, gdf)

    # Right: LISA clusters (unchanged palette)
    ax2 = axes[1]
    for cluster_type, color in CLUSTER_COLORS.items():
        subset = gdf[gdf['lisa_cluster'] == cluster_type]
        if len(subset) > 0:
            a = 0.3 if cluster_type == 'NS' else 0.9
            subset.plot(ax=ax2, color=color, linewidth=0.8,
                        label=f'{cluster_type} ({len(subset)})', alpha=a)
    ctx.add_basemap(ax2, source=ctx.providers.CartoDB.Positron, alpha=0.4)
    ax2.set_title(f'{CITY_NAME} - LISA Clusters\n(p < 0.05)',
                  fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right', title='Cluster Type')
    ax2.set_axis_off()
    add_scalebar_and_north(ax2, gdf)

    plt.tight_layout()
    out = FIGURES_DIR / 'jkt_lisa_clusters.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
