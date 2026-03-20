# OSM-Based Traffic Data Aggregation System

This document describes the OSM-based traffic aggregation system that solves the segment ID consistency problem in HERE traffic data.

## Problem Statement

The HERE traffic API returns data without stable segment identifiers:
- The `id` field is useless (all values = 1.0)
- Feature IDs (`fid`) change between snapshots
- Direct geometry matching fails due to minor coordinate variations
- This makes temporal aggregation impossible without a stable reference

## Solution Overview

We use OpenStreetMap (OSM) road networks as a stable baseline and perform spatial matching to assign consistent OSM way IDs to HERE traffic segments. This enables reliable temporal aggregation and analysis.

## System Architecture

### Core Components

1. **Configuration** (`config.py`)
   - City definitions with bounding boxes
   - Traffic data directories
   - Matching parameters and thresholds
   - Output path management

2. **Utilities** (`utils.py`)
   - Timestamp extraction from filenames
   - Geometry hashing for consistent matching
   - Time period parsing and filtering
   - Temporal grouping functions

3. **OSM Network Builder** (`osm_network_builder.py`)
   - Downloads OSM road networks via OSMnx
   - Covers all drivable roads within city bboxes
   - Caches networks for 30 days
   - Creates composite OSM IDs (osmid_u_v_key)

4. **Spatial Matcher** (`spatial_matcher.py`)
   - Two-stage matching pipeline:
     - Stage 1: Geometric intersection (chooses best overlap)
     - Stage 2: Nearest neighbor fallback (50m threshold)
     - Stage 3: Synthetic IDs for unmatched segments
   - Achieves >95% OSM match rate

5. **Mapping Creator** (`create_here_osm_mapping.py`)
   - Creates HERE geometry hash → OSM ID lookup table
   - One-time spatial join for efficiency
   - Generates diagnostics and quality metrics
   - Saves unmatched segments for review

6. **Traffic Aggregator** (`aggregate_traffic_with_osm.py`)
   - Flexible, parameter-driven aggregation
   - Filters by time period (e.g., morning peak: 6-9am)
   - Groups temporally (daily/weekly/monthly/all)
   - Memory-efficient incremental statistics
   - Outputs GeoPackage with OSM geometry

7. **Validation Tool** (`compare_legacy_vs_osm.py`)
   - Analyzes observation consistency
   - Validates spatial coverage
   - Creates diagnostic visualizations
   - Compares metric distributions

## Workflow

### 1. Download OSM Networks

```bash
# Download for a specific city
python osm_network_builder.py --city smg --date 20260202

# Download for all cities
python osm_network_builder.py --all --date 20260202

# Force refresh cached network
python osm_network_builder.py --city jkt --date 20260202 --force-refresh
```

**Output:**
- `osm_reference/smg_osm_reference_20260202.gpkg`
- Contains OSM road network with composite IDs

### 2. Create HERE→OSM Mapping

```bash
# Create mapping for a specific city
python create_here_osm_mapping.py --city smg --date 20260202

# Create mappings for all cities
python create_here_osm_mapping.py --all --date 20260202
```

**Output:**
- `osm_reference/smg_here_to_osm_mapping_20260202.csv` - Lookup table
- `aggregated_output/smg/diagnostics/smg_matching_diagnostics_20260202.json` - Quality metrics
- `aggregated_output/smg/diagnostics/smg_unmatched_segments_20260202.gpkg` - Unmatched segments

**Key Quality Metrics:**
- Overall OSM match rate: >95% (target)
- Nearest neighbor mean distance: <20m (target)
- Synthetic ID rate: <5%

### 3. Aggregate Traffic Data

The aggregation script is highly flexible with a CLI interface for custom analyses.

#### Example 1: Weekly Morning Peak Congestion

```bash
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric jam_factor \
  --time-period "morning_peak:6-9" \
  --temporal-grouping weekly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

**Output:** `aggregated_output/smg/osm_based/smg_morning_peak_weekly_jam_factor_20250101_20251231.gpkg`

**Schema:**
- `osm_composite_id` - OSM segment ID
- `temporal_group` - e.g., "2025-W01", "2025-W02", ...
- `jam_factor_mean`, `jam_factor_std`, `jam_factor_count`
- `jam_factor_min`, `jam_factor_max`
- `geometry` - Road segment from OSM

**Use case:** Analyze weekly congestion patterns throughout the year, identify consistently congested corridors.

#### Example 2: Monthly Evening Peak Speed

```bash
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric speed \
  --time-period "evening_peak:16-19" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

**Output:** One GPKG with 12 rows per road segment (one per month).

