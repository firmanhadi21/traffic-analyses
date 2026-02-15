"""
traffic-congestion-pipeline
===========================

An open-source pipeline for spatiotemporal traffic congestion analysis
using HERE API, OSMnx, and PySAL across Indonesian metropolitan cities.

Modules
-------
config       : City definitions, time periods, and shared constants
utils        : Timestamp extraction, geometry hashing, temporal grouping
aggregate    : Time-period aggregation of raw GeoPackage traffic snapshots
eda          : Exploratory data analysis and validation
geostatistics: Spatial statistics, hotspot classification, autocorrelation
bottleneck   : Road capacity and bottleneck analysis via OSMnx
poi          : POI-congestion density analysis
synthesis    : Temporal vs spatial predictor comparison
"""

__version__ = "0.1.0"
