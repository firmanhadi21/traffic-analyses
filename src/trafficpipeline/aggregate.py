"""
Time-period aggregation of raw traffic GeoPackage snapshots.

Uses OSM-based segment matching for stable segment identity across
time periods.  Each HERE segment is mapped to an ``osm_composite_id``
via geometry hashing + spatial-join fallback, replacing the legacy
row-index-based ``fid`` which was unstable across snapshots.
"""

from __future__ import annotations

import glob
import hashlib
import os
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import warnings

from trafficpipeline.config import (
    CITIES,
    TIME_PERIODS,
    get_time_period,
    traffic_data_path,
    traffic_output_path,
)

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# OSM mapping dates (when OSM reference networks were built)
# ---------------------------------------------------------------------------
_MAPPING_DATES = {
    "smg": "20260202",
    "bdg": "20260203",
    "jkt": "20260320",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_timestamp(filename: str) -> datetime | None:
    """Extract timestamp from ``city_traffic_YYYYMMDD_HHMMSS.gpkg``."""
    try:
        base = os.path.splitext(os.path.basename(filename))[0]
        parts = base.split("_")
        return datetime.strptime(f"{parts[2]}_{parts[3]}", "%Y%m%d_%H%M%S")
    except Exception:
        return None


def _geom_wkb_hash(geom) -> str:
    """Compute MD5 hash of geometry WKB for O(1) lookup."""
    return hashlib.md5(geom.wkb).hexdigest()


def _load_osm_mapping(city_code: str, base_dir: Path):
    """Load OSM mapping table and reference geometry.

    Returns (osm_ref_gdf, wkt_hash_mapping, create_geometry_hash_fn).
    """
    # Import the root-level utils for WKT-based geometry hashing
    import importlib.util
    utils_path = base_dir / "utils.py"
    if utils_path.exists():
        spec = importlib.util.spec_from_file_location("utils", utils_path)
        utils_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils_mod)
        create_geometry_hash = utils_mod.create_geometry_hash
    else:
        # Fallback: inline implementation
        import re as _re

        def create_geometry_hash(geometry, precision=6):
            wkt_str = geometry.wkt

            def round_number(match):
                return f"{float(match.group(0)):.{precision}f}"

            rounded = _re.sub(r'-?\d+\.\d+', round_number, wkt_str)
            return hashlib.md5(rounded.encode()).hexdigest()

    mapping_date = _MAPPING_DATES.get(city_code)
    if not mapping_date:
        raise FileNotFoundError(
            f"No OSM mapping date configured for city '{city_code}'"
        )

    mapping_path = base_dir / "osm_reference" / f"{city_code}_here_to_osm_mapping_{mapping_date}.csv"
    osm_ref_path = base_dir / "osm_reference" / f"{city_code}_osm_reference_{mapping_date}.gpkg"

    if not mapping_path.exists():
        raise FileNotFoundError(
            f"OSM mapping not found: {mapping_path}\n"
            f"Run: python osm_network_builder.py --city {city_code} --date {mapping_date}\n"
            f"Then: python create_here_osm_mapping.py --city {city_code} --date {mapping_date}"
        )
    if not osm_ref_path.exists():
        raise FileNotFoundError(f"OSM reference not found: {osm_ref_path}")

    mapping_df = pd.read_csv(mapping_path)
    wkt_hash_mapping = dict(zip(
        mapping_df['here_geometry_hash'],
        mapping_df['osm_composite_id']
    ))

    osm_ref_gdf = gpd.read_file(osm_ref_path)
    return osm_ref_gdf, wkt_hash_mapping, create_geometry_hash


