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
    # Import the root-level utils for WKT-based geometry hashing.
    # The legacy utils.py does `from config import TIMEZONE`, so the
    # project base_dir must be on sys.path while it loads.
    import importlib.util
    import sys as _sys
    utils_path = base_dir / "utils.py"
    if utils_path.exists():
        base_str = str(base_dir.resolve())
        added_path = base_str not in _sys.path
        if added_path:
            _sys.path.insert(0, base_str)
        try:
            spec = importlib.util.spec_from_file_location("utils", utils_path)
            utils_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(utils_mod)
            create_geometry_hash = utils_mod.create_geometry_hash
        finally:
            if added_path:
                _sys.path.remove(base_str)
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
    columns: str | list[str] | tuple[str, ...],
    wkb_cache: dict,
    osm_ref_gdf: gpd.GeoDataFrame,
    skip_reasons: dict | None = None,
) -> pd.DataFrame | None:
    """Read snapshot, assign OSM IDs, return osm_composite_id + requested column(s).

    Parameters
    ----------
    columns
        A single column name or a list of column names to extract. The
        snapshot is dropped if ANY of the listed columns is missing.

    When ``skip_reasons`` (a dict) is supplied, increments the appropriate
    counter (``missing_column``, ``read_error``, ``no_osm_match``,
    ``empty_after_dropna``) and records the first offending filename per
    reason in ``skip_reasons[<reason>+'_first']``.
    """
    if isinstance(columns, str):
        cols = [columns]
    else:
        cols = list(columns)

    def _note(reason: str, detail: str | None = None) -> None:
        if skip_reasons is None:
            return
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        key = reason + "_first"
        if key not in skip_reasons:
            skip_reasons[key] = (str(filepath), detail)

    try:
        gdf = gpd.read_file(filepath)
    except Exception as e:
        _note("read_error", f"{type(e).__name__}: {e}")
        return None

    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        _note(
            "missing_column",
            f"missing {missing}; have {sorted(gdf.columns)[:8]}",
        )
        return None

    try:
        gdf = _assign_osm_ids(gdf, wkb_cache, osm_ref_gdf)
    except Exception as e:
        _note("read_error", f"_assign_osm_ids failed: {type(e).__name__}: {e}")
        return None

    if "osm_composite_id" not in gdf.columns:
        _note("no_osm_match", "osm_composite_id column missing after assign")
        return None

    matched = gdf.dropna(subset=["osm_composite_id"])
    if len(matched) == 0:
        _note(
            "empty_after_dropna",
            f"loaded {len(gdf)} rows but all osm_composite_id were null",
        )
        return None

    return matched[["osm_composite_id"] + cols].copy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregate_city(
    city_code: str,
    traffic_column: str | list[str] | tuple[str, ...] = (
        "jam_factor", "speed", "free_flow",
    ),
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

    # Normalise traffic_column → list[str] (preserves backward compat
    # for callers passing a single string).
    if isinstance(traffic_column, str):
        traffic_columns: list[str] = [traffic_column]
    else:
        traffic_columns = list(traffic_column)

    gpkg_files = sorted(glob.glob(str(src / "*.gpkg")))
    if not gpkg_files:
        raise FileNotFoundError(f"No .gpkg files in {src}")

    if verbose:
        print(f"[{city['name']}] Found {len(gpkg_files)} snapshots")
        print(f"  Range: {os.path.basename(gpkg_files[0])} → {os.path.basename(gpkg_files[-1])}")
        print(f"  Aggregating columns: {traffic_columns}")

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
    skip_reasons: dict = {}
    n_bad_timestamp = 0
    bad_timestamp_first: str | None = None
    for i, fp in enumerate(gpkg_files, 1):
        if verbose and i % 500 == 0:
            print(f"  Reading {i}/{len(gpkg_files)} …")
        df = _read_snapshot_osm(
            fp, traffic_columns, wkb_cache, osm_ref_gdf, skip_reasons=skip_reasons,
        )
        if df is None:
            continue
        ts = _extract_timestamp(fp)
        if ts is None:
            n_bad_timestamp += 1
            if bad_timestamp_first is None:
                bad_timestamp_first = os.path.basename(str(fp))
            continue
        df["timestamp"] = ts
        frames.append(df[["osm_composite_id", *traffic_columns, "timestamp"]])

    if verbose and (skip_reasons or n_bad_timestamp):
        print(f"  Skipped snapshots:")
        for reason in ("read_error", "missing_column", "no_osm_match",
                       "empty_after_dropna"):
            n = skip_reasons.get(reason, 0)
            if n:
                fname, detail = skip_reasons.get(reason + "_first", ("?", "?"))
                print(f"    {reason}: {n} (first: {os.path.basename(fname)} — {detail})")
        if n_bad_timestamp:
            print(f"    bad_filename_timestamp: {n_bad_timestamp} "
                  f"(first: {bad_timestamp_first})")

    if not frames:
        diag = [f"{r}={skip_reasons.get(r, 0)}" for r in
                ("read_error", "missing_column", "no_osm_match",
                 "empty_after_dropna")]
        if n_bad_timestamp:
            diag.append(f"bad_filename_timestamp={n_bad_timestamp}")
        # Surface the very first failure detail for fast diagnosis.
        for reason in ("missing_column", "read_error", "no_osm_match",
                       "empty_after_dropna"):
            first = skip_reasons.get(reason + "_first")
            if first:
                fname, detail = first
                raise RuntimeError(
                    f"No valid data read. Counts: {', '.join(diag)}. "
                    f"First {reason} in {os.path.basename(fname)}: {detail}"
                )
        raise RuntimeError(
            f"No valid data read. Counts: {', '.join(diag)}. "
            f"First bad-timestamp filename: {bad_timestamp_first}"
        )

    combined = pd.concat(frames, ignore_index=True)
    combined["hour"] = combined["timestamp"].dt.hour
    combined["time_period"] = combined["hour"].apply(get_time_period)

    if verbose:
        print(f"  Combined records: {len(combined):,}")
        print(f"  Date range: {combined['timestamp'].min()} → {combined['timestamp'].max()}")

    # Reference geometry for output
    osm_geom = osm_ref_gdf.set_index('osm_composite_id')[['geometry']]

    # Aggregate per time period (one combined GeoPackage per period,
    # with mean/std/count/min/max columns for every traffic column).
    results: dict[str, gpd.GeoDataFrame] = {}
    for period in sorted(combined["time_period"].unique()):
        subset = combined[combined["time_period"] == period]

        # Compute mean/std/count/min/max for each requested column.
        agg_spec = {col: ["mean", "std", "count", "min", "max"]
                    for col in traffic_columns}
        stats = (
            subset.groupby("osm_composite_id")
                  .agg(agg_spec)
                  .round(4)
                  .reset_index()
        )
        # Flatten MultiIndex columns: ('jam_factor', 'mean') → 'jam_factor_mean'
        flat_cols = ["osm_composite_id"]
        for col in traffic_columns:
            flat_cols.extend(f"{col}_{stat}" for stat in
                             ["mean", "std", "count", "min", "max"])
        stats.columns = flat_cols

        # Join with OSM geometry
        gdf = stats.merge(osm_geom, left_on='osm_composite_id', right_index=True, how='left')
        gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=osm_ref_gdf.crs)
        gdf = gdf.dropna(subset=['geometry'])

        out_path = dst / f"{period}_{city_code}.gpkg"
        gdf.to_file(out_path, driver="GPKG")
        results[period] = gdf

        if verbose:
            primary = traffic_columns[0]
            means = stats[f"{primary}_mean"]
            extra = f" + {len(traffic_columns)-1} more cols" if len(traffic_columns) > 1 else ""
            print(
                f"  {period}: {len(subset):,} records → "
                f"{primary}_mean={means.mean():.4f}{extra}, "
                f"segments={len(gdf)}  ✓ saved"
            )

    if verbose:
        print(f"[{city['name']}] Aggregation complete — {len(results)} periods saved to {dst}/")

    return results


def aggregate_all(
    traffic_column: str | list[str] | tuple[str, ...] = (
        "jam_factor", "speed", "free_flow",
    ),
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
