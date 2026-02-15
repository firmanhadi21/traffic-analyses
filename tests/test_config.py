"""Tests for trafficpipeline.config."""

from trafficpipeline.config import (
    CITIES,
    TIME_PERIODS,
    get_city,
    get_time_period,
)


def test_cities_keys():
    assert set(CITIES.keys()) == {"smg", "bdg", "jkt"}


def test_city_bbox_tuple():
    for code, city in CITIES.items():
        bbox = city["bbox"]
        assert len(bbox) == 4, f"{code} bbox should have 4 elements"
        assert bbox[0] < bbox[2], f"{code}: west < east"
        assert bbox[1] < bbox[3], f"{code}: south < north"


def test_get_city():
    assert get_city("smg")["name"] == "Semarang"
    assert get_city("bdg")["name"] == "Bandung"
    assert get_city("jkt")["name"] == "Jakarta"


def test_get_city_invalid():
    try:
        get_city("xyz")
        assert False, "Should raise KeyError"
    except KeyError:
        pass


def test_time_periods_count():
    assert len(TIME_PERIODS) == 8


def test_get_time_period():
    # Midnight → night
    assert get_time_period(0) == "night"
    assert get_time_period(3) == "night"
    # Morning peak
    assert get_time_period(7) == "morning_peak"
    assert get_time_period(8) == "morning_peak"
    # Evening peak
    assert get_time_period(17) == "evening_peak"
    assert get_time_period(18) == "evening_peak"
