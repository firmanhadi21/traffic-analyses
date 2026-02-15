#!/usr/bin/env python3
"""
Generate the two missing figures for the manuscript:
  - Figure 1: Analytical framework diagram
  - Figure 6: Street orientation polar histograms
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

# Set publication-quality defaults
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1
})

FIGURES_DIR = os.path.join(os.path.dirname(__file__), '..', 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)


def draw_box(ax, xy, width, height, text, color='#3498db', fontsize=9, text_color='white', alpha=1.0):
    """Draw a rounded box with centered text."""
    box = FancyBboxPatch(
        xy, width, height,
        boxstyle="round,pad=0.15",
        facecolor=color, edgecolor='#2c3e50',
        linewidth=1.5, alpha=alpha
    )
    ax.add_patch(box)
    cx = xy[0] + width / 2
    cy = xy[1] + height / 2
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fontsize, fontweight='bold', color=text_color,
            wrap=True)


def draw_arrow(ax, start, end, color='#2c3e50'):
    """Draw an arrow between two points."""
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle='->', mutation_scale=15,
        color=color, linewidth=1.5,
        connectionstyle='arc3,rad=0'
    )
    ax.add_patch(arrow)


def figure1_analytical_framework():
    """
    Figure 1: Analytical framework diagram.
    Shows the three-pillar methodology: temporal analysis, geostatistical methods,
    and network topology assessment.
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.5)
    ax.axis('off')

    # === Top row: Data Sources ===
    draw_box(ax, (1.5, 7.2), 3.5, 0.9, 'HERE Traffic API\n(Real-Time Traffic Data)',
             color='#2c3e50', fontsize=9)
    draw_box(ax, (7.0, 7.2), 3.5, 0.9, 'OpenStreetMap\n(Road Network Data)',
             color='#2c3e50', fontsize=9)

    # Arrows from data sources down
    draw_arrow(ax, (3.25, 7.2), (3.25, 6.55))
    draw_arrow(ax, (8.75, 7.2), (8.75, 6.55))

    # === Data processing row ===
    draw_box(ax, (0.5, 5.8), 5.5, 0.7, 'Data Collection & Preprocessing\n'
             '265M observations · 18,694 segments · 11 months',
             color='#7f8c8d', fontsize=8)
    draw_box(ax, (6.5, 5.8), 5.0, 0.7, 'Network Construction (OSMnx)\n'
             'Graph extraction · Edge/Node attributes',
             color='#7f8c8d', fontsize=8)

    # Arrows down from preprocessing
    draw_arrow(ax, (2.0, 5.8), (2.0, 5.2))
    draw_arrow(ax, (4.5, 5.8), (6.0, 5.2))
    draw_arrow(ax, (9.0, 5.8), (9.5, 5.2))

    # === Three pillars header ===
    # Pillar 1: Temporal Analysis
    draw_box(ax, (0.3, 4.4), 3.4, 0.7, '(1) Temporal Analysis',
             color='#e74c3c', fontsize=10)
    # Pillar 2: Geostatistical Analysis
    draw_box(ax, (4.3, 4.4), 3.4, 0.7, '(2) Geostatistical Analysis',
             color='#3498db', fontsize=10)
    # Pillar 3: Network Topology
    draw_box(ax, (8.3, 4.4), 3.4, 0.7, '(3) Network Topology',
             color='#2ecc71', fontsize=10)

    # === Pillar 1 sub-items ===
    items_p1 = [
        'Jam Factor by Period\n(8 temporal windows)',
        'Peak vs Off-Peak\nComparison',
        'Temporal Variability\n(CV Analysis)',
    ]
    for i, txt in enumerate(items_p1):
        y = 3.6 - i * 0.8
        draw_box(ax, (0.3, y), 3.4, 0.65, txt,
                 color='#e74c3c', fontsize=7.5, alpha=0.7)

    # === Pillar 2 sub-items ===
    items_p2 = [
        "Spatial Autocorrelation\n(Moran's I)",
        'Hotspot Detection\n(LISA Analysis)',
        'Congestion Clustering\n& Distribution',
    ]
    for i, txt in enumerate(items_p2):
        y = 3.6 - i * 0.8
        draw_box(ax, (4.3, y), 3.4, 0.65, txt,
                 color='#3498db', fontsize=7.5, alpha=0.7)

    # === Pillar 3 sub-items ===
    items_p3 = [
        'Betweenness &\nCloseness Centrality',
        'Street Orientation\n(Bearing Analysis)',
        'Network Efficiency\n& Connectivity',
    ]
    for i, txt in enumerate(items_p3):
        y = 3.6 - i * 0.8
        draw_box(ax, (8.3, y), 3.4, 0.65, txt,
                 color='#2ecc71', fontsize=7.5, alpha=0.7)

    # === Arrows to integration ===
    draw_arrow(ax, (2.0, 1.6), (4.5, 1.15))
    draw_arrow(ax, (6.0, 1.6), (6.0, 1.15))
    draw_arrow(ax, (10.0, 1.6), (7.5, 1.15))

    # === Integration / Output ===
    draw_box(ax, (3.0, 0.3), 6.0, 0.8,
             'Integrated Assessment\nComparative Analysis: Jakarta · Bandung · Semarang\n'
             'Policy Recommendations & Infrastructure Prioritization',
             color='#8e44ad', fontsize=8.5)

    # Title
    ax.text(6.0, 8.3, 'Figure 1. Analytical Framework',
            ha='center', va='center', fontsize=13, fontweight='bold',
            color='#2c3e50')

    plt.tight_layout()
    outpath = os.path.join(FIGURES_DIR, 'analytical_framework.png')
    plt.savefig(outpath, facecolor='white')
    plt.close()
    print(f"Generated: {outpath}")


