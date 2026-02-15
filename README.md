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

## Geostatistical Analysis

The repository includes comprehensive geostatistical analysis to understand traffic patterns across the three cities.

### Running the Analysis

```bash
python geostatistical_analysis.py
```

### Generated Visualizations

All figures are saved to the `figures/` directory:

| Figure | Description |
|--------|-------------|
| `*_traffic_maps.png` | Traffic intensity maps for all 8 time periods per city |
| `*_hotspots_evening_peak.png` | Congestion hotspot analysis during evening peak |
| `temporal_pattern_comparison.png` | Bar chart comparing traffic across time periods |
| `congestion_distribution.png` | Histogram of jam factor distribution per city |
| `peak_vs_offpeak.png` | Scatter plot comparing peak vs off-peak traffic |
| `variability_analysis.png` | Coefficient of variation analysis by segment |
| `boxplot_comparison.png` | Boxplot comparison across cities and time periods |
| `heatmap_summary.png` | Heatmap of traffic patterns (segments × time periods) |
| `statistics_report.txt` | Detailed statistical analysis report |

### Traffic Maps by Time Period

Each city has a comprehensive map showing traffic intensity across all 8 time periods:

**Semarang Traffic Patterns**
![Semarang Traffic Maps](figures/smg_traffic_maps.png)

**Bandung Traffic Patterns**
![Bandung Traffic Maps](figures/bdg_traffic_maps.png)

**Jakarta Traffic Patterns**
![Jakarta Traffic Maps](figures/jkt_traffic_maps.png)

### Temporal Pattern Comparison

![Temporal Pattern](figures/temporal_pattern_comparison.png)

### Congestion Hotspots (Evening Peak)

**Semarang Hotspots**
![Semarang Hotspots](figures/smg_hotspots_evening_peak.png)

**Bandung Hotspots**
![Bandung Hotspots](figures/bdg_hotspots_evening_peak.png)

**Jakarta Hotspots**
![Jakarta Hotspots](figures/jkt_hotspots_evening_peak.png)

### Statistical Analysis Summary

#### Congestion Classification (Evening Peak)

| City | Free Flow | Light Traffic | Moderate | Heavy | Severe |
|------|-----------|---------------|----------|-------|--------|
| Semarang | 0% | 100% | 0% | 0% | 0% |
| Bandung | 0% | 88.1% | 11.9% | 0% | 0% |
| Jakarta | 0% | 46.5% | 53.5% | 0% | 0% |

#### Peak Hour Comparison

- **Semarang**: Evening peak jam factor = 1.65
- **Bandung**: Evening peak jam factor = 1.92
- **Jakarta**: Evening peak jam factor = 2.01

### Key Findings

1. **Evening Peak is the Most Congested Period** across all three cities
2. **Jakarta has the highest congestion levels**, with 53.5% of road segments experiencing moderate traffic during evening peak
3. **Night hours (00:00-06:00)** show the lowest congestion with free-flow conditions
4. **Bandung shows higher afternoon congestion** compared to Semarang
5. **Spatial clustering is relatively low**, indicating congestion is distributed across road networks rather than concentrated in specific areas

## Bottleneck Analysis

Tests whether congestion is driven by **road capacity constraints (bottlenecks)** or by **trip destinations (activity centers)**.

### Methodology

The analysis uses two data sources with fundamentally different coverage:

| Data Source | Segments | Coverage |
|-------------|----------|----------|
| HERE Traffic API | Monitored segments only | Major arterials, trunks, motorways |
| OSMnx Road Network | Full network | All roads including residential, service, alleys |

**Important design decision:** The OSMnx network is **filtered to HERE-comparable road types** (motorway through tertiary, including links) before any analysis. This prevents spurious nearest-neighbor matches between HERE arterial segments and unmonitored residential streets.

### Analysis Components

