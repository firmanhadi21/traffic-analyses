"""Tests for trafficpipeline.collector."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest

from trafficpipeline.collector import HERETrafficCollector, collect_single


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESPONSE: dict = {
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

EMPTY_RESPONSE: dict = {"results": []}

SMG_BBOX = (110.227, -7.105, 110.528, -6.919)


# ---------------------------------------------------------------------------
# Tests: URL construction
# ---------------------------------------------------------------------------


class TestURLConstruction:
    """Verify the API request is constructed correctly."""

    @patch("trafficpipeline.collector.requests")
    def test_request_params(self, mock_requests):
        """API call includes correct bbox and locationReferencing params."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = EMPTY_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        collector = HERETrafficCollector(api_key="test_key", bbox=SMG_BBOX)
        collector.fetch_flow()

        mock_requests.get.assert_called_once()
        _, kwargs = mock_requests.get.call_args
        params = kwargs["params"]
        assert params["in"] == "bbox:110.227,-7.105,110.528,-6.919"
        assert params["locationReferencing"] == "shape"
        assert params["apiKey"] == "test_key"

    @patch("trafficpipeline.collector.requests")
    def test_base_url(self, mock_requests):
        """Request is sent to the correct HERE API endpoint."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = EMPTY_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        collector = HERETrafficCollector(api_key="key", bbox=SMG_BBOX)
        collector.fetch_flow()

        args, _ = mock_requests.get.call_args
        assert args[0] == "https://data.traffic.hereapi.com/v7/flow"


# ---------------------------------------------------------------------------
# Tests: Response parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    """Verify JSON → GeoDataFrame conversion."""

    def test_parse_segments(self):
        """Sample response produces correct number of segments."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        # 1 link from first result + 2 links from second result = 3 segments
        assert len(gdf) == 3

    def test_columns_present(self):
        """All expected columns are present."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        expected = {
            "jam_factor", "speed", "free_flow", "speed_uncapped",
            "confidence", "traversability", "length_m", "timestamp",
            "geometry",
        }
        assert expected.issubset(set(gdf.columns))

    def test_values_correct(self):
        """Flow metrics are correctly extracted."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        row0 = gdf.iloc[0]
        assert row0["jam_factor"] == 3.0
        assert row0["speed"] == 35.0
        assert row0["free_flow"] == 50.0
        assert row0["speed_uncapped"] == 36.0
        assert row0["confidence"] == 0.85

    def test_geometry_type(self):
        """Geometries are LineStrings."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        for geom in gdf.geometry:
            assert geom.geom_type == "LineString"

    def test_geometry_coords(self):
        """Geometry coordinates match the API points (lng, lat order)."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        coords = list(gdf.iloc[0].geometry.coords)
        assert len(coords) == 3
        assert coords[0] == (110.420, -6.920)

    def test_crs_set(self):
        """Output GeoDataFrame has WGS-84 CRS."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 4326

    def test_empty_response(self):
        """Empty response returns an empty GeoDataFrame with correct schema."""
        gdf = HERETrafficCollector._parse_response(EMPTY_RESPONSE)
        assert len(gdf) == 0
        assert "jam_factor" in gdf.columns
        assert "geometry" in gdf.columns

    def test_single_point_link_skipped(self):
        """Links with < 2 points are skipped (can't form a LineString)."""
        data = {
            "results": [
                {
                    "location": {
                        "shape": {
                            "links": [
                                {"points": [{"lat": -6.9, "lng": 110.4}], "length": 0}
                            ]
                        }
                    },
                    "currentFlow": {
                        "speed": 30, "freeFlow": 50, "jamFactor": 4.0,
                        "speedUncapped": 30, "confidence": 0.5,
                    },
                }
            ]
        }
        gdf = HERETrafficCollector._parse_response(data)
        assert len(gdf) == 0


# ---------------------------------------------------------------------------
# Tests: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify retry and error behaviour."""

    @patch("trafficpipeline.collector.time.sleep")  # don't actually wait
    @patch("trafficpipeline.collector.requests")
    def test_retries_on_failure(self, mock_requests, mock_sleep):
        """Retries the configured number of times before raising."""
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.ConnectionError("timeout")
        mock_requests.RequestException = real_requests.RequestException

        collector = HERETrafficCollector(api_key="key", bbox=SMG_BBOX)
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            collector.fetch_flow()

        assert mock_requests.get.call_count == 3

    @patch("trafficpipeline.collector.time.sleep")
    @patch("trafficpipeline.collector.requests")
    def test_succeeds_after_retry(self, mock_requests, mock_sleep):
        """Succeeds on second attempt after first failure."""
        import requests as real_requests

        mock_fail = MagicMock()
        mock_fail.raise_for_status.side_effect = real_requests.HTTPError("500")

        mock_ok = MagicMock()
        mock_ok.raise_for_status = MagicMock()
        mock_ok.json.return_value = SAMPLE_RESPONSE

        mock_requests.get.side_effect = [mock_fail, mock_ok]
        mock_requests.RequestException = real_requests.RequestException

        collector = HERETrafficCollector(api_key="key", bbox=SMG_BBOX)
        gdf = collector.fetch_flow()
        assert len(gdf) == 3


# ---------------------------------------------------------------------------
# Tests: File output
# ---------------------------------------------------------------------------


class TestCollectSingle:
    """Verify single-city collection produces a valid GeoPackage."""

    @patch("trafficpipeline.collector.HERETrafficCollector.fetch_flow")
    def test_creates_gpkg(self, mock_fetch, tmp_path):
        """collect_single writes a .gpkg file in the expected directory."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        mock_fetch.return_value = gdf

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)

        assert outpath.exists()
        assert outpath.suffix == ".gpkg"
        assert "semarang_traffic_" in outpath.name

    @patch("trafficpipeline.collector.HERETrafficCollector.fetch_flow")
    def test_gpkg_readable(self, mock_fetch, tmp_path):
        """Output GeoPackage is readable and contains correct data."""
        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        mock_fetch.return_value = gdf

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)
        loaded = gpd.read_file(outpath)

        assert len(loaded) == 3
        assert "jam_factor" in loaded.columns
        assert "speed" in loaded.columns
        assert "free_flow" in loaded.columns

    @patch("trafficpipeline.collector.HERETrafficCollector.fetch_flow")
    def test_filename_pattern(self, mock_fetch, tmp_path):
        """Filename follows {city}_traffic_YYYYMMDD_HHMMSS.gpkg pattern."""
        import re

        gdf = HERETrafficCollector._parse_response(SAMPLE_RESPONSE)
        mock_fetch.return_value = gdf

        outpath = collect_single("smg", "test_key", output_dir=tmp_path)
        pattern = r"semarang_traffic_\d{8}_\d{6}\.gpkg"
        assert re.match(pattern, outpath.name), f"Unexpected filename: {outpath.name}"
