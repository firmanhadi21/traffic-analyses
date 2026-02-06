#!/usr/bin/env python3
"""
Generate publication-quality figures for the research article.
Spatiotemporal Analysis of Urban Traffic Congestion in Indonesian Cities
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import os

# Set publication-quality defaults
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1
})

# Create output directory
os.makedirs('paper/figures', exist_ok=True)

# City configurations
CITIES = {
    'Jakarta': {
        'code': 'jkt',
        'color': '#e74c3c',
        'population': 10.5,
        'segments': 14549
    },
    'Bandung': {
        'code': 'bdg',
        'color': '#3498db',
        'population': 2.5,
        'segments': 3069
    },
    'Semarang': {
        'code': 'smg',
        'color': '#2ecc71',
        'population': 1.8,
        'segments': 1076
    }
}

# Temporal periods
PERIODS = [
    ('night', 'Night\n(00-06)'),
    ('morning_peak', 'Morning\nPeak\n(06-09)'),
    ('morning_offpeak', 'Morning\nOff-Peak\n(09-12)'),
    ('lunch_hours', 'Lunch\n(12-14)'),
    ('afternoon_offpeak', 'Afternoon\nOff-Peak\n(14-17)'),
    ('evening_peak', 'Evening\nPeak\n(17-20)'),
    ('evening_offpeak', 'Evening\nOff-Peak\n(20-22)'),
    ('late_night', 'Late Night\n(22-24)')
]


def load_traffic_data():
    """Load traffic data for all cities and periods."""
    data = {}
    for city, config in CITIES.items():
        code = config['code']
        city_data = {}
        for period, _ in PERIODS:
            filepath = f'traffic_{code}_output/{period}_{code}.gpkg'
            if os.path.exists(filepath):
                gdf = gpd.read_file(filepath)
                city_data[period] = gdf
        data[city] = city_data
    return data


def figure1_temporal_patterns(data):
    """
    Figure 1: Mean jam factor by temporal period across three cities.
    Bar chart comparing congestion patterns.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(PERIODS))
    width = 0.25

    for i, (city, config) in enumerate(CITIES.items()):
        means = []
        for period, _ in PERIODS:
            if period in data[city]:
                means.append(data[city][period]['jam_factor_mean'].mean())
            else:
                means.append(np.nan)

        bars = ax.bar(x + i * width, means, width,
                      label=city, color=config['color'],
                      edgecolor='black', linewidth=0.5)

    ax.set_xlabel('Time Period')
    ax.set_ylabel('Mean Jam Factor')
    ax.set_title('Mean Jam Factor by Temporal Period')
    ax.set_xticks(x + width)
    ax.set_xticklabels([label for _, label in PERIODS], fontsize=8)
    ax.legend(loc='upper left')
    ax.set_ylim(0, 6)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('paper/figures/fig1_temporal_patterns.png')
    plt.savefig('paper/figures/fig1_temporal_patterns.pdf')
    plt.close()
    print("Generated: Figure 1 - Temporal patterns")