#### 1. Aggregate Capacity Comparison
- Splits road segments into low vs high capacity groups (by median capacity score)
- Compares mean jam factor between groups
- Tests statistical significance (t-test, Cohen's d effect size)

#### 2. Capacity-Congestion Correlation
- Capacity score = estimated lanes × road hierarchy score
- Pearson and Spearman correlation against mean jam factor

#### 3. Peak Sensitivity Analysis
- Peak sensitivity = (evening_peak_JF − night_JF) / (night_JF + ε)
- Tests whether high-sensitivity segments (congested at peak, free at night) have lower capacity

#### 4. Congestion by Road Type
- Breakdown of mean jam factor by OSM highway classification
- Covers: Motorway, Motorway Link, Trunk, Trunk Link, Primary, Primary Link, Secondary, Secondary Link, Tertiary, Tertiary Link

#### 5. Spatial Capacity Drop Analysis (Graph-Based)
- Traverses the filtered road network graph to detect **capacity drop nodes** — intersections where maximum incoming edge capacity exceeds maximum outgoing edge capacity by ≥20%
- These are "funnel" points (e.g., trunk → secondary transition)
- Tests whether **proximity to capacity drops** correlates with higher congestion
- Bins traffic segments into Near/Medium/Far from nearest drop node

#### 6. Local Capacity Gradient (Neighborhood Analysis)
- For each traffic segment, computes the mean capacity of its K=10 nearest spatial neighbors
- Segments with lower capacity than their surroundings are **local bottlenecks**
- Tests whether local bottleneck zones have significantly higher jam factors
- Correlation between local capacity deficit and congestion level

### Running the Analysis

```bash
# Requires OSMnx (downloads road network) — recommended on HPC
python bottleneck_analysis.py
```

### Output

| File | Description |
|------|-------------|
| `analysis_results/bottleneck_analysis_results.csv` | Statistical results for all cities |
| `figures/bottleneck_capacity_comparison.png` | Box plot: low vs high capacity road congestion |
| `figures/capacity_congestion_scatter.png` | Scatter plot: capacity score vs jam factor |
| `figures/capacity_drop_spatial_analysis.png` | Spatial capacity drop proximity and local bottleneck analysis |

### Interpretation Guide

| Metric | Supports Bottleneck Hypothesis If... |
|--------|--------------------------------------|
| Low cap JF > High cap JF (p < 0.05) | Low-capacity roads are significantly more congested |
| Capacity-congestion r < −0.15 | Negative correlation between capacity and congestion |
| Near-drop JF > Far-drop JF (p < 0.05) | Proximity to capacity transitions predicts congestion |
| Local bottleneck d > 0.2 | Relative capacity deficit meaningfully increases congestion |

### Caveat: HERE Jam Factor Normalization

HERE's jam factor is a **normalized** congestion measure — it represents delay relative to each road's free-flow speed. A JF of 5 on a residential road and JF of 5 on a motorway both mean "heavily congested for that road type." This normalization partially removes the capacity effect, which means:
- Absolute capacity may show weak correlations even if bottlenecks exist
- **Spatial** capacity drops (relative transitions) are a stronger test than aggregate capacity levels
- **Temporal** patterns (time-of-day) typically explain more variance than spatial factors

#### Evidence of Normalization in Our Data

The Semarang results demonstrate that JF is already normalized by road class:

| Road Type | Mean JF | n |
|-----------|---------|---|
| Motorway | 1.646 | 6 |
| Trunk | 1.648 | 170 |
| Primary | 1.651 | 132 |
| Secondary | 1.655 | 242 |
| Tertiary | 1.647 | 124 |
| Residential | 1.654 | 300 |

The JF range across all road types is **1.644–1.711 (only ~4% spread)**. If JF measured raw speed or absolute delay, motorways (100+ km/h free-flow) would show vastly different values than residential streets (30 km/h free-flow). The tight clustering confirms JF is computed relative to each segment's own free-flow baseline:

$$JF = f\left(\frac{T_{current}}{T_{freeflow}}\right) \times 10$$

This explains why:
- Pearson r ≈ −0.02 (capacity vs JF) — near-zero because normalization flattens the effect
- Cohen's d ≈ 0.03 (low vs high capacity) — trivial because you're correlating capacity against a measure that already divides out capacity

#### Data Source Mismatch

An additional challenge is the mismatch between traffic data and road network coverage:

| Data Source | Coverage | Segments |
|-------------|----------|----------|
| HERE Traffic API | Major arterials only (motorway through tertiary) | ~1,000–15,000 per city |
| OSMnx Road Network | All roads (including residential, service, alleys) | ~10,000–50,000 per city |

HERE monitors a **subset** of the road network. When spatial-joining traffic data to the full OSMnx network, nearest-neighbor matching can assign a HERE trunk-road segment to a nearby residential lane, introducing noise. The bottleneck analysis addresses this by **filtering OSMnx edges to HERE-comparable road types** before analysis.

#### Denormalization Path (Speed-Based Analysis)

The raw HERE GeoPackage files contain three columns:
- `jam_factor` — normalized congestion (0–10, relative to free-flow) ← **currently aggregated**
- `speed` — current speed (km/h) ← **not aggregated**
- `free_flow` — free-flow speed (km/h) ← **not aggregated**

Only `jam_factor` was aggregated into the time-period output files. To properly test the bottleneck hypothesis without the normalization confound, the data should be re-aggregated with `speed` and `free_flow` columns, enabling a denormalized delay metric:

$$\text{delay} = \frac{1}{\text{speed}} - \frac{1}{\text{free\_flow}}$$

This gives **excess travel time per km** — an absolute measure where a motorway at 40 km/h (with 120 km/h free-flow) produces a much higher delay than a residential street at 25 km/h (with 30 km/h free-flow). This metric directly reflects capacity constraints without the normalization that flattens road class differences.

## License

This project is for research and educational purposes. Traffic data is subject to HERE API terms of service.

## Author

- **firmanhadi21** - [GitHub](https://github.com/firmanhadi21)

## Acknowledgments

- HERE Technologies for traffic data API
- Built with assistance from Claude (Anthropic)
