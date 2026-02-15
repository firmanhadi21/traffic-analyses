"""Smoke test for trafficpipeline.aggregate imports."""

from trafficpipeline.aggregate import aggregate_city, aggregate_all


def test_aggregate_city_callable():
    assert callable(aggregate_city)


def test_aggregate_all_callable():
    assert callable(aggregate_all)
