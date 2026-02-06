#!/usr/bin/env python3
"""
Semarang Traffic Data Aggregation - Full Date Range
Aggregates all traffic data from traffic_data_smg folder by time period
"""

import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime
import geopandas as gpd
import warnings
warnings.filterwarnings('ignore')

def extract_timestamp_from_filename(filename):
    """
    Extract timestamp from filename pattern: city_traffic_YYYYMMDD_HHMMSS.gpkg
    """
    try:
        base_name = os.path.splitext(os.path.basename(filename))[0]
        parts = base_name.split('_')
        date_str = parts[2]
        time_str = parts[3]
        datetime_str = f"{date_str}_{time_str}"
        return datetime.strptime(datetime_str, "%Y%m%d_%H%M%S")
    except Exception as e:
        print(f"Error parsing timestamp from {filename}: {str(e)}")
        return None

def get_time_period(hour):
    """
    Define time periods in a day
    """
    if 0 <= hour < 6:
        return 'night'
    elif 6 <= hour < 9:
        return 'morning_peak'
    elif 9 <= hour < 12:
        return 'morning_offpeak'
    elif 12 <= hour < 14:
        return 'lunch_hours'
    elif 14 <= hour < 16:
        return 'afternoon_offpeak'
    elif 16 <= hour < 19:
        return 'evening_peak'
    elif 19 <= hour < 22:
        return 'evening_offpeak'
    else:
        return 'late_night'

def get_reference_geometry(filepath):
    """
    Get reference geometry from a GPKG file using geopandas
    """
    try:
        gdf = gpd.read_file(filepath)
        # Keep only fid and geometry
        if 'fid' not in gdf.columns:
            gdf['fid'] = range(1, len(gdf) + 1)
        return gdf[['fid', 'geometry']].copy()
    except Exception as e:
        print(f"Error getting reference geometry: {str(e)}")
        return None

def read_gpkg_with_geopandas(filepath, traffic_column='jam_factor'):
    """
    Read GPKG file using geopandas and extract fid and traffic data
    """
    try:
        gdf = gpd.read_file(filepath)

        # Ensure fid column exists
        if 'fid' not in gdf.columns:
            gdf['fid'] = range(1, len(gdf) + 1)

        # Return only needed columns
        return gdf[['fid', traffic_column]].copy()

    except Exception as e:
        print(f"Error reading {filepath}: {str(e)}")
        return None

def analyze_semarang_traffic(city_folder, traffic_column, output_folder):
    """
    Analyze Semarang traffic patterns and save GPKG files for each time period
    """
    os.makedirs(output_folder, exist_ok=True)

    city = 'smg'

    # Get all GPKG files
    gpkg_files = sorted(glob.glob(os.path.join(city_folder, "*.gpkg")))

    if not gpkg_files:
        print(f"No GPKG files found in {city_folder}")
        return

    print(f"Found {len(gpkg_files)} GPKG files")
    print(f"Date range: {os.path.basename(gpkg_files[0])} to {os.path.basename(gpkg_files[-1])}")

    # Get reference geometry from first file
    print("\nExtracting reference geometry...")
    reference_gdf = get_reference_geometry(gpkg_files[0])
    if reference_gdf is None:
        print("Failed to get reference geometry")
        return
    print(f"Reference geometry has {len(reference_gdf)} segments")

    # Read all files and collect data
    print("\nReading all GPKG files...")
    all_data = []

    for i, file in enumerate(gpkg_files):
        if (i + 1) % 500 == 0:
            print(f"  Processing file {i+1}/{len(gpkg_files)}...")

        df = read_gpkg_with_geopandas(file, traffic_column)
        if df is not None:
            timestamp = extract_timestamp_from_filename(file)
            if timestamp:
                df['timestamp'] = timestamp
                df = df[['fid', traffic_column, 'timestamp']]
                all_data.append(df)

    if not all_data:
        print("No valid data found")
        return

    # Combine all data
    print(f"\nCombining {len(all_data)} files...")
    combined_data = pd.concat(all_data, ignore_index=True)
    print(f"Combined data shape: {combined_data.shape}")

    # Add hour and time period
    combined_data['hour'] = combined_data['timestamp'].dt.hour
    combined_data['time_period'] = combined_data['hour'].apply(get_time_period)

    # Show date range
    print(f"\nData date range: {combined_data['timestamp'].min()} to {combined_data['timestamp'].max()}")

    # Show time period distribution
    print("\nTime period distribution:")
    print(combined_data['time_period'].value_counts().sort_index())

    # Process each time period
    for period in sorted(combined_data['time_period'].unique()):
        print(f"\nProcessing time period: {period}")

        # Filter data for this time period
        period_data = combined_data[combined_data['time_period'] == period]
        print(f"  Records for {period}: {len(period_data)}")

        # Calculate statistics for each segment
        period_stats = period_data.groupby('fid').agg({
            traffic_column: ['mean', 'std', 'count', 'min', 'max']
        }).round(4)

        # Flatten column names
        period_stats.columns = [f"{traffic_column}_{col}" for col in ['mean', 'std', 'count', 'min', 'max']]
        period_stats = period_stats.reset_index()

        # Show variation in means
        means = period_stats[f'{traffic_column}_mean']
        print(f"  Variation in segment means:")
        print(f"    Min mean: {means.min():.4f}")
        print(f"    Max mean: {means.max():.4f}")
        print(f"    Mean of means: {means.mean():.4f}")
        print(f"    Std of means: {means.std():.4f}")

        # Merge with geometry
        period_gdf = reference_gdf.merge(period_stats, on='fid', how='left')

        # Count how many fids have data
        valid_data_count = period_gdf[f'{traffic_column}_mean'].notna().sum()
        print(f"  Segments with data: {valid_data_count}/{len(period_gdf)}")

        # Save as GPKG
        output_file = os.path.join(output_folder, f"{period}_{city}.gpkg")
        period_gdf.to_file(output_file, driver='GPKG')
        print(f"  Saved: {output_file}")

    print("\n" + "="*60)
    print("SEMARANG AGGREGATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    city_folder = "traffic_data_smg"
    traffic_column = "jam_factor"
    output_folder = "traffic_smg_output"

    analyze_semarang_traffic(city_folder, traffic_column, output_folder)