**Use case:** Track seasonal speed variations, compare rush hour performance across months.

#### Example 3: Daily Traffic During Special Event

```bash
python aggregate_traffic_with_osm.py \
  --city bdg \
  --metric jam_factor \
  --time-period "allday:0-24" \
  --temporal-grouping daily \
  --start-date 2025-08-17 \
  --end-date 2025-08-23 \
  --mapping-date 20260202
```

**Output:** One GPKG with 7 rows per road segment (one per day).

**Use case:** Analyze day-by-day impact of special events, compare weekday vs. weekend patterns.

#### Example 4: Overall Quarterly Statistics

```bash
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric free_flow \
  --time-period "allday:0-24" \
  --temporal-grouping all \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --mapping-date 20260202
```

**Output:** One GPKG with 1 row per road segment (aggregated across entire quarter).

**Use case:** Baseline road capacity analysis, network-wide speed limit estimation.

### 4. Validate Results

```bash
python compare_legacy_vs_osm.py \
  --city smg \
  --time-period-name morning_peak \
  --temporal-grouping weekly \
  --metric jam_factor \
  --start-date 20250101 \
  --end-date 20251231
```

**Output:**
- Console statistics on observation consistency
- Plots: `aggregated_output/smg/diagnostics/smg_observation_consistency.png`

**Validation checks:**
- Observation count consistency across temporal groups
- Spatial coverage (% of segments with data)
- Metric distribution sanity checks

## Parameters Reference

### Time Periods

Format: `"name:start_hour-end_hour"`

Common examples:
- `"morning_peak:6-9"` - Morning rush hour (6am-9am)
- `"evening_peak:16-19"` - Evening rush hour (4pm-7pm)
- `"midday:10-15"` - Midday period
- `"night:22-6"` - Night hours (not supported - use 0-6 or 22-24)
- `"allday:0-24"` - All 24 hours

**Note:** Hours must be within 0-24, and start < end. For overnight periods, run two separate aggregations.

### Temporal Groupings

- `daily` - One row per segment per day
  - Temporal group format: "2025-01-15"
  - Use for: Short-term event analysis, day-of-week patterns

- `weekly` - One row per segment per ISO week
  - Temporal group format: "2025-W03"
  - Use for: Weekly trends, identifying recurring patterns

- `monthly` - One row per segment per month
  - Temporal group format: "2025-03"
  - Use for: Seasonal analysis, long-term trends

- `all` - One row per segment (aggregated across all dates)
  - Temporal group: "all_time"
  - Use for: Overall statistics, baseline conditions

### Traffic Metrics

- `jam_factor` - Congestion ratio (1.0 = free flow, >1.0 = congestion)
  - Range: typically 1.0-10.0
  - Higher = worse congestion

- `speed` - Current traffic speed (km/h)
  - Range: 0-120 km/h typically
  - Compare with free_flow to assess congestion

- `free_flow` - Free-flow speed capacity (km/h)
  - Relatively stable over time
  - Represents road capacity

## Output File Structure

```
traffic-data/
├── osm_reference/
│   ├── smg_osm_reference_20260202.gpkg
│   ├── smg_here_to_osm_mapping_20260202.csv
│   ├── bdg_osm_reference_20260202.gpkg
│   ├── bdg_here_to_osm_mapping_20260202.csv
│   ├── jkt_osm_reference_20260202.gpkg
│   └── jkt_here_to_osm_mapping_20260202.csv
│
└── aggregated_output/
    ├── smg/
    │   ├── osm_based/
    │   │   ├── smg_morning_peak_weekly_jam_factor_20250101_20251231.gpkg
    │   │   ├── smg_evening_peak_monthly_speed_20250101_20251231.gpkg
    │   │   └── ...
    │   └── diagnostics/
    │       ├── smg_matching_diagnostics_20260202.json
    │       ├── smg_unmatched_segments_20260202.gpkg
    │       └── smg_observation_consistency.png
    │
    ├── bdg/
    │   └── [same structure]
    │
    └── jkt/
        └── [same structure]
```

## Data Quality Metrics

### Matching Quality (from diagnostics JSON)

```json
{
  "total_segments": 1076,
  "intersection_matched": 1015,
  "intersection_match_rate": 0.943,
  "nearest_neighbor_matched": 54,
  "nearest_neighbor_match_rate": 0.050,
  "synthetic_ids": 7,
  "synthetic_rate": 0.007,
  "overall_osm_match_rate": 0.993,
  "nearest_neighbor_mean_distance_m": 15.3,
  "nearest_neighbor_max_distance_m": 48.7
}
```

