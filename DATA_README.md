# Traffic Congestion Dataset — Semarang, Bandung, Jakarta

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18650759.svg)](https://doi.org/10.5281/zenodo.18650759)


https://doi.org/10.5281/zenodo.18650759
## Description

Time-period-aggregated traffic congestion data for three Indonesian metropolitan cities, derived from the HERE Traffic API. Data were collected at 15-minute intervals from **March 2025 to February 2026** (11 months) and aggregated into 8 time-of-day periods.

This dataset accompanies the paper:

> Hadi, F., Wahyuddin, Y., Sabri, L. M., & Indrajit, A. (2026). An Open-Source Pipeline for Spatiotemporal Traffic Congestion Analysis: Integrating HERE API, OSMnx, and PySAL Across Indonesian Metropolitan Cities. *Computers, Environment and Urban Systems*.

The analysis pipeline is available at: https://github.com/firmanhadi21/traffic-analyses

## Cities

| City | Code | Segments | Raw Observations | Bounding Box (W, S, E, N) |
|------|------|----------|------------------|---------------------------|
| Semarang | smg | 1,076 | 15.2 M | 110.227, −7.105, 110.528, −6.919 |
| Bandung | bdg | 3,069 | 43.4 M | 107.469, −7.085, 107.826, −6.829 |
| Jakarta | jkt | 14,549 | 206.3 M | 106.604, −6.410, 107.110, −6.091 |

## Time Periods

| Period | Hours | Description |
|--------|-------|-------------|
| `night` | 00:00–06:00 | Night |
| `morning_peak` | 06:00–09:00 | Morning rush |
| `morning_offpeak` | 09:00–12:00 | Late morning |
| `lunch_hours` | 12:00–14:00 | Midday |
| `afternoon_offpeak` | 14:00–16:00 | Early afternoon |
| `evening_peak` | 16:00–19:00 | Evening rush |
| `evening_offpeak` | 19:00–22:00 | Evening |
| `late_night` | 22:00–00:00 | Late night |

## File Structure

```
zenodo_data/
├── traffic_smg_output/            # Semarang (8 files, ~8.5 MB)
│   ├── night_smg.gpkg
│   ├── morning_peak_smg.gpkg
│   ├── morning_offpeak_smg.gpkg
│   ├── lunch_hours_smg.gpkg
│   ├── afternoon_offpeak_smg.gpkg
│   ├── evening_peak_smg.gpkg
│   ├── evening_offpeak_smg.gpkg
│   └── late_night_smg.gpkg
├── traffic_bdg_output/            # Bandung (8 files, ~23 MB)
│   └── ... (same pattern)
├── traffic_jkt_output/            # Jakarta (8 files, ~84 MB)
│   └── ... (same pattern)
├── analysis_results/              # Computed statistics (CSV)
│   ├── anova_results.csv
│   ├── morans_i_results.csv
│   ├── lisa_results.csv
│   ├── bottleneck_analysis_results.csv
│   ├── centrality_correlations.csv
│   └── poi_congestion_correlations.csv
└── DATA_README.md                 # This file
```

## Data Format

All spatial files use **GeoPackage** (.gpkg), an OGC open standard based on SQLite.
Coordinate reference system: **WGS 84 (EPSG:4326)**.

### Attributes per Road Segment

| Column | Type | Description |
|--------|------|-------------|
| `osm_composite_id` | string | OSM-based composite segment identifier |
| `geometry` | MULTILINESTRING | Road segment geometry |
| `jam_factor_mean` | float | Mean jam factor for the time period (0–10 scale) |
| `jam_factor_std` | float | Standard deviation of jam factor |
| `jam_factor_count` | int | Number of 15-min observations aggregated |
| `jam_factor_min` | float | Minimum jam factor observed |
| `jam_factor_max` | float | Maximum jam factor observed |

### Jam Factor Scale

| Range | Interpretation |
|-------|----------------|
| 0.0–1.0 | Free flow |
| 1.0–3.0 | Light traffic |
| 3.0–6.0 | Moderate traffic |
| 6.0–8.0 | Heavy traffic |
| 8.0–10.0 | Severe congestion |

## How to Use

```python
import geopandas as gpd

# Load evening peak traffic for Jakarta
gdf = gpd.read_file("traffic_jkt_output/evening_peak_jkt.gpkg")
print(gdf[["osm_composite_id", "jam_factor_mean", "jam_factor_std"]].describe())

# Or install the pipeline and run analysis directly:
# pip install -e ".[all]"
# traffic-pipeline geostatistics
```

## Source

Traffic data: [HERE Traffic API](https://developer.here.com/documentation/traffic-api/) via Python-based collector with multi-provider support (HERE, TomTom, Google). See [`src/trafficpipeline/collector.py`](src/trafficpipeline/collector.py) for implementation.

Road networks: [OpenStreetMap](https://www.openstreetmap.org/) via [OSMnx](https://github.com/gboeing/osmnx).

## License

MIT — see [LICENSE](../LICENSE).

## Citation

If you use this dataset, please cite both the paper and the dataset:

```bibtex
@article{hadi2026traffic,
  title={An Open-Source Pipeline for Spatiotemporal Traffic Congestion Analysis: Integrating {HERE} {API}, {OSMnx}, and {PySAL} Across Indonesian Metropolitan Cities},
  author={Hadi, Firman and Wahyuddin, Yasser and Sabri, L. M. and Indrajit, Agung},
  journal={Computers, Environment and Urban Systems},
  year={2026}
}

@dataset{hadi2026traffic_data,
  author={Hadi, Firman and Wahyuddin, Yasser and Sabri, L. M. and Indrajit, Agung},
  title={Traffic Congestion Dataset: Semarang, Bandung, Jakarta (2025--2026)},
  year={2026},
  publisher={Zenodo},
  doi={10.5281/zenodo.XXXXXXX}
}
```
