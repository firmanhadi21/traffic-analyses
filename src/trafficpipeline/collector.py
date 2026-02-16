"""
Pure-Python HERE Traffic Flow v7 data collector.

Replaces the R-based collector (``traffic_collector.R`` + ``hereR::flow()``)
with a direct REST-API client.  Produces identically-formatted GeoPackage
files that are backwards-compatible with the existing aggregation pipeline.

Usage (library)::

    from trafficpipeline.collector import HERETrafficCollector

    collector = HERETrafficCollector(api_key="...", bbox=(west, south, east, north))
    gdf = collector.fetch_flow()

Usage (CLI)::

    traffic-pipeline collect --city smg --api-key $HERE_API_KEY --once
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString

from trafficpipeline.config import CITIES, CRS, TIMEZONE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HERE Traffic Flow v7 endpoint
# ---------------------------------------------------------------------------
_BASE_URL = "https://data.traffic.hereapi.com/v7/flow"

# Maximum retries and backoff parameters
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 2  # seconds


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------
class HERETrafficCollector:
    """Client for the HERE Traffic Flow v7 REST API.

    Parameters
    ----------
    api_key : str
        HERE platform API key.
    bbox : tuple[float, float, float, float]
        Bounding box as ``(west, south, east, north)`` in WGS-84.
    """

    def __init__(self, api_key: str, bbox: tuple[float, float, float, float]) -> None:
        self.api_key = api_key
        self.bbox = bbox  # (west, south, east, north)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_flow(self) -> gpd.GeoDataFrame:
        """Fetch traffic-flow data and return a :class:`GeoDataFrame`.

        The returned frame contains one row per road segment with columns:

        * ``jam_factor``  – normalised congestion 0 (free) … 10 (standstill)
        * ``speed``       – current speed in km/h
        * ``free_flow``   – free-flow speed in km/h
        * ``speed_uncapped`` – speed without legal-limit cap (km/h)
        * ``confidence``  – data-quality indicator (0–1)
        * ``traversability`` – road traversability status
        * ``geometry``    – ``LineString`` of the road segment
        * ``timestamp``   – collection time (UTC)

        Raises
        ------
        RuntimeError
            If the API request fails after all retries.
        """
        west, south, east, north = self.bbox
        params = {
            "in": f"bbox:{west},{south},{east},{north}",
            "locationReferencing": "shape",
            "apiKey": self.api_key,
        }

        data: dict[str, Any] | None = None
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.get(_BASE_URL, params=params, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    wait = _INITIAL_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "HERE API attempt %d/%d failed (%s), retrying in %ds …",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    time.sleep(wait)

        if data is None:
            raise RuntimeError(
                f"HERE API request failed after {_MAX_RETRIES} attempts: {last_error}"
            )

        return self._parse_response(data)

    # ------------------------------------------------------------------ #
    # Response parsing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> gpd.GeoDataFrame:
        """Flatten nested HERE v7 JSON into a flat GeoDataFrame.

        The HERE v7 ``/flow`` response has the structure::

            {
              "results": [
                {
                  "location": {
                    "shape": {
                      "links": [
                        {
                          "points": [{"lat": ..., "lng": ...}, ...],
                          "length": ...
                        }
                      ]
                    }
                  },
                  "currentFlow": {
                    "speed": ...,
                    "freeFlow": ...,
                    "jamFactor": ...,
                    "speedUncapped": ...,
                    "confidence": ...,
                    "traversability": ...
                  }
                },
                ...
              ]
            }
        """
        rows: list[dict[str, Any]] = []
        now = datetime.now()

        for result in data.get("results", []):
            flow = result.get("currentFlow", {})
            location = result.get("location", {})
            shape = location.get("shape", {})
            links = shape.get("links", [])

            # Extract flow metrics
            jam_factor = flow.get("jamFactor")
            speed = flow.get("speed")
            free_flow = flow.get("freeFlow")
            speed_uncapped = flow.get("speedUncapped")
            confidence = flow.get("confidence")
            traversability = flow.get("traversability", "")

            # Each result may contain one or more shape links
            for link in links:
                points = link.get("points", [])
                if len(points) < 2:
                    continue

                coords = [(p["lng"], p["lat"]) for p in points]
                geom = LineString(coords)

                rows.append(
                    {
                        "jam_factor": jam_factor,
                        "speed": speed,
                        "free_flow": free_flow,
                        "speed_uncapped": speed_uncapped,
                        "confidence": confidence,
                        "traversability": traversability,
                        "length_m": link.get("length"),
                        "timestamp": now,
                        "geometry": geom,
                    }
                )

        if not rows:
            logger.warning("HERE API returned 0 road segments")
            return gpd.GeoDataFrame(
                columns=[
                    "jam_factor",
                    "speed",
                    "free_flow",
                    "speed_uncapped",
                    "confidence",
                    "traversability",
                    "length_m",
                    "timestamp",
                    "geometry",
                ],
                geometry="geometry",
                crs=CRS,
            )

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        logger.info("Fetched %d road segments", len(gdf))
        return gdf


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def collect_single(
    city_code: str,
    api_key: str,
    output_dir: str | Path | None = None,
) -> Path:
    """Collect a single snapshot for one city and save as GeoPackage.

    Parameters
    ----------
    city_code : str
        One of ``"smg"``, ``"bdg"``, ``"jkt"`` (or any key in ``CITIES``).
    api_key : str
        HERE platform API key.
    output_dir : str or Path, optional
        Override the default output directory.

    Returns
    -------
    Path
        Path to the created GeoPackage file.
    """
    city = CITIES[city_code]
    bbox = city["bbox"]

    if output_dir is None:
        output_dir = Path(city["traffic_data_dir"])
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    collector = HERETrafficCollector(api_key=api_key, bbox=bbox)
    gdf = collector.fetch_flow()

    # Filename matches the R pattern: {city}_traffic_YYYYMMDD_HHMMSS.gpkg
    import pytz

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    city_prefix = city["filename_pattern"].split("_traffic_")[0]
    filename = f"{city_prefix}_traffic_{timestamp}.gpkg"
    outpath = output_dir / filename

    gdf.to_file(outpath, driver="GPKG")
    logger.info("Saved %d segments → %s", len(gdf), outpath)

    return outpath


def collect_all(
    api_key: str,
    city_codes: list[str] | None = None,
    output_base: str | Path | None = None,
) -> list[Path]:
    """Collect snapshots for multiple cities.

    Parameters
    ----------
    api_key : str
        HERE platform API key.
    city_codes : list of str, optional
        City codes to collect; defaults to all configured cities.
    output_base : str or Path, optional
        Base directory; city sub-directories are created underneath.

    Returns
    -------
    list of Path
        Paths to the created GeoPackage files.
    """
    if city_codes is None:
        city_codes = list(CITIES.keys())

    paths: list[Path] = []
    for code in city_codes:
        out_dir = None
        if output_base is not None:
            out_dir = Path(output_base) / CITIES[code]["traffic_data_dir"]
        try:
            path = collect_single(code, api_key, output_dir=out_dir)
            paths.append(path)
        except Exception:
            logger.exception("Failed to collect %s", code)

    return paths