def _build_wkb_cache(raw_gdf, osm_ref_gdf, wkt_hash_mapping, create_geometry_hash_fn):
    """Build WKB-hash → osm_composite_id cache from a raw snapshot."""
    cache = {}
    wkt_hashes = raw_gdf.geometry.apply(create_geometry_hash_fn)
    wkb_hashes = raw_gdf.geometry.apply(_geom_wkb_hash)
    osm_ids = wkt_hashes.map(wkt_hash_mapping)

    matched = osm_ids.notna()
    for wkb_h, osm_id in zip(wkb_hashes[matched], osm_ids[matched]):
        cache[wkb_h] = osm_id

    # Spatial-join fallback for unmatched
    unmatched = raw_gdf[~matched]
    if len(unmatched) > 0:
        osm_for_join = osm_ref_gdf[['osm_composite_id', 'geometry']].copy()
        if unmatched.crs and osm_for_join.crs and unmatched.crs != osm_for_join.crs:
            unmatched = unmatched.to_crs(osm_for_join.crs)
        joined = gpd.sjoin_nearest(
            unmatched[['geometry']].copy(), osm_for_join,
            how='left', max_distance=0.001,
        )
        joined = joined[~joined.index.duplicated(keep='first')]
        valid = joined['osm_composite_id'].notna()
        unmatched_wkb = unmatched.geometry.apply(_geom_wkb_hash)
        for idx in joined[valid].index:
            cache[unmatched_wkb.loc[idx]] = joined.loc[idx, 'osm_composite_id']

    return cache


def _assign_osm_ids(gdf, wkb_cache, osm_ref_gdf):
    """Assign osm_composite_id to a raw GeoDataFrame via WKB hash cache."""
    gdf = gdf.copy()
    wkb_hashes = gdf.geometry.apply(_geom_wkb_hash)
    gdf['_wkb'] = wkb_hashes
    gdf['osm_composite_id'] = wkb_hashes.map(wkb_cache)

    uncached = gdf['osm_composite_id'].isna()
    if uncached.any():
        osm_for_join = osm_ref_gdf[['osm_composite_id', 'geometry']].copy()
        sub = gdf.loc[uncached]
        if sub.crs and osm_for_join.crs and sub.crs != osm_for_join.crs:
            sub = sub.to_crs(osm_for_join.crs)
        joined = gpd.sjoin_nearest(
            sub[['geometry', '_wkb']].copy(), osm_for_join,
            how='left', max_distance=0.001,
        )
        joined = joined[~joined.index.duplicated(keep='first')]
        valid = joined['osm_composite_id'].notna()
        for idx in joined[valid].index:
            wkb_cache[joined.loc[idx, '_wkb']] = joined.loc[idx, 'osm_composite_id']
            gdf.loc[idx, 'osm_composite_id'] = joined.loc[idx, 'osm_composite_id']

    gdf = gdf.drop(columns=['_wkb'])
    return gdf