**Interpretation:**
- ✓ Overall match rate 99.3% exceeds 95% target
- ✓ Mean NN distance 15.3m is below 20m target
- ✓ Only 0.7% synthetic IDs (unmatched segments)

### Temporal Consistency

Run validation script to check:
- **Observation count consistency:** Segments should have similar observation counts across temporal groups (low coefficient of variation)
- **Spatial coverage:** What % of segments have data in each temporal group
- **Metric distributions:** Check for outliers and data quality issues

## Performance Considerations

### Memory Efficiency

The incremental aggregator processes one file at a time, maintaining only running statistics in memory. This enables processing of large datasets:

- **Semarang:** ~7,200 files × 1,076 segments = 7.7M segment-times ✓
- **Bandung:** ~7,200 files × 3,063 segments = 22M segment-times ✓
- **Jakarta:** ~13,857 files × 14,609 segments = 202M segment-times ✓

Expected runtime:
- Semarang: ~30 minutes
- Bandung: ~45 minutes
- Jakarta: ~2 hours

### Caching

- OSM networks are cached for 30 days
- Mapping tables are reused across multiple aggregations
- Use the same `--mapping-date` for consistent comparisons

## Common Analysis Workflows

### 1. Identify Consistently Congested Corridors

```bash
# Aggregate morning peak weekly for a year
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric jam_factor \
  --time-period "morning_peak:6-9" \
  --temporal-grouping weekly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

In QGIS:
- Open output GPKG
- Style by `jam_factor_mean`
- Filter `jam_factor_count >= 40` (ensure sufficient data)
- Identify red segments with consistently high jam factors

### 2. Before/After Comparison

```bash
# Before period (Q1)
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric speed \
  --time-period "allday:0-24" \
  --temporal-grouping all \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --mapping-date 20260202

# After period (Q2)
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric speed \
  --time-period "allday:0-24" \
  --temporal-grouping all \
  --start-date 2025-04-01 \
  --end-date 2025-06-30 \
  --mapping-date 20260202
```

In Python/R:
- Load both GPKGs
- Join on `osm_composite_id`
- Calculate speed difference: `after_speed - before_speed`
- Test for statistical significance

### 3. Peak vs. Off-Peak Comparison

```bash
# Morning peak
python aggregate_traffic_with_osm.py \
  --city bdg \
  --metric speed \
  --time-period "morning_peak:6-9" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202

# Midday (off-peak)
python aggregate_traffic_with_osm.py \
  --city bdg \
  --metric speed \
  --time-period "midday:10-15" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

Compare speed ratios to identify roads with extreme peak slowdowns.

## Dependencies

### Python Packages

```bash
pip install geopandas pandas numpy osmnx tqdm pytz shapely
```

Required versions:
- geopandas >= 0.10.0
- osmnx >= 1.2.0
- pandas >= 1.3.0
- numpy >= 1.20.0

### System Requirements

- Python 3.8+
- GDAL/OGR (typically via conda/homebrew)
- At least 4GB RAM (8GB recommended for Jakarta)

## Troubleshooting

### Issue: "Mapping file not found"

**Solution:** Run `create_here_osm_mapping.py` before aggregation:
```bash
python create_here_osm_mapping.py --city smg --date 20260202
```

### Issue: "OSM reference not found"

**Solution:** Run `osm_network_builder.py` first:
```bash
python osm_network_builder.py --city smg --date 20260202
```

### Issue: Low match rate (<95%)

**Possible causes:**
- Different CRS between HERE and OSM (should auto-reproject)
- Very sparse road network in bbox
- OSM data incomplete for the region

**Solution:** Check diagnostics JSON and unmatched segments GPKG to investigate.

### Issue: Memory error with Jakarta

**Solution:** Process smaller date ranges:
```bash
# Process Q1 only
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric jam_factor \
  --time-period "morning_peak:6-9" \
  --temporal-grouping weekly \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --mapping-date 20260202
```

Then combine outputs in post-processing.

## Future Enhancements

1. **Parallel processing** - Process multiple files concurrently
2. **Incremental updates** - Add new data without reprocessing everything
3. **Multi-city comparison** - Standardized metrics across cities
4. **Web visualization** - Interactive map dashboard
5. **Automated reporting** - Weekly/monthly traffic summaries

## References

- [OSMnx Documentation](https://osmnx.readthedocs.io/)
- [HERE Traffic API](https://developer.here.com/documentation/traffic-api/dev_guide/index.html)
- [GeoPackage Specification](https://www.geopackage.org/)

## License

This system is part of the micro-mobility traffic data collection project for Indonesian cities.
