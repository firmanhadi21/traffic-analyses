"""
Spatial matching algorithms for HERE traffic segments to OSM road network.
Implements two-stage matching: intersection + nearest neighbor fallback.
"""

import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString

from config import MATCHING_PARAMS
from utils import create_synthetic_id


def calculate_overlap_length(here_geom, osm_geom):
    """
    Calculate geometric overlap length between two line segments.

    Args:
        here_geom: HERE segment geometry
        osm_geom: OSM segment geometry

    Returns:
        Overlap length in degrees (or CRS units)
    """
    try:
        intersection = here_geom.intersection(osm_geom)
        if intersection.is_empty:
            return 0.0
        return intersection.length
    except Exception:
        return 0.0


def match_by_intersection(here_gdf, osm_gdf, verbose=True):
    """
    Stage 1: Match HERE segments to OSM by geometric intersection.

    For segments with multiple matches, chooses OSM segment with longest overlap.

    Args:
        here_gdf: GeoDataFrame of HERE traffic segments
        osm_gdf: GeoDataFrame of OSM road network
        verbose: Print progress messages

    Returns:
        Tuple of (matched_gdf, unmatched_gdf, match_stats)
    """
    if verbose:
        print("Stage 1: Intersection matching...")
        print(f"  HERE segments: {len(here_gdf)}")
        print(f"  OSM segments: {len(osm_gdf)}")

    # Ensure both have same CRS
    if here_gdf.crs != osm_gdf.crs:
        here_gdf = here_gdf.to_crs(osm_gdf.crs)

    # Spatial join with intersection predicate
    joined = gpd.sjoin(
        here_gdf,
        osm_gdf[['osm_composite_id', 'geometry']],
        how='left',
        predicate='intersects'
    )

    # Handle multiple matches per HERE segment
    matched_list = []
    unmatched_list = []

    for here_idx in here_gdf.index:
        matches = joined.loc[joined.index == here_idx]

        if len(matches) == 0 or matches['osm_composite_id'].isna().all():
            # No matches
            unmatched_list.append(here_idx)
        else:
            # One or more matches - choose best by overlap length
            if len(matches) > 1:
                # Calculate overlap for each match
                here_geom = here_gdf.loc[here_idx, 'geometry']
                overlaps = []

                for _, match_row in matches.iterrows():
                    osm_id = match_row['osm_composite_id']
                    if pd.isna(osm_id):
                        overlaps.append(0.0)
                        continue

                    osm_geom = osm_gdf.loc[osm_gdf['osm_composite_id'] == osm_id, 'geometry'].iloc[0]
                    overlap = calculate_overlap_length(here_geom, osm_geom)
                    overlaps.append(overlap)

                # Choose match with longest overlap
                best_idx = np.argmax(overlaps)
                best_match = matches.iloc[best_idx]
            else:
                best_match = matches.iloc[0]

            matched_list.append({
                'here_index': here_idx,
                'osm_composite_id': best_match['osm_composite_id'],
                'match_method': 'intersection',
                'distance_m': 0.0  # Direct intersection
            })

    matched_gdf = here_gdf.loc[[m['here_index'] for m in matched_list]].copy()
    matched_gdf['osm_composite_id'] = [m['osm_composite_id'] for m in matched_list]
    matched_gdf['match_method'] = 'intersection'
    matched_gdf['distance_m'] = 0.0

    unmatched_gdf = here_gdf.loc[unmatched_list].copy()

    stats = {
        'total_segments': len(here_gdf),
        'matched': len(matched_gdf),
        'unmatched': len(unmatched_gdf),
        'match_rate': len(matched_gdf) / len(here_gdf) if len(here_gdf) > 0 else 0
    }

    if verbose:
        print(f"  Matched: {stats['matched']} ({stats['match_rate']:.1%})")
        print(f"  Unmatched: {stats['unmatched']}")

    return matched_gdf, unmatched_gdf, stats


