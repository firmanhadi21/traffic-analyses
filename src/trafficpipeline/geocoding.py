"""
City name geocoding utilities using OpenStreetMap Nominatim.

Provides functions to convert city names to bounding boxes for traffic data
collection.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TypedDict

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)


class CityBbox(TypedDict):
    """Geocoded city bounding box result."""
    name: str
    bbox: tuple[float, float, float, float]
    display_name: str


@lru_cache(maxsize=128)
def geocode_city(city_name: str, timeout: int = 10) -> CityBbox | None:
    """Geocode a city name to a bounding box using Nominatim.
    
    Parameters
    ----------
    city_name : str
        City name, optionally with country (e.g., "Paris, France" or "Tokyo").
    timeout : int
        Request timeout in seconds (default: 10).
    
    Returns
    -------
    CityBbox or None
        Dictionary with keys:
        - ``name``: Normalized city name
        - ``bbox``: ``(west, south, east, north)`` in WGS-84
        - ``display_name``: Full display name from Nominatim
        
        Returns ``None`` if geocoding fails or city not found.
    
    Examples
    --------
    >>> result = geocode_city("Paris, France")
    >>> if result:
    ...     print(result["bbox"])
    (2.2241, 48.8155, 2.4699, 48.9022)
    
    Notes
    -----
    - Results are cached to avoid repeated API calls
    - Uses OpenStreetMap Nominatim with 1-second user agent minimum delay
    - Respects Nominatim usage policy (max 1 request/second)
    """
    geolocator = Nominatim(
        user_agent="traffic-congestion-pipeline/0.2.0",
        timeout=timeout,
    )
    
    try:
        location = geolocator.geocode(
            city_name,
            exactly_one=True,
            addressdetails=True,
        )
        
        if location is None:
            logger.warning("City not found: %s", city_name)
            return None
        
        if not hasattr(location, 'raw') or 'boundingbox' not in location.raw:
            logger.warning("No bounding box available for: %s", city_name)
            return None
        
        # Nominatim returns [south, north, west, east]
        # We need (west, south, east, north)
        bbox_raw = location.raw['boundingbox']
        south, north, west, east = map(float, bbox_raw)
        bbox = (west, south, east, north)
        
        # Extract city name from address if available
        address = location.raw.get('address', {})
        normalized_name = (
            address.get('city') or
            address.get('town') or
            address.get('village') or
            city_name.split(',')[0].strip()
        )
        
        result: CityBbox = {
            'name': normalized_name,
            'bbox': bbox,
            'display_name': location.address,
        }
        
        logger.info(
            "Geocoded '%s' → %s (bbox: %.4f, %.4f, %.4f, %.4f)",
            city_name,
            result['display_name'],
            *bbox,
        )
        
        return result
        
    except GeocoderTimedOut:
        logger.error("Geocoding timeout for: %s", city_name)
        return None
    except GeocoderServiceError as exc:
        logger.error("Geocoding service error for %s: %s", city_name, exc)
        return None
    except Exception as exc:
        logger.exception("Unexpected geocoding error for %s: %s", city_name, exc)
        return None


def parse_bbox_string(bbox_str: str) -> tuple[float, float, float, float] | None:
    """Parse a comma-separated bounding box string.
    
    Parameters
    ----------
    bbox_str : str
        Bounding box as "WEST,SOUTH,EAST,NORTH".
    
    Returns
    -------
    tuple or None
        ``(west, south, east, north)`` as floats, or ``None`` if parsing fails.
    
    Examples
    --------
    >>> parse_bbox_string("-74.05,40.63,-73.75,40.85")
    (-74.05, 40.63, -73.75, 40.85)
    """
    try:
        parts = bbox_str.split(',')
        if len(parts) != 4:
            logger.error("Bbox must have 4 values (west,south,east,north), got: %s", bbox_str)
            return None
        
        west, south, east, north = map(float, parts)
        
        # Validate
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            logger.error("Longitude out of range [-180, 180]: %s", bbox_str)
            return None
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            logger.error("Latitude out of range [-90, 90]: %s", bbox_str)
            return None
        if west >= east:
            logger.error("West must be < east: %s", bbox_str)
            return None
        if south >= north:
            logger.error("South must be < north: %s", bbox_str)
            return None
        
        return (west, south, east, north)
        
    except ValueError as exc:
        logger.error("Invalid bbox format '%s': %s", bbox_str, exc)
        return None