def _read_snapshot_osm(
    filepath: str | Path,
    column: str,
    wkb_cache: dict,
    osm_ref_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame | None:
    """Read snapshot, assign OSM IDs, return osm_composite_id + traffic column."""
    try:
        gdf = gpd.read_file(filepath)
        if column not in gdf.columns:
            return None
        gdf = _assign_osm_ids(gdf, wkb_cache, osm_ref_gdf)
        gdf = gdf.dropna(subset=['osm_composite_id'])
        return gdf[['osm_composite_id', column]].copy()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregate_city(
    city_code: str,
    traffic_column: str = "jam_factor",
    *,
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    base_dir: str | Path | None = None,
    verbose: bool = True,
) -> dict[str, gpd.GeoDataFrame]:
    """Aggregate raw traffic snapshots into per-time-period GeoPackages.

    Uses OSM-based segment matching for stable segment identity.

    Parameters
    ----------
    city_code : str
        One of ``'smg'``, ``'bdg'``, ``'jkt'``.
    traffic_column : str
        Column in the raw snapshots to aggregate (default ``'jam_factor'``).
    data_dir : path-like, optional
        Override for the raw-data folder.
    output_dir : path-like, optional
        Override for the output folder.
    base_dir : path-like, optional
        Project root (where ``osm_reference/`` lives). Defaults to ``"."``.
    verbose : bool
        Print progress messages.

    Returns
    -------
    dict[str, GeoDataFrame]
        Mapping from time-period name to the aggregated GeoDataFrame.
    """
    city = CITIES[city_code]
    base = Path(base_dir) if base_dir else Path(".")

    src = Path(data_dir) if data_dir else traffic_data_path(city_code)
    dst = Path(output_dir) if output_dir else traffic_output_path(city_code)
    dst.mkdir(parents=True, exist_ok=True)

    gpkg_files = sorted(glob.glob(str(src / "*.gpkg")))
    if not gpkg_files:
        raise FileNotFoundError(f"No .gpkg files in {src}")

    if verbose:
        print(f"[{city['name']}] Found {len(gpkg_files)} snapshots")
        print(f"  Range: {os.path.basename(gpkg_files[0])} → {os.path.basename(gpkg_files[-1])}")

    # Load OSM mapping and reference geometry
    if verbose:
        print(f"  Loading OSM mapping...")
    osm_ref_gdf, wkt_hash_mapping, create_geom_hash = _load_osm_mapping(city_code, base)
    if verbose:
        print(f"  OSM segments: {len(osm_ref_gdf)}, mapping entries: {len(wkt_hash_mapping)}")

    # Build WKB hash cache from first raw file
    if verbose:
        print(f"  Building geometry hash cache...")
    first_raw = gpd.read_file(gpkg_files[0])
    wkb_cache = _build_wkb_cache(first_raw, osm_ref_gdf, wkt_hash_mapping, create_geom_hash)
    if verbose:
        print(f"  Cache: {len(wkb_cache)} WKB→OSM mappings")

    # Read all snapshots with OSM ID assignment
    frames: list[pd.DataFrame] = []
    for i, fp in enumerate(gpkg_files, 1):
        if verbose and i % 500 == 0:
            print(f"  Reading {i}/{len(gpkg_files)} …")
        df = _read_snapshot_osm(fp, traffic_column, wkb_cache, osm_ref_gdf)
        if df is None:
            continue
        ts = _extract_timestamp(fp)
        if ts is None:
            continue
        df["timestamp"] = ts
        frames.append(df[["osm_composite_id", traffic_column, "timestamp"]])

    if not frames:
        raise RuntimeError("No valid data read")

    combined = pd.concat(frames, ignore_index=True)
    combined["hour"] = combined["timestamp"].dt.hour
    combined["time_period"] = combined["hour"].apply(get_time_period)

    if verbose:
        print(f"  Combined records: {len(combined):,}")
        print(f"  Date range: {combined['timestamp'].min()} → {combined['timestamp'].max()}")

    # Reference geometry for output
    osm_geom = osm_ref_gdf.set_index('osm_composite_id')[['geometry']]

    # Aggregate per time period
    results: dict[str, gpd.GeoDataFrame] = {}
    for period in sorted(combined["time_period"].unique()):
        subset = combined[combined["time_period"] == period]
        stats = (
            subset.groupby("osm_composite_id")[traffic_column]
            .agg(["mean", "std", "count", "min", "max"])
            .round(4)
            .reset_index()
        )
        stats.columns = [
            "osm_composite_id",
            f"{traffic_column}_mean",
            f"{traffic_column}_std",
            f"{traffic_column}_count",
            f"{traffic_column}_min",
            f"{traffic_column}_max",
        ]

        # Join with OSM geometry
        gdf = stats.merge(osm_geom, left_on='osm_composite_id', right_index=True, how='left')
        gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=osm_ref_gdf.crs)
        gdf = gdf.dropna(subset=['geometry'])

        out_path = dst / f"{period}_{city_code}.gpkg"
        gdf.to_file(out_path, driver="GPKG")
        results[period] = gdf

        if verbose:
            means = stats[f"{traffic_column}_mean"]
            print(
                f"  {period}: {len(subset):,} records → "
                f"mean={means.mean():.4f}, "
                f"segments={len(gdf)}  ✓ saved"
            )

    if verbose:
        print(f"[{city['name']}] Aggregation complete — {len(results)} periods saved to {dst}/")

    return results


def aggregate_all(
    traffic_column: str = "jam_factor",
    *,
    verbose: bool = True,
) -> dict[str, dict[str, gpd.GeoDataFrame]]:
    """Run :func:`aggregate_city` for every city in the config.

    Returns nested dict ``{city_code: {period: GeoDataFrame}}``.
    """
    all_results: dict[str, dict[str, gpd.GeoDataFrame]] = {}
    for code in CITIES:
        try:
            all_results[code] = aggregate_city(code, traffic_column, verbose=verbose)
        except Exception as exc:
            print(f"[{CITIES[code]['name']}] FAILED: {exc}")
    return all_results