def match_by_nearest_neighbor(unmatched_gdf, osm_gdf,
                               threshold_m=None, verbose=True):
    """
    Stage 2: Match remaining segments by nearest neighbor.

    Args:
        unmatched_gdf: GeoDataFrame of unmatched HERE segments
        osm_gdf: GeoDataFrame of OSM road network
        threshold_m: Maximum distance threshold in meters (default from config)
        verbose: Print progress messages

    Returns:
        Tuple of (matched_gdf, still_unmatched_gdf, match_stats)
    """
    if len(unmatched_gdf) == 0:
        return gpd.GeoDataFrame(), unmatched_gdf, {'matched': 0, 'unmatched': 0, 'mean_distance_m': 0}

    if threshold_m is None:
        threshold_m = MATCHING_PARAMS['nearest_neighbor_threshold_m']

    if verbose:
        print(f"\nStage 2: Nearest neighbor matching (threshold: {threshold_m}m)...")
        print(f"  Unmatched segments: {len(unmatched_gdf)}")

    # Ensure both have same CRS
    if unmatched_gdf.crs != osm_gdf.crs:
        unmatched_gdf = unmatched_gdf.to_crs(osm_gdf.crs)

    # Project to metric CRS for distance calculation (UTM zone appropriate for Indonesia)
    # Indonesia spans multiple UTM zones, use zone 49S as approximation
    metric_crs = 'EPSG:32749'  # UTM Zone 49S

    unmatched_metric = unmatched_gdf.to_crs(metric_crs)
    osm_metric = osm_gdf.to_crs(metric_crs)

    # Nearest neighbor join with distance
    joined = gpd.sjoin_nearest(
        unmatched_metric,
        osm_metric[['osm_composite_id', 'geometry']],
        how='left',
        max_distance=threshold_m,
        distance_col='distance_m'
    )

    # Drop duplicates (keep first match per segment)
    # sjoin_nearest can return multiple rows if there are ties
    joined = joined[~joined.index.duplicated(keep='first')]

    # Separate matched and still unmatched
    matched_mask = ~joined['osm_composite_id'].isna()
    matched_indices = joined[matched_mask].index.unique()
    still_unmatched_indices = joined[~matched_mask].index.unique()

    # Build matched GeoDataFrame
    if len(matched_indices) > 0:
        matched_gdf = unmatched_gdf.loc[matched_indices].copy()
        matched_gdf['osm_composite_id'] = joined.loc[matched_indices, 'osm_composite_id'].values
        matched_gdf['match_method'] = 'nearest_neighbor'
        matched_gdf['distance_m'] = joined.loc[matched_indices, 'distance_m'].values
    else:
        matched_gdf = gpd.GeoDataFrame()

    still_unmatched_gdf = unmatched_gdf.loc[still_unmatched_indices].copy()

    stats = {
        'matched': len(matched_gdf),
        'unmatched': len(still_unmatched_gdf),
        'mean_distance_m': matched_gdf['distance_m'].mean() if len(matched_gdf) > 0 else 0,
        'max_distance_m': matched_gdf['distance_m'].max() if len(matched_gdf) > 0 else 0,
        'median_distance_m': matched_gdf['distance_m'].median() if len(matched_gdf) > 0 else 0
    }

    if verbose:
        print(f"  Matched: {stats['matched']}")
        print(f"  Still unmatched: {stats['unmatched']}")
        if stats['matched'] > 0:
            print(f"  Distance stats: mean={stats['mean_distance_m']:.1f}m, "
                  f"median={stats['median_distance_m']:.1f}m, "
                  f"max={stats['max_distance_m']:.1f}m")

    return matched_gdf, still_unmatched_gdf, stats


def assign_synthetic_ids(unmatched_gdf, verbose=True):
    """
    Stage 3: Assign synthetic IDs to remaining unmatched segments.

    Args:
        unmatched_gdf: GeoDataFrame of unmatched HERE segments
        verbose: Print progress messages

    Returns:
        GeoDataFrame with synthetic IDs assigned
    """
    if len(unmatched_gdf) == 0:
        return gpd.GeoDataFrame()

    if verbose:
        print(f"\nStage 3: Assigning synthetic IDs...")
        print(f"  Unmatched segments: {len(unmatched_gdf)}")

    synthetic_gdf = unmatched_gdf.copy()
    synthetic_gdf['osm_composite_id'] = [
        create_synthetic_id(i, MATCHING_PARAMS['synthetic_id_start'])
        for i in range(len(synthetic_gdf))
    ]
    synthetic_gdf['match_method'] = 'synthetic'
    synthetic_gdf['distance_m'] = np.nan

    if verbose:
        print(f"  Created {len(synthetic_gdf)} synthetic IDs")

    return synthetic_gdf


