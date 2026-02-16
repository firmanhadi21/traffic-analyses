"""Tests for trafficpipeline.collector (multi-provider)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest

from trafficpipeline.collector import (
    PROVIDERS,
    GoogleProvider,
    HEREProvider,
    HERETrafficCollector,
    TomTomProvider,
    TrafficProvider,
    collect_single,
    get_provider,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

HERE_RESPONSE: dict = {
    "results": [
        {
            "location": {
                "shape": {
                    "links": [
                        {
                            "points": [
                                {"lat": -6.920, "lng": 110.420},
                                {"lat": -6.921, "lng": 110.421},
                                {"lat": -6.922, "lng": 110.422},
                            ],
                            "length": 250,
                        }
                    ]
                }
            },
            "currentFlow": {
                "speed": 35.0,
                "freeFlow": 50.0,
                "jamFactor": 3.0,
                "speedUncapped": 36.0,
                "confidence": 0.85,
                "traversability": "open",
            },
        },
        {
            "location": {
                "shape": {
                    "links": [
                        {
                            "points": [
                                {"lat": -6.930, "lng": 110.430},
                                {"lat": -6.931, "lng": 110.431},
                            ],
                            "length": 150,
                        },
                        {
                            "points": [
                                {"lat": -6.932, "lng": 110.432},
                                {"lat": -6.933, "lng": 110.433},
                            ],
                            "length": 120,
                        },
                    ]
                }
            },
            "currentFlow": {
                "speed": 20.0,
                "freeFlow": 45.0,
                "jamFactor": 5.5,
                "speedUncapped": 21.0,
                "confidence": 0.72,
                "traversability": "open",
            },
        },
    ]
}

TOMTOM_RESPONSE: dict = {
    "flowSegmentData": {
        "frc": "FRC2",
        "currentSpeed": 38,
        "freeFlowSpeed": 55,
        "currentTravelTime": 120,
        "freeFlowTravelTime": 80,
        "confidence": 0.95,
        "roadClosure": False,
        "coordinates": {
            "coordinate": [
                {"latitude": -6.920, "longitude": 110.420},
                {"latitude": -6.921, "longitude": 110.421},
                {"latitude": -6.922, "longitude": 110.422},
            ]
        },
    }
}

GOOGLE_RESPONSE: dict = {
    "routes": [
        {
            "legs": [
                {
                    "polyline": {
                        "encodedPolyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
                    },
                    "travelAdvisory": {
                        "speedReadingIntervals": [
                            {
                                "startPolylinePointIndex": 0,
                                "endPolylinePointIndex": 1,
                                "speed": "NORMAL",
                            },
                            {
                                "startPolylinePointIndex": 1,
                                "endPolylinePointIndex": 2,
                                "speed": "TRAFFIC_JAM",
                            },
                        ]
                    },
                }
            ]
        }
    ]
}

EMPTY_RESPONSE: dict = {"results": []}
SMG_BBOX = (110.227, -7.105, 110.528, -6.919)


# ═══════════════════════════════════════════════════════════════════════════
# Provider factory & registry
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderFactory:
    """Test get_provider() and PROVIDERS registry."""

    def test_all_providers_registered(self):
        assert set(PROVIDERS.keys()) == {"here", "tomtom", "google"}

    def test_get_here(self):
        p = get_provider("here", api_key="k")
        assert isinstance(p, HEREProvider)
        assert p.name == "here"

    def test_get_tomtom(self):
        p = get_provider("tomtom", api_key="k")
        assert isinstance(p, TomTomProvider)
        assert p.name == "tomtom"

    def test_get_google(self):
        p = get_provider("google", api_key="k")
        assert isinstance(p, GoogleProvider)
        assert p.name == "google"

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("mapbox", api_key="k")

    def test_case_insensitive(self):
        p = get_provider("HERE", api_key="k")
        assert isinstance(p, HEREProvider)

    def test_backwards_compat_alias(self):
        """HERETrafficCollector should be an alias for HEREProvider."""
        assert HERETrafficCollector is HEREProvider

    def test_all_are_subclasses(self):
        for cls in PROVIDERS.values():
            assert issubclass(cls, TrafficProvider)


# ═══════════════════════════════════════════════════════════════════════════
# HERE Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestHEREProvider:
    """Test HERE-specific URL construction and parsing."""

    @patch("trafficpipeline.collector.requests")
    def test_request_params(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = EMPTY_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.request.return_value = mock_resp

        provider = HEREProvider(api_key="test_key")
        provider.fetch_flow(SMG_BBOX)

        mock_requests.request.assert_called_once()
        _, kwargs = mock_requests.request.call_args
        params = kwargs["params"]
        assert params["in"] == "bbox:110.227,-7.105,110.528,-6.919"
        assert params["locationReferencing"] == "shape"
        assert params["apiKey"] == "test_key"

    def test_parse_segments(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        assert len(gdf) == 3

    def test_columns_present(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        required = {"jam_factor", "speed", "free_flow", "confidence",
                     "geometry", "timestamp", "provider"}
        assert required.issubset(set(gdf.columns))

    def test_values_correct(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        row = gdf.iloc[0]
        assert row["jam_factor"] == 3.0
        assert row["speed"] == 35.0
        assert row["free_flow"] == 50.0
        assert row["provider"] == "here"

    def test_geometry_type(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        for geom in gdf.geometry:
            assert geom.geom_type == "LineString"

    def test_geometry_coords(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        coords = list(gdf.iloc[0].geometry.coords)
        assert coords[0] == (110.420, -6.920)

    def test_crs(self):
        gdf = HEREProvider._parse_response(HERE_RESPONSE)
        assert gdf.crs.to_epsg() == 4326

    def test_empty_response(self):
        gdf = HEREProvider._parse_response(EMPTY_RESPONSE)
        assert len(gdf) == 0
        assert "jam_factor" in gdf.columns

    def test_single_point_skipped(self):
        data = {
            "results": [{
                "location": {"shape": {"links": [
                    {"points": [{"lat": -6.9, "lng": 110.4}], "length": 0}
                ]}},
                "currentFlow": {"speed": 30, "freeFlow": 50, "jamFactor": 4.0,
                                "speedUncapped": 30, "confidence": 0.5},
            }]
        }
        assert len(HEREProvider._parse_response(data)) == 0


# ═══════════════════════════════════════════════════════════════════════════
# TomTom Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestTomTomProvider:
    """Test TomTom grid sampling and response parsing."""

    def test_grid_points(self):
        """Grid covers the bbox with reasonable number of points."""
        points = TomTomProvider._grid_points(SMG_BBOX, spacing_m=5000)
        assert len(points) > 0
        for lat, lng in points:
            assert SMG_BBOX[1] <= lat <= SMG_BBOX[3]
            assert SMG_BBOX[0] <= lng <= SMG_BBOX[2]

    def test_grid_density(self):
        """Smaller spacing produces more points."""
        coarse = TomTomProvider._grid_points(SMG_BBOX, spacing_m=5000)
        fine = TomTomProvider._grid_points(SMG_BBOX, spacing_m=1000)
        assert len(fine) > len(coarse)

    @patch("trafficpipeline.collector.requests")
    @patch("trafficpipeline.collector.time.sleep")
    def test_fetch_flow(self, mock_sleep, mock_requests):
        """TomTom fetch returns a GeoDataFrame with standard columns."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = TOMTOM_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.request.return_value = mock_resp
        mock_requests.RequestException = Exception

        provider = TomTomProvider(api_key="k", grid_spacing_m=10000)
        gdf = provider.fetch_flow(SMG_BBOX)

        assert len(gdf) > 0
        assert "jam_factor" in gdf.columns
        assert "speed" in gdf.columns
        assert "free_flow" in gdf.columns
        assert "provider" in gdf.columns
        assert gdf.iloc[0]["provider"] == "tomtom"

    @patch("trafficpipeline.collector.requests")
    @patch("trafficpipeline.collector.time.sleep")
    def test_jam_factor_calculation(self, mock_sleep, mock_requests):
        """jam_factor is correctly computed from speed/freeFlow ratio."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = TOMTOM_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.request.return_value = mock_resp
        mock_requests.RequestException = Exception

        provider = TomTomProvider(api_key="k", grid_spacing_m=50000)
        gdf = provider.fetch_flow(SMG_BBOX)

        if len(gdf) > 0:
            row = gdf.iloc[0]
            expected_jf = round(10.0 * (1.0 - 38 / 55), 2)
            assert row["jam_factor"] == pytest.approx(expected_jf, abs=0.1)

    @patch("trafficpipeline.collector.requests")
    @patch("trafficpipeline.collector.time.sleep")
    def test_deduplication(self, mock_sleep, mock_requests):
        """Identical segments from different grid points are deduplicated."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = TOMTOM_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.request.return_value = mock_resp
        mock_requests.RequestException = Exception

        # Use small spacing to get many queries returning same segment
        provider = TomTomProvider(api_key="k", grid_spacing_m=5000)
        gdf = provider.fetch_flow(SMG_BBOX)

        # Should only have 1 unique segment despite many queries
        assert len(gdf) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Google Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestGoogleProvider:
    """Test Google polyline decoding and response parsing."""

    def test_decode_polyline(self):
        """Standard Google polyline is decoded correctly."""
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        coords = GoogleProvider._decode_polyline(encoded)
        assert len(coords) == 3
        # Known values for this test polyline
        assert coords[0] == pytest.approx((-120.20000, 38.50000), abs=0.001)

    def test_speed_category_mapping(self):
        """Speed categories map to expected jam factors."""
        assert GoogleProvider._SPEED_TO_JF["NORMAL"] == 1.0
        assert GoogleProvider._SPEED_TO_JF["SLOW"] == 4.0
        assert GoogleProvider._SPEED_TO_JF["TRAFFIC_JAM"] == 8.0

    @patch("trafficpipeline.collector.requests")
    @patch("trafficpipeline.collector.time.sleep")
    def test_fetch_flow(self, mock_sleep, mock_requests):
        """Google fetch returns GeoDataFrame with standard columns."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = GOOGLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.request.return_value = mock_resp
        mock_requests.RequestException = Exception

        provider = GoogleProvider(api_key="k", grid_spacing_m=50000)
        gdf = provider.fetch_flow(SMG_BBOX)

        assert "jam_factor" in gdf.columns
        assert "speed_category" in gdf.columns
        assert "provider" in gdf.columns
        if len(gdf) > 0:
            assert gdf.iloc[0]["provider"] == "google"


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Verify retry and error behaviour."""

    @patch("trafficpipeline.collector.time.sleep")
    @patch("trafficpipeline.collector.requests")
    def test_retries_on_failure(self, mock_requests, mock_sleep):
        mock_requests.request.side_effect = Exception("timeout")
        mock_requests.RequestException = Exception

        provider = HEREProvider(api_key="key")
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            provider.fetch_flow(SMG_BBOX)

        assert mock_requests.request.call_count == 3

    @patch("trafficpipeline.collector.time.sleep")
    @patch("trafficpipeline.collector.requests")
    def test_succeeds_after_retry(self, mock_requests, mock_sleep):
        mock_fail = MagicMock()
        mock_fail.raise_for_status.side_effect = Exception("500")

        mock_ok = MagicMock()
        mock_ok.raise_for_status = MagicMock()
        mock_ok.json.return_value = HERE_RESPONSE

        mock_requests.request.side_effect = [mock_fail, mock_ok]
        mock_requests.RequestException = Exception

        provider = HEREProvider(api_key="key")
        gdf = provider.fetch_flow(SMG_BBOX)
        assert len(gdf) == 3


