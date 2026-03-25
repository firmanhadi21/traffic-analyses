"""
traffic-congestion-pipeline
===========================

An open-source pipeline for spatiotemporal traffic congestion analysis
using HERE API, OSMnx, and PySAL across Indonesian metropolitan cities.

Modules
-------
config           : City definitions, time periods, and shared constants
utils            : Timestamp extraction, geometry hashing, temporal grouping
aggregate        : Time-period aggregation of raw GeoPackage traffic snapshots
eda              : Exploratory data analysis and validation
geostatistics    : Spatial statistics, hotspot classification, autocorrelation
bottleneck       : Road capacity and bottleneck analysis via OSMnx
poi              : POI-congestion density analysis
synthesis        : Temporal vs spatial predictor comparison
multilevel       : Multilevel variance decomposition (mixed-effects models)
markov           : LISA Markov and Spatial Markov transition analysis
speed_validation : Speed-based validation across multiple congestion metrics
h3_robustness    : H3 hexagonal aggregation for MAUP robustness testing
"""

__version__ = "0.4.2"
