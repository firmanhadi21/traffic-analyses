"""
Compare legacy FID-based aggregation vs. OSM-based aggregation.
Validates improvements in temporal consistency and data quality.
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns

from config import CITIES, get_aggregated_output_path


def load_aggregated_data(file_path):
    """
    Load aggregated traffic data from GeoPackage.

    Args:
        file_path: Path to aggregated GPKG file

    Returns:
        GeoDataFrame
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"Loading: {file_path.name}")
    gdf = gpd.read_file(file_path)
    print(f"  Rows: {len(gdf)}")
    print(f"  Columns: {list(gdf.columns)}")

    return gdf


def compare_observation_consistency(osm_gdf, metric):
    """
    Analyze observation consistency across temporal groups.

    Args:
        osm_gdf: OSM-based aggregated data
        metric: Metric name

    Returns:
        DataFrame with consistency statistics
    """
    count_col = f'{metric}_count'

    if count_col not in osm_gdf.columns:
        raise ValueError(f"Count column not found: {count_col}")

    # Group by segment and calculate stats across temporal groups
    segment_stats = osm_gdf.groupby('osm_composite_id')[count_col].agg([
        ('mean_observations', 'mean'),
        ('std_observations', 'std'),
        ('min_observations', 'min'),
        ('max_observations', 'max'),
        ('cv_observations', lambda x: x.std() / x.mean() if x.mean() > 0 else 0)
    ]).reset_index()

    print("\nObservation consistency per segment (across temporal groups):")
    print(f"  Mean observations: {segment_stats['mean_observations'].mean():.1f}")
    print(f"  Std of means: {segment_stats['mean_observations'].std():.1f}")
    print(f"  Mean CV: {segment_stats['cv_observations'].mean():.3f}")
    print(f"    (lower CV = more consistent)")

    return segment_stats


def compare_metric_distributions(osm_gdf, metric):
    """
    Analyze metric value distributions.

    Args:
        osm_gdf: OSM-based aggregated data
        metric: Metric name

    Returns:
        DataFrame with distribution statistics
    """
    mean_col = f'{metric}_mean'
    std_col = f'{metric}_std'

    if mean_col not in osm_gdf.columns:
        raise ValueError(f"Mean column not found: {mean_col}")

    print(f"\nMetric distribution ({metric}):")
    print(f"  Overall mean: {osm_gdf[mean_col].mean():.2f}")
    print(f"  Overall std: {osm_gdf[mean_col].std():.2f}")
    print(f"  Min: {osm_gdf[mean_col].min():.2f}")
    print(f"  Max: {osm_gdf[mean_col].max():.2f}")

    # Per-temporal-group statistics
    temporal_stats = osm_gdf.groupby('temporal_group')[mean_col].agg([
        ('mean', 'mean'),
        ('std', 'std'),
        ('count', 'count')
    ]).reset_index()

    print(f"\nPer-temporal-group statistics:")
    print(f"  Temporal groups: {len(temporal_stats)}")
    print(f"  Mean observations per group: {temporal_stats['count'].mean():.1f}")

    return temporal_stats


def analyze_spatial_coverage(osm_gdf):
    """
    Analyze spatial coverage and segment representation.

    Args:
        osm_gdf: OSM-based aggregated data

    Returns:
        Coverage statistics
    """
    total_segments = osm_gdf['osm_composite_id'].nunique()
    total_temporal_groups = osm_gdf['temporal_group'].nunique()

    # Expected rows if all segments present in all temporal groups
    expected_rows = total_segments * total_temporal_groups
    actual_rows = len(osm_gdf)
    coverage_rate = actual_rows / expected_rows if expected_rows > 0 else 0

    # Segments per temporal group
    segments_per_group = osm_gdf.groupby('temporal_group')['osm_composite_id'].nunique()

    print("\nSpatial coverage:")
    print(f"  Unique segments: {total_segments}")
    print(f"  Temporal groups: {total_temporal_groups}")
    print(f"  Expected rows (full coverage): {expected_rows}")
    print(f"  Actual rows: {actual_rows}")
    print(f"  Coverage rate: {coverage_rate:.1%}")
    print(f"\n  Segments per temporal group:")
    print(f"    Mean: {segments_per_group.mean():.1f}")
    print(f"    Std: {segments_per_group.std():.1f}")
    print(f"    Min: {segments_per_group.min()}")
    print(f"    Max: {segments_per_group.max()}")

    stats = {
        'total_segments': total_segments,
        'total_temporal_groups': total_temporal_groups,
        'expected_rows': expected_rows,
        'actual_rows': actual_rows,
        'coverage_rate': coverage_rate,
        'segments_per_group_mean': segments_per_group.mean(),
        'segments_per_group_std': segments_per_group.std()
    }

    return stats