# ═══════════════════════════════════════════════════════════════════════════
# File output
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectSingle:
    """Verify single-city collection produces a valid GeoPackage."""

    @patch("trafficpipeline.collector.get_provider")
    def test_creates_gpkg(self, mock_get_provider, tmp_path):
        mock_provider = MagicMock()
        mock_provider.fetch_flow.return_value = HEREProvider._parse_response(
            HERE_RESPONSE
        )
        mock_get_provider.return_value = mock_provider

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)

        assert outpath.exists()
        assert outpath.suffix == ".gpkg"
        assert "semarang_traffic_" in outpath.name

    @patch("trafficpipeline.collector.get_provider")
    def test_gpkg_readable(self, mock_get_provider, tmp_path):
        mock_provider = MagicMock()
        mock_provider.fetch_flow.return_value = HEREProvider._parse_response(
            HERE_RESPONSE
        )
        mock_get_provider.return_value = mock_provider

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)
        loaded = gpd.read_file(outpath)

        assert len(loaded) == 3
        assert "jam_factor" in loaded.columns
        assert "speed" in loaded.columns

    @patch("trafficpipeline.collector.get_provider")
    def test_filename_pattern(self, mock_get_provider, tmp_path):
        import re

        mock_provider = MagicMock()
        mock_provider.fetch_flow.return_value = HEREProvider._parse_response(
            HERE_RESPONSE
        )
        mock_get_provider.return_value = mock_provider

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)
        pattern = r"semarang_traffic_\d{8}_\d{6}\.gpkg"
        assert re.match(pattern, outpath.name)

    @patch("trafficpipeline.collector.get_provider")
    def test_provider_name_passed(self, mock_get_provider, tmp_path):
        """Provider name is forwarded to get_provider."""
        mock_provider = MagicMock()
        mock_provider.fetch_flow.return_value = HEREProvider._parse_response(
            EMPTY_RESPONSE
        )
        mock_get_provider.return_value = mock_provider

        collect_single("smg", "k", output_dir=tmp_path, provider_name="tomtom")
        mock_get_provider.assert_called_once_with("tomtom", "k")
