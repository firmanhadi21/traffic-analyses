# Traffic Data Analysis - Indonesian Cities

A comprehensive traffic data collection and analysis system for three major Indonesian cities: **Semarang**, **Bandung**, and **Jakarta**. This project uses the HERE API to collect real-time traffic flow data and aggregates it by time periods for urban mobility analysis.

## Overview

This system collects traffic data at 15-minute intervals and processes it into time-period aggregated statistics. The data spans from **March 2025 to February 2026**, providing a full year of traffic patterns for urban planning and transportation research.

### Cities Covered

| City | Segments | Bounding Box | Coverage |
|------|----------|--------------|----------|
| Semarang | 1,076 | 110.227-110.528, -7.105 to -6.919 | Urban core |
| Bandung | 3,069 | 107.469-107.826, -7.085 to -6.829 | Metropolitan area |
| Jakarta | 14,549 | 106.604-107.110, -6.410 to -6.091 | Greater Jakarta |

## Data Summary

| City | Files Processed | Total Records | Date Range |
|------|-----------------|---------------|------------|
| Semarang | 14,122 | 15.2 million | Mar 2025 - Feb 2026 |
| Bandung | 14,136 | 43.4 million | Mar 2025 - Feb 2026 |
| Jakarta | 14,132 | 206.3 million | Mar 2025 - Feb 2026 |

## Time Periods

Data is aggregated into 8 distinct time periods:

| Period | Time Range | Description |
|--------|------------|-------------|
| `night` | 00:00 - 06:00 | Night hours |
| `morning_peak` | 06:00 - 09:00 | Morning rush hour |
| `morning_offpeak` | 09:00 - 12:00 | Late morning |
| `lunch_hours` | 12:00 - 14:00 | Midday |
| `afternoon_offpeak` | 14:00 - 16:00 | Early afternoon |
| `evening_peak` | 16:00 - 19:00 | Evening rush hour |
| `evening_offpeak` | 19:00 - 22:00 | Evening |
| `late_night` | 22:00 - 00:00 | Late night |

## Repository Structure

```
traffic-analyses/
├── README.md
├── CLAUDE.md                    # Project instructions
├── requirements.txt             # Python dependencies
├── .gitignore
│
├── # Data Collection
├── traffic_collector.R          # R script for HERE API data collection
├── traffic_collector.sh         # Shell wrapper for cron scheduling
│
├── # Aggregation Scripts
├── run_semarang_aggregation.py  # Semarang data aggregation
├── run_bandung_aggregation.py   # Bandung data aggregation
├── run_jakarta_aggregation.py   # Jakarta data aggregation
├── aggregate_all.ipynb          # Jupyter notebook for analysis
│
├── # Output Data (GeoPackage format)
├── traffic_smg_output/          # Semarang aggregated data
│   ├── night_smg.gpkg
│   ├── morning_peak_smg.gpkg
│   ├── morning_offpeak_smg.gpkg
│   ├── lunch_hours_smg.gpkg
│   ├── afternoon_offpeak_smg.gpkg
│   ├── evening_peak_smg.gpkg
│   ├── evening_offpeak_smg.gpkg
│   └── late_night_smg.gpkg
├── traffic_bdg_output/          # Bandung aggregated data
│   └── ... (same structure)
└── traffic_jkt_output/          # Jakarta aggregated data
    └── ... (same structure)
```

## Output Data Format

Each GeoPackage file contains road segments with the following attributes:

| Column | Description |
|--------|-------------|
| `fid` | Feature ID (unique segment identifier) |
| `geometry` | Road segment geometry (MULTILINESTRING) |
| `jam_factor_mean` | Average jam factor for the time period |
| `jam_factor_std` | Standard deviation of jam factor |
| `jam_factor_count` | Number of observations |
| `jam_factor_min` | Minimum jam factor observed |
| `jam_factor_max` | Maximum jam factor observed |

### Jam Factor Scale

The jam factor indicates traffic congestion level:
- **0.0 - 1.0**: Free flow
- **1.0 - 3.0**: Light traffic
- **3.0 - 6.0**: Moderate traffic
- **6.0 - 8.0**: Heavy traffic
- **8.0 - 10.0**: Severe congestion

## Traffic Pattern Results

### Semarang
| Time Period | Mean Jam Factor | Std |
|-------------|-----------------|-----|
| Night | 0.45 | 0.06 |
| Morning Peak | 0.95 | 0.08 |
| Morning Off-peak | 1.39 | 0.08 |
| Lunch Hours | 1.45 | 0.08 |
| Afternoon Off-peak | 1.52 | 0.08 |
| Evening Peak | 1.66 | 0.09 |
| Evening Off-peak | 1.33 | 0.10 |
| Late Night | 0.78 | 0.06 |

### Bandung
| Time Period | Mean Jam Factor | Std |
|-------------|-----------------|-----|
| Night | 0.46 | 0.04 |
| Morning Peak | 1.15 | 0.10 |
| Morning Off-peak | 1.63 | 0.08 |
| Lunch Hours | 1.70 | 0.12 |
| Afternoon Off-peak | 1.87 | 0.09 |
| Evening Peak | 1.92 | 0.10 |
| Evening Off-peak | 1.41 | 0.13 |
| Late Night | 0.77 | 0.06 |

### Jakarta
| Time Period | Mean Jam Factor | Std |
|-------------|-----------------|-----|
| Night | 0.50 | 0.13 |
| Morning Peak | 1.20 | 0.17 |
| Morning Off-peak | 1.64 | 0.11 |
| Lunch Hours | 1.67 | 0.11 |
| Afternoon Off-peak | 1.80 | 0.11 |
| Evening Peak | 2.02 | 0.18 |
| Evening Off-peak | 1.68 | 0.16 |
| Late Night | 0.98 | 0.13 |

## Installation

### Requirements

```bash
pip install pandas geopandas shapely numpy
```

### R Dependencies (for data collection)

```r
install.packages(c("hereR", "sf", "lubridate"))
```

## Usage

### Running Aggregation Scripts

```bash
# Aggregate Semarang data
python run_semarang_aggregation.py

# Aggregate Bandung data
python run_bandung_aggregation.py

# Aggregate Jakarta data
python run_jakarta_aggregation.py
```

### Loading Output Data

```python
import geopandas as gpd

# Load morning peak traffic for Jakarta
gdf = gpd.read_file('traffic_jkt_output/morning_peak_jkt.gpkg')

# View statistics
print(gdf[['fid', 'jam_factor_mean', 'jam_factor_std']].describe())

# Plot the data
gdf.plot(column='jam_factor_mean', cmap='RdYlGn_r', legend=True)
```

### Data Collection (requires HERE API key)

```bash
# Run data collection for all cities
./traffic_collector.sh
```

## Data Source

Traffic data is collected using the [HERE Traffic API](https://developer.here.com/documentation/traffic-api/dev_guide/topics/what-is.html) via the [hereR](https://github.com/munterfinger/hereR) R package.

## Timezone

All timestamps are in **GMT+7 (Asia/Bangkok)** to match Indonesian local time (WIB - Western Indonesian Time).

## License

This project is for research and educational purposes. Traffic data is subject to HERE API terms of service.

## Author

- **firmanhadi21** - [GitHub](https://github.com/firmanhadi21)

## Acknowledgments

- HERE Technologies for traffic data API
- Built with assistance from Claude (Anthropic)
