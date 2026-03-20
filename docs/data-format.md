# Data Format

## Aggregated GeoPackages

Each city has 8 GeoPackage files, one per time period:

```
traffic_smg_output/
├── night_smg.gpkg
├── morning_peak_smg.gpkg
├── morning_offpeak_smg.gpkg
├── lunch_hours_smg.gpkg
├── afternoon_offpeak_smg.gpkg
├── evening_peak_smg.gpkg
├── evening_offpeak_smg.gpkg
└── late_night_smg.gpkg
```

## Attributes

| Column | Type | Description |
|--------|------|-------------|
| `osm_composite_id` | string | OSM-based composite segment identifier |
| `geometry` | MULTILINESTRING | Road segment geometry (EPSG:4326) |
| `jam_factor_mean` | float | Average jam factor for the time period |
| `jam_factor_std` | float | Standard deviation of jam factor |
| `jam_factor_count` | int | Number of observations |
| `jam_factor_min` | float | Minimum jam factor observed |
| `jam_factor_max` | float | Maximum jam factor observed |

## Time Periods

| Period | Hours | Description |
|--------|-------|-------------|
| `night` | 00:00–06:00 | Night hours |
| `morning_peak` | 06:00–09:00 | Morning rush |
| `morning_offpeak` | 09:00–12:00 | Late morning |
| `lunch_hours` | 12:00–14:00 | Midday |
| `afternoon_offpeak` | 14:00–16:00 | Early afternoon |
| `evening_peak` | 16:00–19:00 | Evening rush |
| `evening_offpeak` | 19:00–22:00 | Evening |
| `late_night` | 22:00–00:00 | Late night |

## Jam Factor Scale

| Range | Level |
|-------|-------|
| 0.0–1.0 | Free flow |
| 1.0–3.0 | Light traffic |
| 3.0–6.0 | Moderate traffic |
| 6.0–8.0 | Heavy traffic |
| 8.0–10.0 | Severe congestion |

## Loading Data

```python
import geopandas as gpd

# Load a single file
gdf = gpd.read_file("traffic_jkt_output/evening_peak_jkt.gpkg")
print(gdf.head())

# Using the pipeline API
from trafficpipeline.geostatistics import load_city_data
data = load_city_data("jkt")  # dict of {period: GeoDataFrame}
```