def figure6_street_orientation():
    """
    Figure 6: Street orientation polar histograms for each city.
    Computes edge bearings from existing traffic GeoPackage files.
    Uses fiona directly to bypass the broken pyproj CRS in this env.
    """
    import fiona
    from shapely.geometry import shape
    import math

    CITIES = {
        'Semarang': {
            'code': 'smg',
            'color': '#2ecc71',
            'file': 'traffic_smg_output/morning_peak_smg.gpkg',
        },
        'Bandung': {
            'code': 'bdg',
            'color': '#3498db',
            'file': 'traffic_bdg_output/morning_peak_bdg.gpkg',
        },
        'Jakarta': {
            'code': 'jkt',
            'color': '#e74c3c',
            'file': 'traffic_jkt_output/morning_peak_jkt.gpkg',
        },
    }

    def bearing_from_coords(x1, y1, x2, y2):
        """Compute bearing (0-360, north=0, clockwise) from lon/lat pairs."""
        lat1, lat2 = math.radians(y1), math.radians(y2)
        dlon = math.radians(x2 - x1)
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        return bearing % 360

    def get_bearings_from_file(filepath):
        """Extract bearings from LineString geometries using fiona."""
        bearings = []
        with fiona.open(filepath) as src:
            for feat in src:
                geom = shape(feat['geometry'])
                if geom is None or geom.is_empty:
                    continue
                if geom.geom_type == 'MultiLineString':
                    lines = list(geom.geoms)
                elif geom.geom_type == 'LineString':
                    lines = [geom]
                else:
                    continue
                for line in lines:
                    coords = list(line.coords)
                    if len(coords) >= 2:
                        x1, y1 = coords[0][:2]
                        x2, y2 = coords[-1][:2]
                        b = bearing_from_coords(x1, y1, x2, y2)
                        bearings.append(b)
        return bearings

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), subplot_kw={'projection': 'polar'})

    for ax, (city, cfg) in zip(axes, CITIES.items()):
        filepath = cfg['file']
        print(f"  Loading {city} from {filepath}...")
        bearings = np.array(get_bearings_from_file(filepath))

        # Make bearings symmetric (undirected streets)
        bearings_sym = np.concatenate([bearings, (bearings + 180) % 360])

        n_bins = 36
        bins = np.linspace(0, 360, n_bins + 1)
        counts, _ = np.histogram(bearings_sym, bins=bins)

        # Convert to radians for polar plot
        angles = np.deg2rad((bins[:-1] + bins[1:]) / 2)
        width = np.deg2rad(360 / n_bins)

        ax.bar(angles, counts, width=width, color=cfg['color'],
               alpha=0.7, edgecolor='black', linewidth=0.5)
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_title(f'{city}', fontsize=12, fontweight='bold', pad=15)
        ax.set_yticklabels([])

    plt.suptitle('Street Orientation Polar Histograms', fontsize=14,
                 fontweight='bold', y=1.05)
    plt.tight_layout()
    outpath = os.path.join(FIGURES_DIR, 'street_orientation_polar.png')
    plt.savefig(outpath, facecolor='white')
    plt.close()
    print(f"Generated: {outpath}")


if __name__ == '__main__':
    print("Generating Figure 1: Analytical Framework...")
    figure1_analytical_framework()

    print("\nGenerating Figure 6: Street Orientation Polar Histograms...")
    figure6_street_orientation()

    print("\nDone! All figures saved to:", FIGURES_DIR)