def figure2_traffic_maps(data):
    """
    Figure 2: Traffic congestion maps for evening peak period.
    Three-panel figure showing spatial distribution.
    """
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    for ax, (city, config) in zip(axes, CITIES.items()):
        if 'evening_peak' in data[city]:
            gdf = data[city]['evening_peak']
            gdf.plot(column='jam_factor_mean', cmap='RdYlGn_r',
                    linewidth=0.5, ax=ax, legend=False,
                    vmin=0, vmax=8)

            ax.set_title(f'{city}\n(n = {len(gdf):,} segments)')
            ax.set_axis_off()

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap='RdYlGn_r',
                                norm=plt.Normalize(vmin=0, vmax=8))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, orientation='horizontal',
                        fraction=0.05, pad=0.08, aspect=40)
    cbar.set_label('Jam Factor (Evening Peak)')

    plt.suptitle('Spatial Distribution of Traffic Congestion (Evening Peak Period)',
                 fontsize=12, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('paper/figures/fig2_traffic_maps.png')
    plt.savefig('paper/figures/fig2_traffic_maps.pdf')
    plt.close()
    print("Generated: Figure 2 - Traffic maps")


def figure3_congestion_distribution(data):
    """
    Figure 3: Distribution of jam factors (histogram/KDE).
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    for city, config in CITIES.items():
        if 'evening_peak' in data[city]:
            values = data[city]['evening_peak']['jam_factor_mean'].dropna()
            ax.hist(values, bins=50, alpha=0.5, density=True,
                   label=city, color=config['color'], edgecolor='black', linewidth=0.3)

    ax.set_xlabel('Jam Factor')
    ax.set_ylabel('Density')
    ax.set_title('Distribution of Jam Factors (Evening Peak)')
    ax.legend()
    ax.set_xlim(0, 10)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig('paper/figures/fig3_distribution.png')
    plt.savefig('paper/figures/fig3_distribution.pdf')
    plt.close()
    print("Generated: Figure 3 - Congestion distribution")


def figure4_cv_analysis(data):
    """
    Figure 4: Coefficient of variation analysis.
    """
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    for ax, (city, config) in zip(axes, CITIES.items()):
        if 'evening_peak' in data[city]:
            gdf = data[city]['evening_peak']
            if 'jam_factor_std' in gdf.columns and 'jam_factor_mean' in gdf.columns:
                gdf = gdf.copy()
                gdf['cv'] = (gdf['jam_factor_std'] / gdf['jam_factor_mean'] * 100).replace([np.inf, -np.inf], np.nan)
                gdf = gdf.dropna(subset=['cv'])

                gdf.plot(column='cv', cmap='viridis', linewidth=0.5, ax=ax,
                        legend=False, vmin=0, vmax=100)

            ax.set_title(f'{city}')
            ax.set_axis_off()

    sm = plt.cm.ScalarMappable(cmap='viridis',
                                norm=plt.Normalize(vmin=0, vmax=100))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, orientation='horizontal',
                        fraction=0.05, pad=0.08, aspect=40)
    cbar.set_label('Coefficient of Variation (%)')

    plt.suptitle('Temporal Variability of Congestion (CV)',
                 fontsize=12, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('paper/figures/fig4_cv_analysis.png')
    plt.savefig('paper/figures/fig4_cv_analysis.pdf')
    plt.close()
    print("Generated: Figure 4 - CV analysis")


def figure5_comparative_stats(data):
    """
    Figure 5: Comparative statistics across cities.
    """
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    # Panel A: Mean jam factor by city
    ax = axes[0, 0]
    cities = list(CITIES.keys())
    means = []
    stds = []
    colors = [CITIES[c]['color'] for c in cities]

    for city in cities:
        if 'evening_peak' in data[city]:
            mean = data[city]['evening_peak']['jam_factor_mean'].mean()
            std = data[city]['evening_peak']['jam_factor_mean'].std()
            means.append(mean)
            stds.append(std)

    bars = ax.bar(cities, means, yerr=stds, capsize=5, color=colors,
                  edgecolor='black', linewidth=0.5)
    ax.set_ylabel('Mean Jam Factor')
    ax.set_title('(a) Mean Congestion Level')
    ax.set_ylim(0, 6)

    # Panel B: Segments with high congestion
    ax = axes[0, 1]
    high_congestion = []
    for city in cities:
        if 'evening_peak' in data[city]:
            gdf = data[city]['evening_peak']
            pct = (gdf['jam_factor_mean'] > 5).sum() / len(gdf) * 100
            high_congestion.append(pct)

    ax.bar(cities, high_congestion, color=colors, edgecolor='black', linewidth=0.5)
    ax.set_ylabel('Percentage (%)')
    ax.set_title('(b) Segments with Jam Factor > 5')

    # Panel C: Population vs congestion
    ax = axes[1, 0]
    populations = [CITIES[c]['population'] for c in cities]
    ax.scatter(populations, means, s=100, c=colors, edgecolor='black', linewidth=1)
    for i, city in enumerate(cities):
        ax.annotate(city, (populations[i], means[i]),
                   xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel('Population (million)')
    ax.set_ylabel('Mean Jam Factor')
    ax.set_title('(c) Population vs Congestion')

    # Panel D: Segments count
    ax = axes[1, 1]
    segments = [CITIES[c]['segments'] for c in cities]
    ax.bar(cities, segments, color=colors, edgecolor='black', linewidth=0.5)
    ax.set_ylabel('Number of Segments')
    ax.set_title('(d) Traffic Monitoring Coverage')
    ax.ticklabel_format(style='plain', axis='y')

    plt.tight_layout()
    plt.savefig('paper/figures/fig5_comparative_stats.png')
    plt.savefig('paper/figures/fig5_comparative_stats.pdf')
    plt.close()
    print("Generated: Figure 5 - Comparative statistics")


def figure6_period_heatmap(data):
    """
    Figure 6: Heatmap of congestion by city and time period.
    """
    fig, ax = plt.subplots(figsize=(10, 4))

    # Build matrix
    matrix = []
    for city in CITIES.keys():
        row = []
        for period, _ in PERIODS:
            if period in data[city]:
                row.append(data[city][period]['jam_factor_mean'].mean())
            else:
                row.append(np.nan)
        matrix.append(row)

    matrix = np.array(matrix)

    im = ax.imshow(matrix, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=5)

    ax.set_xticks(np.arange(len(PERIODS)))
    ax.set_yticks(np.arange(len(CITIES)))
    ax.set_xticklabels([label.replace('\n', ' ') for _, label in PERIODS],
                       rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels(list(CITIES.keys()))

    # Add values
    for i in range(len(CITIES)):
        for j in range(len(PERIODS)):
            if not np.isnan(matrix[i, j]):
                text = ax.text(j, i, f'{matrix[i, j]:.2f}',
                              ha='center', va='center', fontsize=8,
                              color='white' if matrix[i, j] > 2.5 else 'black')

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Mean Jam Factor')

    ax.set_title('Congestion Patterns by City and Time Period')
    plt.tight_layout()
    plt.savefig('paper/figures/fig6_heatmap.png')
    plt.savefig('paper/figures/fig6_heatmap.pdf')
    plt.close()
    print("Generated: Figure 6 - Period heatmap")


def main():
    """Generate all figures."""
    print("Loading traffic data...")
    data = load_traffic_data()

    print("\nGenerating publication figures...")
    print("-" * 40)

    figure1_temporal_patterns(data)
    figure2_traffic_maps(data)
    figure3_congestion_distribution(data)
    figure4_cv_analysis(data)
    figure5_comparative_stats(data)
    figure6_period_heatmap(data)

    print("-" * 40)
    print("\nAll figures saved to paper/figures/")
    print("Formats: PNG (300 DPI) and PDF")


if __name__ == '__main__':
    main()
