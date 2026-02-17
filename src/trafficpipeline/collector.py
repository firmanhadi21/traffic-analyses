"""
Multi-provider traffic flow data collector.

Supports HERE, TomTom, and Google (experimental) traffic APIs through a
unified provider interface.  All providers produce the same core
GeoDataFrame schema so that downstream analysis scripts work unchanged.

Usage (library)::

    from trafficpipeline.collector import get_provider

    provider = get_provider("here", api_key="...")
    gdf = provider.fetch_flow(bbox=(west, south, east, north))

    provider = get_provider("tomtom", api_key="...")
    gdf = provider.fetch_flow(bbox=(west, south, east, north))

Usage (CLI)::

    traffic-pipeline collect --provider here   --api-key $HERE_API_KEY --once
    traffic-pipeline collect --provider tomtom --api-key $TOMTOM_API_KEY --once
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString, Point

from trafficpipeline.config import CITIES, CRS, TIMEZONE

logger = logging.getLogger(__name__)

# Common retry parameters
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds

# Standard output columns (all providers must produce at least these)
STANDARD_COLUMNS = [
    "jam_factor",
    "speed",
    "free_flow",
    "confidence",
    "geometry",
    "timestamp",
    "provider",
]


# ═══════════════════════════════════════════════════════════════════════════
# Abstract base class
# ═══════════════════════════════════════════════════════════════════════════


class TrafficProvider(ABC):
    """Abstract base class for traffic data providers.

    Subclasses must implement :meth:`fetch_flow` and the :attr:`name`
    property.  The returned GeoDataFrame must contain at minimum the
    columns listed in :data:`STANDARD_COLUMNS`.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider identifier (e.g. ``'here'``, ``'tomtom'``)."""

    @abstractmethod
    def fetch_flow(
        self, bbox: tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        """Fetch traffic-flow data for a bounding box.

        Parameters
        ----------
        bbox : tuple[float, float, float, float]
            ``(west, south, east, north)`` in WGS-84.

        Returns
        -------
        GeoDataFrame
            One row per road segment with at least the standard columns.
        """

    # ── helpers available to all providers ─────────────────────────────

    @staticmethod
    def _empty_gdf(extra_columns: list[str] | None = None) -> gpd.GeoDataFrame:
        """Return an empty GeoDataFrame with the standard schema."""
        cols = list(STANDARD_COLUMNS)
        if extra_columns:
            cols.extend(extra_columns)
        return gpd.GeoDataFrame(
            columns=cols, geometry="geometry", crs=CRS,
        )

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = MAX_RETRIES,
        **kwargs: Any,
    ) -> requests.Response:
        """HTTP request with exponential-backoff retry.

        Parameters
        ----------
        method : str
            HTTP method (``"GET"`` or ``"POST"``).
        url : str
            Request URL.
        max_retries : int
            Maximum attempts.
        **kwargs
            Passed to :func:`requests.request`.

        Returns
        -------
        requests.Response

        Raises
        ------
        RuntimeError
            If all retries are exhausted.
        """
        kwargs.setdefault("timeout", 120)
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_error = exc
                if attempt < max_retries:
                    wait = INITIAL_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "%s API attempt %d/%d failed (%s), retrying in %ds …",
                        self.name,
                        attempt,
                        max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)

        raise RuntimeError(
            f"{self.name} API request failed after {max_retries} attempts: "
            f"{last_error}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# HERE Traffic Flow v7
# ═══════════════════════════════════════════════════════════════════════════


class HEREProvider(TrafficProvider):
    """HERE Traffic Flow v7 REST API provider.

    Calls ``https://data.traffic.hereapi.com/v7/flow`` with bounding-box
    queries and returns one row per road segment.  This is the reference
    provider and produces the richest output.
    """

    _URL = "https://data.traffic.hereapi.com/v7/flow"

    @property
    def name(self) -> str:
        return "here"

    def fetch_flow(
        self, bbox: tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        west, south, east, north = bbox
        params = {
            "in": f"bbox:{west},{south},{east},{north}",
            "locationReferencing": "shape",
            "apiKey": self.api_key,
        }

        resp = self._request_with_retry("GET", self._URL, params=params)
        return self._parse_response(resp.json())

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> gpd.GeoDataFrame:
        """Flatten nested HERE v7 JSON into a flat GeoDataFrame."""
        rows: list[dict[str, Any]] = []
        now = datetime.now()

        for result in data.get("results", []):
            flow = result.get("currentFlow", {})
            location = result.get("location", {})
            shape = location.get("shape", {})
            links = shape.get("links", [])

            jam_factor = flow.get("jamFactor")
            speed = flow.get("speed")
            free_flow = flow.get("freeFlow")
            speed_uncapped = flow.get("speedUncapped")
            confidence = flow.get("confidence")
            traversability = flow.get("traversability", "")

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
                        "provider": "here",
                        "geometry": geom,
                    }
                )

        if not rows:
            logger.warning("HERE API returned 0 road segments")
            return TrafficProvider._empty_gdf(
                ["speed_uncapped", "traversability", "length_m"]
            )

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        logger.info("HERE: fetched %d road segments", len(gdf))
        return gdf


# ═══════════════════════════════════════════════════════════════════════════
# TomTom Traffic Flow
# ═══════════════════════════════════════════════════════════════════════════


class TomTomProvider(TrafficProvider):
    """TomTom Flow Segment Data API provider.

    TomTom does not offer a bounding-box flow endpoint.  Instead, the
    Flow Segment Data service returns data for the road segment nearest
    to a query point.  This provider grids the bbox at configurable
    spacing (default 500 m) and deduplicates segments by geometry hash.

    API: ``https://api.tomtom.com/traffic/services/4/flowSegmentData/
    absolute/{zoom}/json``
    """

    _URL = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData"
        "/absolute/10/json"
    )

    def __init__(
        self,
        api_key: str,
        grid_spacing_m: float = 500,
        request_delay: float = 0.05,
    ) -> None:
        super().__init__(api_key)
        self.grid_spacing_m = grid_spacing_m
        self.request_delay = request_delay  # throttle between API calls

    @property
    def name(self) -> str:
        return "tomtom"

    def fetch_flow(
        self, bbox: tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        points = self._grid_points(bbox, self.grid_spacing_m)
        logger.info(
            "TomTom: querying %d grid points (%.0fm spacing)",
            len(points),
            self.grid_spacing_m,
        )

        seen_hashes: set[str] = set()
        rows: list[dict[str, Any]] = []
        now = datetime.now()

        for i, (lat, lng) in enumerate(points):
            if i > 0 and self.request_delay > 0:
                time.sleep(self.request_delay)

            try:
                resp = self._request_with_retry(
                    "GET",
                    self._URL,
                    params={
                        "point": f"{lat},{lng}",
                        "key": self.api_key,
                        "unit": "KMPH",
                        "openLr": "false",
                    },
                    max_retries=2,
                    timeout=30,
                )
                segment = resp.json().get("flowSegmentData", {})
            except Exception:
                continue

            coords_list = segment.get("coordinates", {}).get("coordinate", [])
            if len(coords_list) < 2:
                continue

            coords = [
                (c["longitude"], c["latitude"]) for c in coords_list
            ]
            geom = LineString(coords)

            # Deduplicate by geometry hash
            geom_hash = hashlib.md5(geom.wkb).hexdigest()
            if geom_hash in seen_hashes:
                continue
            seen_hashes.add(geom_hash)

            current_speed = segment.get("currentSpeed")
            free_flow_speed = segment.get("freeFlowSpeed")

            # Compute jam_factor: 10 * (1 - speed / free_flow)
            if current_speed is not None and free_flow_speed and free_flow_speed > 0:
                jam_factor = round(
                    10.0 * (1.0 - current_speed / free_flow_speed), 2
                )
                jam_factor = max(0.0, min(10.0, jam_factor))
            else:
                jam_factor = None

            rows.append(
                {
                    "jam_factor": jam_factor,
                    "speed": current_speed,
                    "free_flow": free_flow_speed,
                    "confidence": segment.get("confidence"),
                    "current_travel_time": segment.get("currentTravelTime"),
                    "free_flow_travel_time": segment.get("freeFlowTravelTime"),
                    "road_closure": segment.get("roadClosure", False),
                    "frc": segment.get("frc"),
                    "timestamp": now,
                    "provider": "tomtom",
                    "geometry": geom,
                }
            )

        if not rows:
            logger.warning("TomTom: 0 unique segments found")
            return self._empty_gdf()

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        logger.info(
            "TomTom: %d unique segments from %d queries",
            len(gdf),
            len(points),
        )
        return gdf

    @staticmethod
    def _grid_points(
        bbox: tuple[float, float, float, float],
        spacing_m: float,
    ) -> list[tuple[float, float]]:
        """Generate a grid of (lat, lng) points inside the bbox.

        Parameters
        ----------
        bbox : (west, south, east, north)
        spacing_m : approximate distance between points in metres.
        """
        west, south, east, north = bbox
        # Approximate degrees per metre at the bbox centre
        mid_lat = (south + north) / 2
        deg_per_m_lat = 1.0 / 111_320
        deg_per_m_lng = 1.0 / (111_320 * math.cos(math.radians(mid_lat)))

        step_lat = spacing_m * deg_per_m_lat
        step_lng = spacing_m * deg_per_m_lng

        lats = np.arange(south, north, step_lat)
        lngs = np.arange(west, east, step_lng)

        return [(lat, lng) for lat in lats for lng in lngs]


# ═══════════════════════════════════════════════════════════════════════════
# Google Routes API  (experimental)
# ═══════════════════════════════════════════════════════════════════════════


class GoogleProvider(TrafficProvider):
    """Google Routes API provider (experimental).

    Google does *not* offer raw bounding-box traffic-flow data.  This
    provider generates a grid of short routes across the bbox and
    extracts ``speedReadingIntervals`` from each.  Limitations:

    * Returns categorical speed (NORMAL / SLOW / TRAFFIC_JAM), not km/h.
    * ``jam_factor`` is approximated from categories.
    * ``speed`` and ``free_flow`` are **not available** (set to ``None``).
    * Coverage depends on route grid density.

    API: ``https://routes.googleapis.com/directions/v2:computeRoutes``
    """

    _URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    _SPEED_TO_JF = {
        "NORMAL": 1.0,
        "SLOW": 4.0,
        "TRAFFIC_JAM": 8.0,
    }

    def __init__(
        self,
        api_key: str,
        grid_spacing_m: float = 1000,
        route_length_m: float = 2000,
        request_delay: float = 0.1,
    ) -> None:
        super().__init__(api_key)
        self.grid_spacing_m = grid_spacing_m
        self.route_length_m = route_length_m
        self.request_delay = request_delay

    @property
    def name(self) -> str:
        return "google"

    def fetch_flow(
        self, bbox: tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        origins = TomTomProvider._grid_points(bbox, self.grid_spacing_m)
        logger.info(
            "Google (experimental): %d grid origins (%.0fm spacing)",
            len(origins),
            self.grid_spacing_m,
        )

        rows: list[dict[str, Any]] = []
        now = datetime.now()

        # For each origin, create a short eastward route
        mid_lat = (bbox[1] + bbox[3]) / 2.0
        offset_lng = self.route_length_m / (111_320 * math.cos(math.radians(mid_lat)))

        for i, (lat, lng) in enumerate(origins):
            if i > 0 and self.request_delay > 0:
                time.sleep(self.request_delay)

            dest_lng = min(lng + offset_lng, bbox[2])
            if dest_lng <= lng:
                continue

            body = {
                "origin": {
                    "location": {
                        "latLng": {"latitude": lat, "longitude": lng}
                    }
                },
                "destination": {
                    "location": {
                        "latLng": {"latitude": lat, "longitude": dest_lng}
                    }
                },
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "extraComputations": ["TRAFFIC_ON_POLYLINE"],
            }

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": (
                    "routes.legs.polyline,"
                    "routes.legs.travelAdvisory.speedReadingIntervals"
                ),
            }

            try:
                resp = self._request_with_retry(
                    "POST",
                    self._URL,
                    json=body,
                    headers=headers,
                    max_retries=2,
                    timeout=30,
                )
                data = resp.json()
            except Exception:
                continue

            for route in data.get("routes", []):
                for leg in route.get("legs", []):
                    polyline_enc = (
                        leg.get("polyline", {}).get("encodedPolyline", "")
                    )
                    if not polyline_enc:
                        continue

                    try:
                        coords = self._decode_polyline(polyline_enc)
                    except Exception:
                        continue

                    if len(coords) < 2:
                        continue

                    intervals = (
                        leg.get("travelAdvisory", {})
                        .get("speedReadingIntervals", [])
                    )

                    if not intervals:
                        # No traffic data — create single segment
                        geom = LineString(coords)
                        rows.append(
                            {
                                "jam_factor": None,
                                "speed": None,
                                "free_flow": None,
                                "confidence": None,
                                "speed_category": None,
                                "timestamp": now,
                                "provider": "google",
                                "geometry": geom,
                            }
                        )
                        continue

                    for interval in intervals:
                        start_idx = interval.get(
                            "startPolylinePointIndex", 0
                        )
                        end_idx = interval.get(
                            "endPolylinePointIndex", len(coords) - 1
                        )
                        speed_cat = interval.get("speed", "NORMAL")

                        seg_coords = coords[start_idx : end_idx + 1]
                        if len(seg_coords) < 2:
                            continue

                        geom = LineString(seg_coords)
                        jf = self._SPEED_TO_JF.get(speed_cat)

                        rows.append(
                            {
                                "jam_factor": jf,
                                "speed": None,
                                "free_flow": None,
                                "confidence": None,
                                "speed_category": speed_cat,
                                "timestamp": now,
                                "provider": "google",
                                "geometry": geom,
                            }
                        )

        if not rows:
            logger.warning("Google: 0 segments found")
            return self._empty_gdf(["speed_category"])

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        logger.info("Google: collected %d segments", len(gdf))
        return gdf

    @staticmethod
    def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
        """Decode a Google Encoded Polyline into (lng, lat) tuples."""
        coords: list[tuple[float, float]] = []
        index = 0
        lat = 0
        lng = 0

        while index < len(encoded):
            # Decode latitude
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            lat += (~(result >> 1) if (result & 1) else (result >> 1))

            # Decode longitude
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            lng += (~(result >> 1) if (result & 1) else (result >> 1))

            # Return as (lng, lat) for Shapely
            coords.append((lng / 1e5, lat / 1e5))

        return coords


# ═══════════════════════════════════════════════════════════════════════════
# Mapbox Traffic
# ═══════════════════════════════════════════════════════════════════════════


class MapboxProvider(TrafficProvider):
    """Mapbox Traffic v1 via Tilequery API.

    Mapbox provides traffic data through a vector tileset
    (mapbox.mapbox-traffic-v1) with congestion levels updated every ~5 minutes
    from 700M+ active users. This provider queries the tileset using the
    Tilequery API at grid points and returns congestion data.

    API: ``https://api.mapbox.com/v4/mapbox.mapbox-traffic-v1/tilequery/{lng},{lat}.json``
    """

    _TILESET_ID = "mapbox.mapbox-traffic-v1"
    _BASE_URL = "https://api.mapbox.com/v4"

    def __init__(
        self,
        api_key: str,
        grid_spacing_m: float = 500,
        request_delay: float = 0.05,
    ) -> None:
        super().__init__(api_key)
        self.grid_spacing_m = grid_spacing_m
        self.request_delay = request_delay

    @property
    def name(self) -> str:
        return "mapbox"

    def fetch_flow(
        self, bbox: tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        points = TomTomProvider._grid_points(bbox, self.grid_spacing_m)
        logger.info(
            "Mapbox: querying %d grid points (%.0fm spacing)",
            len(points),
            self.grid_spacing_m,
        )

        seen_hashes: set[str] = set()
        rows: list[dict[str, Any]] = []
        now = datetime.now()

        for i, (lat, lng) in enumerate(points):
            if i > 0 and self.request_delay > 0:
                time.sleep(self.request_delay)

            try:
                url = f"{self._BASE_URL}/{self._TILESET_ID}/tilequery/{lng},{lat}.json"
                resp = self._request_with_retry(
                    "GET",
                    url,
                    params={
                        "access_token": self.api_key,
                        "radius": 50,  # meters
                        "limit": 5,  # max features to return
                    },
                    max_retries=2,
                    timeout=30,
                )
                data = resp.json()
            except Exception:
                continue

            features = data.get("features", [])
            if not features:
                continue

            # Process each feature
            for feature in features:
                geom_data = feature.get("geometry", {})
                if geom_data.get("type") != "LineString":
                    continue

                coords = geom_data.get("coordinates", [])
                if len(coords) < 2:
                    continue

                geom = LineString(coords)

                # Deduplicate by geometry hash
                geom_hash = hashlib.md5(geom.wkb).hexdigest()
                if geom_hash in seen_hashes:
                    continue
                seen_hashes.add(geom_hash)

                props = feature.get("properties", {})
                congestion = props.get("congestion", "low")

                # Map Mapbox congestion levels to jam_factor
                # low: minimal congestion
                # moderate: some congestion
                # heavy: significant congestion
                # severe: severe congestion
                congestion_map = {
                    "low": 1.0,
                    "moderate": 4.0,
                    "heavy": 7.0,
                    "severe": 9.0,
                }
                jam_factor = congestion_map.get(congestion, 0.0)

                rows.append(
                    {
                        "jam_factor": jam_factor,
                        "speed": None,  # Mapbox doesn't provide numeric speeds
                        "free_flow": None,
                        "congestion_level": congestion,
                        "road_class": props.get("road_class"),
                        "timestamp": now,
                        "provider": "mapbox",
                        "geometry": geom,
                    }
                )

        if not rows:
            logger.warning("Mapbox: 0 unique segments found")
            return self._empty_gdf(["congestion_level", "road_class"])

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        logger.info(
            "Mapbox: %d unique segments from %d queries",
            len(gdf),
            len(points),
        )
        return gdf


# ═══════════════════════════════════════════════════════════════════════════
# Provider registry & factory
# ═══════════════════════════════════════════════════════════════════════════

PROVIDERS: dict[str, type[TrafficProvider]] = {
    "here": HEREProvider,
    "tomtom": TomTomProvider,
    "google": GoogleProvider,
    "mapbox": MapboxProvider,
}



def get_provider(name: str, api_key: str, **kwargs: Any) -> TrafficProvider:
    """Instantiate a traffic-data provider by name.

    Parameters
    ----------
    name : str
        Provider name (``"here"``, ``"tomtom"``, ``"google"``).
    api_key : str
        API key for the chosen provider.
    **kwargs
        Extra keyword arguments passed to the provider constructor
        (e.g. ``grid_spacing_m`` for TomTom).

    Returns
    -------
    TrafficProvider

    Raises
    ------
    ValueError
        If *name* is not a registered provider.
    """
    cls = PROVIDERS.get(name.lower())
    if cls is None:
        valid = ", ".join(sorted(PROVIDERS))
        raise ValueError(
            f"Unknown provider '{name}'. Choose from: {valid}"
        )
    return cls(api_key=api_key, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Convenience functions (backwards-compatible)
# ═══════════════════════════════════════════════════════════════════════════

# Keep HERETrafficCollector as a public alias for backwards compatibility
HERETrafficCollector = HEREProvider


def collect_single(
    city_code: str,
    api_key: str,
    output_dir: str | Path | None = None,
    provider_name: str = "here",
    **provider_kwargs: Any,
) -> Path:
    """Collect a single snapshot for one city and save as GeoPackage.

    Parameters
    ----------
    city_code : str
        One of ``"smg"``, ``"bdg"``, ``"jkt"`` (or any key in ``CITIES``).
    api_key : str
        API key for the traffic data provider.
    output_dir : str or Path, optional
        Override the default output directory.
    provider_name : str
        Provider to use (default ``"here"``).
    **provider_kwargs
        Extra arguments for the provider (e.g. ``grid_spacing_m``).

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

    provider = get_provider(provider_name, api_key, **provider_kwargs)
    gdf = provider.fetch_flow(bbox)

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
    provider_name: str = "here",
    **provider_kwargs: Any,
) -> list[Path]:
    """Collect snapshots for multiple cities.

    Parameters
    ----------
    api_key : str
        API key for the traffic data provider.
    city_codes : list of str, optional
        City codes to collect; defaults to all configured cities.
    output_base : str or Path, optional
        Base directory; city sub-directories are created underneath.
    provider_name : str
        Provider to use (default ``"here"``).
    **provider_kwargs
        Extra arguments for the provider.

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
            path = collect_single(
                code, api_key, output_dir=out_dir,
                provider_name=provider_name, **provider_kwargs,
            )
            paths.append(path)
        except Exception:
            logger.exception("Failed to collect %s", code)

    return paths
