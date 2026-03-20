# Getting Started with OSM-Based Traffic Aggregation

## Quick Start (5 minutes)

### 1. Check System Status

```bash
python check_system_status.py
```

This will check:
- ✓ Python dependencies installed
- ✓ Traffic data files available
- ✓ OSM networks downloaded
- ✓ Mapping tables created
- ✓ Aggregated outputs exist

### 2. Install Dependencies (if needed)

```bash
pip install -r requirements.txt
```

Required packages: geopandas, osmnx, pandas, numpy, shapely, tqdm, pytz, matplotlib, seaborn

### 3. Run Quick Test

```bash
./test_small_sample.sh
```

This runs a complete smoke test with a 1-day sample:
- Downloads OSM network for Semarang
- Creates HERE→OSM mapping
- Aggregates sample data
- Validates output quality
- Expected runtime: ~5 minutes

## Full Pipeline (30-120 minutes per city)

### Option 1: Automated Pipeline Script

The easiest way to run the complete pipeline:

```bash
# Semarang (smallest, ~30 minutes)
./quickstart_pipeline.sh --city smg

# Bandung (~45 minutes)
./quickstart_pipeline.sh --city bdg

# Jakarta (largest, ~2 hours)
./quickstart_pipeline.sh --city jkt
```

This automatically:
1. Downloads OSM network
2. Creates HERE→OSM mapping
3. Aggregates traffic data (morning peak, weekly, full year)
4. Validates results
5. Shows output file locations

### Option 2: Step-by-Step Manual Execution

#### Step 1: Download OSM Networks

```bash
# Single city
python osm_network_builder.py --city smg --date 20260202

# All cities at once
python osm_network_builder.py --all --date 20260202
```

**Output:** `osm_reference/{city}_osm_reference_20260202.gpkg`

#### Step 2: Create Mapping Tables

```bash
# Single city
python create_here_osm_mapping.py --city smg --date 20260202

# All cities at once
python create_here_osm_mapping.py --all --date 20260202
```

**Output:**
- `osm_reference/{city}_here_to_osm_mapping_20260202.csv`
- `aggregated_output/{city}/diagnostics/{city}_matching_diagnostics_20260202.json`

#### Step 3: Aggregate Traffic Data

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

#### Step 4: Validate Results

```bash
python compare_legacy_vs_osm.py \
  --city smg \
  --time-period-name morning_peak \
  --temporal-grouping weekly \
  --metric jam_factor \
  --start-date 20250101 \
  --end-date 20251231
```

**Output:** Console statistics + plots in `aggregated_output/smg/diagnostics/`

## Common Use Cases

### 1. Weekly Congestion Analysis

Track congestion patterns week-by-week throughout the year:

```bash
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric jam_factor \
  --time-period "morning_peak:6-9" \
  --temporal-grouping weekly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

**Result:** 52 rows per road segment (one per week) showing weekly congestion averages.

**Visualization in QGIS:**
1. Open output GPKG
2. Filter: `jam_factor_count >= 40` (ensure sufficient data)
3. Style by: `jam_factor_mean` with graduated colors
4. Red segments = consistently congested corridors

### 2. Monthly Speed Trends

Compare traffic speeds month-by-month:

```bash
python aggregate_traffic_with_osm.py \
  --city bdg \
  --metric speed \
  --time-period "allday:0-24" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

**Result:** 12 rows per road segment (one per month).

### 3. Special Event Analysis

Analyze day-by-day impact of events:

```bash
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric jam_factor \
  --time-period "allday:0-24" \
  --temporal-grouping daily \
  --start-date 2025-08-17 \
  --end-date 2025-08-23 \
  --mapping-date 20260202
```

**Result:** 7 rows per road segment (one per day) for the event week.

### 4. Before/After Comparison

Compare two time periods:

```bash
# Before period (Q1 2025)
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric speed \
  --time-period "allday:0-24" \
  --temporal-grouping all \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --mapping-date 20260202

# After period (Q2 2025)
python aggregate_traffic_with_osm.py \
  --city jkt \
  --metric speed \
  --time-period "allday:0-24" \
  --temporal-grouping all \
  --start-date 2025-04-01 \
  --end-date 2025-06-30 \
  --mapping-date 20260202
```

Then in Python/R, join on `osm_composite_id` and calculate differences.

### 5. Peak vs Off-Peak Comparison

```bash
# Morning peak
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric speed \
  --time-period "morning_peak:6-9" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202

# Midday (off-peak)
python aggregate_traffic_with_osm.py \
  --city smg \
  --metric speed \
  --time-period "midday:10-15" \
  --temporal-grouping monthly \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --mapping-date 20260202
```

Compare to identify roads with severe peak-hour slowdowns.

## Parameter Reference

### Time Periods

Format: `"name:start_hour-end_hour"`

Common examples:
- `"morning_peak:6-9"` - Morning rush (6am-9am)
- `"evening_peak:16-19"` - Evening rush (4pm-7pm)
- `"midday:10-15"` - Midday period (10am-3pm)
- `"night:0-6"` - Night hours (midnight-6am)
- `"allday:0-24"` - All 24 hours

### Temporal Groupings

- `daily` - One row per segment per day (format: "2025-01-15")
- `weekly` - One row per segment per week (format: "2025-W03")
- `monthly` - One row per segment per month (format: "2025-03")
- `all` - One row per segment, aggregated across all dates

### Traffic Metrics

