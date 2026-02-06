#!/usr/bin/env python3
"""
Geostatistical Analysis and Visualization of Traffic Patterns
Analyzes traffic data for Semarang, Bandung, and Jakarta
"""

import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Create output directory for figures
FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

# City configurations
CITIES = {
    'smg': {'name': 'Semarang', 'folder': 'traffic_smg_output', 'color': '#2ecc71'},
    'bdg': {'name': 'Bandung', 'folder': 'traffic_bdg_output', 'color': '#3498db'},
    'jkt': {'name': 'Jakarta', 'folder': 'traffic_jkt_output', 'color': '#e74c3c'}
}

TIME_PERIODS = [
    'night', 'morning_peak', 'morning_offpeak', 'lunch_hours',
    'afternoon_offpeak', 'evening_peak', 'evening_offpeak', 'late_night'
]

TIME_PERIOD_LABELS = {
    'night': 'Night\n(00-06)',
    'morning_peak': 'Morning\nPeak (06-09)',
    'morning_offpeak': 'Morning\nOff-peak (09-12)',
    'lunch_hours': 'Lunch\n(12-14)',
    'afternoon_offpeak': 'Afternoon\nOff-peak (14-16)',
    'evening_peak': 'Evening\nPeak (16-19)',
    'evening_offpeak': 'Evening\nOff-peak (19-22)',
    'late_night': 'Late Night\n(22-00)'
}

# Custom colormap for jam factor (green to red)
def create_traffic_cmap():
    colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b']
    return LinearSegmentedColormap.from_list('traffic', colors)

TRAFFIC_CMAP = create_traffic_cmap()


def load_city_data(city_code):
    """Load all time period data for a city"""
    city_info = CITIES[city_code]
    folder = city_info['folder']

    data = {}
    for period in TIME_PERIODS:
        filepath = f"{folder}/{period}_{city_code}.gpkg"
        if os.path.exists(filepath):
            gdf = gpd.read_file(filepath)
            data[period] = gdf

    return data


def calculate_spatial_statistics(gdf, column='jam_factor_mean'):
    """Calculate basic spatial statistics"""
    values = gdf[column].dropna()

    stats = {
        'count': len(values),
        'mean': values.mean(),
        'std': values.std(),
        'min': values.min(),
        'max': values.max(),
        'median': values.median(),
        'q25': values.quantile(0.25),
        'q75': values.quantile(0.75),
        'iqr': values.quantile(0.75) - values.quantile(0.25),
        'cv': values.std() / values.mean() if values.mean() > 0 else 0,  # Coefficient of variation
        'skewness': values.skew(),
        'kurtosis': values.kurtosis()
    }

    return stats


def calculate_hotspot_classification(gdf, column='jam_factor_mean'):
    """Classify segments into congestion categories"""
    values = gdf[column].copy()

    # Classification based on jam factor
    conditions = [
        values <= 1.0,
        (values > 1.0) & (values <= 2.0),
        (values > 2.0) & (values <= 4.0),
        (values > 4.0) & (values <= 6.0),
        values > 6.0
    ]
    categories = ['Free Flow', 'Light Traffic', 'Moderate', 'Heavy', 'Severe']

    gdf['congestion_class'] = np.select(conditions, categories, default='Unknown')

    # Count segments in each category
    class_counts = gdf['congestion_class'].value_counts()
    class_pct = (class_counts / len(gdf) * 100).round(2)

    return class_counts, class_pct


def spatial_autocorrelation_proxy(gdf, column='jam_factor_mean'):
    """
    Calculate a proxy for spatial clustering using neighbor analysis
    Uses centroid distance-based approach
    """
    gdf = gdf.copy()
    gdf['centroid'] = gdf.geometry.centroid

    # Get centroids as points
    centroids = gdf['centroid'].values
    values = gdf[column].values

    # Calculate mean value of nearest neighbors (simple approach)
    from scipy.spatial import cKDTree

    coords = np.array([[p.x, p.y] for p in centroids])
    tree = cKDTree(coords)

    # Find 5 nearest neighbors for each point
    k = min(6, len(coords))  # k includes the point itself
    distances, indices = tree.query(coords, k=k)

    # Calculate local mean (excluding self)
    local_means = []
    for i, idx in enumerate(indices):
        neighbor_values = values[idx[1:]]  # Exclude self
        local_means.append(np.mean(neighbor_values))

    gdf['local_mean'] = local_means
    gdf['local_deviation'] = values - np.array(local_means)

    # Spatial clustering indicator
    # Positive: higher than neighbors, Negative: lower than neighbors
    correlation = np.corrcoef(values, local_means)[0, 1]

    return correlation, gdf


