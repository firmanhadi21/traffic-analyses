# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a traffic data collection system for Indonesian cities (Semarang, Bandung, Jakarta) using the HERE API via the `hereR` R package. The system collects real-time traffic flow data at regular intervals and stores it as GeoPackage files for analysis.

## Core Architecture

### Data Collection Pipeline

1. **R Script (`traffic_collector.R`)**: Main data collector with three separate functions:
   - `collect_traffic_data_smg()`: Semarang traffic (bbox: 110.227-110.528, -7.105--6.919)
   - `collect_traffic_data_bdg()`: Bandung traffic (bbox: 107.4688-107.8261, -7.0848--6.8294)
   - `collect_traffic_data_jkt()`: Jakarta traffic (bbox: 106.6036-107.11, -6.4096--6.0911)

2. **Shell Script (`traffic_collector.sh`)**: Orchestrator that runs the R script with correct PATH settings for Homebrew R installation

3. **Jupyter Notebook (`aggregate_all.ipynb`)**: Post-processing notebook for aggregating and analyzing collected GeoPackage files

### Data Storage Structure

- `traffic_data_smg/`: Semarang traffic GeoPackages (format: `semarang_traffic_YYYYMMDD_HHMMSS.gpkg`)
- `traffic_data_bdg/`: Bandung traffic GeoPackages (format: `bandung_traffic_YYYYMMDD_HHMMSS.gpkg`)
- `traffic_data_jkt/`: Jakarta traffic GeoPackages (format: `jakarta_traffic_YYYYMMDD_HHMMSS.gpkg`)

Each GeoPackage is a SQLite database containing:
- Spatial traffic flow data (road segments with geometry)
- Traffic attributes from HERE API
- Timestamp column recording collection time

### Timezone Handling

All timestamps use GMT+7 (Asia/Bangkok timezone) to match Indonesian local time. The R script explicitly sets `TZ="Asia/Bangkok"` for consistency.

## Running the Data Collector

### Manual Execution

```bash
# Run via shell script (recommended - handles PATH setup)
./traffic_collector.sh

# Or run R script directly
Rscript traffic_collector.R
```

### Automated Collection

The shell script is designed for cron scheduling. Each execution collects data for all three cities sequentially.

## Data Analysis

The Jupyter notebook `aggregate_all.ipynb` processes collected GeoPackages:

```bash
# Run in Jupyter environment (designed for Google Colab)
jupyter notebook aggregate_all.ipynb
```

Note: The notebook expects Google Colab environment with Drive mounting. For local execution, modify the Drive mounting cells.

## Dependencies

### R Packages
- `hereR`: HERE API interface for traffic data
- `sf`: Spatial features handling
- `lubridate`: Date/time manipulation

### Python (Jupyter notebook)
- `geopandas`: Geospatial data analysis
- `pandas`: Data manipulation

### Environment
- R installation: `/usr/local/bin/Rscript`
- HERE API key configured in traffic_collector.R line 7

## Important Implementation Notes

### API Key Management
The HERE API key is hardcoded in `traffic_collector.R:7`. When modifying, ensure the key remains valid and has appropriate rate limits for three cities.

### Error Handling
Each collection function uses `tryCatch` to handle API failures gracefully. Errors are logged to stderr with timestamps but don't halt execution of other cities.

### Bounding Box Coordinates
The bbox coordinates are tuned to cover urban areas of each city. Expanding them significantly increases API calls and data volume. The format is `c(xmin, ymin, xmax, ymax)` in WGS84 (EPSG:4326).

### GeoPackage Format
Data is saved as GeoPackage (not Shapefile) because:
- Single-file format (easier to manage than Shapefile's multiple files)
- Better attribute type support
- No column name length restrictions
- Native spatial index support

## Output Files

- `error.log`: Stderr output from scheduled runs
- `output.log`: Stdout output from scheduled runs (empty in current setup)