def plot_observation_consistency(segment_stats, output_dir, city_code):
    """
    Create visualization of observation consistency.

    Args:
        segment_stats: DataFrame with segment-level statistics
        output_dir: Output directory for plots
        city_code: City code
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f'Observation Consistency Analysis - {city_code.upper()}', fontsize=14)

    # Mean observations histogram
    axes[0, 0].hist(segment_stats['mean_observations'], bins=50, edgecolor='black')
    axes[0, 0].set_xlabel('Mean Observations per Segment')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Distribution of Mean Observations')

    # CV histogram
    axes[0, 1].hist(segment_stats['cv_observations'], bins=50, edgecolor='black')
    axes[0, 1].set_xlabel('Coefficient of Variation')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Observation Consistency (lower CV = more consistent)')

    # Scatter: mean vs std
    axes[1, 0].scatter(segment_stats['mean_observations'],
                       segment_stats['std_observations'],
                       alpha=0.5, s=20)
    axes[1, 0].set_xlabel('Mean Observations')
    axes[1, 0].set_ylabel('Std of Observations')
    axes[1, 0].set_title('Mean vs. Std of Observations')

    # Box plot: observation range
    data_to_plot = [
        segment_stats['min_observations'],
        segment_stats['mean_observations'],
        segment_stats['max_observations']
    ]
    axes[1, 1].boxplot(data_to_plot, labels=['Min', 'Mean', 'Max'])
    axes[1, 1].set_ylabel('Observations')
    axes[1, 1].set_title('Observation Range per Segment')

    plt.tight_layout()
    output_path = output_dir / f'{city_code}_observation_consistency.png'
    plt.savefig(output_path, dpi=150)
    print(f"\nPlot saved: {output_path}")
    plt.close()


def analyze_osm_output(city_code, time_period_name, temporal_grouping, metric,
                       start_date, end_date, create_plots=True):
    """
    Analyze OSM-based aggregated output.

    Args:
        city_code: City code
        time_period_name: Time period name (e.g., "morning_peak")
        temporal_grouping: Temporal grouping (e.g., "weekly")
        metric: Traffic metric
        start_date: Start date (YYYYMMDD format)
        end_date: End date (YYYYMMDD format)
        create_plots: Whether to create visualization plots

    Returns:
        Dictionary with analysis results
    """
    city_config = CITIES[city_code]

    print(f"\n{'='*60}")
    print(f"Analyzing OSM-based output for {city_config['name']}")
    print(f"{'='*60}")
    print(f"Time period: {time_period_name}")
    print(f"Temporal grouping: {temporal_grouping}")
    print(f"Metric: {metric}")

    # Load OSM-based output
    osm_path = get_aggregated_output_path(
        city_code, time_period_name, temporal_grouping, metric,
        start_date, end_date
    )

    osm_gdf = load_aggregated_data(osm_path)

    # Run analyses
    segment_stats = compare_observation_consistency(osm_gdf, metric)
    temporal_stats = compare_metric_distributions(osm_gdf, metric)
    coverage_stats = analyze_spatial_coverage(osm_gdf)

    # Create plots if requested
    if create_plots:
        output_dir = Path(f"aggregated_output/{city_code}/diagnostics")
        plot_observation_consistency(segment_stats, output_dir, city_code)

    results = {
        'city_code': city_code,
        'time_period_name': time_period_name,
        'temporal_grouping': temporal_grouping,
        'metric': metric,
        'segment_stats': segment_stats,
        'temporal_stats': temporal_stats,
        'coverage_stats': coverage_stats
    }

    return results


def main():
    """Command-line interface for validation."""
    parser = argparse.ArgumentParser(
        description='Analyze and validate OSM-based traffic aggregation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze OSM-based aggregation output
  python compare_legacy_vs_osm.py \\
    --city smg \\
    --time-period-name morning_peak \\
    --temporal-grouping weekly \\
    --metric jam_factor \\
    --start-date 20250101 \\
    --end-date 20251231

  # Analyze without creating plots
  python compare_legacy_vs_osm.py \\
    --city jkt \\
    --time-period-name evening_peak \\
    --temporal-grouping monthly \\
    --metric speed \\
    --start-date 20250101 \\
    --end-date 20251231 \\
    --no-plots
        """
    )

    parser.add_argument(
        '--city',
        required=True,
        choices=list(CITIES.keys()),
        help='City code (smg, bdg, jkt)'
    )
    parser.add_argument(
        '--time-period-name',
        required=True,
        help='Time period name (e.g., morning_peak, evening_peak, allday)'
    )
    parser.add_argument(
        '--temporal-grouping',
        required=True,
        choices=['daily', 'weekly', 'monthly', 'all'],
        help='Temporal grouping'
    )
    parser.add_argument(
        '--metric',
        required=True,
        choices=['jam_factor', 'speed', 'free_flow'],
        help='Traffic metric'
    )
    parser.add_argument(
        '--start-date',
        required=True,
        help='Start date in YYYYMMDD format'
    )
    parser.add_argument(
        '--end-date',
        required=True,
        help='End date in YYYYMMDD format'
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Skip plot generation'
    )

    args = parser.parse_args()

    # Validate date formats
    from datetime import datetime
    try:
        datetime.strptime(args.start_date, '%Y%m%d')
        datetime.strptime(args.end_date, '%Y%m%d')
    except ValueError as e:
        print(f"Error: Invalid date format. {e}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    try:
        results = analyze_osm_output(
            args.city,
            args.time_period_name,
            args.temporal_grouping,
            args.metric,
            args.start_date,
            args.end_date,
            create_plots=not args.no_plots
        )

        print(f"\n{'='*60}")
        print("Analysis complete!")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\nError during analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