def plot_city_traffic_maps(city_code, data, figsize=(20, 10)):
    """Create traffic maps for all time periods of a city"""
    city_name = CITIES[city_code]['name']

    fig, axes = plt.subplots(2, 4, figsize=figsize)
    axes = axes.flatten()

    for idx, period in enumerate(TIME_PERIODS):
        ax = axes[idx]
        gdf = data[period]

        # Plot the traffic data
        gdf.plot(column='jam_factor_mean',
                 cmap=TRAFFIC_CMAP,
                 linewidth=0.5,
                 ax=ax,
                 vmin=0,
                 vmax=4,
                 legend=False)

        ax.set_title(TIME_PERIOD_LABELS[period], fontsize=10, fontweight='bold')
        ax.set_axis_off()

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap=TRAFFIC_CMAP, norm=plt.Normalize(vmin=0, vmax=4))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, orientation='horizontal', fraction=0.02, pad=0.08)
    cbar.set_label('Jam Factor (0=Free Flow, 4+=Congested)', fontsize=12)

    plt.suptitle(f'{city_name} - Traffic Patterns by Time Period', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()

    filepath = FIGURES_DIR / f'{city_code}_traffic_maps.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_temporal_pattern(all_city_data, figsize=(14, 6)):
    """Plot temporal traffic patterns for all cities"""
    fig, ax = plt.subplots(figsize=figsize)

    x = np.arange(len(TIME_PERIODS))
    width = 0.25

    for i, (city_code, data) in enumerate(all_city_data.items()):
        means = [data[p]['jam_factor_mean'].mean() for p in TIME_PERIODS]
        stds = [data[p]['jam_factor_mean'].std() for p in TIME_PERIODS]

        bars = ax.bar(x + i*width, means, width,
                      label=CITIES[city_code]['name'],
                      color=CITIES[city_code]['color'],
                      yerr=stds, capsize=3, alpha=0.8)

    ax.set_xlabel('Time Period', fontsize=12)
    ax.set_ylabel('Mean Jam Factor', fontsize=12)
    ax.set_title('Traffic Congestion Patterns by Time Period', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels([TIME_PERIOD_LABELS[p].replace('\n', ' ') for p in TIME_PERIODS],
                       rotation=45, ha='right', fontsize=9)
    ax.legend(title='City')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, 3)

    # Add reference lines
    ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Free Flow Threshold')
    ax.axhline(y=2.0, color='orange', linestyle='--', alpha=0.5, label='Moderate Threshold')

    plt.tight_layout()
    filepath = FIGURES_DIR / 'temporal_pattern_comparison.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_congestion_distribution(all_city_data, figsize=(14, 5)):
    """Plot distribution of jam factors for each city"""
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    for idx, (city_code, data) in enumerate(all_city_data.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Combine all periods for overall distribution
        all_values = []
        for period in TIME_PERIODS:
            all_values.extend(data[period]['jam_factor_mean'].dropna().tolist())

        # Plot histogram
        ax.hist(all_values, bins=50, color=CITIES[city_code]['color'],
                alpha=0.7, edgecolor='white')
        ax.axvline(np.mean(all_values), color='red', linestyle='--',
                   label=f'Mean: {np.mean(all_values):.2f}')
        ax.axvline(np.median(all_values), color='blue', linestyle='--',
                   label=f'Median: {np.median(all_values):.2f}')

        ax.set_xlabel('Jam Factor', fontsize=11)
        ax.set_ylabel('Frequency', fontsize=11)
        ax.set_title(f'{city_name}', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    plt.suptitle('Distribution of Traffic Congestion (All Time Periods)',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    filepath = FIGURES_DIR / 'congestion_distribution.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_peak_vs_offpeak(all_city_data, figsize=(12, 5)):
    """Compare peak vs off-peak traffic"""
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    peak_periods = ['morning_peak', 'evening_peak']
    offpeak_periods = ['night', 'morning_offpeak', 'afternoon_offpeak', 'late_night']

    for idx, (city_code, data) in enumerate(all_city_data.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Calculate peak and off-peak means per segment
        peak_values = np.mean([data[p]['jam_factor_mean'].values for p in peak_periods], axis=0)
        offpeak_values = np.mean([data[p]['jam_factor_mean'].values for p in offpeak_periods], axis=0)

        ax.scatter(offpeak_values, peak_values, alpha=0.3, s=10,
                   color=CITIES[city_code]['color'])

        # Add diagonal line
        max_val = max(peak_values.max(), offpeak_values.max())
        ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label='Equal line')

        # Calculate correlation
        corr = np.corrcoef(offpeak_values, peak_values)[0, 1]

        ax.set_xlabel('Off-Peak Jam Factor', fontsize=11)
        ax.set_ylabel('Peak Jam Factor', fontsize=11)
        ax.set_title(f'{city_name}\n(r = {corr:.3f})', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)
        ax.set_xlim(0, None)
        ax.set_ylim(0, None)

    plt.suptitle('Peak vs Off-Peak Traffic Comparison', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    filepath = FIGURES_DIR / 'peak_vs_offpeak.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_variability_analysis(all_city_data, figsize=(14, 5)):
    """Analyze spatial variability in traffic patterns"""
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    for idx, (city_code, data) in enumerate(all_city_data.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Calculate coefficient of variation for each segment across time periods
        segment_values = []
        for period in TIME_PERIODS:
            segment_values.append(data[period]['jam_factor_mean'].values)

        segment_values = np.array(segment_values)

        # Mean and std across time periods for each segment
        segment_means = np.mean(segment_values, axis=0)
        segment_stds = np.std(segment_values, axis=0)
        cv = segment_stds / segment_means  # Coefficient of variation

        ax.scatter(segment_means, cv, alpha=0.3, s=10,
                   color=CITIES[city_code]['color'])

        ax.set_xlabel('Mean Jam Factor', fontsize=11)
        ax.set_ylabel('Coefficient of Variation', fontsize=11)
        ax.set_title(f'{city_name}\n(Mean CV: {np.mean(cv):.3f})', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)

    plt.suptitle('Traffic Variability Analysis by Segment', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    filepath = FIGURES_DIR / 'variability_analysis.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_congestion_hotspots(city_code, data, period='evening_peak', figsize=(12, 10)):
    """Identify and plot congestion hotspots"""
    city_name = CITIES[city_code]['name']
    gdf = data[period].copy()

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Left: Traffic intensity map
    ax1 = axes[0]
    gdf.plot(column='jam_factor_mean',
             cmap=TRAFFIC_CMAP,
             linewidth=0.8,
             ax=ax1,
             vmin=0,
             vmax=4,
             legend=True,
             legend_kwds={'label': 'Jam Factor', 'shrink': 0.8})
    ax1.set_title(f'{city_name} - Traffic Intensity\n({TIME_PERIOD_LABELS[period]})',
                  fontsize=12, fontweight='bold')
    ax1.set_axis_off()

    # Right: Hotspot classification
    ax2 = axes[1]

    # Classify hotspots
    gdf['hotspot'] = 'Normal'
    gdf.loc[gdf['jam_factor_mean'] > gdf['jam_factor_mean'].quantile(0.9), 'hotspot'] = 'Hotspot (Top 10%)'
    gdf.loc[gdf['jam_factor_mean'] < gdf['jam_factor_mean'].quantile(0.1), 'hotspot'] = 'Coldspot (Bottom 10%)'

    colors = {'Normal': '#95a5a6', 'Hotspot (Top 10%)': '#e74c3c', 'Coldspot (Bottom 10%)': '#27ae60'}

    for hotspot_type, color in colors.items():
        subset = gdf[gdf['hotspot'] == hotspot_type]
        if len(subset) > 0:
            subset.plot(ax=ax2, color=color, linewidth=0.8, label=hotspot_type)

    ax2.set_title(f'{city_name} - Congestion Hotspots\n({TIME_PERIOD_LABELS[period]})',
                  fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right')
    ax2.set_axis_off()

    plt.tight_layout()

    filepath = FIGURES_DIR / f'{city_code}_hotspots_{period}.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_boxplot_comparison(all_city_data, figsize=(16, 6)):
    """Create boxplot comparison across cities and time periods"""
    fig, ax = plt.subplots(figsize=figsize)

    # Prepare data for boxplot
    boxplot_data = []
    positions = []
    colors = []
    labels = []

    pos = 0
    for period in TIME_PERIODS:
        for city_code in CITIES.keys():
            values = all_city_data[city_code][period]['jam_factor_mean'].dropna().values
            boxplot_data.append(values)
            positions.append(pos)
            colors.append(CITIES[city_code]['color'])
            pos += 1
        pos += 0.5  # Gap between periods

    # Create boxplot
    bp = ax.boxplot(boxplot_data, positions=positions, widths=0.6, patch_artist=True,
                    showfliers=False)

    # Color the boxes
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # Set x-axis labels
    period_positions = [i * 3.5 + 1 for i in range(len(TIME_PERIODS))]
    ax.set_xticks(period_positions)
    ax.set_xticklabels([TIME_PERIOD_LABELS[p].replace('\n', ' ') for p in TIME_PERIODS],
                       rotation=45, ha='right', fontsize=9)

    # Add legend
    legend_patches = [mpatches.Patch(color=CITIES[c]['color'], label=CITIES[c]['name'], alpha=0.7)
                      for c in CITIES.keys()]
    ax.legend(handles=legend_patches, loc='upper right')

    ax.set_ylabel('Jam Factor', fontsize=12)
    ax.set_title('Traffic Congestion Distribution by City and Time Period',
                 fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    filepath = FIGURES_DIR / 'boxplot_comparison.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def plot_heatmap_summary(all_city_data, figsize=(12, 8)):
    """Create heatmap summary of traffic patterns"""
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    for idx, (city_code, data) in enumerate(all_city_data.items()):
        ax = axes[idx]
        city_name = CITIES[city_code]['name']

        # Create matrix: segments x time periods
        # Sample 100 segments for visualization
        n_segments = len(data[TIME_PERIODS[0]])
        sample_size = min(100, n_segments)
        sample_idx = np.random.choice(n_segments, sample_size, replace=False)
        sample_idx = np.sort(sample_idx)

        matrix = np.zeros((sample_size, len(TIME_PERIODS)))
        for j, period in enumerate(TIME_PERIODS):
            values = data[period]['jam_factor_mean'].values
            matrix[:, j] = values[sample_idx]

        im = ax.imshow(matrix, aspect='auto', cmap=TRAFFIC_CMAP, vmin=0, vmax=3)

        ax.set_xticks(range(len(TIME_PERIODS)))
        ax.set_xticklabels([p.replace('_', '\n') for p in TIME_PERIODS],
                           fontsize=7, rotation=45, ha='right')
        ax.set_ylabel('Road Segments (sample)', fontsize=10)
        ax.set_title(f'{city_name}', fontsize=12, fontweight='bold')

    # Add colorbar
    cbar = fig.colorbar(im, ax=axes, orientation='horizontal', fraction=0.05, pad=0.15)
    cbar.set_label('Jam Factor', fontsize=11)

    plt.suptitle('Traffic Pattern Heatmap (Sample of Road Segments)',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    filepath = FIGURES_DIR / 'heatmap_summary.png'
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {filepath}")


def generate_statistics_report(all_city_data):
    """Generate comprehensive statistics report"""
    report = []
    report.append("=" * 80)
    report.append("GEOSTATISTICAL ANALYSIS REPORT - TRAFFIC PATTERNS")
    report.append("=" * 80)
    report.append("")

    for city_code, data in all_city_data.items():
        city_name = CITIES[city_code]['name']
        report.append(f"\n{'='*40}")
        report.append(f"{city_name.upper()}")
        report.append(f"{'='*40}")

        # Overall statistics
        all_means = []
        for period in TIME_PERIODS:
            all_means.extend(data[period]['jam_factor_mean'].dropna().tolist())

        report.append(f"\nOverall Statistics:")
        report.append(f"  Total segments: {len(data[TIME_PERIODS[0]])}")
        report.append(f"  Overall mean jam factor: {np.mean(all_means):.4f}")
        report.append(f"  Overall std: {np.std(all_means):.4f}")
        report.append(f"  Overall median: {np.median(all_means):.4f}")

        report.append(f"\nStatistics by Time Period:")
        report.append("-" * 60)
        report.append(f"{'Period':<20} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'CV':>8}")
        report.append("-" * 60)

        for period in TIME_PERIODS:
            stats = calculate_spatial_statistics(data[period])
            report.append(f"{period:<20} {stats['mean']:>8.3f} {stats['std']:>8.3f} "
                         f"{stats['min']:>8.3f} {stats['max']:>8.3f} {stats['cv']:>8.3f}")

        # Congestion classification for evening peak
        report.append(f"\nCongestion Classification (Evening Peak):")
        class_counts, class_pct = calculate_hotspot_classification(data['evening_peak'])
        for cat in ['Free Flow', 'Light Traffic', 'Moderate', 'Heavy', 'Severe']:
            if cat in class_counts.index:
                report.append(f"  {cat}: {class_counts[cat]} segments ({class_pct[cat]:.1f}%)")

        # Spatial autocorrelation proxy
        corr, _ = spatial_autocorrelation_proxy(data['evening_peak'])
        report.append(f"\nSpatial Clustering Indicator: {corr:.4f}")
        report.append(f"  (Values close to 1 indicate strong spatial clustering)")

    # Comparative analysis
    report.append(f"\n\n{'='*40}")
    report.append("COMPARATIVE ANALYSIS")
    report.append(f"{'='*40}")

    report.append("\nPeak Hour Comparison (Evening Peak):")
    for city_code, data in all_city_data.items():
        mean_val = data['evening_peak']['jam_factor_mean'].mean()
        report.append(f"  {CITIES[city_code]['name']}: {mean_val:.3f}")

    report.append("\nMost Congested Period by City:")
    for city_code, data in all_city_data.items():
        period_means = {p: data[p]['jam_factor_mean'].mean() for p in TIME_PERIODS}
        worst_period = max(period_means, key=period_means.get)
        report.append(f"  {CITIES[city_code]['name']}: {worst_period} ({period_means[worst_period]:.3f})")

    report_text = "\n".join(report)

    # Save report
    filepath = FIGURES_DIR / 'statistics_report.txt'
    with open(filepath, 'w') as f:
        f.write(report_text)
    print(f"  Saved: {filepath}")

    return report_text


def main():
    print("=" * 60)
    print("GEOSTATISTICAL ANALYSIS OF TRAFFIC PATTERNS")
    print("=" * 60)

    # Load data for all cities
    print("\n1. Loading data...")
    all_city_data = {}
    for city_code in CITIES.keys():
        print(f"  Loading {CITIES[city_code]['name']}...")
        all_city_data[city_code] = load_city_data(city_code)

    # Generate visualizations
    print("\n2. Generating traffic maps...")
    for city_code in CITIES.keys():
        print(f"  Creating maps for {CITIES[city_code]['name']}...")
        plot_city_traffic_maps(city_code, all_city_data[city_code])

    print("\n3. Generating comparative visualizations...")

    print("  Creating temporal pattern comparison...")
    plot_temporal_pattern(all_city_data)

    print("  Creating congestion distribution...")
    plot_congestion_distribution(all_city_data)

    print("  Creating peak vs off-peak comparison...")
    plot_peak_vs_offpeak(all_city_data)

    print("  Creating variability analysis...")
    plot_variability_analysis(all_city_data)

    print("  Creating boxplot comparison...")
    plot_boxplot_comparison(all_city_data)

    print("  Creating heatmap summary...")
    plot_heatmap_summary(all_city_data)

    print("\n4. Generating hotspot analysis...")
    for city_code in CITIES.keys():
        print(f"  Analyzing hotspots for {CITIES[city_code]['name']}...")
        plot_congestion_hotspots(city_code, all_city_data[city_code])

    print("\n5. Generating statistics report...")
    report = generate_statistics_report(all_city_data)
    print("\n" + report)

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE!")
    print(f"All figures saved to: {FIGURES_DIR.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
