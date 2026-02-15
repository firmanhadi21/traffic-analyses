"""
Time-period aggregation of raw traffic GeoPackage snapshots.

This module replaces the three city-specific aggregation scripts
(``run_semarang_aggregation.py``, ``run_bandung_aggregation.py``,
``run_jakarta_aggregation.py``) with a single, parameterized function.
"""

from __future__ import annotations

import glob
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


def _reference_geometry(filepath: str | Path) -> gpd.GeoDataFrame | None:
    """Load reference geometry (fid + geometry) from the first snapshot."""
    try:
        gdf = gpd.read_file(filepath)
        if "fid" not in gdf.columns:
            gdf["fid"] = range(1, len(gdf) + 1)
        return gdf[["fid", "geometry"]].copy()
    except Exception as exc:
        print(f"  Error loading reference geometry: {exc}")
        return None


def _read_snapshot(filepath: str | Path, column: str) -> pd.DataFrame | None:
    """Read a single GeoPackage and return fid + traffic column."""
    try:
        gdf = gpd.read_file(filepath)
        if "fid" not in gdf.columns:
            gdf["fid"] = range(1, len(gdf) + 1)
        return gdf[["fid", column]].copy()
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
    verbose: bool = True,
) -> dict[str, gpd.GeoDataFrame]:
    """Aggregate raw traffic snapshots into per-time-period GeoPackages.

    Parameters
    ----------
    city_code : str
        One of ``'smg'``, ``'bdg'``, ``'jkt'`` (or any key in
        :data:`trafficpipeline.config.CITIES`).
    traffic_column : str
        Column in the raw snapshots to aggregate (default ``'jam_factor'``).
    data_dir : path-like, optional
        Override for the raw-data folder.  Defaults to the path defined
        in :data:`trafficpipeline.config.CITIES`.
    output_dir : path-like, optional
        Override for the output folder.  Defaults to
        ``traffic_{code}_output/``.
    verbose : bool
        Print progress messages.

    Returns
    -------
    dict[str, GeoDataFrame]
        Mapping from time-period name to the aggregated GeoDataFrame.
    """
    city = CITIES[city_code]

    src = Path(data_dir) if data_dir else traffic_data_path(city_code)
    dst = Path(output_dir) if output_dir else traffic_output_path(city_code)
    dst.mkdir(parents=True, exist_ok=True)

    gpkg_files = sorted(glob.glob(str(src / "*.gpkg")))
    if not gpkg_files:
        raise FileNotFoundError(f"No .gpkg files in {src}")

    if verbose:
        print(f"[{city['name']}] Found {len(gpkg_files)} snapshots")
        print(f"  Range: {os.path.basename(gpkg_files[0])} → {os.path.basename(gpkg_files[-1])}")

    # Reference geometry from first file
    ref = _reference_geometry(gpkg_files[0])
    if ref is None:
        raise RuntimeError("Could not load reference geometry")
    if verbose:
        print(f"  Reference segments: {len(ref)}")

    # Read all snapshots
    frames: list[pd.DataFrame] = []
    for i, fp in enumerate(gpkg_files, 1):
        if verbose and i % 500 == 0:
            print(f"  Reading {i}/{len(gpkg_files)} …")
        df = _read_snapshot(fp, traffic_column)
        if df is None:
            continue
        ts = _extract_timestamp(fp)
        if ts is None:
            continue
        df["timestamp"] = ts
        frames.append(df[["fid", traffic_column, "timestamp"]])

    if not frames:
        raise RuntimeError("No valid data read")

    combined = pd.concat(frames, ignore_index=True)
    combined["hour"] = combined["timestamp"].dt.hour
    combined["time_period"] = combined["hour"].apply(get_time_period)

    if verbose:
        print(f"  Combined records: {len(combined):,}")
        print(f"  Date range: {combined['timestamp'].min()} → {combined['timestamp'].max()}")

    # Aggregate per time period
    results: dict[str, gpd.GeoDataFrame] = {}
    for period in sorted(combined["time_period"].unique()):
        subset = combined[combined["time_period"] == period]
        stats = (
            subset.groupby("fid")[traffic_column]
            .agg(["mean", "std", "count", "min", "max"])
            .round(4)
            .reset_index()
        )
        stats.columns = [
            "fid",
            f"{traffic_column}_mean",
            f"{traffic_column}_std",
            f"{traffic_column}_count",
            f"{traffic_column}_min",
            f"{traffic_column}_max",
        ]

        gdf = ref.merge(stats, on="fid", how="left")
        out_path = dst / f"{period}_{city_code}.gpkg"
        gdf.to_file(out_path, driver="GPKG")
        results[period] = gdf

        if verbose:
            means = stats[f"{traffic_column}_mean"]
            valid = gdf[f"{traffic_column}_mean"].notna().sum()
            print(
                f"  {period}: {len(subset):,} records → "
                f"mean={means.mean():.4f}, "
                f"segments w/ data={valid}/{len(gdf)}  ✓ saved"
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