- `jam_factor` - Congestion ratio (1.0 = free flow, higher = more congested)
- `speed` - Current traffic speed in km/h
- `free_flow` - Free-flow speed capacity in km/h

## Understanding Output Files

### GeoPackage Schema

Each aggregated output contains:

```
Columns:
  - osm_composite_id      OSM segment identifier (persistent over time)
  - temporal_group        Time grouping (e.g., "2025-W01", "2025-03", "2025-01-15")
  - {metric}_mean         Mean value of metric
  - {metric}_std          Standard deviation
  - {metric}_count        Number of observations
  - {metric}_min          Minimum value
  - {metric}_max          Maximum value
  - geometry              LineString geometry from OSM
```

### Interpreting Results

**jam_factor_mean:**
- 1.0-2.0: Light traffic
- 2.0-4.0: Moderate congestion
- 4.0-7.0: Heavy congestion
- >7.0: Severe congestion

**{metric}_count:**
- Higher count = more reliable statistics
- Filter by count >= 40 for robust analysis (ensures ≥10 observations per week)

**temporal_group:**
- Weekly: "2025-W01" (ISO week 1 of 2025)
- Monthly: "2025-03" (March 2025)
- Daily: "2025-01-15" (January 15, 2025)
- All-time: "all_time"

## Visualizing Results in QGIS

### 1. Load GeoPackage

- Layer → Add Layer → Add Vector Layer
- Browse to: `aggregated_output/{city}/osm_based/{filename}.gpkg`

### 2. Style by Metric

- Right-click layer → Properties → Symbology
- Type: Graduated
- Column: `{metric}_mean` (e.g., `jam_factor_mean`)
- Color ramp: Red-Yellow-Green (reverse for jam_factor)
- Mode: Quantile or Equal Interval

### 3. Filter by Data Quality

- Right-click layer → Filter
- Expression: `"{metric}_count" >= 40`
- This ensures sufficient observations

### 4. Create Time Series Animation (for daily/weekly/monthly)

- Use Temporal Controller in QGIS
- Set temporal field: `temporal_group`
- Animate through time periods

## Troubleshooting

### Error: "Mapping file not found"

**Solution:** Create mapping first:
```bash
python create_here_osm_mapping.py --city smg --date 20260202
```

### Error: "OSM reference not found"

**Solution:** Download OSM network first:
```bash
python osm_network_builder.py --city smg --date 20260202
```

### Error: "No files found in date range"

**Check:** Do traffic data files exist for that date range?
```bash
ls traffic_data_smg/semarang_traffic_20250115_*.gpkg
```

### Low Match Rate (<95%)

**Check diagnostics:**
```bash
cat aggregated_output/smg/diagnostics/smg_matching_diagnostics_20260202.json
```

**Review unmatched segments:**
- Open `aggregated_output/smg/diagnostics/smg_unmatched_segments_20260202.gpkg` in QGIS
- Check if they're in areas with sparse OSM coverage

### Memory Error (Jakarta)

**Solution:** Process smaller date ranges:
```bash
# Process Q1 only
python aggregate_traffic_with_osm.py \
  --city jkt \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  ...
```

## Performance Expectations

| City     | Segments | Files   | OSM Network | Mapping | Aggregation (1 year) |
|----------|----------|---------|-------------|---------|----------------------|
| Semarang | ~1,076   | ~7,200  | 2 min       | 5 min   | 30 min               |
| Bandung  | ~3,063   | ~7,200  | 3 min       | 8 min   | 45 min               |
| Jakarta  | ~14,609  | ~13,857 | 5 min       | 15 min  | 120 min              |

**Total setup time (all cities):** ~30 minutes
**Total aggregation time (one metric, one period, all cities):** ~3 hours

## Tips for Efficient Workflows

### 1. Reuse Mappings

Once mappings are created, skip those steps:

```bash
./quickstart_pipeline.sh --city smg --skip-osm --skip-mapping \
  --time-period "evening_peak:16-19"
```

### 2. Process Multiple Metrics in Parallel

```bash
# Run in separate terminals
python aggregate_traffic_with_osm.py --city smg --metric jam_factor ... &
python aggregate_traffic_with_osm.py --city smg --metric speed ... &
python aggregate_traffic_with_osm.py --city smg --metric free_flow ... &
```

### 3. Start with Small Date Ranges

Test with 1 week first, then scale up:

```bash
# Test with 1 week
--start-date 2025-01-01 --end-date 2025-01-07

# Then full year
--start-date 2025-01-01 --end-date 2025-12-31
```

## Additional Resources

- **Full Documentation:** `README_OSM_AGGREGATION.md`
- **Implementation Details:** `IMPLEMENTATION_SUMMARY.md`
- **System Status:** Run `python check_system_status.py`
- **Test System:** Run `./test_small_sample.sh`

## Getting Help

If you encounter issues:

1. Check system status: `python check_system_status.py`
2. Review diagnostics JSON files in `aggregated_output/{city}/diagnostics/`
3. Check the README files for detailed documentation
4. Verify all dependencies are installed: `pip list`

## Next Steps

Once you've successfully run the pipeline:

1. **Explore outputs in QGIS** - Visualize congestion patterns
2. **Run different time periods** - Morning vs evening peak
3. **Compare temporal groupings** - Daily vs weekly vs monthly
4. **Try all three cities** - Compare traffic patterns across cities
5. **Export to other formats** - Use ogr2ogr to convert to Shapefile/CSV if needed

Happy analyzing! 🚗📊