def match_here_to_osm(here_gdf, osm_gdf, verbose=True):
    """
    Complete two-stage matching pipeline.

    Args:
        here_gdf: GeoDataFrame of HERE traffic segments
        osm_gdf: GeoDataFrame of OSM road network
        verbose: Print progress messages

    Returns:
        Tuple of (matched_gdf, diagnostics_dict)
    """
    import pandas as pd  # Import here to avoid circular dependency

    if verbose:
        print(f"\n{'='*60}")
        print("Starting spatial matching pipeline")
        print(f"{'='*60}")

    # Stage 1: Intersection matching
    matched_intersection, unmatched_1, stats_1 = match_by_intersection(
        here_gdf, osm_gdf, verbose
    )

    # Stage 2: Nearest neighbor matching
    matched_nn, unmatched_2, stats_2 = match_by_nearest_neighbor(
        unmatched_1, osm_gdf, verbose=verbose
    )

    # Stage 3: Synthetic IDs
    matched_synthetic = assign_synthetic_ids(unmatched_2, verbose)

    # Combine all matches
    if verbose:
        print(f"\n{'='*60}")
        print("Combining results...")
        print(f"{'='*60}")

    all_matched = pd.concat([
        matched_intersection,
        matched_nn,
        matched_synthetic
    ], ignore_index=True)

    # Calculate overall statistics
    total = len(here_gdf)
    n_intersection = len(matched_intersection)
    n_nn = len(matched_nn)
    n_synthetic = len(matched_synthetic)

    diagnostics = {
        'total_segments': total,
        'intersection_matched': n_intersection,
        'intersection_match_rate': n_intersection / total,
        'nearest_neighbor_matched': n_nn,
        'nearest_neighbor_match_rate': n_nn / total,
        'synthetic_ids': n_synthetic,
        'synthetic_rate': n_synthetic / total,
        'overall_osm_match_rate': (n_intersection + n_nn) / total,
        'nearest_neighbor_mean_distance_m': stats_2.get('mean_distance_m', 0),
        'nearest_neighbor_max_distance_m': stats_2.get('max_distance_m', 0),
        'nearest_neighbor_median_distance_m': stats_2.get('median_distance_m', 0)
    }

    if verbose:
        print(f"\nFinal statistics:")
        print(f"  Total segments: {total}")
        print(f"  Intersection matched: {n_intersection} ({diagnostics['intersection_match_rate']:.1%})")
        print(f"  Nearest neighbor matched: {n_nn} ({diagnostics['nearest_neighbor_match_rate']:.1%})")
        print(f"  Synthetic IDs: {n_synthetic} ({diagnostics['synthetic_rate']:.1%})")
        print(f"  Overall OSM match rate: {diagnostics['overall_osm_match_rate']:.1%}")

        if diagnostics['overall_osm_match_rate'] >= MATCHING_PARAMS['target_match_rate']:
            print(f"  ✓ Target match rate achieved ({MATCHING_PARAMS['target_match_rate']:.1%})")
        else:
            print(f"  ⚠ Below target match rate ({MATCHING_PARAMS['target_match_rate']:.1%})")

        if n_nn > 0:
            if diagnostics['nearest_neighbor_mean_distance_m'] <= MATCHING_PARAMS['max_mean_distance_m']:
                print(f"  ✓ Mean NN distance within target "
                      f"({MATCHING_PARAMS['max_mean_distance_m']}m)")
            else:
                print(f"  ⚠ Mean NN distance exceeds target "
                      f"({MATCHING_PARAMS['max_mean_distance_m']}m)")

    return all_matched, diagnostics
